from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import AccessStatus, utcnow
from app.db import Base


class AccessUser(Base):
    __tablename__ = "access_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requested_role: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default=AccessStatus.pending.value)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class AccessMessage(Base):
    __tablename__ = "access_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
