"""Money = integer paise. The ONE half-up rounding helper lives here. No floats."""
from __future__ import annotations


def half_up_div(numerator: int, denominator: int) -> int:
    """Integer division rounding half away from zero."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((2 * -numerator + denominator) // (2 * denominator))


def tax_on(taxable_paise: int, rate_bp: int) -> int:
    """Tax in paise for a taxable value at a rate in basis points (1800 = 18%)."""
    return half_up_div(taxable_paise * rate_bp, 10_000)


def split_tax(tax_paise: int) -> tuple[int, int]:
    """Intra-state split: CGST = floor(tax/2), SGST = remainder (gets the odd paisa)."""
    cgst = tax_paise // 2
    return cgst, tax_paise - cgst


def rupees_to_paise(text: str) -> int:
    """Parse '11,800.50' / '11800' / '₹ 1,18,000.5' exactly (no float)."""
    t = text.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
    neg = t.startswith("-")
    t = t.lstrip("-+").strip()
    if "." in t:
        whole, frac = t.split(".", 1)
        frac = (frac + "00")[:3]
        paise = int(whole or "0") * 100 + int(frac[:2])
        if int(frac[2]) >= 5:
            paise += 1
    else:
        paise = int(t) * 100
    return -paise if neg else paise


def _group_indian(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def format_inr(paise: int, symbol: bool = True) -> str:
    """Lakh/crore grouping: 1234567800 -> '₹1,23,45,678.00'."""
    neg = paise < 0
    paise = abs(paise)
    out = f"{_group_indian(paise // 100)}.{paise % 100:02d}"
    out = ("₹" if symbol else "") + out
    return "-" + out if neg else out
