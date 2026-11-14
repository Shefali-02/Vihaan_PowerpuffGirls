"""GSTIN / PAN format and checksum (pure). Used by the rules engine and docintel validators.

GSTIN: 2-digit state (01-38) + PAN (10) + entity code [1-9A-Z] + 'Z' + mod-36 check char.
Checksum: weights alternate 1,2 from the left; each product p contributes p//36 + p%36.
"""
from __future__ import annotations

import re

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_GSTIN_SHAPE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        p = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += p // 36 + p % 36
    return _CHARS[(36 - total % 36) % 36]


def is_valid_pan(pan: str) -> bool:
    return bool(PAN_RE.match(pan or ""))


def gstin_errors(gstin: str | None) -> list[str]:
    g = (gstin or "").strip().upper()
    if len(g) != 15:
        return ["GSTIN must be 15 characters"]
    if not _GSTIN_SHAPE.match(g):
        errs = []
        if not g[:2].isdigit():
            errs.append("GSTIN state code must be 2 digits")
        if not is_valid_pan(g[2:12]):
            errs.append("GSTIN characters 3-12 must be a valid PAN")
        if g[13] != "Z":
            errs.append("GSTIN 14th character must be 'Z'")
        return errs or ["GSTIN has invalid characters"]
    if not 1 <= int(g[:2]) <= 38:
        return ["GSTIN state code must be between 01 and 38"]
    if gstin_check_char(g[:14]) != g[14]:
        return ["GSTIN checksum does not match"]
    return []


def is_valid_gstin(gstin: str | None) -> bool:
    return not gstin_errors(gstin)


def make_gstin(state_code: str, pan: str, entity: str = "1") -> str:
    """Build a checksum-valid GSTIN (seed data and tests)."""
    first14 = f"{state_code}{pan}{entity}Z"
    return first14 + gstin_check_char(first14)


def state_of(gstin: str) -> str:
    return gstin[:2]
