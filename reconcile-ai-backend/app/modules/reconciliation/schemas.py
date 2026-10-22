from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


ReferenceAgreement = Literal["exact", "partial", "missing", "conflicting"]
CandidateDisposition = Literal["matched", "pending_review", "exception"]
TransactionDisposition = Literal["matched", "pending_review", "exception", "unmatched"]


class TransactionInput(BaseModel):
    id: str
    transaction_date: date
    credit_amount: Decimal | None = None
    debit_amount: Decimal | None = None
    references: list[str] = Field(default_factory=list)
    entity_name: str | None = None


class ReconciliationConfig(BaseModel):
    date_window_days: int = Field(default=3, ge=0, le=365)
    reference_threshold: float = Field(default=0.88, ge=0, le=1)
    reference_free_threshold: float = Field(default=0.82, ge=0, le=1)
    minimum_score_margin: float = Field(default=0.10, ge=0, le=1)
    entity_candidate_threshold: float = Field(default=0.70, ge=0, le=1)
    policy_version: str = "deterministic-v1"
    model_version: str = "string-similarity-v1"


class CandidateFeatures(BaseModel):
    reference_agreement: ReferenceAgreement
    amount_agreement: Literal["exact", "different"]
    date_difference_days: int
    entity_similarity: float | None


class CandidateDecision(BaseModel):
    candidate_id: str | None = None
    review_status: Literal["pending", "approved", "rejected"] | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None
    bank_transaction_id: str
    ledger_entry_id: str
    candidate_sources: list[str]
    features: CandidateFeatures
    rule_outcomes: list[str]
    score: float
    score_threshold: float
    score_margin: float | None = None
    scoring_policy: Literal["reference-supported", "reference-free"]
    disposition: CandidateDisposition
    matching_round: Literal[1, 2] | None = None
    reason_codes: list[str] = Field(default_factory=list)


class TransactionDecision(BaseModel):
    transaction_id: str
    transaction_type: Literal["bank", "ledger"]
    disposition: TransactionDisposition
    reason_codes: list[str] = Field(default_factory=list)


class ReconciliationOutcome(BaseModel):
    run_id: str
    policy_version: str
    model_version: str
    config: ReconciliationConfig
    candidates: list[CandidateDecision]
    transactions: list[TransactionDecision]
    matched_count: int
    pending_review_count: int
    exception_count: int
    unmatched_count: int


class ReconciliationTransactionResult(BaseModel):
    id: str
    display_id: str
    reference: str | None = None
    entity: str
    amount_summary: str
    explanation: str
    status: Literal["matched", "review", "exception", "unmatched"]


class ReconciliationDetails(BaseModel):
    run_id: str
    status: str
    created_at: datetime
    source_summary: str
    total_processed: int
    matched_count: int
    needs_review_count: int
    exception_count: int
    bank_file_name: str
    ledger_file_name: str
    date_window: str
    processing_time: str
    transactions: list[ReconciliationTransactionResult]


class ReconciliationRunRequest(BaseModel):
    config: ReconciliationConfig = Field(default_factory=ReconciliationConfig)


class ValidatedReconciliation(BaseModel):
    run_id: str
    created_at: datetime
    bank_file_name: str
    ledger_file_name: str
    valid_rows: int


class CandidateReviewRequest(BaseModel):
    action: Literal["approve", "reject", "approved", "rejected"]
    comment: str | None = Field(default=None, max_length=2000)


class CandidateReviewResponse(BaseModel):
    candidate_id: str
    status: Literal["accepted", "rejected"]
    message: str


class AnalyzeExceptionRequest(BaseModel):
    candidate_id: str | None = None


class AnalyzeExceptionResponse(BaseModel):
    exception_id: str
    explanation: str
    suggestion: str
    has_collision: bool = False
    collision_warning: str | None = None
    competing_bank_transactions: list[str] = []
    confidence: str | None = "high"

