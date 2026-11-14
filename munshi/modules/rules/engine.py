"""Deterministic GST journal builder (pure: same facts + same tables -> same journal).

Stage order: validation -> tax determination -> posting -> policy -> compliance hints.
LLMs never write journals; they only supply InvoiceFacts that pass through here.
"""
from __future__ import annotations

from collections import OrderedDict

from modules.ledger.money import split_tax, tax_on
from modules.rules import loader
from modules.rules.gstin import gstin_errors, state_of
from modules.rules.models import DraftJournal, DraftLine, InvoiceFacts, Rejection, TaxContext

DISCLAIMER = "Demo rates pending CA validation; not legal/tax advice."


def _pct(bp: int) -> str:
    return f"{bp // 100}%" if bp % 100 == 0 else f"{bp // 100}.{bp % 100:02d}%"


def build_journal(facts: InvoiceFacts, ctx: TaxContext) -> DraftJournal | Rejection:
    explanation: list[dict] = []

    # ---- 1. validation -------------------------------------------------
    ruleset = loader.get_ruleset(facts.doc_type, facts.invoice_date)
    if ruleset is None:
        return Rejection([{"code": "NO_RULESET", "message": f"No ruleset for {facts.doc_type} on {facts.invoice_date}"}])
    rv = ruleset["ruleset_version"]
    reasons: list[dict] = []
    if gstin_errors(ctx.workspace_gstin):
        reasons.append({"code": "WORKSPACE_GSTIN_INVALID", "message": "; ".join(gstin_errors(ctx.workspace_gstin))})
    cp_gstin = (facts.counterparty_gstin or "").strip().upper() or None
    if cp_gstin and gstin_errors(cp_gstin):
        reasons.append({"code": "INVALID_GSTIN", "message": "; ".join(gstin_errors(cp_gstin))})
    if not facts.lines:
        reasons.append({"code": "NO_LINES", "message": "Invoice has no lines"})
    slabs = loader.get_slabs_bp(facts.invoice_date)
    for i, ln in enumerate(facts.lines, 1):
        if ln.taxable_paise <= 0:
            reasons.append({"code": "NON_POSITIVE_AMOUNT", "message": f"Line {i}: taxable value must be > 0"})
        rate = ln.gst_rate_bp if ln.gst_rate_bp is not None else loader.get_gst_rate(ln.hsn_sac, facts.invoice_date)
        if rate is None:
            reasons.append({"code": "UNKNOWN_RATE", "message": f"Line {i}: no GST rate given and HSN/SAC not in table"})
        elif rate not in slabs:
            reasons.append({"code": "INVALID_RATE", "message": f"Line {i}: {_pct(rate)} is not a valid GST slab"})
    if reasons:
        return Rejection(reasons, ruleset_version=rv)
    explanation.append({"stage": "validation", "result": "pass", "ruleset": rv})

    # ---- 2. tax determination -----------------------------------------
    is_purchase = facts.doc_type == "purchase_invoice"
    registered = cp_gstin is not None
    if is_purchase:
        supplier_state = state_of(cp_gstin) if registered else (facts.place_of_supply or ctx.workspace_state)
        intra = supplier_state == ctx.workspace_state
    else:
        pos = facts.place_of_supply or (state_of(cp_gstin) if registered else ctx.workspace_state)
        intra = pos == ctx.workspace_state
    supply_type = "INTRA" if intra else "INTER"
    blocked = loader.blocked_credits()
    review: list[str] = []
    hints: list[str] = []

    per_line = []
    for ln in facts.lines:
        table_rate = loader.get_gst_rate(ln.hsn_sac, facts.invoice_date)
        rate = ln.gst_rate_bp if ln.gst_rate_bp is not None else table_rate
        if table_rate is not None and rate != table_rate:
            review.append(f"Rate {_pct(rate)} differs from HSN/SAC table rate {_pct(table_rate)} for {ln.hsn_sac}")
        tax = tax_on(ln.taxable_paise, rate)
        category = ln.category or facts.category or ("general" if is_purchase else "goods")
        itc_ok = True
        if is_purchase and not registered:
            itc_ok = False
        if is_purchase and category in blocked:
            itc_ok = False
            hints.append(f"Blocked credit: {blocked[category]}")
        per_line.append({"line": ln, "rate": rate, "tax": tax, "category": category, "itc": itc_ok})
    total_taxable = sum(p["line"].taxable_paise for p in per_line)
    total_tax = sum(p["tax"] for p in per_line)
    total = total_taxable + total_tax
    explanation.append({"stage": "tax_determination", "supply_type": supply_type,
                        "taxable_paise": total_taxable, "tax_paise": total_tax,
                        "rule": "intra-state -> CGST+SGST (odd paisa to SGST); inter-state -> IGST"})

    if facts.declared_total_paise is not None:
        tolerance = len(facts.lines)  # 1 paisa per line
        if abs(facts.declared_total_paise - total) > tolerance:
            return Rejection([{"code": "TOTAL_MISMATCH",
                               "message": f"Declared total {facts.declared_total_paise} != computed {total} paise"}],
                             ruleset_version=rv)

    # ---- 3. posting ----------------------------------------------------
    acc = ruleset["accounts"]
    cat_acc = ruleset["category_accounts"]
    debits: "OrderedDict[tuple, int]" = OrderedDict()
    credits: "OrderedDict[tuple, int]" = OrderedDict()

    def add(bucket, code, tag, amt, memo=""):
        if amt:
            bucket[(code, tag, memo)] = bucket.get((code, tag, memo), 0) + amt

    if is_purchase:
        itc_tax = 0
        for p in per_line:
            code = cat_acc.get(p["category"], acc["default_expense"])
            add(debits, code, "INWARD_TAXABLE", p["line"].taxable_paise, "taxable value")
            if p["itc"]:
                itc_tax += p["tax"]
            else:
                add(debits, code, "ITC_INELIGIBLE", p["tax"], "GST not creditable")
        if intra:
            c, s = split_tax(itc_tax)
            add(debits, acc["input_cgst"], "INPUT_CGST", c)
            add(debits, acc["input_sgst"], "INPUT_SGST", s)
        else:
            add(debits, acc["input_igst"], "INPUT_IGST", itc_tax)
        add(credits, acc["payable"], None, total, f"payable to {facts.counterparty_name or 'vendor'}")
    else:
        for p in per_line:
            code = cat_acc.get(p["category"], acc["default_income"])
            add(credits, code, "OUTWARD_TAXABLE", p["line"].taxable_paise, "taxable value")
        if intra:
            c, s = split_tax(total_tax)
            add(credits, acc["output_cgst"], "OUTPUT_CGST", c)
            add(credits, acc["output_sgst"], "OUTPUT_SGST", s)
        else:
            add(credits, acc["output_igst"], "OUTPUT_IGST", total_tax)
        add(debits, acc["receivable"], None, total, f"receivable from {facts.counterparty_name or 'customer'}")

    lines = [DraftLine(k[0], v, 0, k[1], k[2]) for k, v in sorted(debits.items(), key=lambda kv: kv[0][0])]
    lines += [DraftLine(k[0], 0, v, k[1], k[2]) for k, v in sorted(credits.items(), key=lambda kv: kv[0][0])]
    explanation.append({"stage": "posting", "lines": len(lines)})

    # ---- 4. policy -----------------------------------------------------
    if is_purchase and not registered:
        review.append("Unregistered vendor: no input tax credit taken; review for reverse charge")
    explanation.append({"stage": "policy", "review_reasons": list(review)})

    # ---- 5. compliance hints -------------------------------------------
    if is_purchase and not registered:
        hints.append("Check whether reverse charge (RCM) applies to this supply")
    if not is_purchase and not registered:
        hints.append("B2C sale: reported in GSTR-1 B2C section")
    hints.append(DISCLAIMER)
    explanation.append({"stage": "compliance_hints", "hints": list(hints)})

    party = facts.counterparty_name or ("vendor" if is_purchase else "customer")
    narration = f"{'Purchase' if is_purchase else 'Sale'} invoice {facts.invoice_no} - {party}"
    return DraftJournal(
        doc_type=facts.doc_type, entry_date=facts.invoice_date, narration=narration, lines=lines,
        ruleset_id=ruleset["id"], ruleset_version=rv, supply_type=supply_type,
        total_paise=total, tax_paise=total_tax, needs_review=bool(review),
        review_reasons=review, hints=hints, explanation=explanation,
    )
