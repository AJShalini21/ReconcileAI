import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import (
    User,
    ReconciliationRun,
    BankTransaction,
    LedgerEntry,
    MatchCandidate,
    ExceptionRecord,
)
from app.db.session import get_db
from app.auth.dependencies import get_current_user
from app.modules.analyzer.gemini_service import (
    generate_fallback_analysis,
    analyze_discrepancy_with_gemini,
)
from tests.test_workspace import _session_factory


@pytest.fixture
def db_session():
    factory = _session_factory()
    with factory() as session:
        yield session


def test_fallback_analysis_collision_detection():
    bank_tx = {
        "id": "bt-1",
        "date": "2026-05-23",
        "amount": "15000.00",
        "payer_name": "Cedar Retail Group",
        "reference_number": "PAY-1150-0045",
    }
    candidate_ledger = {
        "id": "le-1",
        "date": "2026-05-23",
        "amount": "14825.00",
        "customer_name": "Cedar Retail Group",
        "payment_reference": "PAY-1150-0045",
    }
    competing_txs = [
        {
            "id": "bt-2",
            "date": "2026-05-22",
            "amount": "14825.00",
            "payer_name": "Cedar Retail Stores",
            "reference_number": "PAY-1142-PO9",
        }
    ]
    discrepancy_info = {
        "amount_diff": "INR 175.00",
        "date_diff": "Same day",
        "entity_diff": "Exact match",
        "ref_diff": "Match",
    }

    result = generate_fallback_analysis(
        bank_tx, candidate_ledger, competing_txs, discrepancy_info
    )
    assert result["has_collision"] is True
    assert "Competing Claim" in result["collision_warning"]
    assert "175.00" in result["explanation"]
    assert "competing transaction" in result["suggestion"]


def test_analyze_endpoint_updates_database(db_session: Session):
    now = datetime.now(timezone.utc)
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        email="reconciler@example.com",
        full_name="Reconciler User",
        is_active=True,
        created_at=now,
    )
    db_session.add(test_user)

    file_id = uuid.uuid4()
    run = ReconciliationRun(
        id=uuid.uuid4(),
        created_by=user_id,
        status="completed",
        created_at=now,
    )
    db_session.add(run)

    bank_tx = BankTransaction(
        id=uuid.uuid4(),
        run_id=run.id,
        import_file_id=file_id,
        transaction_date=date(2026, 5, 23),
        credit_amount=Decimal("15000.00"),
        debit_amount=Decimal("0"),
        payer_name="Cedar Retail Group",
        reference_number="PAY-1150-0045",
        description="Invoice payment",
    )
    ledger_entry = LedgerEntry(
        id=uuid.uuid4(),
        run_id=run.id,
        import_file_id=file_id,
        entry_date=date(2026, 5, 23),
        credit_amount=Decimal("14825.00"),
        debit_amount=Decimal("0"),
        customer_name="Cedar Retail Group",
        payment_reference="PAY-1150-0045",
        invoice_id="INV-1150-0045",
    )
    db_session.add_all([bank_tx, ledger_entry])
    db_session.flush()

    candidate = MatchCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        bank_transaction_id=bank_tx.id,
        ledger_entry_id=ledger_entry.id,
        rule_score=Decimal("0.92"),
        status="candidate",
        created_at=now,
    )
    exception = ExceptionRecord(
        id=uuid.uuid4(),
        run_id=run.id,
        bank_transaction_id=bank_tx.id,
        ledger_entry_id=ledger_entry.id,
        exception_type="amount_mismatch",
        status="open",
        suggestion="Review discrepancy",
        explanation=None,
        ai_analyzed_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([candidate, exception])
    db_session.commit()

    def override_get_db():
        yield db_session

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    response = client.post(
        f"/api/v1/reconciliations/{run.id}/exceptions/{exception.id}/analyze",
        headers={"Origin": "http://localhost:5173"},
        json={"candidate_id": str(candidate.id)},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    data = response.json()
    assert "explanation" in data
    assert "suggestion" in data
    assert len(data["explanation"]) > 0

    # Verify that the DB was populated
    db_session.refresh(exception)
    assert exception.explanation is not None
    assert exception.ai_analyzed_at is not None
    assert exception.suggestion is not None
