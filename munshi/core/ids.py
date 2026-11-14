"""Identifier helpers."""
from __future__ import annotations

import hashlib
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def workspace_chain_id(workspace_id: str) -> bytes:
    """Pseudonymous 32-byte workspace id used on-chain (never the raw id or name)."""
    return hashlib.sha256(b"munshi-ws:" + workspace_id.encode()).digest()
