"""MOCK GST adapter. Prepares return-shaped JSON from ledger data; never contacts GSTN."""
from __future__ import annotations

import json

from core.canonical import canonical_json
from core.config import REPO_ROOT
from core.db import utcnow
from core.hashing import sha256_hex

GSTR2B_FIXTURE = REPO_ROOT / "seed" / "fixtures" / "gstr2b.json"


class MockGstAdapter:
    mode = "MOCK"

    def get_gstr2b(self, gstin: str, period: str) -> dict:
        data = json.loads(GSTR2B_FIXTURE.read_text()) if GSTR2B_FIXTURE.exists() else {"b2b": []}
        return {"mode": self.mode, "gstin": gstin, "period": period, **data,
                "note": "Canned data built from seed invoices; not fetched from GSTN."}

    def prepare_gstr1(self, gstin: str, period: str, summary: dict) -> dict:
        payload = {"mode": self.mode, "gstin": gstin, "period": period,
                   "outward_taxable_paise": summary["outward_taxable_paise"],
                   "output_cgst_paise": summary["output_cgst_paise"], "output_sgst_paise": summary["output_sgst_paise"],
                   "output_igst_paise": summary["output_igst_paise"]}
        return {**payload, "payload_hash": sha256_hex(canonical_json(payload)), "generated_at": utcnow().isoformat()}

    def prepare_gstr3b(self, gstin: str, period: str, summary: dict) -> dict:
        payload = {
            "mode": self.mode, "gstin": gstin, "period": period,
            "outward_taxable_paise": summary["outward_taxable_paise"],
            "output_cgst_paise": summary["output_cgst_paise"], "output_sgst_paise": summary["output_sgst_paise"],
            "output_igst_paise": summary["output_igst_paise"],
            "itc_cgst_paise": summary["itc_cgst_paise"], "itc_sgst_paise": summary["itc_sgst_paise"],
            "itc_igst_paise": summary["itc_igst_paise"], "net_payable_paise": summary["net_payable_paise"],
        }
        return {**payload, "payload_hash": sha256_hex(canonical_json(payload)), "generated_at": utcnow().isoformat()}

    def submit(self, return_type: str, payload: dict) -> dict:
        raise NotImplementedError("MVP: filing disabled")
