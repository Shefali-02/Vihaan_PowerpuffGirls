"""MOCK NSWS adapter: designed, not built. No real calls are made."""
from __future__ import annotations


class MockNswsAdapter:
    mode = "MOCK"

    def list_registrations(self, pan: str) -> dict:
        raise NotImplementedError("designed, not built")
