# Campaign agent setup: read-only W1 foundation

Status: 2026-10-28. This is the optional eight-tool read-only foundation.
The full [guarded campaign profile and W1 acceptance](25-campaign-agent-review-and-acceptance.md)
add operator approval, staging, review and a verified dedicated Codex conversation.
Both use fictional onboarding; neither attaches a real campaign automatically.
The backend now has [review revision/transaction guards](20-campaign-data-ownership-and-review.md),
including atomic log finalization. They do not grant the campaign agent write
tools or authenticate human approval.

## What is available

`backend.agent.mcp_server` exposes eight GM-only read tools using the official
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0).
The [operating contract](23-agent-operating-and-data-contract.md) uses dotted
capability names; installed MCP names use underscores:

| MCP tool | Selected source |
| --- | --- |
| `campaign_describe` | Verified binding identity, schema, role, recovery epoch, capabilities |
| `campaign_read_sessions` | Explicit overlay session associations |
| `campaign_read_entities` | Accepted SQL entities |
| `campaign_read_history` | Approved, eligible session logs only |
| `campaign_read_provenance` | Reviewed SQL entity provenance |
| `campaign_read_notes` | One exact allowlisted overlay collection/item |
| `session_read_live` | Operational live state and actual revision |
| `session_read_review` | Pending draft headers or one explicitly selected draft |

Each result carries its GM audience, campaign/binding/epoch, source namespace,
stable ID, content hash, and a `dma://` citation. Overlay sources additionally
carry the file hash; SQL revision/timestamp tokens are returned where present.
These citations identify returned snapshots; they are not public URLs or a
historical snapshot store. SQL and overlay IDs are separate namespaces.
Use `campaign_read_sessions(session_id=...)` and
`campaign_read_history(document_id=...)` to resolve saved references directly,
including older sessions outside the bounded listing window. Explicit log reads
still exclude pending/rejected/ineligible history.

There is no shell, HTTP proxy, arbitrary file path, SQL query, or write tool.
SQLite opens in read-only/query-only mode. Each call checks schema and matching
SQL/overlay binding markers. Missing sources return `missing`; invalid or foreign
sources fail. The reader never substitutes SQL for overlay or reads a vault.
It imports no application settings and has no default live database path.

## Prepare a fictional campaign

Run from the repository root using the existing backend development environment.
The MCP environment must be separate: its SDK needs newer Pydantic dependencies
than the currently pinned backend. Do not install agent requirements into the
backend environment. Paths below are local examples, not committed configuration.

Windows PowerShell:

```powershell
python -m venv ".codex-temp/agent-env"
& ".codex-temp/agent-env/Scripts/python.exe" -m pip install -r backend/requirements-agent-dev.txt
python -m scripts.prepare_campaign_agent_fixture --workspace ".codex-temp/agent-fixture" --agent-python ".codex-temp/agent-env/Scripts/python.exe"
& ".codex-temp/agent-env/Scripts/python.exe" -m backend.agent.mcp_server --binding ".codex-temp/agent-fixture/binding.json" --check
& ".codex-temp/agent-env/Scripts/python.exe" -m scripts.verify_campaign_agent_connection --binding ".codex-temp/agent-fixture/binding.json" --report ".codex-temp/agent-fixture/mcp-verification.json"
```

macOS/Linux (documented equivalent; not yet run on macOS):

```sh
python3 -m venv ".codex-temp/agent-env"
".codex-temp/agent-env/bin/python" -m pip install -r backend/requirements-agent-dev.txt
python3 -m scripts.prepare_campaign_agent_fixture --workspace ".codex-temp/agent-fixture" --agent-python ".codex-temp/agent-env/bin/python"
".codex-temp/agent-env/bin/python" -m backend.agent.mcp_server --binding ".codex-temp/agent-fixture/binding.json" --check
".codex-temp/agent-env/bin/python" -m scripts.verify_campaign_agent_connection --binding ".codex-temp/agent-fixture/binding.json" --report ".codex-temp/agent-fixture/mcp-verification.json"
```

Choose a new workspace each run. Existing workspaces and report files are never
overwritten. The generator runs W0's full-schema fictional recovery rehearsal,
then binds only the generated restored pair. It ignores inherited live database
and private-root settings. Everything generated stays under the chosen workspace.
No local MCP API key is needed; any later model-host authentication is separate.

The output includes `binding.json`, SQL/overlay identity markers, saved session
links, `campaign-workspace/AGENTS.md`, and `codex-config.example.toml`. The source
instructions are [agent/campaign-agent.md](../agent/campaign-agent.md); the same
instructions are supplied through MCP initialization and `campaign_resume`.

The verification script starts two fresh MCP processes, checks the exact read
tool set, follows a saved session reference, compares source citations, and
rejects writes and scope overrides. It tests the protocol connection, not an
LLM's interpretation of those records.

## Dedicated host setup

The generated TOML is a reviewable template, not an automatically installed
configuration. Its stdio command, arguments, working directory, enabled tool list,
and required startup follow the official [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
It requests a read-only sandbox, disabled web search, and disabled `shell_tool`
following the [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).

Use a dedicated campaign workspace and a host configuration/profile exposing
only this reader. Review the host's effective tools: other inherited MCP servers,
apps, developer tools, and filesystem tools must not be available to the campaign
agent. The server's read-only scope does not restrict unrelated host capabilities;
instructions and MCP tool annotations alone do not enforce that separation.
Do not replace the development chat's configuration or built-in instructions.

For a different host, open a fresh dedicated conversation, verify the effective
tool list, describe the binding, resume from saved session associations, cite an
approved record, distinguish pending/live data, and handle a missing source and
unavailable mutation honestly. Capture the actual interaction before calling the
dedicated setup verified. The full guarded profile's native Codex checks are now
recorded in the [W1 completion record](work-records/2026-10-28-w1-campaign-agent-completion.md).
A browser screenshot is not evidence for this interface;
this slice changes no browser UI or archived module.

## Binding and recovery

The binding format is `dma-agent-binding-v1`, GM role only, at schema
either `20261007_0006` or `20261028_0007` for reads; approval/staging require
`20261028_0007` and its separate receipt table. It names one campaign, one SQLite database, one private project
root, a binding ID, and a recovery epoch. Paths resolve relative to the binding
file unless absolute. The database context `campaign-agent-binding` and private
root `.dma-agent-binding.json` must exactly match the four identity fields.
The first deployment supports a single campaign per database; foreign campaign
drafts prevent reads. This is not a multi-tenant authorization system.

Session associations live at
`campaigns/<campaign-id>/agent-session-links.json`, with `campaign_id` and an
`items` array. Each stable session `id` links explicit `overlay_session_id`,
`draft_ids`, and `log_document_ids`. Do not infer associations from similar titles.
The fixture generator provisions these records only for its generated campaign;
a reviewed live provisioning/migration path is still needed.

After restore or source replacement, stop the agent, rotate/reconcile the binding
epoch and both markers, and start a new conversation. The reader rejects a
mismatched pair; the [W0 recovery procedure](23-agent-operating-and-data-contract.md)
still governs the actual restore. Real campaign attachment requires explicit
authorization and a reviewed binding/backup plan. Never commit binding manifests,
generated config, private overlay files, or model transcripts containing GM data.

## Regression checks

Run reader/protocol tests in the isolated agent environment:

```powershell
& ".codex-temp/agent-env/Scripts/python.exe" -m pytest -q tests/unit/test_campaign_agent_reader.py tests/integration/test_campaign_agent_mcp.py
```

```sh
".codex-temp/agent-env/bin/python" -m pytest -q tests/unit/test_campaign_agent_reader.py tests/integration/test_campaign_agent_mcp.py
```

`make agent-test AGENT_PYTHON="path/to/agent/python"` is the equivalent target.
Run `python -m pytest -q tests/integration/test_campaign_agent_fixture_cli.py`
(or `python3`) in the backend environment for full-schema onboarding. The MCP
integration test explicitly skips when the SDK is absent; that skip is not a
successful protocol check. The Make target checks for the SDK before testing.
On Windows, an existing inaccessible pytest TEMP root can be avoided with
`-p no:cacheprovider --basetemp=".codex-temp/<new-test-directory>"`; always select
a new disposable directory because pytest owns that directory. Restricted
execution environments must permit Windows asyncio's internal socket pair even
though this MCP server communicates over stdio and opens no network listener.
Staging, approval, promotion, prep preview, report
publication, and player access remain unavailable through this reader.
