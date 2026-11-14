"""Seed the chart of accounts for a workspace from packages/rules/tables/chart_of_accounts.yaml."""
from __future__ import annotations

from sqlalchemy.orm import Session

from modules.ledger import repository as repo
from modules.ledger.models import Account
from modules.rules import service as rules


def seed_chart(s: Session, workspace_id: str) -> int:
    existing = {a.code for a in repo.accounts(s, workspace_id)}
    added = 0
    for a in rules.chart_of_accounts():
        if a["code"] not in existing:
            s.add(Account(workspace_id=workspace_id, code=a["code"], name=a["name"], type=a["type"],
                          tax_tag=a.get("tax_tag")))
            added += 1
    s.flush()
    return added
