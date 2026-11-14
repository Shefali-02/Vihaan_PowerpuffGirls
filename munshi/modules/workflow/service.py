"""Maker-checker approvals. A preparer never approves their own object; high-risk needs a CA."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import outbox
from core.config import get_settings
from core.db import utcnow
from core.errors import (AnchorFailed, Conflict, NotFound, RoleNotPermitted, SelfApprovalForbidden,
                         ValidationFailed, VersionHashMismatch)
from core.pagination import apply_cursor, page
from modules.identity import service as identity
from modules.ledger import service as ledger
from modules.trust import audit
from modules.trust import service as trust
from modules.workflow import state_machine, version_hash
from modules.workflow.models import Approval, Comment

OBJECT_TYPES = ("journal", "period_close", "investor_pack")
HIGH_RISK_TYPES = ("period_close", "investor_pack")


def _snapshot(s: Session, ws: str, object_type: str, object_id: str) -> dict:
    if object_type == "investor_pack":
        r = trust.report_for_approval(s, ws, object_id)
        return version_hash.snapshot(s, ws, object_type, object_id, extra=r)
    return version_hash.snapshot(s, ws, object_type, object_id)


def _risk(object_type: str, snap: dict) -> str:
    if object_type in HIGH_RISK_TYPES:
        return "HIGH"
    total = sum(ln["debit_paise"] for ln in snap["entry"]["lines"])
    return "HIGH" if total >= get_settings().AUTO_DRAFT_AMOUNT_LIMIT_PAISE else "LOW"


def _diff(old: dict, new: dict) -> list[dict]:
    """Shallow, readable diff of the approved snapshot vs the object as it is now."""
    def rows(snap):
        if snap["type"] == "journal":
            return {f"{ln['account_code']}|{ln['tax_tag']}": ln for ln in snap["entry"]["lines"]}
        if snap["type"] == "period_close":
            return {r["code"]: r for r in snap["trial_balance"]}
        return {"pack": {"pdf_sha256": snap["pdf_sha256"]}}
    a, b = rows(old), rows(new)
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out.append({"key": k, "before": a.get(k), "after": b.get(k)})
    return out


def approval_view(s: Session, a: Approval, include_diff: bool = False) -> dict:
    v = {"id": a.id, "object_type": a.object_type, "object_id": a.object_id, "state": a.state, "risk": a.risk,
         "version_hash": a.version_hash, "requested_by": a.requested_by, "decided_by": a.decided_by,
         "decided_at": a.decided_at.isoformat() if a.decided_at else None, "decision_note": a.decision_note,
         "anchor_batch": a.anchor_batch, "created_at": a.created_at.isoformat() if a.created_at else None,
         "snapshot": a.snapshot}
    if include_diff and a.state == "IN_REVIEW":
        try:
            cur = _snapshot(s, a.workspace_id, a.object_type, a.object_id)
            cur_hash = version_hash.compute(cur)
            v.update({"current_version_hash": cur_hash, "stale": cur_hash != a.version_hash,
                      "diff": _diff(a.snapshot, cur)})
        except NotFound:
            v.update({"current_version_hash": None, "stale": True, "diff": []})
    return v


def _get(s: Session, ws: str, approval_id: str) -> Approval:
    a = s.scalar(select(Approval).where(Approval.workspace_id == ws, Approval.id == approval_id))
    if a is None:
        raise NotFound("Approval not found")
    return a


def request_approval(s: Session, p, object_type: str, object_id: str, comment: str | None = None) -> dict:
    identity.require_role(p, "ACCOUNTANT", "CA")
    if object_type not in OBJECT_TYPES:
        raise ValidationFailed(f"object_type must be one of {OBJECT_TYPES}")
    ws = p.workspace_id
    open_req = s.scalar(select(Approval).where(Approval.workspace_id == ws, Approval.object_type == object_type,
                                               Approval.object_id == object_id,
                                               Approval.state.in_(("IN_REVIEW", "APPROVED", "LOCKED", "ANCHORED"))))
    if open_req is not None:
        raise Conflict(f"An approval for this object already exists ({open_req.state})", extra={"approval_id": open_req.id})
    if object_type == "period_close" and ledger.get_period(s, ws, object_id)["status"] != "OPEN":
        raise Conflict("Period is already locked")
    snap = _snapshot(s, ws, object_type, object_id)
    a = Approval(workspace_id=ws, object_type=object_type, object_id=object_id, state="IN_REVIEW",
                 risk=_risk(object_type, snap), version_hash=version_hash.compute(snap), snapshot=snap,
                 requested_by=p.user_id)
    s.add(a)
    s.flush()
    if comment:
        s.add(Comment(workspace_id=ws, approval_id=a.id, author_id=p.user_id, body=comment))
    audit.record(s, ws, "approval.requested", "approval", a.id, p.user_id,
                 {"object_type": object_type, "object_id": object_id, "version_hash": a.version_hash, "risk": a.risk})
    outbox.emit(s, ws, "approval.requested", {"approval_id": a.id})
    return approval_view(s, a)


def _check_decider(p, a: Approval) -> None:
    if p.role == "INVESTOR":
        raise RoleNotPermitted("Investors have read-only access")
    if p.user_id == a.requested_by:
        raise SelfApprovalForbidden("You requested this approval; a different user must decide")
    if a.risk == "HIGH" and p.role != "CA":
        raise RoleNotPermitted("High-risk approvals require a CA")


def decide(s: Session, p, approval_id: str, note: str | None = None) -> dict:
    ws = p.workspace_id
    a = _get(s, ws, approval_id)
    if a.state != "IN_REVIEW":
        state_machine.transition(a.state, "APPROVED")  # raises INVALID_STATE_TRANSITION
    _check_decider(p, a)
    current = version_hash.compute(_snapshot(s, ws, a.object_type, a.object_id))
    if current != a.version_hash:
        raise VersionHashMismatch("Object changed since approval was requested; request a fresh approval",
                                  extra={"expected": a.version_hash, "current": current})
    a.state = state_machine.transition(a.state, "APPROVED")
    a.decided_by, a.decided_at, a.decision_note = p.user_id, utcnow(), note
    s.flush()
    audit.record(s, ws, "approval.decided", "approval", a.id, p.user_id,
                 {"decision": "APPROVED", "object_type": a.object_type, "object_id": a.object_id,
                  "version_hash": a.version_hash})
    outbox.emit(s, ws, "approval.decided", {"approval_id": a.id, "decision": "APPROVED"})
    if a.object_type == "period_close":
        ledger.lock_period(s, ws, a.object_id, p.user_id)
        a.state = state_machine.transition(a.state, "LOCKED")
    if a.object_type in HIGH_RISK_TYPES:
        try:
            with s.begin_nested():
                batches = trust.run_anchor(s, trigger=f"{a.object_type}_approved", workspace_id=ws)
            a.anchor_batch = batches[0] if batches else None
            a.state = state_machine.transition(a.state, "ANCHORED")
        except AnchorFailed as e:  # approval stands; anchoring can be retried via /v1/admin/anchor/run
            a.decision_note = (note or "") + f" [anchor pending: {e.detail}]"
    s.flush()
    return approval_view(s, a)


def request_changes(s: Session, p, approval_id: str, note: str) -> dict:
    ws = p.workspace_id
    a = _get(s, ws, approval_id)
    if p.role == "INVESTOR":
        raise RoleNotPermitted("Investors have read-only access")
    if p.user_id == a.requested_by:
        raise SelfApprovalForbidden("Requester cannot review their own request")
    a.state = state_machine.transition(a.state, "CHANGES_REQUESTED")
    a.decided_by, a.decided_at, a.decision_note = p.user_id, utcnow(), note
    s.add(Comment(workspace_id=ws, approval_id=a.id, author_id=p.user_id, body=note))
    s.flush()
    audit.record(s, ws, "approval.decided", "approval", a.id, p.user_id,
                 {"decision": "CHANGES_REQUESTED", "object_type": a.object_type, "object_id": a.object_id,
                  "version_hash": a.version_hash})
    return approval_view(s, a)


def list_approvals(s: Session, ws: str, state: str | None, cursor: str | None, limit: int) -> dict:
    stmt = select(Approval).where(Approval.workspace_id == ws)
    if state:
        stmt = stmt.where(Approval.state == state)
    rows, nxt = page(list(s.scalars(apply_cursor(stmt, Approval, cursor, limit))), limit)
    return {"items": [approval_view(s, a, include_diff=True) for a in rows], "next_cursor": nxt}


def period_close_state(s: Session, ws: str, period_id: str) -> str | None:
    a = s.scalar(select(Approval).where(Approval.workspace_id == ws, Approval.object_type == "period_close",
                                        Approval.object_id == period_id).order_by(Approval.created_at.desc()))
    return a.state if a else None


def signoffs(s: Session, ws: str, period_id: str) -> list[dict]:
    rows = s.scalars(select(Approval).where(Approval.workspace_id == ws, Approval.object_type == "period_close",
                                            Approval.object_id == period_id, Approval.decided_by.is_not(None),
                                            Approval.state.in_(("APPROVED", "LOCKED", "ANCHORED"))))
    out = []
    for a in rows:
        u = identity.user_display(s, a.decided_by, ws)
        out.append({"name": u["name"], "role": u["role"], "time": a.decided_at.isoformat(),
                    "object": "period_close", "version_hash": a.version_hash})
    return out
