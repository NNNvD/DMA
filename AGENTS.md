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

## Cross-System Development Context
- This project is actively developed on both macOS and Windows. At the start of implementation work, identify the active OS, shell, and repository root before choosing commands.
- Current Windows PC context uses PowerShell and a repository path like `E:\My Drive\AI projects\DMA-main`; the usual MacBook Pro context uses a POSIX shell and paths like `/Users/...`.
- Keep commands and scripts cross-platform where practical. Prefer `make`, Python modules (`python -m ...` / `python3 -m ...`), and package scripts over OS-specific shell snippets.
- When documenting local commands, include both Windows PowerShell and macOS/Linux examples if they differ.
- Quote paths in commands because local roots may contain spaces, especially on Windows.
- Do not hard-code machine-specific absolute paths in source, tests, or committed config. Put local paths in `.env`, ignored local files, or command arguments.
- Preserve cross-platform Git hygiene: avoid case-only filename changes, normalize line endings through `.gitattributes`, and be careful with executable bits and symlinks.

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
- If the user asks to commit, push, publish, create a pull request, or open a PR, interpret that as: use the local `dma-github-publish` Codex skill/workflow first. Run its preflight helper before staging, avoid reused/stale branches, stage explicit public-safe paths only, and never include private campaign material.

## Architecture Notes & Security
- Align with `docs/07-architecture-notes.md`. Keep adapters for model providers, storage, and embeddings at clear boundaries.
- Store secrets in `.env` (add `.env.example`); never commit real keys. Validate config on startup.

## Agent-Specific Instructions
- Start by reading `README.md` and `docs/` files; implement by roadmap phase.
- Make small, verifiable PRs; add tests first. Prefer deterministic fixtures for LLM/RAG behaviors.
