# Obsidian Vault Workflow

DMA can export the current campaign state into an Obsidian vault and import supported vault edits
back into DMA. The intended model is now hybrid:

- Obsidian is the human-facing campaign command center.
- DMA remains the structured engine for IDs, relationships, retrieval, prep generation, and live
  assistance.
- The vault is portable and readable even for DMs who never install DMA.
- Sync markers tell DMA which parts of a note it can safely rewrite and which parts humans can edit.

## What It Writes

The exporter creates these folders inside the target vault root:

- `Bases/`
- `Command Center/`
- `Campaign/Locations/`
- `Campaign/NPCs/`
- `Campaign/PCs/`
- `Campaign/Factions/`
- `Campaign/Artifacts/`
- `Campaign/Shops/`
- `Campaign/Calendars/`
- `Campaign/Holidays/`
- `Campaign/Events/`
- `Library/References/`
- `Notes/`
- `Sheets/`
- `Sessions/`
- `Prep/`

It also writes index notes like:

- `Command Center/Start Here.md`
- `Command Center/Session Dashboard.md`
- `Command Center/Session 1 Prep.md`
- `Command Center/Party Overview.md`
- `Command Center/Session Threat Fit.md`
- `Command Center/Timeline.md`
- `Command Center/NPC Roster.md`
- `Command Center/Location Atlas.md`
- `Command Center/Encounter Tracker.md`
- `Command Center/Treasure Tracker.md`
- `Campaign/Index.md`
- `Library/Index.md`
- `Notes/Index.md`
- `Sheets/Index.md`
- `Sessions/Index.md`
- `Prep/Index.md`

And companion Bases files such as:

- `Bases/Campaign.base`
- `Bases/Timeline.base`
- `Bases/NPC Roster.base`
- `Bases/Location Atlas.base`
- `Bases/Library.base`
- `Bases/Notes.base`
- `Bases/Sheets.base`
- `Bases/Party Overview.base`
- `Bases/Sessions.base`
- `Bases/Prep.base`

Imported `kind: "reference"` documents now export into `Library/References/`, which makes
private player guides and GM volumes visible in the vault without mixing them into structured
campaign-entity folders.

`Command Center/` is the recommended human starting point. It gathers the generated vault into a
small set of play-facing dashboards:

- `Start Here` links the main prep views and summarizes the export inventory.
- `Session Dashboard` acts as a live-play cockpit that keeps the current party, tonight's prep, and the main trackers together.
- `Session 1 Prep` collects likely opening notes and embeds canonical note sections for immediate use.
- `Party Overview` embeds a GM-focused party Base with defenses, initiative, senses, languages, healing/scouting/frontline roles, and other table-critical fields.
- `Session Threat Fit` turns current party strengths and gaps into a Session 1 readiness read for scouting, social entry, darkness, attrition, and frontline stability.
- `Timeline`, `NPC Roster`, and `Location Atlas` now embed dedicated Bases views instead of static tables.
- `Encounter Tracker` and `Treasure Tracker` now embed the canonical `Encounter Index` and
  `Treasure Index` sections from the reference notes instead of duplicating those rows.

DMA now exports selected reference-linked visuals into the vault as well:

- extracted PDF images under `Library/Assets/<document title>/`
- copied Abomination Vaults map files under `Library/Assets/Maps/Book <n>/`

Those assets are linked back into the relevant reference notes so the books, maps, and campaign
notes are easier to browse together.

## Note Format

Each generated note includes:

- YAML frontmatter
- stable DMA metadata such as `dma_kind`, `entity_id` or `doc_id`, `stable_key`, `vault_sync`, and
  `dma_sync_role`
- Obsidian tags such as `dma/generated` and `dma/entity/npc`
- flat YAML properties for relationships, details, linked entities, source context, access scope,
  encounters, and treasure
- full vault-relative wikilinks like `[[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]`
- inline entity wikilinks inside exported note bodies where DMA can resolve the reference
- source-aware body sections such as `Overview`, `Detailed Notes`, `Relationship Context`,
  `Source References`, `Access And Spoilers`, `Encounter Index`, and `Treasure Index`
- a PC-sheet-specific export view with a structured sheet snapshot plus the imported source
- a GM-friendly `Party Overview` Base that uses player-named sheet notes while still linking to the actual PC entities
- a round-trip-safe body format that preserves DMA import fields for campaign notes and session logs
- DMA-managed sections wrapped in `<!-- dma:managed:start ... -->` markers
- human-editable sections wrapped in `<!-- dma:editable:start ... -->` markers

For PDF-backed reference documents, DMA can now extract a bounded set of larger embedded images
into `Library/Assets/<document title>/` and embed those visuals into the relevant reference notes.

For Abomination Vaults reference notes specifically, DMA also derives a lightweight location index
from source-text callouts such as `Creatures:` and `Treasure:` so the vault can track:

- where monsters and enemies are encountered
- where treasure and notable rewards are found
- whether a note is safe to share with players or should remain DM-only

Entity notes are intentionally written in a format that stays readable in Obsidian while also
remaining compatible with the current campaign-note parser.

## Vault Sync Contract

DMA now writes two kinds of marked sections:

- `dma:managed`: generated content owned by DMA. These sections may be rewritten on export.
- `dma:editable`: human workspace content. These sections are preserved and can be imported back.

Safe places to edit:

- `DM Working Notes`
- `Player-Facing Summary`
- `Session Changes`
- `DMA Editable Source` for campaign notes, PC sheets, and session logs

Avoid editing unless you know what you are doing:

- `dma_kind`
- `entity_id`
- `doc_id`
- `stable_key`
- `vault_sync`
- `dma_sync_role`
- managed block marker comments

When syncing back into DMA, document notes are imported before campaign entity notes. This means a
direct edit on an entity note wins over older source-document text in the same sync pass.

Index notes now embed their companion base using Obsidian's `![[...]]` syntax and no longer repeat
the same content as static link tables. Command-center notes also prefer canonical note embeds such
as `![[...]]` and section embeds such as `![[...#Overview]]` where that is more useful than
re-summarizing the note.

To keep these embed-heavy pages concise, DMA now wraps generated embeds in foldable Obsidian
callouts such as `> [!abstract]- ...`, `> [!info]- ...`, or `> [!example]- ...`.

## Commands

Use the CLI:

```bash
python3 -m scripts.export_obsidian_vault --vault /path/to/vault
```

To pull edited vault notes back into DMA:

```bash
python3 -m scripts.sync_obsidian_vault --vault /path/to/vault
```

Or via `make`:

```bash
make export-obsidian-vault VAULT=/path/to/vault
make sync-obsidian-vault VAULT=/path/to/vault
```

Useful options:

- `--active-only`
- `--no-campaign-notes`
- `--no-pc-sheets`
- `--no-session-logs`
- `--no-session-prep`
- `--no-indexes`
- `--no-command-center`
- `--campaign-note-limit 100`
- `--pc-sheet-limit 50`
- `--session-limit 25`
- `--prep-limit 25`

## API

The same workflow is exposed through:

- `POST /api/campaign/export/obsidian-vault`
- `POST /api/campaign/import/obsidian-vault`

Request body:

```json
{
  "vault_path": "/path/to/vault",
  "include_inactive": true,
  "include_campaign_notes": true,
  "include_pc_sheets": true,
  "include_session_logs": true,
  "include_session_prep": true,
  "include_indexes": true,
  "include_command_center": true,
  "campaign_note_limit": 100,
  "pc_sheet_limit": 50,
  "session_limit": 50,
  "prep_limit": 50
}
```

## Import Compatibility

DMA does not yet treat an Obsidian vault as the sole source of truth. The database remains the
canonical structured state store.

However, the current campaign-note, session-update, and PC-sheet parsers now tolerate:

- YAML frontmatter at the top of the note
- frontmatter `tags`
- Obsidian `[[wikilinks]]` in note fields

That means notes exported by DMA can be edited in Obsidian and still be re-imported through the
existing import routes without stripping frontmatter by hand.

The preferred route for full-vault round trips is now `sync_obsidian_vault` or
`POST /api/campaign/import/obsidian-vault`, because that path understands `vault_sync`,
managed/editable blocks, and note ordering.

## Current Limit

This is a structured sync integration, not a free-form vault parser. It does not yet infer arbitrary
folder semantics, backlinks, canvases, or plugin-specific metadata beyond the DMA frontmatter and
managed/editable section markers.

The encounter and treasure extraction is intentionally conservative. It currently depends on
source-text patterns in imported documents, so it works best on adventure-path PDFs with consistent
area headers and callouts. It does not yet create full monster or treasure entities automatically.
