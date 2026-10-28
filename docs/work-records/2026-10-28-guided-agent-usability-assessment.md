# Guided DMA agent usability assessment before the DM manual

Date: 2026-10-28. Branch: `codex/dma-agent-and-in-game-state-20261028`.
Scope: code/document inspection and local planning changes, not implementation or
a live campaign interaction. The committed checkpoint at assessment start is
`db31e95`; this follow-up is uncommitted and has not been pushed.

The DM requests a setup and before/during/after-session manual, preceded by more
automated, friendly preparation and closure. Desired behavior includes numbered
choices, source-based suggestions, proactive relevant reminders, learning from
responses and appropriately timed feedback that improves operation.

## Findings

- The guarded agent currently exposes eight read tools and four receipt/review
  tools. It does not expose workflow interviews, prep artifact storage, player
  reports, preferences or feedback tools.
- The launcher calls `codex exec --ephemeral` with one prompt. Verified restart
  recovers explicit session/review records; it does not establish a convenient
  ongoing interview or durable DM preference system.
- `PrepService.generate_session_brief` already assembles approved recent sessions,
  hooks, continuity, spotlight and scene seeds. Reuse that foundation while adding
  source-bound guided choices, artifact identity and next-session handoff.
- W1's operator approval console is a useful security boundary, but repeated exact
  hash/receipt commands are not the target day-to-day DM interaction. Improve
  trusted review presentation without giving the campaign agent grant authority.
- Browser operational state is separate from accepted history. A proper event
  inbox and debrief are needed; combat state cannot serve as the complete log.

## Planning change

Added [the guided workflow and feedback contract](../27-guided-agent-workflows-and-feedback.md)
and aligned the roadmap, session-cycle plan, README and collaboration pointer.
Preserved W0–W6 IDs. Preferred order is now W2a durable workflow/capture and scoped
learning records plus interactive entry; W2b debrief, reviewed GM log/player
reports/handoff; W4a guided preparation; local W5 rehearsal; then the verified DM
manual. Optional Discord publishing follows that local usability gate.

The contract distinguishes session choices, facts, intentions, preference
suggestions, confirmed preferences and feedback. Adaptation must be inspectable,
scoped, correctable and usable after restart; it does not mean model training,
automatic prompt/code edits or broader permissions. It includes feedback opt-out,
reminder snooze/dismiss and honest save failures. Draft autosave requires a defined
operator-authorized scope; it does not make every conversational choice canonical.

No new application behavior, tools, grants, model changes, schedules, notifications,
Discord actions or real campaign attachment are introduced by this assessment.
The requested end-to-end manual is deliberately not written as though these
missing workflows already exist. Next implementation starts with W2a.

## Validation

Local Markdown targets and Git whitespace were checked. No runtime tests were
needed for this documentation-only update. Existing W1/UI test results remain
dated evidence, not proof of the planned guided experience. Native interaction,
interrupted interview recovery, player-safe reporting, confirmed preference reuse
and a human DM rehearsal are explicit acceptance gates in the new contract.
