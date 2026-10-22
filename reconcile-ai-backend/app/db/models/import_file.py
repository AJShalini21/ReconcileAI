from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ImportFile(Base):
    __tablename__ = "import_files"
    __table_args__ = (
        CheckConstraint("file_type IN ('bank', 'ledger')"),
        CheckConstraint("status IN ('uploaded', 'processing', 'processed', 'failed')"),
        CheckConstraint("total_rows >= 0"),
        Index("idx_import_files_run", "run_id"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()")
    run_id: Mapped[UUID] = mapped_column(ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="NOW()")

    run: Mapped["ReconciliationRun"] = relationship(back_populates="import_files")
    bank_transactions: Mapped[list["BankTransaction"]] = relationship(back_populates="import_file")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="import_file")
