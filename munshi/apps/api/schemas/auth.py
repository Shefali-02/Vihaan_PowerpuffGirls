from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str
    workspace_id: str
    user_id: str
    name: str


class MeResponse(BaseModel):
    user_id: str
    workspace_id: str
    role: str
    name: str
    email: str
    ca_reg_no: str | None = None
    workspace: dict
