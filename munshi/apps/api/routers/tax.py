from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import DB, CurrentUser
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.reports import GstSummaryOut
from modules.ledger import service as ledger
from modules.tax import service as tax

router = APIRouter(prefix="/v1/tax", tags=["tax"], responses=ERROR_RESPONSES)


@router.get("/gst/summary", response_model=GstSummaryOut, summary="GST summary (MOCK, prepared not filed)")
def gst_summary(p: CurrentUser, db: DB, period: str | None = None):
    """`period` is a period id or name (e.g. FY2026-27); defaults to the current period."""
    pid = None
    if period:
        match = [x for x in ledger.list_periods(db, p.workspace_id) if period in (x["id"], x["name"])]
        pid = match[0]["id"] if match else period
    pid = pid or ledger.current_period(db, p.workspace_id)["id"]
    return tax.summary(db, p.workspace_id, pid)
