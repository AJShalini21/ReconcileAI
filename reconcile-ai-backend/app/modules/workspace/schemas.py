from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class WorkspaceRun(BaseModel):
    id: str
    date: datetime
    bank_file: str = "—"
    ledger_file: str = "—"
    transactions: int
    status: str
    tone: Literal["success", "warning", "error", "info", "neutral"]


class WorkspaceMapping(BaseModel):
    id: str
    original: str
    matched: str
    source: str
    confidence: str
    status: Literal["Pending Review", "Approved", "Rejected"]


class WorkspaceCandidateView(BaseModel):
    id: str
    ledger_entry_id: str | None = None
    title: str | None = None
    customer: str | None = None
    ledger_value: str
    ledger_date: str | None = None
    ledger_reference: str | None = None
    invoice_reference: str | None = None
    difference: str
    confidence: int | None = None
    match_status: str | None = None
    amount_diff_text: str | None = None
    date_diff_text: str | None = None
    entity_diff_text: str | None = None
    ref_diff_text: str | None = None
    suggestion: str | None = None
    evidence: str | None = None
    has_collision: bool = False
    collision_warning: str | None = None
    competing_bank_transactions: list[str] = []


class WorkspaceException(BaseModel):
    id: str
    entity: str
    customer: str | None
    reason: str
    reason_type: str
    run: str
    status: Literal["Pending Review", "Approved", "Rejected"]
    bank_transaction_id: str | None
    ledger_entry_id: str | None
    bank_description: str | None
    bank_label: str
    bank_value: str
    ledger_label: str
    ledger_value: str
    difference: str
    bank_date: str | None
    ledger_date: str | None
    bank_reference: str | None
    ledger_reference: str | None
    invoice_reference: str | None
    suggestion: str | None
    explanation: str | None = None
    ai_analyzed_at: datetime | None = None
    candidates: list[WorkspaceCandidateView] = []


class WorkspaceAuditEvent(BaseModel):
    title: str
    action: str
    run: str
    resource: str
    description: str
    date: datetime
    tone: Literal["success", "warning", "error", "info", "neutral"]
    icon: Literal["audit", "mapping", "upload", "history"]


class WorkspaceMetrics(BaseModel):
    total_runs: int
    matched_transactions: int
    pending_reviews: int
    entity_mappings: int
    audited_approved_exceptions: int = 0


class WorkspaceResponse(BaseModel):
    metrics: WorkspaceMetrics
    runs: list[WorkspaceRun]
    mappings: list[WorkspaceMapping]
    exceptions: list[WorkspaceException]
    audit_events: list[WorkspaceAuditEvent]
