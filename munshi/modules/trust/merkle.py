"""Binary Merkle tree. Node = sha256(0x01 || left || right); an odd node is promoted unchanged.

Proof = [{"sibling": hex, "position": "left"|"right"}] from leaf to root.
"""
from __future__ import annotations

from core.hashing import node_hash


def build_tree(leaves: list[bytes]) -> list[list[bytes]]:
    if not leaves:
        raise ValueError("cannot build a Merkle tree with no leaves")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur, nxt = levels[-1], []
        for i in range(0, len(cur), 2):
            nxt.append(node_hash(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i])
        levels.append(nxt)
    return levels


def root(levels: list[list[bytes]]) -> bytes:
    return levels[-1][0]


def proof(levels: list[list[bytes]], index: int) -> list[dict]:
    path = []
    for level in levels[:-1]:
        sib = index ^ 1
        if sib < len(level):
            path.append({"sibling": level[sib].hex(), "position": "left" if sib < index else "right"})
        index //= 2
    return path


def verify_proof(leaf: bytes, path: list[dict], expected_root: bytes) -> bool:
    h = leaf
    for step in path:
        sib = bytes.fromhex(step["sibling"])
        h = node_hash(sib, h) if step["position"] == "left" else node_hash(h, sib)
    return h == expected_root
