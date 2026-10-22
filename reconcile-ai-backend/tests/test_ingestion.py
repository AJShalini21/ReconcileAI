from fastapi.testclient import TestClient
import pytest

from app.auth.dependencies import get_current_user
from app.db.models import (
    BankTransaction,
    ImportFile,
    LedgerEntry,
    ReconciliationRun,
    User,
)
from app.db.session import SessionLocal
from app.main import app


@pytest.fixture(autouse=True)
def authenticate_as_demo_user():
    with SessionLocal() as session:
        demo_user = session.query(User).filter_by(email="demo@reconcileai.test").one()

    app.dependency_overrides[get_current_user] = lambda: demo_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _authenticated_client() -> TestClient:
    client = TestClient(app)
    client.headers.update({"Origin": "http://localhost:8443"})
    return client


def test_reconciliation_validation_route_accepts_csvs() -> None:
    bank_csv = (
        "transaction_reference,transaction_date,description,amount\n"
        "TXN-001,2026-10-10,Invoice payment,125.50\n"
        "TXN-002,2026-10-11,Refund,-25.00\n"
    )
    ledger_csv = (
        "ledger_entry_id,entry_date,description,amount\n"
        "LED-001,2026-10-10,Invoice payment,125.50\n"
        "LED-002,2026-10-11,Refund,25.00\n"
    )

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["fileName"] == "bank.csv"
    assert payload["validRows"] >= 1
    assert "invalidRows" not in payload


def test_reconciliation_validation_skips_malformed_rows_without_tracking_them() -> None:
    bank_csv = (
        "transaction_reference,transaction_date,description,amount\n"
        "TXN-VALID,2026-10-10,Invoice payment,125.50\n"
        "TXN-BAD,2026-10-11,Malformed amount,not-a-number\n"
    )
    ledger_csv = (
        "ledger_entry_id,entry_date,description,amount\n"
        "LED-VALID,2026-10-10,Invoice payment,125.50\n"
    )

    response = _authenticated_client().post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validRows"] == 2
    assert "invalidRows" not in payload
    assert "errors" not in payload

    with SessionLocal() as session:
        bank_import = (
            session.query(ImportFile)
            .filter_by(id=payload["bank_import_id"])
            .one()
        )
        bank_records = (
            session.query(BankTransaction)
            .filter_by(import_file_id=bank_import.id)
            .all()
        )

    assert bank_import.total_rows == 1
    assert len(bank_records) == 1
    assert bank_records[0].transaction_reference == "TXN-VALID"


def test_reconciliation_validation_accepts_reference_number_and_credit_amount() -> None:
    bank_csv = (
        "reference_number,transaction_date,description,credit_amount\n"
        "TXN-001,2026-10-10,Invoice payment,125.50\n"
        "TXN-002,2026-10-11,Refund,25.00\n"
    )
    ledger_csv = (
        "ledger_entry_id,entry_date,description,amount\n"
        "LED-001,2026-10-10,Invoice payment,125.50\n"
        "LED-002,2026-10-11,Refund,25.00\n"
    )

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["validRows"] == 4
    assert "invalidRows" not in payload


def test_reconciliation_validation_accepts_ledger_transaction_date_alias() -> None:
    bank_csv = (
        "transaction_reference,transaction_date,description,amount\n"
        "TXN-001,2026-10-10,Invoice payment,125.50\n"
        "TXN-002,2026-10-11,Refund,-25.00\n"
    )
    ledger_csv = (
        "ledger_entry_id,transaction_date,description,amount\n"
        "LED-001,2026-10-10,Invoice payment,125.50\n"
        "LED-002,2026-10-11,Refund,25.00\n"
    )

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["validRows"] == 4
    assert "invalidRows" not in payload


def test_reconciliation_validation_persists_valid_rows() -> None:
    bank_csv = (
        "transaction_reference,transaction_date,description,amount\n"
        "TXN-VALIDATE-001,2026-10-10,Invoice payment,125.50\n"
    )
    ledger_csv = (
        "ledger_entry_id,transaction_date,description,amount\n"
        "LED-VALIDATE-001,2026-10-10,Invoice payment,125.50\n"
    )

    with SessionLocal() as session:
        before_run_count = session.query(ReconciliationRun).count()
        before_bank_count = session.query(BankTransaction).count()
        before_ledger_count = session.query(LedgerEntry).count()

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200

    with SessionLocal() as session:
        after_bank_count = session.query(BankTransaction).count()
        after_ledger_count = session.query(LedgerEntry).count()
        after_run_count = session.query(ReconciliationRun).count()

    assert after_bank_count >= before_bank_count + 1
    assert after_ledger_count >= before_ledger_count + 1
    assert after_run_count >= before_run_count + 1


def test_reconciliation_upload_persists_valid_csv_rows() -> None:
    bank_csv = (
        "transaction_reference,transaction_date,description,amount\n"
        "TXN-001,2026-10-10,Invoice payment,125.50\n"
        "TXN-002,2026-10-11,Refund,-25.00\n"
    )
    ledger_csv = (
        "ledger_entry_id,entry_date,description,amount\n"
        "LED-001,2026-10-10,Invoice payment,125.50\n"
        "LED-002,2026-10-11,Refund,25.00\n"
    )

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["fileName"] == "bank.csv"
    assert payload["validRows"] >= 1
    assert "invalidRows" not in payload


def test_ledger_persists_without_description_column() -> None:
    bank_csv = (
        "transaction_reference,transaction_date,description,amount\n"
        "TXN-NODESC-001,2026-10-10,Invoice payment,125.50\n"
    )
    # Notice: No description column at all! Uses invoice_id, customer_name, payment_reference
    ledger_csv = (
        "invoice_id,entry_date,payment_reference,customer_name,amount\n"
        "INV-NODESC-101,2026-10-10,REF-1234,Acme Corp,125.50\n"
    )

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("bank.csv", bank_csv, "text/csv"),
            "ledgerFile": ("ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["validRows"] == 2

    with SessionLocal() as session:
        entry = (
            session.query(LedgerEntry)
            .filter(LedgerEntry.invoice_id == "INV-NODESC-101")
            .first()
        )
        assert entry is not None
        assert entry.customer_name == "Acme Corp"
        assert entry.payment_reference == "REF-1234"
        assert float(entry.credit_amount) == 125.50
        assert float(entry.debit_amount or 0) == 0


def test_ledger_with_inr_and_dd_mm_yyyy_dates() -> None:
    bank_csv = (
        "reference_number,transaction_date,particulars,amount\n"
        "TXN-INR-SUCCESS-001,22-04-2026,Payment received,352042.00\n"
    )
    ledger_csv = (
        'voucher_no,posting_date,particulars,customer_name,net_amount\n'
        'VCH-INR-SUCCESS-001,22-04-2026,NEFT CREDIT,Vertex Infotech Technologies Pvt Ltd,"₹ 3,52,042.00"\n'
    )

    client = _authenticated_client()
    response = client.post(
        "/api/v1/reconciliations/validate",
        files={
            "bankFile": ("nexora_bank_transactions.csv", bank_csv, "text/csv"),
            "ledgerFile": ("nexora_company_ledger.csv", ledger_csv, "text/csv"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "validated"
    assert payload["validRows"] == 2

    with SessionLocal() as session:
        entry = (
            session.query(LedgerEntry)
            .filter(LedgerEntry.ledger_entry_id == "VCH-INR-SUCCESS-001")
            .first()
        )
        assert entry is not None
        assert entry.customer_name == "Vertex Infotech Technologies Pvt Ltd"
        assert float(entry.credit_amount) == 352042.00
        assert float(entry.debit_amount or 0) == 0
        assert str(entry.entry_date) == "2026-04-22"
