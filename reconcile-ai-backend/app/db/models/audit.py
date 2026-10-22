from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditHistory(Base):
    __tablename__ = "audit_history"
    __table_args__ = (
        Index("idx_audit_history_run_created", "run_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()") )
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("reconciliation_runs.id"), nullable=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    run: Mapped["ReconciliationRun | None"] = relationship(back_populates="audit_history_entries")
    actor_user: Mapped["User | None"] = relationship(back_populates="audit_history_entries")
