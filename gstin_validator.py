"""
GSTIN validation: length, state code, structure and the real mod-36 checksum.

A valid result means "well-formed with a correct check character". It does NOT
mean the GSTIN is registered or active. Verifying that needs a GSP / GST portal
lookup, which Munshi does not have yet (Blueprint s2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# 2 digit state | 5 letters + 4 digits + 1 letter (PAN) | entity no. 1-9/A-Z | 'Z' | check char
_FORMAT = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

# GST state / UT codes. Verify against the current GSTN list before production.
STATE_NAMES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman & Diu (legacy)", "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
    "28": "Andhra Pradesh (legacy)", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar Islands",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory",
    "99": "Centre Jurisdiction",
}


def compute_check_char(first14: str) -> str:
    """GSTIN checksum: weights alternate 1,2,1,2...; each product p contributes
    p // 36 + p % 36; the check char is (36 - sum % 36) % 36 mapped to 0-9A-Z."""
    total = 0
    for i, ch in enumerate(first14):
        p = _CHARSET.index(ch) * (2 if i % 2 else 1)
        total += p // 36 + p % 36
    return _CHARSET[(36 - total % 36) % 36]


@dataclass
class GstinResult:
    valid: bool
    normalised: str
    errors: list[str] = field(default_factory=list)   # machine codes
    state_code: Optional[str] = None
    state_name: Optional[str] = None
    pan: Optional[str] = None
    expected_check_char: Optional[str] = None


def normalise_gstin(raw: str) -> str:
    return re.sub(r"\s+", "", raw or "").upper()


def validate_gstin(raw: str) -> GstinResult:
    g = normalise_gstin(raw)
    res = GstinResult(valid=False, normalised=g)

    if len(g) != 15:
        res.errors.append("LENGTH")           # nothing else is meaningful
        return res

    state = g[:2]
    if state in STATE_NAMES:
        res.state_code, res.state_name = state, STATE_NAMES[state]
    else:
        res.errors.append("STATE_CODE")

    if not _FORMAT.match(g):
        res.errors.append("FORMAT")
        return res

    res.pan = g[2:12]
    res.expected_check_char = compute_check_char(g[:14])
    if g[14] != res.expected_check_char:
        res.errors.append("CHECKSUM")

    res.valid = not res.errors
    return res
