# Architecture Notes (Initial Sketch)

> This document is intentionally high-level. Concrete implementation details can be added as the project stack is chosen.

## Active direction — 2026-10-27

The component sketch below is historical. The active product contract and
delivery gates are in [the agent/session-cycle/Discord plan](22-agent-session-cycle-and-discord.md).
Keep these responsibilities separate:

- **Browser application:** operational session workspace and card-based combat.
- **Campaign agent:** durable instructions plus tools, initially operated through
  an existing external agent environment for prep, live help, debrief, and review.
- **Campaign services:** shared read/write boundaries, staged changes, approved
  facts, provenance, versioned live state, and recorded session artifacts. The
  SQL/private-overlay ownership contract is in
  [the data review document](20-campaign-data-ownership-and-review.md).
- **Discord adapter:** approved outbound reports first; restricted player Q&A
  later. Authorization and source visibility apply before retrieval/context
  assembly, including caches and history. The bot receives no general GM toolset.

Intended flow: approved campaign/history -> agent prep -> browser play and event
capture -> agent debrief -> DM review -> accepted facts and approved GM log ->
separate player-report approval -> optional Discord delivery -> next prep.
Player questions use only the authorized player knowledge projection; player
corrections return as review candidates. These connections are planned and must
be verified; their description does not imply that synchronization or a hosted
agent already exists.

Adapters should call explicit campaign services rather than rely on unreviewed
direct file edits or silent SQL/overlay merges. Campaign operation does not
authorize code/Git/deployment changes. Always-on Discord hosting is optional and
must use minimal player data rather than the entire private overlay. Archived
panel modules and retired Obsidian workflows remain inactive.

## 1. Logical Components

1. **Ingestion Layer**
   - Processes:
     - Rulebooks
     - Campaign docs
     - PC sheets
   - Outputs:
     - Structured data
     - Chunks + embeddings for retrieval

2. **Knowledge & State Layer**
   - Stores:
     - Rules chunks and metadata
     - World state (PCs, NPCs, locations, factions, events)
     - Session logs and summaries
   - Provides:
     - Query APIs for higher layers

3. **LLM Orchestration Layer**
   - Handles:
     - Prompt construction
     - Retrieval orchestration
     - Cost and token budgeting
     - Model selection (fast vs strong)

4. **Application Logic Layer**
   - Implements:
     - Stage 1: Setup workflows
     - Stage 2: Prep workflows
     - Stage 3: Live assistance workflows

5. **Interface Layer**
   - Provides:
     - Web UI or VTT integration for DMs
     - CLI or API for advanced users

## 2. Data Flows

- **Rules Q&A Flow:**
  1. User query → Orchestration layer
  2. Retrieval from rules vector store
  3. Prompt assembly with retrieved passages
  4. LLM response → User + citations

- **Session Prep Flow:**
  1. Session logs + target focus → Orchestration
  2. Queries to:
     - World state
     - PC state
     - Rules if needed
  3. LLM generates recap, outline, encounters, props.
  4. Outputs stored as prep artefacts.

- **Live Assistance Flow:**
  1. DM commands with current scene context → Orchestration
  2. Retrieval as needed (rules, world, PCs)
  3. LLM generates short response.
  4. Optional: state updates (e.g., new NPC introduced).

## 3. Configuration

- Per-campaign configuration should include:
  - Game system and rule sources.
  - House rules & style.
  - Player/preferences and safety tools (if stored).
  - Cost/latency preferences (e.g., frugal vs deluxe).

## 4. Next Steps

- Once the implementation stack is chosen, extend this document with:
  - Concrete diagrams.
  - Technology choices.
  - Module boundaries and interface contracts.
