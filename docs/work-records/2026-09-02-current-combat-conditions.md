# Current Combat conditions — task start and completion — 2026-09-02

## Scope and criteria

This slice improves condition usability without changing the PF2e condition
model or countdown rules. Sufficient completion requires condition values to be
visible, conditions to be removable, and existing persistence/countdown logic
to remain intact. Excellent completion additionally requires accessible labels
and live-panel verification.

## Implementation

- Added accessible `Remove condition` labels to condition badges.
- Added an accessible `Condition value` label to condition value inputs.
- Corrected the compact combat status rendering so an empty condition list is
  not treated as an active HTML status value.
- Preserved existing condition timing and turn-countdown behavior.

## Verification

- Full test suite: `139 passed`.
- In-app browser loaded the live DM panel.
- A Ghoul was added to Current Combat.
- `Frightened 2` was added and displayed with its value.
- The accessible removal control appeared and removed the condition.
- After removal, the detailed panel returned to `No conditions`.

## Follow-up

Condition countdown behavior remains covered by the existing session-state
tests and can receive a dedicated turn-advancement UX pass later.
