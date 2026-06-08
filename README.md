# 🐉 Dungeon Master Assistant (DMA)

The Dungeon Master Assistant (DMA) is an LLM-powered co-DM for tabletop RPGs, ready to join your party with spellbooks, maps, and quick rulings.

It ingests:

- 📜 Rulebooks and compendia for the chosen system
- 🗺️ Campaign text, images, and maps
- 🧙‍♂️ Party character sheets and DM notes

It then assists the DM in **three stages**:

1. **Overall Campaign Preparation**
   Build a structured understanding of rules, world, factions, NPCs, and party backstories, including house rules and table conventions.

2. **Per-Session Preparation**
   Generate session recaps, surface unresolved hooks, design encounters and scenes, and check continuity.

3. **Real-Time Session Assistance**
   Provide fast, rules-aware, context-aware support during play (rules lookups, improv NPCs, continuity reminders, pacing suggestions) with low latency and high reliability.

The DMA is *not* meant to replace the DM. It acts as a quiet, knowledgeable assistant that:

- 🧭 Knows the rules and the campaign
- 📂 Helps with organization and prep
- 🎭 Supports improvisation and consistency during sessions
- ⚡ Minimizes latency and API costs

For a detailed description of goals and functionality, see:

- [`docs/01-project-vision.md`](docs/01-project-vision.md)
- [`docs/02-functional-spec.md`](docs/02-functional-spec.md)
- [`docs/03-requirements.md`](docs/03-requirements.md)
- [`docs/04-risks-and-mitigations.md`](docs/04-risks-and-mitigations.md)
- [`docs/05-roadmap-and-milestones.md`](docs/05-roadmap-and-milestones.md)
- [`docs/06-testing-and-quality.md`](docs/06-testing-and-quality.md)
- [`docs/08-ingestion-governance.md`](docs/08-ingestion-governance.md)
- [`docs/09-obsidian-vault.md`](docs/09-obsidian-vault.md)
- [`docs/10-promo-overview.md`](docs/10-promo-overview.md)
- [`docs/11-new-campaign-setup.md`](docs/11-new-campaign-setup.md)
- [`docs/12-operations-manual.md`](docs/12-operations-manual.md)
- [`docs/15-novice-local-setup.md`](docs/15-novice-local-setup.md)
- [`docs/17-image-curation-workflow.md`](docs/17-image-curation-workflow.md)

## ✨ High-Level Features

At maturity, the DMA should support:

- **Rules Engine (RAG-based)** 🧾
  - Ingest rulebooks and compendia
  - Answer rules questions with citations and “strict mode” (no hallucinations when unsure)

- **Campaign Model** 🏰
  - Structured representation of locations, NPCs, factions, timelines, secrets, and world state
  - Party and PC backstory integration

- **Prep Tools** 📓
  - Session recaps based on logs/notes
  - Suggest likely player directions and prepare branches
  - Encounter and scene generation, tuned to party and campaign tone
  - Consistency checks and hook surfacing

- **Live Session Tools** 🗡️
  - Fast rules lookups and rulings consistent with house rules
  - On-the-fly NPCs, descriptions, rumors, and small encounters
  - Continuity and name recall (“What was the innkeeper’s name?”)
  - Pacing and tension suggestions

## 🛠️ Development Approach

This repository is designed to be compatible with human developers and coding agents (e.g., OpenAI’s coding agent “Codex”). The **docs** directory contains:

- A clear functional spec  
- Non-functional requirements (cost, UX, reliability, latency, privacy)  
- Risks and mitigations  
- A phased roadmap  
- Testing, debugging, linting, benchmarking, and integration-testing guidelines per phase

## 🚪 Getting Started (for Developers / Agents)

### Local setup

Use the command style for the computer you are currently on. On macOS, Terminal
usually has `python3`; on Windows, PowerShell usually has `python` or `py`.
Keep local machine paths in `.env` rather than source files so the same repo can
be used from both your MacBook Pro and Windows PC.

macOS/Linux:

```bash
cp .env.example .env
make install
make db-upgrade
make dev
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
python -m alembic upgrade head
python -m uvicorn backend.api.main:app --reload
```

Optional local embedding dependencies:

macOS/Linux:

```bash
python3 -m pip install -r backend/requirements-local.txt
```

Windows PowerShell:

```powershell
python -m pip install -r backend/requirements-local.txt
```

### Common development commands

```bash
make test
make lint
make format
make format-check
make typecheck
make ci
make phase2-check
make phase3-check
make phase4-check
make phase1-benchmark
make preview-assets
make import-assets
make export-ingestion-metadata
make export-obsidian-vault VAULT=/path/to/vault
make sync-obsidian-vault VAULT=/path/to/vault
make maptool-bridge
make push-maptool-fixture
```

On Windows, run the same targets if GNU Make is installed. If it is not, use the
underlying Python module commands shown in the setup guide and keep paths quoted
when they contain spaces.

Phase 1 sign-off:

```bash
make phase1-check
```

Phase 2 sign-off:

```bash
make phase2-check
```

Phase 3 sign-off:

```bash
make phase3-check
```

Phase 4 sign-off:

```bash
make phase4-check
```

Phase 1 benchmarking:

```bash
make phase1-benchmark
```

### Phase 1-2 API surface

- `POST /api/documents`: ingest a document through the chunking pipeline.
- `GET /api/documents/search?q=...`: search ingested documents.
- `POST /api/documents/rules/query`: query rule documents with citations and optional strict mode.
- `GET /api/admin/metrics`: inspect Phase 1 latency/token-cost summaries.
- `POST /api/campaign/entities`: create structured campaign entities such as locations, factions, PCs, NPCs, artifacts, calendars, holidays, shops, and events.
- `GET /api/campaign/entities`: query campaign entities by name, relationship, language, location, owner, and active status.
- `POST /api/campaign/import/notes`: import structured campaign notes, optionally store the raw note as a `campaign_note` document, and upsert entities plus relationships.
- `POST /api/campaign/import/pc-sheet`: import either a raw text sheet or a Pathbuilder 2 JSON export into a versioned PC record, resolve faction/location links, and optionally create notable-item artifact records.
- `POST /api/campaign/import/session-update`: import a structured session log, update campaign state, advance calendar state, and persist the raw log as a `session_log` document.
- `GET /api/campaign/import/dropzone`: preview the files currently sitting in `assets/imports/*` or another import root, including parse summaries and unresolved-reference warnings.
- `POST /api/campaign/import/batch`: batch import drop-zone files with optional `dry_run` preview mode and repeat-safe document refresh.
- `POST /api/campaign/relationships`: link entities together for faction ties, contacts, enemies, mentors, and other campaign relationships.
- `POST /api/campaign/entities/{id}/sheet-versions`: store versioned PC sheet updates and sync high-signal campaign details like languages, goals, and notable items.
- `GET /api/campaign/overview`: inspect the current structured Phase 2 world/party state grouped by entity type.
- `GET /api/campaign/pcs/{id}/dossier`: inspect a PC dossier with sheet history, owned artifacts, faction ties, and grouped relationships.
- `GET /api/campaign/session-history`: inspect imported session logs and matching event entities as a prep-friendly history feed.
- `POST /api/campaign/export/obsidian-vault`: sync campaign entities plus session logs/prep docs into an Obsidian vault with YAML frontmatter, tags, and wikilinks.
- `POST /api/campaign/import/obsidian-vault`: pull supported edited Obsidian vault notes back into DMA using stable metadata plus managed/editable section markers.
- `POST /api/prep/session-brief`: generate a deterministic Phase 3 prep brief from campaign state, recent session history, hooks, continuity checks, and calendar state, with optional `session_prep` document storage.
- `GET /api/live/session-state`: inspect the current live session state plus hydrated active PCs/NPCs, location, current date, recent sessions, and latest prep.
- `PUT /api/live/session-state`: update the current live session state for the DM panel.
- `DELETE /api/live/session-state`: reset the saved live session state.
- `POST /api/live/maptool-sync`: pull a MapTool map into the live session snapshot and surface initiative, HP pressure, and conditions in the DM panel.
- `POST /api/live/respond`: run a compact live assistant command such as `/scene`, `/rules frightened`, `/npc suspicious dock clerk`, `/search Captain Mira`, `/recap`, or `/prep`.
- `GET /dm-panel`: open the lightweight browser DM panel for live state, collapsible modules with inline instructions, DMA chat, Map Room, vault-backed campaign/session overviews, Obsidian vault browsing, reference PDF tabs, live commands, a built-in dice roller, a session-aware soundboard, browser voice read-aloud, session mechanics, quick rules, continuity search, and quick prep.
- `GET /api/live/vault/notes` and `GET /api/live/vault/note`: browse configured Obsidian vault notes from the live panel.
- `GET`/`PATCH /api/live/campaign-overview`: read or update the vault-backed campaign overview at `Command Center/Campaign Overview.md`.
- `GET /api/live/session-overviews` plus `GET`/`PATCH /api/live/session-overview`: list, read, and update vault-backed session overview tabs.
- `GET /api/live/reference-pdfs` and `GET /api/live/reference-pdf`: list and open configured source PDFs in the live panel.
- `GET /api/live/dungeon-maps` and `GET /api/live/dungeon-map`: list and open configured local dungeon map images in the live panel.
- `GET /api/live/dungeon-room-key`: load a structured room key for a selected dungeon map.
- `GET /api/live/pc-sheets` and `GET /api/live/pc-sheet`: list and inspect PC character sheets in the live panel.
- `GET /api/live/npc-sheets` and `GET /api/live/npc-sheet`: list and inspect NPC dossiers in the live panel.
- `PATCH /api/live/npc-sheet`: update live NPC dossier details such as appearance, GM notes, status, party relationship, and encounter points.

### Drop-zone batch import

Put source material into:

- `assets/imports/pathbuilder/`
- `assets/imports/session-logs/`
- `assets/imports/campaign-notes/`
- `assets/imports/misc/aon-rules/raw/` for Archives of Nethys rule payloads imported as `kind: "rule"`
- `assets/imports/misc/pf2e-reference/raw/` for community reference guides imported as `kind: "guide"`
- `assets/imports/misc/private-local/reference/raw/` for private local notes, tables, and primers imported as `kind: "reference"`
- `assets/imports/misc/private-local/media/` for private campaign maps, handouts, and other binary assets tracked for provenance but kept outside text retrieval
- `assets/imports/misc/private-local/room-keys/` for structured dungeon room-key JSON used by the DM panel Map Room

To fetch AoN rules into the rules drop-zone:

```bash
make fetch-aon-rules
```

Or call the script directly for narrower syncs:

```bash
python3 -m scripts.fetch_aon_rules --limit 25
python3 -m scripts.fetch_aon_rules --id 97 --id 98
```

Then preview or import everything in one pass:

```bash
make preview-assets
make import-assets
```

Until real campaign files are available, `make phase2-check` and `make phase3-check`
exercise the import and prep flows against deterministic fixtures.

The underlying script also accepts `--root`, repeated `--category`, `--dry-run`, `--no-store-documents`, and `--stop-on-error`.
Supported categories include `pathbuilder`, `session-logs`, `campaign-notes`, `rules`, `reference-guides`, and `local-reference`:

```bash
python3 -m scripts.import_campaign_assets --dry-run
```

To generate provenance sidecars plus corpus/RAG/train manifests for everything currently under
`assets/imports/`:

```bash
python3 -m scripts.export_ingestion_metadata
```

### Obsidian vault export

DMA can also sync the current campaign state into an Obsidian vault. The exporter writes:

- `Campaign/` entity notes grouped by type
- `Notes/` imported campaign-note documents
- `Sheets/` imported PC sheet documents
- `Sessions/` imported session logs
- `Prep/` generated prep notes
- `Command Center/` generated dashboards for session prep, timeline, NPCs, locations, encounters, and treasure
- `Index.md` notes with Obsidian wikilinks and embedded Bases views
- companion `.base` files for dynamic tables in each exported section

Each generated note includes YAML frontmatter plus Obsidian-friendly wikilinks across related
campaign entities, and the campaign/session/PC-sheet importers can now tolerate exported
frontmatter and `[[wikilinks]]`.

```bash
make export-obsidian-vault VAULT=/path/to/vault
python3 -m scripts.export_obsidian_vault --vault /path/to/vault
make sync-obsidian-vault VAULT=/path/to/vault
python3 -m scripts.sync_obsidian_vault --vault /path/to/vault
```

Generated notes use `dma:managed` sections for content DMA can rewrite and `dma:editable`
sections for GM-authored content that can sync back into DMA.

### Player prep PDF export

DMA can turn a player-safe session prep Markdown note into a readable one-page A4 handout PDF with
a light fantasy style. Use this for short session-openers, recap sheets, arrival handouts, or other
player-facing prep that should be shared outside Obsidian.

```bash
make export-player-prep-pdf INPUT=/path/to/player-prep.md
python3 -m scripts.export_player_prep_pdf --input /path/to/player-prep.md
```

By default, the exporter writes the styled `.html` source and `.pdf` to
`obsidian-abomination-vaults-vault/Exports/Handouts/`. It uses local Chrome/Chromium for PDF
rendering and does not require network access.

### MapTool bridge demo

The current repo ships an experimental local bridge prototype for Phase 4 live mechanics work.
This is not a stock MapTool HTTP API; it is a small helper service that DMA can talk to while we
work out the real MapTool integration path.

Quick demo:

```bash
make maptool-bridge
make push-maptool-fixture
MAPTOOL_BASE_URL=http://127.0.0.1:5005 make dev
curl -X POST http://127.0.0.1:8000/api/live/maptool-sync \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"harbor-docks"}'
```

Then open `http://127.0.0.1:8000/dm-panel`.

For details and current caveats, see [`docs/maptool-sync.md`](docs/maptool-sync.md).

### Migration workflow

```bash
# Create a migration
make db-revision m="describe change"

# Apply migrations
make db-upgrade
```

### Delivery roadmap

Implement the roadmap phases in order:

- Phase 1: Rules Engine & RAG
- Phase 2: Campaign and Party Modeling
- Phase 3: Prep Assistant
- Phase 4: Real-Time Session Assistant
- Phase 5: Hardening & Polish

After each phase, follow the relevant testing and QA steps in [`docs/06-testing-and-quality.md`](docs/06-testing-and-quality.md).

## 🤝 Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 🔌 MapTool integration

The repository currently includes an experimental MapTool adapter plus `/api/maptool` and `/api/live/maptool-sync` routes. Recent local validation showed that a normal MapTool server started from `File -> Start Server...` exposes an `rptools-maptool+tcp://...` connection URI, not the HTTP REST surface the current adapter assumes. Treat the adapter as a placeholder until a real HTTP bridge, plugin, or sidecar is defined. See [`docs/maptool-sync.md`](docs/maptool-sync.md) for the current status and recommended next steps.
