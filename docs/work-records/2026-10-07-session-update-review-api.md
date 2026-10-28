# Staged session update review API — 2026-10-07

## Change

Added a private SQL draft record and Alembic revision `20261007_0005` for staged
session updates. `POST /api/campaign/session-update-drafts` parses source text and
stores candidates without changing campaign entities, calendar, events, session
history, or prep inputs. `GET` collection and item routes support finding pending
drafts and reading source text. Candidate decisions accept, reject, or defer
each entity/calendar/event candidate. Rejection requires a reason. The session
log has a separate approve/reject decision; rejected logs are stored with
retrieval disabled, and prep history now selects approved session logs only.

Each candidate records the matched target's identity and `updated_at` at preview.
Promotion returns HTTP 409 if that target was created, removed, or changed before
acceptance, preserving the newer edit. Each accepted candidate has a decision,
optional self-reported reviewer label, timestamp, promotion result, and source
draft link. Promotion is recoverable one candidate at a time: an interrupted
operation remains `promoting` and can be retried. The legacy
`POST /api/campaign/import/session-update` remains a trusted immediate-write path.

## Verification

- 19 focused session-review, campaign-import, and prep tests passed.
- Full Python suite: 145 passed, 1 failed. The unrelated existing
  `test_aon_creature_cache_without_image_url_still_loads` expects an empty size,
  while the creature catalog resolves the fixture to `Small`.
- Full Python suite excluding that test: 145 passed.
- Ruff passed on changed backend and test files. Black formatting was checked
  using Black's formatter API. Python compilation passed.
- Mypy found no issues in `session_update_service.py`; the full targeted check is
  still blocked by missing PyYAML stubs and existing errors in legacy Obsidian
  modules.
- Alembic upgrade reached `20261007_0005` on a disposable SQLite database and
  confirmed the draft table/columns. The disposable database was removed; the
  local campaign database was not migrated.
- `git diff --check` passed; Git reported only line-ending normalization notices.

## Remaining work

The API has no DM panel review UI. Campaign entities do not yet store a direct
provenance foreign key to their source candidate, and multi-candidate promotion
is not atomic. Add those before treating the review workflow as complete. Do not
use the legacy immediate-write endpoint for uncertain session notes.
