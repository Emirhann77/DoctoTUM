from __future__ import annotations

from fastapi import Depends

from backend import config
from backend.auth import DEMO_USER, CurrentUser, current_user
from backend.store import memory
from backend.store.base import Conflict, NotFound, Store, StoreError, Unavailable
from backend.store.memory import MemoryStore
from backend.store.supabase import SupabaseStore

__all__ = ["Store", "StoreError", "NotFound", "Conflict", "Unavailable", "get_store"]


def get_store(user: CurrentUser = Depends(current_user)) -> Store:
    """FastAPI dependency: the signed-in user's view of the data."""
    if config.supabase_configured() and user.token:
        return SupabaseStore(user.id, user.token)
    if user == DEMO_USER:
        memory.seed_demo_user(user.id)
    return MemoryStore(user.id, user.email)
