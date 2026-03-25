from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, Float, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    restricted_department_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)
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

# --- Nexadec Enterprise EPM Models ---

class Department(Base):
    """Organizational dimension: Hierarchy of departments/cost centers"""
    __tablename__ = "departments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)
    
    # Financial Meta
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="XOF") # e.g., 'XOF', 'USD', 'EUR'
    is_filiale: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    facts: Mapped[list["CubeFact"]] = relationship(
        "CubeFact", 
        back_populates="department", 
        foreign_keys="CubeFact.department_id"
    )

class Account(Base):
    """Chart of Accounts dimension: Revenues, Expenses, etc."""
    __tablename__ = "accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True) # e.g., '1000'
    name: Mapped[str] = mapped_column(String(255), nullable=False)           # e.g., 'Revenus'
    type: Mapped[str] = mapped_column(String(50), nullable=False)            # e.g., 'Revenue', 'Expense', 'Driver'
    
    # Metadata for calculations
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="CURRENCY") # 'CURRENCY', 'COUNT', 'PERCENT'
    pl_section: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)     # e.g., 'INTEREST_REVENUE', 'PERSONNEL_EXPENSES'
    cf_section: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)     # e.g., 'OPERATING', 'INVESTING', 'FINANCING'
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=True)
    
    facts: Mapped[list["CubeFact"]] = relationship("CubeFact", back_populates="account")

class Scenario(Base):
    """Versions dimension: Actuals 2024, Budget 2025, Forecast V1"""
    __tablename__ = "scenarios"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False) # 'Actual', 'Budget', 'Forecast'
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    facts: Mapped[list["CubeFact"]] = relationship("CubeFact", back_populates="scenario")

class CubeFact(Base):
    """The central financial data fact table"""
    __tablename__ = "cube_facts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Dimensions
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Partner Dimension (for Intra-group Eliminations)
    partner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    
    # Value
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Meta
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("access_users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # Relationships
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="facts")
    department: Mapped["Department"] = relationship(
        "Department", 
        back_populates="facts", 
        foreign_keys=[department_id]
    )
    partner: Mapped[Optional["Department"]] = relationship(
        "Department", 
        foreign_keys=[partner_id]
    )
    account: Mapped["Account"] = relationship("Account", back_populates="facts")

class AuditLog(Base):
    """Chronological logging of all data changes"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cube_fact_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True) # Soft link to preserve history even if fact changes
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("access_users.id"), nullable=True, index=True)
    
    action: Mapped[str] = mapped_column(String(50), nullable=False) # 'CREATE', 'UPDATE', 'IMPORT'
    old_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_value: Mapped[float] = mapped_column(Float, nullable=False)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)

class ExchangeRate(Base):
    """Currency conversion rates for consolidation"""
    __tablename__ = "exchange_rates"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False) # 'XOF'
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)   # 'EUR'
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # We use a fixed rate for the year as per implementation plan
    def __repr__(self):
        return f"<ExchangeRate {self.from_currency}->{self.to_currency}: {self.rate}>"

class SubmissionStatus(Base):
    """Workflow state for a specific worksheet (Scenario + Department)"""
    __tablename__ = "submission_statuses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=False)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False) # 'DRAFT', 'SUBMITTED', 'APPROVED'
    
    submitted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) # Clerk User ID
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("scenario_id", "department_id", "year", name="uq_submission_worksheet"),
    )
