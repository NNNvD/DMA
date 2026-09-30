# AoN monster loading — task start — 2026-09-02

## Pre-task reevaluation

The task is to verify and, if necessary, fix Archives of Nethys (AoN) monster
loading in the active card-based Current Combat module. The repository is on
`codex/aon-monster-loading`, with public checkpoint `3e50161` on `main` and
the task-completion policy in commit `a4824e6`. The private campaign bundle
under `assets/imports (1)/` remains excluded.

## Sufficient completion

- Representative valid AoN monsters load through the intended local data/API
  path and render in card-based Current Combat.
- Missing, malformed, and unavailable data fail safely with an understandable
  user-facing state.
- Regression tests cover the diagnosed failure and pass.
- The real frontend flow is operated and visually checked.
- No private campaign or spoiler-sensitive data is exposed in player-facing
  views.
- The work record documents reproduction, cause, decision, implementation,
  verification evidence, and remaining limitations.

## Excellent completion

All sufficient criteria pass, plus representative creature variants and edge
states are covered, loading/empty/error states are polished, browser automation
covers the user path, performance is acceptable for live use, and the fix is
documented with reusable test/support tooling where appropriate.

## Not complete

The task is not complete if a critical loading failure remains, required tests
fail, the actual interface is not verified, spoiler leakage is possible, or
the rationale and limitations are undocumented.

## Next evidence to collect

- Baseline frontend rendering and Current Combat interaction.
- Network/API response for AoN monster loading.
- Relevant fixture and private-overlay data shape.
- Test and browser verification results.

## Baseline findings

- The local API serves the static DM panel at `/dm-panel` and the AoN search
  endpoint responds for `mitflit` with the indexed creature ID `3031`.
- Fetching `/api/live/aon-creature?creature_id=3031` fails in this environment
  when no local cache is found because outbound access to AoN is blocked.
- The service currently resolves its cache under
  `assets/imports/misc/aon-creatures/raw`; the expected root overlay is not
  present in this checkout, while the untracked `assets/imports (1)/` tree
  contains private campaign data and must remain excluded.
- The static panel contains duplicate definitions of the AoN loading and
  combat-conversion functions. The later definitions override the earlier
  ones, so the active behavior needs to be confirmed before changing it.
- The in-app browser could not open the local server and returned
  `ERR_BLOCKED_BY_CLIENT`; direct local HTTP checks remain available, but the
  visual/user-flow criterion is not yet satisfied.

## Implementation result

- Updated `AonCreatureService` to resolve its cache through the configured
  private-data root, including the standard root overlay when present.
- Added a regression test proving that an available overlay cache is preferred.
- Removed the duplicate, later AoN picker/conversion/addition definitions from
  the static panel so the richer active implementation is not silently
  overridden.
- Verification: 31 focused AoN/live API tests passed; the full suite passed
  with 139 tests; focused Ruff checks passed.
- Full-repository Ruff still reports 11 unrelated existing issues, including
  lint findings in the previously checkpointed migration script.

## Completion assessment

**Sufficient completion achieved.** The data-routing fix and duplicate-function
cleanup are tested and documented. **Excellent completion is deferred** until
the frontend can be operated and visually verified in a browser-compatible
environment, and representative cached creatures plus user-facing error and
empty states can be checked in the live interface.

## Live browser evidence

- The local `/dm-panel` page rendered successfully in the in-app browser.
- Current Combat displayed the card-based picker, search field, AoN creature
  select, and Add Monster control.
- The default Mitflit flow was operated. The picker remained stable and
  displayed the network/cache failure inline: `Could not fetch PF2e creature
  data from Archives of Nethys`.
- The UI did not crash and no spoiler-sensitive content was exposed by the
  failure state.
- Completion is blocked pending an approved current private overlay containing
  the AoN creature cache at the configured overlay path, or explicit direction
  to use the untracked `assets/imports (1)/` bundle for local-only verification.

## Overlay follow-up and successful verification

- The approved overlay now contains 12 valid creature files at
  `assets/imports/misc/private-local/reference/aon/creatures/raw/`, including
  Mitflit `3031`.
- After restarting the server, `/api/live/aon-creature?creature_id=3031`
  returned HTTP 200 with the expected stat block fields.
- In the browser, after allowing the panel's initial asynchronous loading to
  finish, Add Monster successfully added Mitflit to Current Combat. The card
  displayed HP 10/10, AC 14, Perception +4, level, traits, and source metadata.
- The browser search empty state was also verified with a non-matching query:
  `No PF2e creatures matched that search.`
- The earlier failure was caused by the cache path not matching the overlay's
  actual `reference/aon/creatures/raw` layout, compounded by the absent cache
  in the original checkout.

**Sufficient completion remains achieved and is now browser-verified.**
Excellent completion remains optional follow-up work: exercise more
representative creatures and polish or verify remote image loading where the
browser/network permits.
