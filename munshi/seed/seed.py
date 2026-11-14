"""Idempotent demo seed.  python -m seed.seed [--reset]

Workspace "Acme Pvt Ltd" (Delhi, state 07) with a checksum-valid GSTIN, the Indian SME chart of accounts,
the current FY period (OPEN), GST rate rows, MOCK integration rows and demo users:
  accountant@acme.demo / demo1234   (ACCOUNTANT)
  ca@ca-firm.demo      / demo1234   (CA, reg no DEMO-000000 - captured for display only, never verified)
  investor@acme.demo   / demo1234   (INVESTOR, read-only)
"""
from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import select

from core.db import create_all, drop_all, session_scope
from core.security import hash_password
from modules.identity.models import Membership, User, Workspace
from modules.integrations.models import IntegrationConnection
from modules.ledger import service as ledger
from modules.rules.service import make_gstin
from modules.tax import tax_tables

PASSWORD = "demo1234"
SAMPLE_INVOICE_DATE = date(2026, 10, 1)  # seed/invoices are dated in FY2026-27
WORKSPACE = {"name": "Acme Pvt Ltd", "state_code": "07", "pan": "AAACA1234C"}
USERS = [
    ("accountant@acme.demo", "Asha Accountant", "ACCOUNTANT", None),
    ("ca@ca-firm.demo", "CA Demo", "CA", "DEMO-000000"),
    ("investor@acme.demo", "Ishaan Investor", "INVESTOR", None),
]


def seed(reset: bool = False, today: date | None = None) -> dict:
    if reset:
        drop_all()
    create_all()
    with session_scope() as s:
        ws = s.scalar(select(Workspace).where(Workspace.name == WORKSPACE["name"]))
        if ws is None:
            ws = Workspace(name=WORKSPACE["name"], state_code=WORKSPACE["state_code"], pan=WORKSPACE["pan"],
                           gstin=make_gstin(WORKSPACE["state_code"], WORKSPACE["pan"]))
            s.add(ws)
            s.flush()
        for email, name, role, reg in USERS:
            u = s.scalar(select(User).where(User.email == email))
            if u is None:
                u = User(email=email, name=name, password_hash=hash_password(PASSWORD), ca_reg_no=reg)
                s.add(u)
                s.flush()
            if s.scalar(select(Membership).where(Membership.workspace_id == ws.id, Membership.user_id == u.id)) is None:
                s.add(Membership(workspace_id=ws.id, user_id=u.id, role=role))
        ledger.seed_chart(s, ws.id)
        period = ledger.ensure_fy_period(s, ws.id, today or date.today())
        ledger.ensure_fy_period(s, ws.id, SAMPLE_INVOICE_DATE)  # same FY today; keeps samples usable later
        tax_tables.sync_from_yaml(s)
        for provider in ("GST", "ITD", "MCA", "EPFO", "NSWS", "AA"):
            if s.scalar(select(IntegrationConnection).where(IntegrationConnection.workspace_id == ws.id,
                                                            IntegrationConnection.provider == provider)) is None:
                s.add(IntegrationConnection(workspace_id=ws.id, provider=provider, mode="MOCK"))
        return {"workspace_id": ws.id, "gstin": ws.gstin, "period": period.name, "period_id": period.id}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = ap.parse_args()
    info = seed(reset=args.reset)
    print(f"Seeded {WORKSPACE['name']} GSTIN {info['gstin']} period {info['period']}")
    for email, _, role, _ in USERS:
        print(f"  {role:<10} {email} / {PASSWORD}")


if __name__ == "__main__":
    main()
