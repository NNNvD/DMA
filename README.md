# Dungeon Master Assistant (DMA)

The Dungeon Master Assistant (DMA) is an LLM-powered co-DM for tabletop RPGs.

It ingests:

- Rulebooks and compendia for the chosen system
- Campaign text, images, and maps
- Party character sheets and DM notes

It then assists the DM in **three stages**:

1. **Overall Campaign Preparation**  
   Build a structured understanding of rules, world, factions, NPCs, and party backstories, including house rules and table conventions.

2. **Per-Session Preparation**  
   Generate session recaps, surface unresolved hooks, design encounters and scenes, and check continuity.

3. **Real-Time Session Assistance**  
   Provide fast, rules-aware, context-aware support during play (rules lookups, improv NPCs, continuity reminders, pacing suggestions) with low latency and high reliability.

The DMA is *not* meant to replace the DM. It acts as a quiet, knowledgeable assistant that:

- Knows the rules and the campaign
- Helps with organization and prep
- Supports improvisation and consistency during sessions
- Minimizes latency and API costs

For a detailed description of goals and functionality, see:

- [`docs/01-project-vision.md`](docs/01-project-vision.md)
- [`docs/02-functional-spec.md`](docs/02-functional-spec.md)
- [`docs/03-requirements.md`](docs/03-requirements.md)
- [`docs/04-risks-and-mitigations.md`](docs/04-risks-and-mitigations.md)
- [`docs/05-roadmap-and-milestones.md`](docs/05-roadmap-and-milestones.md)
- [`docs/06-testing-and-quality.md`](docs/06-testing-and-quality.md)

## High-Level Features

At maturity, the DMA should support:

- **Rules Engine (RAG-based)**  
  - Ingest rulebooks and compendia  
  - Answer rules questions with citations and “strict mode” (no hallucinations when unsure)

- **Campaign Model**  
  - Structured representation of locations, NPCs, factions, timelines, secrets, and world state  
  - Party and PC backstory integration

- **Prep Tools**  
  - Session recaps based on logs/notes  
  - Suggest likely player directions and prepare branches  
  - Encounter and scene generation, tuned to party and campaign tone  
  - Consistency checks and hook surfacing

- **Live Session Tools**  
  - Fast rules lookups and rulings consistent with house rules  
  - On-the-fly NPCs, descriptions, rumors, and small encounters  
  - Continuity and name recall (“What was the innkeeper’s name?”)  
  - Pacing and tension suggestions

## Development Approach

This repository is designed to be compatible with human developers and coding agents (e.g., OpenAI’s coding agent “Codex”). The **docs** directory contains:

- A clear functional spec  
- Non-functional requirements (cost, UX, reliability, latency, privacy)  
- Risks and mitigations  
- A phased roadmap  
- Testing, debugging, linting, benchmarking, and integration-testing guidelines per phase

## Getting Started (for Developers / Agents)

1. Clone this repository into GitHub.
2. Decide on the primary implementation stack (e.g., Python backend + React frontend, or Node.js + VTT plugin).
3. Implement the roadmap phases in order:
   - Phase 1: Rules Engine & RAG
   - Phase 2: Campaign and Party Modeling
   - Phase 3: Prep Assistant
   - Phase 4: Real-Time Session Assistant
   - Phase 5: Hardening & Polish
4. After each phase, follow the relevant testing and QA steps in [`docs/06-testing-and-quality.md`](docs/06-testing-and-quality.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
