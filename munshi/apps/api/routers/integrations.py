from __future__ import annotations

from fastapi import APIRouter

from apps.api.deps import CurrentUser
from apps.api.schemas.common import ERROR_RESPONSES
from apps.api.schemas.reports import IntegrationsOut
from modules.integrations import service as integrations

router = APIRouter(prefix="/v1", tags=["integrations"], responses=ERROR_RESPONSES)


@router.get("/integrations", response_model=IntegrationsOut)
def list_integrations(p: CurrentUser):
    return integrations.list_integrations()
