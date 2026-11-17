from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth import CurrentUser, current_user
from backend.models.schemas import Me
from backend.store import Store, get_store

router = APIRouter()


@router.get("/users/me", response_model=Me)
def me(user: CurrentUser = Depends(current_user), store: Store = Depends(get_store)):
    name = store.display_name() or (user.email or "").split("@")[0] or None
    return Me(id=user.id, email=user.email, display_name=name)
