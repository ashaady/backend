from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum


class AccessRole(str, Enum):
    viewer = "viewer"
    editor = "editor"
    admin = "admin"
    owner = "owner"


class AccessStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


PERMISSIONS_BY_ROLE: dict[AccessRole, list[str]] = {
    AccessRole.viewer: ["dashboard:read", "pnl:global:read"],
    AccessRole.editor: [
        "dashboard:read",
        "pnl:global:read",
        "budget:write:self_profit_center",
    ],
    AccessRole.admin: [
        "dashboard:read",
        "pnl:global:read",
        "budget:write:self_profit_center",
        "scenario:create",
        "period:lock",
        "adjustment:global",
        "user:approval:manage",
    ],
    AccessRole.owner: [
        "dashboard:read",
        "pnl:global:read",
        "budget:write:self_profit_center",
        "scenario:create",
        "period:lock",
        "adjustment:global",
        "model:structure:manage",
        "erp:import",
        "governance:manage",
    ],
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

