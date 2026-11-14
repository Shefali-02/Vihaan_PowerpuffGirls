# CLAUDE.md: Munshi backend shared context

## Project
Munshi backend skeleton: AI-assisted Indian accounting, CA approval, tamper-evident reports. 10-hour hackathon, **golden path only**.
Golden path: upload invoice -> LLM extraction via gateway -> rules engine drafts balanced GST journal -> accountant posts -> P&L/GST -> CA (different user) approves period close -> hash-chained audit -> Merkle root anchored on local Hardhat (or labelled mock) -> investor PDF published -> public verify: original = MATCH, one changed byte = NO MATCH.
If short on time cut dashboards first, never approval -> audit -> anchor -> verify.

## Stack
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Postgres (docker) with SQLite fallback via `DATABASE_URL` (portable types, no RLS), JWT, roles ACCOUNTANT / CA / INVESTOR(read-only), `rfc8785`, `web3.py`, Hardhat, `reportlab`, `qrcode`, `pytest`, `hypothesis`.

## Hard rules
1. LLMs propose; only `modules/ledger` writes journals, after the rules engine validates.
2. All LLM calls go through `modules/ai/gateway.py`. No provider SDK imports anywhere.
3. No real government calls. Ports + mock adapters only; outputs carry `"mode":"MOCK"`; live raises `NotEnabledError`.
4. Money = integer paise, no floats, half-up rounding in one helper.
5. Posted journals and audit events are immutable; fix by reversal + new entry.
6. Only hashes, pseudonymous workspace id and seq go on-chain.
7. Preparer cannot approve own object.
8. Never claim integration/approval by GSTN, CBDT, MCA, EPFO, RBI or Prune. Rates/rules live in YAML/DB with effective dates, never hard-coded.
9. Every business table has `workspace_id`; every query filters by it.

## Layout and dependency direction
`routers -> module service.py -> domain logic/repos -> models`. Services may call ports/adapters and `trust.audit.record()`. Routers never touch the DB. A module never imports another module's models/repository, only its `service.py` or an outbox event.
```
apps/api/ main.py deps.py routers/ schemas/
core/ config db security errors canonical hashing ids outbox
modules/ identity ai docintel rules ledger tax workflow trust reporting integrations
packages/rules/ rulesets/ tables/ golden/
chain/ contracts/ scripts/ deployments/ test/
seed/  scripts/  infra/  tests/
```

## Wiring (who calls whom)
- `core/canonical` = the only JSON canonicalisation (workflow, trust, reporting). `core/outbox.emit()` writes events in the same transaction.
- `docintel.service` -> `ai.gateway` (redaction -> Prune or mock -> `ai_runs`) -> `validators` -> `rules.engine` -> stores `Proposal` + draft journal.
- `ledger.service.post()` re-runs the engine, checks balance and open period, writes entry, calls `trust.audit.record()`, emits outbox.
- `workflow.service.decide()` -> checks role, not-self, version hash -> `ledger.lock_period` -> audit -> `trust.batcher.run`.
- `trust.batcher` -> `merkle` -> `AnchorPort` (hardhat or mock) -> batch + proofs -> audit `anchor.confirmed`.
- `reporting.service` -> `ledger.reports` + `tax.service` + `workflow` -> PDF -> sha256 -> audit `report.published` -> batcher.
- `trust.verify_service` -> report lookup -> proof -> recompute root -> read root **from chain** -> MATCH / NO MATCH.

## Endpoints (frozen)
Core 7: `POST /v1/documents` (multipart) | `POST /v1/journals/draft` | `POST /v1/journals/{id}/post` | `POST /v1/approvals/{id}/approve` (CA) | `GET /v1/reports/pnl` | `POST /v1/reports/pack` | `GET /public/verify?hash=` and `POST /public/verify/upload`.
Extra: `POST /v1/auth/login`, `GET /v1/auth/me`, `GET /v1/documents/{id}`, `GET /v1/proposals?status=`, `GET /v1/journals/{id}`, `POST /v1/approvals`, `GET /v1/approvals?state=`, `POST /v1/approvals/{id}/request-changes`, `GET /v1/periods`, `GET /v1/tax/gst/summary?period=`, `GET /v1/reports/{id}/proof`, `GET /v1/reports/{id}/pdf`, `GET /v1/trust/status`, `POST /v1/admin/anchor/run`, `GET /v1/integrations`, `GET /healthz`.
Conventions: bearer JWT, `Idempotency-Key` on creating POSTs, problem+json with stable `code`, cursor pagination.

## Decisions (do not re-ask)
- Prune is unverified: assume OpenAI-style `POST {PRUNE_BASE_URL}/v1/chat/completions`, Bearer auth, JSON-schema output. Default `LLM_MODE=mock`. Mode appears on every AI response. AI failure -> `MANUAL_ENTRY_REQUIRED`, no direct-provider fallback.
- GSTIN: 15 chars, state 01-38, PAN pattern, 14th = Z, 15th = mod-36 checksum (weights alternate 1,2).
- Intra-state (vendor vs workspace state code) = CGST+SGST, else IGST. Unregistered vendor = no ITC, flag review.
- Odd paise: CGST = floor(tax/2), SGST = remainder.
- Approval object types: `journal`, `period_close` (hash of trial-balance snapshot), `investor_pack` (pack JSON + PDF sha256). Approval stores `version_hash` at request; on decision recompute, mismatch -> 409 `VERSION_HASH_MISMATCH`.
- Audit: `hash = sha256(prev_hash || canonical_json(event))`, genesis prev = 32 zero bytes. Leaf = `sha256(0x00 || salt || canonical_json(event))`, salt stored off-chain. Leaf events: document.ingested (hash only), journal.posted/reversed, approval.requested/decided, period.locked, report.published, anchor.confirmed.
- Merkle: node prefix 0x01, odd node promoted unchanged, proof = `[{sibling, position}]`.
- Confidence gate (config): auto-draft only if rule matched, validations pass, min field confidence >= threshold, amount < limit; else NEEDS_REVIEW with reasons.
- Rules and PDF footer say: demo rates pending CA validation, not legal/tax advice. Sign-off is workflow evidence, not a statutory audit.
- Never say: integrated/approved by a government body, live filing, CA-certified, legally proven, DPDP compliant.

## Definition of done
From a clean checkout: accountant uploads invoice, posts, requests approval, CA approves, pack is published, verify shows MATCH, one-byte edit shows NO MATCH, `pytest` green.

## Implementation notes (added after P1-P8)
- Run tests: `make test` (SQLite + MOCK LLM + MOCK anchor). Contract: `cd chain && SOLC_OFFLINE=1 npx hardhat test`.
- Approval decisions also accept a LOW-risk `journal` approval from a different ACCOUNTANT; HIGH risk (period_close, investor_pack, journals >= AUTO_DRAFT_AMOUNT_LIMIT_PAISE) needs a CA.
- Published reports (`reports` table) live in `modules/trust/models.py`; `reporting` owns no tables.
- `modules/rules/gstin.py` is the single GSTIN checksum implementation (docintel validators re-export it).
- Public verify looks a report up by sha256 across workspaces (the only unscoped query), then scopes by its workspace.
