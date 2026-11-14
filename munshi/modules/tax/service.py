from __future__ import annotations

from sqlalchemy.orm import Session

from modules.identity import service as identity
from modules.integrations import service as integrations
from modules.ledger import service as ledger
from modules.ledger.money import format_inr
from modules.tax import gst_summary

DISCLAIMER = "Demo computation pending CA validation; not legal/tax advice. Not filed with GSTN."


def summary(s: Session, ws: str, period_id: str, include_gstr3b: bool = True) -> dict:
    period = ledger.get_period(s, ws, period_id)
    data = gst_summary.compute(ledger.tax_tag_totals(s, ws, period_id))
    out = {"period": period, **data, "net_payable": format_inr(data["net_payable_paise"]), "mode": "MOCK",
           "disclaimer": DISCLAIMER}
    if include_gstr3b:
        w = identity.get_workspace(s, ws)
        out["gstr3b_preview"] = integrations.gst_port().prepare_gstr3b(w.gstin, period["name"], data)
    return out
