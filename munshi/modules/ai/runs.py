from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from modules.ai.models import AiRun

if TYPE_CHECKING:
    from modules.ai.gateway import LlmRequest, LlmResponse


def record(s: Session, workspace_id: str, req: "LlmRequest", resp: "LlmResponse") -> str:
    run = AiRun(workspace_id=workspace_id, prompt_id=req.prompt_id, llm_mode=resp.llm_mode, model=resp.model,
                input_hash=req.input_hash, status=resp.status if not resp.ok else "OK", output=resp.output,
                error=resp.error, repaired=resp.repaired, latency_ms=resp.latency_ms, redactions=resp.redactions)
    s.add(run)
    s.flush()
    return run.id
