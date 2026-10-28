# Local main reconciliation — 2026-10-27

## Scope and completion criteria

Bring the local repository onto GitHub main while preserving the current local
development work. All work stays local. Sufficient completion requires a
verified recovery snapshot, inclusion of the fetched main tip, preservation of
the source/docs changes, no unresolved merge conflicts, and appropriate combined
regression checks. Excellent completion adds byte-level preservation accounting
and a documented explanation of inherited quality failures.

## Result

- Original branch retained: `codex/aon-monster-loading` at `01bceb3`.
- Fresh local branch: `codex/local-reconciliation-20261027`, tracking `origin/main`.
- Both the active branch and local `main` now point to `70516ad`, the GitHub main
  tip fetched during this reconciliation. Both have zero commits ahead/behind
  that tip. The original branch remains available as a recovery reference.
- GitHub's PDF-over-AoN combat precedence, detailed creature fields, map/room
  changes, backfill safeguards, documentation, and regression tests are included.
- Local condition/turn semantics, versioned saving, explicit module archive,
  atomic session-review provenance, and agent/session-cycle/Discord planning
  remain present. The archived review module was not reactivated.
- Development work remains uncommitted and unstaged. No push or public repository
  change was performed.

## Recovery and preservation

Before changing the worktree, created and verified:

- `.git/local-reconciliation-backups/20261027-223144/worktree.zip`
- `manifest.json` with SHA-256 hashes for all 61 individual changed files
- original index/config/refs, staged/unstaged/binary patches, and status
- retained stash `38241f9fca478fb964fd509c1d2ba720a6008761`

The snapshot includes the recent agent/session-cycle planning work. The earlier
57-path status was an older status count and grouped the frontend test directory;
the recovery manifest counts individual files at operation start.

Final audit: 57 original files are byte-identical to their pre-reconciliation
copies. Four intentionally changed through reconciliation: `live.py`,
`dm_panel.html`, and operations/public-private docs 12 and 14. Original line
endings were restored where stash application normalized them. No original file
is missing. The audit is retained beside the archive.

The stash captured the intended source/docs successfully, then its directory
cleanup returned permission errors on legacy import directories before resetting
tracked files. No blanket cleanup was retried. Verified the stash path inventory,
then restored only the 32 backed-up tracked source/docs paths before switching
branches. Private contents are excluded from the snapshot and stash.

## Fetch repair and conflict resolution

The checkpoint ref previously described as malformed was valid: its target
object exists. The problem was Windows handling of its long ref path. Enabling
`core.longpaths=true` in this repository made the ref readable and allowed a
normal fetch. No checkpoint ref was deleted.

Stash application produced one textual conflict, in
`docs/14-public-repo-and-private-overlay.md`. Kept GitHub's synthetic-fixture
guidance and scratch ignores together with the local requirement for explicit
approval before publishing campaign notes. The other overlapping files merged
automatically and were inspected against the retained local snapshot.

## Verification and limits

- Python 3.11 on Windows, full suite: **151 passed, 1 failed**. Used a fresh
  writable external pytest temp root, a disposable DB setting, and fixture-only
  private-data roots. The remaining AoN cache test expects an empty size while
  the creature index supplies `Small`. The same failure was reproduced on an
  isolated, unmodified export of `origin/main`; it is not a merge regression.
- Node: **14 passed, 1 skipped**, covering local condition/save/archive behavior
  and GitHub's PDF precedence/detail-field behavior. The skipped test depends
  on real private campaign data.
- The imported Node test initially ran that private-data assertion despite a
  CLI name filter, reading local data and failing a completeness assertion. It
  made no writes. Added explicit `DMA_TEST_PRIVATE_OVERLAY=1` opt-in to that test
  and documented the permission requirement; default runs now skip it before
  reading private files. No private contents were copied into this record.
- Merged panel inline JavaScript syntax and `git diff --check` passed.
- Clean Alembic upgrade on a new disposable SQLite DB reached `20261007_0006`;
  verified context revisions, draft table, and provenance table. No live DB was
  opened or migrated by the database checks.
- Full Ruff found **10 inherited findings** in four unchanged files: MapTool
  adapter, private image intake, player prep PDF export, and legacy campaign
  migration script. Those files are unchanged relative to `origin/main`.
- No browser/play-test or new full Black/MyPy verification is claimed. Those
  release-quality gates and the existing baseline failures remain follow-up work.

## Completion

Sufficient completion for local reconciliation, with byte-level preservation
and inherited-failure evidence. The repository is synchronized at its committed
base while local development remains recoverable and ready for further local
work. Full release-quality completion still requires resolving the inherited
Python/lint failures and the outstanding browser/format/type verification gates.
