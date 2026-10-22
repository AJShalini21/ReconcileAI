from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')"),
        CheckConstraint("completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at"),
        Index("idx_runs_created_at", "created_at"),
        Index("idx_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    created_by_user: Mapped["User"] = relationship(back_populates="reconciliation_runs")
    import_files: Mapped[list["ImportFile"]] = relationship(back_populates="run")
    match_candidates: Mapped[list["MatchCandidate"]] = relationship(back_populates="run")
    reconciliation_results: Mapped[list["ReconciliationResult"]] = relationship(back_populates="run")
    exceptions: Mapped[list["ExceptionRecord"]] = relationship(back_populates="run")
    audit_history_entries: Mapped[list["AuditHistory"]] = relationship(back_populates="run")
