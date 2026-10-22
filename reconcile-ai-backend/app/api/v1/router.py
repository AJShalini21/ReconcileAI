import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.router import router as auth_router
from app.auth.dependencies import get_current_user, require_trusted_origin
from app.db.models import User
from app.modules.ingestion.schemas import CSVUploadResponse
from app.modules.ingestion.service import process_uploaded_files, validate_uploaded_files
from app.modules.reconciliation.router import router as reconciliation_router
from app.modules.reconciliation.schemas import ReconciliationConfig
from app.modules.workspace.router import router as workspace_router

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "reconcile-ai-backend"}



@router.post(
    "/reconciliations/validate",
    status_code=200,
    response_model=CSVUploadResponse,
)
async def validate_reconciliation_files(
    bank_file: UploadFile = File(..., alias="bankFile"),
    ledger_file: UploadFile = File(..., alias="ledgerFile"),
    current_user: User = Depends(get_current_user),
    _origin: None = Depends(require_trusted_origin),
) -> CSVUploadResponse:
    try:
        result = await validate_uploaded_files(bank_file, ledger_file, current_user.id)

        return CSVUploadResponse(**result)

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("CSV validation failed")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during CSV validation.",
        ) from exc



@router.post("/reconciliations", status_code=202, response_model=CSVUploadResponse)
async def create_reconciliation(
    bank_file: UploadFile = File(..., alias="bankFile"),
    ledger_file: UploadFile = File(..., alias="ledgerFile"),
    date_window_days: int = Form(default=3, alias="dateWindowDays", ge=0, le=365),
    reference_threshold: float = Form(default=0.88, alias="referenceThreshold", ge=0, le=1),
    reference_free_threshold: float = Form(default=0.82, alias="referenceFreeThreshold", ge=0, le=1),
    minimum_score_margin: float = Form(default=0.10, alias="minimumScoreMargin", ge=0, le=1),
    entity_candidate_threshold: float = Form(default=0.70, alias="entityCandidateThreshold", ge=0, le=1),
    current_user: User = Depends(get_current_user),
    _origin: None = Depends(require_trusted_origin),
) -> CSVUploadResponse:
    if not bank_file or not ledger_file:
        raise HTTPException(status_code=400, detail="Both bankFile and ledgerFile are required.")

    try:
        config = ReconciliationConfig(
            date_window_days=date_window_days,
            reference_threshold=reference_threshold,
            reference_free_threshold=reference_free_threshold,
            minimum_score_margin=minimum_score_margin,
            entity_candidate_threshold=entity_candidate_threshold,
        )
        result = await process_uploaded_files(bank_file, ledger_file, current_user.id, config)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return CSVUploadResponse(**result)


router.include_router(reconciliation_router)
router.include_router(workspace_router)
