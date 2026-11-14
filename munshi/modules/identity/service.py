"""Login, current principal, role checks, workspace context for other modules."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.errors import NotFound, RoleNotPermitted, Unauthenticated
from core.security import decode_token, issue_token, verify_password
from modules.identity import repository as repo


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: str
    role: str
    name: str
    email: str
    ca_reg_no: str | None = None


@dataclass(frozen=True)
class WorkspaceContext:
    id: str
    name: str
    gstin: str
    state_code: str


def login(s: Session, email: str, password: str) -> dict:
    user = repo.user_by_email(s, email)
    if user is None or not verify_password(password, user.password_hash):
        raise Unauthenticated("Invalid email or password")
    ms = repo.memberships_for(s, user.id)
    if not ms:
        raise Unauthenticated("User has no workspace membership")
    m = ms[0]
    token, ttl = issue_token(user_id=user.id, workspace_id=m.workspace_id, role=m.role)
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl,
            "role": m.role, "workspace_id": m.workspace_id, "user_id": user.id, "name": user.name}


def principal_from_token(s: Session, token: str) -> Principal:
    claims = decode_token(token)
    user = repo.user_by_id(s, claims["sub"])
    m = repo.membership(s, claims["ws"], claims["sub"]) if user else None
    if user is None or m is None:
        raise Unauthenticated("Unknown user or membership revoked")
    return Principal(user.id, m.workspace_id, m.role, user.name, user.email, user.ca_reg_no)


def require_role(p: Principal, *roles: str) -> None:
    if p.role not in roles:
        raise RoleNotPermitted(f"Role {p.role} cannot do this; requires one of {', '.join(roles)}")


def get_workspace(s: Session, workspace_id: str) -> WorkspaceContext:
    w = repo.workspace(s, workspace_id)
    if w is None:
        raise NotFound("Workspace not found")
    return WorkspaceContext(w.id, w.name, w.gstin, w.state_code)


def user_display(s: Session, user_id: str, workspace_id: str) -> dict:
    u = repo.user_by_id(s, user_id)
    m = repo.membership(s, workspace_id, user_id)
    if u is None:
        return {"name": "unknown", "role": "unknown"}
    name = u.name + (f" ({u.ca_reg_no})" if u.ca_reg_no else "")
    return {"name": name, "role": m.role if m else "unknown"}


def all_workspace_ids(s: Session) -> list[str]:
    return repo.all_workspace_ids(s)
