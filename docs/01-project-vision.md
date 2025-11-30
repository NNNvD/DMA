# Project Vision: Dungeon Master Assistant (DMA)

## 1. Purpose

The DMA is an LLM-powered assistant that helps tabletop RPG Dungeon Masters prepare and run campaigns. It aims to be:

- **Rules-aware**: grounded in the actual rulebooks and compendia of the chosen system.
- **Campaign-aware**: deeply familiar with the DM’s specific world, NPCs, maps, and ongoing story.
- **Party-aware**: tuned to the current group of player characters, their backstories, goals, and themes.
- **Style-aware**: aligned with the DM’s house rules, tone, and preferred play style.

The DMA’s main role is to increase the DM’s **bandwidth** and **reliability**, without taking control of the game.

## 2. Target Users

- Primary: Dungeon Masters / Game Masters running long-form campaigns.
- Secondary: Co-DMs or assistants who help manage prep and record-keeping.
- Tools: Potential integration with Virtual Tabletop (VTT) platforms, note-taking systems, and scheduling tools.

## 3. Scope

The DMA will:

- Ingest and structure rulebooks, campaign material, and character sheets.
- Assist in three stages:
  1. **Overall Campaign Preparation**
  2. **Per-Session Preparation**
  3. **Real-Time Session Assistance**
- Focus on:
  - Low API costs
  - Good UX
  - Reliable outputs
  - Low-latency responses in live sessions

Non-goals (for this version):

- Direct player-facing chatbot that replaces the DM.
- Generic “AI story generator” without grounding in rules and campaign state.
- Automated dice rolling and combat resolution without DM control (can integrate with existing tools instead).

## 4. High-Level Goals

1. **Trustworthiness**  
   The DM can trust rules answers and campaign consistency. When the DMA is unsure, it states this explicitly and provides sources or options.

2. **Efficiency**  
   Reduce preparation time and cognitive load, especially for bookkeeping, continuity, and routine content like minor NPCs and descriptions.

3. **Flow during Play**  
   Provide quick, minimal-friction assistance that supports improvisation rather than interrupting it.

4. **Cost Consciousness**  
   Be designed from the ground up to minimize unnecessary tokens, re-use summaries, and leverage caching and retrieval.

## 5. Relationship to the Three Assistance Stages

The three stages are the backbone of the product design:

- **Stage 1: Overall Campaign Preparation**  
  Build the foundations: ingest rules and campaign, set up world/party models, and configure table conventions.

- **Stage 2: Per-Session Preparation**  
  Operate as a planning partner that understands what has happened and what might happen next.

- **Stage 3: Real-Time Session Assistance**  
  Sit next to the DM (virtually) and provide fast, context-aware help that respects the DM’s authority and tone.

Each stage has its own functional capabilities and quality gates, defined in detail in `02-functional-spec.md` and `06-testing-and-quality.md`.
