# Roadmap and Build Requirements

This roadmap is structured into five phases. Each phase has:

- Core goals
- Key deliverables
- Dependencies and build requirements

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
