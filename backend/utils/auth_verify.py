"""
Supabase JWT verification for FastAPI routes.

Supabase signs JWTs with the project JWT secret (HS256).
Set SUPABASE_JWT_SECRET in .env.local — found at:
  supabase.com → Project Settings → API → JWT Secret
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status

try:
    from jose import JWTError, jwt
    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False


def _jwt_secret() -> Optional[str]:
    return (os.getenv("SUPABASE_JWT_SECRET") or "").strip() or None


def verify_supabase_token(token: str) -> dict:
    secret = _jwt_secret()
    if not secret or not _JOSE_AVAILABLE:
        # JWT verification not configured — decode without verification (dev only)
        import base64, json
        try:
            payload_b64 = token.split(".")[1]
            padded = payload_b64 + "=" * (-len(payload_b64) % 4)
            return json.loads(base64.urlsafe_b64decode(padded))
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token invalid: {exc}")


def get_token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


# FastAPI dependency — use with Depends(require_auth)
async def require_auth(authorization: Optional[str] = Header(default=None)) -> dict:
    token = get_token_from_header(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_supabase_token(token)


# Soft dependency — returns None instead of 401 when no token (for gradual rollout)
async def optional_auth(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    token = get_token_from_header(authorization)
    if not token:
        return None
    try:
        return verify_supabase_token(token)
    except HTTPException:
        return None
