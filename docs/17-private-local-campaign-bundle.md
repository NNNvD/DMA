# Private-Local Campaign Bundle

DMA now treats this ignored folder as the single private campaign data bundle:

`assets/imports/misc/private-local/`

This folder is the source of truth for generated campaign material that should
not be committed to public GitHub.

## Current Layout

```text
assets/imports/misc/private-local/
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
assets/imports/misc/private-local/
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

Give collaborators the `private-local` folder and ask them to place it at:

`assets/imports/misc/private-local/`

They should not use `local-private-overlay/` for new installs. That workflow is
deprecated and kept only as a compatibility note.

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

`OBSIDIAN_VAULT_PATH` may remain configured for legacy import/export helpers, but
the live DM Panel no longer depends on Obsidian for generated campaign content.
