# W1 first slice: read-only campaign agent connection

Date: 2026-10-27. Local Windows/PowerShell, Python 3.11, repository branch
`codex/local-reconciliation-20261027`. No commit, push, live migration, real
campaign attachment, global Codex configuration change, or browser UI change.

## Result and scope

Implemented the first W1 slice: explicit campaign binding, durable campaign-agent
instructions, eight restricted read tools, fictional onboarding, and an actual
MCP stdio connection using the official SDK pinned to `mcp==1.26.0`.
See [setup](../24-campaign-agent-setup.md) and
[operating contract](../23-agent-operating-and-data-contract.md).

The reader imports no backend settings/ORM and accepts only an explicit binding.
It opens SQLite read-only/query-only, verifies schema and matching SQL/overlay
identity markers on every call, checks the root marker again before returning,
and rejects foreign campaign drafts. Tools expose no mutation, arbitrary path,
SQL execution, HTTP proxy, shell, or development action. Invalid/absent sources
are reported without a vault/SQL/overlay substitution. Source citations preserve
store, ID, content/file hashes, and available SQL revision/timestamp tokens.

The fixture generator reuses W0's real-schema recovery rehearsal and binds only
the newly generated restored pair. It saves explicit session associations, a
binding manifest, an isolated campaign workspace with `AGENTS.md`, and a Codex
configuration example. The example is never activated automatically. Optional
agent dependencies are separate from backend pins because their Pydantic
requirements conflict. No private data was read or copied for this slice.

## Verification

- Isolated agent environment: **17 passed** (16 reader cases and one real SDK
  stdio integration test). Covers read-only database enforcement, unchanged
  source bytes, namespaces, approved-history eligibility, stable fresh-session
  citations, changed-content citations, denied writes/path overrides, invalid
  sources, schema/role/epoch changes, foreign campaigns, and epoch rotation during
  a read, and exact session/log ID lookup beyond the bounded listing window.
  The integration test exercises two fresh server processes, actual
  handshake/tool discovery, durable instructions/prompt, saved session resume,
  citations, and rejected operations.
- Backend environment: **3 passed** (full-schema agent onboarding plus the two
  existing W0 recovery CLI cases). Verifies generated source references, approved
  draft/log links, host configuration template, durable instructions, ignored
  inherited live paths, and refusal to overwrite an existing workspace.
- Standalone fictional full-schema onboarding and `--check` succeeded under
  `.codex-temp/w1-agent-fixture-20261027/`. The protocol verification report in
  `mcp-verification.json` records two fresh connections with identical references,
  the exact eight read tools, and denied write/scope-override attempts. These
  artifacts are ignored disposable evidence, not a public data fixture.
- Focused Ruff passed; Black API check passed for all nine new Python files;
  `git diff --check` passed (existing line-ending normalization warnings only).

Windows verification required permitted execution outside the restricted
sandbox: its socket restrictions stalled asyncio during internal socket-pair
creation before the first MCP request. The normal pytest TEMP root also had
existing access restrictions. Successful runs used new disposable basetemp
directories `.codex-temp/w1-agent-final-20261027-2236` and
`.codex-temp/w1-onboarding-final-20261027-2236`, with cacheprovider disabled.
These setup failures were not passing checks. No application workaround weakens
the reader's scope.

The broader repository quality baseline is unchanged: this slice does not claim
full CI, measured coverage percentage, macOS execution, or release readiness.
Previously recorded unrelated AoN test/static-quality findings remain open.

## Acceptance and next work

**Sufficient for the read-only fixture/protocol slice; W1 overall remains open.**
Two fresh MCP clients establish protocol/resume behavior, not an LLM's actual
campaign conversation. A dedicated host must still demonstrate the effective
tool set, absence of inherited development/other connectors, source-qualified
answers, missing-source handling, and restart/resume behavior on its real surface.
The configuration template requests those restrictions but is not their proof.

Next implement trusted revision-bound human approvals and safe staging/review
adapters, then test their actual review interaction. Prep preview, mutations,
report publication, Discord, player access, and production session-link
provisioning remain unavailable here. Real campaign binding requires explicit
authorization and a reviewed backup/identity plan. The ten archived panel modules
remain archived; Current Combat remains card-based.
