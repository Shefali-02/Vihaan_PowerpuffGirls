from __future__ import annotations

from fastapi import APIRouter
from apps.api.deps import DB
from apps.api.schemas.reports import HealthOut
from core.config import get_settings
from core.db import ping
from modules.ai import gateway
from modules.trust import service as trust

router = APIRouter(tags=["health"])
VERSION = "0.1.0"


@router.get("/healthz", response_model=HealthOut)
def healthz(db: DB):
    return {"status": "ok", "db": ping(db), "llm_mode": gateway.current_mode(),
            "anchor_mode": trust.anchor_mode(db), "anchor_mode_configured": get_settings().ANCHOR_MODE.upper(),
            "version": VERSION}
