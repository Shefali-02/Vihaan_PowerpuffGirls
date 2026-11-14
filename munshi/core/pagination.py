"""Opaque keyset cursors over (created_at, id)."""
from __future__ import annotations

import base64
from datetime import datetime

from sqlalchemy import Select, and_, or_


def encode_cursor(created_at: datetime, id_: str) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{id_}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts, id_ = raw.split("|", 1)
    return datetime.fromisoformat(ts), id_


def apply_cursor(stmt: Select, model, cursor: str | None, limit: int) -> Select:
    """Newest first."""
    if cursor:
        ts, id_ = decode_cursor(cursor)
        stmt = stmt.where(or_(model.created_at < ts, and_(model.created_at == ts, model.id < id_)))
    return stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)


def page(rows: list, limit: int) -> tuple[list, str | None]:
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        return rows, encode_cursor(last.created_at, last.id)
    return rows, None
