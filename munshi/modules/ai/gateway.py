"""THE single entry point for LLM calls. No provider SDK is imported anywhere in the codebase.

Flow: redaction -> prompt render (data delimited) -> Prune or mock -> schema validation -> ai_runs row.
Failures never fall back to a direct provider: callers route to MANUAL_ENTRY_REQUIRED.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session

from core.config import get_settings
from core.hashing import sha256_hex
from modules.ai import prompts, redaction, runs

Validator = Callable[[dict], list[str]]


@dataclass
class LlmRequest:
    prompt_id: str
    system: str
    user: str
    json_schema: dict
    input_hash: str
    validate: Validator | None = None
    temperature: int = 0


@dataclass
class LlmResponse:
    ok: bool
    llm_mode: str
    model: str
    output: dict | None = None
    raw_text: str = ""
    error: str | None = None
    status: str = "OK"  # OK | ERROR | INVALID_SCHEMA
    repaired: bool = False
    latency_ms: int = 0
    redactions: dict = field(default_factory=dict)
    run_id: str | None = None


class LlmGateway(Protocol):
    mode: str

    def complete(self, req: LlmRequest) -> LlmResponse: ...


def get_gateway() -> LlmGateway:
    mode = get_settings().LLM_MODE.lower()
    if mode == "prune":
        from modules.ai.prune_client import PruneClient

        return PruneClient()
    from modules.ai.prune_mock import PruneMock

    return PruneMock()


def current_mode() -> str:
    return "PRUNE" if get_settings().LLM_MODE.lower() == "prune" else "MOCK"


def run_structured(s: Session, workspace_id: str, prompt_id: str, document_text: str,
                   validate: Validator | None = None) -> LlmResponse:
    prompt = prompts.get(prompt_id)
    redacted, counts = redaction.redact(document_text)
    user = prompts.render(prompt, redacted)
    req = LlmRequest(prompt_id=prompt.id, system=prompt.system, user=user, json_schema=prompt.json_schema,
                     input_hash=sha256_hex(user.encode()), validate=validate)
    gw = get_gateway()
    t0 = time.monotonic()
    try:
        resp = gw.complete(req)
    except Exception as e:  # network, circuit open, etc.
        resp = LlmResponse(ok=False, llm_mode=gw.mode, model=getattr(gw, "model", "?"), error=str(e), status="ERROR")
    if resp.ok and validate is not None:
        errs = validate(resp.output or {})
        if errs:
            resp.ok, resp.status, resp.error = False, "INVALID_SCHEMA", "; ".join(errs)
    resp.latency_ms = resp.latency_ms or int((time.monotonic() - t0) * 1000)
    resp.redactions = counts
    resp.run_id = runs.record(s, workspace_id, req, resp)
    return resp
