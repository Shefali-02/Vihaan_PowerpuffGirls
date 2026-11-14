"""Trial balance and P&L from POSTED lines only."""
from __future__ import annotations

from sqlalchemy.orm import Session

from modules.ledger import repository as repo
from modules.ledger.money import format_inr


def trial_balance(s: Session, ws: str, period_id: str) -> dict:
    names = {a.code: (a.name, a.type) for a in repo.accounts(s, ws)}
    rows = []
    for code, dr, cr in repo.account_totals(s, ws, period_id):
        name, typ = names.get(code, (code, "UNKNOWN"))
        rows.append({"code": code, "name": name, "type": typ, "debit_paise": dr, "credit_paise": cr,
                     "balance_paise": dr - cr})
    tot_dr = sum(r["debit_paise"] for r in rows)
    tot_cr = sum(r["credit_paise"] for r in rows)
    return {"period_id": period_id, "rows": rows, "total_debit_paise": tot_dr, "total_credit_paise": tot_cr,
            "balanced": tot_dr == tot_cr}


def profit_and_loss(s: Session, ws: str, period_id: str) -> dict:
    tb = trial_balance(s, ws, period_id)
    income = [{"code": r["code"], "name": r["name"], "amount_paise": r["credit_paise"] - r["debit_paise"]}
              for r in tb["rows"] if r["type"] == "INCOME"]
    expenses = [{"code": r["code"], "name": r["name"], "amount_paise": r["debit_paise"] - r["credit_paise"]}
                for r in tb["rows"] if r["type"] == "EXPENSE"]
    ti = sum(i["amount_paise"] for i in income)
    te = sum(e["amount_paise"] for e in expenses)
    for row in income + expenses:
        row["amount"] = format_inr(row["amount_paise"])
    return {"period_id": period_id, "income": income, "expenses": expenses,
            "total_income_paise": ti, "total_expenses_paise": te, "net_profit_paise": ti - te,
            "total_income": format_inr(ti), "total_expenses": format_inr(te), "net_profit": format_inr(ti - te)}
