# Current Combat initiative workflow — task start and completion — 2026-09-02

## Scope and criteria

This slice improves initiative clarity without changing the existing roll,
manual-edit, turn, or round model. Sufficient completion requires the controls
to remain available and turn navigation to persist. Excellent completion adds
deterministic tie ordering and explicit semantic active-turn state.

## Implementation

- Added a deterministic case-insensitive name tie-breaker after initiative
  total and initiative bonus comparisons.
- Added `aria-live="polite"` to the turn metadata region so round and active-turn
  changes are announced to assistive technology.
- Added `aria-current` to the active initiative-strip chip.

## Verification

- Full test suite: `139 passed`.
- Live DM panel loaded successfully.
- Initiative controls `Roll All Initiative`, `Previous Turn`, and `Next Turn`
  rendered successfully.

## Follow-up

Manual initiative editing and multi-combatant tie behavior can receive a more
extensive interaction test in a later persistence-focused slice.
