"""sha256 helpers shared by the audit chain, Merkle tree and verification."""
from __future__ import annotations

import hashlib
import os

GENESIS_PREV = b"\x00" * 32
LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chain_hash(prev_hash: bytes, canonical_event: bytes) -> bytes:
    """hash = sha256(prev_hash || canonical_json(event))."""
    return sha256(prev_hash + canonical_event)


def leaf_hash(salt: bytes, canonical_event: bytes) -> bytes:
    """leaf = sha256(0x00 || salt || canonical_json(event)). Salt stays off-chain."""
    return sha256(LEAF_PREFIX + salt + canonical_event)


def node_hash(left: bytes, right: bytes) -> bytes:
    return sha256(NODE_PREFIX + left + right)


def new_salt() -> bytes:
    return os.urandom(16)


def to_hex(b: bytes) -> str:
    return "0x" + b.hex()


def from_hex(s: str) -> bytes:
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)
