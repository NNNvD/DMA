# Campaign data ownership and session review contract

Status: the staged-review API is implemented; its DM panel review module is
archived by explicit user choice as recorded in `docs/21-dm-panel-module-archive.md`.
Accepted facts now promote as one transaction with durable candidate-level provenance.
The W0 [operating/data contract](23-agent-operating-and-data-contract.md) now
maps field ownership and tool boundaries, with a verified fictional SQL/overlay
restore rehearsal. Review revision/transaction guards are now implemented below.
Trusted agent approval, prep source traceability, and live-data
recovery remain separate work. The legacy importer retains its trusted
immediate-write behavior. This contract does not authorize data migration or
changes to live campaign data.

## Ownership by data domain

| Domain | Authoritative store | Other copies / role | Prep eligibility |
| --- | --- | --- | --- |
| Accepted campaign facts and relationships (locations, factions, NPC/PC identity, events, calendar) | SQL campaign entities and relationships | Overlay overview/dossier text may hold panel-specific presentation or private notes; do not silently sync overlapping facts | Active accepted DB facts only |
| PC sheet source files and portraits | Private overlay source files | SQL PC entities and `CharacterSheetVersion` are the normalized, accepted runtime records | Accepted DB fields only; private source files are not sent to prep wholesale |
| NPC portraits, dossier presentation, private descriptive notes | Private overlay | Any normalized identity/relationship fields represented in SQL are owned by SQL; no automatic two-way merge | Only explicitly accepted structured facts; private notes are excluded unless selected by the DM |
| Session log and review decisions | SQL document record plus review/provenance metadata | Overlay `sessions.json` remains a panel-authored note/archive until an explicit import links it to a reviewed log | Reviewed logs only; pending and rejected material excluded |
| Session-update candidates | SQL `session_update_drafts`, linked to retained source by stable draft ID and content hash | Candidate payloads/decisions remain on the draft; `campaign_entity_provenance` links promoted candidates to entity IDs and identity snapshots | Never directly; only accepted candidate values promote |
| Generated prep | SQL `session_prep` document | Markdown output is a reproducible artifact, not new campaign fact | Output of accepted DB facts and reviewed session history |
| Current scene/combat snapshot | SQL versioned `contexts` entry | Ephemeral operational state; no implicit promotion to campaign facts or a session recap | Excluded unless explicitly captured into a reviewed session log |
| Campaign overview, treasure tracker, settlement descriptions and panel-only campaign notes | Private overlay JSON under the campaign directory | SQL entities may contain overlapping normalized facts; overlay prose is not automatically authoritative for those fields | Only selected, reviewed fields are eligible as future prep context |
| Room keys, local maps, licensed PDFs, bestiary cache, extracted/reference corpus | Private overlay files | Source, license, privacy, and retrieval policy metadata govern use; paths do not imply approval | Only items explicitly permitted by their source policy; private GM material stays GM-only |
| Public rules/reference inputs and import manifests | Public-safe repository drop zones plus governed SQL documents | Preserve source/license metadata and classifier decisions | According to `docs/19-aon-data-policy.md` and ingestion governance |

### Overlap rule during transition

Several domains currently exist in both SQL and overlay JSON. Until each field
has a field-level owner and a reviewed migration plan, neither side overwrites
the other automatically. Read APIs may continue to use their current source;
write paths must identify the store they update. Reconciliation is a deliberate,
reviewed action that records the selected value and its source. A discrepancy is
reported, not silently merged.

## Session update lifecycle

The intended lifecycle is:

1. **Capture:** retain the submitted log as a private source record with stable
   identity, campaign/session identity, source, and content hash. Editing the
   live Current Combat snapshot does not create or accept a session log.
2. **Parse and preview:** parse metadata, changelog, and entity candidates into
   a draft. Show source text, proposed field-level changes, unresolved entity
   matches, and conflicts. Parsing alone must not change accepted entities,
   calendar state, session history, or prep results.
3. **Review:** the DM accepts, rejects, or defers each candidate. The decision
   records reviewer, time, candidate/source identity, and the accepted value or
   rejection reason. Unknown or ambiguous entities remain unresolved.
4. **Promote:** after every candidate is accepted, rejected, or deferred, call
   `POST /api/campaign/session-update-drafts/{id}/promote`. The service checks
   every accepted candidate's preview baseline before writing, then applies all
   accepted entities, relationships, provenance rows, and draft results in one
   transaction. A conflict or failure rolls back the batch. Repeated calls
   return the existing provenance-backed result. Rejected/deferred candidates
   stay outside accepted campaign state.
5. **Finalize log:** mark the session log reviewed when the DM approves it for
   session history. Only reviewed logs contribute to prep's recent-session
   inputs. All candidates must have a decision, and all accepted candidates
   must be promoted before finalization. A log may be approved while candidates
   are rejected or deferred.
6. **Generate prep:** prep uses active accepted SQL entities plus reviewed,
   eligible session logs and explicit user-selected context. It records the
   source IDs/revisions used so a generated brief can be explained and refreshed.

Reviewing the prose does not automatically approve every extracted fact. A
session log's history eligibility and each candidate's promotion decision are
separate decisions.

## Review revision and transaction guards (2026-10-27)

Candidate decisions, promotion, and session-log finalization accept an optional
strict positive-integer `expected_revision`. Use the revision from the draft
actually displayed for review:

```json
{"decision": "accepted", "expected_revision": 3}
```

For promotion, the optional JSON body is `{"expected_revision": 4}`. For log
finalization, use `{"decision": "approved", "expected_revision": 5}`. The numbers
are examples; each successful state change advances the draft revision. Candidate
decision responses now return `draft_revision` and `source_hash`; promotion and
finalization return the complete draft metadata including `revision`.

A stale revision returns HTTP 409 before a write or completed-operation return.
Reload and reconcile the source/decisions before making a fresh choice; never
silently replace the supplied token. Revision-bound retries with an old token
also conflict. With a current token, completed promotion/finalization can return
their existing results without duplicating records. Durable operation-specific
approval/retry receipts are still future work. Existing local calls may omit the
token for compatibility; an agent mutation adapter must require it.

Before a review mutation reads baselines, a conditional no-op update checks the
observed draft revision and reserves SQLite's writer. The reservation retains
revision/timestamp values and lasts through the operation's commit/rollback.
This prevents a competing SQLite write between baseline validation and promotion.
ORM version conflicts and SQLite busy/locked failures roll back and return 409.
No concurrency guarantee for another database engine is claimed.

Log ingestion (including replacement/rechunking), its governance metadata, and
draft finalization now commit in one transaction. An interruption or version
conflict leaves the prior log/chunks and pending draft intact; an approved log
cannot escape from a failed finalization. Other ingestion callers retain their
normal commit behavior. These guarantees cover database changes, not external
model-provider calls during embedding.

These primitives do not authenticate the DM. A caller-supplied `reviewer` remains
an audit label, not authorization. The optional read-only campaign profile still
exposes eight read tools. The [W1 guarded fixture profile](25-campaign-agent-review-and-acceptance.md)
now implements operator receipts, binding/epoch checks at mutation time, exact
displayed intent/source hashes, session associations, expiry/consumption and
atomic retained results through a separate gateway. Legacy local HTTP routes do
not acquire that authorization automatically. Direct entity edits
still need their own version checks; later writes are not prevented forever by
the promotion reservation.

## Earlier API behavior and remaining gaps (verified 2026-10-07)

- `POST /api/campaign/import/session-update` parses and applies candidate
  entities, calendar changes, and timeline events as part of import. Its request
  has no review decision field or staged-draft mode.
- Session-log documents default to `review_status="approved"`,
  `rag_eligible=True`, and GM-only visibility when no governance fields are
  supplied.
- `CampaignService.get_session_history()` now filters to approved
  `session_log` documents.
- Prep reads SQL campaign entities and this session-history feed. It does not
  read the panel's private overlay `sessions.json` as recent session history.
- Overlay and SQL PC/NPC/session representations coexist. There is no general
  field-level ownership or synchronization service.
- The staged API provides draft creation/list/read, per-candidate accept/reject/
  defer, separate session-log approval/rejection, campaign ID, content hash,
  self-reported reviewer label, and review timestamps. Pending drafts are not
  indexed as documents.
- The archived DM panel Session Update Review module's retained source lists pending drafts, displays the
  source and candidate baseline/payload, and separates candidate decisions from
  session-log finalization. It does not yet offer draft creation or reviewer
  identity configuration; API callers stage drafts and reviewer identity remains
  the service default unless supplied by a caller.
- Candidate promotion is an explicit batch after candidate decisions. A
  `campaign_entity_provenance` row links each accepted candidate to the target
  entity and stores draft/candidate IDs, source hash/name, reviewer/time,
  candidate payload, and an entity identity snapshot. The entity route
  `/api/campaign/entities/{id}/provenance` exposes those links. Its module source
  remains in the repository, while active availability follows the explicit
  archive record and is not changed by this API work.

Treat legacy `POST /api/campaign/import/session-update` as a trusted immediate
write operation. Use the staged `/api/campaign/session-update-drafts` endpoints
for uncertain notes. Draft preview stores source text and parsed candidates in
the private local database but does not alter accepted facts or prep history.

## Implementation order and acceptance tests

1. W1 implements the bound agent/read tools and trusted approval adapter defined
   in the W0 contract. Current review primitives are not an authentication or
   revision-bound approval gateway; ambiguous overlay/fallback writes stay out.
2. W2/W4 add durable session associations and prep input IDs/revisions. Atomic
   promotion, baseline conflicts, no-write-on-accept, provenance, retries, and
   rollback already have disposable fixture coverage.
3. The W0 fictional rehearsal verifies a paired restore, review/history/prep
   eligibility, and stale-write handling through existing APIs. Live recovery
   still needs a separately reviewed paired backup/copy map and DM approval.

Do not test migration or promotion against the live campaign database. Use
disposable databases and deterministic fixtures. A passed fictional rehearsal
does not establish that a live campaign backup or migration has been verified.
