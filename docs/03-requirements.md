# Requirements

This document combines functional and non-functional requirements, including key constraints:
- Low API costs
- Good UX
- Reliable outputs
- Quick responses during real-time assistance

---

## 1. Functional Requirements

1. **Rulebook Ingestion and Query**
   - Ability to ingest rulebooks and compendia.
   - Ability to answer rules questions with:
     - Correct, concise explanations.
     - Citations to source material.

2. **Campaign and Party Modeling**
   - Extract and maintain structured data on:
     - Locations, NPCs, factions, timelines, secrets, and calendars.
     - Environmental cycles (seasons, moons) and culturally important holidays or festivals.
     - Economic locations such as shops, markets, taverns, and guildhalls with owners and typical offerings.
   - Parse and store:
     - PC character sheets and backstories, including known languages and scripts.
   - Track:
     - World state changes, including where key NPCs, factions, and items currently are.
     - PC/NPC relationships and arcs.
     - Ownership and location of notable magic items or artifacts.
     - Versioned history of PC sheets and level progression.

3. **Session Preparation**
   - Generate:
     - Recaps of previous sessions.
     - Scenario plans and likely branches.
     - Encounters and scenes tuned to party and style, including downtime and town visits.
     - Props and handouts (letters, clues, rumors, shop inventories).
     - Time and calendar summaries (current in-world date, upcoming holidays, weather when applicable).
   - Perform:
     - Continuity checks, hook surfacing, and detection of unclaimed loot or unresolved location changes.

4. **Real-Time Assistance**
   - Provide fast rules Q&A.
   - Generate improvised content on demand.
   - Provide continuity and recall assistance (names, promises, language capabilities, calendars, and item/shop locations).
   - Offer pacing/tension suggestions.

---

## 2. Non-Functional Requirements

### 2.1 Low API Costs

- Use RAG (retrieval-augmented generation) to avoid re-sending large texts.
- Summarize and compress state.
- Prefer smaller/cheaper models for routine tasks; reserve larger models for complex reasoning or creative content.
- Implement configurable caps on tokens per query and per session.

### 2.2 Good UX

- Clear interfaces for each stage:
  - Campaign Setup
  - Session Prep
  - Live Session
- Minimal prompt engineering burden: DM should interact primarily via:
  - Short natural-language requests
  - Buttons or commands for common tasks (e.g., “Generate recap”, “Design encounter”).
- Distinguish:
  - Rules-based answers
  - Lore/campaign recall
  - Speculative suggestions

### 2.3 Reliability of Output

- For rules:
  - Always reference source material via retrieval.
  - When uncertain, explicitly say so and offer possible page references or search hints.
- For campaign continuity:
  - Use a structured world model and state history.
  - Avoid contradicting canon unless DM explicitly retcons.

### 2.4 Quick Responses in Live Sessions

- Target response times suitable for real-time play:
  - Rules lookups and recall: very short prompts and contexts.
  - Stream responses so the first tokens appear quickly.
- Preload:
  - Current scene data.
  - PC sheets.
  - Relevant rule sections (e.g., combat rules during combat).

### 2.5 Privacy & Security

- Campaign data and player information must remain under user control.
- If remote LLM APIs are used, minimize sensitive data in prompts where possible.
- Provide potential path for local deployment or self-hosted inference.

### 2.6 Modularity & Extensibility

- Support multiple game systems via:
  - Pluggable rules packs.
  - System-specific configuration.
- Allow new modules (e.g., “Sandbox campaign builder”, “Downtime activities planner”) without breaking core architecture.

### 2.7 Fail-Safe Behavior and DM Authority

- The DMA should:
  - Avoid strong assertions when uncertain.
  - Phrase recommendations as suggestions.
  - Make it trivial for the DM to override and annotate decisions.

---

## 3. Technical Requirements (High-Level)

- **Architecture**
  - Backend service for:
    - LLM orchestration
    - Retrieval and embeddings
    - State management
  - Optional frontend:
    - Web interface or VTT-side panel.
- **Integrations**
  - Optional:
    - VTT APIs
    - Note-taking tools (e.g., Obsidian, Notion) via export/import
- **Observability**
  - Logging and metrics (latency, token usage, error rates).
  - Structured logs of critical decisions (e.g., world state updates).
