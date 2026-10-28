# Guided DMA workflow prototype

Status: 2026-10-28. Implemented operator-runner prototype for **fictional fixtures
and explicitly prepared, verified private rehearsal copies**. Direct live
campaign paths remain forbidden. The full usability contract in [document 27](27-guided-agent-workflows-and-feedback.md)
is not yet complete. This is a technical trial guide, not the final DM manual.

## What works

The trusted local runner presents numbered preparation/debrief questions around
the existing restricted Codex agent. The agent produces source-grounded initial
and final briefs; the runner saves operator answers and private draft artifacts.
It does not add MCP tools, grant shell access, edit the campaign agent's policy or
give it approval authority. Only launch this from the development/operator Python.

Supported behavior:

- Guided and quick interviews; numbered/combined choices, free text, skip, back,
  corrections, private notes and pause/resume. A matching session/kind resumes by
  default; `--new` starts an additional workflow.
- Revisioned private autosave, retry-key deduplication and separate source history.
  Changed answers invalidate generated drafts and report approval.
- An initial and final native Codex brief using approved history, live-state
  context, interview answers, confirmed preferences and a clearly unreviewed
  previous debrief handoff. The agent can use its existing bounded read tools.
  Changed supporting snapshots during generation reject the draft for refresh.
- A private event-note inbox for the named session; debrief uses that workflow's
  captured notes rather than treating combat snapshots as a complete history.
- Separate private GM account, proposed change-review text, full/short player
  recap drafts and next-session handoff. Player recap text is drawn exclusively
  from the operator's explicitly entered `revealed` answer, not a model summary
  of the private GM account. Review still catches mistaken disclosure choices.
- Optional short feedback and explicit confirmation before remembering detail
  preferences for this operator/campaign. Session feedback can change the current
  brief without changing the durable default. Preferences are inspectable and
  forgettable; feedback/reminders can be turned off. Remembered settings never
  expand tools or permissions.
- Once-per-workflow/source reminders referencing approved history and the prior
  unreviewed handoff. A new source context may produce a new reminder. This is
  not an always-on notification service or a full reminder scheduler.

## Setup and entry points

First follow [the guarded W1 setup](25-campaign-agent-review-and-acceptance.md).
Use a generated `--review-tools` fictional fixture with functioning Codex/MCP
environments, or the separately verified [private rehearsal profile](29-private-rehearsal.md).
Do not point this prototype at an existing live campaign store.
The fixture's onboarding, binding, OS operator and SQL/overlay epoch are checked.

From the repository root, Windows PowerShell:

```powershell
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --kind prep --session "next-session" --mode quick
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --capture --session "next-session"
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --kind debrief --session "next-session"
```

macOS/Linux uses the same arguments with `python3`. That platform has not been
executed. Use `--codex` if the CLI is not on PATH. Startup/native failures report
an error and preserve saved answers; no automatic switch to an offline answer
pretends that the agent succeeded. Private native diagnostics, when available,
are retained beside the binding as `guided-agent-last-error.txt`.

`--offline` explicitly rehearses the draft workflow without a model. Its output
contains diagnostic source context, is GM-private, and is not native-agent proof.
For example, add `--offline` to a fictional prep/debrief command above.

Additional operations (use `python3` on macOS/Linux):

```powershell
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --list
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --show "<workflow-id>"
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --resume "<workflow-id>"
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --resume "<workflow-id>" --correct intentions
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --preference detail --value short
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --preference feedback --value off
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --preference reminders --value off
python -m scripts.run_guided_campaign --binding ".codex-temp/w1-demo/binding.json" --preference detail --value forget
```

Other detail choices are `balanced`/`detailed`; reenable feedback with `ask` and
reminders with `show`. Interview and preference changes require a real operator
terminal. List/read operations do not require interactive confirmation.

## Drafts, review and storage

The runner stores `guided-workflows.sqlite3` beside the generated fixture binding.
It is a **private sidecar**, separate from campaign SQL, overlay files, W1 receipt
approvals and accepted logs. The scope includes binding, campaign, epoch, physical
store paths and OS operator. A changed scope does not silently inherit workflows
or preferences. Never commit or share this database. Include it in a future
reviewed paired-recovery plan before real campaign activation; W0's old fixture
recovery does not automatically back up this newly introduced sidecar.

Interviews retain answer/correction history. Forget removes an active preference;
it does not erase original answers or the preference audit trail. A context size
limit rejects oversized updates without discarding earlier checkpoints. Output,
native diagnostics and terminal history should be treated as GM-private.

At debrief end, an operator may inspect the exact player-only packet and approve
it for the group using the existing interactive `APPROVE <hash>` confirmation.
That packet contains neither GM account nor feedback. Approval binds the workflow
revision, content and audience; subsequent edits invalidate it. Nothing is sent
externally. The OS process is trusted here; no model-controlled workflow write or
approval tool exists.

The GM account and candidate text remain **drafts**. Canonical staging/promotion
and GM-log acceptance still use the separate W1 guarded agent/operator workflow.
The prototype does not silently stage or accept these outputs. The final manual
must not describe draft production as completion of that approval lifecycle.

## Remaining usability work

Before the final manual/live onboarding: human-test and simplify the operator
entry/review surface; connect the packet to W1 staging without receipt copying;
expand adaptive question selection beyond the current concise guided/quick sets;
add per-reminder snooze/dismiss management; broaden explicitly scoped preferences
and richer report templates; verify recovery including the sidecar; and rehearse
the full accepted-history → closure → next-prep cycle. Cross-campaign DM defaults,
background notifications, Discord publication and native Codex-app/IDE chat
widgets are not implemented by this terminal runner. It uses native Codex CLI
internally, and can run from an IDE terminal.
