"""Anchoring port. Only (pseudonymous workspace id, seq, Merkle root) ever leave the system."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from core.config import get_settings

log = logging.getLogger("munshi.anchor")


@dataclass(frozen=True)
class AnchorReceipt:
    tx_hash: str
    block_number: int | None
    chain_id: int | None
    contract: str | None
    mode: str  # HARDHAT | MOCK

    def as_dict(self) -> dict:
        return asdict(self)


class AnchorPort(Protocol):
    mode: str

    def anchor(self, ws_chain_id: bytes, seq: int, root: bytes) -> AnchorReceipt: ...

    def get_root(self, ws_chain_id: bytes, seq: int) -> bytes | None: ...


def get_anchor_port(s: Session, mode: str | None = None, *, allow_fallback: bool = True) -> AnchorPort:
    """ANCHOR_MODE=hardhat uses the local node; if unreachable, falls back to the labelled MOCK anchor."""
    from modules.trust.anchor_mock import MockAnchorPort

    mode = (mode or get_settings().ANCHOR_MODE).lower()
    if mode == "hardhat":
        try:
            from modules.trust.anchor_hardhat import HardhatAnchorPort

            return HardhatAnchorPort()
        except Exception as e:  # node down / not deployed
            if not allow_fallback:
                raise
            log.warning("Hardhat anchor unavailable (%s); using MOCK anchor", e)
    return MockAnchorPort(s)


def effective_mode(s: Session) -> str:
    return get_anchor_port(s).mode
