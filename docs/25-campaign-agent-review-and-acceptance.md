# Dedicated campaign agent: guarded review and W1 acceptance

Status: 2026-10-28. W1 meets its **sufficient** criteria for the local fictional
GM workflow. Windows/Python 3.11 and a real dedicated Codex CLI conversation are
verified. macOS commands are documented but untested. Real campaign attachment,
live migration, deployment and a representative human play-test remain separate
gates. No archived DM panel module is reactivated.

## Use the dedicated fixture profile

Use the backend development Python for preparation/operator commands and the
isolated MCP environment for the server. Keep the environments separate; the
MCP SDK and backend currently need different Pydantic versions. The
[read-only setup](24-campaign-agent-setup.md) explains dependency installation.

Windows PowerShell, from the repository root:

```powershell
python -m scripts.prepare_campaign_agent_fixture --workspace ".codex-temp/w1-demo" --agent-python ".codex-temp/agent-env/Scripts/python.exe" --review-tools
python -m scripts.run_campaign_agent --binding ".codex-temp/w1-demo/binding.json" --codex codex --prompt "Resume this campaign and summarize the pending review work, citing your sources."
```

macOS/Linux:

```sh
python3 -m scripts.prepare_campaign_agent_fixture --workspace ".codex-temp/w1-demo" --agent-python ".codex-temp/agent-env/bin/python" --review-tools
python3 -m scripts.run_campaign_agent --binding ".codex-temp/w1-demo/binding.json" --codex codex --prompt "Resume this campaign and summarize the pending review work, citing your sources."
```

Choose a new workspace when regenerating. If `codex` is not on PATH, pass the
installed CLI's absolute path to `--codex`. The launcher uses existing Codex
authentication; it does not copy credentials or edit global configuration.
Each invocation is a fresh ephemeral conversation, resuming from saved records.
The final campaign answer prints normally. `--events <new-file.jsonl>` retains
tool/event evidence locally; `--json` additionally prints that full event stream.
Treat all real-campaign transcripts as GM-private if live use is later enabled.

The fixture generator upgrades a new disposable SQL store through
`20261028_0007`, pairs it with fictional overlay data, writes durable campaign
instructions and a reviewed MCP configuration template, and creates explicit
saved session associations. It does not select or migrate an existing database.
Both the operator console and the backend gateway initially require this
generated fixture onboarding record and bound paths inside that workspace.

## Stage and review with separate authority

The full profile exposes the eight read tools plus:

| Tool | Effect |
| --- | --- |
| `session_stage_update` | Creates a pending request for the exact source/title/session/attribution and retry key. It does not yet create a draft or accept facts. |
| `review_propose` | Requests a specific candidate choice, promotion, or GM-log decision at the displayed draft revision. |
| `review_receipt` | Reads one exact receipt and any retained result. |
| `review_execute` | Consumes an already operator-approved receipt; otherwise fails. Completed retries return the saved result. |

Ask the agent to capture the exact DM account, with a stable source reference and
retry key. It returns a receipt ID and describes the proposed effect. Then the
operator uses a **separate interactive terminal**, for example on Windows:

```powershell
python -m scripts.review_campaign_approval --binding ".codex-temp/w1-demo/binding.json" show --approval-id "<receipt-id>"
python -m scripts.review_campaign_approval --binding ".codex-temp/w1-demo/binding.json" approve --approval-id "<receipt-id>"
```

Use `python3` on macOS/Linux. Review the complete displayed source, parsed
candidates, current SQL values, operation, session and binding, then type the
exact `APPROVE <displayed-hash>` confirmation. Piped input and `--yes` are not
supported. The record uses the process's OS account identity, not a supplied
reviewer string. Windows resolves `DOMAIN\account`; POSIX resolves the UID.
The campaign agent has no approve/grant/revoke tool and no backend shell access.

After approval, ask the agent to execute that receipt and reread the saved
records. An operator may also use the console's `execute` action manually.
`revoke --approval-id ...` cancels a pending/approved receipt without changing
campaign facts. Candidate acceptance, canonical promotion and GM-log approval
each require a distinct receipt. Rejection requires a reason. Deferral stays out
of canon and is not silently changed later.

For a console-only fixture demonstration, the generator also writes
`operator-review-request.json`. Submit it with the console's
`propose --request <that-file>` action, then show/approve/execute as above.
This example is an existing fictional candidate choice, not a real campaign log.

## What the approval record guarantees

The separate `campaign_approvals` SQL table stores the exact operation/source,
parsed candidates, source hash, displayed draft revision, current SQL snapshot,
session association and its source tokens, binding/GM role/schema/recovery epoch,
physical store destination, operator identity, expiry and retained result.
Approval requests expire after 15 minutes. Approval alone changes no draft or
accepted fact. Source references supplied with a staged account are attribution,
not independent validation or approval authority.

The executor reserves SQLite's writer, rechecks the stored intent and all bound
inputs, performs the existing review operation without committing inside it,
and commits the result and receipt consumption together. Mid-operation failures
roll back both. A completed receipt can return its historical result after
expiry, but cannot authorize another operation or survive a changed binding or
restore epoch. A stable stage retry key prevents duplicate drafts and rejects a
different source submitted with that key. An expired/revoked request must be
reconciled explicitly; never overwrite its tokens just to force a write.

Completed staged receipts provide explicit SQL session-to-draft associations,
with their own SQL source citations, alongside the original overlay association.
They require matching campaign/binding/epoch and database/private-root paths.
The agent can resume by those IDs; it does not join records by similar names.
After a restore or store relocation, old receipts and their old-scope links are
not reused automatically. Follow W0's stopped-writer restore procedure and have
the operator review/rebind associations. Binding metadata and association files
are operator-controlled configuration, not ordinary campaign-agent write targets.

The initial conservative approval fingerprint includes all campaign entity and
relationship rows. Any intervening accepted-world edit invalidates approval;
intent display is capped at 500 KB. A narrower field/relationship adapter is a
later improvement for large campaigns. SQL writer locking cannot make external
filesystem edits transactional: stop/reconcile binding/association writers before
restore or reconfiguration. External embedding calls are not rolled back; the
fixture gateway disables embeddings. Other database engines are unverified.

## Host restriction and verified limits

The launcher uses documented [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
and [CLI controls](https://learn.chatgpt.com/docs/developer-commands): it ignores
user config, disables shell, apps, plugins, browser/search, memory, image and
workspace/delegation tools, uses a read-only filesystem, and requires the exact
twelve-tool DMA MCP server. Durable campaign instructions are loaded directly;
development project instructions do not become its role. Codex's isolated Code
Mode router remains enabled because this client needs it to dispatch MCP calls.

Only `review_execute` has an explicit MCP transport permission override; the
documented [per-tool MCP setting](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
lets the server inspect a receipt without another generic host prompt. It does
**not** grant application approval: native-host and SDK checks show unapproved
receipts still fail at the backend. All write authority remains in the separate
operator record. No hook/sandbox bypass flags are used.

Codex CLI 0.164.0-alpha.11.1 still advertises its built-in `apply_patch` tool.
It is not an exported DMA capability. The campaign instructions refuse its use,
and the native read-only sandbox is the enforcement backstop: a controlled
Windows canary test could read the file but received `Access is denied` on a
write, leaving it unchanged. Do not claim that the native tool disappears from
the inventory or that instructions alone provide isolation. Reverify the host
after CLI/configuration changes. This is not protection against a compromised
operator account, edited implementation, or another application with direct DB
access. Legacy local HTTP APIs retain their original trusted-operator behavior;
they must not be exposed as unauthenticated remote agent mutation endpoints.

## Repeat the checks

Backend Python:

```powershell
python -m pytest -q tests/integration/test_campaign_approvals.py tests/integration/test_session_review_guards.py tests/integration/test_session_update_review_api.py tests/unit/test_campaign_agent_launcher.py
```

MCP environment, Windows PowerShell:

```powershell
$env:DMA_TEST_BACKEND_PYTHON = (Get-Command python).Source
$env:DMA_W1_FIXTURE_BINDING = (Resolve-Path ".codex-temp/w1-demo/binding.json").Path
& ".codex-temp/agent-env/Scripts/python.exe" -m pytest -q tests/unit/test_campaign_agent_reader.py tests/integration/test_campaign_agent_mcp.py tests/integration/test_campaign_agent_review_mcp.py
```

macOS/Linux equivalent:

```sh
DMA_TEST_BACKEND_PYTHON="$(command -v python3)" DMA_W1_FIXTURE_BINDING="$PWD/.codex-temp/w1-demo/binding.json" ".codex-temp/agent-env/bin/python" -m pytest -q tests/unit/test_campaign_agent_reader.py tests/integration/test_campaign_agent_mcp.py tests/integration/test_campaign_agent_review_mcp.py
```

The guarded MCP test copies the generated fixture, uses a test driver to simulate
the separate operator, and opens three fresh SDK conversations through the full
stage/review/promote/finalize/resume cycle. It is not a real human play-test.
`make agent-review-test AGENT_PYTHON="<isolated-python>"` requires the same two
environment variables. The [completion work record](work-records/2026-10-28-w1-campaign-agent-completion.md)
separates protocol, native model interaction, sandbox and platform evidence.
