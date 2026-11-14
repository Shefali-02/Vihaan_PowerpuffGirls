#!/usr/bin/env python3
"""Independent verifier: PDF + proof.json (+ chain RPC) -> MATCH / NO MATCH.

Deliberately imports NOTHING from Munshi: it re-implements the hashing rules so an outsider can audit them.

  python scripts/verify_cli.py investor-pack.pdf proof.json --rpc http://127.0.0.1:8545
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def fold(leaf: bytes, path: list[dict]) -> bytes:
    h = leaf
    for step in path:
        sib = bytes.fromhex(step["sibling"])
        h = sha256(b"\x01" + sib + h) if step["position"] == "left" else sha256(b"\x01" + h + sib)
    return h


def read_root_from_chain(rpc: str, contract: str, ws_chain_id: str, seq: int) -> bytes | None:
    from web3 import Web3  # only needed for HARDHAT proofs

    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
    abi = [{"name": "rootOf", "type": "function", "stateMutability": "view",
            "inputs": [{"name": "", "type": "bytes32"}, {"name": "", "type": "uint64"}],
            "outputs": [{"name": "", "type": "bytes32"}]}]
    c = w3.eth.contract(address=Web3.to_checksum_address(contract), abi=abi)
    root = bytes(c.functions.rootOf(bytes.fromhex(ws_chain_id.removeprefix("0x")), seq).call())
    return None if root == b"\x00" * 32 else root


def verify(pdf: bytes, proof: dict, rpc: str | None) -> tuple[str, list[str]]:
    notes: list[str] = []
    file_hash = hashlib.sha256(pdf).hexdigest()
    if file_hash != proof["report_sha256"]:
        return "NO MATCH", [f"file sha256 {file_hash} != proof report_sha256 {proof['report_sha256']}"]
    notes.append("file hash matches proof")
    event = json.loads(proof["canonical_event"])
    if event.get("type") != "report.published" or event.get("payload", {}).get("report_sha256") != file_hash:
        return "NO MATCH", notes + ["audit event does not commit to this file hash"]
    leaf = sha256(b"\x00" + bytes.fromhex(proof["salt"]) + proof["canonical_event"].encode())
    if leaf.hex() != proof["leaf_hash"]:
        return "NO MATCH", notes + ["leaf hash recomputation failed"]
    notes.append("leaf recomputed from salt + canonical event")
    if proof.get("status") != "ANCHORED":
        return "NO MATCH", notes + ["proof is not anchored yet"]
    root = fold(leaf, proof["merkle_path"])
    if "0x" + root.hex() != proof["root"]:
        return "NO MATCH", notes + ["Merkle path does not reach the stated root"]
    notes.append("Merkle path reaches root")
    anchor = proof["anchor"]
    if anchor["mode"] == "MOCK":
        notes.append("MOCK anchor: no blockchain to read; root only checked against proof.json "
                     "(use GET /public/verify for the server-side check)")
        return "MATCH (MOCK ANCHOR)", notes
    if not rpc:
        return "NO MATCH", notes + ["--rpc required to read the anchored root from the chain"]
    onchain = read_root_from_chain(rpc, anchor["contract"], proof["ws_chain_id"], int(proof["batch_seq"]))
    if onchain is None or onchain != root:
        return "NO MATCH", notes + ["on-chain root missing or different"]
    notes.append(f"root read from chain {anchor['chain_id']} contract {anchor['contract']} matches")
    return "MATCH", notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("proof")
    ap.add_argument("--rpc", default=None, help="JSON-RPC URL of the chain holding AnchorRegistry")
    args = ap.parse_args(argv)
    with open(args.pdf, "rb") as f:
        pdf = f.read()
    with open(args.proof) as f:
        proof = json.load(f)
    verdict, notes = verify(pdf, proof, args.rpc)
    for n in notes:
        print(" -", n)
    print(verdict)
    return 0 if verdict.startswith("MATCH") else 1


if __name__ == "__main__":
    sys.exit(main())
