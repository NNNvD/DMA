# In-Game State overview and browser chat retirement

Date: 2026-10-28. Windows / PowerShell, Python 3.11. Local-only changes on
`codex/local-reconciliation-20261027`.

## Result

The DM panel now has a right-hand **In-Game State** overview with location and
linked map, campaign day/weekday/month/year, time of day, weather and environmental
effects. Scene, Focus, Active NPCs and the former summary-card row are absent from
the top panel. The fixed header repeats location, day/time and current combat.

DMA Chat Workbench is explicitly added to the archive manifest and documentation;
there are now eleven archived modules. Its floating launcher is removed and its
startup rendering is suppressed. Its retained source and compatibility REST API
do not provide an active browser chat. The dedicated campaign agent in Codex or
the IDE remains the conversation surface. No other archived module is reactivated.

The editor supports free-form locations, optional linked maps, exposure, climate,
calendar selection, manual calendar/date/time input and independent pinned weather
and environmental overrides. Automatic conditions recompute on relevant context
changes. A reproducible local weather table uses climate, season, date and time;
refreshing the page or saving combat does not reroll conditions. Explicit reroll
changes the weather seed. Indoor and underground views are sheltered from outdoor
weather effects. Generated effects are descriptive suggestions, not numerical
PF2e rules changes.

## Persistence and calendar contract

`PATCH /api/live/in-game-state` requires the current live-state revision and
updates only the nested workspace inputs. The browser uses the existing shared
serial write queue. Legacy combat/live-state saves preserve environment inputs;
environment saves preserve combat. Reset clears both in the revisioned context.
Failures leave the editor's values available for retry. Stale revisions fail with
409 instead of silently replacing another panel's state.

Calendar schemas accept existing string month lists plus optional structured
month lengths/seasons and weekday anchors. Season and fixed-calendar weekdays can
be derived when metadata supports them; unknown calendars permit explicit manual
values without Gregorian assumptions. A removed calendar or changed month length
does not make a saved workspace unreadable; it produces a reconciliation warning.
Workspace day edits do not alter accepted campaign calendars or private overlay
records. No database migration is needed for this nested context data.

The old session-launch constants were removed as part of updating this panel.
Launch now opens the selected available session, checks the note load result,
uses any linked map and preserves tracker/state inputs. It saves an open state
editor before proceeding rather than replacing its unsaved values with a refresh.
It no longer reports Session 04/C7 success after a failed note request.

## Verification

- **11 focused backend tests pass**, covering custom calendars, seasonal and
  weekday derivation, deterministic generation, pinned overrides, indoor effects,
  stale revisions, invalid values, mutual combat/environment preservation, reset,
  location profiles and unavailable calendar handling.
- **257 backend tests pass, one fails, two skip** in the final full isolated run.
  The failure is the previously identified network-dependent
  `test_aon_creature_cache_without_image_url_still_loads` (`Small` versus an empty
  size after successful remote backfill). It was not modified or hidden. The two
  optional MCP SDK modules are unavailable in that backend environment; this run
  is not a new native agent or human play-test.
- **14 Node tests pass, one private-reference PDF check skips**. The archive
  regression manifest includes the explicitly authorized workbench addition.
- **13 rendered Edge checks pass** at desktop, tablet and phone sizes. They cover
  removed summary/chat UI, hidden manual fields, automatic custom-calendar season
  and weekday updates, night effects, pinned overrides and reloads, indoor shelter,
  reroll, injected 503/retry, combat preservation, corrected session launch and
  responsive control bounds. No unhandled JavaScript exceptions were recorded.
- Standard-library statement tracing reports **91.6%** (207/226 executable lines)
  for the new environment service. This is focused statement coverage, not branch
  or whole-repository coverage.
- Ruff passes for the changed Python routes/services and new tests. Black passes
  for the new service, modified live-state service and new tests. Git whitespace
  checks pass with existing line-ending warnings. Earlier repository-wide static
  findings remain outside this UI slice.

The initially failing browser calendar seed exposed that the old campaign API
accepted only string months. The backward-compatible structured-month extension
now has a campaign-API integration regression. Visual review also caught a global
label layout rule overriding the `hidden` attribute; a scoped rule and rendered
check now ensure manual fields stay hidden in Automatic mode.

## Local evidence and inspection

The actual app remains served from the disposable fictional QA database and
overlay. The marked fixture includes an explicitly fictional Belltide calendar;
no real campaign database or private overlay was selected or edited. Nothing was
committed, pushed or deployed.

Ignored local evidence:

- `.codex-temp/ui-qa-20261028-c/in-game-state/browser-results.json`.
- `02-desktop-final.png`, `03-header-768.png`, `03-header-390.png`,
  `04-editor-768.png`, `04-editor-390.png` in that same directory.
- `.codex-temp/in_game_state_browser.cjs`: repeatable marked-fixture browser check.
- `.codex-temp/in-game-state-coverage.json`: focused statement metrics.

See [the user-facing behavior and storage contract](../26-in-game-state.md).
Live campaign activation, richer regional weather/forecast models, leap-calendar
rules, touch/soft-keyboard validation and human play-testing remain separate work.
