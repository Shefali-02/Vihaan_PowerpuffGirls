"""Deterministic checks on extracted data. Each issue: {code, field, message, severity}."""
from __future__ import annotations

from datetime import date

from core.hashing import sha256_hex
from modules.ledger.money import rupees_to_paise, tax_on
from modules.rules.service import gstin_errors, is_valid_gstin, is_valid_pan

__all__ = ["gstin_errors", "is_valid_gstin", "is_valid_pan", "validate_extraction", "dedupe_key"]


def _issue(code: str, field: str, message: str, severity: str = "error") -> dict:
    return {"code": code, "field": field, "message": message, "severity": severity}


def dedupe_key(vendor_gstin: str | None, invoice_no: str | None, total: str | None, invoice_date: str | None) -> str:
    """Duplicate detector key: counterparty + invoice no + total + date."""
    norm = "|".join([(vendor_gstin or "").upper(), (invoice_no or "").strip().upper(),
                     str(rupees_to_paise(total)) if total else "", invoice_date or ""])
    return sha256_hex(norm.encode())


def validate_extraction(ex, workspace_gstin: str, period_open) -> list[dict]:
    """`ex` is an InvoiceExtraction; `period_open(date) -> bool` comes from ledger.service."""
    issues: list[dict] = []
    for field in ("seller_gstin", "buyer_gstin"):
        val = getattr(ex, field)
        if val:
            for msg in gstin_errors(val):
                issues.append(_issue("INVALID_GSTIN", field, msg))
    if ex.classify(workspace_gstin)[0] == "unknown":
        issues.append(_issue("NOT_OUR_INVOICE", "buyer_gstin",
                             "Neither seller nor buyer GSTIN matches this workspace"))
    if not ex.invoice_no:
        issues.append(_issue("MISSING_FIELD", "invoice_no", "Invoice number missing"))
    try:
        d = date.fromisoformat(ex.invoice_date or "")
        if not period_open(d):
            issues.append(_issue("PERIOD_NOT_OPEN", "invoice_date", f"No open period for {d}"))
    except ValueError:
        issues.append(_issue("BAD_DATE", "invoice_date", "Invoice date missing or not YYYY-MM-DD"))
    if not ex.lines:
        issues.append(_issue("NO_LINES", "lines", "No line items found"))
        return issues
    try:
        taxable = [rupees_to_paise(ln.taxable_value) for ln in ex.lines]
        rates = [rupees_to_paise(ln.gst_rate_pct) if ln.gst_rate_pct else None for ln in ex.lines]
    except ValueError:
        issues.append(_issue("BAD_AMOUNT", "lines", "Unparseable amount or rate"))
        return issues
    if ex.total and all(r is not None for r in rates):
        computed = sum(t + tax_on(t, r) for t, r in zip(taxable, rates))
        declared = rupees_to_paise(ex.total)
        if abs(computed - declared) > len(ex.lines):  # within 1 paisa per line
            issues.append(_issue("ARITHMETIC_MISMATCH", "total",
                                 f"Lines + tax = {computed} paise but invoice total says {declared} paise"))
        if ex.tax_total:
            tax = sum(tax_on(t, r) for t, r in zip(taxable, rates))
            if abs(tax - rupees_to_paise(ex.tax_total)) > len(ex.lines):
                issues.append(_issue("TAX_MISMATCH", "tax_total", "Printed tax total differs from computed tax"))
    elif not ex.total:
        issues.append(_issue("MISSING_FIELD", "total", "Invoice total missing"))
    return issues
