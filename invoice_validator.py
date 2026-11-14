"""
Deterministic validation of an extracted invoice. No LLM calls here.

severity "error"   -> cannot become a journal automatically (route: manual_entry)
severity "warning" -> accountant must look (route: review)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .gstin_validator import validate_gstin
from .invoice_schema import INVOICE_TYPES, DocumentType, ExtractedInvoice

REDACTION_TOKEN = re.compile(r"\[(?:AADHAAR|PHONE|PAN|BANK_ACCOUNT)_\d+\]")
TWO_PLACES = Decimal("0.01")


@dataclass
class Issue:
    code: str
    field: str
    severity: str          # 'error' | 'warning'
    message: str


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}

    def to_dict(self) -> dict:
        return {"passed": self.passed, "issues": [i.__dict__ for i in self.issues]}


def _norm_number(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _vendor_key(inv: ExtractedInvoice) -> str:
    g = inv.val("vendor_gstin")
    if g:
        return "gstin:" + g.replace(" ", "").upper()
    return "name:" + re.sub(r"[^a-z0-9]", "", (inv.val("vendor_name") or "").lower())


class DuplicateIndex:
    """In-memory stand-in for a unique index on (workspace, vendor, number, amount, date)
    and on file hash. One instance per workspace."""

    def __init__(self) -> None:
        self._files: set[str] = set()
        self._exact: set[tuple] = set()
        self._by_number: dict[tuple, tuple] = {}

    @staticmethod
    def _keys(inv: ExtractedInvoice):
        vendor, number = _vendor_key(inv), _norm_number(inv.val("invoice_number") or "")
        exact = (vendor, number, inv.val("total_amount"), inv.val("invoice_date"))
        return (vendor, number), exact

    def has_file(self, sha: str) -> bool:
        return sha in self._files

    def has_exact(self, inv: ExtractedInvoice) -> bool:
        return self._keys(inv)[1] in self._exact

    def same_number_other_details(self, inv: ExtractedInvoice) -> bool:
        k, exact = self._keys(inv)
        return k in self._by_number and self._by_number[k] != exact and exact not in self._exact

    def add(self, inv: ExtractedInvoice, file_sha: str) -> None:
        k, exact = self._keys(inv)
        self._files.add(file_sha)
        self._exact.add(exact)
        self._by_number[k] = exact


def validate_invoice(
    inv: ExtractedInvoice,
    *,
    document_type: DocumentType = DocumentType.purchase_invoice,
    today: Optional[date] = None,
    open_period: Optional[tuple[date, date]] = None,   # inclusive (start, end) of the open period
    dup_index: Optional[DuplicateIndex] = None,
    file_sha: Optional[str] = None,
    tolerance: Decimal = Decimal("1.00"),              # Rs; invoices carry round-offs
) -> ValidationReport:
    r = ValidationReport()
    add = lambda code, f, sev, msg: r.issues.append(Issue(code, f, sev, msg))

    if document_type not in INVOICE_TYPES:
        add("UNSUPPORTED_TYPE", "document_type", "error", f"{document_type.value} is not handled here")

    # 1. required fields ------------------------------------------------
    for name in ("vendor_name", "invoice_number", "invoice_date", "taxable_amount", "total_amount"):
        if inv.val(name) in (None, ""):
            add("REQUIRED", name, "error", f"{name} is missing")

    # redaction placeholders mean the real value never reached the model
    for name in ("vendor_name", "invoice_number", "vendor_gstin", "buyer_gstin"):
        v = inv.val(name)
        if v and REDACTION_TOKEN.search(v):
            add("REDACTED_FIELD", name, "error",
                f"{name} was masked by privacy redaction ({v}); enter it manually")

    # 2. GSTIN ------------------------------------------------------------
    for name in ("vendor_gstin", "buyer_gstin"):
        v = inv.val(name)
        if not v or REDACTION_TOKEN.search(v):
            continue
        g = validate_gstin(v)
        if not g.valid:
            add("GSTIN_INVALID", name, "error", f"{name} failed validation: {', '.join(g.errors)}")
    if not inv.val("vendor_gstin"):
        add("GSTIN_MISSING", "vendor_gstin", "warning",
            "no vendor GSTIN: input tax credit cannot be claimed without it")

    # 3. arithmetic -------------------------------------------------------
    taxable, total = inv.val("taxable_amount"), inv.val("total_amount")
    cgst, sgst, igst = inv.amount("cgst"), inv.amount("sgst"), inv.amount("igst")
    tax = cgst + sgst + igst
    if taxable is not None and total is not None and abs(taxable + tax - total) > tolerance:
        add("ARITHMETIC_TOTAL", "total_amount", "error",
            f"taxable {taxable} + tax {tax} = {taxable + tax}, but total is {total}")
    if igst and (cgst or sgst):
        add("INTRA_INTER_MIX", "igst", "error", "invoice has both IGST and CGST/SGST")
    if abs(cgst - sgst) > TWO_PLACES:
        add("CGST_SGST_MISMATCH", "sgst", "warning", f"CGST {cgst} and SGST {sgst} should be equal")
    if inv.items:
        item_base = sum((i.taxable_amount for i in inv.items), Decimal("0"))
        item_tax = sum((i.taxable_amount * i.gst_rate / 100 for i in inv.items), Decimal("0"))
        if taxable is not None and abs(item_base - taxable) > tolerance:
            add("ARITHMETIC_ITEMS", "items", "error", f"line items sum to {item_base}, taxable amount is {taxable}")
        if abs(item_tax - tax) > tolerance:
            add("ARITHMETIC_TAX", "cgst", "error",
                f"tax implied by item rates is {item_tax.quantize(TWO_PLACES)}, invoice shows {tax}")

    # 4. date / period ------------------------------------------------------
    d = inv.val("invoice_date")   # an impossible date already failed schema parsing
    if d is not None:
        if today and d > today:
            add("DATE_FUTURE", "invoice_date", "warning", f"invoice date {d} is in the future")
        if open_period and not (open_period[0] <= d <= open_period[1]):
            add("PERIOD_CLOSED", "invoice_date", "error",
                f"{d} is outside the open period {open_period[0]} to {open_period[1]}")

    # 5. currency -------------------------------------------------------------
    cur = inv.val("currency")
    if cur and cur.upper() != "INR":
        add("CURRENCY", "currency", "warning", f"currency is {cur}; the ledger is INR")

    # 6. duplicates -------------------------------------------------------------
    if dup_index is not None:
        if file_sha and dup_index.has_file(file_sha):
            add("DUPLICATE_FILE", "file", "error", "this exact file was already uploaded")
        if dup_index.has_exact(inv):
            add("DUPLICATE_INVOICE", "invoice_number", "error",
                "same vendor, invoice number, amount and date already exists")
        elif dup_index.same_number_other_details(inv):
            add("DUPLICATE_NUMBER", "invoice_number", "warning",
                "same vendor and invoice number exist with a different amount or date")
    return r
