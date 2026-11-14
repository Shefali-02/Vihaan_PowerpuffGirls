"""MOCK MCA adapter: designed, not built. No real calls are made."""
from __future__ import annotations


class MockMcaAdapter:
    mode = "MOCK"

    def get_company_master(self, cin: str) -> dict:
        raise NotImplementedError("designed, not built")

    def prepare_aoc4(self, cin: str, financial_year: str, financials: dict) -> dict:
        raise NotImplementedError("designed, not built")
