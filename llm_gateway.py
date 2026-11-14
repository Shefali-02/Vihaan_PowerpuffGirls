"""
LlmGateway: the ONLY way any Munshi module reaches an LLM (Blueprint s6.1).

Every AI feature (invoice extraction, categorisation, commentary, ...) calls
LlmGateway.complete(). The gateway owns the safeguards once, so backends
(PruneClient, PruneMock) stay thin and swappable:

  1. validate the request        5. record prompt version, usage, cost
  2. redact sensitive data       6. handle API errors / timeouts (retry)
  3. enforce structured JSON     7. fall back to manual review (fail closed)
  4. record the Prune run id

There is deliberately NO direct-to-provider fallback. If Prune is down the
response has status="manual_review" and the caller queues for a human.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

log = logging.getLogger("munshi.llm")

MOCK_BADGE = "MOCK LLM"
DATA_CLASSES = {"public", "business", "pii"}
DETERMINISTIC_AGENTS = {"docintel", "categoriser", "reconciler"}  # temperature must be 0


# ----------------------------------------------------------------- errors
class LlmError(Exception):
    pass


class LlmValidationError(LlmError):
    """The caller built a bad request (a programming error, so we raise)."""


class BackendError(LlmError):
    retryable = False


class BackendTimeout(BackendError):
    retryable = True


class BackendUnavailable(BackendError):
    retryable = True


# ------------------------------------------------------------ data classes
@dataclass
class LlmRequest:
    workspace_id: str
    actor_id: str
    agent: str                      # 'docintel' | 'categoriser' | 'narrative' | ...
    purpose: str
    prompt_id: str                  # from the prompt registry, never ad-hoc
    prompt_version: str
    messages: list[dict[str, str]]  # [{"role": "user", "content": "..."}]
    idempotency_key: str
    data_class: str = "business"    # public | business | pii
    response_schema: Optional[dict] = None
    max_tokens: int = 1000
    temperature: float = 0.0
    # PAN / phone / bank numbers may be sent only if data_class == 'pii' AND listed here.
    # Aadhaar is NEVER sent, whatever is listed.
    allow_fields: frozenset = frozenset()


@dataclass
class LlmResponse:
    status: str                         # 'ok' | 'manual_review'
    output: Any = None
    prune_run_id: Optional[str] = None
    model: Optional[str] = None
    usage: dict = field(default_factory=lambda: {"in": 0, "out": 0, "cost": 0.0})
    latency_ms: int = 0
    redactions: list[dict] = field(default_factory=list)   # [{"kind": "pan", "count": 1}]
    mock: bool = False
    manual_review_reason: Optional[str] = None
    attempts: int = 1

    @property
    def badge(self) -> Optional[str]:
        """UI must render this next to any AI result when it is not None."""
        return MOCK_BADGE if self.mock else None

    def to_dict(self) -> dict:
        return {
            "status": self.status, "output": self.output, "prune_run_id": self.prune_run_id,
            "model": self.model, "usage": self.usage, "latency_ms": self.latency_ms,
            "redactions": self.redactions, "mock": self.mock, "badge": self.badge,
            "manual_review_reason": self.manual_review_reason,
        }


class LlmBackend(Protocol):
    """What PruneClient and PruneMock both implement."""
    is_mock: bool

    def complete(self, payload: dict) -> dict:
        """payload: messages, max_tokens, temperature, response_schema?, metadata.
        Returns: {"output", "prune_run_id", "model", "usage": {"in","out","cost"}}.
        Raises BackendTimeout / BackendUnavailable / BackendError."""


class InMemoryRunStore:
    """Stand-in for the ai_runs table. Swap for a DB-backed store with the same .record()."""

    def __init__(self) -> None:
        self.runs: list[dict] = []

    def record(self, run: dict) -> None:
        self.runs.append(run)


# --------------------------------------------------------------- redaction
# Order matters: Aadhaar first so a 12-digit number is never mistaken for an account.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("aadhaar", re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")),
    ("phone", re.compile(r"(?<!\d)(?:\+91[ -]?|0)?[6-9]\d{9}(?!\d)")),
    ("pan", re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Za-z0-9])")),
    ("bank_account", re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
]


def redact_text(text: str, data_class: str, allow: frozenset, counts: dict[str, int]) -> str:
    for kind, pattern in _PATTERNS:
        permitted = kind != "aadhaar" and data_class == "pii" and kind in allow
        if permitted:
            continue

        def _sub(_m: re.Match, kind: str = kind) -> str:
            counts[kind] = counts.get(kind, 0) + 1
            return f"[{kind.upper()}_{counts[kind]}]"

        text = pattern.sub(_sub, text)
    return text


# ------------------------------------------------------- schema validation
_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "integer": int, "number": (int, float), "null": type(None),
}


def check_schema(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Minimal JSON-Schema subset (type, required, properties, items, enum).
    Replace with the `jsonschema` package when you want the full spec."""
    errors: list[str] = []
    t = schema.get("type")
    if t:
        expected = _TYPES[t]
        ok = isinstance(value, expected) and not (t in ("integer", "number") and isinstance(value, bool))
        if not ok:
            return [f"{path}: expected {t}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum")
    if t == "object":
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errors.extend(check_schema(value[key], sub, f"{path}.{key}"))
    if t == "array" and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(check_schema(item, schema["items"], f"{path}[{i}]"))
    return errors


def _parse_json_output(raw: Any) -> Any:
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    return json.loads(s)


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


# ----------------------------------------------------------------- gateway
class LlmGateway:
    def __init__(
        self,
        backend: LlmBackend,
        run_store: Optional[InMemoryRunStore] = None,
        max_retries: int = 2,
        backoff_s: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.backend = backend
        self.runs = run_store or InMemoryRunStore()
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self._sleep = sleep
        self._cache: dict[str, LlmResponse] = {}
        if backend.is_mock:
            log.warning("*** %s MODE: AI results are canned fixtures, not real model output ***", MOCK_BADGE)

    # -- public ----------------------------------------------------------
    @property
    def is_mock(self) -> bool:
        return bool(self.backend.is_mock)

    def status(self) -> dict:
        """Serve this from GET /v1/ai/status so the UI can show the badge globally."""
        return {"mode": "mock" if self.is_mock else "prune", "badge": MOCK_BADGE if self.is_mock else None}

    def complete(self, request: LlmRequest) -> LlmResponse:
        self._validate(request)

        cached = self._cache.get(request.idempotency_key)
        if cached is not None:
            return copy.deepcopy(cached)

        start = time.monotonic()
        counts: dict[str, int] = {}
        messages = [
            {**m, "content": redact_text(m["content"], request.data_class, request.allow_fields, counts)}
            for m in request.messages
        ]
        redactions = [{"kind": k, "count": c} for k, c in counts.items()]
        input_hash = _sha(messages)

        def finish(resp: LlmResponse) -> LlmResponse:
            resp.mock = self.is_mock
            resp.redactions = redactions
            resp.latency_ms = int((time.monotonic() - start) * 1000)
            self._record(request, resp, input_hash)
            if resp.status == "ok":
                self._cache[request.idempotency_key] = copy.deepcopy(resp)
            return resp

        attempts = 0
        try:
            raw, n = self._call_with_retries(request, messages)
            attempts += n
            output, errors = self._structure(raw["output"], request.response_schema)

            if errors:  # one repair attempt, then human fallback
                repair = messages + [
                    {"role": "assistant", "content": json.dumps(raw["output"], default=str)},
                    {"role": "user", "content": "Your previous output was invalid: "
                     + "; ".join(errors[:5]) + ". Return only corrected JSON matching the schema."},
                ]
                raw, n = self._call_with_retries(request, repair)
                attempts += n
                output, errors = self._structure(raw["output"], request.response_schema)
                if errors:
                    return finish(LlmResponse(
                        status="manual_review", prune_run_id=raw.get("prune_run_id"), model=raw.get("model"),
                        manual_review_reason="invalid structured output after repair: " + "; ".join(errors[:3]),
                        attempts=attempts))
        except BackendError as e:
            return finish(LlmResponse(status="manual_review", attempts=attempts or 1,
                                      manual_review_reason=f"{type(e).__name__}: {e}"))

        usage = {"in": 0, "out": 0, "cost": 0.0, **(raw.get("usage") or {})}
        return finish(LlmResponse(status="ok", output=output, prune_run_id=raw.get("prune_run_id"),
                                  model=raw.get("model"), usage=usage, attempts=attempts))

    # -- internals -------------------------------------------------------
    @staticmethod
    def _validate(r: LlmRequest) -> None:
        for name in ("workspace_id", "actor_id", "agent", "purpose", "prompt_id",
                     "prompt_version", "idempotency_key"):
            if not getattr(r, name):
                raise LlmValidationError(f"{name} is required")
        if r.data_class not in DATA_CLASSES:
            raise LlmValidationError(f"data_class must be one of {sorted(DATA_CLASSES)}")
        if not r.messages or not all(
            isinstance(m, dict) and m.get("role") in ("system", "user", "assistant")
            and isinstance(m.get("content"), str) for m in r.messages
        ):
            raise LlmValidationError("messages must be a non-empty list of {role, content: str}")
        if not 1 <= r.max_tokens <= 8192:
            raise LlmValidationError("max_tokens must be between 1 and 8192")
        if r.agent in DETERMINISTIC_AGENTS and r.temperature != 0:
            raise LlmValidationError(f"agent '{r.agent}' requires temperature 0")

    def _call_with_retries(self, r: LlmRequest, messages: list[dict]) -> tuple[dict, int]:
        payload = {
            "messages": messages, "max_tokens": r.max_tokens, "temperature": r.temperature,
            "response_schema": r.response_schema,
            "metadata": {"workspace_id": r.workspace_id, "agent": r.agent, "purpose": r.purpose,
                         "prompt_id": r.prompt_id, "prompt_version": r.prompt_version,
                         "data_class": r.data_class, "idempotency_key": r.idempotency_key},
        }
        attempt = 0
        while True:
            attempt += 1
            try:
                return self.backend.complete(payload), attempt
            except BackendError as e:
                if not e.retryable or attempt > self.max_retries:
                    raise
                self._sleep(self.backoff_s * 2 ** (attempt - 1))

    @staticmethod
    def _structure(raw_output: Any, schema: Optional[dict]) -> tuple[Any, list[str]]:
        if schema is None:
            return raw_output, []
        try:
            parsed = _parse_json_output(raw_output)
        except (json.JSONDecodeError, TypeError) as e:
            return None, [f"not valid JSON ({e})"]
        return parsed, check_schema(parsed, schema)

    def _record(self, r: LlmRequest, resp: LlmResponse, input_hash: str) -> None:
        self.runs.record({
            "workspace_id": r.workspace_id, "actor_id": r.actor_id, "agent": r.agent,
            "prune_run_id": resp.prune_run_id, "prompt_id": r.prompt_id, "prompt_version": r.prompt_version,
            "input_hash": input_hash, "output_hash": _sha(resp.output) if resp.output is not None else None,
            "model": resp.model, "usage": resp.usage, "status": resp.status, "mock": resp.mock,
            "manual_review_reason": resp.manual_review_reason, "latency_ms": resp.latency_ms,
        })
