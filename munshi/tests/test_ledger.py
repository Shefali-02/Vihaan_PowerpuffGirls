"""Ledger: posting re-runs the engine, posted entries are immutable, P&L reflects posted lines only."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.errors import ImmutableRecord
from modules.ledger.models import JournalEntry, JournalLine
from tests.conftest import upload, upload_and_post

FACTS = {
    "doc_type": "purchase_invoice", "invoice_no": "MAN-1", "invoice_date": "2026-10-10",
    "counterparty_name": "Manual Vendor", "counterparty_gstin": "07AAFCS4321K1ZC", "category": "rent",
    "lines": [{"description": "Office rent", "hsn_sac": "997212", "taxable_paise": 3000000, "gst_rate_bp": 1800}],
}


def test_manual_draft_post_and_pnl(client, acc):
    r = client.post("/v1/journals/draft", headers=acc, json=FACTS)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "DRAFT" and d["total_paise"] == 3_540_000
    pnl = client.get("/v1/reports/pnl", headers=acc).json()
    assert pnl["total_expenses_paise"] == 0  # drafts never hit reports
    r = client.post(f"/v1/journals/{d['id']}/post", headers=acc)
    assert r.status_code == 200 and r.json()["status"] == "POSTED"
    pnl = client.get("/v1/reports/pnl", headers=acc).json()
    assert pnl["total_expenses_paise"] == 3_000_000 and pnl["net_profit"] == "-₹30,000.00"
    again = client.post(f"/v1/journals/{d['id']}/post", headers=acc)
    assert again.status_code == 409 and again.json()["code"] == "INVALID_STATE_TRANSITION"


def test_rule_rejection_is_problem_json(client, acc):
    bad = {**FACTS, "counterparty_gstin": "07AAFCS4321K1Z0"}
    r = client.post("/v1/journals/draft", headers=acc, json=bad)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "RULE_REJECTED" and r.json()["reasons"][0]["code"] == "INVALID_GSTIN"


def test_posted_entry_is_immutable(client, acc, db):
    posted = upload_and_post(client, acc, "01_purchase_intra_18.txt")
    e = db.scalar(select(JournalEntry).where(JournalEntry.id == posted["id"]))
    e.narration = "tampered"
    with pytest.raises(ImmutableRecord):
        db.flush()
    db.rollback()
    line = db.scalar(select(JournalLine).where(JournalLine.entry_id == posted["id"]))
    line.debit_paise += 1
    with pytest.raises(ImmutableRecord):
        db.flush()
    db.rollback()


def test_post_detects_tampered_draft(client, acc, db):
    doc = upload(client, acc, "01_purchase_intra_18.txt")
    entry_id = doc["proposal"]["draft_entry_id"]
    line = db.scalar(select(JournalLine).where(JournalLine.entry_id == entry_id, JournalLine.account_code == "2100"))
    other = db.scalar(select(JournalLine).where(JournalLine.entry_id == entry_id, JournalLine.account_code == "5200"))
    line.credit_paise += 100
    other.debit_paise += 100  # still balanced, but not what the rules produce
    db.commit()
    r = client.post(f"/v1/journals/{entry_id}/post", headers=acc)
    assert r.status_code == 409 and r.json()["code"] == "DRAFT_MISMATCH"


def test_investor_cannot_post(client, acc):
    from tests.conftest import auth

    inv = auth(client, "investor@acme.demo")
    d = client.post("/v1/journals/draft", headers=acc, json=FACTS).json()
    r = client.post(f"/v1/journals/{d['id']}/post", headers=inv)
    assert r.status_code == 403 and r.json()["code"] == "ROLE_NOT_PERMITTED"


def test_idempotency_key_replays_response(client, acc):
    h = {**acc, "Idempotency-Key": "draft-123"}
    a = client.post("/v1/journals/draft", headers=h, json=FACTS)
    b = client.post("/v1/journals/draft", headers=h, json=FACTS)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"] and b.headers.get("Idempotent-Replay") == "true"


def test_reversal_nets_to_zero(client, acc, db, seeded):
    from modules.identity.service import principal_from_token
    from modules.ledger import service as ledger

    posted = upload_and_post(client, acc, "01_purchase_intra_18.txt")
    p = principal_from_token(db, acc["Authorization"].split()[1])
    ledger.reverse(db, p, posted["id"], reason="wrong vendor")
    db.commit()
    pnl = client.get("/v1/reports/pnl", headers=acc).json()
    assert pnl["total_expenses_paise"] == 0
