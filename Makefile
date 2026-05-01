.PHONY: help install dev test lint format format-check typecheck ci phase1-check phase2-check phase3-check phase4-check phase1-benchmark db-revision db-upgrade fetch-aon-rules import-assets preview-assets export-ingestion-metadata export-obsidian-vault export-player-prep-pdf sync-obsidian-vault maptool-bridge push-maptool-fixture push-maptool-payload watch-maptool-payloads

PYTHON ?= python3
UVICORN ?= uvicorn
APP_MODULE ?= backend.api.main:app
PHASE1_TESTS ?= tests/unit/test_ingestion_service.py tests/unit/test_retrieval_service.py tests/unit/test_metrics_service.py tests/integration/test_documents_api.py tests/integration/test_admin_metrics_api.py tests/acceptance/test_phase1_acceptance.py
PHASE1_TYPECHECK ?= backend/models/base.py backend/models/document.py backend/models/chunk.py backend/models/context.py backend/services/embedding_service.py backend/services/ingestion_service.py backend/services/metrics_service.py backend/services/retrieval_service.py backend/services/rules_service.py backend/api/routes/admin.py backend/api/routes/documents.py
PHASE1_FORMAT ?= backend/models/base.py backend/models/document.py backend/models/chunk.py backend/models/context.py backend/services/embedding_service.py backend/services/ingestion_service.py backend/services/metrics_service.py backend/services/retrieval_service.py backend/services/rules_service.py backend/api/routes/admin.py backend/api/routes/documents.py tests/unit/test_metrics_service.py tests/integration/test_admin_metrics_api.py tests/integration/test_documents_api.py tests/acceptance/test_phase1_acceptance.py tests/support/app_factory.py scripts/benchmark_phase1.py
PHASE2_TESTS ?= tests/acceptance/test_phase1_acceptance.py tests/unit/test_ingestion_service.py tests/unit/test_campaign_service.py tests/unit/test_campaign_note_import_service.py tests/unit/test_pc_sheet_import_service.py tests/unit/test_session_update_service.py tests/integration/test_campaign_api.py tests/integration/test_campaign_note_import_api.py tests/integration/test_pc_sheet_import_api.py tests/integration/test_session_update_api.py tests/integration/test_campaign_asset_import_api.py
PHASE3_TESTS ?= $(PHASE2_TESTS) tests/unit/test_prep_service.py tests/integration/test_prep_api.py
PHASE4_TESTS ?= $(PHASE3_TESTS) tests/integration/test_live_api.py tests/integration/test_maptool_adapter.py

help:
	@echo "Available targets:"
	@echo "  make install        Install runtime + dev dependencies"
	@echo "  make dev            Run FastAPI app locally"
	@echo "  make test           Run test suite"
	@echo "  make lint           Run Ruff lint checks"
	@echo "  make format         Format code with Black"
	@echo "  make format-check   Check formatting with Black"
	@echo "  make typecheck      Run MyPy"
	@echo "  make phase1-check   Run Phase 1 acceptance checks"
	@echo "  make phase2-check   Run Phase 2 campaign/import checks"
	@echo "  make phase3-check   Run Phase 3 prep-assistant checks"
	@echo "  make phase4-check   Run Phase 4 live-session and MapTool checks"
	@echo "  make phase1-benchmark  Run Phase 1 latency/token-cost benchmark"
	@echo "  make ci             Run local CI checks"
	@echo "  make db-upgrade     Apply Alembic migrations"
	@echo "  make db-revision m='message'  Create a new Alembic revision"
	@echo "  make fetch-aon-rules  Fetch retrieval-only PF2e rules from Archives of Nethys"
	@echo "  make preview-assets Preview drop-zone imports without writing"
	@echo "  make import-assets  Import files from assets/imports"
	@echo "  make export-ingestion-metadata  Generate sidecars, manifests, and review queue for assets/imports"
	@echo "  make export-obsidian-vault VAULT=/path/to/vault  Sync DMA state into an Obsidian vault"
	@echo "  make export-player-prep-pdf INPUT=/path/to/player-prep.md  Export a styled one-page player prep PDF"
	@echo "  make sync-obsidian-vault VAULT=/path/to/vault  Pull edited Obsidian notes back into DMA"
	@echo "  make maptool-bridge  Run the local MapTool bridge prototype on 127.0.0.1:5005"
	@echo "  make push-maptool-fixture  Push demo combat state into the local MapTool bridge"
	@echo "  make push-maptool-payload FILE=/path/to/map-state.json  Validate and push a MapTool payload file into the bridge"
	@echo "  make watch-maptool-payloads DIR=/path/to/export-dir  Watch exported MapTool payload files and push updates into the bridge"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r backend/requirements-dev.txt

dev:
	$(PYTHON) -m $(UVICORN) $(APP_MODULE) --reload

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check backend tests scripts

format:
	$(PYTHON) -m black backend tests scripts

format-check:
	$(PYTHON) -m black --check backend tests scripts

typecheck:
	$(PYTHON) -m mypy backend

phase1-check: lint
	$(PYTHON) -m black --check $(PHASE1_FORMAT)
	$(PYTHON) -m mypy $(PHASE1_TYPECHECK)
	$(PYTHON) -m pytest -q $(PHASE1_TESTS)

phase2-check: lint
	$(PYTHON) -m black --check backend tests scripts
	$(PYTHON) -m mypy backend
	$(PYTHON) -m pytest -q $(PHASE2_TESTS)

phase3-check: lint
	$(PYTHON) -m black --check backend tests scripts
	$(PYTHON) -m mypy backend
	$(PYTHON) -m pytest -q $(PHASE3_TESTS)

phase4-check: lint
	$(PYTHON) -m black --check backend tests scripts
	$(PYTHON) -m mypy backend
	$(PYTHON) -m pytest -q $(PHASE4_TESTS)

phase1-benchmark:
	$(PYTHON) -m scripts.benchmark_phase1

ci: lint format-check typecheck test

db-upgrade:
	$(PYTHON) -m alembic upgrade head

db-revision:
	@test -n "$(m)" || (echo "Usage: make db-revision m='short message'" && exit 1)
	$(PYTHON) -m alembic revision -m "$(m)"

fetch-aon-rules:
	$(PYTHON) -m scripts.fetch_aon_rules

preview-assets:
	$(PYTHON) -m scripts.import_campaign_assets --dry-run

import-assets:
	$(PYTHON) -m scripts.import_campaign_assets

export-ingestion-metadata:
	$(PYTHON) -m scripts.export_ingestion_metadata

export-obsidian-vault:
	@test -n "$(VAULT)" || (echo "Usage: make export-obsidian-vault VAULT=/path/to/vault" && exit 1)
	$(PYTHON) -m scripts.export_obsidian_vault --vault "$(VAULT)"

export-player-prep-pdf:
	@test -n "$(INPUT)" || (echo "Usage: make export-player-prep-pdf INPUT=/path/to/player-prep.md [OUTPUT_DIR=/path/to/handouts] [BASENAME=name]" && exit 1)
	$(PYTHON) -m scripts.export_player_prep_pdf --input "$(INPUT)" $(if $(OUTPUT_DIR),--output-dir "$(OUTPUT_DIR)",) $(if $(BASENAME),--basename "$(BASENAME)",)

sync-obsidian-vault:
	@test -n "$(VAULT)" || (echo "Usage: make sync-obsidian-vault VAULT=/path/to/vault" && exit 1)
	$(PYTHON) -m scripts.sync_obsidian_vault --vault "$(VAULT)"

maptool-bridge:
	$(PYTHON) -m scripts.maptool_bridge

push-maptool-fixture:
	$(PYTHON) -m scripts.push_maptool_fixture

push-maptool-payload:
	@test -n "$(FILE)" || (echo "Usage: make push-maptool-payload FILE=/path/to/map-state.json" && exit 1)
	$(PYTHON) -m scripts.push_maptool_payload_file --file "$(FILE)"

watch-maptool-payloads:
	@test -n "$(DIR)" || (echo "Usage: make watch-maptool-payloads DIR=/path/to/export-dir" && exit 1)
	$(PYTHON) -m scripts.watch_maptool_payload_dir --dir "$(DIR)"
