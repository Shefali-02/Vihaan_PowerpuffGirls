"""Test setup: fresh SQLite DB per test, MOCK LLM, MOCK anchor (no network)."""
from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="munshi-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "ANCHOR_MODE": "mock",
    "LLM_MODE": "mock",
    "EXPORT_OPENAPI": "false",
    "JWT_SECRET": "test-secret-test-secret-test-secret",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.db import reset_engine_cache, session_scope  # noqa: E402

reset_engine_cache()

REPO = Path(__file__).resolve().parent.parent
INVOICES = REPO / "seed" / "invoices"
TODAY = date(2026, 11, 14)


@pytest.fixture
def seeded():
    from seed.seed import seed

    return seed(reset=True, today=TODAY)


@pytest.fixture
def client(seeded):
    from apps.api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(seeded):
    with session_scope() as s:
        yield s


def auth(client, email: str, password: str = "demo1234") -> dict:
    r = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def acc(client):
    return auth(client, "accountant@acme.demo")


@pytest.fixture
def ca(client):
    return auth(client, "ca@ca-firm.demo")


@pytest.fixture
def acc2(client, seeded):
    """A second ACCOUNTANT in the same workspace (for maker-checker tests)."""
    from core.security import hash_password
    from modules.identity.models import Membership, User

    with session_scope() as s:
        u = User(email="accountant2@acme.demo", name="Second Accountant", password_hash=hash_password("demo1234"))
        s.add(u)
        s.flush()
        s.add(Membership(workspace_id=seeded["workspace_id"], user_id=u.id, role="ACCOUNTANT"))
    return auth(client, "accountant2@acme.demo")


def upload(client, headers, name: str):
    with open(INVOICES / name, "rb") as f:
        r = client.post("/v1/documents", headers=headers, files={"file": (name, f, "text/plain")})
    assert r.status_code == 201, r.text
    return r.json()


def upload_and_post(client, headers, name: str) -> dict:
    doc = upload(client, headers, name)
    entry_id = doc["proposal"]["draft_entry_id"]
    r = client.post(f"/v1/journals/{entry_id}/post", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
