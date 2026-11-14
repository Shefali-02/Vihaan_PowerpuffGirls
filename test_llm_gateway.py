import pytest

from munshi_ai import (MOCK_BADGE, LlmGateway, LlmRequest, LlmValidationError, PruneClient,
                       PruneMock, build_gateway)
from munshi_ai.llm_gateway import BackendTimeout, BackendUnavailable

SCHEMA = {"type": "object", "required": ["vendor", "taxable_amount"],
          "properties": {"vendor": {"type": "string"}, "taxable_amount": {"type": "number"}}}


def req(**kw):
    base = dict(workspace_id="ws1", actor_id="u1", agent="docintel", purpose="extract invoice",
                prompt_id="docintel.invoice_extract", prompt_version="v1",
                messages=[{"role": "user", "content": "Invoice from ABC Technologies"}],
                idempotency_key="k1", response_schema=SCHEMA)
    base.update(kw)
    return LlmRequest(**base)


def gw(backend=None, **kw):
    return LlmGateway(backend or PruneMock(), sleep=lambda s: None, **kw)


def test_mock_golden_path_shows_badge_and_records_run():
    g = gw()
    r = g.complete(req())
    assert r.status == "ok" and r.output["vendor"] == "ABC Technologies"
    assert r.prune_run_id == "MOCK-001" and r.mock and r.badge == MOCK_BADGE == "MOCK LLM"
    assert g.status() == {"mode": "mock", "badge": "MOCK LLM"}
    run = g.runs.runs[0]
    assert run["prompt_id"] == "docintel.invoice_extract" and run["prompt_version"] == "v1"
    assert run["prune_run_id"] == "MOCK-001" and run["mock"] and run["input_hash"] and run["output_hash"]


def test_redaction_before_backend_and_aadhaar_never_sent():
    backend = PruneMock()
    text = "PAN ABCDE1234F, Aadhaar 1234 5678 9012, ph 9876543210, a/c 123456789012345, GSTIN 27AAPFU0939F1ZV"
    r = gw(backend).complete(req(messages=[{"role": "user", "content": text}]))
    sent = backend.calls[0]["messages"][0]["content"]
    for secret in ("ABCDE1234F", "1234 5678 9012", "9876543210", "123456789012345"):
        assert secret not in sent
    assert "27AAPFU0939F1ZV" in sent  # GSTIN is needed for extraction
    assert {x["kind"] for x in r.redactions} == {"aadhaar", "phone", "pan", "bank_account"}
    # even when explicitly allowed, Aadhaar is still masked; PAN passes only for pii class
    backend2 = PruneMock()
    gw(backend2).complete(req(data_class="pii", allow_fields=frozenset({"pan", "aadhaar"}),
                              messages=[{"role": "user", "content": "ABCDE1234F 1234 5678 9012"}]))
    sent2 = backend2.calls[0]["messages"][0]["content"]
    assert "ABCDE1234F" in sent2 and "1234 5678 9012" not in sent2


def test_request_validation():
    g = gw()
    with pytest.raises(LlmValidationError):
        g.complete(req(prompt_version=""))
    with pytest.raises(LlmValidationError):
        g.complete(req(messages=[]))
    with pytest.raises(LlmValidationError):
        g.complete(req(temperature=0.7))          # docintel must be deterministic
    with pytest.raises(LlmValidationError):
        g.complete(req(data_class="secret"))


class Flaky:
    is_mock = False

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def complete(self, payload):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return {"output": item, "prune_run_id": f"R{self.calls}", "model": "m", "usage": {"in": 5, "out": 7, "cost": 0.01}}


def test_retries_transient_errors_then_succeeds_without_mock_badge():
    f = Flaky([BackendTimeout("t"), BackendUnavailable("u"), '{"vendor": "X", "taxable_amount": 5}'])
    g = gw(f)
    r = g.complete(req())
    assert r.status == "ok" and f.calls == 3 and r.attempts == 3
    assert r.badge is None and g.status()["badge"] is None and r.usage["cost"] == 0.01


def test_prune_down_falls_back_to_manual_review_not_a_provider():
    r = gw(Flaky([BackendUnavailable("down")] * 5)).complete(req())
    assert r.status == "manual_review" and r.output is None
    assert "BackendUnavailable" in r.manual_review_reason


def test_one_repair_attempt_then_manual_review():
    ok = gw(Flaky(["not json", '{"vendor": "X", "taxable_amount": 1}'])).complete(req())
    assert ok.status == "ok" and ok.output["vendor"] == "X"
    bad = gw(Flaky(["not json", '{"vendor": 5}'])).complete(req(idempotency_key="k2"))
    assert bad.status == "manual_review" and "after repair" in bad.manual_review_reason


def test_idempotency_key_returns_cached_result():
    f = Flaky(['{"vendor": "X", "taxable_amount": 1}'])
    g = gw(f)
    a, b = g.complete(req()), g.complete(req())
    assert a.output == b.output and f.calls == 1


def test_prune_client_maps_openai_style_response_and_errors():
    seen = {}

    def ok_post(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body)
        return 200, {"id": "run_42", "model": "m1", "choices": [{"message": {"content": '{"vendor":"V","taxable_amount":9}'}}],
                     "usage": {"prompt_tokens": 11, "completion_tokens": 4, "cost": 0.002}}

    client = PruneClient("https://prune.example/", "SECRET", http_post=ok_post)
    r = gw(client).complete(req())
    assert r.status == "ok" and r.prune_run_id == "run_42" and r.usage == {"in": 11, "out": 4, "cost": 0.002}
    assert seen["url"] == "https://prune.example/v1/chat/completions" and "response_format" in seen["body"]
    assert "SECRET" not in repr(client) and r.badge is None

    r2 = gw(PruneClient("https://p", "k", http_post=lambda *a: (503, {}))).complete(req(idempotency_key="k3"))
    assert r2.status == "manual_review"
    r3 = gw(PruneClient("https://p", "k", http_post=lambda *a: (400, {}))).complete(req(idempotency_key="k4"))
    assert r3.status == "manual_review" and "BackendError" in r3.manual_review_reason


def test_factory_uses_mock_without_credentials(monkeypatch):
    for v in ("PRUNE_BASE_URL", "PRUNE_API_KEY", "PRUNE_MODE"):
        monkeypatch.delenv(v, raising=False)
    assert build_gateway().is_mock
    monkeypatch.setenv("PRUNE_BASE_URL", "https://p")
    monkeypatch.setenv("PRUNE_API_KEY", "k")
    assert not build_gateway().is_mock
    monkeypatch.setenv("PRUNE_MODE", "mock")
    assert build_gateway().is_mock
