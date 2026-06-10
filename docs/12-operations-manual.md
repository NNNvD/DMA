# DMA Operations Manual

This guide explains how to operate DMA during normal use once it has been installed.

## Daily Workflow

A good steady-state operating rhythm is:

1. add or update campaign material
2. preview imports
3. import structured updates
4. inspect campaign state
5. generate prep
6. use the DM panel during live play
7. export to Obsidian, edit the vault during prep, and sync supported edits back as needed

## 1. Add New Material

As your campaign evolves, keep feeding DMA:

- session logs
- campaign notes
- updated PC sheets
- private reference notes
- new rule or guide material where appropriate

Use the same drop-zone folders described in the setup manual.

## 2. Preview Before Import

Run:

```bash
make preview-assets
```

Use this to spot:

- malformed files
- unresolved names or references
- import-category mistakes
- unexpected parser output

## 3. Import Updates

When the preview looks right:

```bash
make import-assets
```

Use direct API endpoints when you want tighter control over one update type:

- `POST /api/campaign/import/notes`
- `POST /api/campaign/import/pc-sheet`
- `POST /api/campaign/import/session-update`

## 4. Work With Campaign State

Useful operational views include:

- `GET /api/campaign/overview`
- `GET /api/campaign/pcs/{id}/dossier`
- `GET /api/campaign/session-history`

Use these to verify that:

- locations and factions are linked correctly
- PCs reflect the latest sheets
- session consequences are visible in structured state

## 5. Generate Session Prep

Use:

- `POST /api/prep/session-brief`

Typical reasons to run it:

- before a session
- after importing a new session log
- after updating campaign notes
- after major changes to party state or world state

## 6. Operate The Live DM Panel

Open:

- `http://127.0.0.1:8000/dm-panel`

The live panel is used to:

- set current scene title and focus
- set current location
- mark active PCs and NPCs
- store live notes
- collapse modules you do not need during the current table moment
- open per-module instructions from the module header
- chat with DMA in a persistent browser-session workbench
- load local dungeon maps and collapsible room notes in `Map Room`
- read and edit the vault-backed `Campaign Overview`
- switch between editable vault-backed session tabs in `Session Overview`
- inspect imported PC sheets in `PC Sheet Viewer`
- inspect NPC summaries, relationships, and notes in `NPC Dossier Viewer`
- browse and read configured Obsidian vault notes
- export DMA state to the vault and sync supported vault edits back into DMA
- open configured source PDFs in reference tabs
- roll dice with expressions like `1d20+7` and `2d6+4`
- trigger session-aware sound cues and ambience
- read text aloud with different installed browser voices
- inspect mechanics snapshots
- run quick live commands

Notes:

- the soundboard uses browser-generated audio, so it works without a separate sound library
- the voice reader uses the browser speech engine by default, so available voices depend on the local machine and browser
- optional Piper support can provide a better local English narrator when installed and configured
- the vault browser reads from `OBSIDIAN_VAULT_PATH`, defaulting to `./obsidian-abomination-vaults-vault`
- the PDF tabs read from `REFERENCE_PDF_ROOT`, defaulting to `./assets/imports/misc/private-local/reference/raw`
- the Map Room reads map images from `DUNGEON_MAP_ROOT`, defaulting to `./assets/imports/misc/private-local/media`
- the Map Room reads room-key JSON from `DUNGEON_ROOM_KEY_ROOT`, defaulting to `./assets/imports/misc/private-local/room-keys`

When those paths are left at their defaults, DMA prefers matching paths under
`./local-private-overlay/project-root/` if that overlay folder exists. This lets
private campaign updates stay in the root overlay without copying them into
`assets/`.

### Map Room

Use `Map Room` when the party is exploring a numbered dungeon map.

1. choose a dungeon map
2. load the map image
3. use the printed room labels on the map to find the matching collapsed room card
4. expand only the room card you need
5. read `What PCs see first` for safe table description
6. use the GM-only sections for monsters, NPCs, traps, haunts, loot, secret doors, visibility, detection, and dependencies

Room-key files are JSON documents under `DUNGEON_ROOM_KEY_ROOT`. The first supported example is:

- `assets/imports/misc/private-local/room-keys/abomination-vaults/level-1.json`

Each room key should use a `map_id` that matches the map image stem normalized to lowercase with
spaces replaced by hyphens. For example, `Level1.jpg` becomes `level1`.

Literal room text can be enriched from the private local reference markdown. This text is
copyright-sensitive and must remain in ignored/private files only.

Preview a backfill:

```bash
python3 scripts/backfill_room_literal_text.py --map-id level1
```

Apply a backfill to the private room-key JSON:

```bash
python3 scripts/backfill_room_literal_text.py --map-id level1 --apply
```

### Current Combat

Use `Current Combat` when initiative starts.

1. open a room in `Map Room`
2. click `Start From Open Room`, or use `Find Monster` and `Add Monster`
3. click `Roll All Initiative`
4. click `Order By Initiative`
5. use the initiative strip to see order at a glance
6. use `Next Turn` and `Previous Turn` to track active turn and round
7. edit current or max HP directly if the encounter needs adjustment
8. add PF2e conditions under each combatant as they happen
9. use the compact cards during play; only the active combatant opens automatically
10. open the `Strategy`, `Look`, `Recall`, and `AoN` pills only when you need extra detail

The module enriches known creatures from the local Archives of Nethys creature index.
If AoN cannot be reached, it keeps the local room encounter snippet and marks missing
details so the GM can retry from `Find Monster`.

If a combat has several monsters of the same type, DMA splits them into separate cards
and labels them `A`, `B`, `C`, and so on. Timed conditions with numeric durations count
down automatically when turns advance.

`Suggested Strategy` is GM-facing inference unless it appears in the campaign text.
Use it as a table aid, not as official adventure text.

### Voice Reader And Piper

The DMA voice reader always supports browser TTS through Chrome's built-in speech
engine. This requires no extra setup and is the safest default.

For better local English narration, install Piper locally and configure DMA to use
it. Piper voices are local files and should not be committed unless their license
explicitly allows redistribution.

Example `.env` values:

```env
TTS_PROVIDER=piper
PIPER_BINARY_PATH=piper
PIPER_VOICE_PATH=/absolute/path/to/en_US-voice.onnx
```

Optional Piper tuning:

```env
PIPER_SPEAKER_ID=
PIPER_LENGTH_SCALE=
PIPER_NOISE_SCALE=
PIPER_NOISE_W=
```

When `TTS_PROVIDER=piper`, the frontend will try the server-side Piper endpoint
for Voice Reader and Map Room read-aloud buttons. If Piper is not configured or
fails, the frontend falls back to browser speech synthesis.

### Campaign Overview

Use `Campaign Overview` when you need to re-anchor yourself in the whole campaign.

The module reads and writes:

- `obsidian-abomination-vaults-vault/Command Center/Campaign Overview.md`

Use it for:

- campaign premise
- GM-only backstory and hidden truth
- current campaign state
- major threats
- future trajectory
- open threads
- table-specific DM notes

Click `Edit Text` to edit the markdown directly, then `Save Changes` to write it back to the
Obsidian vault. If you edit the note in Obsidian, use `Refresh` in the DM panel to reload it.

### Session Overview

Use `Session Overview` when you need the immediate session command center.

The module reads session tabs from:

- `obsidian-abomination-vaults-vault/Command Center/Sessions/*.md`
- legacy command-center files named `Command Center/Session *.md`

The default working tab is `Next Session`. Each session note should stay human-readable and can
include:

- session goal
- starting situation
- likely scenes or rooms
- important NPCs
- monsters, hazards, and treasure
- secrets and reveals
- what to do if the PCs go off-script
- live session notes
- after-session recap

Click a tab to open that session, use `Edit Text` to change the markdown, and `Save Changes` to
write the note back to the Obsidian vault.

### PC Sheet Viewer

Use `PC Sheet Viewer` when you need a fast table reference for a party member.

The viewer prefers current player-named PC sheets from the Obsidian vault when they
exist, then falls back to database records.

The viewer shows:

- portrait slot or placeholder
- player name when DMA can infer it from the sheet source file
- character name, ancestry, heritage, background, class, level, XP, and languages
- HP, AC, speed, perception, initiative, saves, and class DC when enough imported data exists
- ability scores and modifiers
- trained skills and calculated totals where possible
- attacks, armor, feats, specials, resistances, items, money, spells, and focus points

The current version is read-only. Portraits appear when the PC entity has a `portrait`,
`portrait_url`, `image`, or `image_link` detail field.

### Image Curation

Use local vault assets for player portraits and manually confirmed NPC portraits.
DMA resolves local Obsidian image wikilinks such as
`[[Library/Assets/Portraits/PCs/Daan.png]]` into browser-loadable images in the
PC and NPC viewers.

Recommended metadata:

```yaml
imageLink: "[[Library/Assets/Portraits/PCs/Daan.png]]"
image_status: "confirmed"
image_source: "player supplied"
image_attribution: "Daan"
```

For extracted campaign art, build a manual review gallery:

```bash
python3 scripts/build_image_curation_index.py
```

Then open `Command Center/Assets/NPC Image Curation.md` in Obsidian and assign only
confirmed portraits to canonical NPC notes. Monster images from Archives of Nethys are
treated as remote references when available; do not copy them into redistributable
project assets without a separate rights review.

### NPC Dossier Viewer

Use `NPC Dossier Viewer` when you need a fast social or continuity reference.

The viewer shows:

- portrait slot or placeholder
- name, role, status, current location, summary, and description
- read-aloud-safe appearance description when known
- detailed GM summary
- whether the PCs have encountered the NPC
- the NPC's current relationship to the PCs, such as `hostile`, `neutral`, `friendly`, `ally`, or `patron`
- campaign encounter points where the party is expected to meet or revisit the NPC
- player-facing description if present
- goals, secrets, clues, relationships, tags, and structured details
- optional combat/statblock data if stored on the NPC

Use `Edit NPC Notes And Details` inside the dossier to update appearance, GM summary, status,
relationship to the PCs, campaign encounter points, private DM notes, and player-facing summary.
These fields are stored on the NPC entity and can be exported back into the Obsidian vault.

NPC dossiers are intentionally less mechanical than PC sheets because many campaign NPCs are
contacts, patrons, shopkeepers, or lore sources rather than full combatants.

## 7. Use DMA Chat Commands

Use the `DMA Chat Workbench` for conversational questions and compact live commands such as:

- `/scene`
- `/rules frightened`
- `/search Captain Mira`
- `/recap`
- `/npc suspicious dock clerk`
- `/prep`

These route through:

- `POST /api/live/respond`

The dedicated chat module now owns these prompts. Older one-off command-box behavior has been
folded into the workbench so the panel has one primary place to ask DMA for help.

## 8. Run Live Map/Mechanics Sync

The current live-mechanics path uses the local bridge workflow.

Typical operation:

1. start the bridge with `make maptool-bridge`
2. push fixture or real payloads into it
3. call:

```bash
curl -X POST http://127.0.0.1:8000/api/live/maptool-sync \
  -H 'Content-Type: application/json' \
  -d '{"map_id":"harbor-docks"}'
```

4. refresh the DM panel

For file-driven updates:

- `make push-maptool-payload FILE=/path/to/map-state.json`
- `make watch-maptool-payloads DIR=/path/to/export-dir`

## 9. Export To Obsidian

When you want a readable human-facing campaign command center:

```bash
make export-obsidian-vault VAULT=/path/to/vault
```

Use this when:

- you want a browsable campaign notebook
- you want session prep and notes visible outside the API
- you want `Command Center/` dashboards for timeline, NPCs, locations, encounters, and treasure
- you want to round-trip edited notes back into DMA-compatible formats

Recommended rhythm:

1. import or sync new campaign material into DMA
2. generate or refresh prep in DMA
3. export the vault
4. use Obsidian for reading, annotation, and between-session prep
5. sync supported vault edits back before generating the next major prep output

## 10. Export Player Prep PDFs

Use a player prep PDF when you want to hand the players a short, spoiler-safe session opener
without requiring them to open Obsidian or see GM notes.

The source should be a concise Markdown note with:

- one `#` title
- a few `##` sections
- plain paragraphs and short bullet lists
- no GM-only facts, room keys, tactical advice, source citations, or Obsidian-only wikilinks unless the visible text is player-safe

Export it with:

```bash
make export-player-prep-pdf INPUT=/path/to/player-prep.md
```

Optional controls:

```bash
make export-player-prep-pdf INPUT=/path/to/player-prep.md OUTPUT_DIR=/path/to/handouts BASENAME=session-02-arrival
python3 -m scripts.export_player_prep_pdf --input /path/to/player-prep.md --html-only
```

The exporter creates a light fantasy, one-page A4 handout using local HTML/CSS and renders the PDF
with Chrome or Chromium. The editable `.html` is kept next to the `.pdf` so the GM can inspect or
adjust the visual design if needed.

## 11. Edit And Sync The Obsidian Vault

Obsidian is the human-facing campaign command center. DMA is still the automation engine that
maintains stable IDs, structured relationships, retrieval, session prep generation, and live
assistant behavior.

The vault uses two kinds of marked sections:

- `dma:managed`: DMA-generated material. DMA may rewrite these sections on the next export.
- `dma:editable`: GM-authored material. DMA preserves these sections and can import them back.

Safe places to edit in generated notes:

- `DM Working Notes`
- `Player-Facing Summary`
- `Session Changes`
- `DMA Editable Source`

Use those sections for:

- private GM reminders
- player-safe summaries or read-aloud-safe facts
- notes about what changed during play
- corrections to imported campaign-note, PC-sheet, or session-log source text
- extra hooks, secrets, consequences, or unresolved questions you want DMA to consider later

Do not edit DMA marker comments such as:

- `<!-- dma:managed:start ... -->`
- `<!-- dma:editable:start ... -->`
- `<!-- dma:editable:end ... -->`

Also avoid removing or renaming these YAML properties:

- `dma_kind`
- `entity_id`
- `doc_id`
- `stable_key`
- `vault_sync`
- `dma_sync_role`

To pull supported edits back into DMA:

```bash
make sync-obsidian-vault VAULT=/path/to/vault
```

The sync path currently supports:

- `Campaign/` entity notes
- `Notes/` campaign-note documents
- `Sheets/` PC-sheet documents
- `Sessions/` session-log documents

The sync path intentionally ignores unsupported free-form notes unless `vault_sync: true` is present.

After syncing, inspect the result if needed:

- `GET /api/campaign/overview`
- `GET /api/campaign/session-history`
- `GET /api/campaign/entities`

Then regenerate prep if the edits affect upcoming play:

```bash
# API endpoint
POST /api/prep/session-brief
```

### Practical Examples

If an NPC changes during play:

1. open the NPC note in `Campaign/NPCs/`
2. add the change under `Session Changes`
3. add private interpretation under `DM Working Notes`
4. run `make sync-obsidian-vault VAULT=/path/to/vault`
5. generate the next session brief

If a source note was imported with an error:

1. open the note in `Notes/`, `Sheets/`, or `Sessions/`
2. edit the text inside `DMA Editable Source`
3. run `make sync-obsidian-vault VAULT=/path/to/vault`
4. export again if you want the cleaned version reflected everywhere

## 12. Quality And Maintenance

Recommended maintenance commands:

```bash
make test
make lint
make typecheck
make phase2-check
make phase3-check
make phase4-check
```

Use these after meaningful code or prompt changes.

## 13. Troubleshooting

Common issues:

- imports look wrong:
  use `make preview-assets` and inspect the source formatting
- campaign state is incomplete:
  verify the input files actually mention the entities or relationships you expect
- live sync fails:
  confirm the bridge is running and DMA points at the bridge URL, not a MapTool TCP URI
- DM panel is empty:
  verify live session state has been saved and any live mechanics payload has been synced
- Obsidian edits do not sync:
  verify the note has `vault_sync: true` and that the edit is inside a `dma:editable` block

## 14. Best Practices

- preview imports before writing
- prefer real campaign formats over hand-entered duplicates
- keep session logs structured enough to capture NPCs, locations, loot, and date changes
- use Obsidian for human notes, but keep DMA marker blocks intact
- sync vault edits before generating major new prep
- regenerate prep after important campaign-state updates
- treat the MapTool bridge as experimental until a campaign-specific macro or plugin is stable
