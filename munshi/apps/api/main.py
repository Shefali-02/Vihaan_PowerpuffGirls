"""Munshi API entrypoint: `uvicorn apps.api.main:app`."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routers import (approvals, auth, documents, health, integrations, journals, public, reports, tax,
                              trust)
from core.config import REPO_ROOT, get_settings
from core.db import create_all, session_scope
from core.errors import install_error_handlers
from core.idempotency import IdempotencyMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("munshi")

OPENAPI_PATH = REPO_ROOT / "packages" / "contracts" / "openapi.json"


def export_openapi(app: FastAPI) -> None:
    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    create_all()
    from modules.ai import gateway
    from modules.trust import service as trust_service

    with session_scope() as s:
        anchor_mode = trust_service.anchor_mode(s)
    log.info("Munshi API starting: LLM_MODE=%s ANCHOR_MODE=%s (effective %s)",
             gateway.current_mode(), settings.ANCHOR_MODE.upper(), anchor_mode)
    if settings.EXPORT_OPENAPI:
        try:
            export_openapi(app)
        except OSError as e:  # read-only filesystem in some deploys
            log.warning("could not export OpenAPI: %s", e)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Munshi API",
        version="0.1.0",
        description=("AI-assisted Indian accounting with CA approval and tamper-evident reports. "
                     "All government integrations are MOCK. Demo rates pending CA validation; not legal/tax advice."),
        lifespan=lifespan,
    )
    origins = [o.strip() for o in get_settings().CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=origins != ["*"],
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["Idempotent-Replay"])
    app.add_middleware(IdempotencyMiddleware)
    install_error_handlers(app)
    for r in (health, auth, documents, journals, approvals, reports, tax, trust, integrations, public):
        app.include_router(r.router)
    return app


app = create_app()
