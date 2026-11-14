from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from apps.api.deps import DB, CurrentUser
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.ledger import PnlOut
from apps.api.schemas.reports import PackOut, PackRequest, ProofOut
from modules.ledger import service as ledger
from modules.reporting import service as reporting
from modules.trust import service as trust

router = APIRouter(prefix="/v1/reports", tags=["reports"], responses=ERROR_RESPONSES)


@router.get("/pnl", response_model=PnlOut)
def pnl(p: CurrentUser, db: DB, period_id: str | None = None):
    pid = period_id or ledger.current_period(db, p.workspace_id)["id"]
    return ledger.profit_and_loss(db, p.workspace_id, pid)


@router.post("/pack", response_model=PackOut, status_code=201,
             summary="Publish the investor pack (409 PERIOD_CLOSE_NOT_APPROVED unless a CA approved the close)")
def publish_pack(body: PackRequest, p: CurrentUser, db: DB):
    return reporting.build_investor_pack(db, p, body.period_id)


@router.get("/{report_id}/proof", response_model=ProofOut)
def proof(report_id: str, p: CurrentUser, db: DB):
    return trust.proof_bundle(db, p.workspace_id, report_id)


@router.get("/{report_id}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def pdf(report_id: str, p: CurrentUser, db: DB):
    data, filename = trust.get_report_pdf(db, p.workspace_id, report_id)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
