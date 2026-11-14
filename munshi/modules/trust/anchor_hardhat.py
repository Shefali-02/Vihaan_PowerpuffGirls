"""Anchor to the AnchorRegistry contract on a local Hardhat node via web3.py.

Reads ONLY chain/deployments/local.json ({address, abi_path, chain_id, anchorer}).
"""
from __future__ import annotations

import json
from pathlib import Path

from web3 import Web3

from core.config import get_settings
from core.errors import AnchorFailed
from modules.trust.anchor_port import AnchorReceipt

ZERO32 = b"\x00" * 32


class HardhatAnchorPort:
    mode = "HARDHAT"

    def __init__(self):
        s = get_settings()
        dep_path = Path(s.DEPLOYMENT_FILE)
        if not dep_path.exists():
            raise RuntimeError(f"deployment file missing: {dep_path}")
        dep = json.loads(dep_path.read_text())
        abi_path = Path(dep["abi_path"])
        if not abi_path.is_absolute():
            abi_path = dep_path.parent.parent / abi_path
        abi = json.loads(abi_path.read_text())
        abi = abi["abi"] if isinstance(abi, dict) else abi
        self.w3 = Web3(Web3.HTTPProvider(s.CHAIN_RPC_URL, request_kwargs={"timeout": 5}))
        if not self.w3.is_connected():
            raise RuntimeError(f"chain node unreachable at {s.CHAIN_RPC_URL}")
        self.address = Web3.to_checksum_address(dep["address"])
        if self.w3.eth.get_code(self.address) in (b"", b"\x00"):
            raise RuntimeError("no contract code at deployment address (node restarted?)")
        self.chain_id = int(self.w3.eth.chain_id)
        self.contract = self.w3.eth.contract(address=self.address, abi=abi)
        self.private_key = s.ANCHOR_PRIVATE_KEY or None
        self.anchorer = Web3.to_checksum_address(dep["anchorer"])

    def anchor(self, ws_chain_id: bytes, seq: int, root: bytes) -> AnchorReceipt:
        try:
            fn = self.contract.functions.anchor(ws_chain_id, seq, root)
            if self.private_key:
                acct = self.w3.eth.account.from_key(self.private_key)
                tx = fn.build_transaction({"from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address),
                                           "chainId": self.chain_id})
                signed = acct.sign_transaction(tx)
                raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
                tx_hash = self.w3.eth.send_raw_transaction(raw)
            else:
                tx_hash = fn.transact({"from": self.anchorer})
            rcpt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            if rcpt.status != 1:
                raise AnchorFailed("anchor transaction reverted")
        except AnchorFailed:
            raise
        except Exception as e:
            raise AnchorFailed(f"anchor failed: {e}") from e
        return AnchorReceipt(tx_hash=Web3.to_hex(tx_hash), block_number=int(rcpt.blockNumber),
                             chain_id=self.chain_id, contract=self.address, mode=self.mode)

    def get_root(self, ws_chain_id: bytes, seq: int) -> bytes | None:
        r = bytes(self.contract.functions.rootOf(ws_chain_id, seq).call())
        return None if r == ZERO32 else r
