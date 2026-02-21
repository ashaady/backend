from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_api_key, require_approved_admin
from app.models import AccessUser
from app.schemas import (
    AccessProfileResponse,
    AdminUserResponse,
    ApproveRequest,
    CreateAdminUserRequest,
    DeleteUserResponse,
    PendingUserResponse,
    RejectRequest,
)
from app.services.access_service import (
    approve_user,
    create_user_as_admin,
    delete_user,
    get_all_users,
    get_pending_users,
    reject_user,
)


router = APIRouter(prefix="/admin", dependencies=[Depends(require_api_key)])


@router.get("/users/pending", response_model=list[PendingUserResponse])
def get_pending_users_route(
    db: Session = Depends(get_db),
    _: AccessUser = Depends(require_approved_admin),
) -> list[PendingUserResponse]:
    return get_pending_users(db)


@router.get("/users", response_model=list[AdminUserResponse])
def get_all_users_route(
    db: Session = Depends(get_db),
    _: AccessUser = Depends(require_approved_admin),
) -> list[AdminUserResponse]:
    return get_all_users(db)


@router.post("/users", response_model=AccessProfileResponse)
def create_user_as_admin_route(
    payload: CreateAdminUserRequest,
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_admin),
) -> AccessProfileResponse:
    return create_user_as_admin(payload, actor, db)


@router.post("/users/{clerk_user_id}/approve", response_model=AccessProfileResponse)
def approve_user_route(
    clerk_user_id: str,
    payload: ApproveRequest,
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_admin),
) -> AccessProfileResponse:
    return approve_user(clerk_user_id, payload, actor, db)


@router.post("/users/{clerk_user_id}/reject", response_model=AccessProfileResponse)
def reject_user_route(
    clerk_user_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_admin),
) -> AccessProfileResponse:
    return reject_user(clerk_user_id, payload, actor, db)


@router.delete("/users/{clerk_user_id}", response_model=DeleteUserResponse)
def delete_user_route(
    clerk_user_id: str,
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_admin),
) -> DeleteUserResponse:
    return delete_user(clerk_user_id, actor, db)
