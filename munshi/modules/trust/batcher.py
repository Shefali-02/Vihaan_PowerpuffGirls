"""Batch unanchored leaves per workspace -> Merkle tree -> anchor root -> store proofs -> audit."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.ids import workspace_chain_id
from modules.trust import audit, merkle
from modules.trust.anchor_port import get_anchor_port
from modules.trust.models import MerkleBatch, MerkleLeaf


def run(s: Session, trigger: str = "manual", workspace_id: str | None = None) -> list[dict]:
    stmt = select(MerkleLeaf.workspace_id).where(MerkleLeaf.batch_id.is_(None)).distinct()
    if workspace_id:
        stmt = stmt.where(MerkleLeaf.workspace_id == workspace_id)
    out = []
    for ws in sorted(s.scalars(stmt)):
        out.append(_run_workspace(s, ws, trigger))
    return out


def _run_workspace(s: Session, ws: str, trigger: str) -> dict:
    leaves = list(s.scalars(select(MerkleLeaf).where(MerkleLeaf.workspace_id == ws, MerkleLeaf.batch_id.is_(None))
                            .order_by(MerkleLeaf.audit_seq)))
    levels = merkle.build_tree([bytes.fromhex(lf.leaf_hash) for lf in leaves])
    root = merkle.root(levels)
    batch_seq = int(s.scalar(select(func.coalesce(func.max(MerkleBatch.batch_seq), 0))
                             .where(MerkleBatch.workspace_id == ws)) or 0) + 1
    port = get_anchor_port(s)
    receipt = port.anchor(workspace_chain_id(ws), batch_seq, root)
    batch = MerkleBatch(workspace_id=ws, batch_seq=batch_seq, root=root.hex(), leaf_count=len(leaves),
                        from_seq=leaves[0].audit_seq, to_seq=leaves[-1].audit_seq, trigger=trigger,
                        anchor_mode=receipt.mode, chain_id=receipt.chain_id, contract_address=receipt.contract,
                        tx_hash=receipt.tx_hash, block_number=receipt.block_number)
    s.add(batch)
    s.flush()
    for i, lf in enumerate(leaves):
        lf.batch_id, lf.leaf_index, lf.proof = batch.id, i, merkle.proof(levels, i)
    s.flush()
    audit.record(s, ws, "anchor.confirmed", "merkle_batch", batch.id, "system",
                 {"batch_seq": batch_seq, "root": root.hex(), "leaf_count": len(leaves),
                  "tx_hash": receipt.tx_hash, "block": receipt.block_number, "mode": receipt.mode})
    return batch_view(batch)


def batch_view(b: MerkleBatch) -> dict:
    return {"id": b.id, "batch_seq": b.batch_seq, "root": "0x" + b.root, "leaf_count": b.leaf_count,
            "from_seq": b.from_seq, "to_seq": b.to_seq, "trigger": b.trigger,
            "anchor": {"mode": b.anchor_mode, "tx_hash": b.tx_hash, "block": b.block_number, "chain_id": b.chain_id,
                       "contract": b.contract_address},
            "created_at": b.created_at.isoformat() if b.created_at else None}
