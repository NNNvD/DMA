# Guided workflow implementation and fictional rehearsal

Date: 2026-10-28. Windows / PowerShell, backend Python 3.11, local development
branch `codex/dma-agent-and-in-game-state-20261028`. This follow-up is not committed
or pushed. No live campaign was attached or altered.

## Implemented scope

Added `GuidedStore` and the trusted `run_guided_campaign` operator runner. W1's
MCP inventory, restrictive host launcher, agent profile and approval implementation
are unchanged. The runner checks generated-fixture identity and OS operator,
stores only private workflow drafts in a separately scoped sidecar, and delegates
source-grounded initial/final briefs to the existing restricted Codex agent.

The implementation supports guided/quick questions, numbered/combined/free-text
answers, follow-up details, skip/back/pause, revisioned corrections, notes,
same-session resume, working handoff, confirmed detail/feedback/reminder settings,
optional feedback and explicit remember/forget. Writes use transactions and
idempotent retry keys; changed answers invalidate draft/report approvals. A scope
change blocks writes. Agent failures do not erase saved answers. Changed source
snapshots during generation reject the proposed draft rather than call it current.

Prep produces a private agent runbook. Debrief retains a private GM account,
proposed review text, explicit player recap text and next-prep intentions. Full and
short player recap drafts use only the operator's revealed-text field. The trusted
report approval preview contains **only those player reports**, not the GM log or
feedback, and binds exact content/revision/audience to interactive confirmation.
No sharing or publication occurs. This approval is separate from accepted facts
or GM-log approval; those still require W1's existing review process.

The [trial guide](../28-guided-agent-prototype.md) states prerequisites, commands,
storage/recovery boundaries and missing parts of the broader interaction contract.

## Evidence

- **35 focused tests passed**, covering twelve new workflow cases plus existing
  restricted reader/launcher behavior. New cases include interrupted interviews,
  correction, quick mode, scope isolation, retry conflicts, preference whitelist
  and forgetting, secret separation, stale report rejection, native failure and
  changed-source rejection.
- **269 full backend tests passed, one failed, two skipped** in the isolated
  backend run. The remaining failure is the already recorded network-dependent
  AoN cache expectation (`Small` versus empty size). Optional MCP SDK modules are
  skipped in that environment; this run does not claim full CI success.
- A real restricted native Codex preparation run produced and saved a cited
  runbook; reopening the operator store recovered it. The agent identified the
  missing exact session association and unsupported bridge-lead details, rather
  than inventing approved facts. An initial native attempt failed with saved
  answers retained; the later run succeeded. No unsupported cause is asserted.
- The actual terminal debrief runner completed a quick-mode fictional interview
  with simulated operator answers and sharing review deliberately skipped. Its
  private account contained a hidden-patron sentinel while its player report
  contained only the explicitly revealed bridge crossing. It retained the next
  intention to return to town and left canon/publication unchanged.
- A separate real native Codex debrief run then saved a GM-private review brief;
  the operator store retained the handoff, excluded the sentinel from the player
  approval packet and confirmed no approval had been granted.
- Focused Ruff and Black and Git whitespace checks passed. Existing wider static
  findings remain outside this slice. Documentation links were checked locally.

Ignored evidence: `.codex-temp/guided-native-rehearsal.json`,
`.codex-temp/guided-debrief-native.json`, and the explicitly fictional fixture's
`guided-workflows.sqlite3`. Simulated operator input and protocol tests are not
evidence of a representative human play-test or human approval.

## Remaining acceptance work

This is the first usable fixture prototype, not completion of W2/W4/W5 or the
entire document-27 contract. Canonical staging/log acceptance still requires the
W1 operator workflow; packet-to-review integration without copying remains open.
The current question sets adapt through mode, skip/back/correction and detail
follow-up, not a general learned question-selection policy. Player report
formatting is deliberately conservative and uses explicit revealed text; richer
source-constrained narrative templates remain open. Reminder snooze/dismiss UI,
broader/global preferences, sidecar-aware recovery, native application/IDE chat
controls, live onboarding and a human usability rehearsal remain required before
the final end-to-end DM manual. Nothing is published to Discord or scheduled.
