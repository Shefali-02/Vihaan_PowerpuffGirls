"""MOCK AA adapter: designed, not built. No real calls are made."""
from __future__ import annotations


class MockAaAdapter:
    mode = "MOCK"

    def request_consent(self, customer_vua: str, fi_types: list[str], purpose: str) -> dict:
        raise NotImplementedError("designed, not built")

    def fetch_statements(self, consent_id: str) -> dict:
        raise NotImplementedError("designed, not built")
