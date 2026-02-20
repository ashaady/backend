from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.constants import AccessRole, AccessStatus


class SyncRequest(BaseModel):
    clerk_user_id: str = Field(min_length=1, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    requested_role: AccessRole


class AccessProfileResponse(BaseModel):
    clerk_user_id: str
    email: Optional[str]
    full_name: Optional[str]
    status: AccessStatus
    requested_role: AccessRole
    approved_role: Optional[AccessRole]
    permissions: list[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]


class PendingUserResponse(BaseModel):
    clerk_user_id: str
    email: Optional[str]
    full_name: Optional[str]
    requested_role: AccessRole
    created_at: datetime


class AdminUserResponse(BaseModel):
    clerk_user_id: str
    email: Optional[str]
    full_name: Optional[str]
    requested_role: AccessRole
    approved_role: Optional[AccessRole]
    status: AccessStatus
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class CreateAdminUserRequest(BaseModel):
    clerk_user_id: str = Field(min_length=1, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    approved_role: AccessRole


class ApproveRequest(BaseModel):
    approved_role: Optional[AccessRole] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)

