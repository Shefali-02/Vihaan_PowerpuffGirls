"""GST summary from tax-tagged ledger lines (POSTED only).

Set-off order (simplified, cf. s.49/49A/49B; DEMO, pending CA validation):
  IGST credit -> IGST, then CGST, then SGST;  CGST credit -> CGST, then IGST;  SGST credit -> SGST, then IGST.
"""
from __future__ import annotations


def _cr(tags: dict, tag: str) -> int:
    t = tags.get(tag, {})
    return t.get("credit_paise", 0) - t.get("debit_paise", 0)


def _dr(tags: dict, tag: str) -> int:
    t = tags.get(tag, {})
    return t.get("debit_paise", 0) - t.get("credit_paise", 0)


def _use(credit: int, liab: dict, head: str) -> int:
    used = min(credit, liab[head])
    liab[head] -= used
    return credit - used


def compute(tags: dict) -> dict:
    out = {"cgst": _cr(tags, "OUTPUT_CGST"), "sgst": _cr(tags, "OUTPUT_SGST"), "igst": _cr(tags, "OUTPUT_IGST")}
    itc = {"cgst": _dr(tags, "INPUT_CGST"), "sgst": _dr(tags, "INPUT_SGST"), "igst": _dr(tags, "INPUT_IGST")}
    liab = dict(out)
    rem_igst = itc["igst"]
    for head in ("igst", "cgst", "sgst"):
        rem_igst = _use(rem_igst, liab, head)
    rem_cgst = itc["cgst"]
    for head in ("cgst", "igst"):
        rem_cgst = _use(rem_cgst, liab, head)
    rem_sgst = itc["sgst"]
    for head in ("sgst", "igst"):
        rem_sgst = _use(rem_sgst, liab, head)
    return {
        "outward_taxable_paise": _cr(tags, "OUTWARD_TAXABLE"),
        "inward_taxable_paise": _dr(tags, "INWARD_TAXABLE"),
        "output_cgst_paise": out["cgst"], "output_sgst_paise": out["sgst"], "output_igst_paise": out["igst"],
        "itc_cgst_paise": itc["cgst"], "itc_sgst_paise": itc["sgst"], "itc_igst_paise": itc["igst"],
        "itc_ineligible_paise": _dr(tags, "ITC_INELIGIBLE"),
        "net_payable_cgst_paise": liab["cgst"], "net_payable_sgst_paise": liab["sgst"],
        "net_payable_igst_paise": liab["igst"],
        "net_payable_paise": liab["cgst"] + liab["sgst"] + liab["igst"],
        "itc_carry_forward_paise": {"igst": rem_igst, "cgst": rem_cgst, "sgst": rem_sgst},
    }
