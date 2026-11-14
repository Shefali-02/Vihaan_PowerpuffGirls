from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import DB, CurrentUser
from apps.api.schemas.auth import LoginRequest, MeResponse, TokenResponse
from apps.api.schemas.common import ERROR_RESPONSES
from modules.identity import service as identity

router = APIRouter(prefix="/v1/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DB):
    return identity.login(db, body.email, body.password)


@router.get("/me", response_model=MeResponse)
def me(p: CurrentUser, db: DB):
    w = identity.get_workspace(db, p.workspace_id)
    return {"user_id": p.user_id, "workspace_id": p.workspace_id, "role": p.role, "name": p.name, "email": p.email,
            "ca_reg_no": p.ca_reg_no, "workspace": {"id": w.id, "name": w.name, "gstin": w.gstin,
                                                    "state_code": w.state_code}}
