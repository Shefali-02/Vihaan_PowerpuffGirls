"""Hash-chained, append-only audit log (one chain per workspace).

hash_n = sha256(hash_{n-1} || canonical_json(event_n)), genesis prev = 32 zero bytes.
Leaf events also get leaf = sha256(0x00 || salt || canonical_json(event)) for Merkle batching.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.canonical import canonical_json
from core.db import utcnow
from core.hashing import GENESIS_PREV, chain_hash, leaf_hash, new_salt
from modules.trust.models import AuditEvent, ChainHead, MerkleLeaf

LEAF_EVENTS = frozenset({
    "document.ingested", "journal.posted", "journal.reversed", "approval.requested", "approval.decided",
    "period.locked", "report.published", "anchor.confirmed",
})


def event_body(ws: str, seq: int, event_type: str, object_type: str, object_id: str, actor_id: str,
               occurred_at: str, payload: dict) -> dict:
    return {"v": 1, "ws": ws, "seq": seq, "type": event_type,
            "object": {"type": object_type, "id": object_id}, "actor": actor_id, "at": occurred_at,
            "payload": payload}


def body_of(ev: AuditEvent) -> dict:
    return event_body(ev.workspace_id, ev.seq, ev.event_type, ev.object_type, ev.object_id, ev.actor_id,
                      ev.occurred_at, ev.payload)


def record(s: Session, ws: str, event_type: str, object_type: str, object_id: str, actor_id: str,
           payload: dict) -> AuditEvent:
    head = s.scalar(select(ChainHead).where(ChainHead.workspace_id == ws).with_for_update())
    if head is None:
        head = ChainHead(workspace_id=ws, seq=0, head_hash=GENESIS_PREV.hex())
        s.add(head)
        s.flush()
    seq = head.seq + 1
    at = utcnow().isoformat()
    canon = canonical_json(event_body(ws, seq, event_type, object_type, object_id, actor_id, at, payload))
    h = chain_hash(bytes.fromhex(head.head_hash), canon)
    is_leaf = event_type in LEAF_EVENTS
    salt = new_salt() if is_leaf else None
    lh = leaf_hash(salt, canon) if is_leaf else None
    ev = AuditEvent(workspace_id=ws, seq=seq, event_type=event_type, object_type=object_type,
                    object_id=object_id, actor_id=actor_id, occurred_at=at, payload=payload,
                    prev_hash=head.head_hash, hash=h.hex(), is_leaf=is_leaf,
                    salt=salt.hex() if salt else None, leaf_hash=lh.hex() if lh else None)
    s.add(ev)
    head.seq, head.head_hash = seq, h.hex()
    if is_leaf:
        s.add(MerkleLeaf(workspace_id=ws, audit_seq=seq, leaf_hash=lh.hex()))
    s.flush()
    return ev


def verify_chain(s: Session, ws: str) -> dict:
    """Recompute every link; report the first broken seq (None when intact)."""
    prev = GENESIS_PREV
    n = 0
    for ev in s.scalars(select(AuditEvent).where(AuditEvent.workspace_id == ws).order_by(AuditEvent.seq)):
        n += 1
        canon = canonical_json(body_of(ev))
        ok = (ev.seq == n and ev.prev_hash == prev.hex() and chain_hash(prev, canon).hex() == ev.hash)
        if ok and ev.is_leaf:
            ok = ev.salt is not None and leaf_hash(bytes.fromhex(ev.salt), canon).hex() == ev.leaf_hash
        if not ok:
            return {"ok": False, "length": n, "first_broken_seq": ev.seq}
        prev = bytes.fromhex(ev.hash)
    head = s.get(ChainHead, ws)
    if head is not None and head.head_hash != prev.hex():
        return {"ok": False, "length": n, "first_broken_seq": n + 1}
    return {"ok": True, "length": n, "first_broken_seq": None, "head_hash": prev.hex()}
