# Guided DM workflows, preferences and feedback

Status: design and acceptance contract, 2026-10-28. This defines the experience
to implement and verify **before writing the end-to-end DM manual**. It does not
claim that guided preparation, debrief, durable learning or player reports are
implemented. Reuse W1's campaign binding, citations and guarded review services.

Implementation update: [the guided operator-runner prototype](28-guided-agent-prototype.md)
delivers an initial subset of this contract. It does not complete the human-tested
interactive experience, canonical closure integration, recovery or live onboarding.

## Product decision

The DM should be able to start with **Prepare the next session**, **Help me run
this session**, or **Debrief this session**. DMA does the record gathering,
organization and drafting, proposes sensible choices, asks only useful questions,
and resumes saved progress. The DM supplies creative direction, corrects evidence
and approves consequential outcomes. Preparation and debrief usability take
priority over optional Discord publishing and over documenting unfinished flows.

Automate retrieval, draft organization, checklists, suggestions and handoff. Keep
uncertain recollections, proposed fiction, operating preferences, accepted world
facts, GM logs, player-report approval and external publication distinct. A choice
in an interview is not approval for every later write or publication.

## Verified starting point and gaps

| Area | Current implementation | Required improvement |
| --- | --- | --- |
| Dedicated agent | Eight read tools and four guarded request/receipt tools; fictional native host and MCP review/resume verified | A convenient ongoing conversation with workflow start/resume, rather than requiring repeated prompt/receipt commands |
| Preparation | Backend generates deterministic briefs with recent sessions, hooks, spotlight, continuity and scene seeds | Guided goal selection, source-linked editable runbook, readiness checks, artifact storage and recovery through the agent |
| Debrief | Staging, candidate decisions, promotion and separate GM-log approval exist | Question selection, progress/answer storage, uncertain or conflicting accounts, corrections, report drafts and next-session handoff |
| Learning and feedback | No dedicated workflow/preference/feedback records or agent tools were found | Private scoped records, explicit durable preferences, feedback triggers, correction/forget controls and fresh-conversation proof |
| During play | Browser notes and operational state exist; agent can read selected live state | Quick attributed event capture and a debrief inbox; no assumption that combat state is an event log |
| DM manual | Technical W1 fixture/operator setup is documented | A tested task-oriented manual for preparation, live use and closure, with prerequisites and honest limitations |

The current `scripts/run_campaign_agent.py` invokes an ephemeral `codex exec`
conversation with one `--prompt`. Its resume evidence concerns saved campaign and
review records, not a completed interactive interview or persistent preference
system. Do not label prompt wording alone as implementation of this contract.

## Shared conversation behavior

- Read relevant saved records first; show a short understanding and identify gaps.
  Do not ask the DM to repeat facts that are already available and current.
- Ask one meaningful question at a time, usually with 2–4 numbered options.
  Put a recommendation first when there is supporting evidence, explain its
  relevance briefly, and accept free text or combined choices. Support **Other**,
  **Not sure**, **Skip**, **Back**, **Correct that** and **Resume later**.
- Start in a concise guided mode. Offer quick and detailed modes; adjust the
  remaining interview to the DM's answers and available prep/debrief time.
- Distinguish a recommendation from a selection. An unanswered question never
  accepts a proposed default, approves a write or marks a step completed.
- Show progress by completed decisions and remaining blockers. Explain why a
  question matters when its connection is not obvious. Avoid a fixed exhaustive
  questionnaire and repeated confirmation of low-impact choices.
- Save authorized workflow drafts and answers automatically at meaningful
  checkpoints. Show the saved workflow/session identity. If saving is unavailable
  or fails, retain the answer in the conversation and report that it is unsaved.
  On restart, resume durable state rather than claiming unsaved chat was retained.
- Separate optional improvement suggestions from blocking facts that must be
  reconciled. A DM can intentionally leave an uncertainty unresolved.

Numbered text choices must work in both Codex and an IDE conversation; the workflow
must not depend on a proprietary multiple-choice widget. Native interactive host
behavior and the convenient entry point need verification on the actual surface.
Keep the campaign role isolated from development/shell privileges.

## A. Guided session preparation

1. Identify the campaign and intended session; offer to resume an unfinished prep.
   Read the previous approved GM log, accepted changes, unresolved hooks, player
   intentions, relevant PCs/NPCs and current operational state. Cite sources and
   distinguish live state from the accepted historical record.
2. Present a concise continuity snapshot and 2–4 plausible directions. Example:
   **1. Continue the unresolved bridge lead (recommended because of the last
   session's stated intention); 2. Return to town; 3. Explore another lead;
   4. Something else.** Examples in this document are fictional, not campaign facts.
3. Ask only for missing priorities: likely player direction, available session
   time, desired tone/pacing and any character spotlight or constraints. Reuse
   confirmed preferences while making a session-specific exception easy.
4. Draft a usable runbook: opening, likely scenes/branches, relevant NPC motives,
   encounter/reference needs, clues, player choices, fallback material and a short
   unresolved-question list. Do not railroad players or turn planned events into
   historical facts. Identify unavailable maps, rules or other source material.
5. Surface relevant reminders, each grounded in a saved record: unfinished player
   intentions, known consequences, promised spotlight, calendar commitments,
   unresolved rulings or missing prep resources. Let the DM resolve, defer or
   dismiss each; do not repeat dismissed reminders without a new reason.
6. Save the runbook as a versioned GM-private prep artifact with source revisions,
   chosen priorities and pending questions. Offer **Ready to run**, **Revise one
   part**, or **Continue later**. Readiness is a checklist result, not proof of play.

The next prep should already know the previous session's handoff. It should not
need the DM to paste old logs or restate feedback that was durably recorded.

## B. Live assistance and note capture

During play, prioritize short answers and low interruption. Support natural
commands such as **Note that the party promised to return**, **Remind me of this
NPC**, or **Flag this ruling for debrief**. Capture source, session, relevant
entities, sequence/time context and certainty. Separate DM reports from agent
suggestions and player intentions. Corrections retain their source history.

Show whether a note was saved, merely proposed or remains unsaved. Captured events
feed the debrief inbox; they do not automatically promote campaign facts. Browser
In-Game State and combat snapshots inform context but cannot reconstruct every
event. Avoid feedback questionnaires or unsolicited long planning during combat.

## C. Guided debrief, closure and next-session handoff

1. Offer to resume an incomplete debrief. Read the prep/runbook, captured events,
   operational notes and prior unresolved questions. Present an initial event
   outline, then ask what is missing or wrong instead of asking for a full retell.
2. Follow up only where necessary: outcomes, discoveries, relationships, resources,
   promises, rulings, uncertainties and what players intend next. Allow **Confirmed**,
   **Correct**, **Uncertain** and **Did not happen**. Confidence never replaces DM
   confirmation; contradictory accounts remain visible and source-qualified.
3. Draft separate outputs: private GM log; proposed fact changes; player-facing
   report(s); unresolved hooks/intentions; preparation handoff; and optional
   experience/agent feedback. Give each its own identity, revision and status.
4. Review the meaningful differences. Reuse guarded candidate decisions and atomic
   promotion. GM-log approval is distinct. Make the approval presentation concise
   and readable while preserving the exact content, revision and destination that
   the trusted operator authorizes. Repetitive manual receipt transcription is a
   usability gap to remove through a tested trusted review surface, not by giving
   the campaign agent approval-grant authority.
5. Draft player reports from explicitly revealed, appropriate material. Approved
   GM logs remain GM-private and can contain spoilers. Generate an optional short
   recap and a fuller narrative; audience-specific variants require their own
   source/audience check. Unsupported or ambiguous revelations stay out pending
   clarification. Review exact report content before marking it approved to share.
6. Save a next-session handoff with confirmed consequences, unresolved leads,
   explicit player intentions, needed prep and desired spotlight. Offer to start
   the next prep immediately or resume later. Publication is optional and requires
   its separate exact-report/destination authorization.

Local report drafting, review and handoff must work before Discord is configured.
No player report, log or workflow is marked complete while required items are
unsaved or approval/delivery results are unknown.

## Learning and feedback contract

**Learning means durable, inspectable adaptation of the DM's workflow and
preferences, not automatic model training or self-modification.** Apply the DM's
responses in the current workflow immediately. Preserve meaningful answers as
workflow state; do not classify every answer as a permanent preference or save
unbounded raw transcripts by default.

Keep these record classes separate:

| Record | Examples | Effect |
| --- | --- | --- |
| Campaign fact / session event | An NPC moved; an encounter ended | Existing reviewed campaign/log lifecycle |
| Session choice or intention | Prepare travel next; players might return | Scoped to the named session or handoff; not historical truth |
| Confirmed DM preference | Short recaps; fewer reminders; emphasize social scenes | Reused within its authorized DM/campaign scope until corrected or expired |
| Preference suggestion | Agent infers a style preference from several responses | Presented for confirmation; not silently promoted to a durable default |
| Feedback / correction | Missed a clue; summary too long; recommendation was useful | Source-linked operational feedback, with an explicit proposed adjustment |

Offer **This session only**, **Use for this campaign**, or **Make this my DM
default** when a durable preference is appropriate; broader scope needs explicit
consent. A session override takes precedence over campaign and DM defaults.
Store the source, scope, status, revision, timestamp and any expiry. Make **What
have you learned about my preferences?**, **Change that** and **Forget that**
available. Explain what deletion/retention policy applies to original source
records instead of promising that deleting a preference erases every audit record.

Ask brief, optional feedback when it can change the next interaction: after the
first use of a guided flow, after a substantive correction, at closure if useful,
or when repeated edits suggest a mismatch. Usually ask one optional question,
such as **1. Shorter; 2. About right; 3. More detail**, with room for free text.
Do not ask after every message. Honor **Not now**, reduced frequency and opt-out;
do not interpret skipped feedback as satisfaction. Keep player-experience feedback
separate from feedback about DMA's operation.

Show the proposed change: **I'll make the next recap shorter. Apply only next
time, or remember for this campaign?** Verify in the next relevant workflow that
the adjustment was actually used. Uncertain inferences, personal judgments about
players and sensitive feedback must not become player-visible facts or reports.

Preferences cannot weaken source visibility, approvals, campaign binding, tool
permissions or the campaign/development separation. The agent does not rewrite
its own system instructions, software, model weights or security policy.

## Proactive behavior without interruption

Prompt from meaningful context: workflow start/resume, an unresolved item becoming
relevant, a source changing, a session ending or the next prep beginning. Give the
reason and offer a useful action. Maintain reminder status and snooze/dismiss
scope so the same item is not repeatedly raised. Mark outdated recommendations
when their supporting records change.

Initially this happens inside an active DM conversation or explicitly started
workflow. Notifications while the agent is closed require separately configured
scheduling and notification preferences; no always-on assistant or reminder
service is implied by this design.

## Implementation slices and manual gate

Keep W0–W6 identifiers stable, but make the preferred local implementation order
**W2a → W2b → W4a → local W5 rehearsal → manual**, followed by optional W3
publishing and broader W4 live assistance. W1 is reused, not reopened as incomplete.

1. **W2a — durable guided workflow foundation:** versioned workflow/answer state,
   start/resume/back/correct/skip operations, capture inbox, scoped preference and
   feedback records, authorized draft autosave and a convenient interactive entry
   point. Define narrow agent tools and trusted review actions. Do not put these
   records into generic campaign entities or reopen archived browser modules.
2. **W2b — closure:** adaptive debrief, corrections/uncertainty, GM log and candidate
   review, player-report drafts and audience checks, and saved next-session handoff.
   Streamline the operator review experience without weakening W1 enforcement.
3. **W4a — preparation:** guided source-based runbook using accepted closure output,
   saved preferences and reminder state. Reuse the existing prep builder where
   useful; deterministic briefing alone is not the conversational workflow.
4. **W5 local rehearsal and manual:** run fictional prep → live capture → debrief →
   reviewed log/report → fresh-conversation next prep. Then write and human-test
   the requested manual's setup, before/during/after chapters against the verified
   entry point. Identify genuinely necessary manual decisions in the manual.

Required acceptance cases include:

- Fresh conversation resumes an interrupted interview without repeating answered
  questions; failed writes remain honestly unsaved and retries do not duplicate.
- Numbered and free-text answers, combined choices, skip/back/correction and
  quick/detailed modes alter subsequent prompts appropriately.
- Draft autosave stays within the operator-authorized scope; selection never
  invents an approval or changes canon/publication authority.
- An uncertain claim is deferred, a false claim is rejected, an accepted event
  enters the reviewed log/canon, and the next prep selects the correct sources.
- A GM secret appears in the private account but not in any player-report variant;
  report revision/audience changes require renewed share approval.
- A style preference is confirmed and used after restart; a session exception does
  not overwrite it; correction/forget/feedback opt-out have demonstrable effects.
- Relevant reminders appear once, include their source and reason, respect snooze,
  and change when evidence changes. No unsolicited live-play feedback barrage.
- Actual native Codex or IDE interaction proves the workflow, alongside protocol
  tests. Simulated choices or a prompt document alone are insufficient evidence.

This is a design gate, not authorization to attach real campaign data, publish
reports, start schedules, change host permissions or push further code to GitHub.
