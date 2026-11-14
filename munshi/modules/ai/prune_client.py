"""Prune gateway client.

ASSUMED CONTRACT (unverified - replace in P3b when Prune docs/key exist; touch only this file):
  POST {PRUNE_BASE_URL}/v1/chat/completions
  Authorization: Bearer {PRUNE_API_KEY}
  body: {model, temperature, messages:[{role,content}], response_format:{type:"json_schema", json_schema:{name, schema, strict}}}
  reply: {choices:[{message:{content:"<json>"}}], model}

Behaviour: timeout, 2 retries with backoff on 5xx/timeouts, circuit breaker (3 consecutive failures -> open 60 s),
schema validation with exactly one repair attempt. No direct-provider fallback, ever.
"""
from __future__ import annotations

import json
import threading
import time

import httpx

from core.config import get_settings

_CB_LOCK = threading.Lock()
_CB = {"failures": 0, "open_until": 0.0}
CB_THRESHOLD, CB_COOLDOWN_S, RETRIES = 3, 60.0, 2


class CircuitOpen(RuntimeError):
    pass


class PruneClient:
    mode = "PRUNE"

    def __init__(self):
        s = get_settings()
        if not s.PRUNE_API_KEY:
            raise RuntimeError("PRUNE_API_KEY is not set; use LLM_MODE=mock")
        self.base = s.PRUNE_BASE_URL.rstrip("/")
        self.key = s.PRUNE_API_KEY
        self.model = s.PRUNE_MODEL
        self.timeout = s.PRUNE_TIMEOUT_S

    # -- transport -------------------------------------------------------------------
    def _post(self, messages: list[dict], schema: dict) -> tuple[str, str]:
        with _CB_LOCK:
            if time.monotonic() < _CB["open_until"]:
                raise CircuitOpen("Prune circuit breaker is open")
        body = {"model": self.model, "temperature": 0, "messages": messages,
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "extraction", "schema": schema, "strict": True}}}
        last: Exception | None = None
        for attempt in range(RETRIES + 1):
            try:
                r = httpx.post(f"{self.base}/v1/chat/completions", json=body, timeout=self.timeout,
                               headers={"Authorization": f"Bearer {self.key}"})
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                data = r.json()
                with _CB_LOCK:
                    _CB["failures"] = 0
                return data["choices"][0]["message"]["content"], data.get("model", self.model)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as e:
                last = e
                retriable = not isinstance(e, httpx.HTTPStatusError) or e.response.status_code >= 500
                if not retriable or attempt == RETRIES:
                    break
                time.sleep(0.5 * (2 ** attempt))
        with _CB_LOCK:
            _CB["failures"] += 1
            if _CB["failures"] >= CB_THRESHOLD:
                _CB["open_until"] = time.monotonic() + CB_COOLDOWN_S
        raise RuntimeError(f"Prune request failed: {last}")

    # -- gateway protocol ----------------------------------------------------------
    def complete(self, req):
        from modules.ai.gateway import LlmResponse

        t0 = time.monotonic()
        messages = [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}]
        text, model = self._post(messages, req.json_schema)
        out, errs = _parse(text, req.validate)
        repaired = False
        if errs:  # exactly one repair attempt
            repaired = True
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "Your JSON was invalid: " + "; ".join(errs)
                          + ". Return corrected JSON only, matching the schema."}]
            text, model = self._post(messages, req.json_schema)
            out, errs = _parse(text, req.validate)
        ms = int((time.monotonic() - t0) * 1000)
        if errs:
            return LlmResponse(ok=False, llm_mode=self.mode, model=model, raw_text=text, error="; ".join(errs),
                               status="INVALID_SCHEMA", repaired=repaired, latency_ms=ms)
        return LlmResponse(ok=True, llm_mode=self.mode, model=model, output=out, raw_text=text,
                           repaired=repaired, latency_ms=ms)


def _parse(text: str, validate) -> tuple[dict | None, list[str]]:
    try:
        out = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"not JSON: {e}"]
    if not isinstance(out, dict):
        return None, ["top-level JSON must be an object"]
    return out, (validate(out) if validate else [])
