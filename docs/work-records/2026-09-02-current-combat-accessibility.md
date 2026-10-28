# Current Combat accessibility and visual polish — task start and completion — 2026-09-02

## Scope and criteria

This slice improves keyboard visibility and semantic labels without changing
the Current Combat layout or visual identity. Sufficient completion requires
the combat controls to remain usable and visually coherent. Excellent
completion additionally requires accessible names for mutable combat fields
and a consistent visible focus treatment.

## Implementation

- Added a visible `:focus-visible` outline for Current Combat buttons, inputs,
  selects, and disclosure summaries.
- Added accessible names for monster and PC current/max HP fields.
- Added accessible names for manual initiative inputs.

## Verification

- Full test suite: `139 passed`.
- Live DM panel loaded successfully.
- After adding Mitflit, the rendered card exposed `Mitflit initiative`,
  `Mitflit current HP`, and `Mitflit maximum HP` accessible names.
- Temporary verification data was archived after shutdown.

## Follow-up

Responsive layout and broader keyboard traversal can receive a separate visual
QA pass if the panel is used on smaller screens or with a screen reader.
