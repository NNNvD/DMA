# Private-Local Campaign Bundle

DMA treats the private campaign data bundle as ignored local material. The
preferred collaborator layout is the root overlay:

`local-private-overlay/project-root/assets/imports/misc/private-local/`

When the standard `.env` defaults are used, DMA checks this root overlay before
the legacy `assets/imports/misc/private-local/` path. The overlay is the normal
source of truth for generated campaign material that should not be committed to
public GitHub.

## Current Layout

```text
local-private-overlay/project-root/assets/imports/misc/private-local/
  campaigns/abomination-vaults/
    campaign-overview.json
    campaign-recaps.json
    sessions.json
    treasure-tracker.json
    pcs.json
    npcs.json
    images.json
  room-keys/abomination-vaults/
  bestiary/abomination-vaults/
  media/abomination-vaults/
  reference/raw/
  reference/extracted/
  imports/abomination-vaults/
  import-recipes/
  character-sheets/abomination-vaults/
```

The live DM Panel reads campaign overview tabs, session notes, PC sheets, NPC
dossiers, portraits, room keys, and campaign bestiary data from this folder
first.

## Import Review Pipeline

New campaign imports should pass through a draft review layer before they become
live DMA data.

```text
local-private-overlay/project-root/assets/imports/misc/private-local/
  campaigns/abomination-vaults/sources.json
  reference/extracted/<source-id>/
    manifest.json
    pages.json
    pages/page-001.txt
  imports/abomination-vaults/<run-id>/
    import-manifest.json
    entity-candidates.json
    room-drafts.json
    field-audit.json
    image-match-audit.json
    unresolved-issues.json
    human-review-log.json
```

The first implementation is rooms-first. The `Import Review` module in the DM
Panel lets the GM create an import run, inspect room drafts, approve or reject
drafts, save reviewer notes, and promote approved rooms into live room-key JSON.

Unreviewed drafts do not appear in Map Room.

## Sharing With Collaborators

Give collaborators the full `local-private-overlay/` folder and ask them to
place it at the repository root:

`DMA-main/local-private-overlay/project-root/`

They must acquire this folder manually from the GM or approved private
distribution channel. GitHub cannot and should not provide it. After every public
DMA update, confirm whether a newer `local-private-overlay/` was also provided.

Do **not** copy or unpack `local-private-overlay/project-root/assets/...` into
`assets/imports/...` for normal use. The backend already prefers the root overlay
when default paths are configured.

## Migration

To regenerate the JSON bundle from the current local Obsidian vault and database:

```bash
python3 scripts/migrate_private_local_campaign_data.py --apply
```

Run without `--apply` first for a dry run.

## Environment

The key settings are:

```env
DMA_PRIVATE_DATA_ROOT=./assets/imports/misc/private-local
DMA_CAMPAIGN_ID=abomination-vaults
```

When `DMA_PRIVATE_DATA_ROOT` is left at the default value, the app first checks
for `./local-private-overlay/project-root/assets/imports/misc/private-local` and
uses that root overlay if present. This keeps private updates in the root
`local-private-overlay/` folder instead of requiring a copy into `assets/`.

`OBSIDIAN_VAULT_PATH` may remain configured for legacy import/export helpers, but
the live DM Panel no longer depends on Obsidian for generated campaign content.

## Current Combat Guardrail

The Current Combat module is card-based only. Do not restore the older
table-based combat module when applying updates, resolving conflicts, or using an
LLM to modify the DMA. If a feature exists only in old table-oriented code,
rebuild that feature in the card-based module.
