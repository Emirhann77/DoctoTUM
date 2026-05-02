from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.database import db

router = APIRouter()


@router.get("/users/me")
def get_demo_user(user_id: int = Query(1, ge=1)):
    u = db.get_user(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": u.id, "full_name": u.full_name, "email": u.email}
