"""
Who is calling: the Supabase access token, verified.

- HS256 tokens are checked against SUPABASE_JWT_SECRET (older projects).
- ES256 / RS256 tokens are checked against the project's published signing keys
  ({SUPABASE_URL}/auth/v1/.well-known/jwks.json), cached for ten minutes.
- A token is never decoded without verification. If nothing is available to verify
  it against, the request fails with 503 rather than being trusted.
- With no Supabase settings at all (keyless local development), requests run as a
  fixed demo user against the in-memory store.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from backend import config

_ASYMMETRIC = ("ES256", "RS256")
_JWKS_TTL_SECONDS = 600
_jwks_lock = threading.Lock()
_jwks_cache: dict[str, Any] = {"url": None, "fetched": 0.0, "keys": {}}


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: Optional[str] = None
    token: Optional[str] = None


DEMO_USER = CurrentUser(id="demo-user", email="demo@example.com", token=None)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _signing_keys(force: bool = False) -> dict[str, dict]:
    url = config.supabase_url()
    if not url:
        return {}
    with _jwks_lock:
        fresh = (
            _jwks_cache["url"] == url
            and time.monotonic() - _jwks_cache["fetched"] < _JWKS_TTL_SECONDS
        )
        if fresh and not force:
            return _jwks_cache["keys"]
        try:
            r = httpx.get(f"{url}/auth/v1/.well-known/jwks.json", timeout=10.0)
            r.raise_for_status()
            keys = {k["kid"]: k for k in r.json().get("keys", []) if k.get("kid")}
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sign-in could not be verified right now. Please try again.",
            ) from exc
        _jwks_cache.update(url=url, fetched=time.monotonic(), keys=keys)
        return keys


def reset_key_cache() -> None:
    with _jwks_lock:
        _jwks_cache.update(url=None, fetched=0.0, keys={})


def verify_token(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _unauthorized("Invalid token") from exc
    alg = header.get("alg")

    if alg == "HS256":
        key: Any = config.supabase_jwt_secret()
        if not key:
            raise _unauthorized("Invalid token")
    elif alg in _ASYMMETRIC:
        kid = header.get("kid")
        keys = _signing_keys()
        if kid not in keys:
            keys = _signing_keys(force=True)  # the project may have rotated its key
        key = keys.get(kid)
        if not key:
            raise _unauthorized("Invalid token")
    else:
        raise _unauthorized("Invalid token")

    try:
        claims = jwt.decode(token, key, algorithms=[alg], audience="authenticated")
    except JWTError as exc:
        raise _unauthorized("Invalid or expired token") from exc

    issuer = f"{config.supabase_url()}/auth/v1"
    if config.supabase_url() and claims.get("iss") != issuer:
        raise _unauthorized("Invalid token")
    if not claims.get("sub"):
        raise _unauthorized("Invalid token")
    return claims


def current_user(authorization: Optional[str] = Header(default=None)) -> CurrentUser:
    """FastAPI dependency. The only source of user identity in the API."""
    token = None
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            token = value.strip()

    if not config.auth_required():
        return DEMO_USER
    if not token:
        raise _unauthorized("Sign in to continue")
    claims = verify_token(token)
    return CurrentUser(id=str(claims["sub"]), email=claims.get("email"), token=token)
