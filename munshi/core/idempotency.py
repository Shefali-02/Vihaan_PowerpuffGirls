"""Idempotency-Key support for creating POSTs (ASGI-level, so routers stay DB-free).

Scope = (workspace, user, method+path, key). A replay returns the stored response.
"""
from __future__ import annotations

import json

from sqlalchemy import JSON, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.db import Base, IdMixin, TimestampMixin, get_sessionmaker
from core.security import decode_token


class IdempotencyKey(Base, IdMixin, TimestampMixin):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", "route", "key"),)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36))
    route: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSON)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get("idempotency-key")
        auth = request.headers.get("authorization", "")
        if request.method != "POST" or not key or not auth.lower().startswith("bearer "):
            return await call_next(request)
        try:
            claims = decode_token(auth.split(" ", 1)[1])
        except Exception:
            return await call_next(request)
        ws, uid, route = claims["ws"], claims["sub"], f"POST {request.url.path}"
        Session = get_sessionmaker()
        with Session() as s:
            row = s.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.workspace_id == ws, IdempotencyKey.user_id == uid,
                    IdempotencyKey.route == route, IdempotencyKey.key == key,
                )
            )
            if row is not None:
                return Response(json.dumps(row.response_body), status_code=row.status_code,
                                media_type="application/json", headers={"Idempotent-Replay": "true"})
        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])
        ctype = response.headers.get("content-type", "")
        if response.status_code < 500 and "json" in ctype:
            try:
                with Session() as s:
                    s.add(IdempotencyKey(workspace_id=ws, user_id=uid, route=route, key=key,
                                         status_code=response.status_code, response_body=json.loads(body or b"{}")))
                    s.commit()
            except Exception:  # race with a concurrent identical request: first writer wins
                pass
        return Response(body, status_code=response.status_code, headers=dict(response.headers),
                        media_type=response.media_type)
