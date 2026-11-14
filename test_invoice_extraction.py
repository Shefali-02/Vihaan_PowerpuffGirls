from datetime import date
from decimal import Decimal

import pytest

from munshi_ai import InvoiceExtractor, LlmGateway, PruneMock
from munshi_ai.gstin_validator import compute_check_char, validate_gstin
from munshi_ai.invoice_extractor import CLASSIFY_PROMPT_ID, EXTRACT_PROMPT_ID, detect_file_type
from munshi_ai.invoice_schema import DocumentType, ExtractedInvoice
from munshi_ai.invoice_validator import DuplicateIndex, validate_invoice

# Widely circulated example GSTINs. Checksum-valid; NOT verified as registered. Replace with a
# CA-supplied test set before relying on them.
KNOWN_VALID = ["27AAPFU0939F1ZV", "07AAGFF2194N1Z1", "29AAGCB7383J1Z4", "27AAACR5055K1Z7"]
SYNTHETIC_VALID = "29ABCDE1234F1ZW"          # checksum computed by us; not a real registration


def s(v, c=0.97):
    return {"value": v, "confidence": c}


def good_fields(**over):
    f = {"vendor_name": s("ABC Technologies"), "vendor_gstin": s(SYNTHETIC_VALID),
         "invoice_number": s("INV001"), "invoice_date": s("2026-11-10"),
         "items": [{"description": "Software services", "taxable_amount": 10000, "gst_rate": 18}],
         "taxable_amount": s(10000), "cgst": s(900), "sgst": s(900), "igst": s(0),
         "total_amount": s(11800), "currency": s("INR")}
    f.update(over)
    return f


def inv(**over) -> ExtractedInvoice:
    return ExtractedInvoice.model_validate(good_fields(**over))


def extractor(extract=None, cls=None, **kw):
    fx = {CLASSIFY_PROMPT_ID: cls or {"document_type": "purchase_invoice", "confidence": 0.97},
          EXTRACT_PROMPT_ID: extract if extract is not None else good_fields()}
    return InvoiceExtractor(LlmGateway(PruneMock(fx), sleep=lambda x: None), **kw)


def run(ex, body=b"Invoice INV001 ABC Technologies total 11800", name="inv.txt"):
    return ex.process(name, body, workspace_id="ws", actor_id="u", business_name="Acme")


# ---------------------------------------------------------------- GSTIN
def test_gstin_checksum_matches_known_examples():
    for g in KNOWN_VALID + [SYNTHETIC_VALID]:
        assert validate_gstin(g).valid, g
    assert compute_check_char("27AAPFU0939F1Z") == "V"


def test_gstin_failures():
    bad_check = KNOWN_VALID[0][:-1] + "W"
    assert validate_gstin(bad_check).errors == ["CHECKSUM"]
    assert validate_gstin("29ABCDE1234F1Z5").errors == ["CHECKSUM"]       # the brief's illustrative GSTIN
    assert validate_gstin("27AAPFU0939F1Z").errors == ["LENGTH"]
    assert "STATE_CODE" in validate_gstin("00AAPFU0939F1ZV").errors
    assert "FORMAT" in validate_gstin("27AAPF10939F1ZV").errors            # digit where a letter belongs
    assert "FORMAT" in validate_gstin("27AAPFU0939F1AV").errors            # 14th char must be Z
    r = validate_gstin(" 27aapfu0939f1zv ")                               # whitespace / case normalised
    assert r.valid and r.state_name == "Maharashtra" and r.pan == "AAPFU0939F"


# ---------------------------------------------------------- validations
def test_valid_invoice_passes_with_no_issues():
    rep = validate_invoice(inv(), today=date(2026, 11, 14), open_period=(date(2026, 4, 1), date(2027, 3, 31)))
    assert rep.passed and not rep.issues


def test_arithmetic_failures():
    assert "ARITHMETIC_TOTAL" in validate_invoice(inv(total_amount=s(12000))).codes()
    assert "ARITHMETIC_TAX" in validate_invoice(inv(cgst=s(500), sgst=s(500), total_amount=s(11000))).codes()
    assert "INTRA_INTER_MIX" in validate_invoice(inv(igst=s(1800), total_amount=s(13600))).codes()
    assert validate_invoice(inv(total_amount=s(11800.40))).passed            # round-off within Re 1


def test_bad_gstin_missing_fields_and_redaction():
    assert "GSTIN_INVALID" in validate_invoice(inv(vendor_gstin=s("29ABCDE1234F1Z5"))).codes()
    rep = validate_invoice(inv(invoice_number=s(None)))
    assert "REQUIRED" in rep.codes() and not rep.passed
    rep = validate_invoice(inv(invoice_number=s("[BANK_ACCOUNT_1]")))
    assert "REDACTED_FIELD" in rep.codes()
    assert "GSTIN_MISSING" in validate_invoice(inv(vendor_gstin=s(None))).codes()


def test_date_rules():
    rng = (date(2026, 4, 1), date(2027, 3, 31))
    assert "PERIOD_CLOSED" in validate_invoice(inv(invoice_date=s("2026-03-31")), open_period=rng).codes()
    assert "DATE_FUTURE" in validate_invoice(inv(), today=date(2026, 11, 1)).codes()
    with pytest.raises(ValueError):
        inv(invoice_date=s("31-02-2026"))                                    # impossible date fails schema
    assert inv(invoice_date=s("10-11-2026")).val("invoice_date") == date(2026, 11, 10)


def test_duplicates():
    idx = DuplicateIndex()
    first = inv()
    assert validate_invoice(first, dup_index=idx, file_sha="a").passed
    idx.add(first, "a")
    assert "DUPLICATE_INVOICE" in validate_invoice(inv(invoice_number=s("inv-001")), dup_index=idx).codes()
    assert "DUPLICATE_FILE" in validate_invoice(inv(invoice_number=s("INV002")), dup_index=idx, file_sha="a").codes()
    other = validate_invoice(inv(total_amount=s(11900), igst=s(100)), dup_index=idx)
    assert "DUPLICATE_NUMBER" in other.codes() and "DUPLICATE_INVOICE" not in other.codes()


def test_money_parsing_accepts_rupee_strings():
    assert inv(taxable_amount=s("₹10,000")).amount("taxable_amount") == Decimal("10000")


# ------------------------------------------------------------ end to end
def test_clean_invoice_is_ready_and_stored_with_mock_badge():
    ex = extractor()
    r = run(ex)
    assert r.route == "ready" and r.reasons == [] and r.document_type == DocumentType.purchase_invoice
    d = ex.store.items[r.extraction_id]
    assert d["extracted"]["total_amount"] == 11800 and d["extracted"]["invoice_date"] == "2026-11-10"
    assert d["fields"]["vendor_gstin"]["confidence"] == 0.97 and d["ai"]["badge"] == "MOCK LLM"
    assert len(r.prune_run_ids) == 2


def test_low_confidence_critical_field_goes_to_review_not_ready():
    r = run(extractor(good_fields(vendor_gstin=s(SYNTHETIC_VALID, 0.72))))
    assert r.route == "review" and r.low_confidence_fields == ["vendor_gstin"]
    assert any(x.startswith("LOW_CONFIDENCE: vendor_gstin") for x in r.reasons)


def test_validation_failure_goes_to_manual_entry_with_reasons():
    r = run(extractor(good_fields(total_amount=s(12000))))
    assert r.route == "manual_entry" and any("ARITHMETIC_TOTAL" in x for x in r.reasons)
    r = run(extractor(good_fields(vendor_gstin=s("29ABCDE1234F1Z5"))))
    assert r.route == "manual_entry" and any("GSTIN_INVALID" in x for x in r.reasons)


def test_duplicate_file_and_duplicate_invoice_are_blocked():
    ex = extractor()
    assert run(ex).route == "ready"
    assert "DUPLICATE_FILE" in run(ex).reasons[0]
    r = run(ex, body=b"different bytes, same invoice")
    assert r.route == "manual_entry" and any("DUPLICATE_INVOICE" in x for x in r.reasons)


def test_non_invoice_types_and_uncertain_type():
    assert run(extractor(cls={"document_type": "credit_note", "confidence": 0.95})).route == "unsupported"
    assert run(extractor(cls={"document_type": "bank_statement", "confidence": 0.99})).route == "unsupported"
    r = run(extractor(cls={"document_type": "purchase_invoice", "confidence": 0.5}))
    assert r.route == "manual_entry" and "TYPE_UNCERTAIN" in r.reasons[0]


def test_sales_invoice_supported():
    r = run(extractor(cls={"document_type": "sales_invoice", "confidence": 0.95}))
    assert r.route == "ready" and r.document_type == DocumentType.sales_invoice


def test_bad_model_output_goes_to_manual_entry():
    r = run(extractor(good_fields(taxable_amount=s("ten thousand"))))
    assert r.route == "manual_entry" and "BAD_EXTRACTION" in r.reasons[0]
    r = run(extractor(good_fields(invoice_date=s("31-02-2026"))))
    assert r.route == "manual_entry" and "BAD_EXTRACTION" in r.reasons[0]


def test_real_pdf_text_layer_is_read_and_scanned_pdf_is_flagged():
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 80), "TAX INVOICE ABC Technologies INV001 total 11800", fontsize=12)
    ex = extractor()
    r = run(ex, body=doc.tobytes(), name="a.pdf")
    assert r.file_type == "pdf" and r.route == "ready"
    blank = pymupdf.open()
    blank.new_page()
    r2 = run(ex, body=blank.tobytes(), name="scan.pdf")
    assert r2.route == "manual_entry" and "OCR is not enabled" in r2.reasons[0]


def test_file_type_detection():
    assert detect_file_type("x", b"%PDF-1.7") == "pdf"
    assert detect_file_type("x.png", b"\x89PNG\r\n\x1a\n...") == "image"
    assert detect_file_type("s.csv", b"a,b\n1,2") == "csv"
