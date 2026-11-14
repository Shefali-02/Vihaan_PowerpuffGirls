# Munshi backend. `make help` lists targets.
PY ?= python3
export SOLC_OFFLINE ?= 1

.PHONY: help install up down logs demo dryrun dryrun-local test chain-test chain-node chain-deploy api check openapi

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## install Python + chain dependencies
	$(PY) -m pip install -r requirements.txt
	cd chain && npm install

up: ## docker: postgres + hardhat node + contract deploy + API on :8000
	docker compose -f infra/docker-compose.yml up --build -d
	@echo "API: http://localhost:8000/docs"

down: ## docker: stop everything
	docker compose -f infra/docker-compose.yml down

logs: ## docker: follow API logs
	docker compose -f infra/docker-compose.yml logs -f api

demo: ## (docker) re-seed and print logins
	docker compose -f infra/docker-compose.yml exec api python -m seed.seed --reset

dryrun: ## (docker) re-seed in the container, then run the HTTP dry run from here
	docker compose -f infra/docker-compose.yml exec api python -m seed.seed --reset
	$(PY) scripts/dryrun.py --no-reset

api: ## local: seed (idempotent) and run the API with SQLite unless DATABASE_URL is set
	$(PY) -m seed.seed
	$(PY) -m uvicorn apps.api.main:app --reload --port 8000

dryrun-local: ## local: dry run against a local API (re-seeds the same DATABASE_URL first)
	$(PY) scripts/dryrun.py

test: ## pytest + provider-SDK check
	$(PY) scripts/check_no_provider_sdk.py
	$(PY) -m pytest -q

chain-test: ## contract tests (hardhat)
	cd chain && npx hardhat test

chain-node: ## local hardhat node on :8545
	cd chain && npx hardhat node

chain-deploy: ## deploy AnchorRegistry to the local node, writes chain/deployments/local.json
	cd chain && npx hardhat run scripts/deploy.js --network localhost

openapi: ## export packages/contracts/openapi.json without starting a server
	$(PY) -c "from apps.api.main import app, export_openapi; export_openapi(app)"

check: test chain-test ## everything
