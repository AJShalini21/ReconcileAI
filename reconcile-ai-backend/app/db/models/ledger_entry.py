from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index("idx_ledger_entries_run", "run_id"),
        Index("idx_ledger_entries_invoice", "invoice_id"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[UUID] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    import_file_id: Mapped[UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    ledger_entry_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    debit_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    import_file: Mapped["ImportFile"] = relationship(back_populates="ledger_entries")
    match_candidates: Mapped[list["MatchCandidate"]] = relationship(back_populates="ledger_entry")
    reconciliation_results: Mapped[list["ReconciliationResult"]] = relationship(back_populates="ledger_entry")
    exceptions: Mapped[list["ExceptionRecord"]] = relationship(back_populates="ledger_entry")
