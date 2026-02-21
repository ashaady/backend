from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_api_key, require_approved_user
from app.models import AccessUser
from app.schemas import (
    MessageResponse,
    MessagingUserResponse,
    ReadAllMessagesResponse,
    SendMessageRequest,
    UnreadCountResponse,
)
from app.services.messaging_service import (
    get_unread_messages_count,
    list_inbox_messages,
    list_organization_users,
    list_sent_messages,
    mark_all_messages_as_read,
    mark_message_as_read,
    send_message,
)


router = APIRouter(prefix="/messages", dependencies=[Depends(require_api_key)])


@router.get("/users", response_model=list[MessagingUserResponse])
def list_organization_users_route(
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> list[MessagingUserResponse]:
    return list_organization_users(actor, db)


@router.get("/inbox", response_model=list[MessageResponse])
def list_inbox_messages_route(
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> list[MessageResponse]:
    return list_inbox_messages(actor, db)


@router.get("/sent", response_model=list[MessageResponse])
def list_sent_messages_route(
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> list[MessageResponse]:
    return list_sent_messages(actor, db)


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_messages_count_route(
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> UnreadCountResponse:
    return UnreadCountResponse(count=get_unread_messages_count(actor, db))


@router.post("/read-all", response_model=ReadAllMessagesResponse)
def mark_all_messages_as_read_route(
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> ReadAllMessagesResponse:
    return ReadAllMessagesResponse(updated_count=mark_all_messages_as_read(actor, db))


@router.post("/send", response_model=MessageResponse)
def send_message_route(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> MessageResponse:
    return send_message(payload, actor, db)


@router.post("/{message_id}/read", response_model=MessageResponse)
def mark_message_as_read_route(
    message_id: int,
    db: Session = Depends(get_db),
    actor: AccessUser = Depends(require_approved_user),
) -> MessageResponse:
    return mark_message_as_read(message_id, actor, db)
