from __future__ import annotations

from pydantic import BaseModel


class ProposalOut(BaseModel):
    id: str
    document_id: str
    status: str  # DRAFT_AI | NEEDS_REVIEW | DUPLICATE | MANUAL_ENTRY_REQUIRED
    reasons: list[str]
    draft_entry_id: str | None
    ruleset_version: str | None
    llm_mode: str
    doc_type: str | None
    total_paise: int | None
    facts: dict | None
    created_at: str | None


class ExtractionOut(BaseModel):
    id: str
    llm_mode: str
    data: dict | None
    confidence_min: float | None
    valid: bool
    issues: list[dict]


class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: str
    duplicate_of: str | None
    created_at: str | None
    llm_mode: str | None
    extraction: ExtractionOut | None
    proposal: ProposalOut | None


class ProposalPage(BaseModel):
    items: list[ProposalOut]
    next_cursor: str | None
