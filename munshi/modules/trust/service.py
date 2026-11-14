"""Trust facade for other modules and routers: reports, proofs, status, anchor runs."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.errors import NotFound
from core.hashing import sha256_hex
from modules.trust import audit, batcher, proofs
from modules.trust.anchor_port import effective_mode
from modules.trust.models import MerkleBatch, Report


def register_report(s: Session, ws: str, actor_id: str, period_id: str, period_name: str, pdf: bytes,
                    pack_json: dict, filename: str) -> dict:
    sha = sha256_hex(pdf)
    existing = s.scalar(select(Report).where(Report.sha256 == sha))
    if existing is not None:  # deterministic PDF: same inputs -> same report
        return report_view(existing)
    ev = audit.record(s, ws, "report.published", "report", sha, actor_id,
                      {"report_sha256": sha, "period": period_name, "kind": "investor_pack"})
    r = Report(workspace_id=ws, period_id=period_id, sha256=sha, filename=filename, pdf=pdf, pack_json=pack_json,
               audit_seq=ev.seq, created_by=actor_id)
    s.add(r)
    s.flush()
    return report_view(r)


def report_view(r: Report) -> dict:
    return {"id": r.id, "period_id": r.period_id, "kind": r.kind, "sha256": r.sha256, "filename": r.filename,
            "audit_seq": r.audit_seq, "created_at": r.created_at.isoformat() if r.created_at else None}


def _report(s: Session, ws: str, report_id: str) -> Report:
    r = s.scalar(select(Report).where(Report.workspace_id == ws, Report.id == report_id))
    if r is None:
        raise NotFound("Report not found")
    return r


def get_report_pdf(s: Session, ws: str, report_id: str) -> tuple[bytes, str]:
    r = _report(s, ws, report_id)
    return r.pdf, r.filename


def report_for_approval(s: Session, ws: str, report_id: str) -> dict:
    r = _report(s, ws, report_id)
    return {"pack_json": r.pack_json, "pdf_sha256": r.sha256}


def proof_bundle(s: Session, ws: str, report_id: str) -> dict:
    return proofs.bundle_for(s, _report(s, ws, report_id))


def anchor_mode(s: Session) -> str:
    return effective_mode(s)


def run_anchor(s: Session, trigger: str, workspace_id: str | None = None) -> list[dict]:
    return batcher.run(s, trigger, workspace_id)


def status(s: Session, ws: str) -> dict:
    chain = audit.verify_chain(s, ws)
    last = s.scalar(select(MerkleBatch).where(MerkleBatch.workspace_id == ws).order_by(MerkleBatch.batch_seq.desc()))
    return {"chain_length": chain["length"], "chain_valid": chain["ok"], "first_broken_seq": chain["first_broken_seq"],
            "head_hash": chain.get("head_hash"), "anchor_mode": effective_mode(s),
            "last_anchor": batcher.batch_view(last) if last else None}


def recent_events(s: Session, ws: str, limit: int = 50) -> list[dict]:
    from modules.trust.models import AuditEvent

    rows = s.scalars(select(AuditEvent).where(AuditEvent.workspace_id == ws).order_by(AuditEvent.seq.desc())
                     .limit(limit))
    return [{"seq": e.seq, "type": e.event_type, "object_type": e.object_type, "object_id": e.object_id,
             "actor_id": e.actor_id, "at": e.occurred_at, "hash": e.hash, "is_leaf": e.is_leaf} for e in rows]
