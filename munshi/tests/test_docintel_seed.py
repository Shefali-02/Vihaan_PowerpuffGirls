"""Every seed invoice lands in its expected status (P3 check)."""
from __future__ import annotations

import json

from tests.conftest import INVOICES, upload


def test_seed_invoices_route_as_expected(client, acc):
    expected = json.loads((INVOICES / "EXPECTED.json").read_text())
    for name, status in expected.items():  # order matters: 05 duplicates 01
        doc = upload(client, acc, name)
        assert doc["status"] == status, (name, doc["proposal"])
        assert doc["proposal"]["llm_mode"] == "MOCK"
        if status == "DRAFT_AI":
            j = client.get(f"/v1/journals/{doc['proposal']['draft_entry_id']}", headers=acc).json()
            assert sum(ln["debit_paise"] for ln in j["lines"]) == sum(ln["credit_paise"] for ln in j["lines"])
    review = client.get("/v1/proposals?status=NEEDS_REVIEW", headers=acc).json()["items"]
    assert len(review) == list(expected.values()).count("NEEDS_REVIEW")


def test_exact_same_file_is_duplicate(client, acc):
    upload(client, acc, "02_purchase_inter_igst.txt")
    assert upload(client, acc, "02_purchase_inter_igst.txt")["status"] == "DUPLICATE"


def test_ai_runs_are_recorded_without_raw_text(client, acc, db):
    from sqlalchemy import select

    from modules.ai.models import AiRun

    upload(client, acc, "01_purchase_intra_18.txt")
    run = db.scalar(select(AiRun))
    assert run.llm_mode == "MOCK" and run.status == "OK" and len(run.input_hash) == 64
    assert run.redactions.get("[PHONE]") == 1


def test_unsupported_file_type(client, acc):
    r = client.post("/v1/documents", headers=acc, files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415 and r.json()["code"] == "UNSUPPORTED_DOCUMENT"
