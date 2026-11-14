"""Definition of done, over HTTP: upload -> post -> approve close -> publish -> verify MATCH (mock anchor)."""
from __future__ import annotations

from tests.conftest import upload_and_post


def test_golden_path_ends_in_match(client, acc, ca):
    p1 = upload_and_post(client, acc, "01_purchase_intra_18.txt")
    upload_and_post(client, acc, "07_sale_intra.txt")
    pid = p1["period_id"]

    pnl = client.get(f"/v1/reports/pnl?period_id={pid}", headers=acc).json()
    assert pnl["net_profit_paise"] == 4_000_000  # 50,000 sales - 10,000 stationery
    gst = client.get(f"/v1/tax/gst/summary?period={pid}", headers=acc).json()
    assert gst["net_payable_paise"] == 720_000 and gst["gstr3b_preview"]["mode"] == "MOCK"

    # pack before approval is refused
    r = client.post("/v1/reports/pack", headers=acc, json={"period_id": pid})
    assert r.status_code == 409 and r.json()["code"] == "PERIOD_CLOSE_NOT_APPROVED"

    a = client.post("/v1/approvals", headers=acc, json={"object_type": "period_close", "object_id": pid}).json()
    approved = client.post(f"/v1/approvals/{a['id']}/approve", headers=ca).json()
    assert approved["state"] == "ANCHORED"

    pack = client.post("/v1/reports/pack", headers=acc, json={"period_id": pid}).json()
    pdf = client.get(f"/v1/reports/{pack['report_id']}/pdf", headers=acc).content
    assert pdf.startswith(b"%PDF")

    v = client.post("/public/verify/upload", files={"file": ("p.pdf", pdf, "application/pdf")}).json()
    assert v["verdict"] == "MATCH", v
    assert v["anchor"]["mode"] == "MOCK"
    assert v["signoffs"][0]["role"] == "CA" and "DEMO-000000" in v["signoffs"][0]["name"]
    assert "paise" not in str(v) and "Sharma" not in str(v)  # no amounts or counterparty names leak

    proof = client.get(f"/v1/reports/{pack['report_id']}/proof", headers=acc).json()
    assert proof["status"] == "ANCHORED" and proof["report_sha256"] == pack["sha256"]

    status = client.get("/v1/trust/status", headers=ca).json()
    assert status["chain_valid"] and status["last_anchor"]


def test_openapi_lists_every_frozen_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/v1/documents", "/v1/journals/draft", "/v1/journals/{entry_id}/post",
              "/v1/approvals/{approval_id}/approve", "/v1/reports/pnl", "/v1/reports/pack", "/public/verify",
              "/public/verify/upload", "/v1/auth/login", "/v1/auth/me", "/v1/documents/{doc_id}", "/v1/proposals",
              "/v1/journals/{entry_id}", "/v1/approvals", "/v1/approvals/{approval_id}/request-changes",
              "/v1/periods", "/v1/tax/gst/summary", "/v1/reports/{report_id}/proof", "/v1/reports/{report_id}/pdf",
              "/v1/trust/status", "/v1/admin/anchor/run", "/v1/integrations", "/healthz"]:
        assert p in paths, p


def test_integrations_are_mock_and_live_is_disabled(client, acc):
    import pytest

    from core.errors import NotEnabledError
    from modules.integrations import registry

    items = client.get("/v1/integrations", headers=acc).json()["items"]
    assert all(i["mode"] == "MOCK" and not i["live_available"] for i in items)
    with pytest.raises(NotEnabledError):
        registry.get_port("GST", "LIVE")
    with pytest.raises(NotImplementedError, match="filing disabled"):
        registry.get_port("GST").submit("GSTR3B", {})
