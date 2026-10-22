from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session, selectinload, joinedload
from uuid import UUID

from app.auth.dependencies import get_current_user, require_trusted_origin
from app.db.models import (
    BankTransaction,
    ExceptionRecord,
    ImportFile,
    LedgerEntry,
    MatchCandidate,
    ReconciliationRun,
    User,
)
from app.db.session import get_db

from app.modules.reconciliation.schemas import (
    AnalyzeExceptionRequest,
    AnalyzeExceptionResponse,
    CandidateReviewRequest,
    CandidateReviewResponse,
    ReconciliationDetails,
    ReconciliationOutcome,
    ReconciliationRunRequest,
    ValidatedReconciliation,
)
from app.modules.reconciliation.repository import ReconciliationRepository
from app.modules.reconciliation.service import review_candidate, run_reconciliation
from app.modules.analyzer.gemini_service import analyze_discrepancy_with_gemini

router = APIRouter(prefix="/reconciliations", tags=["reconciliation"])


@router.get("/validated", response_model=list[ValidatedReconciliation])
def list_validated_reconciliations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ValidatedReconciliation]:
    print(f"Listing validated reconciliations for user_id: {current_user.id}")
    runs = db.scalars(
        select(ReconciliationRun)
        .options(selectinload(ReconciliationRun.import_files))
        .where(
            ReconciliationRun.created_by == current_user.id,
            ReconciliationRun.status == "pending",
        )
        .order_by(ReconciliationRun.created_at.desc())
    ).all()
    run_ids = [run.id for run in runs]
    if not run_ids:
        return []

    bank_counts = dict(
        db.execute(
            select(BankTransaction.run_id, func.count())
            .where(BankTransaction.run_id.in_(run_ids))
            .group_by(BankTransaction.run_id)
        ).all()
    )
    ledger_counts = dict(
        db.execute(
            select(LedgerEntry.run_id, func.count())
            .where(LedgerEntry.run_id.in_(run_ids))
            .group_by(LedgerEntry.run_id)
        ).all()
    )
    response = []
    for run in runs:
        imports = {item.file_type: item for item in run.import_files}
        bank_file = imports.get("bank")
        ledger_file = imports.get("ledger")
        if bank_file is None or ledger_file is None:
            continue
        response.append(
            ValidatedReconciliation(
                run_id=str(run.id),
                created_at=run.created_at,
                bank_file_name=bank_file.file_name,
                ledger_file_name=ledger_file.file_name,
                valid_rows=bank_counts.get(run.id, 0) + ledger_counts.get(run.id, 0),
            )
        )
    return response


@router.get("/{run_id}/details", response_model=ReconciliationDetails)
def get_reconciliation_details(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReconciliationDetails:
    print(f"Fetching reconciliation details for run_id: {run_id} and user_id: {current_user.id}")
    owned_run = db.scalar(
        select(ReconciliationRun.id).where(
            ReconciliationRun.id == run_id,
            ReconciliationRun.created_by == current_user.id,
        )
    )
    if owned_run is None:
        raise HTTPException(status_code=404, detail="Reconciliation run was not found.")

    repository = ReconciliationRepository(db)
    outcome = repository.load_outcome(run_id)
    if outcome is not None and repository.ensure_persisted_results(outcome, run_id):
        db.commit()

    details = repository.get_details(run_id, current_user.id)
    if details is None:
        raise HTTPException(
            status_code=409,
            detail="Reconciliation results are not available for this run yet.",
        )
    return details


@router.post("/{run_id}/execute", response_model=ReconciliationOutcome)
def execute_reconciliation(
    run_id: UUID,
    request: ReconciliationRunRequest = ReconciliationRunRequest(),
    current_user: User = Depends(get_current_user),
    _origin: None = Depends(require_trusted_origin),
) -> ReconciliationOutcome:
    print(f"Executing reconciliation for run_id: {run_id} by user_id: {current_user.id}")
    try:
        return run_reconciliation(str(run_id), current_user.id, request.config)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/{run_id}/candidates/{candidate_id}/review",
    response_model=CandidateReviewResponse,
)
def review_reconciliation_candidate(
    run_id: UUID,
    candidate_id: UUID,
    request: CandidateReviewRequest,
    current_user: User = Depends(get_current_user),
    _origin: None = Depends(require_trusted_origin),
) -> CandidateReviewResponse:
    print(f"Reviewing candidate {candidate_id} for run_id: {run_id} with action: {request.action} by user_id: {current_user.id}")
    try:
        status = review_candidate(
            str(run_id),
            str(candidate_id),
            request.action,
            current_user.id,
            request.comment,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CandidateReviewResponse(
        candidate_id=str(candidate_id),
        status=status,
        message=f"Candidate {status} successfully.",
    )


@router.post(
    "/{run_id}/exceptions/{exception_id}/analyze",
    response_model=AnalyzeExceptionResponse,
)
def analyze_exception(
    run_id: UUID,
    exception_id: UUID,
    request: AnalyzeExceptionRequest = AnalyzeExceptionRequest(),
    current_user: User = Depends(get_current_user),
    _origin: None = Depends(require_trusted_origin),
    db: Session = Depends(get_db),
) -> AnalyzeExceptionResponse:
    print(f"Analyzing exception {exception_id} for run_id {run_id} by user_id {current_user.id}")
    exception = db.scalar(
        select(ExceptionRecord)
        .options(
            joinedload(ExceptionRecord.bank_transaction),
            joinedload(ExceptionRecord.ledger_entry),
        )
        .where(
            ExceptionRecord.id == exception_id,
            ExceptionRecord.run_id == run_id,
        )
    )
    if exception is None:
        raise HTTPException(status_code=404, detail="Exception record was not found.")

    bank = exception.bank_transaction
    target_ledger = exception.ledger_entry

    # If candidate_id is specified, find the specific candidate's ledger entry
    cand_uuid = None
    if request.candidate_id:
        try:
            cand_uuid = UUID(str(request.candidate_id))
        except (ValueError, TypeError):
            cand_uuid = None

    if cand_uuid:
        cand = db.scalar(
            select(MatchCandidate)
            .options(joinedload(MatchCandidate.ledger_entry))
            .where(
                or_(
                    MatchCandidate.id == cand_uuid,
                    MatchCandidate.ledger_entry_id == cand_uuid,
                )
            )
        )
        if cand and cand.ledger_entry:
            target_ledger = cand.ledger_entry

    # If still no ledger entry, pick top candidate from MatchCandidate
    if target_ledger is None and bank is not None:
        cand = db.scalar(
            select(MatchCandidate)
            .options(joinedload(MatchCandidate.ledger_entry))
            .where(
                MatchCandidate.run_id == run_id,
                MatchCandidate.bank_transaction_id == bank.id,
            )
            .order_by(MatchCandidate.rule_score.desc().nullslast())
            .limit(1)
        )
        if cand and cand.ledger_entry:
            target_ledger = cand.ledger_entry

    bank_dict = {}
    if bank:
        b_amount = (bank.credit_amount or Decimal("0")) - (bank.debit_amount or Decimal("0"))
        bank_dict = {
            "id": str(bank.id),
            "date": bank.transaction_date.isoformat(),
            "amount": f"{b_amount:.2f}",
            "payer_name": bank.payer_name or "N/A",
            "reference_number": bank.reference_number or "N/A",
            "description": bank.description or "",
        }

    ledger_dict = {}
    if target_ledger:
        l_amount = (target_ledger.credit_amount or Decimal("0")) - (target_ledger.debit_amount or Decimal("0"))
        ledger_dict = {
            "id": str(target_ledger.id),
            "date": target_ledger.entry_date.isoformat(),
            "amount": f"{l_amount:.2f}",
            "customer_name": target_ledger.customer_name or "N/A",
            "payment_reference": target_ledger.payment_reference or "N/A",
            "invoice_id": target_ledger.invoice_id or "N/A",
        }

    # Find competing bank transactions for this ledger entry
    competing_bank_txs = []
    if target_ledger:
        competing_candidates = db.scalars(
            select(MatchCandidate)
            .options(joinedload(MatchCandidate.bank_transaction))
            .where(
                MatchCandidate.run_id == run_id,
                MatchCandidate.ledger_entry_id == target_ledger.id,
                MatchCandidate.bank_transaction_id != (bank.id if bank else None),
                MatchCandidate.status.in_(("candidate", "accepted")),
            )
        ).all()
        for cc in competing_candidates:
            if cc.bank_transaction:
                cbt = cc.bank_transaction
                cb_amount = (cbt.credit_amount or Decimal("0")) - (cbt.debit_amount or Decimal("0"))
                competing_bank_txs.append({
                    "id": str(cbt.id),
                    "date": cbt.transaction_date.isoformat(),
                    "amount": f"{cb_amount:.2f}",
                    "payer_name": cbt.payer_name or "N/A",
                    "reference_number": cbt.reference_number or "N/A",
                    "description": cbt.description or "",
                })

    # Other candidate ledger entries for this bank transaction
    other_candidates = []
    if bank:
        other_records = db.scalars(
            select(MatchCandidate)
            .options(joinedload(MatchCandidate.ledger_entry))
            .where(
                MatchCandidate.run_id == run_id,
                MatchCandidate.bank_transaction_id == bank.id,
                MatchCandidate.ledger_entry_id != (target_ledger.id if target_ledger else None),
            )
        ).all()
        for oc in other_records:
            if oc.ledger_entry:
                ole = oc.ledger_entry
                ol_amount = (ole.credit_amount or Decimal("0")) - (ole.debit_amount or Decimal("0"))
                other_candidates.append({
                    "id": str(ole.id),
                    "date": ole.entry_date.isoformat(),
                    "amount": f"{ol_amount:.2f}",
                    "customer_name": ole.customer_name or "N/A",
                    "payment_reference": ole.payment_reference or "N/A",
                })

    # Calculate differences
    b_amt = Decimal(bank_dict.get("amount", "0.00"))
    l_amt = Decimal(ledger_dict.get("amount", "0.00"))
    diff_val = abs(b_amt - l_amt)
    amount_diff = f"{diff_val:,.2f}"

    date_diff = "Same day"
    if bank and target_ledger:
        days = abs((bank.transaction_date - target_ledger.entry_date).days)
        date_diff = f"{days} days variance" if days > 0 else "Same day"

    entity_diff = "Match"
    if bank and target_ledger and bank.payer_name and target_ledger.customer_name:
        entity_diff = (
            "Exact match"
            if bank.payer_name.strip().lower() == target_ledger.customer_name.strip().lower()
            else f"'{bank.payer_name}' vs '{target_ledger.customer_name}'"
        )

    ref_diff = "Match"
    if bank and target_ledger and bank.reference_number and target_ledger.payment_reference:
        ref_diff = (
            "Exact match"
            if bank.reference_number.strip().lower() == target_ledger.payment_reference.strip().lower()
            else f"Bank ref '{bank.reference_number}' vs Ledger ref '{target_ledger.payment_reference}'"
        )

    discrepancy_info = {
        "amount_diff": amount_diff,
        "date_diff": date_diff,
        "entity_diff": entity_diff,
        "ref_diff": ref_diff,
    }

    analysis = analyze_discrepancy_with_gemini(
        bank_tx=bank_dict,
        candidate_ledger=ledger_dict,
        competing_bank_txs=competing_bank_txs,
        other_candidates=other_candidates,
        discrepancy_info=discrepancy_info,
    )

    # Persist the AI output into the database
    exception.explanation = analysis.get("explanation")
    exception.suggestion = analysis.get("suggestion")
    exception.ai_analyzed_at = datetime.now(timezone.utc)
    db.commit()

    comp_refs = [
        f"Bank Tx {tx.get('reference_number') or tx.get('id')[:8]}"
        for tx in competing_bank_txs
    ]

    return AnalyzeExceptionResponse(
        exception_id=str(exception.id),
        explanation=exception.explanation or "Analysis complete.",
        suggestion=exception.suggestion or "Review supporting documents before deciding.",
        has_collision=bool(analysis.get("has_collision") or competing_bank_txs),
        collision_warning=analysis.get("collision_warning"),
        competing_bank_transactions=comp_refs,
        confidence=analysis.get("confidence", "high"),
    )
