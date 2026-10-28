# Testing, Debugging, and Quality Guidelines

This document specifies how to ensure quality after each roadmap phase, including:

- Testing strategies
- Debugging/troubleshooting guidelines
- Linting and style
- Benchmarking and integration testing

The concrete tools (e.g., `pytest` vs `jest`) depend on the chosen stack; this document is intentionally tooling-agnostic with examples.

The active product delivery order is W0-W6 in
`22-agent-session-cycle-and-discord.md`; M1-M5 in the roadmap remain supporting
engineering workstreams. The original
phase sections below remain coverage guidance for the existing phase-check
commands. Apply relevant quality gates in every milestone, including M1.

---

## 1. General Principles

1. **Automate what you can**  
   - Every feature merged into main should have automated tests.
   - CI should run lint + tests on every pull request.

2. **Test the LLM integration with realistic prompts**  
   - Use fixture prompts and expected answer patterns, not exact strings.

3. **Keep logs for hard bugs**  
   - For difficult issues (e.g., hallucinations, continuity bugs), keep anonymized prompts and responses as regression cases.

---

## 2. Phase-by-Phase Quality Gates

### 2.1 Phase 1 – Rules Engine & RAG

**Focus:** Correctness and reliability of rules answers; basic performance.

**Tests:**

- **Unit Tests**
  - Chunking and ingestion:
    - Given sample input document, verify chunks created and stored correctly.
  - Retrieval:
    - Given known queries, ensure correct or highly relevant chunks are returned.
- **Integration Tests**
  - Rules Q&A:
    - Provide a curated list of rules questions with known answers and references.
    - Assert that:
      - The response cites the correct section/page.
      - The explanation is consistent with the source text.
- **LLM Behavior Tests**
  - Strict mode:
    - Questions outside the ingested rules should trigger:
      - “I don’t know” style responses
      - Suggestions for manual checks, not hallucinated rules.

**Debugging / Troubleshooting:**

- If answers cite wrong sections:
  - Check embedding model and search parameters.
  - Inspect the top-k retrieved chunks for relevance.
- If model hallucinates rules:
  - Ensure prompt explicitly instructs:
    - “You may only answer based on the provided context; otherwise say you don’t know.”
  - Verify retrieval results are actually supplied to the model.

**Linting & Style:**

- Adopt a linter for the chosen language:
  - Python: `flake8`, `black`, or `ruff`.
  - TypeScript/JavaScript: `eslint`, `prettier`.
- Enforce via CI.

**Benchmarking:**

- Measure average latency for:
  - Single rules questions.
- Track token usage per request.
- Use `make phase1-benchmark` to run the active acceptance corpus as a lightweight benchmark.
- Use `GET /api/admin/metrics` to inspect accumulated Phase 1 latency and token/cost summaries while exercising the API.

---

### 2.2 Phase 2 – Campaign & Party Modeling

**Focus:** Data integrity, consistency, and queryability of the campaign model.

**Tests:**

- **Unit Tests**
  - Data models:
    - Validate schemas (PCs, NPCs, locations, factions, events).
  - Importers:
    - PC sheet parser: given a sample sheet, ensure correct attributes and features.
    - Campaign note parser: detect and tag entities, relationships, and locations.
- **Integration Tests**
  - End-to-end ingestion:
    - Provide a small sample campaign and verify:
      - Entities are created as expected.
      - Queries like “find all NPCs in city X” or “PC’s faction ties” work.
- **Consistency Checks**
  - Ensure no duplicate IDs for entities.
  - Detect circular references where they should not exist.

**Debugging / Troubleshooting:**

- If entities are missing:
  - Check the extraction rules or LLM prompts used for parsing.
  - Log intermediate representations for inspection.
- If relationships are wrong:
  - Enhance entity disambiguation (e.g., “Mira” vs “Commander Mira”).

**Linting & Style:**

- Extend linting to include:
  - Schema definition files.
  - DB migration scripts, if present.

**Benchmarking:**

- Measure ingestion time for:
  - A typical rulebook.
  - A modest campaign (e.g., 50–100 pages of notes).

---

### 2.3 Phase 3 – Prep Assistant

**Focus:** Quality of session prep outputs and continuity handling.

**Tests:**

- **Unit Tests**
  - Template rendering:
    - Given a set of data (world state, logs), ensure templates for recaps/encounters/props render without errors.
- **Scenario-Based Tests**
  - Create 2–3 synthetic campaigns with:
    - Known past sessions.
    - Planned future events.
  - For each, generate:
    - Recap
    - Session outline
    - Encounter suite
  - Manually evaluate:
    - Does recap match the logs?
    - Are hooks and NPCs correct?
    - Are proposed encounters appropriate and consistent?
- **Continuity Tests**
  - Introduce deliberate contradictions in test data and check if:
    - The continuity checker flags them.

**Debugging / Troubleshooting:**

- If recaps omit key events:
  - Update summarization prompts to emphasize certain tags or markers.
- If encounters are too easy/hard:
  - Adjust challenge-calculation logic (e.g., CR formulas, XP budgets, or system-specific guidelines).

**Linting & Style:**

- Lint any orchestration/workflow code.
- Add style checks for:
  - Data pipeline scripts.

**Benchmarking:**

- Time to generate full prep document for:
  - A typical session (e.g., 3–4 hours of play).
- Token usage for:
  - Recap
  - Outline
  - Encounter generation

---

### 2.4 Phase 4 – Real-Time Session Assistant

**Focus:** Latency, stability, and usefulness in live conditions.

**Tests:**

- **Latency Tests**
  - Measure:
    - 50th, 90th, and 99th percentile response times for:
      - Rules queries
      - NPC generation
      - Continuity recall
- **Load Tests**
  - Simulate:
    - A burst of queries (e.g., 20–50 requests in a short period).
  - Ensure:
    - No crashes or severe slowdowns.
- **Scenario-Based Live Simulations**
  - Run mock sessions where:
    - A script sends queries typical of play.
    - Human or scripted evaluators rate:
      - Utility
      - Clarity
      - Distractingness

**Debugging / Troubleshooting:**

- If latency is high:
  - Inspect:
    - Prompt size
    - Retrieval overhead
  - Introduce caching of:
    - Current scene context
    - Frequent rules answers
- If answers feel irrelevant:
  - Check:
    - Query routing logic (is the right context retrieved?)
    - Whether session state is updated correctly.

**Linting & Style:**

- Lint:
  - Frontend code (if present).
  - Any client-side scripts.

**Benchmarking:**

- Set target thresholds, e.g.:
  - Rules queries: average < X ms (excluding network).
  - NPC generation: average < Y ms.
- Track errors and timeouts.

---

### 2.5 Phase 5 – Hardening & Polish

**Focus:** Reliability, maintainability, and readiness for broader use.

**Tests:**

- **Regression Test Suite**
  - Combine:
    - Rules tests
    - Campaign ingestion tests
    - Prep scenarios
    - Live simulations
- **End-to-End Tests**
  - Simulate:
    - A short campaign arc:
      - Set up world and rules
      - Run 3–4 sessions with logs and prep
      - Use live assistant during sessions
  - Check:
    - Continuity
    - Reliability
    - Cost and latency metrics

**Debugging / Troubleshooting:**

- Systematic approach:
  - Log and categorize user issues.
  - Create regression tests for recurring bugs.

**Linting & Style:**

- Ensure:
  - All code passes linting.
  - Style guides are documented and enforced.

**Benchmarking:**

- Track:
  - Tokens per session
  - Average latency per query type
  - Error rates (e.g., failed retrievals, timeout)
- Consider having:
  - “Benchmark scenarios” with expected cost and latency envelopes.

---

## 3. Workflow Suggestions

- Use feature branches for significant changes.
- Require:
  - Tests for new features.
  - Code review (even if by a second AI agent) before merge.
- Keep:
  - A CHANGELOG of user-visible changes.
- Periodically:
  - Run full integration and scenario tests.
  - Review cost and latency metrics.

## 4. Task Completion Standard

Before work begins on every task, define task-specific acceptance criteria and
record them with the task or its work record. If criteria were defined in
advance, reevaluate them immediately before starting so that scope, risks,
dependencies, and verification methods are current.

### Sufficient completion

The task works within its stated scope, appropriate automated tests pass, no
known critical regression remains, the user-facing flow is verified when
relevant, and the work record explains what changed, why, how it was tested,
and what remains open.

### Excellent completion

Sufficient completion is met, and the task also has meaningful edge-case
coverage, clear loading/empty/error states, polished user-facing behavior,
visual and interaction verification, acceptable performance, and reusable
documentation or tooling where appropriate.

### Not complete

A task is not complete if a critical failure remains, required tests are
missing or failing, the actual interface is unverified when relevant,
private/spoiler-sensitive data may leak, or the rationale and limitations are
not documented.

The final work record must state which level was achieved and list the concrete
steps needed to raise a sufficient result to excellent. These criteria are
completion gates, not permission to expand a task's scope without approval.

## 5. Milestone Evidence Requirements

- Track implemented, automatically verified, browser verified, and play-tested
  independently using the roadmap's evidence definitions. Record the date, code
  revision or working-tree scope, runtime, checks, outcomes, and limitations.
- Python API tests and HTML-content assertions do not verify JavaScript behavior.
  Combat condition transitions, manual inputs, save ordering, and recovery need
  focused logic tests and representative browser interactions.
- Persistence checks must cover rapid changes, delayed/out-of-order responses,
  failed requests, stale writes, reset during a pending save, and reload/recovery.
- Data workflow checks must cover absent vaults, empty overlay records, source
  review status, and an approved session update reaching subsequent prep.
- Retrieval checks must include older relevant documents beyond the current
  500-document candidate window, source/edition conflicts, and abstention.
- Keep synthetic fixture checks, real integration checks, and real-play evidence
  distinct. Historical evidence remains dated and does not close newly discovered
  defects or untested acceptance criteria.
- Full quality acceptance includes lint, formatting, type checks, and applicable
  Python/browser checks in declared supported environments. An unavailable tool
  is an unverified check, not a pass. Do not reduce gates merely to obtain green CI.
- Measure representative latency and cost first, then record numerical budgets
  and acceptance thresholds before performance sign-off. Model-service results
  must identify provider/model and cannot be inferred from deterministic tests.
- Give each implementation slice sufficient/excellent criteria before coding;
  record explicit non-applicability for evidence dimensions outside its scope.

## 6. Session-cycle, agent, and Discord gates

- Verify the actual external campaign-agent interaction separately from API tests:
  a fresh conversation can load the right campaign/session, read approved state,
  stage uncertain claims, and resume from saved records without this chat history.
- A fictional full-cycle scenario covers prep, browser play, restart/recovery,
  debrief, accepted/rejected/deferred candidates, separate log approval, a reviewed
  player report, and next prep with source IDs/revisions. Include conflicting
  recollections, a revealed fact, a GM secret, and an interrupted debrief.
- Player visibility is enforced before retrieval and context construction. Test
  source filtering, citations, attachments, caches, conversation history, revoked
  visibility, and adversarial requests. A prompt to hide secrets is insufficient.
- Discord report approval binds exact content revision and destination. Test
  stale approval, wrong channel, failed delivery, ambiguous timeout, duplicate
  prevention/reconciliation, long reports, disabled mentions, and corrections.
- Discord questions require server/channel/user authorization, source-grounded
  responses or abstention, budget/timeout handling, and review-only player
  corrections. Player messages must not expand tool authority or write canon.
- Use synthetic data and mocked transport first. An authorized Discord test-channel
  interaction verifies actual delivery; a mock alone cannot close that gate.
  Planning approval does not authorize posting to a real server.
- Record agent, browser, Discord, automated, and play-test evidence independently,
  including applicable environments, measured latency/cost, and remaining manual
  steps. Core local-cycle acceptance does not imply Discord Q&A acceptance.
