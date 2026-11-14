"""Redact personal identifiers before any text leaves for an LLM.

Aadhaar-like numbers are ALWAYS removed. GSTINs are kept (needed for extraction; they are public
business identifiers), but a PAN that stands alone (not inside a GSTIN) is masked.
"""
from __future__ import annotations

import re

_BANK = re.compile(r"(?i)(\b(?:a/?c|account)\s*(?:no\.?|number|#)?\s*[:\-]?\s*)(\d[\d\s-]{7,20}\d)")
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_AADHAAR = re.compile(r"(?<![\d])[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?![\d])")
_PAN_STANDALONE = re.compile(r"(?<![0-9A-Z])[A-Z]{5}[0-9]{4}[A-Z](?![0-9A-Z])")
_PHONE = re.compile(r"(?<![\d])(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?![\d])")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def redact(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}

    def sub(pattern, repl, s):
        new, n = pattern.subn(repl, s)
        if n:
            counts[repl if isinstance(repl, str) else "BANK_AC"] = n
        return new

    out = sub(_BANK, lambda m: m.group(1) + "[BANK_AC]", text)
    out = sub(_IFSC, "[IFSC]", out)
    out = sub(_AADHAAR, "[AADHAAR]", out)
    out = sub(_PAN_STANDALONE, "[PAN]", out)
    out = sub(_PHONE, "[PHONE]", out)
    out = sub(_EMAIL, "[EMAIL]", out)
    return out, counts
