# Current Combat condition semantics — 2026-09-30

## Scope and acceptance criteria

Correct the condition magnitude/duration conflation in the card-based Current
Combat panel. Condition value remains descriptive severity or magnitude. An
optional, separate duration counts down at the end of that combatant's turn.
Previous Turn remains navigation only and does not undo a completed turn.
Legacy conditions without a separate duration must remain unchanged.

Completion requires focused regression tests for the pure duration rules and
checks that the panel wires duration separately, preserves legacy values, and
does not tick conditions when navigating backwards. Browser interaction evidence
is recorded separately from automated code checks.

## Implementation

- Added a separate optional `durationTurns` field and duration input. The existing
  condition value remains magnitude or descriptive detail; only the separate
  positive integer duration counts down after that combatant's turn.
- Existing conditions without `durationTurns`, including legacy numeric values,
  are preserved and are not silently reinterpreted or decremented.
- Defined Previous Turn as navigation only. It does not reverse condition changes
  already applied when a creature's turn ended.
- Kept the condition transition rules in a small browser/CommonJS module so the
  exact production logic can run in Node's built-in test runner.
- Added the frontend test target to `make ci` and configured Node.js 22 in CI.
- Updated the operations guide and panel help text with the semantics.

## Verification

- `node --test tests/frontend/*.test.js`: 4 passed; `node --check` passed for the
  helper and test files.
- `python -m pytest -q`: 139 passed, including the live API route and script checks.
- Focused Ruff checks for the changed Python route and integration test passed.
- `git diff --check` passed for the implementation scope.
- Operated the live panel in an isolated in-memory fixture. The legacy `Frightened
  2` stayed at 2 after its turn; a separate two-turn duration remained 2 through
  Previous Turn navigation and became 1 only after that combatant acted. The
  fixture's browser console had no errors. No actual campaign session data was
  modified during browser verification.

## Limitations and follow-up

Excellent completion for this condition/turn semantics slice. The rest of M1,
especially save ordering, reset races, failed-save recovery, and broader keyboard
interaction coverage, remains open. Durations currently expire at the end of the
affected creature's turn; condition-specific expiry triggers are future work.
