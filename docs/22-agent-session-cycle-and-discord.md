# DMA agent, session cycle, and Discord delivery plan

Last reviewed: 2026-10-28. Status: W0 contract and fictional recovery verified;
W1 sufficient for the local fictional GM workflow, including native Codex
interaction, separately approved staging/review and restart; W2-W6 remain open.
macOS, live attachment and human play-testing are not claimed. This document defines the active product
delivery order alongside the engineering gates in
[the roadmap](05-roadmap-and-milestones.md).

## Purpose and operating model

DMA helps the human DM prepare, run, and learn from each session using rules,
campaign knowledge, and persistent records. Its primary delivery milestone is a
verified complete session cycle, rather than the presence of individual tools.

| Surface or component | Responsibility | Boundary |
| --- | --- | --- |
| DMA browser application | Session workspace: maps, references, characters, card-based combat, and operational controls | Writes identify their store and revision; current state is not automatically an approved session history |
| DMA agent | Conversational preparation, grounded live assistance, guided debrief, proposed campaign updates, logs, and player-report drafts | Initially operated directly in Codex or an agent-capable IDE; another chat environment needs an explicit data/tool connection |
| Shared campaign services and storage | Read current state, stage changes, record review decisions, promote facts, retain sources, and supply subsequent prep | Follow the SQL/private-overlay ownership contract; no silent synchronization of overlapping fields |
| Discord interface | Publish approved player reports, later answer player questions | Player requests use separately authorized sources and tools; no general access to GM knowledge or campaign writes |

The campaign agent needs its own durable instructions, tools, and onboarding.
The software-development assistant and this chat history do not constitute that
setup. Campaign operation must not grant authority to change application code,
Git history, credentials, or deployment configuration. Host-specific setup will
be verified when implementing the agent; no automatic chat-to-repository access
is assumed.

Obsidian remains retired. The private overlay stays at
`local-private-overlay/project-root/`; it is not copied into public drop zones.
Current Combat stays card-based. Archived panel modules remain archived under
[the existing archive decision](21-dm-panel-module-archive.md). Agent review is
the intended accessible alternative; restoring a panel module requires its own
explicit request and verification.

## Current position

Existing code provides prep briefs, live state, campaign imports, and staged
session-update APIs with atomic promotion and provenance. This is a useful
foundation, not evidence of a completed recurring workflow. Prep is currently
deterministic; conversational model behavior needs separate evaluation. The
session-review panel is archived, guided debrief is missing, and the frontend
player-PDF export is disconnected. No Discord delivery or question-answering
implementation has been established by this review.

The Oct 8 engineering baseline remains dated in the roadmap. W0's later
contract/recovery evidence is in the
[W0 work record](work-records/2026-10-27-w0-operating-contract-and-recovery.md).
Focused fixture verification does not establish full CI or release readiness.

## Active product delivery sequence

W0 is complete for its contract/fixture scope in the
[operating and data contract](23-agent-operating-and-data-contract.md). The
trusted agent adapter, session linking, and approval enforcement are W1/W2 work;
they are not deployed by W0. Reuse existing M1-M5 engineering work and its
evidence; do not restart implemented features. Every implementation slice must
reevaluate its sufficient/excellent criteria immediately before work begins.

| Order | Deliverable and dependencies | Sufficient completion | Excellent completion |
| --- | --- | --- | --- |
| W0 | Operating and data contract; start here, building on M2 | Define field owners, campaign/session IDs, draft/approved states, visibility, read/write tools, approval boundaries, and a DB-plus-overlay recovery procedure; conflicts never silently overwrite facts | Rehearse restore with disposable paired fixtures and document stale-write/conflict recovery and onboarding |
| W1 | Dedicated campaign-agent setup; depends on W0 | Durable instructions and a verified tool connection support loading a campaign, reading current state, citing sources, staging updates, and explicit review; a fresh conversation can resume from saved records | Repeatable Windows/macOS setup, missing-source and unavailable-tool handling, and tested separation of campaign operation from software-development privileges |
| W2 | Session closure; depends on W1 and existing M2 review services | Agent interviews the DM, retains uncertain claims as drafts, produces a GM log and separate player-report draft, reviews candidates individually, promotes accepted facts, separately finalizes the log, and saves unresolved hooks/player intentions for next prep | Resumable debrief, source-linked field changes, corrections and conflicting recollections, idempotent retries, revision-bound approval, and useful report templates |
| W3 | Discord report publishing; depends on W2, player-source approval, and focused quality gates | Preview exact report and target channel; DM authorizes that report revision; webhook publishes it to a configured channel and records confirmed delivery or failure | Recover safely after timeouts and retries without duplicate posts, support reviewed corrections, and show revision/message delivery history |
| W4 | Connected preparation and live assistance; depends on W2 and W0 data ownership | Agent prepares from approved facts/history and explicit focus, saves a usable runbook, reads relevant live state, distinguishes suggestions from facts, and offers explicit capture of session events | Source IDs/revisions explain prep, stale inputs prompt refresh, uncertain answers abstain, and grounded suggestions meet scenario and measured latency/cost criteria |
| W5 | Complete session-cycle rehearsal; depends on W2/W4, with W3 tested if enabled | A fictional campaign completes prep, browser play, restart/recovery, debrief, fact/log review, player-report approval, and next prep; approved changes appear and rejected/deferred claims stay excluded | Repeat across multiple sessions, include interruptions/conflicts and report corrections, then record a representative DM play-test |
| W6 | Discord player questions; depends on W3, W5, and the tested player access boundary | Bot handles explicit commands such as `/recap` and `/ask-dma`, answers only from authorized sources, abstains on missing evidence, and stages corrections for DM review | Test adversarial spoiler requests, identity/channel restrictions, stale or revoked sources, multi-turn isolation, rate/cost limits, and offline recovery |

W3 is the first Discord increment and can follow session closure without waiting
for broad assistant or reference-corpus expansion. It does not block a local-only
W5 rehearsal when Discord is not configured. Always-on Discord hosting and bot
deployment are separate operational decisions, not prerequisites for local DMA.

Engineering hardening runs throughout W0-W6. Before a slice relies on a service,
verify its relevant M1-M3 gates. Full checkpoint/release acceptance still requires
the roadmap's complete CI, migration/recovery, and browser checks; a focused
slice does not waive those gates. Broad refactoring follows demonstrated workflow
needs and must preserve working behavior.

## Session artifacts and transitions

1. **Prepare:** select campaign/session and focus; read approved history and facts;
   save prep with source IDs/revisions, runbook, open questions, and draft status.
   Future scenes and encounters remain proposals rather than historical events.
2. **Play:** use the browser workspace and agent; capture events, rulings,
   discoveries, loot, NPC changes, and player intentions with time/source context.
   Saving combat state or a chat message does not approve those claims as canon.
3. **Debrief:** reconcile captured notes with the DM's account. Ask about missing
   events, outcomes, uncertainties, player experience, and next-session intentions.
   Keep subjective feedback distinct from in-world facts.
4. **Review and log:** create a private GM log and candidate updates. Preserve
   accept/reject/defer decisions, source provenance, and conflicts. Promote accepted
   candidates atomically, then separately approve the log using the existing M2
   lifecycle. Neither action approves publication.
5. **Report:** draft a player account from approved, revealed material. Review for
   spoilers, inaccuracies, and character-specific secrets. Record the approved
   report revision, permitted audience, and destination before publication.
6. **Continue:** carry approved consequences, unresolved hooks, and explicitly
   marked intentions into next-session prep. Preserve links to the previous
   session, reviewed log, report, and source revisions so the cycle can resume in
   a new conversation without depending on chat memory.

Record artifact identity, campaign/session, status, revision, source links, and
visibility. Agent suggestions, player claims, and uncertain recollections remain
drafts until reviewed. Existing trusted immediate-write import routes must not
silently replace staged review for uncertain debrief or player input.

## Discord stages and access contract

### Stage A: approved report publication (W3)

Use a channel webhook for outbound publication. A bot is not required for this
stage. Keep credentials in ignored local configuration, validate the destination,
and disable automatic mentions by default. Publication approval covers the exact
content revision and destination; edits invalidate that approval. Retain the
report ID/revision, channel, returned message IDs, time, and outcome. A timeout
with unknown delivery requires reconciliation before resending. Support long
reports through reviewed message splitting or an approved attachment format.

Planning this interface is not authorization to create credentials, connect a
real server, deploy a service, or post messages. Those happen in a separately
requested implementation/configuration task with the chosen server and channel.

### Stage B: player questions (W6)

Use a bot/application with explicit commands before considering ambient message
listening. Enforce campaign, server, channel, and user access in application code.
The answering path receives only approved player reports, revealed facts,
approved handouts, and eligible rules material. It must not retrieve GM-only
notes, unrevealed adventure text, private debriefs, hidden maps, or other players'
secrets and then rely on a prompt to suppress them.

Start with group-visible knowledge. Character-specific private answers require a
separate identity/access design and tests before enabling them. Apply source
visibility before retrieval and context construction; prevent leakage through
citations, attachments, caches, tool results, logs, and conversation history.
Player messages and retrieved documents cannot grant new tool permissions.

Answers identify supporting player-visible sources and uncertainty. Missing
knowledge must not be answered from GM memory or invented as canon. Player
corrections become private review candidates; the bot has no direct campaign-fact
write authority. Track model usage and enforce limits with useful unavailable,
timeout, and exhausted-budget responses.

### Runtime and operational decisions

Outbound reports can be sent during an explicit local publishing run. Answering
questions while the DM's computer is off requires a separately hosted service.
Before deployment, select hosting, model/provider, budget, credentials handling,
data retention, monitoring, and offline behavior. Host only the minimal authorized
player dataset; do not upload the private overlay wholesale. Whether commands
arrive by Gateway or HTTP is an implementation choice to verify against current
Discord documentation. No inbound exposure of the local DM panel is assumed.

Technical references for implementation (recheck when starting each slice):

- [Discord webhooks](https://docs.discord.com/developers/resources/webhook)
- [Discord interactions and commands](https://github.com/discord/discord-api-docs/blob/main/developers/platform/interactions.mdx)

## Acceptance and release evidence

Apply [the task completion standard](06-testing-and-quality.md) and record
implemented, automatically verified, browser verified, and play-tested separately.
The external agent and Discord also need interaction evidence on their actual
surfaces; browser evidence alone cannot verify them.

The W5 fixture must include a confirmed event, a rejected claim, a deferred
uncertainty, a GM secret, a revealed fact, a disputed entity update, and an
interrupted save/debrief. Verify durable approved history, source traceability,
correct next prep, and the absence of secrets in the player report. For W3/W6,
use mocked delivery and a separately authorized test channel; include wrong
destination, duplicate/retry, revoked visibility, unsupported question, and
attempted permission escalation cases.

Sufficient product completion is one repeatable full cycle with documented
manual steps, durable reviewed records, and a checked player report. Excellent
completion adds repeated sessions, smooth recovery, consistent agent/browser
state, and real-play evidence. Discord publication and player Q&A each have
their own gates; neither is implied by core local-cycle completion. Missing
tests, unverified required interactions, unexplained state drift, or any exposed
GM secret keeps the affected milestone open.

## Parked and later work

- Full AoN acquisition remains parked pending a suitable authorized source/export.
  A small approved fixture corpus is sufficient for this workflow work.
- Real MapTool integration remains experimental and deferred.
- Broad rules-system expansion, ambient Discord listening, character-private
  answers, and a replacement in-browser conversational agent await demonstrated
  needs and separate acceptance criteria.
- Existing deployment, backup, data ownership, provenance, and public/private
  boundaries remain in force; this plan does not migrate live campaign data.

W1's binding, durable instructions, and read-only MCP connection are now verified
with fictional data; see [setup and limits](24-campaign-agent-setup.md) and the
[work record](work-records/2026-10-27-w1-read-only-agent-connection.md).
The review backend now provides optional draft revision checks and atomic
SQLite review/log transactions; see the
[guard work record](work-records/2026-10-27-w1-review-revision-and-transaction-guards.md).
W1 is now sufficient; the [guarded profile guide](25-campaign-agent-review-and-acceptance.md)
and [completion record](work-records/2026-10-28-w1-campaign-agent-completion.md)
record actual host interaction, trusted operator receipts and their limits.
Next is W2 guided debrief/session closure. Retain current stores, W0 ownership
restrictions and separate approval for accepted facts, GM log and player reports.
