"""GSTIN/PAN validation (generated with the same checksum function), arithmetic, redaction."""
from __future__ import annotations

import string

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from modules.ai.redaction import redact
from modules.docintel.schemas import InvoiceExtraction
from modules.docintel.validators import gstin_errors, is_valid_gstin, is_valid_pan, validate_extraction
from modules.rules.gstin import make_gstin

ALNUM = string.digits + string.ascii_uppercase
pans = st.builds(lambda a, d, z: a + d + z,
                 st.text(string.ascii_uppercase, min_size=5, max_size=5),
                 st.text(string.digits, min_size=4, max_size=4),
                 st.text(string.ascii_uppercase, min_size=1, max_size=1))
states = st.integers(1, 38).map(lambda n: f"{n:02d}")
entity = st.sampled_from(list("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


@settings(max_examples=300)
@given(states, pans, entity)
def test_generated_gstins_are_valid(state, pan, ent):
    assert is_valid_gstin(make_gstin(state, pan, ent))


@settings(max_examples=500)
@given(states, pans, entity, st.integers(0, 14), st.sampled_from(list(ALNUM)))
def test_flipping_any_character_invalidates(state, pan, ent, pos, ch):
    g = make_gstin(state, pan, ent)
    assume(g[pos] != ch)
    assert not is_valid_gstin(g[:pos] + ch + g[pos + 1:])


def test_known_bad_gstins():
    assert gstin_errors("07AAACA1234C1Z") == ["GSTIN must be 15 characters"]
    assert gstin_errors("99AAACA1234C1ZI")  # state out of range
    good = make_gstin("07", "AAACA1234C")
    assert gstin_errors(good[:13] + "X" + good[14:])  # 14th must be Z
    assert is_valid_pan("AAACA1234C") and not is_valid_pan("AAAC1234CA")


def _ex(**kw):
    base = {"invoice_no": "1", "invoice_date": "2026-10-05", "seller_gstin": make_gstin("07", "AAFCS4321K"),
            "buyer_gstin": make_gstin("07", "AAACA1234C"),
            "lines": [{"description": "x", "taxable_value": "10000.00", "gst_rate_pct": "18"}],
            "total": "11800.00", "confidence": {}}
    base.update(kw)
    return InvoiceExtraction.model_validate(base)


def test_arithmetic_within_one_paisa_per_line():
    ws = make_gstin("07", "AAACA1234C")
    assert validate_extraction(_ex(total="11800.01"), ws, lambda d: True) == []
    issues = validate_extraction(_ex(total="11800.05"), ws, lambda d: True)
    assert [i["code"] for i in issues] == ["ARITHMETIC_MISMATCH"]


def test_period_and_ownership_checks():
    ws = make_gstin("07", "AAACA1234C")
    codes = [i["code"] for i in validate_extraction(_ex(buyer_gstin=make_gstin("07", "AAKFM1357N")), ws, lambda d: False)]
    assert "NOT_OUR_INVOICE" in codes and "PERIOD_NOT_OPEN" in codes


def test_redaction_never_sends_aadhaar():
    text = "Aadhaar 2345 6789 0123, PAN ABCDE1234F, Ph 9876543210, A/c No: 123456789012, GSTIN 07ABCDE1234F1Z5"
    out, counts = redact(text)
    assert "2345 6789 0123" not in out and "[AADHAAR]" in out
    assert "9876543210" not in out and "123456789012" not in out
    assert "PAN [PAN]" in out and "07ABCDE1234F1Z5" in out  # standalone PAN masked, GSTIN kept
