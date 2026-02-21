from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ACCESS_BACKEND_API_KEY
from app.constants import AccessRole, AccessStatus
from app.db import SessionLocal
from app.models import AccessUser


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="x-api-key")) -> None:
    if x_api_key != ACCESS_BACKEND_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def require_approved_user(
    db: Session = Depends(get_db),
    x_actor_clerk_user_id: Optional[str] = Header(default=None, alias="x-actor-clerk-user-id"),
) -> AccessUser:
    if not x_actor_clerk_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing actor id")

    actor = db.scalar(select(AccessUser).where(AccessUser.clerk_user_id == x_actor_clerk_user_id))
    if actor is None or actor.status != AccessStatus.approved.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only approved users can perform this action")

    return actor


def require_approved_admin(
    db: Session = Depends(get_db),
    x_actor_clerk_user_id: Optional[str] = Header(default=None, alias="x-actor-clerk-user-id"),
) -> AccessUser:
    actor = require_approved_user(db=db, x_actor_clerk_user_id=x_actor_clerk_user_id)
    if actor.approved_role != AccessRole.admin.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only approved admins can perform this action")

    return actor
