"""Deterministic stand-in for Prune. Every response is labelled llm_mode="MOCK".

1. Fixture lookup: seed/fixtures/ai/<prompt_id>/<input_hash>.json
2. Fallback: a deterministic parser for the labelled-text invoice layout used by seed/invoices.
"""
from __future__ import annotations

import json
import re

from core.config import REPO_ROOT
from modules.ai import prompts

FIXTURES = REPO_ROOT / "seed" / "fixtures" / "ai"
_CONF_FOUND, _CONF_MISSING = 0.97, 0.0


class PruneMock:
    mode = "MOCK"
    model = "prune-mock-1"

    def complete(self, req):
        from modules.ai.gateway import LlmResponse

        fx = FIXTURES / req.prompt_id.replace("@", "_at_") / f"{req.input_hash}.json"
        if fx.exists():
            fixture = json.loads(fx.read_text())
            if fixture.get("_simulate") == "error":
                raise RuntimeError("MOCK: simulated gateway failure")
            out = fixture["output"]
        elif req.prompt_id.startswith("docintel.invoice_extract"):
            out = parse_invoice_text(prompts.extract_data_block(req.user))
        else:
            raise RuntimeError(f"MOCK has no fixture for {req.prompt_id}")
        return LlmResponse(ok=True, llm_mode=self.mode, model=self.model, output=out, raw_text=json.dumps(out))


_LABELS = {
    "invoice no": "invoice_no", "invoice number": "invoice_no", "invoice date": "invoice_date",
    "seller": "seller_name", "seller gstin": "seller_gstin", "buyer": "buyer_name", "buyer gstin": "buyer_gstin",
    "place of supply": "place_of_supply", "category": "category", "total": "total", "invoice total": "total",
    "tax total": "tax_total",
}
_ITEM = re.compile(r"^\s*\d+\s*\|\s*(?P<desc>[^|]+)\|\s*(?P<hsn>[^|]*)\|\s*(?P<amt>[\d,]+(?:\.\d+)?)\s*\|\s*"
                   r"(?P<rate>\d+(?:\.\d+)?)\s*%\s*(?:\|\s*(?P<cat>[a-z_]+))?\s*$")


def parse_invoice_text(text: str) -> dict:
    out: dict = {k: None for k in ("invoice_no", "invoice_date", "seller_name", "seller_gstin", "buyer_name",
                                    "buyer_gstin", "place_of_supply", "category", "tax_total", "total")}
    lines = []
    for raw in text.splitlines():
        m = _ITEM.match(raw)
        if m:
            lines.append({"description": m["desc"].strip(), "hsn_sac": (m["hsn"].strip() or None),
                          "taxable_value": m["amt"].replace(",", ""), "gst_rate_pct": m["rate"],
                          "category": m["cat"]})
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
    conf = {k: (_CONF_FOUND if out.get(k) else _CONF_MISSING)
            for k in ("invoice_no", "invoice_date", "seller_gstin", "buyer_gstin", "total")}
    conf["lines"] = _CONF_FOUND if lines else _CONF_MISSING
    out["confidence"] = conf
    return out
