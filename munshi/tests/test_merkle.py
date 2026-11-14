"""Merkle tree: proofs for every leaf at sizes 1,2,3,7,8; wrong leaf or sibling fails."""
from __future__ import annotations

import pytest

from core.hashing import node_hash, sha256
from modules.trust import merkle


def leaves(n):
    return [sha256(f"leaf-{i}".encode()) for i in range(n)]


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8])
def test_every_leaf_proves(n):
    ls = leaves(n)
    levels = merkle.build_tree(ls)
    root = merkle.root(levels)
    for i, lf in enumerate(ls):
        assert merkle.verify_proof(lf, merkle.proof(levels, i), root)


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8])
def test_wrong_leaf_fails(n):
    ls = leaves(n)
    levels = merkle.build_tree(ls)
    root = merkle.root(levels)
    for i in range(n):
        assert not merkle.verify_proof(sha256(b"evil"), merkle.proof(levels, i), root)


def test_single_leaf_root_is_leaf_and_odd_node_promoted():
    ls = leaves(3)
    assert merkle.root(merkle.build_tree(ls[:1])) == ls[0]
    assert merkle.root(merkle.build_tree(ls)) == node_hash(node_hash(ls[0], ls[1]), ls[2])


def test_tampered_sibling_fails():
    ls = leaves(8)
    levels = merkle.build_tree(ls)
    p = merkle.proof(levels, 5)
    p[1] = {**p[1], "sibling": sha256(b"x").hex()}
    assert not merkle.verify_proof(ls[5], p, merkle.root(levels))


def test_empty_tree_rejected():
    with pytest.raises(ValueError):
        merkle.build_tree([])
