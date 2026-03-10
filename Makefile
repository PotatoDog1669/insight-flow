.PHONY: help doctor bootstrap infra-up infra-down backend-deps backend-browser-deps frontend-deps migrate backend frontend dev-local dev-docker test-backend lint-frontend build-frontend test-all sync-sources profile-gen profile-check smoke-e2e run-mvp-codex-notion

help:
	@echo "Available commands:"
	@echo "  make doctor          # Run local environment diagnostics"
	@echo "  make bootstrap       # Rebuild/repair local dev dependencies"
	@echo "  make infra-up        # Start Postgres + Redis"
	@echo "  make infra-down      # Stop all Docker services"
	@echo "  make backend-deps    # Install backend dependencies into .venv"
	@echo "  make backend-browser-deps # Install Playwright Chromium for browser collectors"
	@echo "  make frontend-deps   # Install frontend dependencies"
	@echo "  make migrate         # Run Alembic migrations"
	@echo "  make sync-sources    # Sync all source presets into DB (upsert)"
	@echo "  make backend         # Run backend dev server"
	@echo "  make frontend        # Run frontend dev server"
	@echo "  make dev-local       # One command local dev (infra + migrate + backend + frontend)"
	@echo "  make dev-docker      # One command full docker dev"
	@echo "  make test-all        # Backend tests + frontend lint/build"
	@echo "  make profile-gen     # Generate missing P0 site profiles from presets"
	@echo "  make profile-check   # Validate all profiles + P0 coverage"
	@echo "  make smoke-e2e       # Deterministic E2E smoke pipeline check"
	@echo "  make run-mvp-codex-notion # Run 4-source MVP chain (OpenAI/Anthropic/GitHub/HF) -> Notion"

doctor:
	./scripts/doctor.sh

bootstrap:
	./scripts/bootstrap.sh

infra-up:
	docker compose up -d postgres redis

infra-down:
	docker compose down

backend-deps:
	cd backend && ../.venv/bin/python -m pip install -e ".[dev]"

backend-browser-deps:
	cd backend && ../.venv/bin/python -m playwright install chromium

frontend-deps:
	cd frontend && npm install

migrate:
	cd backend && PYTHONPATH=. ../.venv/bin/python -m alembic upgrade head

sync-sources:
	cd backend && PYTHONPATH=. ../.venv/bin/python scripts/sync_sources_from_presets.py

backend:
	cd backend && PYTHONPATH=. ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev-local:
	./scripts/dev-local.sh

dev-docker:
	docker compose up --build

test-backend:
	cd backend && ../.venv/bin/python -m pytest -q

lint-frontend:
	cd frontend && npm run lint

build-frontend:
	cd frontend && npm run build

test-all: test-backend lint-frontend build-frontend

profile-gen:
	.venv/bin/python backend/scripts/generate_site_profiles_from_presets.py

profile-check:
	.venv/bin/python backend/scripts/validate_site_profile.py --all --check-p0

smoke-e2e:
	cd backend && PYTHONPATH=. ../.venv/bin/python scripts/smoke_e2e.py

run-mvp-codex-notion:
	cd backend && PYTHONPATH=. ../.venv/bin/python scripts/run_codex_mvp_chain.py
