"""The ONLY JSON canonicalisation in the codebase (RFC 8785 / JCS).

Used by workflow (version hashes), trust (audit chain, leaves) and reporting (pack JSON).
Floats are rejected: money is integer paise everywhere.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import rfc8785


def _normalise(obj: Any) -> Any:
    if isinstance(obj, float):
        raise TypeError("floats are not allowed in canonical JSON (use integer paise / strings)")
    if isinstance(obj, dict):
        return {str(k): _normalise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalise(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.hex()
    return obj


def canonical_json(obj: Any) -> bytes:
    return rfc8785.dumps(_normalise(obj))
