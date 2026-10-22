import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.db.models import (
    AuditHistory,
    BankTransaction,
    EntityMapping,
    ExceptionRecord,
    ImportFile,
    LedgerEntry,
    ReconciliationResult,
    ReconciliationRun,
    User,
)
from app.db.session import get_db
from app.main import app
from app.modules.workspace.router import get_workspace


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        schema = """
            CREATE TABLE users (
                id CHAR(32) PRIMARY KEY,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255),
                is_active BOOLEAN NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE reconciliation_runs (
                id CHAR(32) PRIMARY KEY,
                created_by CHAR(32) NOT NULL,
                status VARCHAR(30) NOT NULL,
                started_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE bank_transactions (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32) NOT NULL,
                import_file_id CHAR(32) NOT NULL,
                transaction_reference VARCHAR(255),
                transaction_date DATE NOT NULL,
                payer_name VARCHAR(255),
                credit_amount NUMERIC(18, 2) NOT NULL,
                debit_amount NUMERIC(18, 2) NOT NULL,
                description TEXT,
                reference_number VARCHAR(255)
            );
            CREATE TABLE ledger_entries (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32) NOT NULL,
                import_file_id CHAR(32) NOT NULL,
                ledger_entry_id VARCHAR(255),
                invoice_id VARCHAR(255),
                customer_id INTEGER,
                customer_name VARCHAR(255),
                entry_date DATE NOT NULL,
                credit_amount NUMERIC(18, 2) NOT NULL,
                debit_amount NUMERIC(18, 2),
                payment_reference VARCHAR(255)
            );
            CREATE TABLE reconciliation_results (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32) NOT NULL,
                bank_transaction_id CHAR(32),
                ledger_entry_id CHAR(32),
                transaction_count INTEGER NOT NULL,
                status VARCHAR(30) NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE match_candidates (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32) NOT NULL,
                bank_transaction_id CHAR(32) NOT NULL,
                ledger_entry_id CHAR(32) NOT NULL,
                rule_score NUMERIC(8, 4),
                ml_score NUMERIC(8, 4),
                status VARCHAR(30) NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE import_files (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                status VARCHAR(30) NOT NULL,
                total_rows INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            );
            CREATE TABLE exceptions (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32) NOT NULL,
                bank_transaction_id CHAR(32),
                ledger_entry_id CHAR(32),
                result_id CHAR(32),
                entity_mapping_id CHAR(32),
                reviewed_by CHAR(32),
                exception_type VARCHAR(50) NOT NULL,
                status VARCHAR(30) NOT NULL,
                suggestion TEXT,
                explanation TEXT,
                ai_analyzed_at DATETIME,
                review_comment TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE TABLE entity_mappings (
                id CHAR(32) PRIMARY KEY,
                owner_user_id CHAR(32) NOT NULL,
                approved_by CHAR(32),
                source_name VARCHAR(255) NOT NULL,
                canonical_name VARCHAR(255) NOT NULL,
                status VARCHAR(30) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            CREATE TABLE audit_history (
                id CHAR(32) PRIMARY KEY,
                run_id CHAR(32),
                actor_user_id CHAR(32),
                action VARCHAR(100) NOT NULL,
                description TEXT,
                created_at DATETIME NOT NULL
            );
            """
        for statement in schema.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_workspace_returns_only_authenticated_users_records() -> None:
    factory = _session_factory()
    now = datetime.now(timezone.utc)
    owner_id, other_id = uuid4(), uuid4()
    owner_run_id, other_run_id = uuid4(), uuid4()
    bank_id, ledger_id = uuid4(), uuid4()

    with factory() as session:
        owner = User(
            id=owner_id,
            full_name="Workspace Owner",
            email="owner@example.com",
            is_active=True,
            created_at=now,
        )
        other = User(
            id=other_id,
            full_name="Other User",
            email="other@example.com",
            is_active=True,
            created_at=now,
        )
        session.add_all(
            [
                owner,
                other,
                ReconciliationRun(
                    id=owner_run_id,
                    created_by=owner_id,
                    status="completed",
                    created_at=now,
                ),
                ReconciliationRun(
                    id=other_run_id,
                    created_by=other_id,
                    status="completed",
                    created_at=now,
                ),
                BankTransaction(
                    id=bank_id,
                    run_id=owner_run_id,
                    import_file_id=uuid4(),
                    transaction_date=date(2026, 10, 20),
                    payer_name="Owner Customer",
                    credit_amount=Decimal("100.00"),
                    debit_amount=Decimal("0"),
                ),
                LedgerEntry(
                    id=ledger_id,
                    run_id=owner_run_id,
                    import_file_id=uuid4(),
                    ledger_entry_id="LED-OWNER",
                    customer_name="Owner Customer",
                    entry_date=date(2026, 10, 20),
                    credit_amount=Decimal("100.00"),
                    debit_amount=Decimal("0"),
                ),
                ReconciliationResult(
                    id=uuid4(),
                    run_id=owner_run_id,
                    bank_transaction_id=bank_id,
                    ledger_entry_id=ledger_id,
                    transaction_count=2,
                    status="matched",
                    created_at=now,
                ),
                ExceptionRecord(
                    id=uuid4(),
                    run_id=owner_run_id,
                    bank_transaction_id=bank_id,
                    ledger_entry_id=ledger_id,
                    exception_type="amount_mismatch",
                    status="open",
                    suggestion="Review the amounts",
                    created_at=now,
                    updated_at=now,
                ),
                EntityMapping(
                    id=uuid4(),
                    owner_user_id=owner_id,
                    source_name="Owner Ltd",
                    canonical_name="Owner Limited",
                    status="approved",
                    created_at=now,
                    updated_at=now,
                ),
                EntityMapping(
                    id=uuid4(),
                    owner_user_id=other_id,
                    source_name="Private Ltd",
                    canonical_name="Private Limited",
                    status="approved",
                    created_at=now,
                    updated_at=now,
                ),
                AuditHistory(
                    id=uuid4(),
                    run_id=owner_run_id,
                    action="reconciliation_completed",
                    description="Owner event",
                    created_at=now,
                ),
                AuditHistory(
                    id=uuid4(),
                    run_id=other_run_id,
                    action="reconciliation_completed",
                    description="Private event",
                    created_at=now,
                ),
            ]
        )
        session.commit()

        result = get_workspace(owner, session)

    assert result.metrics.total_runs == 1
    assert result.metrics.matched_transactions == 1
    assert result.metrics.pending_reviews == 1
    assert result.metrics.entity_mappings == 1
    assert [run.id for run in result.runs] == [str(owner_run_id)]
    assert result.runs[0].transactions == 2
    assert [mapping.original for mapping in result.mappings] == ["Owner Ltd"]
    assert result.exceptions[0].entity == "Owner Customer"
    assert result.audit_events[0].description == "Owner event"

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/workspace")
        assert response.status_code == 200
        assert response.json()["metrics"]["total_runs"] == 1
        assert len(response.json()["runs"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_empty_workspace_returns_zero_metrics_and_no_records() -> None:
    factory = _session_factory()
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid4(),
        full_name="New User",
        email="new@example.com",
        is_active=True,
        created_at=now,
    )
    with factory() as session:
        session.add(user)
        session.commit()

        result = get_workspace(user, session)

    assert result.metrics.total_runs == 0
    assert result.metrics.matched_transactions == 0
    assert result.metrics.pending_reviews == 0
    assert result.metrics.entity_mappings == 0
    assert result.runs == []
    assert result.mappings == []
    assert result.exceptions == []
    assert result.audit_events == []


def test_pending_validated_runs_only_include_current_user() -> None:
    from app.modules.reconciliation.router import list_validated_reconciliations

    factory = _session_factory()
    now = datetime.now(timezone.utc)
    owner_id, other_id = uuid4(), uuid4()
    owner_run_id, other_run_id = uuid4(), uuid4()
    owner_bank_import_id, owner_ledger_import_id = uuid4(), uuid4()
    with factory() as session:
        owner = User(
            id=owner_id,
            full_name="Owner",
            email="owner@example.com",
            is_active=True,
            created_at=now,
        )
        other = User(
            id=other_id,
            full_name="Other",
            email="other@example.com",
            is_active=True,
            created_at=now,
        )
        session.add_all(
            [
                owner,
                other,
                ReconciliationRun(
                    id=owner_run_id,
                    created_by=owner_id,
                    status="pending",
                    created_at=now,
                ),
                ReconciliationRun(
                    id=other_run_id,
                    created_by=other_id,
                    status="pending",
                    created_at=now,
                ),
                ImportFile(
                    id=owner_bank_import_id,
                    run_id=owner_run_id,
                    file_type="bank",
                    file_name="owner-bank.csv",
                    status="processed",
                    total_rows=2,
                    created_at=now,
                ),
                ImportFile(
                    id=owner_ledger_import_id,
                    run_id=owner_run_id,
                    file_type="ledger",
                    file_name="owner-ledger.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                ImportFile(
                    id=uuid4(),
                    run_id=other_run_id,
                    file_type="bank",
                    file_name="private-bank.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                ImportFile(
                    id=uuid4(),
                    run_id=other_run_id,
                    file_type="ledger",
                    file_name="private-ledger.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                BankTransaction(
                    id=uuid4(),
                    run_id=owner_run_id,
                    import_file_id=owner_bank_import_id,
                    transaction_date=date(2026, 10, 20),
                    credit_amount=Decimal("10"),
                    debit_amount=Decimal("0"),
                ),
                LedgerEntry(
                    id=uuid4(),
                    run_id=owner_run_id,
                    import_file_id=owner_ledger_import_id,
                    entry_date=date(2026, 10, 20),
                    credit_amount=Decimal("10"),
                    debit_amount=Decimal("0"),
                ),
            ]
        )
        session.commit()

        result = list_validated_reconciliations(owner, session)

    assert len(result) == 1
    assert result[0].run_id == str(owner_run_id)
    assert result[0].bank_file_name == "owner-bank.csv"
    assert result[0].ledger_file_name == "owner-ledger.csv"
    assert result[0].valid_rows == 2
def test_reconciliation_details_returns_saved_results_and_hides_other_users_runs() -> None:
    factory = _session_factory()
    now = datetime.now(timezone.utc)
    owner_id, other_id = uuid4(), uuid4()
    run_id = uuid4()
    bank_file_id, ledger_file_id = uuid4(), uuid4()
    bank_id, ledger_id = uuid4(), uuid4()
    config = {
        "date_window_days": 3,
        "reference_threshold": 0.88,
        "reference_free_threshold": 0.82,
        "minimum_score_margin": 0.1,
        "entity_candidate_threshold": 0.7,
        "policy_version": "deterministic-v1",
        "model_version": "string-similarity-v1",
    }
    with factory() as session:
        owner = User(
            id=owner_id,
            full_name="Owner",
            email="owner@example.com",
            is_active=True,
            created_at=now,
        )
        other = User(
            id=other_id,
            full_name="Other",
            email="other@example.com",
            is_active=True,
            created_at=now,
        )
        session.add_all(
            [
                owner,
                other,
                ReconciliationRun(
                    id=run_id,
                    created_by=owner_id,
                    status="completed",
                    started_at=now,
                    completed_at=now,
                    created_at=now,
                ),
                ImportFile(
                    id=bank_file_id,
                    run_id=run_id,
                    file_type="bank",
                    file_name="bank.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                ImportFile(
                    id=ledger_file_id,
                    run_id=run_id,
                    file_type="ledger",
                    file_name="ledger.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                BankTransaction(
                    id=bank_id,
                    run_id=run_id,
                    import_file_id=bank_file_id,
                    transaction_reference="BANK-001",
                    transaction_date=date(2026, 10, 20),
                    payer_name="Example Customer",
                    credit_amount=Decimal("125.50"),
                    debit_amount=Decimal("0"),
                ),
                LedgerEntry(
                    id=ledger_id,
                    run_id=run_id,
                    import_file_id=ledger_file_id,
                    ledger_entry_id="LEDGER-001",
                    invoice_id="INV-001",
                    customer_name="Example Customer",
                    entry_date=date(2026, 10, 20),
                    credit_amount=Decimal("125.50"),
                    debit_amount=Decimal("0"),
                ),
                ReconciliationResult(
                    id=uuid4(),
                    run_id=run_id,
                    bank_transaction_id=bank_id,
                    transaction_count=1,
                    status="unmatched",
                    created_at=now,
                ),
                ReconciliationResult(
                    id=uuid4(),
                    run_id=run_id,
                    ledger_entry_id=ledger_id,
                    transaction_count=1,
                    status="unmatched",
                    created_at=now,
                ),
                AuditHistory(
                    id=uuid4(),
                    run_id=run_id,
                    action="reconciliation_completed",
                    description=json.dumps(
                        {
                            "matched_count": 0,
                            "pending_review_count": 0,
                            "exception_count": 0,
                            "unmatched_count": 2,
                            "policy_version": "deterministic-v1",
                            "model_version": "string-similarity-v1",
                            "config": config,
                            "completed_at": now.isoformat(),
                        }
                    ),
                    created_at=now,
                ),
            ]
        )
        session.commit()

    def override_db():
        with factory() as session:
            yield session

    authenticated_user = [owner]
    app.dependency_overrides[get_current_user] = lambda: authenticated_user[0]
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/reconciliations/{run_id}/details")
            assert response.status_code == 200
            payload = response.json()
            assert payload["run_id"] == str(run_id)
            assert payload["status"] == "Completed"
            assert payload["bank_file_name"] == "bank.csv"
            assert payload["ledger_file_name"] == "ledger.csv"
            assert payload["total_processed"] == 2
            assert payload["exception_count"] == 2
            assert {row["status"] for row in payload["transactions"]} == {"unmatched"}
            assert {row["entity"] for row in payload["transactions"]} == {
                "Example Customer",
            }
            assert {row["display_id"] for row in payload["transactions"]} == {
                "BANK-001",
                "LEDGER-001",
            }

            authenticated_user[0] = other
            forbidden_response = client.get(
                f"/api/v1/reconciliations/{run_id}/details"
            )
            assert forbidden_response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_cached_reconciliation_repairs_missing_result_rows(monkeypatch) -> None:
    from app.modules.reconciliation import service
    from app.modules.reconciliation.router import get_reconciliation_details

    factory = _session_factory()
    now = datetime.now(timezone.utc)
    user_id, run_id, bank_import_id, ledger_import_id, bank_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    config = {
        "date_window_days": 3,
        "reference_threshold": 0.88,
        "reference_free_threshold": 0.82,
        "minimum_score_margin": 0.1,
        "entity_candidate_threshold": 0.7,
        "policy_version": "deterministic-v1",
        "model_version": "string-similarity-v1",
    }

    with factory() as session:
        user = User(
            id=user_id,
            full_name="Owner",
            email="owner@example.com",
            is_active=True,
            created_at=now,
        )
        run = ReconciliationRun(
            id=run_id,
            created_by=user_id,
            status="completed",
            started_at=now,
            completed_at=now,
            created_at=now,
        )
        bank_file = ImportFile(
            id=bank_import_id,
            run_id=run_id,
            file_type="bank",
            file_name="bank.csv",
            status="processed",
            total_rows=1,
            created_at=now,
        )
        ledger_file = ImportFile(
            id=ledger_import_id,
            run_id=run_id,
            file_type="ledger",
            file_name="ledger.csv",
            status="processed",
            total_rows=0,
            created_at=now,
        )
        bank_transaction = BankTransaction(
            id=bank_id,
            run_id=run_id,
            import_file_id=bank_import_id,
            transaction_reference="BANK-001",
            transaction_date=date(2026, 10, 20),
            payer_name="Example Customer",
            credit_amount=Decimal("125.50"),
            debit_amount=Decimal("0"),
        )
        classified = {
            "transaction_id": str(bank_id),
            "transaction_type": "bank",
            "disposition": "unmatched",
            "reason_codes": [],
        }
        completed = {
            "matched_count": 0,
            "pending_review_count": 0,
            "exception_count": 0,
            "unmatched_count": 1,
            "policy_version": "deterministic-v1",
            "model_version": "string-similarity-v1",
            "config": config,
            "completed_at": now.isoformat(),
        }
        session.add_all(
            [
                user,
                run,
                bank_file,
                ledger_file,
                bank_transaction,
                AuditHistory(
                    id=uuid4(),
                    run_id=run_id,
                    action="transaction_classified",
                    description=json.dumps(classified),
                    created_at=now,
                ),
                AuditHistory(
                    id=uuid4(),
                    run_id=run_id,
                    action="reconciliation_completed",
                    description=json.dumps(completed),
                    created_at=now,
                ),
            ]
        )
        session.commit()

        details = get_reconciliation_details(run_id, user, session)
        assert details.total_processed == 1
        repaired_rows = session.scalars(
            select(ReconciliationResult).where(
                ReconciliationResult.run_id == run_id
            )
        ).all()
        assert len(repaired_rows) == 1
        assert repaired_rows[0].status == "unmatched"

    monkeypatch.setattr(service, "SessionLocal", factory)
    outcome = service.run_reconciliation(str(run_id), user_id)

    with factory() as session:
        result_rows = session.scalars(
            select(ReconciliationResult).where(
                ReconciliationResult.run_id == run_id
            )
        ).all()

    assert outcome.unmatched_count == 1
    assert len(outcome.transactions) == 1
    assert outcome.transactions[0].transaction_id == str(bank_id)
    assert len(result_rows) == 1
    assert result_rows[0].status == "unmatched"


def test_new_reconciliation_persists_result_rows(monkeypatch) -> None:
    from app.modules.reconciliation import service

    factory = _session_factory()
    now = datetime.now(timezone.utc)
    user_id, run_id, bank_import_id, bank_id = uuid4(), uuid4(), uuid4(), uuid4()
    with factory() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    full_name="Owner",
                    email="owner@example.com",
                    is_active=True,
                    created_at=now,
                ),
                ReconciliationRun(
                    id=run_id,
                    created_by=user_id,
                    status="pending",
                    created_at=now,
                ),
                ImportFile(
                    id=bank_import_id,
                    run_id=run_id,
                    file_type="bank",
                    file_name="bank.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                BankTransaction(
                    id=bank_id,
                    run_id=run_id,
                    import_file_id=bank_import_id,
                    transaction_reference="BANK-001",
                    transaction_date=date(2026, 10, 20),
                    payer_name="Example Customer",
                    credit_amount=Decimal("125.50"),
                    debit_amount=Decimal("0"),
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(service, "SessionLocal", factory)
    outcome = service.run_reconciliation(str(run_id), user_id)

    with factory() as session:
        result_rows = session.scalars(
            select(ReconciliationResult).where(
                ReconciliationResult.run_id == run_id
            )
        ).all()

    assert outcome.unmatched_count == 1
    assert len(result_rows) == 1
    assert result_rows[0].status == "unmatched"


def test_matched_reconciliation_persists_paired_result_row(monkeypatch) -> None:
    from app.modules.reconciliation import service

    factory = _session_factory()
    now = datetime.now(timezone.utc)
    user_id, run_id = uuid4(), uuid4()
    bank_import_id, ledger_import_id = uuid4(), uuid4()
    bank_id, ledger_id = uuid4(), uuid4()
    with factory() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    full_name="Owner",
                    email="owner@example.com",
                    is_active=True,
                    created_at=now,
                ),
                ReconciliationRun(
                    id=run_id,
                    created_by=user_id,
                    status="pending",
                    created_at=now,
                ),
                ImportFile(
                    id=bank_import_id,
                    run_id=run_id,
                    file_type="bank",
                    file_name="bank.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                ImportFile(
                    id=ledger_import_id,
                    run_id=run_id,
                    file_type="ledger",
                    file_name="ledger.csv",
                    status="processed",
                    total_rows=1,
                    created_at=now,
                ),
                BankTransaction(
                    id=bank_id,
                    run_id=run_id,
                    import_file_id=bank_import_id,
                    transaction_reference="INV-100",
                    transaction_date=date(2026, 10, 20),
                    payer_name="Example Customer",
                    credit_amount=Decimal("125.50"),
                    debit_amount=Decimal("0"),
                ),
                LedgerEntry(
                    id=ledger_id,
                    run_id=run_id,
                    import_file_id=ledger_import_id,
                    invoice_id="INV-100",
                    customer_name="Example Customer",
                    entry_date=date(2026, 10, 20),
                    credit_amount=Decimal("125.50"),
                    debit_amount=Decimal("0"),
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(service, "SessionLocal", factory)
    outcome = service.run_reconciliation(str(run_id), user_id)

    with factory() as session:
        result_rows = session.scalars(
            select(ReconciliationResult).where(
                ReconciliationResult.run_id == run_id
            )
        ).all()

    assert outcome.matched_count == 1
    assert len(result_rows) == 1
    assert result_rows[0].status == "matched"
    assert result_rows[0].transaction_count == 2
    assert result_rows[0].bank_transaction_id == bank_id
    assert result_rows[0].ledger_entry_id == ledger_id
