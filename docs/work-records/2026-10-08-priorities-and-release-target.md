# DMA priorities and release target review — 2026-10-08

## Scope and completion criteria

Review the plan against repository evidence, completed work, current risks, and
the next release target. Sufficient completion means the roadmap and workboard
identify the active priorities and do not describe completed work as upcoming.
Excellent completion adds a bounded release target with evidence-based exit
gates and reconciles known status conflicts. This is a planning review; it does
not authorize a commit, publication, campaign migration, or private-data access.

## Evidence baseline

- Local branch: `codex/aon-monster-loading`; HEAD `01bceb3`.
- Working tree contains 56 modified or untracked paths. This review did not
  compare against a fresh remote state; no release state is claimed.
- The immediately preceding M2 slice recorded 16 passing focused API/service
  tests and a disposable Alembic upgrade through `20261007_0006`. A broader
  Windows run reported 19 passed and 2 setup errors because `%TEMP%` access was
  denied before those vault-test bodies ran.
- Sep 30 records document 141 passing Python tests, Node coverage, and isolated
  browser verification for combat persistence. Oct 7 panel module archive work
  was not browser-verified after the archive changes.
- Static inspection confirms collapse/expand handlers remain in the panel,
  archived IDs remain out of active menus/layout, and Dice Roller is the sole
  default pin. Automated archive assertions do not prove rendered behavior.
- No live DB or private overlay was read, migrated, copied, or changed.

## Completed work

1. **M1 combat reliability:** condition magnitude and optional duration are
   separated; Previous Turn is navigation; versioned writes, conflict handling,
   save ordering, reset coordination, and retry/reload states are implemented.
   Focused automated and historical isolated-browser evidence exists.
2. **M2 review foundation:** SQL/overlay ownership inventory and contract;
   pending review drafts; approved-session-history filtering; candidate baseline
   conflicts; explicit accepted/rejected/deferred decisions; atomic accepted
   candidate promotion; durable candidate provenance; disposable migration and
   API regression evidence.
3. **M3 recovery/archive groundwork:** panel shell fallback, explicit ten-module
   archive manifest and regression assertions, restored collapse controls, and
   Dice Roller as the sole default pin. Archive scope and reactivation gate are
   explicit in `docs/21-dm-panel-module-archive.md`.
4. **Governance:** root private-overlay location and non-public boundary are
   documented; Obsidian workflows are marked compatibility/retired; AoN policy
   is recorded. No source expansion or live migration occurred.

## Open risks

| Risk | Effect | Evidence / response |
| --- | --- | --- |
| Worktree is large and uncommitted; HEAD is an older code checkpoint | No reproducible release artifact; public/private path review is still required | 56 paths changed/untracked; isolate and inspect explicit deliverable paths before any release operation |
| Full current CI is unverified | Lint/type/full-suite failures may remain outside the focused slices | Run `make ci` in the declared Python 3.11 environment; address the pytest temp-root permission issue first |
| Post-archive panel experience is not browser-verified | Collapse, pin, navigation, keyboard, or narrow-screen regressions may remain | Exercise active panels after archive; verify Dice Roller pin and collapsed-state persistence |
| Session Update Review UI is archived | New staged review workflow is API-only in the active panel | Keep archive intact; an interactive GM release must first select and approve an alternate surface or deliberate reactivation |
| M2 source ownership/prep traceability incomplete | Prep inputs are hard to explain; SQL/overlay overlaps could drift | Map field-level owners; record accepted source IDs/revisions in prep; avoid sync/migration before contract is approved |
| Backup/restore not rehearsed | Recovery is not established for the paired database and private overlay | Rehearse with disposable fixtures, then separately approve any real-data operation |
| New Alembic revisions have fixture-only evidence | Existing local DB upgrade path remains unverified | Continue disposable upgrades; require backup and recovery approval before any live migration |
| MapTool protocol mismatch | Current adapter cannot claim stock MapTool compatibility | M5 remains deferred pending a real HTTP bridge/plugin/sidecar and verified mapping |

## Priority order

1. **Reproducible quality checkpoint:** run the full declared CI set from a clean
   Python 3.11 environment; fix the temp-root setup limitation and resolve any
   real failures. Keep the working-tree path set explicit.
2. **M2 data explainability and ownership:** specify the field-level SQL/overlay
   contract, then make prep record accepted campaign/session source IDs and
   revisions. Keep the session-review module archived unless the user explicitly
   changes that decision.
3. **M2 recovery gate:** rehearse database and overlay backup/restore together
   with disposable fixtures, checking the restored campaign/session state and
   recording the recovery steps.
4. **M3 panel verification and maintainability:** browser-check the archived
   layout and controls, then address duplicate frontend functions and full
   repository formatting/type-check gaps.
5. **M4/M5:** keep model-grounding expansion and integrations/content expansion
   deferred until M2 ownership and M3 quality gates pass. MapTool remains
   specifically deferred until a compatible bridge exists.

## Next release target

Target an **unversioned local engineering checkpoint**, covering the active
Current Combat and panel modules plus the staged review API. Do not call this a
public release or a complete GM-facing M2 release: the current tree is uncommitted,
full CI is not current, backup/restore is untested, and staged review has no active
panel UI by explicit choice.

The roadmap's checkpoint exit gates are: reviewed public-safe deliverable paths;
full CI in the supported environment; a disposable clean-install/upgrade and
backup/restore rehearsal; and post-archive browser verification of collapse,
pinning, navigation, keyboard, and small-screen behavior. A later GM release that
claims a guided session-to-prep flow needs an approved interactive review surface
and prep source traceability. No release number is proposed because the repo has
no release tag or current version target.

## Plan updates and achieved level

- `docs/05-roadmap-and-milestones.md` now records the worktree evidence, M1–M3
  status, release target, and gates.
- `COLLAB_TASKS.md` no longer lists the completed combat persistence slice as
  the next task.
- The Oct 7 panel-controls work record now explains that Session Soundboard's
  temporary default-pin restoration was superseded by the explicit archive
  decision.

Excellent completion for this planning review. The review remains local and
unpublished; no implementation, test execution, database migration, or live
browser check was performed on 2026-10-08.
