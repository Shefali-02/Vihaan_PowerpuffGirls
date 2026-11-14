"""Portable proof.json: everything an outsider needs to verify a report without trusting Munshi."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.canonical import canonical_json
from core.ids import workspace_chain_id
from modules.trust import audit
from modules.trust.models import AuditEvent, MerkleBatch, MerkleLeaf, Report

PROOF_FORMAT = "munshi-proof/1"


def bundle_for(s: Session, report: Report) -> dict:
    ws = report.workspace_id
    ev = s.scalar(select(AuditEvent).where(AuditEvent.workspace_id == ws, AuditEvent.seq == report.audit_seq))
    leaf = s.scalar(select(MerkleLeaf).where(MerkleLeaf.workspace_id == ws, MerkleLeaf.audit_seq == report.audit_seq))
    batch = s.get(MerkleBatch, leaf.batch_id) if leaf and leaf.batch_id else None
    out = {
        "format": PROOF_FORMAT,
        "report_id": report.id,
        "report_sha256": report.sha256,
        "event_seq": report.audit_seq,
        "salt": ev.salt,
        "canonical_event": canonical_json(audit.body_of(ev)).decode(),
        "leaf_hash": leaf.leaf_hash if leaf else None,
        "ws_chain_id": "0x" + workspace_chain_id(ws).hex(),
        "status": "ANCHORED" if batch else "PENDING_ANCHOR",
        "leaf_rule": "sha256(0x00 || salt || canonical_event)",
        "node_rule": "sha256(0x01 || left || right); odd node promoted",
        "note": "Hashes only are on-chain. Sign-off is workflow evidence, not a statutory audit.",
    }
    if batch:
        out.update({
            "merkle_path": leaf.proof, "root": "0x" + batch.root, "batch_seq": batch.batch_seq,
            "anchor": {"mode": batch.anchor_mode, "chain_id": batch.chain_id, "contract": batch.contract_address,
                       "tx_hash": batch.tx_hash, "block": batch.block_number},
        })
    return out
