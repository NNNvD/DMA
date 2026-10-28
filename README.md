# 🐉 Dungeon Master Assistant (DMA)

The Dungeon Master Assistant (DMA) is an LLM-powered co-DM for tabletop RPGs, ready to join your party with spellbooks, maps, and quick rulings.

It ingests:

- 📜 Rulebooks and compendia for the chosen system
- 🗺️ Campaign text, images, and maps
- 🧙‍♂️ Party character sheets and DM notes

It assists the DM through campaign setup and a recurring session cycle:

1. **Overall Campaign Preparation**
   Build a structured understanding of rules, world, factions, NPCs, and party backstories, including house rules and table conventions.

2. **Per-Session Preparation**
   Generate session recaps, surface unresolved hooks, design encounters and scenes, and check continuity.

3. **Real-Time Session Assistance**
   Provide fast, rules-aware, context-aware support during play (rules lookups, improv NPCs, continuity reminders, pacing suggestions) with low latency and high reliability.

4. **Session Debrief and Continuation**
   Debrief the DM, review a GM log and proposed campaign changes, draft a
   player report, and carry approved outcomes into preparation for the next session.

The **DMA browser application** is the session workspace. The **DMA agent** is
the conversational collaborator for preparation, live assistance, and debrief;
its initial [dedicated Codex setup](docs/25-campaign-agent-review-and-acceptance.md)
is verified with a fictional campaign.
The planned **Discord interface** first publishes DM-approved reports and later
answers player questions using only authorized player knowledge. These workflow
and Discord capabilities are delivery goals, not claims of completed features.
See [the session-cycle plan](docs/22-agent-session-cycle-and-discord.md).
The [W0 operating/data contract](docs/23-agent-operating-and-data-contract.md)
defines source ownership, agent tool boundaries, and a repeatable fictional
SQL/overlay recovery rehearsal. The [read-only W1 setup](docs/24-campaign-agent-setup.md)
provides fictional campaign onboarding, durable instructions, and a verified
MCP connection. W1's full guarded profile now supports separately approved
staging/review and fresh-session resume, with native Codex interaction evidence.
Real campaign activation is a separate reviewed operation; W2 session closure is next.
Before the DM manual, prioritize [guided preparation/debrief, reminders and
durable scoped feedback](docs/27-guided-agent-workflows-and-feedback.md), then
verify the local session cycle. Those interaction/learning capabilities are
planned improvements rather than claims about the current W1 profile.
An initial [guided operator-runner prototype](docs/28-guided-agent-prototype.md)
now adds resumable prep/debrief interviews, private note capture and confirmed
campaign preferences around the restricted W1 agent. It supports fictional fixtures
and verified private rehearsal copies; the full guided-workflow/manual acceptance
gate is still open. Follow the [cross-system agent setup](docs/30-agent-cross-system-setup.md)
when moving development to another computer.

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
- [`docs/09-obsidian-vault.md`](docs/09-obsidian-vault.md) (legacy compatibility; workflow retired)
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

### Private campaign overlay: required manual step

The GitHub repository does **not** contain private campaign assets. Collaborators
must manually acquire the latest `local-private-overlay/` bundle from the GM or
the approved private distribution channel after pulling GitHub updates.

Place it at the repository root:

```text
DMA-main/local-private-overlay/project-root/
```

Do **not** copy or unpack this overlay into `assets/imports/...`. When `.env`
uses the default local paths, DMA automatically prefers the root overlay for the
private data, maps, PDFs, room keys, and bestiary images. Obsidian is retired;
compatibility code does not make the vault part of the active workflow. If
anything looks stale, update GitHub **and** manually refresh
`local-private-overlay/`.

Current Combat is the card-based combat module only. Do not restore the older
table-based combat UI when updating or resolving conflicts.

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
make frontend-test
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
- `POST`/`GET /api/campaign/session-update-drafts`, `GET /api/campaign/session-update-drafts/{id}`, candidate decision routes, `POST /api/campaign/session-update-drafts/{id}/promote`, and `/finalize`: stage uncertain session updates, record candidate decisions, atomically promote all accepted facts with durable provenance, and separately approve/reject the log for prep history. A log with accepted candidates must be promoted before finalization. `GET /api/campaign/entities/{id}/provenance` inspects source links. This is the review-first workflow; the legacy import endpoint above applies trusted updates immediately.
- `GET /api/campaign/import/dropzone`: preview the files currently sitting in `assets/imports/*` or another import root, including parse summaries and unresolved-reference warnings.
- `POST /api/campaign/import/batch`: batch import drop-zone files with optional `dry_run` preview mode and repeat-safe document refresh.
- `POST /api/campaign/relationships`: link entities together for faction ties, contacts, enemies, mentors, and other campaign relationships.
- `POST /api/campaign/entities/{id}/sheet-versions`: store versioned PC sheet updates and sync high-signal campaign details like languages, goals, and notable items.
- `GET /api/campaign/overview`: inspect the current structured Phase 2 world/party state grouped by entity type.
- `GET /api/campaign/pcs/{id}/dossier`: inspect a PC dossier with sheet history, owned artifacts, faction ties, and grouped relationships.
- `GET /api/campaign/session-history`: inspect imported session logs and matching event entities as a prep-friendly history feed.
- `POST /api/campaign/export/obsidian-vault` and `POST /api/campaign/import/obsidian-vault`: legacy compatibility only; not part of active campaign workflow.
- `POST /api/prep/session-brief`: generate a deterministic Phase 3 prep brief from campaign state, recent session history, hooks, continuity checks, and calendar state, with optional `session_prep` document storage.
- `GET /api/live/session-state`: inspect the current live session state plus hydrated active PCs/NPCs, location, current date, recent sessions, and latest prep.
- `PUT /api/live/session-state`: update the current live session state for the DM panel.
- `DELETE /api/live/session-state`: reset the saved live session state.
- `POST /api/live/maptool-sync`: pull a MapTool map into the live session snapshot and surface initiative, HP pressure, and conditions in the DM panel.
- `POST /api/live/respond`: legacy helper compatibility route for compact commands. The browser chat workbench is archived; use the dedicated DMA agent in Codex or the IDE for conversation.
- `PATCH /api/live/in-game-state`: save revisioned session-local location, calendar date, time, weather and environmental overrides without replacing combat. See [`docs/26-in-game-state.md`](docs/26-in-game-state.md).
- `GET /dm-panel`: open the browser DM panel with the editable In-Game State overview and card-based combat. Eleven deferred modules, including the browser chat workbench, are intentionally archived and excluded from the active layout and tool menu; see [`docs/21-dm-panel-module-archive.md`](docs/21-dm-panel-module-archive.md) before restoring any module. Talk to the dedicated DMA agent in Codex or the IDE. Obsidian vault browsing is legacy compatibility only.
- `GET /api/live/vault/notes`, `GET /api/live/vault/note`, and legacy vault-backed campaign/session overview routes: compatibility only; inactive unless an archived vault is deliberately restored and configured.
- `GET /api/live/reference-pdfs` and `GET /api/live/reference-pdf`: list and open configured source PDFs in the live panel.
- `GET /api/live/dungeon-maps` and `GET /api/live/dungeon-map`: list and open configured local dungeon map images in the live panel.
- `GET /api/live/dungeon-room-key`: load a structured room key for a selected dungeon map.
- `GET /api/live/pc-sheets` and `GET /api/live/pc-sheet`: list and inspect PC character sheets in the live panel.
- `GET /api/live/npc-sheets` and `GET /api/live/npc-sheet`: list and inspect NPC dossiers in the live panel.
- `PATCH /api/live/npc-sheet`: update live NPC dossier details such as appearance, GM notes, status, party relationship, and encounter points.

### Drop-zone batch import

Put approved, non-private source material into:

- `assets/imports/pathbuilder/`
- `assets/imports/session-logs/`
- `assets/imports/campaign-notes/`
- `assets/imports/misc/aon-rules/raw/` for Archives of Nethys rule payloads imported as `kind: "rule"`
- `assets/imports/misc/pf2e-reference/raw/` for community reference guides imported as `kind: "guide"`

Keep private campaign references, maps, handouts, and room keys in the ignored
root overlay described above. They are local runtime data, not public drop-zone
content. Do not copy the overlay into `assets/imports/` to run the batch importer.

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

### Legacy Obsidian compatibility (inactive)

Obsidian export/import, vault browsing, and sync routes remain for compatibility
with deliberately restored legacy vaults. They are not part of the supported
campaign workflow, and a fresh setup does not require or create a vault. Do not
use these routes for routine campaign updates. See
[`docs/18-obsidian-retirement.md`](docs/18-obsidian-retirement.md).

The legacy exporter writes:

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

Follow W0-W6 in [the roadmap](docs/05-roadmap-and-milestones.md) and
[the detailed session-cycle plan](docs/22-agent-session-cycle-and-discord.md):

1. Define data ownership and establish the dedicated campaign agent.
2. Complete debrief, reviewed logging, player-report drafting, and next-session handoff.
3. Add approved Discord report publication.
4. Connect preparation/live assistance and verify a complete session cycle.
5. Add Discord player questions after access controls and the core workflow are verified.

M1-M5 remain engineering workstreams supporting this sequence: combat reliability,
campaign consistency, frontend/quality baseline, grounded assistance, and
integrations. Quality and recovery gates apply throughout, including the existing
local engineering checkpoint requirements. AoN acquisition remains parked.

The original five phases remain a capability catalogue, and the existing
`phase1-check` through `phase4-check` commands retain their meanings. Apply
[`docs/06-testing-and-quality.md`](docs/06-testing-and-quality.md) throughout each
milestone; record implementation, automated verification, browser verification,
and play-testing separately.

## 🤝 Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 🔌 MapTool integration

The repository currently includes an experimental MapTool adapter plus `/api/maptool` and `/api/live/maptool-sync` routes. Recent local validation showed that a normal MapTool server started from `File -> Start Server...` exposes an `rptools-maptool+tcp://...` connection URI, not the HTTP REST surface the current adapter assumes. Treat the adapter as a placeholder until a real HTTP bridge, plugin, or sidecar is defined. See [`docs/maptool-sync.md`](docs/maptool-sync.md) for the current status and recommended next steps.
