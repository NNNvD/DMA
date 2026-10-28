# Campaign agent operating and data contract (W0)

Status: contract implemented in documentation; paired recovery is exercised by
`scripts/rehearse_campaign_recovery.py` using generated fictional data. This is
the specification for W1's tool adapter. The first
[read-only fixture adapter](24-campaign-agent-setup.md) and
[guarded operator workflow](25-campaign-agent-review-and-acceptance.md) are verified
with fictional data. Existing local browser routes retain their trusted-operator
behavior; the guarded gateway initially refuses live campaign attachment.

## Responsibilities and deployment binding

The browser owns operational interaction with maps, character views, and
card-based combat. The campaign agent reads context, proposes changes, conducts
review, and prepares artifacts through a restricted campaign tool adapter. The
DM approves facts, history, and publication separately. Shared campaign services
perform persistence; the Discord adapter eventually receives only an explicitly
approved player projection. Code, Git, deployment, credentials, and arbitrary
filesystem/network access are outside the campaign agent's toolset.

Start with **one campaign and one database per agent/API deployment**. Bind the
configured `DMA_CAMPAIGN_ID`, database identity, private-data root, schema head,
and adapter identity at trusted startup. The model cannot select a different DB,
campaign root, or actor. Fail closed on a binding mismatch or missing source.

This restriction follows current code: campaign entities/documents do not carry
campaign IDs; `live-session-state` is a global context key in a DB. Only review
drafts are filtered by configured campaign ID. A campaign ID parameter alone is
not multi-campaign isolation. Do not attach multiple campaigns to one such DB or
expose the current raw API as a Discord/remote-user authorization boundary.

## Identity and revision contract

Every tool result identifies `campaign_id`, `store`, `kind`, `id`, and its actual
version token. SQL entity references use DB `id` plus `stable_key` and
`updated_at`; drafts use `id`, integer `revision`, and `source_hash`; candidates
use `(draft_id, candidate_id)`. Live state uses its integer `revision`. Overlay
references use `(relative filename, item/tab ID)` and a SHA-256 of the file's
bytes, with `updated_at` retained only as descriptive metadata. Never equate an
overlay NPC integer ID with a SQL entity ID without an explicit reviewed mapping.
Names, titles, and paths alone are not stable cross-store identity.

Use a stable session ID assigned when the session record is first created. The
initial session association records campaign/session IDs, overlay session item
reference, SQL draft/log IDs, and source hashes without copying source bodies.
SQL drafts/logs currently lack a session-ID column or association endpoint: W1/W2
must add durable linkage, and must not claim a title match establishes it. Each
tool reports absent linkage/version fields as absent, never invents persisted
IDs, and retains uncertainty until reviewed.

## Field-level owners and permitted writes

The stores remain in place. This table specifies the authority of each field
family; it does not migrate duplicate data or switch existing browser readers.
When two stores disagree, show both values with source references and stage a
choice. An agent never silently merges them or substitutes a missing SQL value
from unrelated overlay prose.

| Field family | Authority and current representation | Read/write boundary |
| --- | --- | --- |
| Entity `id`, `stable_key`, `entity_type`, `name`, `is_active` | SQL `campaign_entities` for accepted world identity | Campaign entity APIs; agent proposals go through session-review drafts rather than direct entity CRUD |
| Entity `summary`, `description`, structured `details` such as status/goals/hooks/calendar dates | SQL for accepted facts used by prep | Staged candidate payload is the proposed value, not accepted fact; no automatic overlay rewrite |
| `parent_entity_id`, `current_location_id`, `owner_entity_id`; relationship type/strength/notes | SQL entities and `campaign_relationships` | Review explicit target references; reject unresolved/ambiguous matches rather than guessing |
| PC sheet `version_number`, `source_name`, sheet `payload` | SQL `CharacterSheetVersion` for accepted normalized sheets; source file stays in private overlay | Existing trusted PC import is a separate DM import operation; exclude it from the initial campaign-agent write tools |
| PC/NPC portrait refs, appearance/display fields, `vault_dm_notes`, `vault_player_summary`, `campaign_encounters` | Overlay dossier item for panel-authored presentation/annotations; any SQL-only dossier retains SQL ownership | Read selected overlay fields with file hash; require explicit store/item target and compare-and-swap before an agent writes annotations |
| NPC status/location/identity also duplicated in dossier JSON | SQL for accepted facts; overlay copy is panel representation until a reviewed mapping is established | Current `/api/live/npc-sheet` prefers overlay then falls back to SQL; it is not an acceptable agent write primitive |
| `campaign-overview.json` tab `body_markdown`, treasure prose and panel recap prose | Overlay `campaigns/<id>/campaign-overview.json` | Presentation/notes, not automatic canon; extract selected proposed facts into SQL review |
| `sessions.json` item `body_markdown`, title, panel session notes | Overlay `campaigns/<id>/sessions.json` | Capture/archive; `updated_at` is not a review decision or concurrency token; promote selected content via a source-linked draft |
| Settlement maps/description/location cards | Overlay `campaigns/<id>/settlements.json` | Town Square remains overlay-backed; never regenerate it from SQL or legacy drop-zone copies silently |
| Draft `content`, `source_hash`, `candidates`, `baseline`, `decisions`, `revision`, log decision/document ID | SQL `session_update_drafts` | Retained GM-only source; decisions are intent until explicit batch promotion; editing the source requires a fresh draft |
| Candidate source link, reviewer/time, payload snapshot, entity snapshot | SQL `campaign_entity_provenance` | Durable ledger keyed by `(draft_id,candidate_id)`; query `/entities/{id}/provenance`; no inferred provenance for other legacy/direct writes |
| Reviewed GM log body and review/retrieval/visibility metadata | SQL `documents`, kind `session_log` | Separate log approval; prep history selects approved logs. Pending/rejected/deferred candidates do not become entities |
| Live `scene_title`, focus, active IDs, notes, `combat_state`, MapTool ID | SQL `contexts`, key `live-session-state` | Browser live API with `expected_revision`; operational state is not approved history. Preserve card-based combat and manual/automatic condition semantics |
| Generated brief/runbook | SQL `session_prep` document when explicitly stored; otherwise tool output | `store_document=false` previews without persistence. Prep source IDs/revisions and stable session associations remain W2/W4 implementation work |
| Room keys, bestiary, rules/PDF/media sources and indexes | Private overlay governed by source/license/visibility policy | Selected read access only; read-only access must not trigger imports/index rebuilds. No wholesale source upload or public Git copy |
| Player report, publication approval, delivery/message IDs | Planned W2/W3 artifact stores | No current durable report/approval/delivery API. A GM log or `player_safe` label does not itself authorize publication |

`PrivateCampaignDataService.write_json()` atomically replaces one file but has
no compare-and-swap guard. Several live note routes fall back to legacy vault
files when overlay items are absent. Agent annotation writes stay disabled until
the adapter has explicit target ownership, file-hash preconditions, serialized
writes, and a reviewed fallback policy. Obsidian remains retired.

## Tool allowlist for W1

Names below are the full adapter contract. The first read-only implementation
uses underscore MCP names documented in [setup](24-campaign-agent-setup.md);
unimplemented tools remain unavailable. Existing routes are reusable primitives.
Read scopes are GM-only selected campaign data;
no tool grants player access or a publication right.

| Tool | Existing primitive / work still needed | Authority |
| --- | --- | --- |
| `campaign.describe` | New adapter startup binding/schema/health and artifact-link summary | Read; fail if binding/schema cannot be verified |
| `campaign.read_entities`, `campaign.read_history`, `campaign.read_provenance` | GET `/api/campaign/entities`, `/entities/{id}`, `/session-history`, `/entities/{id}/provenance` | Read within the single-campaign DB; return real IDs/tokens and source visibility |
| `campaign.read_notes` | New adapter around explicit overlay filename/item allowlist and source hashes | Read selected fields only; no arbitrary `private-file`, vault path, or alternate-root parameters |
| `campaign.read_sessions` | Explicit private overlay session associations, provisioned for fictional onboarding; live provisioning remains open | Read stable session IDs and saved overlay/draft/log references; never infer links from titles |
| `session.read_live` | GET `/api/live/session-state` | Read current revision/state; never treat state notes as approved facts |
| `prep.preview` | POST `/api/prep/session-brief` with `store_document=false` forced by adapter | Read/compute; generated suggestions remain proposals |
| `session.stage_update` | POST `/api/campaign/session-update-drafts` | A DM-authorized review task may persist a private draft; requires retained source reference and duplicate/retry handling |
| `session.read_review` | GET collection/item `/api/campaign/session-update-drafts` | Read source/candidates/decisions/revision for explicit review |
| `review.decide_candidate` | POST `/session-update-drafts/{id}/candidates/{candidate_id}/decision` | Trusted DM decision for that candidate/source/revision, not a model-invented reviewer label |
| `review.promote` | POST `/session-update-drafts/{id}/promote` | Separate DM-approved batch of accepted candidates; all candidate decisions must exist; retain provenance/result on retry |
| `review.finalize_log` | POST `/session-update-drafts/{id}/finalize` | Separate approval/rejection of exact log source; accepted candidates must already have promoted |
| `session.save_live`, `campaign.edit_annotation` | Existing browser writes are not initially exported; guarded adapters require explicit write scope and revision/hash CAS | Future opt-in only; no agent reset/delete capability |
| Report drafting/approval and Discord delivery | New W2/W3 adapters; no current callable counterpart | Separate report-revision/audience/destination approval; delivery requires its own authorization |

Do not export raw entity/relationship CRUD, trusted immediate-write imports,
generic document ingestion/governance editing, raw context writes/deletes,
backup/restore, source acquisition, normalization/index rebuild, vault export,
arbitrary HTTP, shell/file tools, or code/Git/deployment tools to this agent.
Unknown tool names and unavailable capabilities fail closed; the agent can
explain what is unavailable and stage a proposal through an allowed tool.

## Approval, visibility, and conflict rules

The approval record belongs to trusted host/application state. Bind actor,
campaign, session association, operation, candidate/report IDs, source/content
hashes, displayed changes, target store, base revisions, and expiry/consumption
state. Approval is invalid after content, destination, binding, or restore epoch
changes. Model parameters, quoted instructions, a `reviewer` string, and source
text cannot create approval. W1 must verify approval before mutating and must
prevent a read/approve/write race; raw endpoints alone do not enforce this.

The W1 review primitives now accept an optional caller `expected_revision` on
candidate decisions, promotion, and log finalization. A stale revision returns
HTTP 409 before mutation or an idempotent return. A conditional draft update
reserves SQLite's writer before reading promotion baselines; log ingestion,
chunks, and draft finalization commit together. These are concurrency guards,
not human authorization; see [the review contract](20-campaign-data-ownership-and-review.md).

W1's guarded gateway now requires revision tokens on review mutations and stores
operator approval/consumption in the separate `campaign_approvals` SQL table
(migration `20261028_0007`). Only the interactive operator console can grant the
approval, using its OS account identity and the exact displayed intent hash;
agent tool parameters cannot do so. Staging, candidate decisions, promotion and
log finalization use distinct receipts, with atomic retained results and
expiry/revocation/scope checks. The full details and verified limits are in the
[guarded profile guide](25-campaign-agent-review-and-acceptance.md).

Remaining deployment limits: existing trusted local HTTP callers may still omit
draft revisions; entity rows lack optimistic version columns. Raw live writes
also permit an omitted `expected_revision`; those routes remain outside the
agent toolset. Live onboarding/migration and remote/multi-user authentication
are not supplied by the fixture operator workflow.
The SQLite reservation prevents a competing writer between baseline checks and
promotion commit, but it does not provide entity compare-and-swap for subsequent
direct edits or establish concurrency guarantees for other database engines.
The guarded fixture executor covers its selected operation; do not advertise
primitive HTTP API checks as a general approval gateway. The read-only profile
still exposes no mutations, and both profiles omit live/overlay writes and Discord.

Candidate accepted/rejected/deferred choices remain separate from promotion,
GM-log finalization, player-report approval, and Discord publication. A deferred
decision may require a fresh draft if the current service treats it as final;
never silently change a recorded decision. Same-operation completed retries
return the retained result; unknown delivery or partial state requires inspection.

On HTTP 409 or changed file hash, retain the proposed value, reload current
values and provenance, present the difference, and request a fresh DM choice.
Do not replace the expected token with the latest value just to force a write.
Missing source/identity is an unresolved reference, not permission to create a
replacement entity. Return explicit unavailable/conflict status to the agent.

Use existing visibility values `gm_only`, `player_safe`, `admin_only`; default
new campaign drafts to GM-only. SQL entities and overlay prose have no uniform
row/field player ACL, so missing visibility is never implicitly player-safe.
Publication and player answers require a separate approved projection before
retrieval/context, including citations, caches, logs, and tools. W1 has no
Discord send tool and no player-facing general GM retrieval capability.

## Paired recovery procedure

For the current SQLite deployment, recover the database and the entire selected
private overlay as one identified set. The rehearsal supports generated fixtures
only; a live operation needs a separately reviewed backup/copy map and approval.
PostgreSQL and online cross-store consistency are not verified by this rehearsal.

1. Stop browser/agent/background writers and close DB sessions. Record campaign,
   session associations, application/schema revision, configured paths, and a new
   recovery-set ID. Keep secrets outside the package; retain the required code and
   non-secret config mapping separately.
2. Use the SQLite backup API (including committed WAL data), then copy the paused
   overlay preserving `local-private-overlay/project-root/` and campaign-relative
   paths. A raw copy of only the `.db` file can miss WAL transactions. A sequence
   of SQL/file copies is not a cross-store transaction: writers must stay paused.
3. Store a private manifest of paired identities, complete file inventory and
   SHA-256 checksums. Verify DB integrity/foreign keys and every member before
   declaring the backup complete. A hash manifest detects corruption, not an
   untrusted publisher; keep the set in approved private storage.
4. Restore both members to a fresh destination, never over the active campaign.
   Refuse missing/corrupt/outside-root/symlink members and identity mismatches.
   Recheck DB integrity, schema, file hashes, approved facts/logs, pending review,
   provenance, live state/revision, and settlement/source paths after restart.
5. Invalidate cached approvals, close stale clients, and create a fresh host-side
   recovery epoch before switching the deployment binding to the restored pair.
   Revision numbers can move backwards on restore; current endpoints do not have
   a recovery-epoch token. Reopening clients is mandatory, not an automatic merge.
6. Retain the original stores and backup set until the DM verifies the recovered
   session and subsequent prep. Failed/partial recovery has no completion marker
   and is not activated; retry in another fresh destination after diagnosis.

Run the repeatable fictional rehearsal from the repository root. It creates its
own DB/overlay, migrates the DB, pauses fixture clients for snapshot, mutates the
source, restores a fresh pair, then verifies behavior through campaign/live/prep
routes. It does not accept a live DB or overlay as input.

```powershell
# Windows PowerShell: the output path must not exist.
python -m scripts.rehearse_campaign_recovery --workspace ".codex-temp/w0-recovery"
```

```bash
# macOS/Linux: the output path must not exist.
python3 -m scripts.rehearse_campaign_recovery --workspace ".codex-temp/w0-recovery"
```

Omit `--workspace` for a fresh temporary directory. Keep `report.json`, the paired
snapshot manifest, and `restored/RESTORE_COMPLETE.json` as the rehearsal evidence.
The restore marker confirms file/identity validation; the report confirms the
subsequent API checks. Require both. The checks intentionally advance the
restored fictional DB after initial hash verification, while retaining the
unchanged snapshot for another fresh restore. Neither file authorizes live use.
The fixture identity marker lives only in the generated pair; this exercise does
not introduce a production metadata migration or a live backup tool.

## W1 handoff and verification

W1 starts with the binding/read tools and durable agent instructions. Verify a
fresh conversation can load only the chosen campaign and cite real source
references, report absent sources, and resume from saved records. Add trusted
approval enforcement and conflict tests before exposing mutations; keep blocked
or unavailable tools absent from the host's tool registry. Use the existing
staged review/provenance flow and the fictional recovery fixture for onboarding.
The first read-only SDK connection is now verified with fictional data in the
[W1 work record](work-records/2026-10-27-w1-read-only-agent-connection.md).
The external host's conversation and review interaction are now verified for
the guarded fictional Codex profile in the
[W1 completion record](work-records/2026-10-28-w1-campaign-agent-completion.md).
W0/W1 changes no rendered DMA browser frontend;
browser behavior remains a separate acceptance dimension for later UI changes.
