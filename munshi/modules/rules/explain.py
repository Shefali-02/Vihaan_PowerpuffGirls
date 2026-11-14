"""Human-readable explanation of an engine result (for the review UI)."""
from __future__ import annotations

from modules.ledger.money import format_inr
from modules.rules.models import DraftJournal, Rejection


def explain(result: DraftJournal | Rejection) -> list[str]:
    if isinstance(result, Rejection):
        return [f"Rejected: {r['message']}" for r in result.reasons]
    out = [f"Ruleset {result.ruleset_version}; supply {result.supply_type}."]
    for ln in result.lines:
        side = f"Dr {format_inr(ln.debit_paise)}" if ln.debit_paise else f"Cr {format_inr(ln.credit_paise)}"
        out.append(f"{ln.account_code} {side} {('[' + ln.tax_tag + ']') if ln.tax_tag else ''} {ln.memo}".strip())
    out += [f"Review: {r}" for r in result.review_reasons]
    out += [f"Hint: {h}" for h in result.hints]
    return out
