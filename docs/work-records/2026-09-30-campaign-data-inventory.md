# Campaign data source and ownership inventory — 2026-09-30

## Scope and method

This is a structural inventory of repository code and documentation. It did not
open, enumerate, hash, or change private overlay files or the local campaign
database. It records configured storage boundaries and code paths only; it does
not claim that a local backup or restore has been rehearsed.

## Current storage map

| Data | Current store / reader | Current write path | Observed ownership and concern |
| --- | --- | --- | --- |
| Campaign entities, relationships, calendar, timeline events | SQL database: `campaign_entities` and `campaign_relationships` | Campaign APIs and session update import | Structured campaign state and prep source; session import can apply parsed entities and calendar/event changes during import. Review/approval semantics need to be explicit. |
| Session logs and generated prep documents | SQL database: ingested `documents` | Session update/import and Prep API | Prep queries campaign entities plus DB session history. It does not read `private-local/campaigns/<id>/sessions.json` as its recent-session source. |
| Live scene/combat snapshot | SQL database: versioned `contexts` entry | Current Combat autosave/manual save/reset | Operational, mutable session state with optimistic revision checks; not an accepted campaign fact or session log. |
| Campaign overview tabs, session-note JSON, PC/NPC dossiers, treasure tracker, image metadata, settlements | Private overlay JSON under `assets/imports/misc/private-local/campaigns/<campaign-id>/` | `PrivateCampaignDataService` and live-panel APIs | Local/private runtime data. Some domains overlap conceptually with DB entities and session history; ownership and synchronization are not uniformly declared. |
| Room keys, bestiary cache, maps, PDFs, portraits, extracted/reference corpus | Private overlay files in specialized roots | Import/review and local maintenance services | Private or licensed source material. Must not enter public Git. Room import has a draft/review/promote boundary; corpus policies are separate. |
| Raw imports, source manifests, governance metadata | `assets/imports/` drop zones and generated metadata | Import/governance scripts and ingestion APIs | Mixed source classes; destination and retrieval rights depend on review and source policy. Do not treat path alone as approval. |
| Legacy Obsidian vault and export/sync code | Compatibility services, scripts, and older setup docs | Explicit legacy helper commands | Docs say the active vault was retired, but compatibility code and older instructions remain. The supported state and safe use of legacy commands need to be consistent. |

## Main workflow finding

The current prep generator reads SQL campaign entities and SQL session history.
The DM panel's session-note APIs read and write overlay `sessions.json`. The
session-update importer separately writes parsed facts into SQL entities and
stores a SQL session-log document. These are parallel representations without
one documented promotion contract. Before changing storage or adding syncing,
define which session note is a draft/log, what explicit review accepts a fact,
and how prep selects accepted facts and session history.

## Documentation and migration risks

- Root setup and overlay docs establish the private root overlay as canonical,
  and Town Square's `settlements.json` path must remain in the campaign folder.
- The inventory found conflicts between `docs/14-public-repo-and-private-overlay.md`,
  `docs/15-novice-local-setup.md`, and the Obsidian retirement note. These have
  now been reconciled: the root overlay is canonical, private overlay contents
  stay out of Git, and Obsidian guidance is labeled retired compatibility.
- `docs/12-operations-manual.md` retains detailed legacy Obsidian procedures
  under an explicit warning. These should be removed or further separated if
  compatibility support is formally ended.
- The standalone migration script describes regenerating overlay JSON from
  Obsidian and database sources. It must not be run against the real campaign
  data until it has a reviewed source-to-destination map, retained originals,
  conflict policy, dry-run evidence, and recovery procedure.
- No M2 data migration or campaign-data synchronization was performed for this
  inventory. No campaign contents were inspected.

## Recommended next M2 slice

1. Correct the conflicting public/private and legacy setup instructions.
2. Specify ownership per field/domain and a review transition from session log
   to accepted campaign state to prep input.
3. Add fixtures proving rejected/pending session updates do not alter accepted
   entities or prep inputs.
4. Design backup/restore verification for the SQL database and overlay without
   running it against private production data.

## Evidence inspected

- `README.md`; docs 05, 08, 14, 15, 17, and 18.
- `backend/config/local_paths.py` and `backend/services/private_campaign_data_service.py`.
- `backend/models/campaign.py`, `backend/models/context.py`,
  `backend/services/prep_service.py`, and
  `backend/services/session_update_service.py`.
- Live API references for campaign/session notes, PC/NPC dossiers, Town Square,
  room keys, and current session state.

## Documentation reconciliation follow-up

Updated the README, public/private boundary guide, novice local setup guide, new
campaign guide, and Obsidian-specific guides to match the root-overlay policy.
Removed the private bundle copy commands, outdated specific-session setup
checks, and routine Obsidian sync steps. Legacy routes remain in the codebase but
are labeled as inactive compatibility. `git diff --check` passed (the existing
`.env.example` line-ending normalization notice remains unrelated).

## Ownership and review contract follow-up — 2026-10-07

The proposed field-domain ownership and session update lifecycle now live in
`docs/20-campaign-data-ownership-and-review.md`. Code inspection confirmed an
important implementation gap: the current session-update endpoint applies
parsed entities/calendar/events immediately, stores session logs approved by
default, and prep history does not filter session logs by review status. The
contract records this as current behavior, defines the staged/preview/review/
promote target, and specifies regression acceptance before implementation.
