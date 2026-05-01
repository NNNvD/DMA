# New Campaign Setup Manual

This guide walks through how to install DMA and stand it up for a brand-new campaign.

## 1. Install DMA

From the project root:

```bash
cp .env.example .env
make install
make db-upgrade
```

If you want local embeddings instead of disabling embeddings:

```bash
python3 -m pip install -r backend/requirements-local.txt
```

## 2. Configure Environment

Open `.env` and decide:

- whether embeddings are `disabled`, `local`, or `openai`
- where the database should live
- whether you want to use the experimental MapTool bridge path later

Minimum local setup:

```bash
EMBEDDING_PROVIDER=disabled
DATABASE_URL=sqlite+aiosqlite:///./dma.db
MAPTOOL_BASE_URL=http://127.0.0.1:5005
```

## 3. Start DMA

```bash
make dev
```

The API will be available locally, and the live DM panel is served at:

- `http://127.0.0.1:8000/dm-panel`

## 4. Gather Campaign Source Material

DMA is strongest when you give it real campaign material early.

Useful inputs include:

- rules text or rules reference documents
- campaign notes and lore docs
- session logs or recaps
- character sheets
- private reference notes

## 5. Place Files In The Drop Zones

Put your material here:

- `assets/imports/pathbuilder/`
- `assets/imports/session-logs/`
- `assets/imports/campaign-notes/`
- `assets/imports/misc/aon-rules/raw/`
- `assets/imports/misc/pf2e-reference/raw/`
- `assets/imports/misc/private-local/reference/raw/`
- `assets/imports/misc/private-local/media/`

## 6. Preview Imports First

Before writing anything into the database:

```bash
make preview-assets
```

Review the parse summaries and warnings. This is the safest way to catch formatting issues or
missing references before importing.

## 7. Import Campaign Material

Once the preview looks good:

```bash
make import-assets
```

This populates structured campaign state and stores the underlying source material where relevant.
Textual references like PDFs can be imported into the database; binary media like maps and images
are tracked through governance sidecars/manifests and kept outside the text corpus.

## 8. Generate Governance Metadata

If you want provenance sidecars and manifests for the import tree:

```bash
make export-ingestion-metadata
```

This is especially useful once the campaign has a meaningful amount of source material.

## 9. Verify The Campaign Model

After importing, inspect the data through the campaign endpoints or UI consumers:

- entity overview
- PC dossiers
- session history
- exported Obsidian vault notes

For local engineering verification:

```bash
make phase2-check
make phase3-check
```

## 10. Create Your First Session Brief

Generate prep for the next session:

- `POST /api/prep/session-brief`

This uses campaign state, recent sessions, hooks, and continuity logic to assemble a session-prep
document.

## 11. Optional: Use Obsidian As The Campaign Command Center

If you want a browsable note vault or want to hand a prepared campaign to another DM:

```bash
make export-obsidian-vault VAULT=/path/to/vault
```

The exported vault is readable on its own in Obsidian. DMs can browse campaign indexes, locations,
NPCs, source references, maps, session prep, and notes without running DMA.

If the same DM later edits supported sections in Obsidian, sync those edits back before generating
new prep:

```bash
make sync-obsidian-vault VAULT=/path/to/vault
```

Safe editable sections are:

- `DM Working Notes`
- `Player-Facing Summary`
- `Session Changes`
- `DMA Editable Source`

Do not remove DMA YAML IDs or the `dma:managed` / `dma:editable` marker comments.

## 12. Optional: Enable The Live Bridge Workflow

DMA's stock MapTool integration is currently bridge-based, not a confirmed direct MapTool HTTP API.

For the local bridge demo:

```bash
make maptool-bridge
make push-maptool-fixture
MAPTOOL_BASE_URL=http://127.0.0.1:5005 make dev
```

For a more realistic path, use:

- `make push-maptool-payload FILE=/path/to/map-state.json`
- `make watch-maptool-payloads DIR=/path/to/export-dir`

See [maptool-sync.md](/Users/noah/Google%20Drive/AI%20projects/DMA-main/docs/maptool-sync.md) for details.

## Recommended First Rollout

For a new campaign, the most practical order is:

1. install and start DMA
2. preview and import notes, session logs, and character sheets
3. verify campaign entities and dossiers
4. generate session prep
5. export to Obsidian as the human-facing campaign command center if desired
6. only then experiment with live-session and bridge workflows
