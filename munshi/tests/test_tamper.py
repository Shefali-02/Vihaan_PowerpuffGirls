"""Tamper evidence: one flipped byte -> NO MATCH; tampered proof or anchor -> NO MATCH; PDF is deterministic."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from scripts import verify_cli
from scripts.demo_tamper import flip_one_byte
from tests.conftest import upload_and_post


@pytest.fixture
def published(client, acc, ca):
    p = upload_and_post(client, acc, "01_purchase_intra_18.txt")
    a = client.post("/v1/approvals", headers=acc,
                    json={"object_type": "period_close", "object_id": p["period_id"]}).json()
    client.post(f"/v1/approvals/{a['id']}/approve", headers=ca)
    pack = client.post("/v1/reports/pack", headers=acc, json={"period_id": p["period_id"]}).json()
    pdf = client.get(f"/v1/reports/{pack['report_id']}/pdf", headers=acc).content
    proof = client.get(f"/v1/reports/{pack['report_id']}/proof", headers=acc).json()
    return {"pack": pack, "pdf": pdf, "proof": proof, "period_id": p["period_id"]}


def verify(client, data: bytes) -> dict:
    return client.post("/public/verify/upload", files={"file": ("x.pdf", data, "application/pdf")}).json()


def test_original_matches_and_one_byte_does_not(client, published):
    assert verify(client, published["pdf"])["verdict"] == "MATCH"
    for offset in (0, len(published["pdf"]) // 2, len(published["pdf"]) - 1):
        v = verify(client, flip_one_byte(published["pdf"], offset))
        assert v["verdict"] == "NO MATCH" and v["signoffs"] == []


def test_unknown_or_malformed_hash_is_no_match(client, seeded):
    assert client.get("/public/verify?hash=" + "ab" * 32).json()["verdict"] == "NO MATCH"
    assert client.get("/public/verify?hash=nothex").json()["verdict"] == "NO MATCH"


def test_tampered_anchor_root_is_detected(client, published, db):
    db.execute(text("UPDATE mock_anchors SET root = :r"), {"r": "00" * 31 + "01"})
    db.commit()
    v = verify(client, published["pdf"])
    assert v["verdict"] == "NO MATCH" and "root" in " ".join(v["reasons"]).lower()


def test_pdf_is_deterministic(client, acc, published, db):
    from modules.reporting import pack_pdf, service

    pack = service.build_pack_json(db, published["proof"]["canonical_event"] and
                                   json.loads(published["proof"]["canonical_event"])["ws"], published["period_id"])
    a, b = pack_pdf.build(pack, "http://x/verify"), pack_pdf.build(pack, "http://x/verify")
    assert a == b
    again = client.post("/v1/reports/pack", headers=acc, json={"period_id": published["period_id"]}).json()
    assert again["sha256"] == published["pack"]["sha256"]


def test_independent_cli_verifier(tmp_path, published):
    pdf, proof = tmp_path / "p.pdf", tmp_path / "proof.json"
    pdf.write_bytes(published["pdf"])
    proof.write_text(json.dumps(published["proof"]))
    assert verify_cli.main([str(pdf), str(proof)]) == 0
    pdf.write_bytes(flip_one_byte(published["pdf"]))
    assert verify_cli.main([str(pdf), str(proof)]) == 1
    forged = dict(published["proof"], merkle_path=[{"sibling": "11" * 32, "position": "left"}])
    pdf.write_bytes(published["pdf"])
    proof.write_text(json.dumps(forged))
    assert verify_cli.main([str(pdf), str(proof)]) == 1
