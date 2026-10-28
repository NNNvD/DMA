# Development Roadmap and Build Requirements

Last reviewed: 2026-10-28 (W1 acceptance and guided-workflow priorities); engineering evidence below is
dated 2026-10-08 unless stated otherwise.

The active product sequence now centers on the complete session cycle and the
distinction between the DMA browser application, DMA agent, and Discord player
interface. M1-M5 below remain engineering workstreams and quality dependencies,
rather than a requirement to finish every workstream before session-cycle work.
The original five phases remain a capability catalogue later in this document;
they are not phase
completion claims or the current implementation order. Existing `phase1-check`
through `phase4-check` commands retain their names and coverage.

## Active product plan — 2026-10-27

The detailed scope, dependencies, sufficient/excellent criteria, artifact
lifecycle, and Discord access contract are in
[DMA agent, session cycle, and Discord](22-agent-session-cycle-and-discord.md).
W0's operating/data contract and fictional paired recovery are verified in
[the W0 contract](23-agent-operating-and-data-contract.md). W1 meets its sufficient
criteria for the local fictional GM workflow: a dedicated Codex connection,
durable instructions, grounded reads, separately approved staging/review, and
fresh-session resume are verified. See the [guarded setup](25-campaign-agent-review-and-acceptance.md)
and [completion record](work-records/2026-10-28-w1-campaign-agent-completion.md).
W2-W6 remain open; existing M1-M3 implementation is reused. macOS execution,
live campaign migration/attachment, full release CI and human play-testing are
separate unverified gates; this is sufficient W1, not excellent or release-ready.

| Order | Outcome |
| --- | --- |
| W0 | Define browser/agent responsibilities, field-level data ownership, tools, approval boundaries, and recovery |
| W1 | Establish a dedicated campaign agent in Codex or an agent-capable IDE with durable instructions and a verified data/tool connection |
| W2 | Complete guided debrief, reviewed GM log, candidate promotion, player-report drafting, and next-session handoff |
| W3 | Publish the exact DM-approved player report to a chosen Discord channel, with delivery records and retry handling |
| W4 | Connect agent preparation and live assistance to approved history and relevant browser state |
| W5 | Rehearse a complete session cycle, including restart/recovery and the next prep, then play-test |
| W6 | Add Discord player questions using a separately authorized player knowledge set and restricted tools |

W3 can follow W2 and the player access review; broad corpus/model expansion is
not a prerequisite. Discord configuration is optional for a local-only W5
rehearsal. W6 follows the verified core cycle and Discord publication. Hardening
applies throughout; full release/checkpoint gates below still apply.

### DM usability gate before the manual — 2026-10-28

The DM requests guided multiple-choice preparation/debrief, grounded suggestions
and reminders, durable learning from responses, and appropriately timed feedback.
The [guided interaction and feedback contract](27-guided-agent-workflows-and-feedback.md)
sets the concrete behavior, record classes and acceptance cases. These capabilities
are planned; W1's guarded primitives do not yet deliver the complete experience.

Initial implementation: the [guided operator-runner prototype](28-guided-agent-prototype.md)
provides durable interviews, note capture, confirmed preferences and native Codex
prep/debrief drafts without expanding MCP permissions. Fictional fixtures and
verified private rehearsal copies are supported; this does not close W2/W4/W5
or the final DM-manual usability gate.

Keep W0–W6 IDs stable. Prioritize W2a workflow/answer/capture and scoped preference
records plus interactive entry; W2b debrief, separate GM/player artifacts and
handoff; W4a guided preparation; then a local W5 full-cycle rehearsal and the
requested setup/before/during/after DM manual. Optional W3 Discord publishing can
follow that local usability gate; broader W4 live assistance continues afterward.
Reuse existing prep and W1 review services. Streamline trusted human review
without granting the agent approval authority. Learning adjusts explicit scoped
preferences, not model weights, system instructions or security boundaries.

The browser remains the operational session workspace; the external campaign
agent becomes the intended conversational preparation/review surface. The agent
setup now has native fixture-host verification beyond the read-only adapter. Archived panel
modules stay archived; no reactivation is needed to plan the agent review path.
Player answers must exclude GM-only material before retrieval/context assembly.
Player input never automatically becomes accepted campaign fact.

Next implementation slice: W2a durable guided workflow state, capture inbox,
scoped preferences/feedback and convenient interactive start/resume. Then deliver
W2b debrief and resumable closure using the W1 receipt/review gateway. Add
uncertainty handling, corrections, separate player-report drafting and next-session
intentions without weakening distinct fact, GM-log and publication approvals. The earlier
[read-only slice](work-records/2026-10-27-w1-read-only-agent-connection.md) and
[primitive guards](work-records/2026-10-27-w1-review-revision-and-transaction-guards.md)
remain dated evidence; W1's final outcome is in its completion record.
Full AoN acquisition remains parked; MapTool stays experimental.
The W0 rehearsal used fictional data; live migration, publication, and deployment
remain separately gated.

## Engineering evidence baseline — 2026-10-08

The review covers the local working tree on `codex/aon-monster-loading` at
`01bceb3`. At review start it already contained 56 modified or untracked paths;
this review adds further planning edits. No fresh remote comparison was
performed. The worktree is not a release artifact and these changes are not
established as published.

| Area | Evidence as of this review | Remaining qualification |
| --- | --- | --- |
| Rules, campaign, prep, and live APIs | Implementations and Python tests exist across original Phases 1–4 | This does not establish complete delivery of every phase requirement |
| Rules answers and prep | Rules responses compose retrieved excerpts; prep builds deterministic briefs | Model generation, streaming, and enforced request/session budgets remain planned |
| Current Combat and panel controls | Condition semantics, revision-aware saves/recovery, fallback controls, per-module collapse controls, and archived-module manifest are implemented; Dice Roller remains the sole default pin | Browser behavior was last manually verified before the Oct 7 module archive/control edits; post-archive collapse, pin, and small-screen flows remain unverified |
| Automated tests | Sep 30 recorded full suite at 141 passed; Oct 7 M2-focused suite passed 16 tests; frontend archive assertions exist | No current full-repository test/CI run; latest broader Windows run hit two `%TEMP%` setup errors before test bodies |
| Static quality | Oct 7 focused Ruff lint/format and Python compilation passed for the M2 slice | Full repo lint, Black check, and MyPy have not been verified for this worktree |
| Runtime support | CI specifies Python 3.11 on Ubuntu; latest focused backend tests used Python 3.11 on Windows | Full supported-runtime matrix and Windows CI remain unverified |
| Data workflow | Staged review API, prep-history filter, atomic promotion, provenance migration `20261007_0006`, and provenance lookup are implemented and verified with disposable fixtures | Review UI is archived by explicit choice; prep source IDs/revisions, field ownership, and DB+overlay restore rehearsal remain open |
| MapTool | Experimental adapter and synthetic bridge work are recorded | Stock application exposes a non-HTTP URI; real integration remains deferred and unverified |

### Release target and readiness

**Engineering target retained: an unversioned local engineering checkpoint, not
a public or GM release candidate.** The Oct 8 baseline recorded a 56-path
uncommitted worktree, no clean checkpoint commit, and no current full CI result.
This planning update does not refresh those verification results. A checkpoint can
be called release-ready only after the release-gate checklist below passes.

The checkpoint may cover Current Combat and the active panel modules. The
Session Update Review module stays archived per `docs/21-dm-panel-module-archive.md`;
the staged workflow is API-only for this scope. Any GM-facing release that claims
interactive session review needs a verified active interface before it can claim
that workflow as a usable product feature. W1/W2 now select the external campaign
agent as the intended surface; this does not reactivate the panel UI.

Release gates:

1. Review and isolate the current worktree into a clean, public-safe deliverable;
   inspect staged paths and confirm no private overlay data is included.
2. Pass the complete `make ci` quality checks in the declared Python 3.11
   environment; resolve the Windows pytest temp-root setup issue and record any
   platform limitation separately from test failures.
3. Verify a clean database upgrade through `20261007_0006` and a representative
   backup/restore rehearsal using disposable database and overlay fixtures.
4. Run browser checks after the module archive for collapse/expand persistence,
   Dice Roller pinning, active panel navigation, keyboard use, and small screens.
5. Keep campaign/overlay synchronization and live database migration out of the
   checkpoint until ownership, backup, copy map, and recovery have separate review.

Historical work records remain evidence of the checks they describe. Later
findings reopen affected acceptance criteria; labels such as "excellent" do not
establish correctness of behavior those checks did not exercise.

## Engineering workstreams (M1-M5)

Execute small, reviewable slices as dependencies of W0-W6; the M1-M5 order below
is the historical engineering sequence. Quality checks and focused
extraction of code needed to test a slice apply from M1 onward. M3 consolidates
that work; it does not postpone testing or permit knowingly broken quality gates.

| Milestone | Outcome | Dependency | Current status |
| --- | --- | --- | --- |
| M1 | Reliable combat conditions, turns, and saving | Define condition and navigation semantics | Core implementation and focused regression checks complete; full CI and optional browser automation remain |
| M2 | Consistent campaign data and session-to-prep workflow | M1 core stable; inventory data ownership before migration | Staged review, atomic promotion/provenance, W0 field/tool contract, and fictional paired recovery verified; review UI stays archived; runtime approval guards, prep source evidence, and live recovery readiness remain |
| M3 | Maintainable frontend and reproducible quality baseline | Preserve M1/M2 behavior during extraction | In progress: archive manifest and regression assertions are recorded; controls/browser verification, duplicate-function cleanup, and full repo quality checks remain |
| M4 | Evaluated, grounded assistant capabilities | M2 data contract and M3 test baseline | Planned |
| M5 | Validated integrations and reviewed content expansion | Relevant M1–M4 gates for each addition | Discord publication planned under W3; player Q&A under W6; MapTool and broad content expansion remain deferred |

### M1 — Reliable combat

Deliver in two slices: condition/turn correctness, then persistence/recovery.

- Separate condition magnitude from duration and expiry trigger. Define supported
  automatic transitions, source references, and explicit GM overrides. Preserve
  ambiguous existing values for review rather than interpreting them as durations.
- Define whether Previous Turn navigates or undoes a turn. Undo must restore
  affected state; navigation must not imply that condition changes were reversed.
- Serialize combat saves and track acknowledged revisions. Reject or resolve stale
  writes so a slow request or another tab cannot silently replace newer state.
- Coordinate pending saves with reset, reload, and manual live-state edits. Saved
  feedback must refer to the current acknowledged revision. Surface failed saves
  with a retry/recovery path and protect edits that have not yet been acknowledged.
- Preserve the richer card-based interface and existing initiative, HP, creature,
  and affliction features.

Acceptance evidence:

- Focused tests distinguish magnitude, duration, expiry, and manual conditions;
  exercise turn boundaries and the chosen backwards-navigation contract.
- Browser interactions cover manual HP and initiative edits, ties, add/remove
  condition, turn advancement, and the relevant keyboard controls.
- Delayed and failed requests, rapid edits, stale writes, pending-save reset, and
  refresh/recovery have explicit expected outcomes and automated regression coverage.
- No older response can incorrectly mark newer unsaved edits as saved. Reload
  restores acknowledged state and any recovery mechanism identifies pending edits.

### M2 — Consistent campaign data

The data ownership and session review contract is recorded in
[`docs/20-campaign-data-ownership-and-review.md`](20-campaign-data-ownership-and-review.md).
Staged review decisions promote accepted candidates atomically with durable
source provenance. W0 defines field-level store ownership and demonstrates paired
fixture recovery; remaining work includes runtime approval/ownership enforcement,
prep source evidence, and live recovery readiness. This does not authorize live
data migration.

- Record ownership of campaign entities, live notes, session history, prep,
  images, and reference data across the database and overlay JSON. Specify write
  paths and synchronization rules before moving or consolidating data.
- Make Obsidian compatibility opt-in. Without explicit activation, missing overlay
  records produce useful empty states rather than vault fallback or note creation.
- Connect live updates to the workflow: review session changes, apply approved
  campaign updates, then generate the next prep. Distinguish temporary scene notes,
  suggestions, and accepted campaign facts; explain which inputs prep actually uses.
- Align the AoN classifier, fetch commands, destinations, and retrieval eligibility
  with `19-aon-data-policy.md`. Legacy paths must not silently confer public or
  approved status. This work does not require importing new source data.
- Document backup/restore of both database state and the private overlay. Any data
  migration needs a reviewed copy map, retained originals, and a recovery path.

Acceptance evidence:

- Fresh setup with no vault supports campaign and session views, including empty
  records and missing tabs, without creating or requiring Obsidian data.
- A session update reaches the intended next prep through the documented review
  flow. Rejected changes stay out of accepted campaign state.
- Session update preview and candidate decisions are side-effect-free; one
  atomic promote call applies all accepted facts with provenance, and only
  reviewed session logs enter prep history.
- Governance tests cover reviewed, pending, and legacy sources and their permitted
  destinations/use. Town Square retains `campaigns/<campaign-id>/settlements.json`.
- A restore rehearsal recovers representative campaign and live-session state.

### M3 — Maintainable and reproducible baseline

- Inventory DM panel modules and launchers; record which stay, merge, or retire
  with usage and dependency evidence before deleting UI. Do not infer that a
  table within a sheet viewer is the retired table-based combat module. The
  current archive list and reactivation gate are in
  [`docs/21-dm-panel-module-archive.md`](21-dm-panel-module-archive.md).
- Inventory the 32 duplicated function names found in the panel, establish the
  intended active behavior, and consolidate definitions with regression coverage.
- Extract combat state/rules, rendering, API access, maps, and notes in small steps.
  The 12,323-line panel and 3,580-line live route module are review baselines, not
  target sizes. Update architecture documentation to describe actual boundaries.
- Resolve the 11 observed Ruff findings and establish passing formatting and type
  checks. Declare supported Python versions and make clean environment setup
  reproducible on Windows and macOS/Linux; add Windows CI coverage.
- Add browser/JavaScript checks for behavior implemented in the frontend. Python
  HTML-content assertions cannot serve as interaction verification.

Acceptance evidence:

- Consolidated functions retain documented behavior; focused combat and map flows
  work after each extraction, with no return to the old table-based combat UI.
- Lint, formatting, type checks, and relevant Python/browser suites pass on the
  declared environments. Report unavailable checks explicitly.
- Keyboard and smaller-screen checks cover the primary live-play workflows.

### M4 — Grounded assistant capability

- Describe existing retrieval and deterministic generation accurately in the UI
  and docs. Treat model orchestration, streamed responses, and cost controls as
  separate deliverables with explicit acceptance criteria.
- Replace or redesign the latest-500-document candidate restriction before corpus
  growth makes older relevant references inaccessible. Evaluate retrieval at
  representative corpus sizes, including relevant documents outside that window.
- Evaluate source/edition conflicts, unsupported questions, and abstention.
  Retrieval relevance scores must not be presented as calibrated answer certainty.
- Preserve citations and provenance; distinguish source-backed answers, campaign
  facts, and suggestions. Generated suggestions become canon only through GM review.
- Establish measured latency and cost baselines, then record numerical budgets
  before declaring performance acceptance. Model calls require request/session
  caps, timeout behavior, data boundaries, and a useful fallback.
- Keep branch planning, encounter/scene generation, and handouts in the capability
  backlog until their output quality has its own scenario evaluation.

Acceptance evidence:

- A versioned question/scenario corpus checks correct support, edition selection,
  missing evidence, and justified abstention, including realistic distractors.
- Record corpus size, embedding/provider settings, latency percentiles, and cost
  where applicable. Deterministic fixture performance is not model-service evidence.
- Any introduced model flow meets its documented budgets and demonstrates timeout,
  unavailable-provider, and exhausted-budget behavior without changing canon.

### M5 — Integrations and reviewed expansion

- Implement Discord in the W3/W6 stages of
  `22-agent-session-cycle-and-discord.md`: approved report publication first,
  then player questions after the core session cycle and access tests. Keep
  publication approval separate from campaign-log approval and exclude GM-only
  data before retrieval. Hosting is a separate operational decision.
- Validate the MapTool bridge against one real campaign's token properties,
  initiative, HP, and conditions. Keep the standalone DMA workflow usable while
  this optional integration remains experimental.
- Expand the reference corpus one approved category at a time, starting with
  demonstrated play needs. Follow the provenance and intake checklist in
  `19-aon-data-policy.md`; the former full-cache task is not bulk-fetch approval.
- Require representative browser and real-play evidence before wider release.
  Broader game-system support follows explicit demand and evaluated rules packs.

Acceptance evidence:

- Discord requires exact-revision/destination approval, confirmed delivery and
  retry evidence, and player-source isolation tests; see the W3/W6 criteria.
- A real MapTool export/push reaches DMA with documented field mapping and failure
  behavior; synthetic bridge results remain labelled separately.
- Each category has source/destination review, normalization evidence, refreshed
  indexes, and relevant retrieval/UI checks. Private bundles remain manually shared.
- A dated play-test record captures usability, latency, recovery, and open defects.

## Evidence and completion tracking

Every milestone slice records these dimensions independently; each entry names
the revision or working-tree scope, date, environment, evidence, and limitations:

| Dimension | Meaning |
| --- | --- |
| Implemented | Required behavior exists in the stated code scope |
| Automatically verified | Named checks pass for that scope; missing checks remain explicit |
| Browser verified | Relevant rendered interactions, including failure states, were exercised |
| Play-tested | A representative session was run and findings recorded |

Use `planned`, `in progress`, `verified`, `blocked`, or `not applicable` for each
dimension, with a reason for blocked/not-applicable entries. A milestone closes
only when its acceptance evidence and the task-completion standard in
`06-testing-and-quality.md` are met. Do not infer completion from endpoint
existence, a test count, or a historical status label.

See `work-records/2026-09-30-development-plan-review.md` for the milestone
decision and `work-records/2026-10-08-priorities-and-release-target.md` for the
Oct 8 priority assessment and checkpoint gates. The product priorities in
`22-agent-session-cycle-and-discord.md` supersede that record's priority order;
its historical verification limits remain in force. See
`work-records/2026-10-27-session-cycle-and-discord-plan.md` for this revision.

## Original capability catalogue

The five phases below preserve the product scope and the meaning of existing
phase-check commands. Their deliverables remain subject to the milestones above.

---

## Phase 1 – Rules Engine & RAG

### Goals

- Implement ingestion and retrieval for rulebooks.
- Provide a minimal API or CLI for rules Q&A with citations.
- Establish basic cost and latency measurement.

### Deliverables

- Document ingestion pipeline:
  - PDF/HTML → text → chunks → embeddings.
- Vector store setup and query API.
- LLM prompt templates for:
  - Rules Q&A (standard mode).
  - Strict rules mode with uncertainty handling.
- Basic interface:
  - CLI, simple web endpoint, or dev-only web UI.

### Build Requirements

- Choice of:
  - Backend language (e.g., Python or Node.js).
  - Embeddings and vector store (e.g., OpenAI embeddings + a DB).
- Config for:
  - Rulebook locations.
  - Game system metadata (e.g., D&D 5e, generic fantasy).

---

## Phase 2 – Campaign & Party Modeling

### Goals

- Represent campaign world and PCs as structured data.
- Allow ingestion and updating of:
  - Campaign notes
  - Maps (with metadata)
  - NPCs, factions, timelines, calendars, and environmental cycles
  - PC sheets and backstories (including languages and scripts)

### Deliverables

- Schema definitions for:
  - PCs, NPCs, factions, locations, artifacts, events, calendars, and holidays.
- APIs or tools to:
  - Import campaign texts and notes.
  - Parse PC character sheets into structured form.
  - Link PCs to hooks, factions, languages, and locations.
- Interfaces to:
  - Query campaign entities by name, relationship, language, or location.
- Persistence layer:
  - Database or files for world/party state, magic item registry, and shop/service indexes.

### Build Requirements

- Data model design and implementation.
- Tools for:
  - Tagging entities, languages, and time references in text.
  - Updating world state after each session, including item ownership and calendars.
- Minimal UI:
  - World overview.
  - NPC list.
  - PC dossiers (with language capabilities and notable items).
  - Calendar and shop/service views.

---

## Phase 3 – Prep Assistant

### Goals

- Provide per-session prep assistance using rules + campaign + party models.
- Automate:
  - Recaps
  - Branch planning
  - Encounter and scene design
  - Hook surfacing
  - Prop generation
  - Time and calendar tracking

### Deliverables

- Session prep generation workflow:
  - Input: last session logs + target focus.
  - Output: structured prep document.
- Templates for:
  - Recaps
  - Session outlines (scenes, branches)
  - Encounters and stat bundles
  - Props/handouts
  - Time and calendar summaries (current day, season, upcoming events)
- Continuity checker:
  - Flags contradictions, unresolved hooks, unclaimed loot, and time-sensitive events.

### Build Requirements

- Orchestration workflows combining:
  - World/party state queries
  - Rules RAG
  - LLM generation
- Storage of:
  - Generated prep as canonical artefacts (with DM annotations).

---

## Phase 4 – Real-Time Session Assistant

### Goals

- Provide fast, context-aware assistance during sessions.
- Integrate with the DM’s environment (web UI, VTT plugin, or separate app).

### Deliverables

- Live “DM panel” that supports:
  - Quick rules Q&A
  - On-the-fly content generation
  - Continuity recall
  - Optional mechanical support (initiative, HP, etc.)
- Command syntax or UI shortcuts (e.g., `/rules`, `/npc`, `/recap`).
- Latency-optimized prompt templates.

### Build Requirements

- Session state management:
  - Track current scene, active NPCs, and PCs.
- Frontend integration:
  - Basic web interface or plugin.
- Graceful degradation:
  - If latency or costs are high, use shorter answers or fallback behaviors.

---

## Phase 5 – Hardening & Polish

Hardening is required throughout M1–M5. This catalogue section describes its
scope, not a final stage at which quality work first begins.

### Goals

- Improve robustness, reliability, and usability.
- Prepare for wider usage.

### Deliverables

- Automated test suite:
  - Unit, integration, and scenario-based tests.
- CI pipeline:
  - Lint, tests, basic benchmarks.
- Configurable:
  - Game systems
  - House rules
  - Cost and latency thresholds
- Documentation:
  - User guides
  - Developer guides
  - Examples

### Build Requirements

- Telemetry and logging.
- Error handling patterns.
- Documentation build pipeline (if needed).

### Deferred Follow-Up Tasks

- Candidate reference categories include creatures, rules, conditions, actions,
  spells, feats, items/equipment/treasure, hazards, afflictions/diseases, traits,
  rituals, and subsystems. Select one category by play need and approved provenance
  under M5; full-cache population is not the next delivery target.
