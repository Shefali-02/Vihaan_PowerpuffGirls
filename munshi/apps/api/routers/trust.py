from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import DB, CurrentUser, require
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.reports import AnchorRunOut, TrustStatusOut
from modules.trust import service as trust

router = APIRouter(prefix="/v1", tags=["trust"], responses=ERROR_RESPONSES)


@router.get("/trust/status", response_model=TrustStatusOut)
def status(p: CurrentUser, db: DB):
    return trust.status(db, p.workspace_id)


@router.post("/admin/anchor/run", response_model=AnchorRunOut, dependencies=[require("ACCOUNTANT", "CA")],
             summary="Batch unanchored audit leaves into a Merkle tree and anchor the root")
def anchor_run(p: CurrentUser, db: DB):
    return {"batches": trust.run_anchor(db, trigger="manual", workspace_id=p.workspace_id)}
