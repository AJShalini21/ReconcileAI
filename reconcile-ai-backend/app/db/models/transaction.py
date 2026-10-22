from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        CheckConstraint("credit_amount >= 0"),
        CheckConstraint("debit_amount >= 0"),
        CheckConstraint("NOT (credit_amount > 0 AND debit_amount > 0)"),
        Index("idx_bank_transactions_run", "run_id"),
        Index("idx_bank_transactions_reference", "transaction_reference"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[UUID] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    import_file_id: Mapped[UUID] = mapped_column(ForeignKey("import_files.id"), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    payer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    debit_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(255), nullable=True)

    import_file: Mapped["ImportFile"] = relationship(back_populates="bank_transactions")
    match_candidates: Mapped[list["MatchCandidate"]] = relationship(back_populates="bank_transaction")
    reconciliation_results: Mapped[list["ReconciliationResult"]] = relationship(back_populates="bank_transaction")
    exceptions: Mapped[list["ExceptionRecord"]] = relationship(back_populates="bank_transaction")
