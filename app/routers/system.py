from __future__ import annotations

from fastapi import APIRouter

from app.constants import PERMISSIONS_BY_ROLE


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/roles")
def list_roles() -> dict[str, list[str]]:
    return {role.value: permissions for role, permissions in PERMISSIONS_BY_ROLE.items()}

