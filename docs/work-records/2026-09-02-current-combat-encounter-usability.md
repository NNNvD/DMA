# Current Combat encounter usability — task start and completion — 2026-09-02

## Scope and criteria

This first Current Combat improvement targets live encounter readability. The
sufficient criterion is that healthy, low-HP, and defeated combatants are
visually distinguishable in both the compact initiative strip and the full card
without changing initiative, condition, or persistence rules. Excellent
completion additionally requires explicit accessible status text and verified
user-level behavior in the live panel.

## Implementation

- Added derived HP states: healthy, low HP (25% or less), and defeated (0 HP).
- Added distinct card and initiative-strip styling for low-HP and defeated
  combatants.
- Added accessible labels and visible status text for the derived state.
- Kept existing combat rules, persistence, initiative, and condition handling
  unchanged.

## Verification

- Full test suite: `139 passed`.
- In-app browser loaded the DM panel successfully.
- A Giant Scorpion was added to Current Combat.
- Repeated user-style `-10` HP controls reduced it to 0 HP and produced the
  explicit `Defeated` state in the card and initiative strip.
- Existing AoN creature selection remained available.

## Follow-up

Direct manual text-entry HP changes should receive a separate focused check in
the next pass if we decide that input-event behavior needs additional hardening.
