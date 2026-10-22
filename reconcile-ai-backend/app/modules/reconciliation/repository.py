from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditHistory,
    BankTransaction,
    EntityMapping,
    ExceptionRecord,
    ImportFile,
    LedgerEntry,
    MatchCandidate,
    ReconciliationResult,
    ReconciliationRun,
    User,
)
from app.modules.reconciliation.schemas import (
    CandidateDecision,
    ReconciliationConfig,
    ReconciliationDetails,
    ReconciliationOutcome,
    ReconciliationTransactionResult,
    TransactionDecision,
    TransactionInput,
)


class ReconciliationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_transactions(
        self, run_id: UUID, owner_user_id: UUID
    ) -> tuple[list[TransactionInput], list[TransactionInput]]:
        print(f"Fetching transactions for run_id: {run_id} and owner_user_id: {owner_user_id}")
        mappings = self.session.scalars(
            select(EntityMapping).where(
                EntityMapping.status == "approved",
                EntityMapping.owner_user_id == owner_user_id,
            )
        ).all()
        canonical_names = {
            mapping.source_name.strip().casefold(): mapping.canonical_name
            for mapping in mappings
        }
        bank_rows = self.session.scalars(
            select(BankTransaction)
            .where(BankTransaction.run_id == run_id)
            .order_by(BankTransaction.id)
        ).all()
        ledger_rows = self.session.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.run_id == run_id)
            .order_by(LedgerEntry.id)
        ).all()
        bank = [
            TransactionInput(
                id=str(row.id),
                transaction_date=row.transaction_date,
                credit_amount=Decimal(str(row.credit_amount)) if row.credit_amount else None,
                debit_amount=Decimal(str(row.debit_amount)) if row.debit_amount else None,
                references=[value for value in (row.transaction_reference, row.reference_number) if value],
                entity_name=canonical_names.get(
                    (row.payer_name or "").strip().casefold(), row.payer_name
                ),
            )
            for row in bank_rows
        ]
        ledger = [
            TransactionInput(
                id=str(row.id),
                transaction_date=row.entry_date,
                credit_amount=Decimal(str(row.credit_amount or 0)) if row.credit_amount else None,
                debit_amount=Decimal(str(row.debit_amount or 0)) if row.debit_amount else None,

                references=[
                    value
                    for value in (row.invoice_id, row.payment_reference)
                    if value
                ],
                entity_name=canonical_names.get(
                    (row.customer_name or "").strip().casefold(), row.customer_name
                ),
            )
            for row in ledger_rows
        ]
        return bank, ledger

    def get_details(
        self, run_id: UUID, owner_user_id: UUID
    ) -> ReconciliationDetails | None:
        print(f"Fetching reconciliation details for run_id: {run_id} and owner_user_id: {owner_user_id}")
        run = self.session.scalar(
            select(ReconciliationRun).where(
                ReconciliationRun.id == run_id,
                ReconciliationRun.created_by == owner_user_id,
            )
        )
        if run is None:
            return None

        outcome = self.load_outcome(run_id)
        if outcome is None:
            return None

        imports = self.session.scalars(
            select(ImportFile).where(ImportFile.run_id == run_id)
        ).all()
        files_by_type = {item.file_type: item for item in imports}
        bank_file = files_by_type.get("bank")
        ledger_file = files_by_type.get("ledger")
        if bank_file is None or ledger_file is None:
            return None

        bank_rows = self.session.scalars(
            select(BankTransaction)
            .where(BankTransaction.run_id == run_id)
            .order_by(BankTransaction.transaction_date, BankTransaction.id)
        ).all()
        ledger_rows = self.session.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.run_id == run_id)
            .order_by(LedgerEntry.entry_date, LedgerEntry.id)
        ).all()
        bank_by_id = {str(row.id): row for row in bank_rows}
        ledger_by_id = {str(row.id): row for row in ledger_rows}
        candidates_by_bank: dict[str, list[CandidateDecision]] = {}
        candidates_by_ledger: dict[str, list[CandidateDecision]] = {}
        for candidate in outcome.candidates:
            candidates_by_bank.setdefault(candidate.bank_transaction_id, []).append(
                candidate
            )
            candidates_by_ledger.setdefault(candidate.ledger_entry_id, []).append(
                candidate
            )

        def transaction_explanation(
            decision: TransactionDecision,
            candidates: list[CandidateDecision],
        ) -> str:
            print(f"Generating explanation for transaction {decision.transaction_id} with disposition {decision.disposition}")
            if not candidates:
                return "No eligible ledger candidate found"
            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.disposition == "matched"
                ),
                max(candidates, key=lambda candidate: candidate.score),
            )
            if decision.reason_codes:
                return " · ".join(
                    reason.replace("_", " ").capitalize()
                    for reason in decision.reason_codes
                )
            details = [
                "Exact amount"
                if selected.features.amount_agreement == "exact"
                else "Amount differs",
                f"Date difference: {selected.features.date_difference_days} days",
            ]
            if selected.features.reference_agreement != "missing":
                details.append(
                    f"Reference {selected.features.reference_agreement}"
                )
            if selected.features.entity_similarity is not None:
                details.append(
                    f"Name similarity {selected.features.entity_similarity:.0%}"
                )
            return " · ".join(details)

        transaction_views: list[ReconciliationTransactionResult] = []
        for decision in outcome.transactions:
            bank = (
                bank_by_id.get(decision.transaction_id)
                if decision.transaction_type == "bank"
                else None
            )
            ledger = (
                ledger_by_id.get(decision.transaction_id)
                if decision.transaction_type == "ledger"
                else None
            )
            candidates = (
                candidates_by_bank.get(decision.transaction_id, [])
                if bank is not None
                else candidates_by_ledger.get(decision.transaction_id, [])
            )

            if bank is not None:
                transaction_id = str(bank.id)
                reference = bank.reference_number or bank.transaction_reference
                entity = bank.payer_name or "Bank transaction"
                amount = Decimal(str(bank.credit_amount or 0)) - Decimal(
                    str(bank.debit_amount or 0)
                )
                display_id = bank.transaction_reference or bank.reference_number or transaction_id
            elif ledger is not None:
                transaction_id = str(ledger.id)
                reference = ledger.payment_reference or ledger.invoice_id
                entity = ledger.customer_name or "Ledger entry"
                amount = Decimal(str(ledger.credit_amount or 0)) - Decimal(
                    str(ledger.debit_amount or 0)
                )
                display_id = ledger.ledger_entry_id or ledger.invoice_id or transaction_id
            else:
                continue

            transaction_views.append(
                ReconciliationTransactionResult(
                    id=transaction_id,
                    display_id=display_id,
                    reference=reference,
                    entity=entity,
                    amount_summary=str(amount),
                    explanation=transaction_explanation(decision, candidates),
                    status={
                        "matched": "matched",
                        "pending_review": "review",
                        "exception": "exception",
                        "unmatched": "unmatched",
                    }[decision.disposition],
                )
            )

        duration_seconds = None
        if run.started_at is not None and run.completed_at is not None:
            duration_seconds = max(
                0.0, (run.completed_at - run.started_at).total_seconds()
            )
        transaction_dates = [
            row.transaction_date for row in bank_rows
        ] + [row.entry_date for row in ledger_rows]
        if transaction_dates:
            date_window = " – ".join(
                value.strftime("%b %d, %Y").replace(" 0", " ")
                for value in (min(transaction_dates), max(transaction_dates))
            )
        else:
            date_window = f"{outcome.config.date_window_days} days"
        status = {
            "completed": "Completed",
            "failed": "Failed",
            "processing": "In progress",
            "pending": "Pending",
            "cancelled": "Cancelled",
        }.get(run.status, run.status.replace("_", " ").title())

        return ReconciliationDetails(
            run_id=str(run.id),
            status=status,
            created_at=run.created_at,
            source_summary="Bank Statement vs Company Ledger",
            total_processed=len(outcome.transactions),
            matched_count=sum(
                item.disposition == "matched" for item in outcome.transactions
            ),
            needs_review_count=sum(
                item.disposition == "pending_review" for item in outcome.transactions
            ),
            exception_count=sum(
                item.disposition in {"exception", "unmatched"}
                for item in outcome.transactions
            ),
            bank_file_name=bank_file.file_name,
            ledger_file_name=ledger_file.file_name,
            date_window=date_window,
            processing_time=(
                f"{duration_seconds:.1f} seconds"
                if duration_seconds is not None
                else "Unavailable"
            ),
            transactions=transaction_views,
        )

    def persist_outcome(
        self,
        run: ReconciliationRun,
        outcome: ReconciliationOutcome,
        config: ReconciliationConfig,
    ) -> None:
        print(f"Persisting reconciliation outcome for run_id: {run.id} with {len(outcome.candidates)} candidates and {len(outcome.transactions)} transactions")
        now = datetime.now(timezone.utc)
        for decision in outcome.candidates:
            candidate = MatchCandidate(
                id=uuid4(),
                run_id=run.id,
                bank_transaction_id=UUID(decision.bank_transaction_id),
                ledger_entry_id=UUID(decision.ledger_entry_id),
                rule_score=Decimal(str(decision.score)),
                ml_score=(
                    Decimal(str(decision.features.entity_similarity))
                    if decision.features.entity_similarity is not None
                    else None
                ),
                status="accepted" if decision.disposition == "matched" else "candidate",
                created_at=now,
            )
            self.session.add(candidate)
            self.session.flush()
            decision.candidate_id = str(candidate.id)
            self.session.add(
                AuditHistory(
                    id=uuid4(),
                    run_id=run.id,
                    action="candidate_evaluated",
                    description=json.dumps(
                        {
                            "candidate_id": str(candidate.id),
                            "decision": decision.model_dump(mode="json"),
                            "config": config.model_dump(mode="json"),
                        },
                        sort_keys=True,
                    ),
                    created_at=now,
                )
            )
            if decision.disposition == "exception":
                self.session.add(
                    ExceptionRecord(
                        id=uuid4(),
                        run_id=run.id,
                        bank_transaction_id=UUID(decision.bank_transaction_id),
                        ledger_entry_id=UUID(decision.ledger_entry_id),
                        exception_type=(decision.reason_codes[0] if decision.reason_codes else "review_required")[:50],
                        suggestion="Review the recorded candidate features and discrepancy before deciding.",
                        created_at=now,
                        updated_at=now,
                    )
                )

        self.ensure_persisted_results(outcome, run.id)

        run.status = "completed"
        run.completed_at = now
        self.session.add(
            AuditHistory(
                id=uuid4(),
                run_id=run.id,
                action="reconciliation_completed",
                description=json.dumps(
                    {
                        "matched_count": outcome.matched_count,
                        "pending_review_count": outcome.pending_review_count,
                        "exception_count": outcome.exception_count,
                        "unmatched_count": outcome.unmatched_count,
                        "policy_version": outcome.policy_version,
                        "model_version": outcome.model_version,
                        "config": config.model_dump(mode="json"),
                        "completed_at": now.isoformat(),
                    },
                    sort_keys=True,
                ),
                created_at=now,
            )
        )

    def ensure_persisted_results(
        self, outcome: ReconciliationOutcome, run_id: UUID
    ) -> bool:
        print(f"Ensuring persisted results for run_id: {run_id}")
        expected = self._result_rows_for_outcome(outcome, run_id)
        existing = self.session.scalars(
            select(ReconciliationResult).where(
                ReconciliationResult.run_id == run_id
            )
        ).all()

        def result_key(result: ReconciliationResult) -> tuple[str | None, str | None, int, str]:
            print(f"Generating key for result: {result.id}")
            return (
                str(result.bank_transaction_id) if result.bank_transaction_id else None,
                str(result.ledger_entry_id) if result.ledger_entry_id else None,
                result.transaction_count,
                result.status,
            )

        stored_counts = Counter(result_key(result) for result in existing)
        expected_counts = Counter(result_key(result) for result in expected)
        inserted = False
        for key, expected_count in expected_counts.items():
            missing_count = expected_count - stored_counts[key]
            for _ in range(max(0, missing_count)):
                bank_id, ledger_id, transaction_count, status = key
                self.session.add(
                    ReconciliationResult(
                        id=uuid4(),
                        run_id=run_id,
                        bank_transaction_id=UUID(bank_id) if bank_id else None,
                        ledger_entry_id=UUID(ledger_id) if ledger_id else None,
                        transaction_count=transaction_count,
                        status=status,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                inserted = True
        return inserted

    @staticmethod
    def _result_rows_for_outcome(
        outcome: ReconciliationOutcome, run_id: UUID
    ) -> list[ReconciliationResult]:
        print(f"Generating result rows for outcome of run_id: {run_id}")
        results: list[ReconciliationResult] = []
        created_at = datetime.now(timezone.utc)
        matched_transactions: set[tuple[str, str]] = set()
        for candidate in outcome.candidates:
            if (
                candidate.disposition != "matched"
                and candidate.review_status != "approved"
            ):
                continue
            results.append(
                ReconciliationResult(
                    id=uuid4(),
                    run_id=run_id,
                    bank_transaction_id=UUID(candidate.bank_transaction_id),
                    ledger_entry_id=UUID(candidate.ledger_entry_id),
                    transaction_count=2,
                    status="matched",
                    created_at=created_at,
                )
            )
            matched_transactions.add(("bank", candidate.bank_transaction_id))
            matched_transactions.add(("ledger", candidate.ledger_entry_id))

        status_by_disposition = {
            "pending_review": "manual_review",
            "exception": "partial",
            "unmatched": "unmatched",
        }
        for classification in outcome.transactions:
            if (
                classification.disposition == "matched"
                or (
                    classification.transaction_type,
                    classification.transaction_id,
                )
                in matched_transactions
            ):
                continue
            transaction_id = classification.transaction_id
            bank_id = None
            ledger_id = None
            if classification.transaction_type == "bank":
                bank_id = UUID(transaction_id)
            else:
                ledger_id = UUID(transaction_id)
            results.append(
                ReconciliationResult(
                    id=uuid4(),
                    run_id=run_id,
                    bank_transaction_id=bank_id,
                    ledger_entry_id=ledger_id,
                    transaction_count=1,
                    status=status_by_disposition[classification.disposition],
                    created_at=created_at,
                )
            )
        return results

    def load_outcome(self, run_id: UUID) -> ReconciliationOutcome | None:
        outcome_audit_actions = (
            "candidate_evaluated",
            "candidate_approved",
            "candidate_rejected",
            "transaction_classified",
            "reconciliation_completed",
        )
        audits = self.session.scalars(
            select(AuditHistory)
            .where(
                AuditHistory.run_id == run_id,
                AuditHistory.action.in_(outcome_audit_actions),
            )
            .order_by(AuditHistory.created_at, AuditHistory.id)
        ).all()
        print(f"Loading reconciliation outcome for run_id: {run_id} with {len(audits)} audit records")
        candidate_decisions: list[CandidateDecision] = []
        classified_decisions: list[TransactionDecision] = []
        summary: dict[str, object] | None = None
        for audit in audits:
            if not audit.description:
                continue
            payload = json.loads(audit.description)
            if audit.action == "candidate_evaluated":
                candidate_decisions.append(CandidateDecision.model_validate(payload["decision"]))
            elif audit.action == "transaction_classified":
                if payload.get("disposition") != "invalid":
                    classified_decisions.append(
                        TransactionDecision.model_validate(payload)
                    )
            elif audit.action in {"candidate_approved", "candidate_rejected"}:
                candidate = next(
                    (
                        decision
                        for decision in candidate_decisions
                        if decision.candidate_id == payload["candidate_id"]
                    ),
                    None,
                )
                if candidate is not None:
                    candidate.review_status = (
                        "approved"
                        if audit.action == "candidate_approved"
                        else "rejected"
                    )
                    candidate.reviewed_by = audit.actor_user_id and str(audit.actor_user_id)
                    candidate.review_comment = payload.get("comment")
            elif audit.action == "reconciliation_completed":
                summary = payload
        if summary is None:
            return None
        transaction_decisions: list[TransactionDecision] = []
        known_transactions: set[tuple[str, str]] = set()
        for decision in classified_decisions:
            transaction_key = (decision.transaction_type, decision.transaction_id)
            if transaction_key not in known_transactions:
                transaction_decisions.append(decision)
                known_transactions.add(transaction_key)
        for candidate in candidate_decisions:
            if candidate.disposition != "matched" and candidate.review_status != "approved":
                continue
            for transaction_type, transaction_id in (
                ("bank", candidate.bank_transaction_id),
                ("ledger", candidate.ledger_entry_id),
            ):
                if (transaction_type, transaction_id) not in known_transactions:
                    transaction_decisions.append(
                        TransactionDecision(
                            transaction_id=transaction_id,
                            transaction_type=transaction_type,
                            disposition="matched",
                        )
                    )
                    known_transactions.add((transaction_type, transaction_id))
        results = self.session.scalars(
            select(ReconciliationResult)
            .where(ReconciliationResult.run_id == run_id)
            .order_by(ReconciliationResult.created_at, ReconciliationResult.id)
        ).all()
        for result in results:
            disposition = {
                "matched": "matched",
                "manual_review": "pending_review",
                "partial": "exception",
                "unmatched": "unmatched",
            }[result.status]
            if result.bank_transaction_id is not None:
                transaction_key = ("bank", str(result.bank_transaction_id))
                if transaction_key not in known_transactions:
                    reasons = sorted(
                        {
                            reason
                            for candidate in candidate_decisions
                            if candidate.bank_transaction_id
                            == str(result.bank_transaction_id)
                            for reason in candidate.reason_codes
                        }
                    )
                    transaction_decisions.append(
                        TransactionDecision(
                            transaction_id=str(result.bank_transaction_id),
                            transaction_type="bank",
                            disposition=disposition,
                            reason_codes=reasons,
                        )
                    )
                    known_transactions.add(transaction_key)
            if result.ledger_entry_id is not None:
                transaction_key = ("ledger", str(result.ledger_entry_id))
                if transaction_key not in known_transactions:
                    reasons = sorted(
                        {
                            reason
                            for candidate in candidate_decisions
                            if candidate.ledger_entry_id
                            == str(result.ledger_entry_id)
                            for reason in candidate.reason_codes
                        }
                    )
                    transaction_decisions.append(
                        TransactionDecision(
                            transaction_id=str(result.ledger_entry_id),
                            transaction_type="ledger",
                            disposition=disposition,
                            reason_codes=reasons,
                        )
                    )
                    known_transactions.add(transaction_key)
        return ReconciliationOutcome(
            run_id=str(run_id),
            policy_version=str(summary["policy_version"]),
            model_version=str(summary["model_version"]),
            config=ReconciliationConfig.model_validate(summary["config"]),
            candidates=candidate_decisions,
            transactions=transaction_decisions,
            matched_count=sum(
                decision.disposition == "matched"
                or decision.review_status == "approved"
                for decision in candidate_decisions
            ),
            pending_review_count=sum(
                decision.disposition == "pending_review"
                and decision.review_status is None
                for decision in candidate_decisions
            ),
            exception_count=sum(
                decision.disposition == "exception"
                and decision.review_status is None
                for decision in candidate_decisions
            ),
            unmatched_count=sum(
                decision.disposition == "unmatched"
                for decision in transaction_decisions
            ),
        )

    def review_candidate(
        self,
        run_id: UUID,
        candidate_id: UUID,
        action: str,
        reviewer_user_id: UUID,
        owner_user_id: UUID,
        comment: str | None,
    ) -> str:
        print(f"Reviewing candidate {candidate_id} for run_id: {run_id} with action: {action} by reviewer_user_id: {reviewer_user_id}")
        run = self.session.scalar(
            select(ReconciliationRun)
            .where(
                ReconciliationRun.id == run_id,
                ReconciliationRun.created_by == owner_user_id,
            )
            .with_for_update()
        )
        if run is None:
            raise LookupError("Reconciliation run was not found.")
        reviewer = self.session.get(User, reviewer_user_id)
        if reviewer is None or not reviewer.is_active:
            raise ValueError("An active reviewer user is required.")
        candidate = self.session.scalar(
            select(MatchCandidate)
            .where(
                MatchCandidate.id == candidate_id,
                MatchCandidate.run_id == run_id,
            )
            .with_for_update()
        )
        if candidate is None:
            # Fallback 1: check if candidate_id is an ExceptionRecord id
            ex = self.session.get(ExceptionRecord, candidate_id)
            if ex and ex.bank_transaction_id and ex.ledger_entry_id:
                candidate = self.session.scalar(
                    select(MatchCandidate).where(
                        MatchCandidate.run_id == run_id,
                        MatchCandidate.bank_transaction_id == ex.bank_transaction_id,
                        MatchCandidate.ledger_entry_id == ex.ledger_entry_id,
                    ).with_for_update()
                )
            # Fallback 2: check if candidate_id is a ledger_entry_id
            if candidate is None:
                candidate = self.session.scalar(
                    select(MatchCandidate).where(
                        MatchCandidate.run_id == run_id,
                        MatchCandidate.ledger_entry_id == candidate_id,
                    ).with_for_update()
                )

        if candidate is None:
            raise LookupError("Candidate was not found in this reconciliation run.")

        is_approve = action in ("approve", "approved")

        # If already in the target state, treat idempotently
        if is_approve and candidate.status == "accepted":
            related_exceptions = self.session.scalars(
                select(ExceptionRecord).where(
                    ExceptionRecord.run_id == run_id,
                    ExceptionRecord.status.in_(("open", "in_review")),
                    or_(
                        ExceptionRecord.bank_transaction_id == candidate.bank_transaction_id,
                        ExceptionRecord.ledger_entry_id == candidate.ledger_entry_id,
                    ),
                )
            ).all()
            for exception in related_exceptions:
                exception.status = "resolved"
                exception.reviewed_by = reviewer_user_id
                if comment:
                    exception.review_comment = comment
            self.session.commit()
            return "accepted"

        if not is_approve and candidate.status == "rejected":
            related_exceptions = self.session.scalars(
                select(ExceptionRecord).where(
                    ExceptionRecord.run_id == run_id,
                    ExceptionRecord.status.in_(("open", "in_review")),
                    or_(
                        ExceptionRecord.bank_transaction_id == candidate.bank_transaction_id,
                        ExceptionRecord.ledger_entry_id == candidate.ledger_entry_id,
                    ),
                )
            ).all()
            for exception in related_exceptions:
                exception.status = "resolved"
                exception.reviewed_by = reviewer_user_id
                if comment:
                    exception.review_comment = comment
            self.session.commit()
            return "rejected"

        if is_approve:
            existing_conflict = self.session.scalar(
                select(ReconciliationResult.id)
                .where(
                    ReconciliationResult.run_id == run_id,
                    ReconciliationResult.status == "matched",
                    or_(
                        and_(
                            ReconciliationResult.bank_transaction_id == candidate.bank_transaction_id,
                            ReconciliationResult.ledger_entry_id != candidate.ledger_entry_id,
                        ),
                        and_(
                            ReconciliationResult.ledger_entry_id == candidate.ledger_entry_id,
                            ReconciliationResult.bank_transaction_id != candidate.bank_transaction_id,
                        ),
                    ),
                )
                .limit(1)
            )
            if existing_conflict is not None:
                raise ValueError("One or both transactions are already matched to a different record.")
            old_results = self.session.scalars(
                select(ReconciliationResult).where(
                    ReconciliationResult.run_id == run_id,
                    ReconciliationResult.status != "matched",
                    or_(
                        ReconciliationResult.bank_transaction_id == candidate.bank_transaction_id,
                        ReconciliationResult.ledger_entry_id == candidate.ledger_entry_id,
                    ),
                )
            ).all()
            old_result_ids = [result.id for result in old_results]
            if old_result_ids:
                exceptions = self.session.scalars(
                    select(ExceptionRecord).where(ExceptionRecord.result_id.in_(old_result_ids))
                ).all()
                for exception in exceptions:
                    exception.result_id = None
                for result in old_results:
                    self.session.delete(result)
            self.session.add(
                ReconciliationResult(
                    run_id=run_id,
                    bank_transaction_id=candidate.bank_transaction_id,
                    ledger_entry_id=candidate.ledger_entry_id,
                    transaction_count=2,
                    status="matched",
                )
            )
            candidate.status = "accepted"

            # Reject competing candidate matches for the same bank transaction or ledger entry
            competing_candidates = self.session.scalars(
                select(MatchCandidate).where(
                    MatchCandidate.run_id == run_id,
                    MatchCandidate.id != candidate.id,
                    MatchCandidate.status == "candidate",
                    or_(
                        MatchCandidate.bank_transaction_id == candidate.bank_transaction_id,
                        MatchCandidate.ledger_entry_id == candidate.ledger_entry_id,
                    ),
                )
            ).all()
            for comp in competing_candidates:
                comp.status = "rejected"

            # Resolve all open exceptions for this bank transaction or ledger entry
            related_exceptions = self.session.scalars(
                select(ExceptionRecord).where(
                    ExceptionRecord.run_id == run_id,
                    ExceptionRecord.status.in_(("open", "in_review")),
                    or_(
                        ExceptionRecord.bank_transaction_id == candidate.bank_transaction_id,
                        ExceptionRecord.ledger_entry_id == candidate.ledger_entry_id,
                    ),
                )
            ).all()
            for exception in related_exceptions:
                exception.status = "resolved"
                exception.reviewed_by = reviewer_user_id
                exception.review_comment = comment

            # Auto-learn / update Entity Mapping rule
            bank_tx = self.session.get(BankTransaction, candidate.bank_transaction_id)
            ledger_entry = self.session.get(LedgerEntry, candidate.ledger_entry_id)
            if bank_tx and ledger_entry and bank_tx.payer_name and ledger_entry.customer_name:
                source_name = bank_tx.payer_name.strip()
                canonical_name = ledger_entry.customer_name.strip()
                if source_name.lower() != canonical_name.lower():
                    mapping = self.session.scalar(
                        select(EntityMapping).where(
                            EntityMapping.owner_user_id == owner_user_id,
                            EntityMapping.source_name.ilike(source_name),
                        )
                    )
                    if mapping:
                        mapping.canonical_name = canonical_name
                        mapping.status = "approved"
                        mapping.approved_by = reviewer_user_id
                        mapping.updated_at = datetime.now(timezone.utc)
                    else:
                        self.session.add(
                            EntityMapping(
                                owner_user_id=owner_user_id,
                                source_name=source_name,
                                canonical_name=canonical_name,
                                status="approved",
                                approved_by=reviewer_user_id,
                            )
                        )
        else:
            candidate.status = "rejected"
            related_exceptions = self.session.scalars(
                select(ExceptionRecord).where(
                    ExceptionRecord.run_id == run_id,
                    ExceptionRecord.status.in_(("open", "in_review")),
                    ExceptionRecord.bank_transaction_id == candidate.bank_transaction_id,
                    ExceptionRecord.ledger_entry_id == candidate.ledger_entry_id,
                )
            ).all()
            for exception in related_exceptions:
                exception.status = "resolved"
                exception.reviewed_by = reviewer_user_id
                exception.review_comment = comment
            self.session.flush()
            for is_bank, transaction_id in (
                (True, candidate.bank_transaction_id),
                (False, candidate.ledger_entry_id),
            ):
                has_pending_candidates = self.session.scalar(
                    select(MatchCandidate.id)
                    .where(
                        MatchCandidate.run_id == run_id,
                        MatchCandidate.status == "candidate",
                        (
                            MatchCandidate.bank_transaction_id == transaction_id
                            if is_bank
                            else MatchCandidate.ledger_entry_id == transaction_id
                        ),
                    )
                    .limit(1)
                )
                open_exception = self.session.scalar(
                    select(ExceptionRecord.id)
                    .where(
                        ExceptionRecord.run_id == run_id,
                        ExceptionRecord.status.in_(("open", "in_review")),
                        (
                            ExceptionRecord.bank_transaction_id == transaction_id
                            if is_bank
                            else ExceptionRecord.ledger_entry_id == transaction_id
                        ),
                    )
                    .limit(1)
                )
                result = self.session.scalar(
                    select(ReconciliationResult)
                    .where(
                        ReconciliationResult.run_id == run_id,
                        ReconciliationResult.status != "matched",
                        (
                            ReconciliationResult.bank_transaction_id == transaction_id
                            if is_bank
                            else ReconciliationResult.ledger_entry_id == transaction_id
                        ),
                    )
                    .with_for_update()
                )
                if result is not None:
                    result.status = (
                        "manual_review"
                        if has_pending_candidates is not None
                        else "partial"
                        if open_exception is not None
                        else "unmatched"
                    )

        self.session.add(
            AuditHistory(
                run_id=run_id,
                actor_user_id=reviewer_user_id,
                action=f"candidate_{'approved' if is_approve else 'rejected'}",
                description=json.dumps(
                    {
                        "candidate_id": str(candidate.id),
                        "bank_transaction_id": str(candidate.bank_transaction_id),
                        "ledger_entry_id": str(candidate.ledger_entry_id),
                        "comment": comment,
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    },
                    sort_keys=True,
                ),
            )
        )
        self.session.commit()
        return "accepted" if is_approve else "rejected"
