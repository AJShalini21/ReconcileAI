from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"
    __table_args__ = (
        CheckConstraint("status IN ('matched', 'unmatched', 'partial', 'manual_review')"),
        CheckConstraint("transaction_count >= 0"),
        CheckConstraint("status <> 'matched' OR (bank_transaction_id IS NOT NULL AND ledger_entry_id IS NOT NULL)"),
        Index("idx_results_run_status", "run_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[UUID] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    bank_transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("bank_transactions.id"), nullable=True)
    ledger_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("ledger_entries.id"), nullable=True)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    run: Mapped["ReconciliationRun"] = relationship(back_populates="reconciliation_results")
    bank_transaction: Mapped["BankTransaction | None"] = relationship(back_populates="reconciliation_results")
    ledger_entry: Mapped["LedgerEntry | None"] = relationship(back_populates="reconciliation_results")
    exceptions: Mapped[list["ExceptionRecord"]] = relationship(back_populates="result")
