import json
from collections import defaultdict
from decimal import Decimal
from typing import Literal
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.auth.dependencies import get_current_user, require_trusted_origin
from app.db.models import (
    AuditHistory,
    BankTransaction,
    EntityMapping,
    ExceptionRecord,
    LedgerEntry,
    MatchCandidate,
    ReconciliationResult,
    ReconciliationRun,
    User,
)
from app.db.session import get_db
from app.modules.workspace.schemas import (
    WorkspaceAuditEvent,
    WorkspaceCandidateView,
    WorkspaceException,
    WorkspaceMapping,
    WorkspaceMetrics,
    WorkspaceResponse,
    WorkspaceRun,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _run_status(status: str) -> tuple[str, str]:
    return {
        "completed": ("Completed", "success"),
        "failed": ("Failed", "error"),
        "pending": ("In progress", "info"),
        "processing": ("In progress", "info"),
        "cancelled": ("Cancelled", "neutral"),
    }.get(status, (status.replace("_", " ").title(), "neutral"))


def _exception_status(status: str) -> str:
    return {
        "open": "Pending Review",
        "in_review": "Pending Review",
        "resolved": "Approved",
        "ignored": "Rejected",
    }.get(status, "Pending Review")


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


@router.get("", response_model=WorkspaceResponse)
def get_workspace(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    runs = db.scalars(
        select(ReconciliationRun)
        .options(selectinload(ReconciliationRun.import_files))
        .where(ReconciliationRun.created_by == user.id)
        .order_by(ReconciliationRun.created_at.desc())
    ).all()
    run_ids = [run.id for run in runs]

    bank_counts: dict[UUID, int] = defaultdict(int)
    ledger_counts: dict[UUID, int] = defaultdict(int)
    matched_count = 0
    total_audited_approved = 0
    exceptions: list[ExceptionRecord] = []
    audit_events: list[AuditHistory] = []

    if run_ids:
        bank_counts.update(
            dict(
                db.execute(
                    select(BankTransaction.run_id, func.count())
                    .where(BankTransaction.run_id.in_(run_ids))
                    .group_by(BankTransaction.run_id)
                ).all()
            )
        )
        ledger_counts.update(
            dict(
                db.execute(
                    select(LedgerEntry.run_id, func.count())
                    .where(LedgerEntry.run_id.in_(run_ids))
                    .group_by(LedgerEntry.run_id)
                ).all()
            )
        )
        matched_count = db.scalar(
            select(func.count())
            .select_from(ReconciliationResult)
            .where(
                ReconciliationResult.run_id.in_(run_ids),
                ReconciliationResult.status == "matched",
            )
        ) or 0
        exceptions = db.scalars(
            select(ExceptionRecord)
            .options(
                joinedload(ExceptionRecord.bank_transaction),
                joinedload(ExceptionRecord.ledger_entry),
            )
            .where(
                ExceptionRecord.run_id.in_(run_ids),
                ExceptionRecord.status.in_(("open", "in_review")),
            )
            .order_by(ExceptionRecord.created_at.desc())
        ).all()
        user_audit_actions = [
            "files_validated",
            "file_validated",
            "reconciliation_executed",
            "reconciliation_completed",
            "exception_approved",
            "exception_rejected",
            "candidate_approved",
            "candidate_rejected",
            "entity_mapping_approved",
            "entity_mapping_rejected",
            "entity_mapping_reviewed",
        ]
        audit_events = db.scalars(
            select(AuditHistory)
            .where(
                or_(
                    AuditHistory.run_id.in_(run_ids),
                    AuditHistory.actor_user_id == user.id,
                ),
                AuditHistory.action.in_(user_audit_actions),
            )
            .order_by(AuditHistory.created_at.desc())
        ).all()

        audited_count = db.scalar(
            select(func.count())
            .select_from(AuditHistory)
            .where(
                or_(
                    AuditHistory.run_id.in_(run_ids),
                    AuditHistory.actor_user_id == user.id,
                ),
                AuditHistory.action.in_(("exception_approved", "candidate_approved")),
            )
        ) or 0
        resolved_count = db.scalar(
            select(func.count())
            .select_from(ExceptionRecord)
            .where(
                ExceptionRecord.run_id.in_(run_ids),
                ExceptionRecord.status.in_(("resolved", "approved")),
            )
        ) or 0
        total_audited_approved = max(audited_count, resolved_count)

    mappings = db.scalars(
        select(EntityMapping)
        .where(EntityMapping.owner_user_id == user.id)
        .order_by(EntityMapping.updated_at.desc())
    ).all()

    run_views = []
    for run in runs:
        status, tone = _run_status(run.status)
        imports = {f.file_type: f.file_name for f in run.import_files}
        bank_file = imports.get("bank", "—")
        ledger_file = imports.get("ledger", "—")
        run_views.append(
            WorkspaceRun(
                id=str(run.id),
                date=run.created_at,
                bank_file=bank_file,
                ledger_file=ledger_file,
                transactions=bank_counts[run.id] + ledger_counts[run.id],
                status=status,
                tone=tone,
            )
        )

    mapping_views = [
        WorkspaceMapping(
            id=str(mapping.id),
            original=mapping.source_name,
            matched=mapping.canonical_name,
            source="Workspace",
            confidence="—",
            status={
                "pending": "Pending Review",
                "approved": "Approved",
                "rejected": "Rejected",
            }.get(mapping.status, "Pending Review"),
        )
        for mapping in mappings
    ]

    # Query all candidate matches and detect cross-transaction collisions
    bank_tx_ids = [ex.bank_transaction_id for ex in exceptions if ex.bank_transaction_id]
    candidates_by_bank: dict[UUID, list[MatchCandidate]] = defaultdict(list)
    banks_by_ledger: dict[UUID, list[UUID]] = defaultdict(list)
    competing_bank_tx_map: dict[UUID, BankTransaction] = {}

    if run_ids:
        all_candidates = db.scalars(
            select(MatchCandidate)
            .options(joinedload(MatchCandidate.ledger_entry))
            .where(
                MatchCandidate.run_id.in_(run_ids),
                MatchCandidate.status.in_(("candidate", "accepted")),
            )
            .order_by(MatchCandidate.rule_score.desc().nullslast())
        ).all()
        for cand in all_candidates:
            if cand.bank_transaction_id in bank_tx_ids:
                candidates_by_bank[cand.bank_transaction_id].append(cand)
            if cand.ledger_entry_id:
                banks_by_ledger[cand.ledger_entry_id].append(cand.bank_transaction_id)

        all_candidate_bank_ids = {
            bt_id for bt_ids in banks_by_ledger.values() for bt_id in bt_ids
        }
        if all_candidate_bank_ids:
            all_bank_txs = db.scalars(
                select(BankTransaction).where(BankTransaction.id.in_(all_candidate_bank_ids))
            ).all()
            competing_bank_tx_map = {bt.id: bt for bt in all_bank_txs}

    exception_views = []
    for exception in exceptions:
        bank = exception.bank_transaction
        ledger = exception.ledger_entry
        reason_type = _humanize(exception.exception_type)
        entity = (
            (bank.payer_name if bank else None)
            or (ledger.customer_name if ledger else None)
            or "Unknown entity"
        )
        bank_amount = (
            (bank.credit_amount or Decimal("0")) - (bank.debit_amount or Decimal("0"))
            if bank
            else None
        )
        ledger_amount = (
            (ledger.credit_amount or Decimal("0")) - (ledger.debit_amount or Decimal("0"))
            if ledger
            else None
        )
        difference = (
            abs(bank_amount - ledger_amount)
            if bank_amount is not None and ledger_amount is not None
            else "Unavailable"
        )

        candidate_views: list[WorkspaceCandidateView] = []
        cands = candidates_by_bank.get(bank.id if bank else None, [])

        if cands:
            for cand in cands:
                c_ledger = cand.ledger_entry
                if not c_ledger:
                    continue
                c_amount = (
                    (c_ledger.credit_amount or Decimal("0")) - (c_ledger.debit_amount or Decimal("0"))
                )
                c_diff = (
                    abs(bank_amount - c_amount)
                    if bank_amount is not None
                    else "Unavailable"
                )
                conf = int(float(cand.rule_score) * 100) if cand.rule_score is not None else 90
                match_status = "High Match" if conf >= 85 else "Medium Match" if conf >= 65 else "Low Match"

                amt_diff_text = "✓ Exact amount" if (bank_amount is not None and bank_amount == c_amount) else f"Diff: {c_diff}"

                date_diff_text = None
                if bank and c_ledger.entry_date:
                    days = abs((bank.transaction_date - c_ledger.entry_date).days)
                    date_diff_text = "✓ Same day" if days == 0 else f"{days} days diff"

                entity_diff_text = None
                if bank and bank.payer_name and c_ledger.customer_name:
                    if bank.payer_name.strip().lower() == c_ledger.customer_name.strip().lower():
                        entity_diff_text = "✓ Exact name"
                    elif cand.ml_score is not None:
                        entity_diff_text = f"{int(float(cand.ml_score) * 100)}% entity sim"
                    else:
                        entity_diff_text = "Entity similarity"

                ref_diff_text = None
                if bank and bank.reference_number and c_ledger.payment_reference:
                    ref_diff_text = "✓ Match" if bank.reference_number.strip().lower() == c_ledger.payment_reference.strip().lower() else "Different ref"
                elif c_ledger.payment_reference:
                    ref_diff_text = "Ref present"

                competing_bids = [
                    bid for bid in banks_by_ledger.get(c_ledger.id, [])
                    if bank and bid != bank.id
                ]
                has_collision = len(competing_bids) > 0
                collision_warning = None
                competing_refs: list[str] = []
                if has_collision:
                    for c_bid in competing_bids:
                        c_tx = competing_bank_tx_map.get(c_bid)
                        ref = c_tx.reference_number if c_tx and c_tx.reference_number else str(c_bid)[:8]
                        competing_refs.append(f"Bank Tx {ref}")
                    warning_detail = ", ".join(competing_refs[:2])
                    collision_warning = (
                        f"Competing Claim: Also matched to {warning_detail}. "
                        "Approving here will unbind it from other transactions."
                    )

                candidate_views.append(
                    WorkspaceCandidateView(
                        id=str(cand.id),
                        ledger_entry_id=str(c_ledger.id),
                        title=f"Ledger entry • {c_ledger.customer_name or 'Ledger record'}",
                        customer=c_ledger.customer_name,
                        ledger_value=f"{c_amount:.2f}" if isinstance(c_amount, Decimal) else str(c_amount),
                        ledger_date=c_ledger.entry_date.isoformat(),
                        ledger_reference=c_ledger.payment_reference,
                        invoice_reference=c_ledger.invoice_id,
                        difference=f"{c_diff:.2f}" if isinstance(c_diff, Decimal) else str(c_diff),
                        confidence=conf,
                        match_status=match_status,
                        amount_diff_text=amt_diff_text,
                        date_diff_text=date_diff_text,
                        entity_diff_text=entity_diff_text,
                        ref_diff_text=ref_diff_text,
                        suggestion=exception.suggestion,
                        has_collision=has_collision,
                        collision_warning=collision_warning,
                        competing_bank_transactions=competing_refs,
                    )
                )

        if not candidate_views and ledger:
            competing_bids = [
                bid for bid in banks_by_ledger.get(ledger.id, [])
                if bank and bid != bank.id
            ]
            has_collision = len(competing_bids) > 0
            collision_warning = None
            competing_refs = []
            if has_collision:
                for c_bid in competing_bids:
                    c_tx = competing_bank_tx_map.get(c_bid)
                    ref = c_tx.reference_number if c_tx and c_tx.reference_number else str(c_bid)[:8]
                    competing_refs.append(f"Bank Tx {ref}")
                warning_detail = ", ".join(competing_refs[:2])
                collision_warning = (
                    f"Competing Claim: Also matched to {warning_detail}. "
                    "Approving here will unbind it from other transactions."
                )

            candidate_views.append(
                WorkspaceCandidateView(
                    id=str(exception.id),
                    ledger_entry_id=str(ledger.id),
                    title=f"Ledger entry • {ledger.customer_name or entity}",
                    customer=ledger.customer_name or entity,
                    ledger_value=f"{ledger_amount:.2f}" if isinstance(ledger_amount, Decimal) else str(ledger_amount or "0.00"),
                    ledger_date=ledger.entry_date.isoformat(),
                    ledger_reference=ledger.payment_reference,
                    invoice_reference=ledger.invoice_id,
                    difference=f"{difference:.2f}" if isinstance(difference, Decimal) else str(difference),
                    confidence=94,
                    match_status="High Match",
                    amount_diff_text="✓ Exact amount" if bank_amount == ledger_amount else f"Diff: {difference}",
                    date_diff_text="✓ Same day" if (bank and bank.transaction_date == ledger.entry_date) else None,
                    entity_diff_text="✓ Exact name",
                    ref_diff_text="✓ Match" if (bank and bank.reference_number and ledger.payment_reference and bank.reference_number == ledger.payment_reference) else None,
                    suggestion=exception.suggestion,
                    has_collision=has_collision,
                    collision_warning=collision_warning,
                    competing_bank_transactions=competing_refs,
                )
            )

        exception_views.append(
            WorkspaceException(
                id=str(exception.id),
                entity=entity,
                customer=ledger.customer_name if ledger else None,
                reason=reason_type,
                reason_type=reason_type,
                run=str(exception.run_id),
                status=_exception_status(exception.status),
                bank_transaction_id=str(bank.id) if bank else None,
                ledger_entry_id=str(ledger.id) if ledger else None,
                bank_description=bank.description if bank else None,
                bank_label="Bank amount",
                bank_value=f"{bank_amount:.2f}" if isinstance(bank_amount, Decimal) else str(bank_amount or "0.00"),
                ledger_label="Ledger amount",
                ledger_value=f"{ledger_amount:.2f}" if isinstance(ledger_amount, Decimal) else str(ledger_amount or "0.00"),
                difference=f"{difference:.2f}" if isinstance(difference, Decimal) else str(difference),
                bank_date=bank.transaction_date.isoformat() if bank else None,
                ledger_date=ledger.entry_date.isoformat() if ledger else None,
                bank_reference=(bank.reference_number) if bank else None,
                ledger_reference=(
                    ledger.payment_reference
                    if ledger
                    else None
                ),
                invoice_reference=ledger.invoice_id if ledger else None,
                suggestion=exception.suggestion,
                explanation=exception.explanation,
                ai_analyzed_at=exception.ai_analyzed_at,
                candidates=candidate_views,
            )
        )

    audit_views = [_format_audit_event(event) for event in audit_events]

    return WorkspaceResponse(
        metrics=WorkspaceMetrics(
            total_runs=len(runs),
            matched_transactions=matched_count,
            pending_reviews=len(exceptions),
            entity_mappings=len(mappings),
            audited_approved_exceptions=total_audited_approved,
        ),
        runs=run_views,
        mappings=mapping_views,
        exceptions=exception_views,
        audit_events=audit_views,
    )


def _format_audit_event(event: AuditHistory) -> WorkspaceAuditEvent:
    run_id = str(event.run_id) if event.run_id else ""
    act = event.action.lower()

    if "files_validated" in act or "file_validated" in act:
        title = "Files Validated"
        action = "Validating files"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "info"
        icon: Literal["audit", "mapping", "upload", "history"] = "upload"
    elif "reconciliation" in act:
        title = "Run Reconciliation"
        action = "Run reconciliation"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "info"
        icon: Literal["audit", "mapping", "upload", "history"] = "history"
    elif "approved" in act and ("candidate" in act or "exception" in act):
        title = "Exception Approved"
        action = "Exception review approve"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "success"
        icon: Literal["audit", "mapping", "upload", "history"] = "audit"
    elif "rejected" in act and ("candidate" in act or "exception" in act):
        title = "Exception Rejected"
        action = "Exception review reject"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "error"
        icon: Literal["audit", "mapping", "upload", "history"] = "audit"
    elif "mapping" in act and "approved" in act:
        title = "Entity Mapping Approved"
        action = "Entity matching approve"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "success"
        icon: Literal["audit", "mapping", "upload", "history"] = "mapping"
    elif "mapping" in act and "rejected" in act:
        title = "Entity Mapping Rejected"
        action = "Entity matching reject"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "error"
        icon: Literal["audit", "mapping", "upload", "history"] = "mapping"
    elif "mapping" in act:
        title = "Entity Mapping Reviewed"
        action = "Entity matching review"
        tone: Literal["success", "warning", "error", "info", "neutral"] = "info"
        icon: Literal["audit", "mapping", "upload", "history"] = "mapping"
    else:
        title = _humanize(event.action)
        action = _humanize(event.action)
        tone: Literal["success", "warning", "error", "info", "neutral"] = "info"
        icon: Literal["audit", "mapping", "upload", "history"] = "audit"

    description = event.description or title
    if description.startswith("{") and description.endswith("}"):
        try:
            parsed = json.loads(description)
            if "comment" in parsed and parsed["comment"]:
                description = f"{title}. Reviewer note: {parsed['comment']}"
            elif "matched_count" in parsed:
                description = f"Completed run: {parsed.get('matched_count', 0)} matched, {parsed.get('pending_review_count', 0)} pending review, {parsed.get('exception_count', 0)} exceptions."
            else:
                description = f"{title} for reconciliation run {run_id[:8] if run_id else ''}."
        except Exception:
            pass

    return WorkspaceAuditEvent(
        title=title,
        action=action,
        run=run_id,
        resource=run_id or str(event.id),
        description=description,
        date=event.created_at,
        tone=tone,
        icon=icon,
    )


class EntityMappingReviewRequest(BaseModel):
    action: Literal["approve", "reject", "approved", "rejected"]


@router.post("/entity-mappings/{mapping_id}/review", response_model=WorkspaceMapping)
def review_entity_mapping(
    mapping_id: UUID,
    request: EntityMappingReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _origin: None = Depends(require_trusted_origin),
) -> WorkspaceMapping:
    mapping = db.scalar(
        select(EntityMapping)
        .where(
            EntityMapping.id == mapping_id,
            EntityMapping.owner_user_id == current_user.id,
        )
        .with_for_update()
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="Entity mapping not found.")

    is_approve = request.action in ("approve", "approved")
    mapping.status = "approved" if is_approve else "rejected"
    mapping.approved_by = current_user.id
    mapping.updated_at = datetime.now(timezone.utc)

    db.add(
        AuditHistory(
            actor_user_id=current_user.id,
            action="entity_mapping_approved" if is_approve else "entity_mapping_rejected",
            description=f"{'Approved' if is_approve else 'Rejected'} entity mapping: '{mapping.source_name}' -> '{mapping.canonical_name}'.",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return WorkspaceMapping(
        id=str(mapping.id),
        original=mapping.source_name,
        matched=mapping.canonical_name,
        source="Workspace",
        confidence="100%",
        status="Approved" if is_approve else "Rejected",
    )
