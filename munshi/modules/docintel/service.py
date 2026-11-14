from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import outbox
from core.errors import NotFound
from core.pagination import apply_cursor, page
from modules.docintel import pipeline
from modules.docintel.models import Document, Extraction, Proposal


def proposal_view(p: Proposal) -> dict:
    return {"id": p.id, "document_id": p.document_id, "status": p.status, "reasons": p.reasons or [],
            "draft_entry_id": p.draft_entry_id, "ruleset_version": p.ruleset_version, "llm_mode": p.llm_mode,
            "doc_type": p.doc_type, "total_paise": p.total_paise, "facts": p.facts,
            "created_at": p.created_at.isoformat() if p.created_at else None}


def document_view(s: Session, d: Document) -> dict:
    ext = s.scalar(select(Extraction).where(Extraction.workspace_id == d.workspace_id,
                                            Extraction.document_id == d.id))
    prop = s.scalar(select(Proposal).where(Proposal.workspace_id == d.workspace_id, Proposal.document_id == d.id))
    return {
        "id": d.id, "filename": d.filename, "content_type": d.content_type, "size_bytes": d.size_bytes,
        "sha256": d.sha256, "status": d.status, "duplicate_of": d.duplicate_of,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "llm_mode": prop.llm_mode if prop else None,
        "extraction": None if ext is None else {
            "id": ext.id, "llm_mode": ext.llm_mode, "data": ext.data, "confidence_min": ext.confidence_min,
            "valid": ext.valid, "issues": ext.issues or []},
        "proposal": proposal_view(prop) if prop else None,
    }


def upload(s: Session, principal, filename: str, content_type: str, data: bytes) -> dict:
    doc, prop = pipeline.ingest(s, principal, filename, content_type, data)
    outbox.emit(s, principal.workspace_id, "document.processed", {"document_id": doc.id, "status": prop.status})
    return document_view(s, doc)


def get_document(s: Session, ws: str, doc_id: str) -> dict:
    d = s.scalar(select(Document).where(Document.workspace_id == ws, Document.id == doc_id))
    if d is None:
        raise NotFound("Document not found")
    return document_view(s, d)


def list_proposals(s: Session, ws: str, status: str | None, cursor: str | None, limit: int) -> dict:
    stmt = select(Proposal).where(Proposal.workspace_id == ws)
    if status:
        stmt = stmt.where(Proposal.status == status)
    rows, nxt = page(list(s.scalars(apply_cursor(stmt, Proposal, cursor, limit))), limit)
    return {"items": [proposal_view(p) for p in rows], "next_cursor": nxt}
