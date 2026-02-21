from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.constants import AccessStatus, utcnow
from app.models import AccessMessage, AccessUser
from app.schemas import MessageResponse, MessagingUserResponse, SendMessageRequest


def _index_users_by_clerk_id(users: Iterable[AccessUser]) -> dict[str, AccessUser]:
    return {user.clerk_user_id: user for user in users}


def _to_message_response(message: AccessMessage, users_by_id: dict[str, AccessUser]) -> MessageResponse:
    sender = users_by_id.get(message.sender_clerk_user_id)
    recipient = users_by_id.get(message.recipient_clerk_user_id)
    return MessageResponse(
        id=message.id,
        sender_clerk_user_id=message.sender_clerk_user_id,
        sender_email=sender.email if sender else None,
        sender_full_name=sender.full_name if sender else None,
        recipient_clerk_user_id=message.recipient_clerk_user_id,
        recipient_email=recipient.email if recipient else None,
        recipient_full_name=recipient.full_name if recipient else None,
        subject=message.subject,
        body=message.body,
        reply_to_message_id=message.reply_to_message_id,
        read_at=message.read_at,
        created_at=message.created_at,
    )


def list_organization_users(actor: AccessUser, db: Session) -> list[MessagingUserResponse]:
    users = db.scalars(
        select(AccessUser)
        .where(AccessUser.status == AccessStatus.approved.value)
        .order_by(AccessUser.full_name.asc(), AccessUser.email.asc())
    ).all()
    return [
        MessagingUserResponse(
            clerk_user_id=user.clerk_user_id,
            email=user.email,
            full_name=user.full_name,
        )
        for user in users
        if user.clerk_user_id != actor.clerk_user_id
    ]


def send_message(payload: SendMessageRequest, actor: AccessUser, db: Session) -> MessageResponse:
    recipient = db.scalar(
        select(AccessUser).where(
            AccessUser.clerk_user_id == payload.recipient_clerk_user_id,
            AccessUser.status == AccessStatus.approved.value,
        )
    )
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    if recipient.clerk_user_id == actor.clerk_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot send message to yourself")

    if payload.reply_to_message_id is not None:
        referenced = db.scalar(
            select(AccessMessage).where(AccessMessage.id == payload.reply_to_message_id)
        )
        if referenced is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced message not found")
        if actor.clerk_user_id not in {referenced.sender_clerk_user_id, referenced.recipient_clerk_user_id}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot reply to a message outside your conversation",
            )

    subject = payload.subject.strip()
    body = payload.body.strip()
    if not subject or not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject and body are required")

    message = AccessMessage(
        sender_clerk_user_id=actor.clerk_user_id,
        recipient_clerk_user_id=recipient.clerk_user_id,
        subject=subject,
        body=body,
        reply_to_message_id=payload.reply_to_message_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    users_by_id = _index_users_by_clerk_id([actor, recipient])
    return _to_message_response(message, users_by_id)


def list_inbox_messages(actor: AccessUser, db: Session) -> list[MessageResponse]:
    messages = db.scalars(
        select(AccessMessage)
        .where(AccessMessage.recipient_clerk_user_id == actor.clerk_user_id)
        .order_by(AccessMessage.created_at.desc())
    ).all()
    user_ids = {actor.clerk_user_id}
    user_ids.update(message.sender_clerk_user_id for message in messages)
    users = db.scalars(select(AccessUser).where(AccessUser.clerk_user_id.in_(user_ids))).all()
    users_by_id = _index_users_by_clerk_id(users)
    return [_to_message_response(message, users_by_id) for message in messages]


def list_sent_messages(actor: AccessUser, db: Session) -> list[MessageResponse]:
    messages = db.scalars(
        select(AccessMessage)
        .where(AccessMessage.sender_clerk_user_id == actor.clerk_user_id)
        .order_by(AccessMessage.created_at.desc())
    ).all()
    user_ids = {actor.clerk_user_id}
    user_ids.update(message.recipient_clerk_user_id for message in messages)
    users = db.scalars(select(AccessUser).where(AccessUser.clerk_user_id.in_(user_ids))).all()
    users_by_id = _index_users_by_clerk_id(users)
    return [_to_message_response(message, users_by_id) for message in messages]


def mark_message_as_read(message_id: int, actor: AccessUser, db: Session) -> MessageResponse:
    message = db.scalar(select(AccessMessage).where(AccessMessage.id == message_id))
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.recipient_clerk_user_id != actor.clerk_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update this message")

    if message.read_at is None:
        message.read_at = utcnow()
        message.updated_at = utcnow()
        db.commit()
        db.refresh(message)

    users = db.scalars(
        select(AccessUser).where(
            AccessUser.clerk_user_id.in_([message.sender_clerk_user_id, message.recipient_clerk_user_id])
        )
    ).all()
    users_by_id = _index_users_by_clerk_id(users)
    return _to_message_response(message, users_by_id)


def get_unread_messages_count(actor: AccessUser, db: Session) -> int:
    count = db.scalar(
        select(func.count())
        .select_from(AccessMessage)
        .where(
            AccessMessage.recipient_clerk_user_id == actor.clerk_user_id,
            AccessMessage.read_at.is_(None),
        )
    )
    return int(count or 0)


def mark_all_messages_as_read(actor: AccessUser, db: Session) -> int:
    timestamp = utcnow()
    result = db.execute(
        update(AccessMessage)
        .where(
            AccessMessage.recipient_clerk_user_id == actor.clerk_user_id,
            AccessMessage.read_at.is_(None),
        )
        .values(read_at=timestamp, updated_at=timestamp)
    )
    db.commit()
    return int(result.rowcount or 0)
