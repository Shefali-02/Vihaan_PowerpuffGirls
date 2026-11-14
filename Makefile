# Root Makefile — convenience targets for local development.
# Prerequisites: Python 3.11+, Node 20+, npm.
#
# Quick start:
#   make install   # install all dependencies
#   make seed      # seed the demo database (idempotent)
#   make dev       # start backend + frontend concurrently

.PHONY: install install-backend install-frontend seed dev dev-backend dev-frontend \
        lint test docker-up docker-down clean

# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

install: install-backend install-frontend

install-backend:
	cd munshi && pip install -r requirements.txt

install-frontend:
	cd web && npm ci

# ---------------------------------------------------------------------------
# Seed the demo database
# ---------------------------------------------------------------------------

seed:
	cd munshi && python -m seed.seed

# ---------------------------------------------------------------------------
# Development servers
# ---------------------------------------------------------------------------

# Start both servers in separate windows (Windows / PowerShell).
# On Linux/macOS you can replace `start` with `(` ... ` &)`.
dev:
	@echo "Starting backend on :8000 and frontend on :3000 ..."
	@start "Munshi API" cmd /k "cd munshi && uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000"
	@start "Munshi Web" cmd /k "cd web && npm run dev"
	@echo "Backend: http://localhost:8000/docs"
	@echo "Frontend: http://localhost:3000"

dev-backend:
	cd munshi && uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd web && npm run dev

# ---------------------------------------------------------------------------
# Lint & test
# ---------------------------------------------------------------------------

lint:
	cd munshi && python -m ruff check .
	cd web && npm run lint

test:
	cd munshi && python -m pytest

# ---------------------------------------------------------------------------
# Docker (full stack)
# ---------------------------------------------------------------------------

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------

clean:
	cd munshi && rm -f munshi.db
	cd web && rm -rf .next node_modules/.cache
