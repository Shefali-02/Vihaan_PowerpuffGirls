"""Sync the YAML GST rate table into the gst_rates DB table (for audit/reporting queries)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.rules import service as rules
from modules.tax.models import GstRate

GLOBAL = "*"


def sync_from_yaml(s: Session) -> int:
    version = rules.tables_version()
    existing = {(r.hsn_sac, r.effective_from) for r in s.scalars(select(GstRate).where(GstRate.workspace_id == GLOBAL))}
    added = 0
    for row in rules.gst_rate_rows():
        eff = row["effective_from"] if isinstance(row["effective_from"], date) else date.fromisoformat(str(row["effective_from"]))
        key = (str(row["hsn_sac"]), eff)
        if key in existing:
            continue
        s.add(GstRate(workspace_id=GLOBAL, hsn_sac=key[0], rate_bp=int(row["rate_bp"]), effective_from=eff,
                      effective_to=row.get("effective_to"), description=row.get("description", ""),
                      source_version=version))
        added += 1
    s.flush()
    return added


def list_rates(s: Session) -> list[dict]:
    return [{"hsn_sac": r.hsn_sac, "rate_bp": r.rate_bp, "effective_from": r.effective_from.isoformat(),
             "description": r.description}
            for r in s.scalars(select(GstRate).where(GstRate.workspace_id == GLOBAL).order_by(GstRate.hsn_sac))]
