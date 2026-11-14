"""Regenerate seed/invoices/*.txt, EXPECTED.json and seed/fixtures/gstr2b.json (checksum-valid GSTINs)."""
from __future__ import annotations

import json
from pathlib import Path

from modules.rules.service import make_gstin
from seed.seed import WORKSPACE

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "seed" / "invoices"
ACME = make_gstin(WORKSPACE["state_code"], WORKSPACE["pan"])
SHARMA = make_gstin("07", "AAFCS4321K")
INFOTECH = make_gstin("29", "AABCI5678L")
CHAI = make_gstin("07", "AAGFC2468M")
MEHTA = make_gstin("07", "AAKFM1357N")
GUPTA = make_gstin("27", "AADCG9753P")
BAD = SHARMA[:14] + ("0" if SHARMA[14] != "0" else "1")  # wrong checksum


def inv(seller, seller_gstin, buyer, buyer_gstin, no, dt, pos, items, total, category=None, extra=""):
    lines = ["TAX INVOICE", f"Seller: {seller}"]
    if seller_gstin:
        lines.append(f"Seller GSTIN: {seller_gstin}")
    lines += ["Seller Phone: +91 98765 43210", f"Buyer: {buyer}"]
    if buyer_gstin:
        lines.append(f"Buyer GSTIN: {buyer_gstin}")
    lines += [f"Invoice No: {no}", f"Invoice Date: {dt}", f"Place of Supply: {pos}"]
    if category:
        lines.append(f"Category: {category}")
    lines.append("Items (No | Description | HSN/SAC | Taxable Value | GST Rate):")
    lines += [f"{i} | {d} | {h} | {a} | {r}%" for i, (d, h, a, r) in enumerate(items, 1)]
    lines += [f"Total: {total}", "Bank A/c No: 50100234567812  IFSC: HDFC0001234", extra]
    return "\n".join(lines).strip() + "\n"


FILES = {
    "01_purchase_intra_18.txt": (inv("Sharma Office Supplies Pvt Ltd", SHARMA, "Acme Pvt Ltd", ACME, "SOS/26-27/0142",
                                     "2026-10-05", "07", [("A4 paper, registers and stationery", "4820", "10,000.00", 18)],
                                     "11,800.00", "office_supplies"), "DRAFT_AI"),
    "02_purchase_inter_igst.txt": (inv("Infotech Solutions Pvt Ltd", INFOTECH, "Acme Pvt Ltd", ACME, "INF/2026/7781",
                                       "2026-10-12", "07", [("IT consulting - ERP setup", "998313", "25,000.00", 18)],
                                       "29,500.00", "professional_fees"), "DRAFT_AI"),
    "03_purchase_5pct.txt": (inv("Chai Point Traders", CHAI, "Acme Pvt Ltd", ACME, "CPT-0091", "2026-10-20", "07",
                                 [("Assam tea, 20 kg pantry stock", "0902", "2,000.00", 5)], "2,100.00", "general"),
                             "DRAFT_AI"),
    "04_bad_gstin.txt": (inv("Sharma Office Supplies Pvt Ltd", BAD, "Acme Pvt Ltd", ACME, "SOS/26-27/0150",
                             "2026-10-25", "07", [("Printer cartridges", "8443", "4,000.00", 18)], "4,720.00",
                             "office_supplies"), "NEEDS_REVIEW"),
    "05_duplicate_of_01.txt": (inv("Sharma Office Supplies Pvt Ltd", SHARMA, "Acme Pvt Ltd", ACME, "SOS/26-27/0142",
                                   "2026-10-05", "07", [("A4 paper, registers and stationery", "4820", "10,000.00", 18)],
                                   "11,800.00", "office_supplies", extra="(re-scanned copy)"), "DUPLICATE"),
    "06_arithmetic_mismatch.txt": (inv("Chai Point Traders", CHAI, "Acme Pvt Ltd", ACME, "CPT-0102", "2026-10-28", "07",
                                       [("Green tea, 5 kg", "0902", "1,500.00", 5)], "1,800.00", "general"),
                                   "NEEDS_REVIEW"),
    "07_sale_intra.txt": (inv("Acme Pvt Ltd", ACME, "Mehta Retail LLP", MEHTA, "ACME/S/2026/031", "2026-10-15", "07",
                              [("Implementation services", "998313", "50,000.00", 18, )], "59,000.00", "services"),
                          "DRAFT_AI"),
    "08_sale_inter.txt": (inv("Acme Pvt Ltd", ACME, "Gupta Exports Pvt Ltd", GUPTA, "ACME/S/2026/032", "2026-10-18",
                              "27", [("Laptops (refurbished)", "8471", "40,000.00", 18)], "47,200.00", "goods"),
                          "DRAFT_AI"),
    "09_unregistered_vendor.txt": (inv("Ramesh Carpentry Works", None, "Acme Pvt Ltd", ACME, "RC-17", "2026-10-30", "07",
                                       [("Office cabinet repair (labour)", "", "3,000.00", 0)], "3,000.00", "repairs"),
                                   "NEEDS_REVIEW"),
    "10_gateway_failure.txt": (inv("Sharma Office Supplies Pvt Ltd", SHARMA, "Acme Pvt Ltd", ACME, "SOS/26-27/0160",
                                   "2026-11-02", "07", [("Whiteboard markers", "9608", "800.00", 18)], "944.00",
                                   "office_supplies", extra="(fixture simulates an AI gateway outage)"),
                               "MANUAL_ENTRY_REQUIRED"),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    expected = {}
    for name, (text, status) in FILES.items():
        (OUT / name).write_text(text)
        expected[name] = status
    (OUT / "EXPECTED.json").write_text(json.dumps(expected, indent=2) + "\n")
    gstr2b = {"b2b": [
        {"supplier_gstin": SHARMA, "invoice_no": "SOS/26-27/0142", "date": "2026-10-05", "taxable_paise": 1000000,
         "cgst_paise": 90000, "sgst_paise": 90000, "igst_paise": 0, "itc_available": True},
        {"supplier_gstin": INFOTECH, "invoice_no": "INF/2026/7781", "date": "2026-10-12", "taxable_paise": 2500000,
         "cgst_paise": 0, "sgst_paise": 0, "igst_paise": 450000, "itc_available": True},
        {"supplier_gstin": CHAI, "invoice_no": "CPT-0091", "date": "2026-10-20", "taxable_paise": 200000,
         "cgst_paise": 5000, "sgst_paise": 5000, "igst_paise": 0, "itc_available": True},
    ]}
    (ROOT / "seed" / "fixtures" / "gstr2b.json").write_text(json.dumps(gstr2b, indent=2) + "\n")
    print("ACME", ACME, "BAD", BAD)
