from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_api_key
from app.schemas import AccessProfileResponse, SyncRequest
from app.services.access_service import sync_user


router = APIRouter(prefix="/auth", dependencies=[Depends(require_api_key)])


@router.post("/sync", response_model=AccessProfileResponse)
def sync_user_route(payload: SyncRequest, db: Session = Depends(get_db)) -> AccessProfileResponse:
    return sync_user(payload, db)

