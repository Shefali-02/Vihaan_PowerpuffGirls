"""Loads effective-dated rulesets and tables from packages/rules (cached)."""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from core.config import REPO_ROOT

RULES_DIR = REPO_ROOT.joinpath("packages", "rules")  # joinpath: no "/" operator in rules (float check)


def _d(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _effective(item: dict, on: date) -> bool:
    start, end = _d(item.get("effective_from")), _d(item.get("effective_to"))
    return (start is None or start <= on) and (end is None or on < end)


@lru_cache
def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


@lru_cache
def _rulesets() -> tuple[dict, ...]:
    return tuple(_load(str(p)) for p in sorted(RULES_DIR.joinpath("rulesets").glob("*.yaml")))


def get_ruleset(doc_type: str, on: date) -> dict | None:
    matches = [r for r in _rulesets() if r["doc_type"] == doc_type and _effective(r, on)]
    if not matches:
        return None
    r = max(matches, key=lambda r: _d(r["effective_from"]))
    return {**r, "ruleset_version": f"{r['id']}@{r['version']}"}


def gst_table() -> dict:
    return _load(str(RULES_DIR.joinpath("tables", "gst_rates.yaml")))


def get_slabs_bp(on: date) -> list[int]:
    for s in gst_table()["slab_sets"]:
        if _effective(s, on):
            return list(s["slabs_bp"])
    return []


def get_gst_rate(hsn_sac: str | None, on: date) -> int | None:
    """Longest-prefix HSN/SAC match effective on the date; None when unknown."""
    if not hsn_sac:
        return None
    best: tuple[int, int] | None = None
    for row in gst_table()["rates"]:
        code = str(row["hsn_sac"])
        if hsn_sac.startswith(code) and _effective(row, on):
            if best is None or len(code) > best[0]:
                best = (len(code), int(row["rate_bp"]))
    return best[1] if best else None


def blocked_credits() -> dict[str, str]:
    return _load(str(RULES_DIR.joinpath("tables", "blocked_credits.yaml")))["blocked_categories"]


def chart_of_accounts() -> list[dict]:
    return _load(str(RULES_DIR.joinpath("tables", "chart_of_accounts.yaml")))["accounts"]


def tables_version() -> str:
    return gst_table()["version"]


def clear_cache() -> None:
    _load.cache_clear()
    _rulesets.cache_clear()
