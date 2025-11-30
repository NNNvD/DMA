# Repository Guidelines

## Project Structure & Module Organization
- Current layout: `docs/` contains vision, specs, QA, and architecture notes.
- When code is added, organize by capability:
  - `src/rag/`, `src/campaign/`, `src/prep/`, `src/realtime/`
  - `tests/unit/`, `tests/integration/`
  - `scripts/` for one-off tools; `assets/` for sample data/maps.
- Keep modules decoupled; cross-module calls go through clear interfaces.

## Build, Test, and Development Commands
- Prefer a Makefile or package scripts with consistent names:
  - `make dev` (or `npm run dev`): start local dev server/tooling.
  - `make test` (or `pytest`, `npm test`): run all tests.
  - `make lint` (or `ruff check`, `eslint .`): static analysis.
  - `make format` (or `black .`, `prettier --write .`): auto-format.
- Examples:
  - Python: `pytest -q`, `ruff check src tests`, `black -l 88 src tests`.
  - Node/TS: `npm run build`, `npm test`, `eslint .`, `prettier --check .`.

## Coding Style & Naming Conventions
- Python (recommended for backend): 4-space indent, `snake_case` for functions/vars, `PascalCase` for classes. Tools: `ruff`, `black`, `mypy`.
- TypeScript (recommended for UI/tools): `camelCase` for functions/vars, `PascalCase` for components/types. Tools: `eslint`, `prettier`, `tsc --noEmit`.
- Files/folders: `kebab-case` (e.g., `src/rules-engine/`). Keep public APIs small and documented.

## Testing Guidelines
- Frameworks: Python `pytest`; Node `vitest`/`jest`.
- Structure: `tests/unit/test_*.py` or `__tests__/*.test.ts`; integration under `tests/integration/`.
- Target ≥80% coverage on changed code. Include fixture data for RAG prompts and retrieval.
- Follow phase gates in `docs/06-testing-and-quality.md`.

## Commit & Pull Request Guidelines
- Use Conventional Commits (e.g., `feat: add NPC generator`, `fix: handle empty compendium`).
- PRs include: purpose, scope (which roadmap phase), testing notes, and links to relevant docs in `docs/`.
- Update docs when behavior or prompts change. Include screenshots/logs for UX-affecting changes.

## Architecture Notes & Security
- Align with `docs/07-architecture-notes.md`. Keep adapters for model providers, storage, and embeddings at clear boundaries.
- Store secrets in `.env` (add `.env.example`); never commit real keys. Validate config on startup.

## Agent-Specific Instructions
- Start by reading `README.md` and `docs/` files; implement by roadmap phase.
- Make small, verifiable PRs; add tests first. Prefer deterministic fixtures for LLM/RAG behaviors.
