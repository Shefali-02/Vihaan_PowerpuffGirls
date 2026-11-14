"""
PruneMock: canned responses for development and offline demos.

Anything produced here is NOT real AI output. LlmGateway stamps every response
from this backend with mock=True, which makes the UI show the MOCK LLM badge.
The response shape below is illustrative, not a confirmed Prune API response.
"""
from __future__ import annotations

import copy
import itertools
from typing import Any, Optional

# Figures match the blueprint's worked example (s7.2): Rs 10,000 + 18% GST, intra-state.
DEFAULT_FIXTURES: dict[str, Any] = {
    "docintel.invoice_extract": {
        "vendor": "ABC Technologies",
        "vendor_gstin": "27AAPFU0939F1ZV",
        "invoice_number": "INV001",
        "invoice_date": "2026-11-03",
        "taxable_amount": 10000,
        "gst_rate": 18,
        "cgst": 900,
        "sgst": 900,
        "igst": 0,
        "total": 11800,
        "confidence": 0.93,
    },
    "categoriser.account": {"account": "Software expense", "tax_code": "PUR-GST-STD", "confidence": 0.91},
    "narrative.variance": {"commentary": "[MOCK] Software spend is on budget for the month.", "citations": []},
}
FALLBACK_OUTPUT = {"note": "mock response (no fixture for this prompt_id)"}


class PruneMock:
    is_mock = True

    def __init__(self, fixtures: Optional[dict[str, Any]] = None) -> None:
        self.fixtures = {**DEFAULT_FIXTURES, **(fixtures or {})}
        self._counter = itertools.count(1)
        self.calls: list[dict] = []   # handy for tests: exactly what the backend received

    def complete(self, payload: dict) -> dict:
        self.calls.append(copy.deepcopy(payload))
        prompt_id = payload.get("metadata", {}).get("prompt_id", "")
        return {
            "output": copy.deepcopy(self.fixtures.get(prompt_id, FALLBACK_OUTPUT)),
            "prune_run_id": f"MOCK-{next(self._counter):03d}",
            "model": "mock-model",
            "usage": {"in": 0, "out": 0, "cost": 0.0},
        }
