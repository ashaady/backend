from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.constants import AccessRole, AccessStatus, PERMISSIONS_BY_ROLE, utcnow
from app.models import AccessMessage, AccessUser
from app.schemas import (
    AccessProfileResponse,
    AdminUserResponse,
    ApproveRequest,
    CreateAdminUserRequest,
    DeleteUserResponse,
    PendingUserResponse,
    RejectRequest,
    SyncRequest,
)


def build_profile(user: AccessUser) -> AccessProfileResponse:
    approved_role = AccessRole(user.approved_role) if user.approved_role else None
    permissions = (
        PERMISSIONS_BY_ROLE[approved_role]
        if approved_role and user.status == AccessStatus.approved.value
        else []
    )
    return AccessProfileResponse(
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        full_name=user.full_name,
        status=AccessStatus(user.status),
        requested_role=AccessRole(user.requested_role),
        approved_role=approved_role,
        permissions=permissions,
        approved_by=user.approved_by,
        approved_at=user.approved_at,
        rejection_reason=user.rejection_reason,
    )


def has_approved_admin(db: Session) -> bool:
    admin_count = db.scalar(
        select(func.count())
        .select_from(AccessUser)
        .where(
            AccessUser.status == AccessStatus.approved.value,
            AccessUser.approved_role == AccessRole.admin.value,
        )
    )
    return bool(admin_count and admin_count > 0)


def sync_user(payload: SyncRequest, db: Session) -> AccessProfileResponse:
    user = db.scalar(select(AccessUser).where(AccessUser.clerk_user_id == payload.clerk_user_id))
    approved_admin_exists = has_approved_admin(db)

    if user is None:
        user = AccessUser(
            clerk_user_id=payload.clerk_user_id,
            email=payload.email,
            full_name=payload.full_name,
            requested_role=payload.requested_role.value,
            status=AccessStatus.pending.value,
        )
        if payload.requested_role == AccessRole.admin and not approved_admin_exists:
            user.status = AccessStatus.approved.value
            user.approved_role = AccessRole.admin.value
            user.approved_by = "bootstrap-first-admin"
            user.approved_at = utcnow()
        db.add(user)
    else:
        user.email = payload.email
        user.full_name = payload.full_name
        user.updated_at = utcnow()

        if user.status == AccessStatus.pending.value:
            user.requested_role = payload.requested_role.value

            if payload.requested_role == AccessRole.admin and not approved_admin_exists:
                user.status = AccessStatus.approved.value
                user.approved_role = AccessRole.admin.value
                user.approved_by = "bootstrap-first-admin"
                user.approved_at = utcnow()

    db.commit()
    db.refresh(user)
    return build_profile(user)


def get_pending_users(db: Session) -> list[PendingUserResponse]:
    users = db.scalars(
        select(AccessUser)
        .where(AccessUser.status == AccessStatus.pending.value)
        .order_by(AccessUser.created_at.asc())
    ).all()
    return [
        PendingUserResponse(
            clerk_user_id=user.clerk_user_id,
            email=user.email,
            full_name=user.full_name,
            requested_role=AccessRole(user.requested_role),
            created_at=user.created_at,
        )
        for user in users
    ]


def get_all_users(db: Session) -> list[AdminUserResponse]:
    users = db.scalars(select(AccessUser).order_by(AccessUser.created_at.desc())).all()
    return [
        AdminUserResponse(
            clerk_user_id=user.clerk_user_id,
            email=user.email,
            full_name=user.full_name,
            requested_role=AccessRole(user.requested_role),
            approved_role=AccessRole(user.approved_role) if user.approved_role else None,
            status=AccessStatus(user.status),
            approved_by=user.approved_by,
            approved_at=user.approved_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user in users
    ]


def create_user_as_admin(
    payload: CreateAdminUserRequest,
    actor: AccessUser,
    db: Session,
) -> AccessProfileResponse:
    existing_user = db.scalar(select(AccessUser).where(AccessUser.clerk_user_id == payload.clerk_user_id))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = AccessUser(
        clerk_user_id=payload.clerk_user_id,
        email=payload.email,
        full_name=payload.full_name,
        requested_role=payload.approved_role.value,
        approved_role=payload.approved_role.value,
        status=AccessStatus.approved.value,
        approved_by=actor.clerk_user_id,
        approved_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_profile(user)


def approve_user(
    clerk_user_id: str,
    payload: ApproveRequest,
    actor: AccessUser,
    db: Session,
) -> AccessProfileResponse:
    user = db.scalar(select(AccessUser).where(AccessUser.clerk_user_id == clerk_user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    approved_role = payload.approved_role.value if payload.approved_role else user.requested_role
    user.status = AccessStatus.approved.value
    user.approved_role = approved_role
    user.approved_by = actor.clerk_user_id
    user.approved_at = utcnow()
    user.rejection_reason = None
    user.updated_at = utcnow()

    db.commit()
    db.refresh(user)
    return build_profile(user)


def reject_user(
    clerk_user_id: str,
    payload: RejectRequest,
    actor: AccessUser,
    db: Session,
) -> AccessProfileResponse:
    user = db.scalar(select(AccessUser).where(AccessUser.clerk_user_id == clerk_user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.status = AccessStatus.rejected.value
    user.approved_role = None
    user.approved_by = actor.clerk_user_id
    user.approved_at = utcnow()
    user.rejection_reason = payload.reason
    user.updated_at = utcnow()

    db.commit()
    db.refresh(user)
    return build_profile(user)


def delete_user(
    clerk_user_id: str,
    actor: AccessUser,
    db: Session,
) -> DeleteUserResponse:
    user = db.scalar(select(AccessUser).where(AccessUser.clerk_user_id == clerk_user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.clerk_user_id == actor.clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account",
        )

    is_approved_admin = (
        user.status == AccessStatus.approved.value and user.approved_role == AccessRole.admin.value
    )
    if is_approved_admin:
        approved_admin_count = db.scalar(
            select(func.count())
            .select_from(AccessUser)
            .where(
                AccessUser.status == AccessStatus.approved.value,
                AccessUser.approved_role == AccessRole.admin.value,
            )
        )
        if not approved_admin_count or approved_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last approved admin",
            )

    deleted_messages = db.execute(
        delete(AccessMessage).where(
            or_(
                AccessMessage.sender_clerk_user_id == clerk_user_id,
                AccessMessage.recipient_clerk_user_id == clerk_user_id,
            )
        )
    ).rowcount

    db.delete(user)
    db.commit()

    return DeleteUserResponse(
        clerk_user_id=clerk_user_id,
        deleted_messages_count=int(deleted_messages or 0),
    )
