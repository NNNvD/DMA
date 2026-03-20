.PHONY: help install dev test lint format format-check typecheck ci phase1-check phase1-benchmark phase2-benchmark db-revision db-upgrade

PYTHON ?= python3
UVICORN ?= uvicorn
APP_MODULE ?= backend.api.main:app
PHASE1_TESTS ?= tests/unit/test_ingestion_service.py tests/unit/test_retrieval_service.py tests/unit/test_metrics_service.py tests/integration/test_documents_api.py tests/integration/test_admin_metrics_api.py tests/acceptance/test_phase1_acceptance.py
PHASE1_TYPECHECK ?= backend/models/base.py backend/models/document.py backend/models/chunk.py backend/models/context.py backend/services/embedding_service.py backend/services/ingestion_service.py backend/services/metrics_service.py backend/services/retrieval_service.py backend/services/rules_service.py backend/api/routes/admin.py backend/api/routes/documents.py
PHASE1_FORMAT ?= backend/models/base.py backend/models/document.py backend/models/chunk.py backend/models/context.py backend/services/embedding_service.py backend/services/ingestion_service.py backend/services/metrics_service.py backend/services/retrieval_service.py backend/services/rules_service.py backend/api/routes/admin.py backend/api/routes/documents.py tests/unit/test_metrics_service.py tests/integration/test_admin_metrics_api.py tests/integration/test_documents_api.py tests/acceptance/test_phase1_acceptance.py tests/support/app_factory.py scripts/benchmark_phase1.py

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
	@echo "  make phase1-benchmark  Run Phase 1 latency/token-cost benchmark"
	@echo "  make phase2-benchmark  Run Phase 2 campaign import/query benchmark"
	@echo "  make ci             Run local CI checks"
	@echo "  make db-upgrade     Apply Alembic migrations"
	@echo "  make db-revision m='message'  Create a new Alembic revision"

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

phase1-benchmark:
	$(PYTHON) -m scripts.benchmark_phase1

phase2-benchmark:
	$(PYTHON) -m scripts.benchmark_phase2

ci: lint format-check typecheck test

db-upgrade:
	$(PYTHON) -m alembic upgrade head

db-revision:
	@test -n "$(m)" || (echo "Usage: make db-revision m='short message'" && exit 1)
	$(PYTHON) -m alembic revision -m "$(m)"
