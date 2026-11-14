"""MOCK ITD adapter: designed, not built. No real calls are made."""
from __future__ import annotations


class MockItdAdapter:
    mode = "MOCK"

    def get_26as(self, pan: str, assessment_year: str) -> dict:
        raise NotImplementedError("designed, not built")

    def prepare_tds_return(self, tan: str, quarter: str, deductions: list[dict]) -> dict:
        raise NotImplementedError("designed, not built")
