"""Hash-chained audit log: any edit is detected at the first broken seq; ORM refuses edits."""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from core.errors import ImmutableRecord
from modules.trust import audit
from modules.trust.models import AuditEvent, MerkleLeaf


def _seed_events(db, ws, n=6):
    for i in range(n):
        audit.record(db, ws, "journal.posted" if i % 2 == 0 else "note.added", "journal", f"obj-{i}", "user-1",
                     {"i": i, "total_paise": 1000 * i})
    db.commit()


def test_intact_chain_verifies(db, seeded):
    ws = seeded["workspace_id"]
    _seed_events(db, ws)
    res = audit.verify_chain(db, ws)
    assert res == {"ok": True, "length": 6, "first_broken_seq": None, "head_hash": res["head_hash"]}
    leaves = db.scalars(select(MerkleLeaf).where(MerkleLeaf.workspace_id == ws)).all()
    assert len(leaves) == 3  # only leaf event types get leaves


def test_editing_one_event_reports_first_broken_seq(db, seeded):
    ws = seeded["workspace_id"]
    _seed_events(db, ws)
    db.execute(text("UPDATE audit_events SET payload = :p WHERE workspace_id = :ws AND seq = 4"),
               {"p": '{"i": 3, "total_paise": 999999}', "ws": ws})  # bypasses ORM guard (SQLite has no trigger)
    db.commit()
    assert audit.verify_chain(db, ws)["first_broken_seq"] == 4


def test_deleting_an_event_is_detected(db, seeded):
    ws = seeded["workspace_id"]
    _seed_events(db, ws)
    db.execute(text("DELETE FROM audit_events WHERE workspace_id = :ws AND seq = 2"), {"ws": ws})
    db.commit()
    assert audit.verify_chain(db, ws)["first_broken_seq"] == 3


def test_orm_guard_blocks_update_and_delete(db, seeded):
    ws = seeded["workspace_id"]
    _seed_events(db, ws, 2)
    ev = db.scalar(select(AuditEvent).where(AuditEvent.workspace_id == ws, AuditEvent.seq == 1))
    ev.payload = {"hacked": True}
    with pytest.raises(ImmutableRecord):
        db.flush()
    db.rollback()
    ev = db.scalar(select(AuditEvent).where(AuditEvent.workspace_id == ws, AuditEvent.seq == 1))
    db.delete(ev)
    with pytest.raises(ImmutableRecord):
        db.flush()
    db.rollback()


def test_posting_adds_chained_event_and_leaf(client, acc, db, seeded):
    from tests.conftest import upload_and_post

    upload_and_post(client, acc, "01_purchase_intra_18.txt")
    types = [e.event_type for e in db.scalars(select(AuditEvent).order_by(AuditEvent.seq))]
    assert types == ["document.ingested", "journal.posted"]
    st = client.get("/v1/trust/status", headers=acc).json()
    assert st["chain_valid"] and st["chain_length"] == 2
