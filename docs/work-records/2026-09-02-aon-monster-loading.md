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
