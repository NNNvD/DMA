# DM Panel module archive

Status: the original ten modules were archived from the active panel by explicit
user decision on 2026-10-07. DMA Chat Workbench was additionally archived on
2026-10-28 because conversation belongs in the dedicated DMA agent in Codex or
the IDE. Their source code is retained for possible later
reactivation. Do not restore a module merely by adding it to the default panel
order, tool registry, pinned tools, or a launch flow.

## Archived modules

| Module | Stable ID | Archive scope |
| --- | --- | --- |
| Current Scene | `current-scene` | Active panel UI and launcher |
| Session Update Review | `session-update-review` | Active panel UI, launcher, and startup list request |
| Import Review | `import-review` | Active panel UI, launcher, and startup index/image/import requests |
| Quick Rules | `quick-rules` | Tool drawer and dock |
| Quick Prep | `quick-prep` | Tool drawer and dock |
| Session Soundboard | `session-soundboard` | Tool drawer and dock |
| Voice Reader | `voice-reader` | Tool drawer and dock and startup voice/TTS requests |
| Reference PDFs | `reference-pdfs` | Tool drawer and dock and startup PDF request |
| Continuity Search | `continuity-search` | Tool drawer and dock |
| Session Context | `session-context` | Tool drawer and dock |
| DMA Chat Workbench | `dma-chat-workbench` | Active panel, floating launcher and startup rendering; use the dedicated external DMA agent |

The panel stores these modules under the hidden `archived-module-stash`. Their
markup and feature code remain available in the repository; they are not
deleted. The active tool menu and default top-level order omit the archived IDs.
Dice Roller remains active and is the sole default pinned tool. Custom active
pins remain supported.

The top panel no longer displays Scene, Focus or Active NPCs. The separate
Current Date, Location and Map cards are replaced by the editable
[In-Game State overview](26-in-game-state.md). This does not reactivate Current
Scene or any other archived module. The old `/api/live/respond` service remains
for compatibility; it is not the dedicated agent and has no active browser chat
launcher. Do not restore the workbench or its launcher automatically.

## Reactivation gate

Reactivate a module only after a direct user request and a short review of its
current dependencies and replacement path. Update this document and the
`ARCHIVED_MODULE_IDS` manifest in `backend/api/static/dm_panel.html` together.
Then restore the module in the appropriate active layout or tool registry,
remove it from startup-request suppression where relevant, revise the frontend
archive regression test, and verify its rendered workflow. The regression test
intentionally fails if this list is changed without an explicit archive-list
update.

## Separate legacy compatibility

The hidden Obsidian `Vault Workspace` is not part of the archive list above.
It remains separately hidden as documented in
[`docs/18-obsidian-retirement.md`](18-obsidian-retirement.md). Its compatibility
services and routes are not removed by this decision.
