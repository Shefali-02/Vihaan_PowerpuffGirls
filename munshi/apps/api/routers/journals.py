from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import DB, CurrentUser
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.ledger import InvoiceFacts, JournalOut, PeriodOut
from modules.ledger import service as ledger

router = APIRouter(prefix="/v1", tags=["ledger"], responses=ERROR_RESPONSES)


@router.post("/journals/draft", response_model=JournalOut, status_code=201,
             summary="Draft a journal from invoice facts (rules engine decides every line)")
def draft_journal(body: InvoiceFacts, p: CurrentUser, db: DB):
    return ledger.create_draft(db, p, body)


@router.post("/journals/{entry_id}/post", response_model=JournalOut,
             summary="Post a draft: re-runs the engine, checks balance and open period, writes audit event")
def post_journal(entry_id: str, p: CurrentUser, db: DB):
    return ledger.post(db, p, entry_id)


@router.get("/journals/{entry_id}", response_model=JournalOut)
def get_journal(entry_id: str, p: CurrentUser, db: DB):
    return ledger.get_entry(db, p.workspace_id, entry_id)


@router.get("/periods", response_model=list[PeriodOut])
def list_periods(p: CurrentUser, db: DB):
    return ledger.list_periods(db, p.workspace_id)
