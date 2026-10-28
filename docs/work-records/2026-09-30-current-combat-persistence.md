# Current Combat persistence and recovery — 2026-09-30

## Scope and acceptance criteria

Serialize browser session-state writes, add server-side revision checks so stale
clients cannot overwrite newer state, coordinate reset with pending saves, and
surface failures without discarding local edits.

Acceptance requires a monotonic revision across updates and reset; stale writes
are rejected with a conflict response; autosave, manual save, and reset share one
client request queue; failure leaves local edits visible and retryable where safe;
and focused API, queue, and isolated browser checks cover out-of-order, stale,
failed, and reset-pending scenarios.

## Implementation

- Added a monotonic revision to saved context entries and an Alembic migration.
  SQLAlchemy optimistic versioning also catches concurrent writers that race
  after the API's explicit revision check.
- Live session snapshots return their revision. Panel PUT requests send the
  revision they edited; stale writes and stale resets return HTTP 409 without
  replacing newer state.
- Autosave, manual save, retry, and reset share one serial write queue. Reset
  writes an empty snapshot instead of deleting the row, preserving revision
  history. It waits behind an in-flight save and suppresses queued saves while
  reset is pending.
- Failed writes keep current panel values visible and show Retry Save for
  recoverable request failures. A 409 requires reload/reconciliation and does
  not offer an unsafe blind retry.
- Browser verification exposed a startup no-op save: loading PC sheets committed
  any active encounter even if it contained no PCs. Party refresh now returns
  unless the encounter has a PC combatant, avoiding an unnecessary revision bump
  for monster-only encounters.
- The fixture also exposed that GET `/reference-corpus/status` invoked the AoN
  initializer and tried to rewrite a private overlay manifest during page load.
  Replaced it with a read-only status method and added a unit test that confirms
  it creates no directories and leaves existing manifest/normalized files intact.
- Added API revision/conflict coverage and frontend queue tests for failure
  continuation, reset ordering, and retaining local state after a stale revision.

## Verification

- `python -m pytest -q tests/integration/test_live_api.py`: 23 passed.
- `python -m pytest -q tests/unit/test_private_index_service.py`: 4 passed.
- `node --test tests/frontend/*.test.js`: 7 passed.
- `python -m pytest -q`: 141 passed.
- `python -m pytest -q tests/integration/test_live_api.py tests/unit/test_private_index_service.py`:
  27 passed after the browser-check fixes.
- Focused Ruff checks passed for the changed Python model, service, route, and
  integration/unit tests. Python compilation passed for changed Python files.
- `git diff --check` passed. It reported an existing `.env.example` line-ending
  normalization notice; no whitespace errors were reported.
- Migration file and parent revision were inspected. Installed the repository-
  declared Alembic 1.14.0 development dependency and ran the complete upgrade
  against a disposable SQLite database using the async SQLite URL. Upgrade
  reached `20260930_0004`; `contexts.revision` was present. The temporary
  database was removed. The live campaign database was not migrated.
- Exercised the production panel at `127.0.0.1:8765` against the in-memory test
  app with 800 ms write delays and a one-shot injected 503. Rapid HP/initiative
  edits produced two ordered revisions and the latest values. A failed autosave
  kept HP 16 visible; keyboard activation of Retry Save persisted it. Reset
  queued behind an in-flight save, disabled controls while pending, and produced
  an empty snapshot at a newer revision. An external fixture save caused HTTP
  409; the local scene text remained visible and blind retry was hidden.
- In the browser fixture, reload did not change the revision for a monster-only
  encounter after the startup-save guard. Keyboard checks covered HP and
  initiative entry, deterministic equal-initiative sorting, condition add and
  remove, Next/Previous Turn, Retry Save, reset, and Current Scene form submission.
  Keyboard focus styling was visible on a combat input. A panel GET initially
  attempted to replace the existing AoN overlay manifest and received a permission
  error. The manifest timestamp and all category `normalized.json` timestamps
  remained at their pre-run September 2 values; the failed write's temporary
  staging file was removed. The fixture database was in memory; the private
  overlay has no remaining changes from the verification.
- The automated tests cover API revisions/conflicts, serial queue failure
  continuation, and reset ordering. Delayed-request UI behavior, retry controls,
  keyboard paths, and stale-panel presentation were manually exercised in the
  isolated browser fixture; they are not a committed end-to-end browser suite.

## Limitations and follow-up

This work protects cooperating DMA clients. Apply the repository's Alembic upgrade
before running this code against an existing database; the migration was verified
on a disposable database but not applied to the live campaign database. Recovery
is local to the running panel; cross-device offline merge is out of scope. M1's
core queue and API regression coverage is in place. A committed browser suite for
delayed/failing saves, retry controls, reset races, and keyboard flows remains a
follow-up if those UI-level paths need to run automatically in CI.
