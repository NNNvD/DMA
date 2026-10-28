# Current Combat persistence — task start and completion — 2026-09-02

## Scope and criteria

This slice improves recovery feedback without changing the server-backed
combat-state format. Sufficient completion requires combat state to load and
save as before, with failures surfaced clearly. Excellent completion adds an
explicit visible status for loaded, saving, saved, and failed-save states.

## Implementation

- Added a polite live status region beneath the Current Combat metadata.
- The status now reports when combat state is loaded from the server, when a
  change is being saved, when saving succeeds, and when saving fails.
- Existing debounced server persistence and normalized state handling remain
  unchanged.

## Verification

- Full test suite: `139 passed`.
- Live DM panel loaded successfully.
- The visible status `Combat state loaded from the server.` was present after
  page initialization.
- Temporary verification data was archived after the server was stopped.

## Follow-up

The next persistence pass can add a deliberate refresh/recovery interaction
test after a combat mutation, if we want stronger end-to-end coverage of the
server round trip.
