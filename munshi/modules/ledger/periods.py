"""Indian financial year (1 April - 31 March) helpers."""
from __future__ import annotations

from datetime import date

from core.errors import PeriodLocked, PeriodNotFound


def fy_bounds(on: date) -> tuple[date, date]:
    start_year = on.year if on.month >= 4 else on.year - 1
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def fy_name(on: date) -> str:
    start, _ = fy_bounds(on)
    return f"FY{start.year}-{str(start.year + 1)[-2:]}"


def assert_open(period, on: date | None = None) -> None:
    if period is None:
        raise PeriodNotFound(f"No accounting period covers {on}")
    if period.status != "OPEN":
        raise PeriodLocked(f"Period {period.name} is locked")
