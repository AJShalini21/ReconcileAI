from __future__ import annotations

import logging
import json
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import insert, text
from decimal import Decimal
from starlette.concurrency import run_in_threadpool

from app.db.models import (
    AuditHistory,
    BankTransaction,
    ImportFile,
    LedgerEntry,
    ReconciliationRun,
)
from app.db.session import SessionLocal
from app.modules.ingestion.parser import read_csv_rows, required_columns_present
from app.modules.ingestion.validator import (
    BANK_ALLOWED_ALIASES,
    BANK_REQUIRED_COLUMNS,
    LEDGER_ALLOWED_ALIASES,
    LEDGER_REQUIRED_COLUMNS,
    bank_columns_present,
    ledger_columns_present,
    normalize_bank_row,
    normalize_ledger_row,
)
from app.modules.reconciliation.schemas import ReconciliationConfig

logger = logging.getLogger(__name__)

def persist_validated_imports(
    bank_file: UploadFile,
    ledger_file: UploadFile,
    valid_bank_rows: list[dict[str, Any]],
    valid_ledger_rows: list[dict[str, Any]],
    owner_user_id: UUID,
) -> dict[str, str]:
    """Persist normalized records and import metadata for one upload atomically."""
    import time

    with SessionLocal() as session:
        try:
            session.execute(text("SET LOCAL statement_timeout = '15000'"))
            session.execute(text("SET LOCAL lock_timeout = '10000'"))

            created_at = datetime.now(timezone.utc)

            run = ReconciliationRun(
                created_by=owner_user_id,
                status="pending",
                started_at=created_at,
                created_at=created_at,
            )
            session.add(run)
            session.flush()

            bank_import = ImportFile(
                run_id=run.id,
                file_type="bank",
                file_name=bank_file.filename or "bank.csv",
                status="processed",
                total_rows=len(valid_bank_rows),
                created_at=created_at,
            )
            ledger_import = ImportFile(
                run_id=run.id,
                file_type="ledger",
                file_name=ledger_file.filename or "ledger.csv",
                status="processed",
                total_rows=len(valid_ledger_rows),
                created_at=created_at,
            )
            session.add_all([bank_import, ledger_import])
            session.flush()

            # Prepare bank records
            bank_records = []
            for row in valid_bank_rows:
                txn_date = row["transaction_date"]
                if isinstance(txn_date, str):
                    txn_date = date.fromisoformat(txn_date)

                bank_records.append({
                    "run_id": run.id,
                    "import_file_id": bank_import.id,
                    "transaction_reference": row.get(
                        "transaction_reference"
                    ),
                    "transaction_date": txn_date,
                    "payer_name": row.get("counterparty_name"),
                    "credit_amount": Decimal(str(row["credit_amount"])),
                    "debit_amount": Decimal(str(row["debit_amount"])),
            
                    "description": row.get("description"),
                    "reference_number": row.get("payment_reference"),
                })

            # Prepare ledger records
            ledger_records = []
            for row in valid_ledger_rows:
                entry_date = row["entry_date"]
                if isinstance(entry_date, str):
                    entry_date = date.fromisoformat(entry_date)

                credit_amount = Decimal(str(row["credit_amount"] or 0))
                debit_amount = Decimal(str(row["debit_amount"] or 0))
                ledger_records.append({
                    "run_id": run.id,
                    "import_file_id": ledger_import.id,
                    "ledger_entry_id": row.get("ledger_entry_id"),
                    "invoice_id": row.get("invoice_id"),
                    "customer_id": row.get("customer_id"),
                    "customer_name": row.get("customer_name"),
                    "entry_date": entry_date,
                    "credit_amount": credit_amount,
                    "debit_amount": debit_amount,
                    "payment_reference": row.get("payment_reference"),
                })

            batch_size = 1000

            # Bulk insert bank transactions
            start = time.perf_counter()
            logger.info(
                "BANK_INSERT_START rows=%d batch_size=%d",
                len(bank_records),
                batch_size,
            )

            for offset in range(0, len(bank_records), batch_size):
                session.execute(
                    insert(BankTransaction),
                    bank_records[offset:offset + batch_size],
                )

            logger.info(
                "BANK_INSERT_END rows=%d elapsed_seconds=%.2f",
                len(bank_records),
                time.perf_counter() - start,
            )

            # Bulk insert ledger entries
            start = time.perf_counter()
            logger.info(
                "LEDGER_INSERT_START rows=%d batch_size=%d",
                len(ledger_records),
                batch_size,
            )

            for offset in range(0, len(ledger_records), batch_size):
                session.execute(
                    insert(LedgerEntry),
                    ledger_records[offset:offset + batch_size],
                )

            logger.info(
                "LEDGER_INSERT_END rows=%d elapsed_seconds=%.2f",
                len(ledger_records),
                time.perf_counter() - start,
            )

            # Record files validated audit entry
            session.add(
                AuditHistory(
                    run_id=run.id,
                    actor_user_id=owner_user_id,
                    action="files_validated",
                    description=f"Validated bank file '{bank_file.filename or 'bank.csv'}' ({len(bank_records)} records) and ledger file '{ledger_file.filename or 'ledger.csv'}' ({len(ledger_records)} records).",
                    created_at=datetime.now(timezone.utc),
                )
            )

            # Commit the entire import atomically
            start = time.perf_counter()
            logger.info("COMMIT_START")

            session.commit()

            logger.info(
                "COMMIT_END elapsed_seconds=%.2f",
                time.perf_counter() - start,
            )

            return {
                "run_id": str(run.id),
                "bank_import_id": str(bank_import.id),
                "ledger_import_id": str(ledger_import.id),
            }

        except Exception:
            session.rollback()
            logger.exception("Import persistence failed; transaction rolled back")
            raise

async def validate_uploaded_files(
    bank_file: UploadFile,
    ledger_file: UploadFile,
    owner_user_id: UUID,
) -> dict[str, Any]:
    if not bank_file or not ledger_file:
        raise ValueError("Both bank and ledger files are required.")

    print("1. Starting validation")
    
    bank_rows = await read_csv_rows(bank_file)
    print("2. Bank CSV parsed")

    ledger_rows = await read_csv_rows(ledger_file)
    print("3. Ledger CSV parsed")

    if not bank_rows:
        raise ValueError("Bank file is empty or missing a valid header row.")
    if not ledger_rows:
        raise ValueError("Ledger file is empty or missing a valid header row.")

    bank_headers = set(bank_rows[0].keys())
    ledger_headers = set(ledger_rows[0].keys())

    if not bank_columns_present(bank_headers):
        missing = sorted(
            column
            for column in BANK_REQUIRED_COLUMNS
            if not any(alias in bank_headers for alias in BANK_ALLOWED_ALIASES[column])
        )
        raise ValueError(f"Bank CSV is missing required columns: {', '.join(missing)}")
    if not ledger_columns_present(ledger_headers):
        missing = sorted(
            column
            for column in LEDGER_REQUIRED_COLUMNS
            if not any(alias in ledger_headers for alias in LEDGER_ALLOWED_ALIASES[column])
        )
        raise ValueError(f"Ledger CSV is missing required columns: {', '.join(missing)}")

    valid_bank_rows: list[dict[str, Any]] = []
    bank_errors: list[str] = []
    for idx, row in enumerate(bank_rows, start=2):
        try:
            valid_bank_rows.append(normalize_bank_row(row, row_index=idx - 1))
        except ValueError as exc:
            bank_errors.append(f"Row {idx}: {exc}")

    valid_ledger_rows: list[dict[str, Any]] = []
    ledger_errors: list[str] = []
    for idx, row in enumerate(ledger_rows, start=2):
        try:
            valid_ledger_rows.append(normalize_ledger_row(row, row_index=idx - 1))
        except ValueError as exc:
            ledger_errors.append(f"Row {idx}: {exc}")

    if not valid_bank_rows:
        sample = "; ".join(bank_errors[:3]) if bank_errors else "no valid rows"
        raise ValueError(f"No valid records found in bank CSV: {sample}")

    if not valid_ledger_rows:
        sample = "; ".join(ledger_errors[:3]) if ledger_errors else "no valid rows"
        raise ValueError(f"No valid records found in ledger CSV: {sample}")

    print("4. Before persisting validated imports")
    logger.info("Dispatching import persistence to a worker thread")
    persisted = await run_in_threadpool(
        persist_validated_imports,
        bank_file,
        ledger_file,
        valid_bank_rows,
        valid_ledger_rows,
        owner_user_id,
    )
    logger.info("Import persistence returned successfully")

    print("5. Validation completed")
    return {
        "fileName": bank_file.filename or ledger_file.filename,
        "status": "validated",
        "validRows": len(valid_bank_rows) + len(valid_ledger_rows),
        "run_id": persisted["run_id"],
        "bank_import_id": persisted["bank_import_id"],
        "ledger_import_id": persisted["ledger_import_id"],
    }

async def process_uploaded_files(
    bank_file: UploadFile,
    ledger_file: UploadFile,
    owner_user_id: UUID,
    config: ReconciliationConfig | None = None,
) -> dict[str, Any]:
    validation = await validate_uploaded_files(bank_file, ledger_file, owner_user_id)
    run_id = validation["run_id"]
    from app.modules.reconciliation.service import run_reconciliation

    outcome = await run_in_threadpool(run_reconciliation, run_id, owner_user_id, config)
    completed_at = datetime.now(timezone.utc)

    return {
        "fileName": validation["fileName"],
        "status": "validated",
        "validRows": validation["validRows"],
        "run_id": str(run_id),
        "created_at": completed_at.isoformat(),
        "matchedCount": outcome.matched_count,
        "pendingReviewCount": outcome.pending_review_count,
        "exceptionCount": outcome.exception_count,
        "unmatchedCount": outcome.unmatched_count,
    }