"""Engine/session setup. Portable types only (Postgres or SQLite via DATABASE_URL)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import DateTime, String, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from core.config import get_settings
from core.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class WorkspaceMixin:
    """Every business table carries workspace_id; every query filters by it."""

    workspace_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


@lru_cache
def get_engine() -> Engine:
    url = get_settings().DATABASE_URL
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=True, expire_on_commit=False)


def ping(s: Session) -> str:
    s.execute(text("SELECT 1"))
    return s.get_bind().dialect.name


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


@contextmanager
def session_scope() -> Iterator[Session]:
    s = get_sessionmaker()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def import_all_models() -> None:
    """Import every models module so Base.metadata knows all tables."""
    import core.idempotency  # noqa: F401
    import core.outbox  # noqa: F401
    import modules.ai.models  # noqa: F401
    import modules.docintel.models  # noqa: F401
    import modules.identity.models  # noqa: F401
    import modules.integrations.models  # noqa: F401
    import modules.ledger.models  # noqa: F401
    import modules.reporting.models  # noqa: F401
    import modules.rules.models  # noqa: F401
    import modules.tax.models  # noqa: F401
    import modules.trust.models  # noqa: F401
    import modules.workflow.models  # noqa: F401


# Postgres-only hardening: append-only audit log and immutable posted journals.
_PG_HARDENING = [
    """
    CREATE OR REPLACE FUNCTION munshi_forbid_change() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'IMMUTABLE_RECORD: % is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events",
    """CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
       FOR EACH ROW EXECUTE FUNCTION munshi_forbid_change()""",
    """
    CREATE OR REPLACE FUNCTION munshi_forbid_posted_change() RETURNS trigger AS $$
    BEGIN
      IF OLD.status = 'POSTED' THEN RAISE EXCEPTION 'IMMUTABLE_RECORD: posted journal'; END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF; RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS journal_entries_posted_immutable ON journal_entries",
    """CREATE TRIGGER journal_entries_posted_immutable BEFORE UPDATE OR DELETE ON journal_entries
       FOR EACH ROW EXECUTE FUNCTION munshi_forbid_posted_change()""",
    "REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM PUBLIC",
]


def create_all() -> None:
    import_all_models()
    engine = get_engine()
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for stmt in _PG_HARDENING:
                conn.execute(text(stmt))


def drop_all() -> None:
    import_all_models()
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events"))
            conn.execute(text("DROP TRIGGER IF EXISTS journal_entries_posted_immutable ON journal_entries"))
    Base.metadata.drop_all(engine)


def reset_engine_cache() -> None:
    """Tests: forget cached engine/sessionmaker after changing DATABASE_URL."""
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
