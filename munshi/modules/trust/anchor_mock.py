"""MOCK anchor: stores roots in the DB with a fake tx hash. Every receipt says mode=MOCK."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.errors import AnchorFailed
from core.hashing import sha256
from modules.trust.anchor_port import AnchorReceipt
from modules.trust.models import MockAnchor


class MockAnchorPort:
    mode = "MOCK"

    def __init__(self, s: Session):
        self.s = s

    def anchor(self, ws_chain_id: bytes, seq: int, root: bytes) -> AnchorReceipt:
        ws_hex = ws_chain_id.hex()
        if self.s.scalar(select(MockAnchor).where(MockAnchor.ws_chain_id == ws_hex, MockAnchor.seq == seq)):
            raise AnchorFailed("MOCK anchor slot already used")
        block = int(self.s.scalar(select(func.count()).select_from(MockAnchor)) or 0) + 1
        tx = "0x" + sha256(b"mock-tx" + ws_chain_id + seq.to_bytes(8, "big") + root).hex()
        self.s.add(MockAnchor(workspace_id="onchain-sim", ws_chain_id=ws_hex, seq=seq, root=root.hex(), tx_hash=tx,
                              block_number=block))
        self.s.flush()
        return AnchorReceipt(tx_hash=tx, block_number=block, chain_id=None, contract=None, mode=self.mode)

    def get_root(self, ws_chain_id: bytes, seq: int) -> bytes | None:
        row = self.s.scalar(select(MockAnchor).where(MockAnchor.ws_chain_id == ws_chain_id.hex(),
                                                     MockAnchor.seq == seq))
        return bytes.fromhex(row.root) if row else None
