"""Investor pack: requires an APPROVED period close; publishes a deterministic PDF and anchors its hash."""
from __future__ import annotations

from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import PeriodCloseNotApproved
from modules.ai import gateway
from modules.identity import service as identity
from modules.ledger import service as ledger
from modules.reporting import pack_pdf, qr
from modules.tax import service as tax
from modules.trust import service as trust
from modules.workflow import service as workflow

APPROVED_STATES = ("APPROVED", "LOCKED", "ANCHORED")


def build_pack_json(s: Session, ws: str, period_id: str) -> dict:
    w = identity.get_workspace(s, ws)
    period = ledger.get_period(s, ws, period_id)
    pnl = ledger.profit_and_loss(s, ws, period_id)
    gst = tax.summary(s, ws, period_id, include_gstr3b=False)
    approvals = workflow.list_approvals(s, ws, None, None, 100)["items"]
    pc = next((a for a in approvals if a["object_type"] == "period_close" and a["object_id"] == period_id
               and a["state"] in APPROVED_STATES), None)
    keep = ("outward_taxable_paise", "output_cgst_paise", "output_sgst_paise", "output_igst_paise",
            "itc_cgst_paise", "itc_sgst_paise", "itc_igst_paise", "itc_ineligible_paise", "net_payable_paise")
    return {
        "format": "munshi-investor-pack/1",
        "workspace": {"name": w.name, "gstin": w.gstin},
        "period": {k: period[k] for k in ("id", "name", "start_date", "end_date")},
        "pnl": {k: pnl[k] for k in ("income", "expenses", "total_income_paise", "total_expenses_paise",
                                    "net_profit_paise")},
        "gst": {k: gst[k] for k in keep},
        "signoffs": workflow.signoffs(s, ws, period_id),
        "period_close_anchor": pc["anchor_batch"] if pc else None,
        "sources": {"llm": gateway.current_mode(), "gst": "MOCK", "anchor": trust.anchor_mode(s)},
        "assurance": pack_pdf.ASSURANCE,
        "disclaimer": pack_pdf.DISCLAIMER,
    }


def build_investor_pack(s: Session, p, period_id: str) -> dict:
    identity.require_role(p, "ACCOUNTANT", "CA")
    ws = p.workspace_id
    state = workflow.period_close_state(s, ws, period_id)
    if state not in APPROVED_STATES:
        raise PeriodCloseNotApproved(f"Period close is {state or 'not requested'}; a CA must approve it first")
    pack = build_pack_json(s, ws, period_id)
    base = get_settings().PUBLIC_BASE_URL.rstrip("/")
    pdf = pack_pdf.build(pack, verify_url=f"{base}/verify")
    filename = f"investor-pack-{pack['period']['name']}.pdf"
    report = trust.register_report(s, ws, p.user_id, period_id, pack["period"]["name"], pdf, pack, filename)
    batches = trust.run_anchor(s, trigger="report_published", workspace_id=ws)
    qr_payload = f"/verify?hash={report['sha256']}"
    return {
        "report_id": report["id"], "sha256": report["sha256"], "filename": filename,
        "qr_payload": qr_payload, "qr_png_base64": qr.png_base64(base + qr_payload),
        "proof_url": f"/v1/reports/{report['id']}/proof", "pdf_url": f"/v1/reports/{report['id']}/pdf",
        "anchor": batches[0]["anchor"] if batches else None, "sources": pack["sources"],
    }
