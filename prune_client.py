"""
PruneClient: real backend for the Prune LLM gateway.

UNVERIFIED: no public Prune documentation was found (Blueprint s2, s6). This
assumes an OpenAI-style chat-completions contract. When the real docs arrive,
only these things should need to change (all marked "ASSUMED"):
  - CHAT_PATH, auth header, request body, and _parse() response mapping.
Nothing outside this file knows the wire format.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Callable, Optional

from .llm_gateway import BackendError, BackendTimeout, BackendUnavailable

HttpPost = Callable[[str, dict, dict, float], tuple[int, dict]]


def _urllib_post(url: str, headers: dict, body: dict, timeout: float) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}
    except (socket.timeout, TimeoutError):
        raise BackendTimeout("Prune request timed out")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise BackendTimeout("Prune request timed out")
        raise BackendUnavailable(f"cannot reach Prune: {e.reason}")


class PruneClient:
    is_mock = False
    CHAT_PATH = "/v1/chat/completions"          # ASSUMED

    def __init__(
        self,
        base_url: str,
        api_key: str,
        default_model: str = "default",           # ASSUMED: real model list unknown
        timeout_s: float = 30.0,
        http_post: Optional[HttpPost] = None,      # injectable for tests
    ) -> None:
        if not base_url or not api_key:
            raise ValueError("PruneClient needs base_url and api_key")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.default_model = default_model
        self.timeout_s = timeout_s
        self._post = http_post or _urllib_post

    @classmethod
    def from_env(cls) -> "PruneClient":
        return cls(os.environ["PRUNE_BASE_URL"], os.environ["PRUNE_API_KEY"],
                   default_model=os.environ.get("PRUNE_MODEL", "default"))

    def __repr__(self) -> str:                      # never leak the key into logs
        return f"PruneClient(base_url={self.base_url!r}, api_key=***)"

    def complete(self, payload: dict) -> dict:
        body = {                                    # ASSUMED request shape
            "model": payload.get("model") or self.default_model,
            "messages": payload["messages"],
            "max_tokens": payload["max_tokens"],
            "temperature": payload["temperature"],
            "metadata": payload.get("metadata", {}),
        }
        if payload.get("response_schema"):
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "output", "schema": payload["response_schema"]}}
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self._api_key}",          # ASSUMED auth scheme
                   "Idempotency-Key": payload.get("metadata", {}).get("idempotency_key", "")}
        status, data = self._post(self.base_url + self.CHAT_PATH, headers, body, self.timeout_s)

        if status in (408, 504):
            raise BackendTimeout(f"Prune returned {status}")
        if status == 429 or status >= 500:
            raise BackendUnavailable(f"Prune returned {status}")
        if status >= 400:
            raise BackendError(f"Prune rejected the request ({status})")
        return self._parse(data)

    @staticmethod
    def _parse(data: dict) -> dict:                 # ASSUMED response shape
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise BackendError("unexpected Prune response shape")
        u = data.get("usage") or {}
        return {
            "output": content,
            "prune_run_id": data.get("id") or data.get("run_id"),
            "model": data.get("model"),
            "usage": {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0),
                      "cost": u.get("cost", 0.0)},
        }
