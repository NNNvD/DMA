# W1 review revision and transaction guards

Date: 2026-10-27. Windows/PowerShell, Python 3.11, local branch
`codex/local-reconciliation-20261027`. This continues W1 using fictional fixtures;
there is no live database migration, private overlay edit, commit, or push.

## Problem and change

Review API callers previously could not bind a decision to the draft revision
they saw. Log ingestion also committed its document/chunks before the surrounding
draft finalization completed. New regression tests reproduced the gaps: a review
response had no revision token, and an interruption left a new approved log or
an approved replacement behind while its draft remained pending.

Candidate decisions, promotion, and finalization now accept strict optional
`expected_revision` values and reject stale values with HTTP 409. Candidate
decision responses include the resulting `draft_revision` and `source_hash`.
Existing calls may omit the token for compatibility; an eventual agent write
adapter must require it. Fresh completed-operation retries retain the existing
result; stale revision-bound retries conflict and require reconciliation.

A conditional no-op draft update acquires SQLite's write reservation before
promotion reads baselines. Its version predicate catches a change between the
read and reservation, without advancing revision/timestamps for a no-op. The
reservation lasts through commit/rollback, including all accepted candidates
and provenance. Review operations map ORM stale writes and SQLite busy/locked
failures to conflicts and roll back the operation.

Ingestion now offers `commit=False` for caller-owned transactions, including
deduplicated existing-document refresh/rechunking. Finalization uses that option
so log/chunks/governance and draft status commit together. An interruption or
version conflict preserves the prior document/chunks and pending draft. Other
ingestion callers retain their normal default commit behavior.

The guard is database concurrency control, not human authorization. It does not
authenticate a `reviewer` label, create approval receipts, expose MCP mutations,
change the browser, reactivate archived modules, or alter card-based combat.

## Verification

The deterministic regressions in `tests/integration/test_session_review_guards.py`
cover stale tokens at each step, separate decision/promotion/log approval,
strict token types, failures with both new and existing logs, genuine ORM
version conflicts, competing SQLite entity writes, two reviewers observing the
same revision, and a busy database. External embeddings are disabled for these
tests. The first concurrency fixture was corrected to use separate sessions for
entity creation and draft capture, matching actual API requests rather than
retaining an in-memory timestamp representation across both operations.

- The initial regression run reproduced three failures on the old behavior:
  missing decision revision metadata and interrupted finalization leaving new or
  replacement approved logs behind.
- Final scoped regression group: **36 passed, one recovery subprocess timed out
  after 90 seconds**. The recovery CLI group rerun alone passed **2 tests**.
  Together, all **37 distinct tests passed across runs**: 18 new guard cases,
  existing review/parser/ingestion/document/import behavior, real-schema agent
  onboarding, and paired recovery. The timeout remains an execution limitation;
  it was not treated as a passing check or hidden by increasing its threshold.
- The final new guard suite also passed **18 tests** with external embeddings
  disabled and standard-library line tracing. The two new helpers covered
  **23/24 executable lines (95.8%)** in `_review_write` and **22/23 (95.7%)**
  in `_lock_review_draft`. The disposable report is
  `.codex-temp/w1-review-guard-coverage.json`. This is helper line coverage, not
  a repository-wide or branch-coverage claim.
- Focused Ruff and Black checks passed for the three changed implementation
  files and the new regression file; `git diff --check` passed with existing
  line-ending normalization warnings only. Tests also report the existing
  Starlette/AnyIO deprecation warning.

Tests used new disposable directories under `.codex-temp/` and permitted
execution outside the Windows sandbox, since its socket restrictions prevent
asyncio setup. Pytest cacheprovider was disabled to avoid the existing Windows
TEMP/cache permission problem. The final serial recovery report lives under
`.codex-temp/w1-recovery-recheck-20261027/`.

## Acceptance and remaining W1 work

**Sufficient for the review-primitive guard slice.** This provides
revision/transaction prerequisites for a trusted approval
adapter. W1 overall remains open: trusted actor identity, exact displayed
changes and source hashes, campaign/session/binding/epoch checks at mutation
time, expiring/consumable approval receipts with retained results, staging
deduplication, and actual dedicated-host interaction still need implementation
and verification. The MCP connection continues to expose eight read tools only.

SQLite reservation behavior is tested; no other database engine's concurrency
guarantees are established. Entity rows still lack their own optimistic version
columns. A subsequent direct edit can legitimately follow promotion; it needs
its own stale-edit protection. Database rollback does not undo any external
embedding-provider call. Full CI, supported-platform coverage, real-campaign
recovery, and release readiness remain separate gates.
