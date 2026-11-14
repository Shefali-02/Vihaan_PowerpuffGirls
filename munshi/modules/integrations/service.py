from __future__ import annotations

from modules.integrations import registry

CLAIM = ("All integrations are MOCK. Munshi is not integrated with or approved by GSTN, CBDT, MCA, EPFO, RBI "
         "or any government body, and does not file returns.")


def gst_port():
    return registry.get_port("GST")


def list_integrations() -> dict:
    return {"items": registry.catalogue(), "notice": CLAIM}
