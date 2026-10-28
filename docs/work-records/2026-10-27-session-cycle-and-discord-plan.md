# Session-cycle and Discord development plan — 2026-10-27

## Request and criteria reevaluated before editing

Update the DMA development plan to reflect the browser/agent distinction, the
complete prepare/play/debrief/log/report/next-prep cycle, and staged Discord
publication and player questions.

Sufficient: record responsibilities, ordered deliverables, current gaps,
dependencies, and sufficient/excellent acceptance criteria without claiming
planned behavior is implemented. Preserve existing engineering gates and work.

Excellent: reconcile the roadmap, README, workboard, quality and architecture
documents; define player knowledge/approval boundaries, a full-cycle rehearsal,
and a concrete next slice. Not complete if priorities conflict, Discord can read
GM knowledge unrestricted, archived UI is implicitly restored, or existing
recovery/privacy requirements are dropped.

## Baseline and scope

- Windows, PowerShell Core, repository root verified from the active environment.
- Existing large dirty worktree on `codex/aon-monster-loading` was inspected;
  prior source, test, migration, and documentation work is preserved.
- Read the current roadmap, quality standard, architecture sketch, ownership
  contract, module archive, and Oct 8 priorities record. Reused existing M1-M5
  workstreams instead of replacing their implementation or historical evidence.
- This is a documentation update. No live campaign data, database, secrets, or
  private overlay content was opened or changed. No GitHub refresh/release,
  Discord setup, external message, deployment, or migration was performed.

## Changes and rationale

- Added `docs/22-agent-session-cycle-and-discord.md` as the detailed product plan.
  W0-W6 cover the operating contract, dedicated external agent, closure,
  Discord report publication, connected prep/live help, full-cycle rehearsal,
  and restricted Discord player questions.
- Kept M1-M5 as engineering workstreams and retained full CI, recovery, migration,
  and browser acceptance requirements. Oct 8 evidence stays explicitly dated.
- Made the external agent the intended review surface while preserving the
  explicit browser-module archive. Agent setup and host connectivity still need
  implementation and verification.
- Defined reviewed artifact transitions and separate approvals for candidate
  promotion, GM history, player report, and publication. Player corrections stay
  proposals; the bot does not write campaign facts directly.
- Required player-only source selection before retrieval/context, revision-bound
  report approval, delivery records, safe retries, and explicit hosting decisions.
- Updated roadmap, README, collaboration pointer, architecture, and quality gates
  to use the same delivery order. AoN remains parked and MapTool deferred.

## Verification and achieved level

Documentation checks: re-read modified passages, inspect the scoped diff, check
relative Markdown links and W0-W6 coverage, and check changed-file whitespace.
Code, browser, CI, and live Discord checks are not applicable to this planning
change; their future implementation requirements remain open.

- Relative Markdown links passed across all seven documents.
- W0-W6 each have dependency and sufficient/excellent acceptance coverage.
- Scoped tracked-file `git diff --check` passed. New documents were separately
  checked for trailing whitespace and conflict markers.
- Re-read the active pointers and plan, including the distinction between dated
  engineering evidence and new product priorities. Prior worktree edits remain.

Achieved: excellent for this planning task. Product milestones remain open;
documentation verification does not constitute implementation or play-testing.

## Remaining work

Next: W0 field-level SQL/overlay ownership and explicit agent read/write tool and
approval contract. Then implement and verify the campaign-agent setup. Existing
CI, source traceability, paired restore, and browser verification gaps remain.
Discord server/channel credentials and hosting choices are deferred configuration
inputs, not required to begin W0. This update is local and uncommitted.
