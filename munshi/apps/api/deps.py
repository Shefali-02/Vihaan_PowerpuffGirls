"""Request dependencies: one DB transaction per request (committed BEFORE the response is sent)."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.db import get_sessionmaker
from core.errors import Unauthenticated
from modules.identity import service as identity
from modules.identity.service import Principal

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    s = get_sessionmaker()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


DB = Annotated[Session, Depends(get_db, scope="function")]


def current_principal(db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthenticated("Bearer token required")
    return identity.principal_from_token(db, creds.credentials)


CurrentUser = Annotated[Principal, Depends(current_principal)]


def require(*roles: str):
    def _dep(p: CurrentUser) -> Principal:
        identity.require_role(p, *roles)
        return p
    return Depends(_dep)
