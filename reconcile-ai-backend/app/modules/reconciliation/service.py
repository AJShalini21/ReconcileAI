from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.db.models import ReconciliationRun
from app.db.session import SessionLocal
from app.modules.reconciliation.engine import reconcile
from app.modules.reconciliation.repository import ReconciliationRepository
from app.modules.reconciliation.schemas import (
    ReconciliationConfig,
    ReconciliationOutcome,
)


def run_reconciliation(
    run_id: str,
    owner_user_id: UUID,
    config: ReconciliationConfig | None = None,
) -> ReconciliationOutcome:
    print(f"Running reconciliation for run_id: {run_id} by owner_user_id: {owner_user_id}")
    parsed_run_id = UUID(run_id)
    selected_config = config or ReconciliationConfig()
    with SessionLocal() as session:
        with session.begin():
            repository = ReconciliationRepository(session)
            run = session.scalar(
                select(ReconciliationRun)
                .where(
                    ReconciliationRun.id == parsed_run_id,
                    ReconciliationRun.created_by == owner_user_id,
                )
                .with_for_update()
            )
            if run is None:
                raise LookupError("Reconciliation run was not found.")

            previous_outcome = repository.load_outcome(parsed_run_id)
            if previous_outcome is not None:
                repository.ensure_persisted_results(previous_outcome, parsed_run_id)
                return previous_outcome

            run.status = "processing"
            run.started_at = datetime.now(timezone.utc)
            bank_transactions, ledger_entries = repository.get_transactions(
                parsed_run_id, owner_user_id
            )
            outcome = reconcile(
                str(parsed_run_id),
                bank_transactions,
                ledger_entries,
                selected_config,
            )
            repository.persist_outcome(run, outcome, selected_config)
        return outcome


def review_candidate(
    run_id: str,
    candidate_id: str,
    action: str,
    reviewer_user_id: UUID,
    comment: str | None = None,
) -> str:
    print(f"Reviewing candidate {candidate_id} for run_id: {run_id} with action: {action} by reviewer_user_id: {reviewer_user_id}")
    repository_run_id = UUID(run_id)
    repository_candidate_id = UUID(candidate_id)
    with SessionLocal() as session:
        repository = ReconciliationRepository(session)
        return repository.review_candidate(
            repository_run_id,
            repository_candidate_id,
            action,
            reviewer_user_id,
            reviewer_user_id,
            comment,
        )
