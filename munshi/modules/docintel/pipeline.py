"""ingest -> classify -> read -> extract -> validate -> score -> route.

Routing outcomes (Proposal.status):
  DRAFT_AI               engine matched, validations pass, confidence >= threshold, amount < limit
  NEEDS_REVIEW           anything else that is still usable (reasons listed; draft created when the engine accepts)
  DUPLICATE              same file, or same counterparty + invoice no + total + date
  MANUAL_ENTRY_REQUIRED  AI gateway failed or file unreadable
"""
from __future__ import annotations

import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import UnsupportedDocument
from core.hashing import sha256_hex
from modules.ai import gateway
from modules.docintel import validators
from modules.docintel.models import Document, Extraction, Proposal
from modules.docintel.schemas import InvoiceExtraction, schema_errors
from modules.identity import service as identity
from modules.ledger import service as ledger
from modules.trust import audit

PROMPT_ID = "docintel.invoice_extract@1"
TEXT_TYPES = (".txt", ".md", ".csv")
MAX_BYTES = 10 * 1024 * 1024


def classify_file(filename: str, content_type: str) -> str:
    name = filename.lower()
    if name.endswith(TEXT_TYPES) or content_type.startswith("text/"):
        return "text"
    if name.endswith(".pdf") or content_type == "application/pdf":
        return "pdf"
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")) or content_type.startswith("image/"):
        return "image"
    return "unsupported"


def read_text(kind: str, data: bytes) -> str | None:
    if kind == "text":
        return data.decode("utf-8", errors="replace")
    if kind == "pdf":
        try:
            from pypdf import PdfReader

            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        except Exception:
            return None
    return None  # images: no OCR in the MVP -> manual entry


def _proposal(s, ws, doc, status, reasons, llm_mode, extraction=None, **kw) -> Proposal:
    p = Proposal(workspace_id=ws, document_id=doc.id, extraction_id=extraction.id if extraction else None,
                 status=status, reasons=reasons, llm_mode=llm_mode, **kw)
    s.add(p)
    doc.status = status
    s.flush()
    return p


def ingest(s: Session, principal, filename: str, content_type: str, data: bytes) -> tuple[Document, Proposal]:
    identity.require_role(principal, "ACCOUNTANT", "CA")
    ws = principal.workspace_id
    if len(data) > MAX_BYTES:
        raise UnsupportedDocument("File larger than 10 MB")
    kind = classify_file(filename, content_type or "")
    if kind == "unsupported":
        raise UnsupportedDocument(f"Unsupported file type: {filename}")
    sha = sha256_hex(data)
    llm_mode = gateway.current_mode()

    doc = Document(workspace_id=ws, filename=filename, content_type=content_type or "application/octet-stream",
                   size_bytes=len(data), sha256=sha, content=data, status="RECEIVED", uploaded_by=principal.user_id)
    s.add(doc)
    s.flush()
    audit.record(s, ws, "document.ingested", "document", doc.id, principal.user_id, {"sha256": sha})

    # duplicate by file hash
    prior = s.scalar(select(Document).where(Document.workspace_id == ws, Document.sha256 == sha,
                                            Document.id != doc.id).order_by(Document.created_at))
    if prior is not None:
        doc.duplicate_of = prior.id
        return doc, _proposal(s, ws, doc, "DUPLICATE", [f"Same file already uploaded as {prior.id}"], llm_mode)

    text = read_text(kind, data)
    doc.text = text
    if not text or not text.strip():
        return doc, _proposal(s, ws, doc, "MANUAL_ENTRY_REQUIRED", ["No machine-readable text (no OCR in MVP)"],
                              llm_mode)

    # extract via the gateway (redaction happens inside)
    resp = gateway.run_structured(s, ws, PROMPT_ID, text, validate=schema_errors)
    if resp.status == "ERROR":
        return doc, _proposal(s, ws, doc, "MANUAL_ENTRY_REQUIRED", [f"AI gateway unavailable: {resp.error}"],
                              resp.llm_mode)
    ext = Extraction(workspace_id=ws, document_id=doc.id, ai_run_id=resp.run_id, llm_mode=resp.llm_mode,
                     data=resp.output)
    s.add(ext)
    s.flush()
    if resp.status == "INVALID_SCHEMA":
        ext.issues = [{"code": "INVALID_SCHEMA", "field": "*", "message": resp.error, "severity": "error"}]
        return doc, _proposal(s, ws, doc, "NEEDS_REVIEW", [f"Extraction did not match schema: {resp.error}"],
                              resp.llm_mode, ext)

    ex = InvoiceExtraction.model_validate(resp.output)
    wsc = identity.get_workspace(s, ws)
    doc_type, cp_gstin, _ = ex.classify(wsc.gstin)
    ext.dedupe_key = validators.dedupe_key(cp_gstin, ex.invoice_no, ex.total, ex.invoice_date)
    ext.confidence_min = ex.min_confidence()

    # duplicate by business key
    dup = s.scalar(select(Extraction).where(Extraction.workspace_id == ws, Extraction.dedupe_key == ext.dedupe_key,
                                            Extraction.id != ext.id))
    if dup is not None:
        return doc, _proposal(s, ws, doc, "DUPLICATE",
                              [f"Same counterparty, invoice no, total and date as document {dup.document_id}"],
                              resp.llm_mode, ext, doc_type=doc_type)

    issues = validators.validate_extraction(ex, wsc.gstin, lambda d: ledger.is_period_open(s, ws, d))
    ext.issues = issues
    errors = [i for i in issues if i["severity"] == "error"]
    ext.valid = not errors
    if errors:
        return doc, _proposal(s, ws, doc, "NEEDS_REVIEW", [i["message"] for i in errors], resp.llm_mode, ext,
                              doc_type=doc_type)

    # score + route through the rules engine
    facts = ex.to_facts(wsc.gstin)
    result = ledger.preview(s, ws, facts)
    if not hasattr(result, "lines"):  # Rejection
        return doc, _proposal(s, ws, doc, "NEEDS_REVIEW", [r["message"] for r in result.reasons], resp.llm_mode,
                              ext, doc_type=doc_type, ruleset_version=result.ruleset_version,
                              facts=facts.model_dump(mode="json"))
    cfg = get_settings()
    reasons = list(result.review_reasons)
    if ext.confidence_min < cfg.CONFIDENCE_THRESHOLD:
        reasons.append(f"Low extraction confidence ({ext.confidence_min:.2f} < {cfg.CONFIDENCE_THRESHOLD:.2f})")
    if result.total_paise >= cfg.AUTO_DRAFT_AMOUNT_LIMIT_PAISE:
        reasons.append("Amount at or above auto-draft limit")
    draft = ledger.create_draft(s, principal, facts, source_document_id=doc.id)
    status = "NEEDS_REVIEW" if reasons else "DRAFT_AI"
    return doc, _proposal(s, ws, doc, status, reasons, resp.llm_mode, ext, draft_entry_id=draft["id"],
                          doc_type=doc_type, ruleset_version=result.ruleset_version, total_paise=result.total_paise,
                          facts=facts.model_dump(mode="json"))
