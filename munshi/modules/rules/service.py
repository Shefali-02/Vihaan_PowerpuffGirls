"""Public face of the rules module for other modules."""
from __future__ import annotations

from modules.rules import loader
from modules.rules.engine import build_journal
from modules.rules.explain import explain
from modules.rules.gstin import gstin_errors, is_valid_gstin, is_valid_pan, make_gstin
from modules.rules.models import DraftJournal, InvoiceFacts, InvoiceLineFacts, Rejection, TaxContext

__all__ = [
    "DraftJournal", "InvoiceFacts", "InvoiceLineFacts", "Rejection", "TaxContext",
    "build_journal", "explain", "gstin_errors", "is_valid_gstin", "is_valid_pan", "make_gstin",
    "chart_of_accounts", "gst_rate_rows",
]


def chart_of_accounts() -> list[dict]:
    return loader.chart_of_accounts()


def gst_rate_rows() -> list[dict]:
    return list(loader.gst_table()["rates"])


def tables_version() -> str:
    return loader.tables_version()
