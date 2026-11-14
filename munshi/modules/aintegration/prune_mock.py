"""
PruneMock — deterministic LlmBackend for the new LlmGateway protocol.

Implements the same interface as PruneClient so LlmGateway can swap them:
    backend.complete(payload) -> {"output", "prune_run_id", "model", "usage"}
    backend.is_mock -> True

Fixture lookup priority:
  1. munshi/seed/fixtures/ai/<prompt_id>/<input_hash>.json
  2. Deterministic text parser for the seed/invoices labelled-text format
  3. Empty extraction with 0-confidence (triggers manual_review in the gateway)
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Seed fixtures are relative to the munshi package root
_FIXTURE_ROOT: Path | None = None


def _fixtures() -> Path:
    global _FIXTURE_ROOT
    if _FIXTURE_ROOT is None:
        here = Path(__file__).resolve()
        # Walk up to find the munshi package root (contains seed/)
        for parent in here.parents:
            candidate = parent / "seed" / "fixtures" / "ai"
            if candidate.exists():
                _FIXTURE_ROOT = candidate
                break
        if _FIXTURE_ROOT is None:
            _FIXTURE_ROOT = Path(__file__).parent  # fallback: no fixtures found
    return _FIXTURE_ROOT


_MOCK_MODEL = "prune-mock-1"

# Labels used by the seed/invoices text format
_LABELS: dict[str, str] = {
    "invoice no": "invoice_no", "invoice number": "invoice_no", "invoice date": "invoice_date",
    "seller": "seller_name", "seller gstin": "seller_gstin",
    "buyer": "buyer_name", "buyer gstin": "buyer_gstin",
    "place of supply": "place_of_supply", "category": "category",
    "total": "total", "invoice total": "total", "tax total": "tax_total",
}
_ITEM_RE = re.compile(
    r"^\s*\d+\s*\|\s*(?P<desc>[^|]+)\|\s*(?P<hsn>[^|]*)\|\s*"
    r"(?P<amt>[\d,]+(?:\.\d+)?)\s*\|\s*(?P<rate>\d+(?:\.\d+)?)\s*%\s*"
    r"(?:\|\s*(?P<cat>[a-z_]+))?\s*$"
)


def _parse_invoice_text(text: str) -> dict:
    out: dict[str, Any] = {k: None for k in (
        "invoice_no", "invoice_date", "seller_name", "seller_gstin",
        "buyer_name", "buyer_gstin", "place_of_supply", "category", "tax_total", "total",
    )}
    lines = []
    for raw in text.splitlines():
        m = _ITEM_RE.match(raw)
        if m:
            lines.append({
                "description": m["desc"].strip(),
                "hsn_sac": m["hsn"].strip() or None,
                "taxable_value": m["amt"].replace(",", ""),
                "gst_rate_pct": m["rate"],
                "category": m["cat"],
            })
            continue
        if ":" in raw:
            k, v = raw.split(":", 1)
            key = _LABELS.get(k.strip().lower())
            if key and v.strip():
                val = v.strip()
                if key in ("total", "tax_total"):
                    val = val.replace("₹", "").replace("Rs.", "").replace(",", "").strip()
                out[key] = val
    out["lines"] = lines
    conf = {k: (0.97 if out.get(k) else 0.0)
            for k in ("invoice_no", "invoice_date", "seller_gstin", "buyer_gstin", "total")}
    conf["lines"] = 0.97 if lines else 0.0
    out["confidence"] = conf
    return out


class PruneMock:
    is_mock: bool = True
    model: str = _MOCK_MODEL

    # -- LlmBackend protocol -----------------------------------------------
    def complete(self, payload: dict) -> dict:
        """
        payload keys used here:
          messages        list[{"role", "content"}]
          metadata        dict — contains prompt_id and idempotency_key
        """
        meta = payload.get("metadata", {})
        prompt_id = meta.get("prompt_id", "")
        idempotency_key = meta.get("idempotency_key", "")

        # Derive an input hash from the idempotency key or message content
        input_hash = hashlib.sha256(idempotency_key.encode()).hexdigest() if idempotency_key else ""

        # 1. Try fixture file
        if input_hash:
            safe_id = prompt_id.replace("@", "_at_").replace("/", "_")
            fx = _fixtures() / safe_id / f"{input_hash}.json"
            if fx.exists():
                data = json.loads(fx.read_text())
                if data.get("_simulate") == "error":
                    from .llm_gateway import BackendUnavailable
                    raise BackendUnavailable("MOCK: simulated gateway failure")
                return {"output": data.get("output", data), "prune_run_id": f"mock-{input_hash[:8]}",
                        "model": self.model, "usage": {"in": 0, "out": 0, "cost": 0.0}}

        # 2. Parse from user message text (seed invoice format)
        user_text = ""
        for msg in payload.get("messages", []):
            if msg.get("role") == "user":
                user_text = msg.get("content", "")
                break

        if prompt_id.startswith("docintel"):
            output = _parse_invoice_text(user_text)
        else:
            # Minimal classification response as fallback
            output = {"document_type": "purchase_invoice", "confidence": 0.5, "reason": "mock fallback"}

        return {"output": output, "prune_run_id": f"mock-{abs(hash(user_text)):016x}",
                "model": self.model, "usage": {"in": 0, "out": 0, "cost": 0.0}}
