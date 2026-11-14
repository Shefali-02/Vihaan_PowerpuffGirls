"""
PruneClient — LlmBackend adapter for the new LlmGateway protocol.

Implements the LlmBackend protocol expected by LlmGateway in llm_gateway.py:
    backend.complete(payload) -> {"output", "prune_run_id", "model", "usage"}
    backend.is_mock -> False

The Prune API key and base URL come from environment variables (see env.example):
    PRUNE_BASE_URL   = https://api.withprune.com/v1
    PRUNE_API_KEY    = prune_...
    PRUNE_MODEL      = default  (optional)
    PRUNE_TIMEOUT_S  = 30       (optional)
"""
from __future__ import annotations

import json
import os
import threading
import time

import httpx

_CB_LOCK = threading.Lock()
_CB: dict = {"failures": 0, "open_until": 0.0}
CB_THRESHOLD, CB_COOLDOWN_S, RETRIES = 3, 60.0, 2


class CircuitOpen(RuntimeError):
    pass


class PruneClient:
    is_mock: bool = False

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "default",
        timeout: float = 30.0,
    ) -> None:
        self.base = (base_url or os.environ.get("PRUNE_BASE_URL", "https://api.withprune.com/v1")).rstrip("/")
        self.key = api_key or os.environ.get("PRUNE_API_KEY", "")
        self.model = model or os.environ.get("PRUNE_MODEL", "default")
        self.timeout = float(os.environ.get("PRUNE_TIMEOUT_S", timeout))
        if not self.key:
            raise RuntimeError("PRUNE_API_KEY is not set; use PruneMock instead")

    @classmethod
    def from_env(cls) -> "PruneClient":
        return cls()

    # -- LlmBackend protocol -----------------------------------------------
    def complete(self, payload: dict) -> dict:
        """
        payload keys used here:
          messages        list[{"role", "content"}]
          max_tokens      int
          temperature     float
          response_schema dict | None  (used as json_schema for structured output)
          metadata        dict (logged but not sent to Prune)
        """
        messages = payload["messages"]
        schema = payload.get("response_schema")

        body: dict = {
            "model": self.model,
            "temperature": payload.get("temperature", 0),
            "messages": messages,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "extraction", "schema": schema, "strict": True},
            }

        text, model = self._post(body)

        # Parse JSON output
        try:
            output = json.loads(text)
        except json.JSONDecodeError as exc:
            # Return raw text so the gateway can attempt a repair
            output = text

        return {
            "output": output,
            "prune_run_id": None,  # Prune may add this in a response header or field
            "model": model,
            "usage": {"in": 0, "out": 0, "cost": 0.0},
        }

    # -- transport ---------------------------------------------------------
    def _post(self, body: dict) -> tuple[str, str]:
        with _CB_LOCK:
            if time.monotonic() < _CB["open_until"]:
                raise CircuitOpen("Prune circuit breaker is open — wait and retry")

        last: Exception | None = None
        for attempt in range(RETRIES + 1):
            try:
                r = httpx.post(
                    f"{self.base}/chat/completions",
                    json=body,
                    timeout=self.timeout,
                    headers={"Authorization": f"Bearer {self.key}"},
                )
                if r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                data = r.json()
                with _CB_LOCK:
                    _CB["failures"] = 0
                return data["choices"][0]["message"]["content"], data.get("model", self.model)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last = exc
                retriable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code >= 500
                if not retriable or attempt == RETRIES:
                    break
                time.sleep(0.5 * (2 ** attempt))

        with _CB_LOCK:
            _CB["failures"] += 1
            if _CB["failures"] >= CB_THRESHOLD:
                _CB["open_until"] = time.monotonic() + CB_COOLDOWN_S

        from .llm_gateway import BackendUnavailable
        raise BackendUnavailable(f"Prune request failed after {RETRIES + 1} attempts: {last}")
