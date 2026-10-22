from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    reconciliation_runs: Mapped[list["ReconciliationRun"]] = relationship(back_populates="created_by_user")
    entity_mappings: Mapped[list["EntityMapping"]] = relationship(
        back_populates="owner_user",
        foreign_keys="EntityMapping.owner_user_id",
    )
    approved_entity_mappings: Mapped[list["EntityMapping"]] = relationship(
        back_populates="approved_by_user",
        foreign_keys="EntityMapping.approved_by",
    )
    reviewed_exceptions: Mapped[list["ExceptionRecord"]] = relationship(back_populates="reviewed_by_user")
    audit_history_entries: Mapped[list["AuditHistory"]] = relationship(back_populates="actor_user")
