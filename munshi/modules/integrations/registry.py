"""Adapter registry. Only MOCK adapters exist; LIVE raises NotEnabledError."""
from __future__ import annotations

from core.errors import NotEnabledError
from modules.integrations.mock_aa import MockAaAdapter
from modules.integrations.mock_epfo import MockEpfoAdapter
from modules.integrations.mock_gst import MockGstAdapter
from modules.integrations.mock_itd import MockItdAdapter
from modules.integrations.mock_mca import MockMcaAdapter
from modules.integrations.mock_nsws import MockNswsAdapter

PROVIDERS = {
    "GST": {"adapter": MockGstAdapter, "built": ["get_gstr2b", "prepare_gstr1", "prepare_gstr3b"],
            "disabled": ["submit"], "description": "GST returns (prepared from ledger; filing disabled)"},
    "ITD": {"adapter": MockItdAdapter, "built": [], "disabled": [], "description": "Income-tax data / TDS (designed)"},
    "MCA": {"adapter": MockMcaAdapter, "built": [], "disabled": [], "description": "Company filings (designed)"},
    "EPFO": {"adapter": MockEpfoAdapter, "built": [], "disabled": [], "description": "Provident fund ECR (designed)"},
    "NSWS": {"adapter": MockNswsAdapter, "built": [], "disabled": [], "description": "Registrations (designed)"},
    "AA": {"adapter": MockAaAdapter, "built": [], "disabled": [],
           "description": "Account Aggregator bank data (designed)"},
}


def get_port(provider: str, mode: str = "MOCK"):
    if provider not in PROVIDERS:
        raise KeyError(provider)
    if mode.upper() != "MOCK":
        raise NotEnabledError(f"LIVE {provider} integration is not enabled in this MVP")
    return PROVIDERS[provider]["adapter"]()


def catalogue() -> list[dict]:
    return [{"provider": k, "mode": "MOCK", "live_available": False, "description": v["description"],
             "capabilities_built": v["built"], "capabilities_disabled": v["disabled"],
             "status": "MOCK" if v["built"] else "DESIGNED_NOT_BUILT"} for k, v in PROVIDERS.items()]
