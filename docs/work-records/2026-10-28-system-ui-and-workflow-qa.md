# DMA system, rendered UI and workflow QA

Date: 2026-10-28. Windows / PowerShell, Python 3.11, installed Edge via
Playwright. Local branch: `codex/local-reconciliation-20261027`.

**Assessment: the core workspace is usable in a fictional rehearsal, but session
launch and several interaction details need correction before a confident DM
play-test. The full repository quality gate is not green.** No application code,
real campaign records, Git history or remote repository was changed by this QA.

## Scope and evidence

The actual FastAPI application, including its lifespan and routes, ran against a
disposable SQLite backup of the explicitly marked W1 fictional fixture and a
separate synthetic private overlay. Added test material covered a PC, an NPC,
campaign summaries, a session, a dungeon, a settlement, a cached creature, a
custom bestiary creature and an affliction. All edits made through the browser
were confined to that disposable pair. The test server disabled external AoN
fetching; its cached combat values were explicitly synthetic, not rules evidence.

The desktop computer-control runtime failed during initialization. Rendered
testing therefore used isolated headless Edge contexts, genuine browser clicks,
keyboard input, reloads and screenshots, at 1440 x 1000, 768 x 1024 / 844 and
390 x 844. This establishes browser interaction evidence, not a human's feel for
running a session, touch/soft-keyboard behavior, or another operating system.

Local-only scripts and evidence are under `.codex-temp/` and remain ignored:

- Fixture and screenshots: `.codex-temp/ui-qa-20261028-c/`.
- Browser records: `initial.json`, `workflows.json`, `extended.json`,
  `final-checks.json`, `room-privacy.json` within that directory.
- Harnesses: `prepare_ui_qa.py`, `serve_ui_qa.py`, `ui_qa_initial.cjs`,
  `ui_qa_workflows.cjs`, `ui_qa_extended.cjs`, `ui_qa_final.cjs`,
  `qa_room_privacy.py` within `.codex-temp/`.

These are local evidence paths, not distributable campaign assets. The earlier
`ui-qa-20261028` and `ui-qa-20261028-b` attempts are superseded: fixture setup and
overlay nesting were corrected before the assessment below.

## Verified behavior

| Area | Current browser / API evidence |
| --- | --- |
| Module archive | Eight visible workspace modules; all ten archived modules remain hidden. The separate legacy Vault Workspace also remains hidden. Archived tools are absent from the tool menu. |
| Collapse controls | Map Room collapses, stays collapsed after reload, and expands again. |
| Dice Roller | Dock opens the drawer; `2d6+3` and `1d20+7` produce results and history; invalid input shows an error. Drawer and results can be reached at tablet and phone widths. |
| Map Room / Town Square | Synthetic dungeon and settlement images load, room details open, and settlement locations render. |
| PC / NPC viewers | Party and NPC overviews render; Open loads the respective full detail view. |
| Campaign notes | Editing and saving the overview survives reload. Player recap displays a PLAYER-SAFE badge and excludes the fictional GM secret. |
| Session notes | Sketch Pad persists locally, copies into tracker notes, and explicit tracker writes survive reload in the private session note. |
| Card combat | Party PC and cached synthetic creature can be added, initiative rolled/ordered, HP changed and reloaded. The richer card interface remains in use. |
| Conditions / turns | Explicit one-turn Clumsy expires when its creature ends its turn; Frightened value 2 without a duration remains unchanged. Advancing through the roster increments the round. |
| Failed saves | Injected HTTP 503 retains the edited HP and exposes Retry. Retry saves the value once service returns; reload confirms it. |
| Stale saves | Two panels produce an HTTP 409 on a genuinely changed stale edit; the second panel retains its local value and the newer server value is preserved. |
| Bestiary | Search opens a synthetic custom creature, Add To Combat creates a card, and Track Affliction populates the separate combat tracker. |
| Browser helper chat | `/scene` responds from live state. A question without matching rules evidence explicitly says it cannot find a confident answer. This is the existing REST helper, separate from the W1 dedicated agent. |
| Player-safe room projection | GM room JSON includes the sentinel; `/api/live/dungeon-room-key/player-safe` excludes it and retains the player-visible room description. This tests projection, not a complete authorization audit. |
| Dedicated agent | Two real MCP SDK integration tests pass, including guarded staging/review, fresh-process resume and retained results. These use fictional bindings and simulated operator approval. |

No unhandled JavaScript exceptions were recorded. Expected failure responses
include the deliberately injected 503, stale-write 409, and unavailable optional
MapTool room-state 404. The old-session 404 below is an actual product finding.

## Findings and recommended order

### P1: Current-session launch uses old campaign constants and reports false success

With the fictional QA session already available, clicking **Launch Current
Session** requests `Command Center/Sessions/Session 04 - Level 3 C9 Start.md`.
That request returns 404. Nevertheless, the hero reports:

> Session Launch Mode ready: Session 04, C7 map context, party overview, NPC dossier, and campaign overview are loaded.

It also fills the tracker with C7 / "Choose first route from C7", while the actual
QA session remains displayed. Saving that tracker would introduce the wrong room
context into the otherwise valid session note.

The cause is visible in `backend/api/static/dm_panel.html`:
`launchSessionPath`, `findLevelThreeMapId()` and `launchCurrentSession()` encode
Session 04 / Level 3 / C7; `openSessionOverview()` catches errors without returning
a failure to its caller. The launcher therefore continues after a failed load.

Derive launch targets from an explicit current-session configuration, preserve
existing tracker values until all required loads succeed, and report partial or
failed launch honestly. Add a browser regression with a different campaign/session
and a missing target. This is the first fix before a DM rehearsal.

### P2: Dice Roller offers an Unpin action that cannot take effect

Open the tools menu and choose **Unpin Dice Roller**. The dock button remains and
the menu still offers Unpin. `loadPinnedToolIds()` always adds default pins back,
including immediately after a save. Either respect unpinning or present an honest
fixed shortcut without an Unpin action. Keep the default shortcut available for
fresh profiles, in line with the prior controls recovery.

### P2: Tool drawer keyboard behavior needs completion

Opening Dice Roller and pressing Escape leaves the drawer open. Focus is not
moved into the drawer on open; the observed active element was the page body.
Implement deliberate focus placement, Escape close and return to the opener.
Choose nonmodal versus modal behavior explicitly before adding any focus trap.
The pointer-operated close button works.

### P2: Fixed chrome obscures module destinations and narrow-screen actions

The **Go to Current Combat** shortcut scrolls its heading beneath the fixed status
strip. At phone width the heading starts around y=21 while the strip covers it.
The fixed bottom dock can cover the card's End Turn / Roll All controls when they
are at the viewport edge. The page has no horizontal document overflow at the
tested widths; the wide PC/NPC overview tables use internal scrolling, so their
large descendant bounds alone are not an overflow defect.

Add header-aware scroll offsets and bottom safe space; then retest jump targets
and combat controls on desktop, tablet and phone. The drawers fit within the
tested widths and their internal scrolling reaches the dice result, but this
does not establish comfortable touch use or software-keyboard behavior.

### P2: Repository checks remain red

The corrected full-suite run reports **246 passed, 1 failed, 2 skipped**. The
failure is `test_aon_creature_cache_without_image_url_still_loads`: its cache lacks
`image_url`, so the service tries a live AoN fetch and now obtains size `Small`;
the test expects an empty size. With network access explicitly unavailable in a
test-only fixture, that same test passes. Make fallback and successful-backfill
expectations deterministic; do not hide the failure or declare full-suite success.

Ruff reports **10 findings** across `maptool_adapter.py`,
`private_image_intake_service.py`, `export_player_prep_pdf.py` and
`migrate_private_local_campaign_data.py`. These include unused imports/variables
and import-order violations. The local JSON output is `ruff.json` in the evidence
directory. These are quality-gate findings, not ten observed runtime failures.

### P3: Reorient the landing page around live play

The warm palette, readable headings and distinct combat cards are coherent.
However, the large introductory hero consumes roughly the first 650 desktop
pixels before Map Room and considerably more than a phone screen. It still says
"Phase 4 Live Assistance" and advertises several archived workflows. Initial
scene counts describe selected live entities, while Add Party PCs can populate
combat independently; that distinction is unclear.

Replace development-stage copy with a compact live-session overview, make the
selected-scene meaning clear, and bring current map/combat/session actions nearer
the top. Preserve the working dock, collapse state and card-based combat.

### P3: Clarify helper-chat and integration status

The floating DMA Chat Workbench runs the older `/api/live/respond` helper rather
than the dedicated W1 campaign-agent/review protocol. Its availability is not
proof of W1 review UX. Session Mechanics is accessible, but its help directs the
DM to configure MapTool in Current Scene, which is intentionally archived. The
drawer does not visibly qualify MapTool as experimental/unconfigured. Make these
boundaries and prerequisites understandable without reactivating archived modules.

## Automated results and interpretation

| Check | Result |
| --- | --- |
| Full backend suite, corrected isolation | 246 passed, 1 failed, 2 skipped; existing Starlette/AnyIO deprecation warning |
| Missing-image cache fallback with network explicitly unavailable | 1 passed; diagnostic rerun of the failing test, not an additional full-suite pass |
| Real MCP protocol integration | 2 passed in the isolated SDK environment; neither skipped |
| Frontend and PDF-precedence Node tests | 14 passed, 1 skipped, 0 failed; skipped PDF check needs private reference material |
| Ruff | 10 findings; gate fails |
| Black formatting check | 21 files would be reformatted, 112 unchanged; no formatting changes applied |
| Git whitespace check | Passed; existing line-ending normalization warnings |

The first backend attempt had five failures. Four were introduced by the QA
runner: an absolute shared cache override defeated per-test `project_root`, and
placing pytest temporary directories inside the repository violated tests that
expect external paths to count as private. Independent AoN test roots and an
external temporary test directory removed those four failures. The remaining
AoN failure reproduced and is recorded above.

Raw browser records also retain early harness mistakes: counting the hidden Vault
Workspace as active, inspecting a dossier before its async load completed, using
an unchanged HP value that emitted no change event, and looking for an affliction
container ID that the application does not use. Corrected checks verified those
behaviors; they are not product defects. Session-launch, unpin, keyboard and
fixed-header findings remain after inspection.

## Screenshots to inspect locally

- `01-desktop-initial.png`: initial workspace and large hero.
- `02-dice-roller.png`: open desktop dice tool and invalid-expression response.
- `05-card-combat.png`: rich combat cards and initiative controls.
- `06-combat-save-failure.png`: simulated outage and retained edit.
- `07-phone.png`: first-screen phone density.
- `09-pc-sheet.png`, `10-npc-dossier.png`: full detail viewers.
- `11-stale-combat-edit.png`: preserved conflicting edit.
- `13-combat-390.png`: shortcut destination hidden beneath status chrome.
- `14-combat-controls-390.png`: fixed dock near card actions.
- `15-mobile-dice-result-390.png`: result reachable by drawer scrolling.
- `16-campaign-bestiary.png`: synthetic bestiary content.
- `17-session-mechanics.png`: integration drawer and current wording.

All filenames above are relative to the ignored evidence directory. They contain
fictional test data only.

## Remaining acceptance boundary

Next: correct session launch, pin behavior and keyboard/viewport issues; make the
AoN regression deterministic and clear static gates; repeat the affected browser
checks; then run a short representative DM rehearsal (start session, investigate
room, fight encounter, record outcome, review recap). Keep W1's fixture-only
guarded agent acceptance separate from live campaign attachment and W2 work.

This assessment does not verify real campaign overlay completeness, paid model
answer quality, live MapTool synchronization, Discord, narrator audio quality,
macOS, physical touch devices, a full accessibility audit or human play-testing.
No archived module was reactivated and no real campaign migration was performed.
The disposable QA server was stopped after testing; screenshots and records remain
available locally.
