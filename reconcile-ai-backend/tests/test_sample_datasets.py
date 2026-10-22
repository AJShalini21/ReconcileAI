import os
from decimal import Decimal
import pytest

from app.modules.ingestion.validator import (
    bank_columns_present,
    ledger_columns_present,
    normalize_bank_row,
    normalize_ledger_row,
)
from app.modules.ingestion.parser import read_csv_rows
from app.modules.reconciliation.engine import reconcile
from app.modules.reconciliation.schemas import TransactionInput, ReconciliationConfig

class MockUploadFile:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            self._content = f.read()

    async def seek(self, pos):
        pass

    async def read(self):
        return self._content

import asyncio

@pytest.mark.parametrize("records", [100, 150, 200])
def test_sample_dataset_conformance_and_engine(records: int):
    async def _runner():
        # Locate dataset files
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "reconcile-ai-frontend", "public", "sample-data"))
        bank_path = os.path.join(base_dir, f"dataset-{records}-bank.csv")
        ledger_path = os.path.join(base_dir, f"dataset-{records}-ledger.csv")
        
        assert os.path.exists(bank_path), f"Bank file missing: {bank_path}"
        assert os.path.exists(ledger_path), f"Ledger file missing: {ledger_path}"
        
        bank_raw = await read_csv_rows(MockUploadFile(bank_path))
        ledger_raw = await read_csv_rows(MockUploadFile(ledger_path))
        
        assert len(bank_raw) == records
        assert len(ledger_raw) == records
        
        bank_headers = set(bank_raw[0].keys())
        ledger_headers = set(ledger_raw[0].keys())
        
        # 1. Schema & Header conformance: No currency column and required columns present
        assert "currency" not in bank_headers, f"Currency column found in bank CSV: {bank_headers}"
        assert "currency" not in ledger_headers, f"Currency column found in ledger CSV: {ledger_headers}"
        assert bank_columns_present(bank_headers)
        assert ledger_columns_present(ledger_headers)
        
        # 2. Row normalization validation
        bank_transactions = []
        for idx, row in enumerate(bank_raw, 1):
            norm = normalize_bank_row(row, row_index=idx)
            bank_transactions.append(
                TransactionInput(
                    id=norm["transaction_reference"] or f"TXN-{idx:05d}",
                    source="bank",
                    transaction_date=norm["transaction_date"],
                    description=norm["description"],
                    credit_amount=norm["credit_amount"],
                    debit_amount=norm["debit_amount"],
                    currency="USD",
                    entity_name=norm["counterparty_name"],
                    references={norm["transaction_reference"], norm["payment_reference"]} - {None, ""},
                )
            )
            
        ledger_entries = []
        for idx, row in enumerate(ledger_raw, 1):
            norm = normalize_ledger_row(row, row_index=idx)
            ledger_entries.append(
                TransactionInput(
                    id=norm["ledger_entry_id"] or f"LED-{idx:05d}",
                    source="ledger",
                    transaction_date=norm["entry_date"],
                    description=norm["description"],
                    credit_amount=norm["credit_amount"],
                    debit_amount=norm["debit_amount"],
                    currency="USD",
                    entity_name=norm["customer_name"],
                    references={norm["ledger_entry_id"], norm["payment_reference"], norm["invoice_id"]} - {None, ""},
                )
            )
            
        # 3. Engine evaluation
        config = ReconciliationConfig(
            date_window_days=3,
            reference_threshold=0.88,
            reference_free_threshold=0.82,
            minimum_score_margin=0.10,
            entity_candidate_threshold=0.70,
        )
        outcome = reconcile(f"RUN-TEST-{records}", bank_transactions, ledger_entries, config)
        
        assert outcome.matched_count > 0
        assert outcome.pending_review_count + outcome.exception_count + outcome.unmatched_count > 0

    asyncio.run(_runner())
