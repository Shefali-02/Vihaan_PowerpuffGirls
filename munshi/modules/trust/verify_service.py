"""Public verification: report hash -> leaf -> Merkle proof -> root read FROM THE CHAIN -> MATCH / NO MATCH.

Never returns amounts or counterparty names. Unknown hash = NO MATCH.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.canonical import canonical_json
from core.hashing import leaf_hash, sha256_hex
from core.ids import workspace_chain_id
from modules.trust import audit, merkle
from modules.trust.anchor_port import get_anchor_port
from modules.trust.models import AuditEvent, MerkleBatch, MerkleLeaf, Report


def _no(h: str, *reasons: str, anchor: dict | None = None) -> dict:
    return {"verdict": "NO MATCH", "hash": h, "reasons": list(reasons), "anchor": anchor, "signoffs": [],
            "report": None}


def verify_hash(s: Session, sha: str) -> dict:
    h = (sha or "").lower().removeprefix("0x").strip()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        return _no(h, "Not a sha256 hex digest")
    report = s.scalar(select(Report).where(Report.sha256 == h))  # global lookup by hash; scope from the row
    if report is None:
        return _no(h, "No published report has this hash (file differs from any published pack)")
    ws = report.workspace_id
    ev = s.scalar(select(AuditEvent).where(AuditEvent.workspace_id == ws, AuditEvent.seq == report.audit_seq))
    leaf = s.scalar(select(MerkleLeaf).where(MerkleLeaf.workspace_id == ws, MerkleLeaf.audit_seq == report.audit_seq))
    if ev is None or leaf is None:
        return _no(h, "Audit record for this report is missing")
    canon = canonical_json(audit.body_of(ev))
    if ev.event_type != "report.published" or ev.payload.get("report_sha256") != h:
        return _no(h, "Audit event does not commit to this hash")
    if leaf_hash(bytes.fromhex(ev.salt), canon).hex() != leaf.leaf_hash:
        return _no(h, "Leaf hash does not match the audit event")
    if leaf.batch_id is None:
        return {**_no(h, "Report is published but not yet anchored"), "verdict": "PENDING"}
    batch = s.get(MerkleBatch, leaf.batch_id)
    anchor = {"tx": batch.tx_hash, "block": batch.block_number, "chain": batch.chain_id,
              "contract": batch.contract_address, "mode": batch.anchor_mode, "batch_seq": batch.batch_seq,
              "root": "0x" + batch.root}
    if not merkle.verify_proof(bytes.fromhex(leaf.leaf_hash), leaf.proof or [], bytes.fromhex(batch.root)):
        return _no(h, "Merkle proof does not reach the batch root", anchor=anchor)
    try:
        port = get_anchor_port(s, batch.anchor_mode.lower(), allow_fallback=False)
        onchain = port.get_root(workspace_chain_id(ws), batch.batch_seq)
    except Exception as e:
        return _no(h, f"Could not read root from chain: {e}", anchor=anchor)
    if onchain is None:
        return _no(h, "No root anchored on chain for this batch", anchor=anchor)
    if onchain.hex() != batch.root:
        return _no(h, "On-chain root differs from recomputed root", anchor=anchor)
    reasons = ["File hash matches a published report", "Leaf recomputed from audit event",
               "Merkle proof reaches root", f"Root read from {batch.anchor_mode} anchor matches"]
    if batch.anchor_mode == "MOCK":
        reasons.append("MOCK anchor: root stored in Munshi DB, not on a blockchain")
    return {"verdict": "MATCH", "hash": h, "reasons": reasons, "anchor": anchor,
            "signoffs": report.pack_json.get("signoffs", []),
            "report": {"id": report.id, "period": report.pack_json.get("period", {}).get("name"),
                       "published_at": report.created_at.isoformat() if report.created_at else None}}


def verify_upload(s: Session, data: bytes) -> dict:
    return verify_hash(s, sha256_hex(data))
