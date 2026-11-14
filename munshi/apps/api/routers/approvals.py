from __future__ import annotations

from fastapi import APIRouter, Query

from apps.api.deps import DB, CurrentUser
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.workflow import ApprovalCreate, ApprovalDecision, ApprovalOut, ApprovalPage, ChangesRequest
from modules.workflow import service as workflow

router = APIRouter(prefix="/v1/approvals", tags=["approvals"], responses=ERROR_RESPONSES)


@router.post("", response_model=ApprovalOut, status_code=201)
def request_approval(body: ApprovalCreate, p: CurrentUser, db: DB):
    return workflow.request_approval(db, p, body.object_type, body.object_id, body.comment)


@router.get("", response_model=ApprovalPage, summary="List approvals with version hash, staleness and diff")
def list_approvals(p: CurrentUser, db: DB, state: str | None = None, cursor: str | None = None,
                   limit: int = Query(50, ge=1, le=200)):
    return workflow.list_approvals(db, p.workspace_id, state, cursor, limit)


@router.post("/{approval_id}/approve", response_model=ApprovalOut,
             summary="Approve (CA for high-risk; never the requester). Period close locks + anchors.")
def approve(approval_id: str, p: CurrentUser, db: DB, body: ApprovalDecision | None = None):
    return workflow.decide(db, p, approval_id, body.note if body else None)


@router.post("/{approval_id}/request-changes", response_model=ApprovalOut)
def request_changes(approval_id: str, body: ChangesRequest, p: CurrentUser, db: DB):
    return workflow.request_changes(db, p, approval_id, body.note)
