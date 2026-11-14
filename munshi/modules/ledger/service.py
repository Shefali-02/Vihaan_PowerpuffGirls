"""The ONLY writer of journals. Every write goes through the rules engine first."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from core import outbox
from core.canonical import canonical_json
from core.db import utcnow
from core.errors import DraftMismatch, InvalidTransition, NotFound, PeriodNotFound, RuleRejected, UnbalancedJournal
from core.hashing import sha256_hex
from modules.identity import service as identity
from modules.ledger import coa, periods, reports
from modules.ledger import repository as repo
from modules.ledger.models import JournalEntry, JournalLine, Period
from modules.ledger.money import format_inr
from modules.rules import service as rules
from modules.trust import audit

POSTERS = ("ACCOUNTANT", "CA")


# ---- views ---------------------------------------------------------------------
def line_view(ln: JournalLine) -> dict:
    return {"line_no": ln.line_no, "account_code": ln.account_code, "debit_paise": ln.debit_paise,
            "credit_paise": ln.credit_paise, "tax_tag": ln.tax_tag, "memo": ln.memo}


def entry_view(e: JournalEntry) -> dict:
    total = sum(ln.debit_paise for ln in e.lines)
    return {
        "id": e.id, "status": e.status, "entry_date": e.entry_date.isoformat(), "narration": e.narration,
        "period_id": e.period_id, "doc_type": e.doc_type, "source_document_id": e.source_document_id,
        "ruleset_version": e.ruleset_version, "supply_type": e.supply_type,
        "needs_review": e.needs_review, "review_reasons": e.review_reasons or [], "hints": e.hints or [],
        "lines": [line_view(ln) for ln in e.lines], "total_paise": total, "total": format_inr(total),
        "created_by": e.created_by, "posted_by": e.posted_by,
        "posted_at": e.posted_at.isoformat() if e.posted_at else None, "reverses_entry_id": e.reverses_entry_id,
    }


def _lines_hash(lines: list[dict]) -> str:
    return sha256_hex(canonical_json([{k: ln[k] for k in ("account_code", "debit_paise", "credit_paise", "tax_tag")}
                                      for ln in lines]))


# ---- periods -------------------------------------------------------------------
def ensure_fy_period(s: Session, ws: str, on: date) -> Period:
    start, end = periods.fy_bounds(on)
    p = repo.period_for_date(s, ws, on)
    if p is None:
        p = Period(workspace_id=ws, name=periods.fy_name(on), start_date=start, end_date=end, status="OPEN")
        s.add(p)
        s.flush()
    return p


def seed_chart(s: Session, ws: str) -> int:
    return coa.seed_chart(s, ws)


def period_view(p: Period) -> dict:
    return {"id": p.id, "name": p.name, "start_date": p.start_date.isoformat(), "end_date": p.end_date.isoformat(),
            "status": p.status, "locked_at": p.locked_at.isoformat() if p.locked_at else None,
            "locked_by": p.locked_by}


def list_periods(s: Session, ws: str) -> list[dict]:
    return [period_view(p) for p in repo.periods(s, ws)]


def get_period(s: Session, ws: str, period_id: str) -> dict:
    p = repo.period(s, ws, period_id)
    if p is None:
        raise NotFound("Period not found")
    return period_view(p)


def current_period(s: Session, ws: str, on: date | None = None) -> dict:
    p = repo.period_for_date(s, ws, on or date.today())
    if p is None:
        ps = repo.periods(s, ws)
        if not ps:
            raise PeriodNotFound("Workspace has no periods")
        p = ps[-1]
    return period_view(p)


def is_period_open(s: Session, ws: str, on: date) -> bool:
    p = repo.period_for_date(s, ws, on)
    return p is not None and p.status == "OPEN"


def lock_period(s: Session, ws: str, period_id: str, actor_id: str) -> dict:
    p = repo.period(s, ws, period_id)
    if p is None:
        raise NotFound("Period not found")
    if p.status == "LOCKED":
        return period_view(p)
    if repo.count_entries(s, ws, period_id, "DRAFT"):
        raise InvalidTransition("Period has unposted drafts; post or discard them before close")
    tb = reports.trial_balance(s, ws, period_id)
    if not tb["balanced"]:
        raise UnbalancedJournal("Trial balance does not balance; cannot lock")
    p.status, p.locked_at, p.locked_by = "LOCKED", utcnow(), actor_id
    s.flush()
    audit.record(s, ws, "period.locked", "period", p.id, actor_id,
                 {"period": p.name, "trial_balance_sha256": sha256_hex(canonical_json(tb))})
    outbox.emit(s, ws, "period.locked", {"period_id": p.id})
    return period_view(p)


# ---- journals ------------------------------------------------------------------
def _ctx(s: Session, ws: str) -> rules.TaxContext:
    w = identity.get_workspace(s, ws)
    return rules.TaxContext(workspace_gstin=w.gstin, workspace_state=w.state_code)


def preview(s: Session, ws: str, facts: rules.InvoiceFacts):
    """Run the engine without writing (used by docintel to decide routing)."""
    return rules.build_journal(facts, _ctx(s, ws))


def create_draft(s: Session, principal, facts: rules.InvoiceFacts, source_document_id: str | None = None) -> dict:
    identity.require_role(principal, *POSTERS)
    ws = principal.workspace_id
    result = rules.build_journal(facts, _ctx(s, ws))
    if isinstance(result, rules.Rejection):
        raise RuleRejected("Rules engine rejected the invoice", extra={"reasons": result.reasons})
    if not result.balanced:  # defensive: engine invariant
        raise UnbalancedJournal()
    p = repo.period_for_date(s, ws, result.entry_date)
    periods.assert_open(p, result.entry_date)
    e = JournalEntry(
        workspace_id=ws, period_id=p.id, entry_date=result.entry_date, narration=result.narration, status="DRAFT",
        doc_type=result.doc_type, source_document_id=source_document_id,
        input_facts=facts.model_dump(mode="json"), ruleset_version=result.ruleset_version,
        supply_type=result.supply_type, needs_review=result.needs_review, review_reasons=result.review_reasons,
        hints=result.hints, explanation=result.explanation, created_by=principal.user_id,
    )
    e.lines = [JournalLine(workspace_id=ws, line_no=i, account_code=ln.account_code, debit_paise=ln.debit_paise,
                           credit_paise=ln.credit_paise, tax_tag=ln.tax_tag, memo=ln.memo)
               for i, ln in enumerate(result.lines, 1)]
    s.add(e)
    s.flush()
    outbox.emit(s, ws, "journal.drafted", {"entry_id": e.id})
    return entry_view(e)


def get_entry(s: Session, ws: str, entry_id: str) -> dict:
    e = repo.entry(s, ws, entry_id)
    if e is None:
        raise NotFound("Journal entry not found")
    return entry_view(e)


def entry_snapshot(s: Session, ws: str, entry_id: str) -> dict:
    """Stable snapshot used for approval version hashes."""
    v = get_entry(s, ws, entry_id)
    return {"id": v["id"], "status": v["status"], "entry_date": v["entry_date"], "narration": v["narration"],
            "lines": [{k: ln[k] for k in ("account_code", "debit_paise", "credit_paise", "tax_tag")}
                      for ln in v["lines"]]}


def post(s: Session, principal, entry_id: str) -> dict:
    identity.require_role(principal, *POSTERS)
    ws = principal.workspace_id
    e = repo.entry(s, ws, entry_id)
    if e is None:
        raise NotFound("Journal entry not found")
    if e.status != "DRAFT":
        raise InvalidTransition(f"Entry is {e.status}; only DRAFT entries can be posted")
    p = repo.period_for_date(s, ws, e.entry_date)
    periods.assert_open(p, e.entry_date)
    if e.input_facts is not None:  # re-run the engine: the stored draft must be exactly what rules produce now
        result = rules.build_journal(rules.InvoiceFacts.model_validate(e.input_facts), _ctx(s, ws))
        if isinstance(result, rules.Rejection):
            raise RuleRejected("Rules engine now rejects this draft", extra={"reasons": result.reasons})
        expected = sorted(ln.key() for ln in result.lines)
        actual = sorted((ln.account_code, ln.debit_paise, ln.credit_paise, ln.tax_tag or "") for ln in e.lines)
        if expected != actual:
            raise DraftMismatch("Draft lines differ from current rules output; re-draft the entry")
    dr = sum(ln.debit_paise for ln in e.lines)
    cr = sum(ln.credit_paise for ln in e.lines)
    if dr != cr or dr <= 0:
        raise UnbalancedJournal(f"Debits {dr} != credits {cr}")
    e.status, e.posted_by, e.posted_at = "POSTED", principal.user_id, utcnow()
    s.flush()
    view = entry_view(e)
    audit.record(s, ws, "journal.posted", "journal", e.id, principal.user_id,
                 {"entry_id": e.id, "period": p.name, "total_paise": dr, "lines_sha256": _lines_hash(view["lines"]),
                  "ruleset_version": e.ruleset_version})
    outbox.emit(s, ws, "journal.posted", {"entry_id": e.id})
    return view


def reverse(s: Session, principal, entry_id: str, on: date | None = None, reason: str = "") -> dict:
    identity.require_role(principal, *POSTERS)
    ws = principal.workspace_id
    e = repo.entry(s, ws, entry_id)
    if e is None:
        raise NotFound("Journal entry not found")
    if e.status != "POSTED":
        raise InvalidTransition("Only POSTED entries can be reversed")
    if repo.reversal_of(s, ws, entry_id) is not None:
        raise InvalidTransition("Entry already reversed")
    on = on or date.today()
    p = repo.period_for_date(s, ws, on)
    periods.assert_open(p, on)
    r = JournalEntry(workspace_id=ws, period_id=p.id, entry_date=on, status="POSTED",
                     narration=f"Reversal of {e.narration}" + (f" ({reason})" if reason else ""),
                     doc_type=e.doc_type, reverses_entry_id=e.id, created_by=principal.user_id,
                     posted_by=principal.user_id, posted_at=utcnow(), review_reasons=[], hints=[], explanation=[])
    r.lines = [JournalLine(workspace_id=ws, line_no=ln.line_no, account_code=ln.account_code,
                           debit_paise=ln.credit_paise, credit_paise=ln.debit_paise, tax_tag=ln.tax_tag,
                           memo=f"reversal: {ln.memo}") for ln in e.lines]
    s.add(r)
    s.flush()
    view = entry_view(r)
    audit.record(s, ws, "journal.reversed", "journal", r.id, principal.user_id,
                 {"entry_id": r.id, "reverses": e.id, "lines_sha256": _lines_hash(view["lines"])})
    outbox.emit(s, ws, "journal.reversed", {"entry_id": r.id, "reverses": e.id})
    return view


# ---- reports -------------------------------------------------------------------
def trial_balance(s: Session, ws: str, period_id: str) -> dict:
    if repo.period(s, ws, period_id) is None:
        raise NotFound("Period not found")
    return reports.trial_balance(s, ws, period_id)


def profit_and_loss(s: Session, ws: str, period_id: str) -> dict:
    if repo.period(s, ws, period_id) is None:
        raise NotFound("Period not found")
    return reports.profit_and_loss(s, ws, period_id)


def tax_tag_totals(s: Session, ws: str, period_id: str) -> dict[str, dict[str, int]]:
    return {t: {"debit_paise": d, "credit_paise": c} for t, d, c in repo.tag_totals(s, ws, period_id)}
