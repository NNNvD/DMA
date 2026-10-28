# Atomic session update promotion — 2026-10-07

## Change

Candidate accept/reject/defer decisions are now review intent only. A separate
`POST /api/campaign/session-update-drafts/{id}/promote` call requires a decision
for every candidate, checks all accepted candidates against their preview
baselines before writing, then promotes all accepted facts and relationship
updates in one database transaction. A stale baseline returns HTTP 409. Any
failure rolls back entities, relationships, provenance, and draft promotion
results together. Session-log approval remains a separate decision and cannot
complete until accepted candidates have been promoted.

Added `campaign_entity_provenance`, migration `20261007_0006`, and
`GET /api/campaign/entities/{id}/provenance`. Each provenance row records the
source draft/candidate, hash/name, reviewer/time, candidate payload, entity
identity snapshot, and nullable entity reference. A uniqueness constraint
protects candidate-level retries. Legacy importer callers keep their existing
commit behavior; only staged promotion requests flush within the outer batch.

Updated the ownership contract, roadmap, and README API sequence. The contract
now says accepted facts become prep-eligible after explicit batch promotion;
the current review UI remains governed by the explicit module archive record.

## Completion gates

- **Sufficient:** no accepted fact is written by its decision request; the
  atomic promotion rolls back on a mid-batch failure; stale baselines conflict;
  retries do not duplicate provenance; all fixtures use disposable databases.
- **Excellent:** durable provenance is queryable and the API workflow, limits,
  and remaining M2 work are documented.
- **Not complete if:** partial batch writes are possible, legacy imports change
  behavior, or live campaign/overlay data is modified.

## Verification

- Session-review API tests: 6 passed (in-memory SQLite fixtures). The final
  related API/service regression set passed 16 tests.
- Migration `upgrade head` reached `20261007_0006` on a newly created temporary
  SQLite database and confirmed the provenance table columns; the temporary DB
  was removed. No live database or private overlay was opened or migrated.
- Ruff lint/format checks, Python compilation, and `git diff --check` passed.
- A wider focused regression run reported 19 passed and 2 setup errors. Both
  errors were existing `tmp_path` setup failures caused by Windows access
  denial in `%TEMP%\pytest-of-NNNvD`; neither test reached its body. Re-run those
  vault export/import tests in an environment with a writable pytest temp root.

## Remaining M2 work

- Define field-level source ownership and API mapping for overlapping SQL and
  private overlay campaign data.
- Record accepted input IDs/revisions in generated prep and verify explainability.
- Rehearse backup/restore for both DB and private overlay using disposable or
  approved copies. Do not run against the live campaign DB without a separately
  reviewed backup and recovery plan.
- Review deferred candidates and finalized-draft history as API/UI behavior;
  the Session Update Review panel module is archived by explicit user choice.

## Achieved level

Sufficient for the atomic-promotion slice. The successful test and migration
evidence covers the changed workflow; browser verification and live play testing
were not applicable to this backend-only change. The wider regression run had
two environment-level setup errors described above.
