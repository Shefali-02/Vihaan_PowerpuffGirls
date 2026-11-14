"""Builds sample_invoice.pdf and runs it through the pipeline on PruneMock to produce
sample_extracted_invoice.json. The PDF text is really read by PyMuPDF; the extraction
fields come from a mock fixture (NOT a real model reading), so the output carries the MOCK LLM badge."""
import json
import pathlib

import pymupdf

from . import InvoiceExtractor, LlmGateway, PruneMock
from .invoice_extractor import CLASSIFY_PROMPT_ID, EXTRACT_PROMPT_ID

HERE = pathlib.Path(__file__).parent
GSTIN = "29ABCDE1234F1ZW"   # synthetic: checksum-valid, not a registered GSTIN
BUYER = "27AAPFU0939F1ZV"   # widely circulated example GSTIN


def s(v, c):
    return {"value": v, "confidence": c}


FIXTURES = {
    CLASSIFY_PROMPT_ID: {"document_type": "purchase_invoice", "confidence": 0.97, "reason": "Tax invoice from a supplier"},
    EXTRACT_PROMPT_ID: {
        "vendor_name": s("ABC Technologies", 0.98), "vendor_gstin": s(GSTIN, 0.96),
        "buyer_name": s("Acme Pvt Ltd", 0.95), "buyer_gstin": s(BUYER, 0.94),
        "invoice_number": s("INV001", 0.95), "invoice_date": s("10-11-2026", 0.97),
        "items": [{"description": "Software services", "hsn_sac": "998314", "taxable_amount": 10000, "gst_rate": 18}],
        "taxable_amount": s(10000, 0.98), "cgst": s(900, 0.97), "sgst": s(900, 0.97), "igst": s(0, 0.9),
        "total_amount": s(11800, 0.98), "currency": s("INR", 0.99),
    },
}


def build_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    lines = ["TAX INVOICE", "ABC Technologies", f"GSTIN: {GSTIN}", "Invoice No: INV001   Date: 10-11-2026",
             "Bill to: Acme Pvt Ltd   GSTIN: " + BUYER, "Software services (SAC 998314)   Taxable value: 10,000.00",
             "CGST 9%: 900.00   SGST 9%: 900.00   IGST: 0.00", "Total: Rs 11,800.00"]
    for i, line in enumerate(lines):
        page.insert_text((50, 70 + 22 * i), line, fontsize=12)
    return doc.tobytes()


if __name__ == "__main__":
    pdf = build_pdf()
    (HERE / "sample_invoice.pdf").write_bytes(pdf)
    ex = InvoiceExtractor(LlmGateway(PruneMock(FIXTURES)))
    result = ex.process("sample_invoice.pdf", pdf, workspace_id="demo-ws", actor_id="demo-user",
                        business_name="Acme Pvt Ltd")
    (HERE / "sample_extracted_invoice.json").write_text(json.dumps(result.to_dict(), indent=2))
    print(result.route, result.reasons)
