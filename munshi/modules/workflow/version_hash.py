"""What exactly a reviewer approves, per object type, hashed with the single canonicaliser.

journal        -> entry snapshot (date, narration, lines)
period_close   -> trial-balance snapshot of the period
investor_pack  -> pack JSON + PDF sha256
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from core.canonical import canonical_json
from core.errors import ValidationFailed
from core.hashing import sha256_hex
from modules.ledger import service as ledger


def snapshot(s: Session, ws: str, object_type: str, object_id: str, extra: dict | None = None) -> dict:
    if object_type == "journal":
        return {"type": "journal", "entry": ledger.entry_snapshot(s, ws, object_id)}
    if object_type == "period_close":
        tb = ledger.trial_balance(s, ws, object_id)
        return {"type": "period_close", "period": ledger.get_period(s, ws, object_id)["name"],
                "trial_balance": [{k: r[k] for k in ("code", "debit_paise", "credit_paise")} for r in tb["rows"]]}
    if object_type == "investor_pack":
        if not extra or "pack_json" not in extra or "pdf_sha256" not in extra:
            raise ValidationFailed("investor_pack approval needs pack_json and pdf_sha256")
        return {"type": "investor_pack", "pack": extra["pack_json"], "pdf_sha256": extra["pdf_sha256"]}
    raise ValidationFailed(f"Unknown object type {object_type}")


def compute(snap: dict) -> str:
    return sha256_hex(canonical_json(snap))
