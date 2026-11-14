# File map
Format: **file**: what it does · depends on → used by

## Root
- **CLAUDE.md**: shared context for Claude Code sessions (Part A + implementation notes) · none → every session
- **README.md**: quickstart, env vars, rules, endpoints, error codes, gaps, claims register · none → humans
- **Makefile**: `up/down/demo/dryrun/api/dryrun-local/test/chain-test/openapi` targets · docker, python, npm → humans/CI
- **requirements.txt**: Python dependencies · none → pip, Dockerfile.api
- **.env.example**: every setting with safe defaults · none → copy to `.env`
- **pytest.ini**: test discovery and warnings · none → pytest

## core/
- **config.py**: `Settings` from env (DB, JWT, LLM/anchor modes, gate thresholds) · pydantic-settings → everything
- **db.py**: engine/session, `Base` + mixins, `create_all` (+ Postgres triggers/REVOKE), `drop_all`, `ping` · config → models, deps, seed
- **ids.py**: UUIDs and the pseudonymous on-chain workspace id · hashlib → db, trust
- **canonical.py**: the ONLY JSON canonicaliser (RFC 8785, rejects floats) · rfc8785 → trust, workflow, ledger, integrations
- **hashing.py**: sha256, chain/leaf/node hash rules, salts · hashlib → trust, docintel, verify
- **errors.py**: `DomainError` subclasses, stable code list, problem+json handlers · fastapi → all services, main
- **security.py**: PBKDF2 passwords, JWT issue/decode · PyJWT, config → identity, idempotency, seed
- **outbox.py**: `outbox` table + `emit()` in the same transaction · db → ledger, workflow, docintel
- **idempotency.py**: `idempotency_keys` table + ASGI middleware replaying POST responses · db, security → main
- **pagination.py**: opaque keyset cursors · sqlalchemy → docintel, workflow services

## apps/api/
- **main.py**: app factory, CORS, middleware, routers, startup (create tables, log modes, export OpenAPI) · all routers, core → uvicorn
- **deps.py**: per-request session (commits before response), bearer principal, `require()` · core.db, identity.service → routers
- **routers/auth.py**: login, me · identity.service → frontend
- **routers/documents.py**: upload, get document, list proposals · docintel.service → frontend
- **routers/journals.py**: draft, post, get journal, list periods · ledger.service → frontend
- **routers/approvals.py**: request, list (diff/stale), approve, request-changes · workflow.service → frontend
- **routers/reports.py**: P&L, publish pack, proof, PDF · ledger, reporting, trust services → frontend
- **routers/tax.py**: GST summary (+ MOCK GSTR-3B preview) · tax.service → frontend
- **routers/trust.py**: trust status, admin anchor run · trust.service → frontend/ops
- **routers/integrations.py**: MOCK integration catalogue · integrations.service → frontend
- **routers/public.py**: unauthenticated verify by hash / upload · trust.verify_service → public verify page
- **routers/health.py**: `/healthz` with db and effective modes · core.db, ai.gateway, trust.service → ops, dryrun
- **schemas/*.py**: typed request/response models for OpenAPI (auth, ledger, documents, workflow, reports, common) · pydantic, rules.service → routers

## modules/identity
- **models.py**: `workspaces`, `users` (CA reg no display-only), `memberships` (role check) · core.db → identity repo, seed
- **repository.py**: user/membership/workspace queries · models → identity.service
- **service.py**: login, principal from token, `require_role`, workspace context, user display · repo, security → deps, all modules

## modules/rules (pure; no tables)
- **models.py**: `InvoiceFacts` (engine input), `TaxContext`, `DraftJournal`, `DraftLine`, `Rejection` · pydantic → engine, ledger, docintel
- **gstin.py**: GSTIN/PAN shape + mod-36 checksum, `make_gstin` · none → engine, docintel.validators, seed
- **loader.py**: effective-dated rulesets, slabs, HSN rates, blocked credits, CoA from YAML (cached) · PyYAML, packages/rules → engine, ledger.coa, tax
- **engine.py**: `build_journal`: validation → tax determination → posting → policy → hints · loader, gstin, ledger.money → rules.service
- **explain.py**: human-readable lines for a result · ledger.money → rules.service
- **service.py**: public facade re-exporting engine, types, GSTIN helpers, tables · all of the above → ledger, docintel, tax, schemas

## modules/ledger
- **money.py**: half-up rounding, `tax_on`, `split_tax`, exact rupee parsing, lakh/crore formatting · none → rules, ledger, docintel, reporting
- **periods.py**: FY bounds/name, `assert_open` · errors → ledger.service
- **models.py**: `accounts`, `periods`, `journal_entries`, `journal_lines` (one-side check) + immutability guards · core.db → ledger repo/service
- **repository.py**: workspace-scoped queries, account and tax-tag totals · models → ledger.service, reports
- **coa.py**: seed chart of accounts from YAML · rules.service, repo → ledger.service
- **reports.py**: trial balance, P&L from POSTED lines · repo, money → ledger.service
- **service.py**: the only journal writer: draft, post (re-run engine), reverse, lock period, views, report wrappers · rules, identity, trust.audit, outbox → routers, docintel, workflow, tax, reporting

## modules/ai
- **models.py**: `ai_runs` (hashed input, mode, status, redaction counts) · core.db → runs
- **redaction.py**: masks Aadhaar (always), bank a/c, IFSC, standalone PAN, phone, email · re → gateway, fixtures script
- **prompts.py**: versioned registry (`docintel.invoice_extract@1`), JSON schema, delimited data block · none → gateway, mock
- **gateway.py**: `LlmRequest/LlmResponse`, `LlmGateway` protocol, `get_gateway`, `run_structured` · prompts, redaction, runs → docintel, reporting, health
- **runs.py**: writes `ai_runs` rows · models → gateway
- **prune_client.py**: assumed Prune contract, retries, circuit breaker, single schema repair · httpx, config → gateway
- **prune_mock.py**: fixtures by (prompt_id, input_hash) + deterministic invoice parser, `llm_mode=MOCK` · prompts → gateway, fixture script

## modules/docintel
- **models.py**: `documents`, `extractions`, `proposals` · core.db → pipeline, service
- **schemas.py**: `InvoiceExtraction` (per-field confidence), classify vs workspace GSTIN, `to_facts` · pydantic, money, rules.service → pipeline
- **validators.py**: GSTIN/PAN, ownership, period open, arithmetic within 1 paisa/line, dedupe key · rules.service, money → pipeline
- **pipeline.py**: ingest → classify → read → extract → validate → score → route (gate) · ai.gateway, ledger.service, identity, trust.audit → service
- **service.py**: upload, document/proposal views, proposal listing · pipeline, outbox → routers

## modules/workflow
- **models.py**: `approvals` (version hash, snapshot, risk), `comments` · core.db → service
- **state_machine.py**: allowed transitions DRAFT_AI…ANCHORED · errors → service
- **version_hash.py**: snapshot per object type + hash via canonical JSON · ledger.service, canonical → service
- **service.py**: request, decide (role/not-self/hash checks → lock → anchor), request changes, list with diff, sign-offs · identity, ledger, trust → routers, reporting

## modules/tax
- **models.py**: `gst_rates` DB mirror of the YAML table · core.db → tax_tables
- **tax_tables.py**: sync YAML rates into DB, list rates · rules.service → seed
- **gst_summary.py**: outward/inward/ITC/net payable with simplified set-off · none → tax.service
- **service.py**: period GST summary + MOCK GSTR-3B preview · ledger, identity, integrations → routers, reporting

## modules/integrations
- **ports.py**: `GstPort`, `ItdPort`, `McaPort`, `EpfoPort`, `NswsPort`, `AaPort` protocols · none → adapters
- **models.py**: `integration_connections` (MOCK rows) · core.db → seed
- **mock_gst.py**: canned GSTR-2B, GSTR-1/3B payloads with hash; `submit` disabled · canonical, hashing → registry
- **mock_itd.py, mock_mca.py, mock_epfo.py, mock_nsws.py, mock_aa.py**: "designed, not built" stubs · none → registry
- **registry.py**: provider catalogue; LIVE raises `NotEnabledError` · mocks → service
- **service.py**: `gst_port()`, catalogue + claims notice · registry → tax, routers

## modules/trust
- **models.py**: `audit_events` (append-only guard), `audit_chain_heads`, `merkle_leaves`, `merkle_batches`, `reports`, `mock_anchors` · core.db → trust
- **audit.py**: `record()` (lock head, seq+1, chain hash, salted leaf), `verify_chain()` · canonical, hashing → ledger, workflow, docintel, batcher, trust.service
- **merkle.py**: `build_tree`, `proof`, `verify_proof` · hashing → batcher, verify_service
- **anchor_port.py**: `AnchorPort` protocol, receipt, factory with hardhat→MOCK fallback · config → batcher, verify, status
- **anchor_hardhat.py**: web3.py client reading only `deployments/local.json` · web3 → anchor_port
- **anchor_mock.py**: DB-backed MOCK anchor with fake tx hash · models → anchor_port
- **batcher.py**: unbatched leaves → tree → anchor → batch + proofs → `anchor.confirmed` · merkle, anchor_port, audit → trust.service
- **proofs.py**: portable proof.json bundle · audit, models → trust.service
- **verify_service.py**: hash/upload → report → leaf → proof → root read from anchor → verdict · merkle, anchor_port → public router
- **service.py**: register report (`report.published`), PDF/proof access, status, run anchor, anchor mode · audit, batcher, proofs → reporting, workflow, routers

## modules/reporting
- **models.py**: none (reports are trust objects) · none → none
- **qr.py**: QR as PNG base64 and as a reportlab drawing · qrcode, reportlab → pack_pdf, service
- **pack_pdf.py**: deterministic PDF (invariant mode), MOCK watermark, assurance line, disclaimer · reportlab, money → service
- **service.py**: build pack JSON, require approved close, PDF → register → anchor → response · ledger, tax, workflow, trust, identity, ai.gateway → reports router

## packages/
- **rules/rulesets/purchase_gst.yaml, sale_gst.yaml**: account mapping + policy per doc type, effective-dated · none → rules.loader
- **rules/tables/gst_rates.yaml**: slabs and HSN/SAC rates (demo, effective-dated) · none → rules.loader, tax_tables
- **rules/tables/chart_of_accounts.yaml**: Indian SME CoA with tax tags · none → ledger.coa
- **rules/tables/blocked_credits.yaml**: ITC-blocked categories (CA must validate) · none → engine
- **rules/golden/*.json**: expected journals for fixed inputs · none → test_rules_engine
- **contracts/openapi.json**: exported API contract · main.py → frontend

## chain/
- **contracts/AnchorRegistry.sol**: anchorer-only, write-once `rootOf[ws][seq]`, `Anchored` event · solidity → deploy, tests, anchor_hardhat
- **hardhat.config.js**: solc 0.8.24, localhost network, `SOLC_OFFLINE` solcjs fallback · hardhat → npx
- **scripts/deploy.js**: deploys with first account as anchorer, writes `deployments/local.json` + ABI · hardhat → make chain-deploy, compose
- **test/AnchorRegistry.test.js**: anchor ok, non-anchorer reverts, double anchor reverts, event, empty root · chai → npx hardhat test
- **package.json / package-lock.json**: hardhat toolbox + solc · npm → chain
- **deployments/**: generated `local.json` + ABI (git-ignored) · deploy.js → anchor_hardhat

## seed/
- **seed.py**: idempotent `--reset` seed: workspace, users, CoA, FY period(s), GST rates, MOCK integrations · identity, ledger, tax, rules → make, dryrun, tests
- **invoices/*.txt + EXPECTED.json**: 10 sample invoices and their expected routing · none → tests, dryrun, demo
- **fixtures/ai/…/<input_hash>.json**: MOCK LLM outputs keyed by prompt and input hash · make_mock_fixtures → prune_mock
- **fixtures/gstr2b.json**: canned GSTR-2B · make_seed_invoices → mock_gst

## scripts/
- **dryrun.py**: HTTP-only 16-step golden path, PASS/FAIL per step, modes, non-zero exit on failure · httpx → make dryrun
- **verify_cli.py**: independent PDF + proof.json (+ RPC) verifier; imports nothing from Munshi · web3 (HARDHAT only) → auditors, test_tamper
- **demo_tamper.py**: flips one byte of a file · none → demo, test_tamper
- **check_no_provider_sdk.py**: AST scan for LLM provider SDK imports · ast → make test, test_architecture
- **dev/make_seed_invoices.py**: regenerates seed invoices, EXPECTED.json, gstr2b fixture · rules.gstin → maintainers
- **dev/make_mock_fixtures.py**: regenerates MOCK LLM fixtures with gateway-identical hashing · ai → maintainers

## infra/
- **Dockerfile.api**: Python 3.12 image; seeds then runs uvicorn · requirements → compose
- **Dockerfile.chain**: Node 22 image; compiles with solcjs, runs hardhat node · chain → compose
- **docker-compose.yml**: `db`, `chain`, one-shot `chain-deploy`, `api` (depends on all) · Dockerfiles → make up

## tests/
- **conftest.py**: temp SQLite, MOCK modes, seeded client, login helpers, second accountant · app, seed → all tests
- **test_rules_engine.py**: 6+ engine cases, money helpers, golden files, Hypothesis "always balances" · rules, money
- **test_ledger.py**: draft/post/P&L, rejection problem+json, immutability, draft mismatch, roles, idempotency, reversal · API, ORM
- **test_validators.py**: generated GSTINs, "flip any char fails", arithmetic tolerance, redaction · docintel, ai
- **test_docintel_seed.py**: every seed invoice routes as expected; ai_runs; unsupported files · API
- **test_prune_client.py**: assumed Prune contract, single repair, outage → manual entry · prune_client, API
- **test_approval_rules.py**: self-approval, high-risk role, investor read-only, stale hash 409, lock + anchor · API
- **test_audit_chain.py**: intact chain, edited/deleted event → first broken seq, ORM guards, posting adds leaf · trust.audit
- **test_merkle.py**: sizes 1/2/3/7/8, wrong leaf, tampered sibling · trust.merkle
- **test_tamper.py**: one byte → NO MATCH, tampered anchor root, deterministic PDF, independent CLI · API, scripts
- **test_golden_path.py**: full flow → MATCH; OpenAPI lists every endpoint; integrations MOCK · API
- **test_architecture.py**: provider SDKs, cross-module imports, routers vs DB, no floats in ledger/rules, workspace_id everywhere · ast
