from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ApprovalCreate(BaseModel):
    object_type: Literal["journal", "period_close", "investor_pack"]
    object_id: str
    comment: str | None = None


class ApprovalDecision(BaseModel):
    note: str | None = None


class ChangesRequest(BaseModel):
    note: str


class ApprovalOut(BaseModel):
    id: str
    object_type: str
    object_id: str
    state: str
    risk: str
    version_hash: str
    requested_by: str
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    anchor_batch: dict | None
    created_at: str | None
    snapshot: dict
    current_version_hash: str | None = None
    stale: bool | None = None
    diff: list[dict] | None = None


class ApprovalPage(BaseModel):
    items: list[ApprovalOut]
    next_cursor: str | None
