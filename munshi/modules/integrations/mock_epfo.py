"""MOCK EPFO adapter: designed, not built. No real calls are made."""
from __future__ import annotations


class MockEpfoAdapter:
    mode = "MOCK"

    def prepare_ecr(self, establishment_id: str, wage_month: str, members: list[dict]) -> dict:
        raise NotImplementedError("designed, not built")
