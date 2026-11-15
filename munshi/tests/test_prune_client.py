"""Prune client (real Gemini-proxy contract): repair once, then fail closed."""
from __future__ import annotations

import json
import httpx
import pytest
from modules.ai import prune_client
from modules.docintel.schemas import schema_errors
from tests.conftest import upload

GOOD = {"invoice_no": "1", "invoice_date": "2026-10-05", "seller_gstin": None, "buyer_gstin": None,
        "lines": [{"description": "x", "taxable_value": "100.00"}], "total": "118.00", "confidence": {}}

def _gemini(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture
def prune_env(monkeypatch):
    from core.config import get_settings
    monkeypatch.setenv("LLM_MODE", "prune")
    monkeypatch.setenv("PRUNE_API_KEY", "test-key")
    monkeypatch.setenv("PRUNE_BASE_URL", "https://prune.test/v1")
    get_settings.cache_clear()
    prune_client._CB.update(failures=0, open_until=0.0)
    yield
    get_settings.cache_clear()


def fake(replies, seen):
    def _post(url, json=None, headers=None, timeout=None):
        seen.append({"url": url, "body": json, "headers": headers})
        r = replies.pop(0)
        req = httpx.Request("POST", url)
        if isinstance(r, int):
            return httpx.Response(r, request=req)
        return httpx.Response(200, request=req, json=_gemini(r))
    return _post


def _req():
    from modules.ai.gateway import LlmRequest
    return LlmRequest(prompt_id="docintel.invoice_extract@1", system="s", user="u", json_schema={},
                      input_hash="h", validate=schema_errors)


def test_contract_and_single_repair(prune_env, monkeypatch):
    seen = []
    monkeypatch.setattr(httpx, "post", fake([json.dumps({"invoice_no": 1}), json.dumps(GOOD)], seen))
    resp = prune_client.PruneClient().complete(_req())
    assert resp.ok and resp.repaired and resp.llm_mode == "PRUNE"
    assert seen[0]["url"] == "https://prune.test/v1/proxy/gemini/generateContent"
    assert seen[0]["headers"]["X-Prune-Key"] == "test-key"
    assert "response_format" not in seen[0]["body"]
    assert "invalid" in seen[1]["body"]["messages"][-1]["content"]


def test_still_invalid_after_repair_is_rejected(prune_env, monkeypatch):
    monkeypatch.setattr(httpx, "post", fake(["not json", "still not json"], []))
    resp = prune_client.PruneClient().complete(_req())
    assert not resp.ok and resp.status == "INVALID_SCHEMA"


def test_outage_routes_to_manual_entry_without_fallback(prune_env, monkeypatch, client, acc):
    monkeypatch.setattr(prune_client.time, "sleep", lambda s: None)
    monkeypatch.setattr(httpx, "post", fake([503] * 20, []))
    doc = upload(client, acc, "01_purchase_intra_18.txt")
    assert doc["status"] == "MANUAL_ENTRY_REQUIRED" and doc["proposal"]["llm_mode"] == "PRUNE"
