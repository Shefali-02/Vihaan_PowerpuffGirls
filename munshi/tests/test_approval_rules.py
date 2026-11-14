"""Maker-checker rules: no self-approval, CA-only for high risk, stale version hash -> 409."""
from __future__ import annotations

from tests.conftest import auth, upload_and_post


def _period_id(client, h):
    return client.get("/v1/periods", headers=h).json()[0]["id"]


def test_self_approval_blocked(client, acc):
    j = upload_and_post(client, acc, "03_purchase_5pct.txt")
    a = client.post("/v1/approvals", headers=acc, json={"object_type": "journal", "object_id": j["id"]}).json()
    assert a["risk"] == "LOW"
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=acc)
    assert r.status_code == 403 and r.json()["code"] == "SELF_APPROVAL_FORBIDDEN"


def test_accountant_can_approve_low_risk_journal_of_someone_else(client, acc, acc2):
    j = upload_and_post(client, acc, "03_purchase_5pct.txt")
    a = client.post("/v1/approvals", headers=acc, json={"object_type": "journal", "object_id": j["id"]}).json()
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=acc2)
    assert r.status_code == 200 and r.json()["state"] == "APPROVED"


def test_accountant_blocked_on_high_risk(client, acc, acc2):
    upload_and_post(client, acc, "01_purchase_intra_18.txt")
    a = client.post("/v1/approvals", headers=acc,
                    json={"object_type": "period_close", "object_id": _period_id(client, acc)}).json()
    assert a["risk"] == "HIGH"
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=acc2)
    assert r.status_code == 403 and r.json()["code"] == "ROLE_NOT_PERMITTED"


def test_investor_is_read_only(client, acc):
    inv = auth(client, "investor@acme.demo")
    upload_and_post(client, acc, "01_purchase_intra_18.txt")
    a = client.post("/v1/approvals", headers=acc,
                    json={"object_type": "period_close", "object_id": _period_id(client, acc)}).json()
    assert client.post(f"/v1/approvals/{a['id']}/approve", headers=inv).status_code == 403
    assert client.post("/v1/approvals", headers=inv,
                       json={"object_type": "period_close", "object_id": _period_id(client, acc)}).status_code == 403


def test_stale_version_hash_returns_409(client, acc, ca):
    upload_and_post(client, acc, "01_purchase_intra_18.txt")
    pid = _period_id(client, acc)
    a = client.post("/v1/approvals", headers=acc, json={"object_type": "period_close", "object_id": pid}).json()
    upload_and_post(client, acc, "02_purchase_inter_igst.txt")  # trial balance changes after the request
    listed = client.get("/v1/approvals?state=IN_REVIEW", headers=ca).json()["items"][0]
    assert listed["stale"] is True and listed["diff"]
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=ca)
    assert r.status_code == 409 and r.json()["code"] == "VERSION_HASH_MISMATCH"


def test_period_close_approval_locks_and_anchors(client, acc, ca):
    upload_and_post(client, acc, "01_purchase_intra_18.txt")
    pid = _period_id(client, acc)
    a = client.post("/v1/approvals", headers=acc, json={"object_type": "period_close", "object_id": pid}).json()
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=ca, json={"note": "Reviewed TB"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "ANCHORED" and body["anchor_batch"]["anchor"]["mode"] == "MOCK"
    period = client.get("/v1/periods", headers=acc).json()[0]
    assert period["status"] == "LOCKED"
    r = client.post("/v1/journals/draft", headers=acc, json={
        "doc_type": "purchase_invoice", "invoice_no": "LATE-1", "invoice_date": "2026-10-11",
        "counterparty_gstin": "07AAFCS4321K1ZC",
        "lines": [{"taxable_paise": 1000, "gst_rate_bp": 1800}]})
    assert r.status_code == 409 and r.json()["code"] == "PERIOD_LOCKED"


def test_request_changes_then_cannot_approve_same_request(client, acc, ca):
    upload_and_post(client, acc, "01_purchase_intra_18.txt")
    a = client.post("/v1/approvals", headers=acc,
                    json={"object_type": "period_close", "object_id": _period_id(client, acc)}).json()
    r = client.post(f"/v1/approvals/{a['id']}/request-changes", headers=ca, json={"note": "Attach bank recon"})
    assert r.json()["state"] == "CHANGES_REQUESTED"
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=ca)
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATE_TRANSITION"


def test_period_close_blocked_with_unposted_drafts(client, acc, ca):
    from tests.conftest import upload

    upload(client, acc, "01_purchase_intra_18.txt")  # draft only
    a = client.post("/v1/approvals", headers=acc,
                    json={"object_type": "period_close", "object_id": _period_id(client, acc)}).json()
    r = client.post(f"/v1/approvals/{a['id']}/approve", headers=ca)
    assert r.status_code == 409 and r.json()["code"] == "INVALID_STATE_TRANSITION"
