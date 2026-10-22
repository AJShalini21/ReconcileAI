from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExceptionRecord(Base):
    __tablename__ = "exceptions"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_review', 'resolved', 'ignored')"),
        Index("idx_exceptions_run_status", "run_id", "status"),
        Index("idx_exceptions_reviewed_by", "reviewed_by"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[UUID] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    bank_transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("bank_transactions.id"), nullable=True)
    ledger_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("ledger_entries.id"), nullable=True)
    result_id: Mapped[UUID | None] = mapped_column(ForeignKey("reconciliation_results.id"), nullable=True)
    entity_mapping_id: Mapped[UUID | None] = mapped_column(ForeignKey("entity_mappings.id"), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    exception_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    run: Mapped["ReconciliationRun"] = relationship(back_populates="exceptions")
    bank_transaction: Mapped["BankTransaction | None"] = relationship(back_populates="exceptions")
    ledger_entry: Mapped["LedgerEntry | None"] = relationship(back_populates="exceptions")
    result: Mapped["ReconciliationResult | None"] = relationship(back_populates="exceptions")
    entity_mapping: Mapped["EntityMapping | None"] = relationship(back_populates="exceptions")
    reviewed_by_user: Mapped["User | None"] = relationship(back_populates="reviewed_exceptions")
