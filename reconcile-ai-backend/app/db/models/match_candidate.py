from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MatchCandidate(Base):
    __tablename__ = "match_candidates"
    __table_args__ = (
        CheckConstraint("status IN ('candidate', 'accepted', 'rejected')"),
        Index("idx_match_candidates_run_status", "run_id", "status"),
        Index("idx_match_candidates_bank", "bank_transaction_id"),
        Index("idx_match_candidates_ledger", "ledger_entry_id"),
        UniqueConstraint("run_id", "bank_transaction_id", "ledger_entry_id", name="uq_match_candidates_run_bank_ledger"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[UUID] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    bank_transaction_id: Mapped[UUID] = mapped_column(ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False)
    ledger_entry_id: Mapped[UUID] = mapped_column(ForeignKey("ledger_entries.id", ondelete="CASCADE"), nullable=False)
    rule_score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    ml_score: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    run: Mapped["ReconciliationRun"] = relationship(back_populates="match_candidates")
    bank_transaction: Mapped["BankTransaction"] = relationship(back_populates="match_candidates")
    ledger_entry: Mapped["LedgerEntry"] = relationship(back_populates="match_candidates")
