"""Deterministic investor-pack PDF: same pack JSON -> byte-identical PDF (reportlab invariant mode)."""
from __future__ import annotations

import io

from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from modules.ledger.money import format_inr

ASSURANCE = "Reviewed in Munshi workflow; not a statutory audit."
DISCLAIMER = ("Demo rates pending CA validation; not legal/tax advice. Sign-off is workflow evidence, "
              "not a statutory audit or certification.")


def _rs(paise: int) -> str:
    return "Rs " + format_inr(paise, symbol=False)


class _Writer:
    def __init__(self, c: canvas.Canvas):
        self.c, self.y = c, A4[1] - 60

    def line(self, text: str, size: int = 10, bold: bool = False, x: int = 50, gap: int = 14):
        if self.y < 90:
            self.c.showPage()
            self.y = A4[1] - 60
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.drawString(x, self.y, text)
        self.y -= gap

    def row(self, left: str, right: str, bold: bool = False):
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        self.c.drawString(60, self.y, left[:70])
        self.c.drawRightString(A4[0] - 60, self.y, right)
        self.y -= 14

    def gap(self, n: int = 8):
        self.y -= n


def build(pack: dict, verify_url: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, invariant=1, pageCompression=0)
    c.setTitle(f"Investor pack {pack['workspace']['name']} {pack['period']['name']}")
    c.setAuthor("Munshi")
    c.setCreator("Munshi reporting/pack_pdf v1")
    c.setSubject("Investor pack")
    mock = any(v != "LIVE" for v in pack["sources"].values())

    def watermark():
        if mock:
            c.saveState()
            c.setFillGray(0.88)
            c.setFont("Helvetica-Bold", 46)
            c.translate(A4[0] / 2, A4[1] / 2)
            c.rotate(35)
            c.drawCentredString(0, 0, "MOCK DATA SOURCES - DEMO")
            c.restoreState()

    watermark()
    w = _Writer(c)
    w.line(f"Investor Pack - {pack['workspace']['name']}", 18, True, gap=22)
    w.line(f"Period {pack['period']['name']} ({pack['period']['start_date']} to {pack['period']['end_date']})"
           f"   GSTIN {pack['workspace']['gstin']}", 10)
    w.gap()

    pnl = pack["pnl"]
    w.line("Profit and Loss", 13, True, gap=18)
    w.row("Income", "", True)
    for r in pnl["income"]:
        w.row(f"  {r['code']} {r['name']}", _rs(r["amount_paise"]))
    w.row("Total income", _rs(pnl["total_income_paise"]), True)
    w.row("Expenses", "", True)
    for r in pnl["expenses"]:
        w.row(f"  {r['code']} {r['name']}", _rs(r["amount_paise"]))
    w.row("Total expenses", _rs(pnl["total_expenses_paise"]), True)
    w.row("Net profit / (loss)", _rs(pnl["net_profit_paise"]), True)
    w.gap()

    g = pack["gst"]
    w.line("GST summary (prepared, not filed)", 13, True, gap=18)
    for label, key in [("Outward taxable value", "outward_taxable_paise"), ("Output CGST", "output_cgst_paise"),
                       ("Output SGST", "output_sgst_paise"), ("Output IGST", "output_igst_paise"),
                       ("Input tax credit CGST", "itc_cgst_paise"), ("Input tax credit SGST", "itc_sgst_paise"),
                       ("Input tax credit IGST", "itc_igst_paise"), ("GST not creditable", "itc_ineligible_paise"),
                       ("Net GST payable", "net_payable_paise")]:
        w.row(label, _rs(g[key]), key == "net_payable_paise")
    w.gap()

    w.line("Sign-offs", 13, True, gap=18)
    if not pack["signoffs"]:
        w.line("  none", 10)
    for so in pack["signoffs"]:
        w.line(f"  {so['name']} - {so['role']} - approved period close at {so['time']}", 10)
        w.line(f"  version hash {so['version_hash']}", 8)
    w.line(ASSURANCE, 10, True)
    w.gap()

    w.line("Integrity", 13, True, gap=18)
    pc = pack.get("period_close_anchor") or {}
    if pc:
        w.line(f"  Period-close batch #{pc.get('batch_seq')} root {pc.get('root')}", 8)
        w.line(f"  anchor {pc.get('anchor', {}).get('mode')} tx {pc.get('anchor', {}).get('tx_hash')}", 8)
    w.line("  The SHA-256 of this exact file is recorded in a hash-chained audit log and its Merkle root", 9)
    w.line(f"  is anchored. Upload this PDF at {verify_url} to check it. Any changed byte gives NO MATCH.", 9)
    renderPDF.draw(_qr(verify_url), c, A4[0] - 150, max(w.y - 100, 100))

    c.setFont("Helvetica", 7)
    src = ", ".join(f"{k}={v}" for k, v in sorted(pack["sources"].items()))
    c.drawString(50, 50, DISCLAIMER)
    c.drawString(50, 40, f"Data sources: {src}. Not integrated with or approved by any government body.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _qr(url: str):
    from modules.reporting.qr import drawing

    return drawing(url)
