#!/usr/bin/env python3
"""HTTP-only end-to-end dry run of the golden path. Prints PASS/FAIL per step; exits non-zero on failure.

  python scripts/dryrun.py [--base-url http://localhost:8000] [--no-reset]

By default the database is re-seeded first (`python -m seed.seed --reset` with the current env), which makes the
run repeatable: the golden path locks the period, so a second run on the same data cannot close it again.
Use --no-reset when the API's database is not reachable from here (e.g. Docker: reset inside the container).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
PURCHASE = ROOT / "seed" / "invoices" / "01_purchase_intra_18.txt"
SALE = ROOT / "seed" / "invoices" / "07_sale_intra.txt"


class Run:
    def __init__(self, base: str):
        self.c = httpx.Client(base_url=base, timeout=60)
        self.results: list[tuple[str, bool, str]] = []
        self.ctx: dict = {}

    def step(self, name: str, fn):
        try:
            detail = fn() or ""
            self.results.append((name, True, str(detail)))
            print(f"PASS  {name}  {detail}")
            return True
        except Exception as e:  # report and stop: later steps depend on earlier ones
            self.results.append((name, False, str(e)))
            print(f"FAIL  {name}  {e}")
            return False

    def login(self, email):
        r = self.c.post("/v1/auth/login", json={"email": email, "password": "demo1234"})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("MUNSHI_BASE_URL", "http://localhost:8000"))
    ap.add_argument("--no-reset", action="store_true", help="do not re-seed the database first")
    args = ap.parse_args()
    if not args.no_reset:
        subprocess.run([sys.executable, "-m", "seed.seed", "--reset"], cwd=ROOT, check=True)

    r = Run(args.base_url)
    x = r.ctx

    def health():
        h = r.c.get("/healthz").json()
        x["llm_mode"], x["anchor_mode"] = h["llm_mode"], h["anchor_mode"]
        expect(h["status"] == "ok", h)
        return f"llm_mode={h['llm_mode']} anchor_mode={h['anchor_mode']} db={h['db']}"

    def login_acc():
        x["acc"] = r.login("accountant@acme.demo")

    def upload(path, key):
        def _do():
            with open(path, "rb") as f:
                res = r.c.post("/v1/documents", headers={**x["acc"], "Idempotency-Key": f"dryrun-{key}"},
                               files={"file": (path.name, f, "text/plain")})
            expect(res.status_code == 201, res.text)
            d = res.json()
            expect(d["status"] in ("DRAFT_AI", "NEEDS_REVIEW"), f"status {d['status']}: {d['proposal']['reasons']}")
            x[key] = d["proposal"]["draft_entry_id"]
            return f"{d['status']} llm_mode={d['proposal']['llm_mode']}"
        return _do

    def draft():
        for key in ("purchase", "sale"):
            j = r.c.get(f"/v1/journals/{x[key]}", headers=x["acc"]).json()
            dr = sum(ln["debit_paise"] for ln in j["lines"])
            expect(j["status"] == "DRAFT", f"entry already {j['status']} from an earlier run: re-seed (omit --no-reset)")
            expect(dr == sum(ln["credit_paise"] for ln in j["lines"]), "draft not balanced")
            x["period_id"] = j["period_id"]
        return "both drafts balanced"

    def post():
        for key in ("purchase", "sale"):
            res = r.c.post(f"/v1/journals/{x[key]}/post", headers=x["acc"])
            expect(res.status_code == 200 and res.json()["status"] == "POSTED", res.text)

    def pnl_gst():
        p = r.c.get(f"/v1/reports/pnl?period_id={x['period_id']}", headers=x["acc"]).json()
        g = r.c.get(f"/v1/tax/gst/summary?period={x['period_id']}", headers=x["acc"]).json()
        expect(p["net_profit_paise"] == 4_000_000, p)
        expect(g["net_payable_paise"] == 720_000 and g["mode"] == "MOCK", g)
        return f"net profit {p['net_profit']}, net GST payable {g['net_payable']}"

    def request_approval():
        res = r.c.post("/v1/approvals", headers=x["acc"],
                       json={"object_type": "period_close", "object_id": x["period_id"]})
        expect(res.status_code == 201, res.text)
        x["approval"] = res.json()["id"]
        return f"version_hash {res.json()['version_hash'][:16]}..."

    def login_ca():
        x["ca"] = r.login("ca@ca-firm.demo")

    def approve():
        res = r.c.post(f"/v1/approvals/{x['approval']}/approve", headers=x["ca"], json={"note": "dry run"})
        expect(res.status_code == 200, res.text)
        st = res.json()["state"]
        expect(st in ("LOCKED", "ANCHORED"), st)
        return f"state={st}"

    def anchor_run():
        res = r.c.post("/v1/admin/anchor/run", headers=x["ca"])
        expect(res.status_code == 200, res.text)
        b = res.json()["batches"]
        return f"{len(b)} batch(es)" + (f", tx {b[0]['anchor']['tx_hash'][:18]}..." if b else "")

    def publish():
        res = r.c.post("/v1/reports/pack", headers=x["acc"], json={"period_id": x["period_id"]})
        expect(res.status_code == 201, res.text)
        p = res.json()
        x["report_id"], x["sha"] = p["report_id"], p["sha256"]
        return f"sha256 {p['sha256'][:16]}... anchor {p['anchor']['mode'] if p['anchor'] else 'existing'}"

    def download():
        res = r.c.get(f"/v1/reports/{x['report_id']}/pdf", headers=x["acc"])
        expect(res.status_code == 200 and res.content[:4] == b"%PDF", res.status_code)
        x["pdf"] = res.content
        return f"{len(res.content)} bytes"

    def verify_match():
        v = r.c.post("/public/verify/upload", files={"file": ("pack.pdf", x["pdf"], "application/pdf")}).json()
        expect(v["verdict"] == "MATCH", v)
        h = r.c.get(f"/public/verify?hash={x['sha']}").json()
        expect(h["verdict"] == "MATCH", h)
        return f"MATCH via {v['anchor']['mode']} (tx {v['anchor']['tx'][:18]}...)"

    def verify_tampered():
        b = bytearray(x["pdf"])
        b[len(b) // 2] ^= 0x01
        v = r.c.post("/public/verify/upload", files={"file": ("pack.pdf", bytes(b), "application/pdf")}).json()
        expect(v["verdict"] == "NO MATCH", v)
        return "NO MATCH (1 byte flipped)"

    def trust_status():
        s = r.c.get("/v1/trust/status", headers=x["ca"]).json()
        expect(s["chain_valid"], s)
        return f"chain length {s['chain_length']} valid, anchor_mode={s['anchor_mode']}"

    steps = [
        ("health", health), ("login accountant", login_acc),
        ("upload purchase invoice", upload(PURCHASE, "purchase")), ("upload sale invoice", upload(SALE, "sale")),
        ("draft journals", draft), ("post journals", post), ("P&L and GST", pnl_gst),
        ("request period-close approval", request_approval), ("login CA", login_ca), ("CA approves", approve),
        ("anchor run", anchor_run), ("publish investor pack", publish), ("download PDF", download),
        ("verify original", verify_match), ("verify tampered", verify_tampered), ("trust status", trust_status),
    ]
    for name, fn in steps:
        if not r.step(name, fn):
            break
    ok = all(res[1] for res in r.results) and len(r.results) == len(steps)
    print(f"\nllm_mode={x.get('llm_mode')} anchor_mode={x.get('anchor_mode')}")
    print("DRY RUN:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
