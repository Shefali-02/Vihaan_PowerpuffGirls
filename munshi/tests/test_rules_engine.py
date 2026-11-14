"""Rules engine: deterministic, balanced GST journals in integer paise."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from modules.ledger.money import format_inr, half_up_div, rupees_to_paise, split_tax, tax_on
from modules.rules.engine import build_journal
from modules.rules.gstin import make_gstin
from modules.rules.models import DraftJournal, InvoiceFacts, InvoiceLineFacts, Rejection, TaxContext

ACME = make_gstin("07", "AAACA1234C")
CTX = TaxContext(workspace_gstin=ACME, workspace_state="07")
DELHI_VENDOR = make_gstin("07", "AAFCS4321K")
KA_VENDOR = make_gstin("29", "AABCI5678L")
MH_CUSTOMER = make_gstin("27", "AADCG9753P")
GOLDEN = Path(__file__).resolve().parent.parent / "packages" / "rules" / "golden"
D = date(2026, 10, 5)


def facts(doc_type="purchase_invoice", gstin=DELHI_VENDOR, lines=None, **kw) -> InvoiceFacts:
    lines = lines or [InvoiceLineFacts(description="x", taxable_paise=1_000_000, gst_rate_bp=1800)]
    return InvoiceFacts(doc_type=doc_type, invoice_no="T-1", invoice_date=D, counterparty_name="Party",
                        counterparty_gstin=gstin, lines=lines, **kw)


def as_rows(j: DraftJournal) -> dict:
    return {(ln.account_code, ln.tax_tag): (ln.debit_paise, ln.credit_paise) for ln in j.lines}


def test_intra_state_18_percent_rs_10000():
    j = build_journal(facts(category="office_supplies"), CTX)
    assert isinstance(j, DraftJournal) and j.balanced and j.supply_type == "INTRA"
    rows = as_rows(j)
    assert rows[("5200", "INWARD_TAXABLE")] == (1_000_000, 0)      # Dr expense 10,000.00
    assert rows[("1310", "INPUT_CGST")] == (90_000, 0)              # Dr Input CGST 900.00
    assert rows[("1320", "INPUT_SGST")] == (90_000, 0)              # Dr Input SGST 900.00
    assert rows[("2100", None)] == (0, 1_180_000)                   # Cr Payables 11,800.00
    assert format_inr(1_180_000) == "₹11,800.00"
    assert not j.needs_review


def test_inter_state_uses_igst():
    j = build_journal(facts(gstin=KA_VENDOR), CTX)
    rows = as_rows(j)
    assert j.supply_type == "INTER"
    assert rows[("1330", "INPUT_IGST")] == (180_000, 0)
    assert ("1310", "INPUT_CGST") not in rows and ("1320", "INPUT_SGST") not in rows
    assert rows[("2100", None)] == (0, 1_180_000)


def test_unregistered_vendor_gets_no_itc_and_needs_review():
    j = build_journal(facts(gstin=None), CTX)
    rows = as_rows(j)
    assert j.balanced and j.needs_review
    assert rows[("5100", "INWARD_TAXABLE")] == (1_000_000, 0)
    assert rows[("5100", "ITC_INELIGIBLE")] == (180_000, 0)          # tax becomes cost
    assert not any(tag and tag.startswith("INPUT_") for _, tag in rows)
    assert any("Unregistered vendor" in r for r in j.review_reasons)


def test_odd_paise_cgst_floor_sgst_remainder():
    j = build_journal(facts(lines=[InvoiceLineFacts(taxable_paise=1003, gst_rate_bp=1800)]), CTX)
    rows = as_rows(j)
    assert tax_on(1003, 1800) == 181                                  # 180.54 -> 181 (half-up)
    assert rows[("1310", "INPUT_CGST")] == (90, 0)
    assert rows[("1320", "INPUT_SGST")] == (91, 0)
    assert j.balanced


def test_bad_gstin_is_rejected():
    bad = DELHI_VENDOR[:14] + ("0" if DELHI_VENDOR[14] != "0" else "1")
    r = build_journal(facts(gstin=bad), CTX)
    assert isinstance(r, Rejection)
    assert r.reasons[0]["code"] == "INVALID_GSTIN"


def test_sale_intra_and_inter():
    intra = build_journal(facts(doc_type="sale_invoice", gstin=make_gstin("07", "AAKFM1357N"), category="services"),
                          CTX)
    rows = as_rows(intra)
    assert rows[("1200", None)] == (1_180_000, 0)
    assert rows[("4200", "OUTWARD_TAXABLE")] == (0, 1_000_000)
    assert rows[("2310", "OUTPUT_CGST")] == (0, 90_000) and rows[("2320", "OUTPUT_SGST")] == (0, 90_000)
    inter = build_journal(facts(doc_type="sale_invoice", gstin=MH_CUSTOMER), CTX)
    rows = as_rows(inter)
    assert inter.supply_type == "INTER" and rows[("2330", "OUTPUT_IGST")] == (0, 180_000)
    assert rows[("4100", "OUTWARD_TAXABLE")] == (0, 1_000_000)


def test_blocked_credit_category_adds_tax_to_cost():
    j = build_journal(facts(category="food_beverages"), CTX)
    rows = as_rows(j)
    assert rows[("5700", "ITC_INELIGIBLE")] == (180_000, 0)
    assert any("Blocked credit" in h for h in j.hints)


def test_invalid_slab_and_total_mismatch_rejected():
    r = build_journal(facts(lines=[InvoiceLineFacts(taxable_paise=1000, gst_rate_bp=1700)]), CTX)
    assert isinstance(r, Rejection) and r.reasons[0]["code"] == "INVALID_RATE"
    r = build_journal(facts(declared_total_paise=999), CTX)
    assert isinstance(r, Rejection) and r.reasons[0]["code"] == "TOTAL_MISMATCH"


def test_rate_from_hsn_table_when_missing():
    j = build_journal(facts(lines=[InvoiceLineFacts(hsn_sac="0902", taxable_paise=200_000)]), CTX)
    assert j.tax_paise == 10_000  # tea @5%


def test_disclaimer_always_present():
    j = build_journal(facts(), CTX)
    assert any("pending CA validation" in h for h in j.hints)


def test_money_helpers():
    assert half_up_div(5, 10) == 1 and half_up_div(4, 10) == 0 and half_up_div(-5, 10) == -1
    assert split_tax(181) == (90, 91)
    assert rupees_to_paise("1,18,000.505") == 11_800_051
    assert format_inr(12_345_678_900) == "₹12,34,56,789.00"


@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.json")), ids=lambda p: p.stem)
def test_golden_journals(path):
    g = json.loads(path.read_text())
    ctx = TaxContext(g["workspace"]["gstin"], g["workspace"]["state"])
    j = build_journal(InvoiceFacts.model_validate(g["facts"]), ctx)
    assert isinstance(j, DraftJournal), getattr(j, "reasons", None)
    got = [{"account_code": ln.account_code, "debit_paise": ln.debit_paise, "credit_paise": ln.credit_paise,
            "tax_tag": ln.tax_tag} for ln in j.lines]
    assert got == g["expected"]["lines"]
    assert j.supply_type == g["expected"]["supply_type"]
    assert j.needs_review == g["expected"]["needs_review"]


@settings(max_examples=300, deadline=None)
@given(
    doc_type=st.sampled_from(["purchase_invoice", "sale_invoice"]),
    gstin=st.sampled_from([DELHI_VENDOR, KA_VENDOR, MH_CUSTOMER, None]),
    category=st.sampled_from([None, "office_supplies", "food_beverages", "services", "goods", "rent"]),
    lines=st.lists(st.tuples(st.integers(1, 10**10), st.sampled_from([0, 500, 1200, 1800, 2800])),
                   min_size=1, max_size=8),
)
def test_every_built_journal_balances(doc_type, gstin, category, lines):
    f = InvoiceFacts(doc_type=doc_type, invoice_no="H", invoice_date=D, counterparty_gstin=gstin, category=category,
                     lines=[InvoiceLineFacts(taxable_paise=a, gst_rate_bp=r) for a, r in lines])
    j = build_journal(f, CTX)
    assert isinstance(j, DraftJournal)
    assert j.total_debit == j.total_credit == j.total_paise
    assert all((ln.debit_paise > 0) != (ln.credit_paise > 0) for ln in j.lines)
    assert j.total_paise == sum(a + tax_on(a, r) for a, r in lines)
