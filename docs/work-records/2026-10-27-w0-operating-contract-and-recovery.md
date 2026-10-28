# W0 operating contract and paired recovery — 2026-10-27

## Scope and reevaluated completion gates

Implement W0 from the active session-cycle plan: define field ownership,
campaign/session identity, source visibility, tool read/write boundaries, trusted
DM approval, conflict handling, and paired database/overlay recovery. This slice
retains existing storage and archived modules; the W1 agent connection is separate.

- Sufficient: source-backed field/API mapping and approval contract, actionable
  recovery procedure, explicit current implementation gaps, and safe fictional
  data fixtures. No live campaign access or implicit sync/migration.
- Excellent: repeatable paired restore, retained pending/rejected/deferred state,
  provenance and prep checks after restart, stale-write recovery, and meaningful
  refusal tests for damaged snapshots and overwrite attempts.
- Incomplete if the contract suggests unsafe raw APIs already enforce trusted
  approval, the rehearsal can overwrite live stores, required checks fail, or
  the evidence conflates fixture recovery with a live recovery guarantee.

## Delivered

Added `docs/23-agent-operating-and-data-contract.md` with field-level SQL/overlay
owners, source-qualified references, session association requirements, current API
primitives versus planned agent tools, a one-campaign-per-database binding, and
explicit approval/visibility/conflict rules. It identifies existing limitations:
global live-state keys and unscoped entity/document rows; absent session linkage;
overlay/vault write fallback; no overlay CAS; no trusted approval ledger; and
the remaining concurrent-writer/revision-bound review work. Agent mutation stays
gated on W1 enforcement. The self-reported reviewer field is not authentication.

Added `scripts/rehearse_campaign_recovery.py`. It has no live DB/overlay input:
it creates a new workspace, migrates a fictional SQLite DB, creates a matching
overlay with session notes and settlement data, stages approved/rejected/deferred/
pending review cases, and snapshots both stores with a paired identity and file
checksums. It uses SQLite backup for committed WAL data, restores into a fresh
destination, restarts the campaign/live/prep APIs, and checks the recovered pair.
Original fixture stores and snapshot remain available. A completion marker is
written only after restore validation; the report is written only after API checks.

The command refuses existing workspaces, protected data/Git roots, and execution
in a process that has already loaded backend settings. This prevents inherited
configuration from selecting a live DB. Tests additionally prove explicitly
supplied environment paths are not used as rehearsal inputs.

Updated README, roadmap, collaboration workboard, and ownership/session-cycle
docs to record W0's completed contract/fixture scope and hand off to W1 binding,
durable instructions, and verified read tools. Removed the stale statement that
candidate provenance was absent. No agent gateway is installed by this slice.

## Verification

Windows PowerShell, Python 3.11; local `codex/local-reconciliation-20261027`
working tree based on `70516ad`, including the existing uncommitted work.

- **15 tests passed:** 7 new unit cases, 2 new CLI integration cases, and the 6
  existing session-review API tests. Tests cover WAL completeness, corruption,
  missing files, path escape, pair mismatch, existing-target refusal, preloaded
  settings refusal, and the complete restarted-service recovery workflow.
- A standalone run saved an ignored fixture package at
  `.codex-temp/w0-recovery-20261027/`. See `report.json`,
  `snapshot/manifest.json`, and `restored/RESTORE_COMPLETE.json` there.
- All seven behavioral checks passed: schema/integrity; live state/revision;
  overlay session and settlement paths; accepted facts/approved history reaching
  prep; provenance/idempotent retry; stale live write plus successful fresh save;
  and stale candidate baseline preserving a newer entity edit.
- Clean fixture migration reached `20261007_0006`; source and restored pair use
  a shared fictional recovery-set identity. No production marker or schema
  migration was added for W0.
- Ruff and Black's formatter API passed for the three new Python files.
  `git diff --check` passed. The WAL unit case caught temporary sidecars entering
  the initial inventory; the snapshot now checkpoints into a self-contained DB
  before checksumming and inventories only intended members.
- No frontend changed, so rendered-browser and play-test evidence are not
  applicable to W0. The earlier browser-readiness check is separate evidence.

## Limits and handoff

Excellent completion for W0's contract and fictional recovery scope. The
rehearsal assumes paused writers and verifies SQLite only; it is not an online
cross-store transaction or a general-purpose live backup/restore command.
Restoring older revisions requires closing clients and invalidating cached
approvals. Current APIs do not enforce a recovery epoch.

W1 must implement and verify the trusted agent binding/read tools, durable session
references, and revision-bound approval executor before agent mutations are
enabled. Live recovery still needs a reviewed copy map, retained originals,
approval, and campaign-specific verification. Full CI/format/type/browser gates
and the inherited failures documented in the reconciliation record remain open.
Everything remains local and uncommitted; no push, Discord connection, source
acquisition, live campaign read, or live migration was performed for W0.
