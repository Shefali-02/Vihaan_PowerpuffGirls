from __future__ import annotations

from pydantic import BaseModel


class PackRequest(BaseModel):
    period_id: str


class AnchorInfo(BaseModel):
    mode: str
    tx_hash: str | None = None
    block: int | None = None
    chain_id: int | None = None
    contract: str | None = None


class PackOut(BaseModel):
    report_id: str
    sha256: str
    filename: str
    qr_payload: str
    qr_png_base64: str
    proof_url: str
    pdf_url: str
    anchor: AnchorInfo | None
    sources: dict


class ProofOut(BaseModel):
    format: str
    report_id: str
    report_sha256: str
    event_seq: int
    salt: str
    canonical_event: str
    leaf_hash: str | None
    ws_chain_id: str
    status: str
    leaf_rule: str
    node_rule: str
    note: str
    merkle_path: list[dict] | None = None
    root: str | None = None
    batch_seq: int | None = None
    anchor: dict | None = None


class Signoff(BaseModel):
    name: str
    role: str
    time: str
    object: str | None = None
    version_hash: str | None = None


class VerifyAnchor(BaseModel):
    tx: str | None
    block: int | None
    chain: int | None
    contract: str | None
    mode: str
    batch_seq: int | None = None
    root: str | None = None


class VerifyOut(BaseModel):
    verdict: str  # MATCH | NO MATCH | PENDING
    hash: str
    reasons: list[str]
    anchor: VerifyAnchor | None
    signoffs: list[Signoff]
    report: dict | None


class GstSummaryOut(BaseModel):
    period: dict
    outward_taxable_paise: int
    inward_taxable_paise: int
    output_cgst_paise: int
    output_sgst_paise: int
    output_igst_paise: int
    itc_cgst_paise: int
    itc_sgst_paise: int
    itc_igst_paise: int
    itc_ineligible_paise: int
    net_payable_cgst_paise: int
    net_payable_sgst_paise: int
    net_payable_igst_paise: int
    net_payable_paise: int
    net_payable: str
    itc_carry_forward_paise: dict
    mode: str
    disclaimer: str
    gstr3b_preview: dict | None = None


class TrustStatusOut(BaseModel):
    chain_length: int
    chain_valid: bool
    first_broken_seq: int | None
    head_hash: str | None
    anchor_mode: str
    last_anchor: dict | None


class AnchorRunOut(BaseModel):
    batches: list[dict]


class IntegrationsOut(BaseModel):
    items: list[dict]
    notice: str


class HealthOut(BaseModel):
    status: str
    db: str
    llm_mode: str
    anchor_mode: str
    anchor_mode_configured: str
    version: str
