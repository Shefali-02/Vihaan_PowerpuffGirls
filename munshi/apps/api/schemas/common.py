from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Problem(BaseModel):
    """RFC 7807 problem+json with a stable machine `code`."""

    type: str
    title: str
    status: int
    code: str
    detail: str
    instance: str = ""


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": Problem, "description": "UNAUTHENTICATED"},
    403: {"model": Problem, "description": "FORBIDDEN / ROLE_NOT_PERMITTED / SELF_APPROVAL_FORBIDDEN"},
    404: {"model": Problem, "description": "NOT_FOUND"},
    409: {"model": Problem, "description": "Conflict (see code)"},
    422: {"model": Problem, "description": "VALIDATION_ERROR / RULE_REJECTED / ..."},
}


class Modes(BaseModel):
    llm_mode: str = Field(..., examples=["MOCK"])
    anchor_mode: str = Field(..., examples=["HARDHAT"])
