from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from apps.api.deps import DB
from apps.api.schemas.reports import VerifyOut
from modules.trust import verify_service

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/verify", response_model=VerifyOut, summary="Verify a report by SHA-256 (no auth)")
def verify(db: DB, hash: str):
    return verify_service.verify_hash(db, hash)


@router.post("/verify/upload", response_model=VerifyOut, summary="Verify an uploaded PDF (no auth)")
async def verify_upload(db: DB, file: UploadFile = File(...)):
    return verify_service.verify_upload(db, await file.read())
