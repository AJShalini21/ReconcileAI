from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CSVUploadResponse(BaseModel):
    fileName: str
    status: str = "validated"
    validRows: int = 0

    run_id: str | None = None
    bank_import_id: str | None = None
    ledger_import_id: str | None = None
    matchedCount: int = 0
    pendingReviewCount: int = 0
    exceptionCount: int = 0
    unmatchedCount: int = 0


class CSVPreviewResponse(BaseModel):
    fileName: str
    totalRows: int = 0
    columns: list[str] = Field(default_factory=list)
    preview: list[dict[str, Any]] = Field(default_factory=list)
