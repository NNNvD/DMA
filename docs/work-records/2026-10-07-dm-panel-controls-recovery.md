# DM panel controls and module inventory — 2026-10-07

## Completion criteria

- Sufficient: shell controls survive a missing combat helper; saved pins retain
  custom entries and restore Dice Roller and Session Soundboard; retired combat
  UI is not reintroduced; ambiguous modules are not deleted without evidence.
- Excellent: rendered-browser interactions and small-screen layout are checked.
- Not complete: controls remain missing after these changes, syntax is invalid,
  or a legacy table-based combat interface is present/routed.

## Changes and findings

The DM panel now falls back to the same small combat-condition helper behavior
when `/api/live/combat-conditions.js` is unavailable, allowing the rest of panel
initialization to continue. Pin loading preserves saved custom pins and adds any
missing default pins (Dice Roller and Session Soundboard).

The module inventory found ten top-level panels: Map Room, Town Square, Current
Combat, Campaign Overview, Session Overview, Session Update Review, Import
Review, Campaign Bestiary, PC Sheet Viewer, and NPC Dossier Viewer. The Current
Combat panel remains card-based. No legacy table-based combat module or other
top-level module explicitly designated for removal was found, so none were
deleted. The M3 roadmap now requires a usage/dependency-backed keep/merge/retire
inventory before future UI deletions.

## Evidence and limitations

- `node --check` passed for the inline panel script; `git diff --check` passed.
- Search found no `combat-table`, `initiative-table`, or `data-combat-table`
  implementation in the DM panel.
- Browser rendering could not be inspected: the computer-use helper failed to
  initialize, and no server was listening at `127.0.0.1:8000`. The visible
  browser symptom and the helper endpoint response therefore remain unverified.
- No campaign data or database was read or changed.

Status: implemented and statically checked; browser verification remains open.

## Archive decision follow-up — 2026-10-07

The user selected Current Scene, Session Update Review, Import Review, Quick
Rules, Quick Prep, Session Soundboard, Voice Reader, Reference PDFs, Continuity
Search, and Session Context for archival. These panels are now parked outside
the active layout, absent from active tool/default-order registries, and omitted
from their archived-only startup requests. Their implementation remains in the
hidden stash. The authoritative list and reactivation gate are recorded in
`docs/21-dm-panel-module-archive.md`; the roadmap and README link to it.

The frontend suite passed (9 tests), including new checks that archived IDs
remain excluded and are parked before layout initialization. Browser
verification remains open because the local panel server/browser inspection was
unavailable during the earlier recovery check.

The earlier default-pin recovery statement above predates the archive decision.
After the user explicitly archived Session Soundboard, the active code and
`docs/21-dm-panel-module-archive.md` were aligned: Dice Roller is the sole default
pin, Session Soundboard is archived, and the remaining collapse controls stay in
the shell. Post-archive browser verification of collapse state and pin behavior
is still open.
