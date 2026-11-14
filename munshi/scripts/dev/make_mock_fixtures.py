"""Regenerate MOCK LLM fixtures for seed invoices: seed/fixtures/ai/<prompt>/<input_hash>.json.

The input hash is computed exactly as the gateway does (redact -> render -> sha256), so fixtures are found
by (prompt_id, input_hash). 10_gateway_failure gets a fixture that simulates a gateway outage.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.hashing import sha256_hex
from modules.ai import prompts, redaction
from modules.ai.prune_mock import FIXTURES, parse_invoice_text

ROOT = Path(__file__).resolve().parents[2]
PROMPT_ID = "docintel.invoice_extract@1"

if __name__ == "__main__":
    prompt = prompts.get(PROMPT_ID)
    outdir = FIXTURES / PROMPT_ID.replace("@", "_at_")
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*.json"):
        old.unlink()
    for f in sorted((ROOT / "seed" / "invoices").glob("*.txt")):
        red, _ = redaction.redact(f.read_text())
        user = prompts.render(prompt, red)
        h = sha256_hex(user.encode())
        if "gateway_failure" in f.name:
            fixture = {"source": f.name, "_simulate": "error"}
        else:
            fixture = {"source": f.name, "output": parse_invoice_text(prompts.extract_data_block(user))}
        (outdir / f"{h}.json").write_text(json.dumps(fixture, indent=2) + "\n")
        print(f.name, h[:12])
