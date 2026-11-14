# Munshi backend

AI-assisted Indian accounting with CA approval and tamper-evident investor reports.

The golden path: upload an invoice → the LLM (through one gateway) extracts fields → a deterministic rules engine drafts a balanced GST journal → the accountant posts it → P&L and GST summary → a CA (a different user) approves the period close → every step lands in a hash-chained audit log → Merkle roots are anchored on a local Hardhat chain (or a clearly labelled MOCK) → an investor PDF is published → anyone can verify it: the original gives **MATCH**, one changed byte gives **NO MATCH**.

> Demo rates pending CA validation; not legal/tax advice. Sign-off is workflow evidence, not a statutory audit. All government integrations are MOCK.

## Quickstart

### Option A: Docker (Postgres + Hardhat + API)
```bash
make up            # db, hardhat node, one-shot contract deploy, API on :8000 (seeds itself)
make dryrun        # re-seeds inside the container, then runs the HTTP dry run from your machine
open http://localhost:8000/docs
```

### Option B: local, no Docker
```bash
make install                         # pip + npm
cd chain && npx hardhat node &       # terminal 1 (optional: skip it and the API anchors in MOCK mode)
make chain-deploy                    # writes chain/deployments/local.json
make api                             # seeds SQLite ./munshi.db, runs uvicorn on :8000
make dryrun-local                    # re-seeds the same DB and runs every golden-path step over HTTP
make test                            # provider-SDK check + pytest
```
Contract compilation uses the bundled `solc` npm package when `SOLC_OFFLINE=1` (the Makefile and Dockerfile set it), so no compiler download is needed.

### Demo logins (password `demo1234`)
| Role | Email | Notes |
|---|---|---|
| ACCOUNTANT | `accountant@acme.demo` | uploads, drafts, posts, requests approvals |
| CA | `ca@ca-firm.demo` | reg no `DEMO-000000` (captured for display only, never verified) |
| INVESTOR | `investor@acme.demo` | read-only |

Workspace: **Acme Pvt Ltd**, Delhi (state 07), GSTIN `07AAACA1234C1ZI` (checksum-valid demo value), period FY2026-27.

### Seed invoices (`seed/invoices/`, expected outcomes in `EXPECTED.json`)
| File | Expected status | Shows |
|---|---|---|
| 01_purchase_intra_18 | DRAFT_AI | Rs 10,000 @18% → CGST 900 + SGST 900 |
| 02_purchase_inter_igst | DRAFT_AI | Karnataka vendor → IGST |
| 03_purchase_5pct | DRAFT_AI | 5% item |
| 04_bad_gstin | NEEDS_REVIEW | GSTIN checksum fails |
| 05_duplicate_of_01 | DUPLICATE | same vendor + invoice no + total + date |
| 06_arithmetic_mismatch | NEEDS_REVIEW | printed total ≠ lines + tax |
| 07_sale_intra, 08_sale_inter | DRAFT_AI | Dr Receivable / Cr Sales + output tax |
| 09_unregistered_vendor | NEEDS_REVIEW | no ITC, RCM hint |
| 10_gateway_failure | MANUAL_ENTRY_REQUIRED | fixture simulates an AI outage |

## Environment variables
| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./munshi.db` | Postgres (`postgresql+psycopg://…`) or SQLite |
| `JWT_SECRET`, `JWT_TTL_MINUTES` | dev value, 720 | HS256 bearer tokens |
| `LLM_MODE` | `mock` | `mock` (fixtures + deterministic parser) or `prune` |
| `PRUNE_BASE_URL`, `PRUNE_API_KEY`, `PRUNE_MODEL`, `PRUNE_TIMEOUT_S` | | Prune gateway (assumed contract) |
| `ANCHOR_MODE` | `hardhat` | `hardhat` (falls back to MOCK if the node is unreachable) or `mock` |
| `CHAIN_RPC_URL`, `ANCHOR_PRIVATE_KEY`, `DEPLOYMENT_FILE` | `:8545`, empty, `chain/deployments/local.json` | empty key = first unlocked Hardhat account |
| `CONFIDENCE_THRESHOLD` | `0.85` | min per-field confidence for auto-draft |
| `AUTO_DRAFT_AMOUNT_LIMIT_PAISE` | `10000000` | at/above this → NEEDS_REVIEW and HIGH-risk approvals |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | frontend origin; QR codes point to `{PUBLIC_BASE_URL}/verify` |
| `CORS_ORIGINS`, `EXPORT_OPENAPI` | `*`, `true` | |

`/healthz` and the startup log always show the effective `llm_mode` and `anchor_mode`.

## Dependency rules
`routers → module service.py → domain logic / repository → models`. Enforced by `tests/test_architecture.py`:
- Routers never import SQLAlchemy, models or repositories.
- A module never imports another module's `models` or `repository`; only its `service.py` (or pure helpers such as `ledger.money`, `trust.audit.record`, `ai.gateway`).
- No LLM provider SDK anywhere (`scripts/check_no_provider_sdk.py`); every LLM call goes through `modules/ai/gateway.py`.
- No float literals, `float()` or true division in `modules/ledger` and `modules/rules`; money is integer paise, rounded half-up in `ledger/money.py`.
- Every business table has `workspace_id`; every query filters by it. One exception: public verify looks up a report by its sha256 and then scopes by that report's workspace.
- Only `modules/ledger` writes journals, and only after the rules engine validates; posting re-runs the engine and refuses drafts that no longer match (`DRAFT_MISMATCH`).
- Posted journals and audit events are immutable (ORM guards; on Postgres also triggers and `REVOKE`). Fix by reversal.

## Endpoints
| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/v1/auth/login` | any | `{email,password}` → bearer JWT |
| GET | `/v1/auth/me` | auth | |
| POST | `/v1/documents` | ACC, CA | multipart `file`; returns document + extraction + proposal |
| GET | `/v1/documents/{id}` | auth | |
| GET | `/v1/proposals?status=&cursor=&limit=` | auth | DRAFT_AI, NEEDS_REVIEW, DUPLICATE, MANUAL_ENTRY_REQUIRED |
| POST | `/v1/journals/draft` | ACC, CA | body = invoice facts (manual entry path) |
| POST | `/v1/journals/{id}/post` | ACC, CA | re-runs engine, checks balance + open period, audit event |
| GET | `/v1/journals/{id}` | auth | |
| POST | `/v1/approvals` | ACC, CA | `{object_type: journal\|period_close\|investor_pack, object_id}` |
| GET | `/v1/approvals?state=` | auth | includes `version_hash`, `current_version_hash`, `stale`, `diff` |
| POST | `/v1/approvals/{id}/approve` | CA (LOW-risk journal: any other ACC) | never the requester; period close → lock → anchor |
| POST | `/v1/approvals/{id}/request-changes` | reviewer | |
| GET | `/v1/periods` | auth | |
| GET | `/v1/reports/pnl?period_id=` | auth | |
| GET | `/v1/tax/gst/summary?period=` | auth | MOCK GSTR-3B preview included |
| POST | `/v1/reports/pack` | ACC, CA | 409 unless period close approved; returns sha256, QR, proof URL |
| GET | `/v1/reports/{id}/pdf`, `/v1/reports/{id}/proof` | auth | proof.json is portable |
| GET | `/v1/trust/status` | auth | chain length, `verify_chain`, last anchor, anchor mode |
| POST | `/v1/admin/anchor/run` | ACC, CA | batch + anchor now |
| GET | `/v1/integrations` | auth | all MOCK; LIVE raises `NOT_ENABLED` |
| GET | `/public/verify?hash=` | none | MATCH / NO MATCH / PENDING |
| POST | `/public/verify/upload` | none | multipart `file` |
| GET | `/healthz` | none | modes + db |

Conventions: bearer JWT; send `Idempotency-Key` on creating POSTs (replays return the stored response with `Idempotent-Replay: true`); errors are `application/problem+json` with a stable `code`; lists use opaque `cursor` pagination. The OpenAPI file is exported to `packages/contracts/openapi.json` on startup (`make openapi` without a server).

## Error codes
`VALIDATION_ERROR` 422 · `UNAUTHENTICATED` 401 · `FORBIDDEN` 403 · `ROLE_NOT_PERMITTED` 403 · `SELF_APPROVAL_FORBIDDEN` 403 · `NOT_FOUND` 404 · `CONFLICT` 409 · `INVALID_STATE_TRANSITION` 409 · `VERSION_HASH_MISMATCH` 409 · `PERIOD_NOT_FOUND` 422 · `PERIOD_LOCKED` 409 · `PERIOD_CLOSE_NOT_APPROVED` 409 · `UNBALANCED_JOURNAL` 422 · `DRAFT_MISMATCH` 409 · `RULE_REJECTED` 422 (with `reasons[]`) · `IMMUTABLE_RECORD` 409 · `DUPLICATE_DOCUMENT` 409 · `UNSUPPORTED_DOCUMENT` 415 · `MANUAL_ENTRY_REQUIRED` 422 · `NOT_ENABLED` 501 · `ANCHOR_FAILED` 502 · `IDEMPOTENCY_KEY_REUSED` 422 · `INTERNAL` 500. Source of truth: `core/errors.py`.

## How tamper evidence works
1. Every significant action appends an audit event: `hash = sha256(prev_hash || canonical_json(event))` (RFC 8785 JSON, genesis prev = 32 zero bytes).
2. Leaf events also get `leaf = sha256(0x00 || salt || canonical_json(event))`; the salt stays off-chain.
3. The batcher builds a Merkle tree (`node = sha256(0x01 || L || R)`, odd node promoted) over unanchored leaves and anchors `(sha256("munshi-ws:"+workspace_id), batch_seq, root)` in `AnchorRegistry`. Nothing else goes on-chain.
4. Publishing a pack records `report.published` with the PDF's sha256, then anchors it.
5. Verify: hash → report → audit event → leaf → Merkle proof → root, then **reads the root from the chain** and compares. `scripts/verify_cli.py pack.pdf proof.json --rpc URL` repeats this without importing any Munshi code.

## Verified in this build
- `pytest`: 74 tests green (engine incl. Hypothesis "every journal balances", golden journals, validators incl. "flip any GSTIN char fails", approvals, audit chain, Merkle 1/2/3/7/8, tamper, golden path, architecture, Prune client contract).
- `npx hardhat test`: 5 contract tests green.
- Dry run, all 16 steps PASS: (a) Hardhat + MOCK LLM on SQLite and on Postgres 16; (b) `ANCHOR_MODE=mock` (verify shows `mode: "MOCK"`); fallback from hardhat to MOCK when the node is unreachable. On Postgres, raw-SQL `UPDATE/DELETE` on `audit_events` and posted journals is rejected by triggers.
- Not run: (c) real Prune (no key), and `docker compose up` itself (no Docker daemon in the build sandbox; the compose file passes `docker compose config`).

## Assumptions and gaps
- **Prune is unverified.** `modules/ai/prune_client.py` assumes an OpenAI-style `POST /v1/chat/completions` with Bearer auth and JSON-schema output. Replace only that file once docs exist (P3b). There is no direct-provider fallback: failures route to `MANUAL_ENTRY_REQUIRED`.
- **GST rates are demo values** in `packages/rules/tables/gst_rates.yaml` (slabs 0/5/12/18/28, effective-dated). The September 2025 rate rationalisation is **not** modelled; a CA must add effective-dated rows. Blocked-credit categories are a CA-must-validate list.
- Periods are whole financial years (Apr–Mar). Closing a period locks the whole FY.
- No OCR: images and scanned PDFs go to `MANUAL_ENTRY_REQUIRED`. Text PDFs are read with `pypdf`.
- GST set-off order is simplified (IGST credit → IGST, CGST, SGST; CGST → CGST, IGST; SGST → SGST, IGST).
- Anchor-then-commit: if the DB commit fails after an on-chain anchor, that chain slot is spent and the next run uses a new `batch_seq`. Acceptable for the demo.
- The MOCK anchor stores roots in the same DB, so it shows the mechanics but proves nothing against a DB admin. Every MOCK result says so.
- The outbox is written transactionally but no relay publishes it yet.
- `dryrun.py` re-seeds by default (the golden path locks the period, so it can only run once per seed).

## Claims register
| We say | We never say |
|---|---|
| "GST summary prepared from your ledger (MOCK, not filed)" | filed with / integrated with / approved by GSTN, CBDT, MCA, EPFO, RBI or Prune |
| "Reviewed in Munshi workflow; not a statutory audit" | CA-certified, audited, statutory audit |
| "Tamper-evident: any change to the file gives NO MATCH" | legally proven, court-admissible |
| "Demo rates pending CA validation; not legal/tax advice" | compliant (incl. DPDP compliant) |
| "Anchored on a local Hardhat chain" or "MOCK anchor" | anchored on mainnet / public blockchain (unless configured) |

## Optional hosted deploy
- **API + Postgres on one VM:** install Docker, copy the repo, set `JWT_SECRET`, `PUBLIC_BASE_URL`, `CORS_ORIGINS` in the environment, `make up`. Put Caddy or nginx in front for TLS.
- **PaaS (Render, Railway, Fly):** build `infra/Dockerfile.api`, attach managed Postgres via `DATABASE_URL`, set `ANCHOR_MODE=mock` (labelled) or point `CHAIN_RPC_URL` + `ANCHOR_PRIVATE_KEY` at a testnet and ship a `local.json` for that deployment. Never commit keys.
- **Chain:** local Hardhat for demos; for a testnet, add a network to `chain/hardhat.config.js`, deploy, and mount the resulting deployment JSON.

See `docs/FILE_MAP.md` for a one-line description of every file.
