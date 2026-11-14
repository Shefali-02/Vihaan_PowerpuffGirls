from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile

from apps.api.deps import DB, CurrentUser
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.documents import DocumentOut, ProposalPage
from modules.docintel import service as docintel

router = APIRouter(prefix="/v1", tags=["documents"], responses=ERROR_RESPONSES)


@router.post("/documents", response_model=DocumentOut, status_code=201,
             summary="Upload an invoice; AI extraction via gateway -> validators -> rules engine -> proposal")
async def upload_document(p: CurrentUser, db: DB, file: UploadFile = File(...)):
    data = await file.read()
    return docintel.upload(db, p, file.filename or "upload", file.content_type or "", data)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, p: CurrentUser, db: DB):
    return docintel.get_document(db, p.workspace_id, doc_id)


@router.get("/proposals", response_model=ProposalPage)
def list_proposals(p: CurrentUser, db: DB, status: str | None = None, cursor: str | None = None,
                   limit: int = Query(50, ge=1, le=200)):
    return docintel.list_proposals(db, p.workspace_id, status, cursor, limit)
