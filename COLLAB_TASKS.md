# Collaboration Tasks

Last updated: 2026-04-10

This file is the shared workboard for human tasks, incoming source material, and handoff notes between you and Codex.

## How We Use This File

- Codex can add or update concrete tasks for you here.
- You can drop source material into the folders listed below.
- When you add new material, note it briefly under `Incoming Material` so I know what changed.
- If something is anonymized or partial, that is still useful. Please do not wait for “perfect” samples.

## Drop Zones

- Pathbuilder 2 character exports:
  `assets/imports/pathbuilder/`
- Session logs, recaps, or post-session notes:
  `assets/imports/session-logs/`
- Campaign notes, lore docs, faction notes, world summaries:
  `assets/imports/campaign-notes/`
- Miscellaneous reference material:
  `assets/imports/misc/`

Once files are in place, Codex can preview or import them in bulk with:

- `make preview-assets`
- `make import-assets`

## File Naming Suggestions

- Pathbuilder 2 exports:
  `pc-<character-name>-pathbuilder.json`
- Session logs:
  `session-<number>-log.md`
- Campaign notes:
  `campaign-<topic>.md`

## Current Tasks For Noah

These are helpful when convenient, but not blocking the current engineering work.

- [ ] Drop 1 or 2 anonymized Pathbuilder 2 JSON exports into `assets/imports/pathbuilder/`
  The most useful next samples are:
  1. a spellcaster
  2. a higher-level character with runes, magic gear, or other more complex data
- [ ] Drop 1 anonymized session log into `assets/imports/session-logs/`
  Ideal format:
  session recap, named NPCs, location changes, loot/items, and any calendar/date notes
- [ ] Drop 1 campaign note sample into `assets/imports/campaign-notes/`
  Ideal format:
  location/faction/NPC references in the style you actually use

## Incoming Material

- 2026-03-25:
  Pathbuilder 2 JSON sample for Conan was shared in chat and used to build initial importer support.

## Notes For Codex

- Prefer real user formats over generic synthetic formats once samples exist.
- Keep importers backwards-compatible with the current deterministic text formats where reasonable.
- Update this file when new human input would materially unblock the next slice of work.
- Use the drop-zone preview/batch importer before asking the user to hand-enter content already available as files.
- As of 2026-04-10, synthetic Phase 2 validation is green via `make phase2-check`; the next high-value validation step is running the batch importer against real sample files when they are available.

## Done Recently

- [x] Added structured campaign entity import for notes
- [x] Added generic text PC sheet import
- [x] Added session update import flow
- [x] Added initial Pathbuilder 2 JSON import support
- [x] Added drop-zone batch import with dry-run preview
- [x] Added PC dossier and session-history read endpoints
- [x] Added a dedicated `make phase2-check` target and completed a full synthetic verification pass
