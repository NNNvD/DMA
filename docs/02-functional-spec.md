# Functional Specification

This document specifies what the DMA should be capable of at each of the three assistance stages.

---

## 1. Stage 1 – Overall Campaign Preparation

### 1.1 Objectives

- Ingest and structure foundational data:
  - Rulebooks and compendia
  - Campaign materials (text, maps, images, notes)
  - Character sheets
  - House rules and table conventions
- Create a coherent internal representation of:
  - Rules
  - World and factions
  - PCs, NPCs, and their relationships
  - Timelines, calendars, and secrets

### 1.2 Inputs

- Rulebook PDFs / text (possibly proprietary; ingestion must remain local or user-owned).
- Campaign text files, wiki pages, or notes.
- Map images and basic annotations (regions, rooms, labels).
- PC character sheets (ideally as structured data).
- Homebrew and house rules (text).
- Session 0 notes, including play style, tone, and safety tools.

### 1.3 Capabilities

1. **Rules Engine (RAG)**
   - Ingest rules and chunk them for retrieval.
   - Answer rules questions with:
     - Short natural-language answers
     - Citation(s) to source (book name, section, page)
   - “Strict rules mode”: if relevant passages cannot be retrieved with high confidence, respond with uncertainty and suggested manual lookup locations.

2. **World & Campaign Model**
   - Extract and structure:
     - Locations and regions (dungeons, wilderness, settlements, planes)
     - Factions and organizations
     - NPCs, including roles and relationships
     - Artifacts, major plot items, and secrets
     - Timelines (past events, future planned events)
   - Calendars and environmental cycles:
     - In-world calendar (days, months, years) and current in-game date.
     - Moon cycles, seasons, and other relevant astronomical cycles.
     - Cultural/religious holidays, festivals, and recurring events tied to locations or factions.
   - Economic locations:
     - Shops, markets, taverns, guildhalls, and similar sites, including where they are, who runs them, and what they generally offer.
   - Languages and cultures:
     - Which languages and dialects are associated with regions, factions, and key NPCs.
   - Assign stable internal IDs to entities (“NPC#23” → “Captain Mira”) to reduce ambiguity.

3. **Party Integration**
   - Parse PC sheets:
     - Attributes, skills, class features, spells, items
     - Backgrounds, personal goals, notes
     - Languages and scripts known (spoken, read, written)
   - Link PCs to:
     - Factions
     - NPCs (contacts, mentors, enemies)
     - Locations and hooks from the campaign material
   - Track notable inventory:
     - Maintain a register of key magic items and artifacts.
     - Record which PC, NPC, or location currently holds each item and how ownership changes over time.
   - Support character progression:
     - Track level-ups and changes to abilities, spells, and items over time.
     - Accept updated character sheets from players/DMs or suggest updates based on rules and house rules.
     - Maintain a versioned history of each PC sheet.

4. **House Rules & Table Conventions**
   - Store:
     - Mechanical changes (e.g., rest rules, crits, spell alterations)
     - Banned/allowed content
     - Preferred ruling style (“rulings over rules”, “RAW whenever possible”)
   - Ensure all future rules answers respect these conventions.

### 1.4 Outputs

- Internal “rules knowledge base” with retrieval interface.
- Structured campaign and party database.
- Summary documents:
  - World overview
  - Faction overview
  - NPC roster
  - PC dossiers with hook mappings
- Utility overviews:
  - In-world calendar and holidays summary.
  - Shop and services index (locations, owners, and typical stock).
  - Magic item registry and language capability table for PCs and important NPCs.

---

## 2. Stage 2 – Per-Session Preparation

### 2.1 Objectives

- Help the DM plan each session based on:
  - Previous session events
  - Current world state
  - PCs’ arcs and active hooks
  - Planned future events, payoffs, and foreshadowing opportunities (e.g., earlier rooms or scenes hinting at later locations, twists, or revelations)
  - In-world time and calendar (how many days have passed, current season, upcoming holidays or time-sensitive events)
- Provide concrete, ready-to-use prep materials.

### 2.2 Inputs

- Updated world/party state from Stage 1.
- Session logs or notes from previous session(s).
- DM’s target for the upcoming session (e.g., “explore the old mine”, “focus on character X’s backstory”).

### 2.3 Capabilities

1. **Recap & State Update**
   - Generate clear recaps of last session:
     - Main events, NPCs involved, choices made.
   - Update:
     - Factions’ plans and clocks.
     - NPC goals and current whereabouts (what area/region they are in).
     - Location states (e.g., dungeon cleared, town damaged or rebuilt, new constructions, new threats).
     - PCs’ progress on personal arcs.
     - Distribution of notable magic items and other important loot, including unclaimed treasure left in specific locations.
   - Maintain a changelog of world state.

2. **Branch & Scenario Planning**
   - Suggest likely directions players may take based on:
     - Existing hooks
     - Current location
     - Social and narrative pressures
   - For each likely branch, sketch:
     - Key scenes and beats
     - Important NPCs and their agendas
     - Expected challenges and rewards
   - Consider how NPCs and locations evolve if branches are followed or ignored (e.g., villains relocate, shops close or expand, a disease spreads after its incubation period if not addressed).

3. **Encounter and Scene Design**
   - Propose:
     - Combat encounters tuned to party strength and style
     - Social encounters (negotiations, intrigue, roleplay scenes)
     - Exploration challenges (traps, puzzles, environment)
     - Downtime/town sequences, including visits to shops, markets, and services with a quick overview of relevant locations and their current stock.
   - Produce:
     - Quick-reference stat bundles for relevant NPCs/monsters
     - Boxed text or scene descriptions the DM can customize

4. **Consistency & Hook Surfacing**
   - Detect continuity issues.
   - Surface:
     - Forgotten NPCs
     - Old hooks that could return
     - Chekhov’s guns to pay off
     - Unlooted loot, unresolved oddities, or unfinished changes in previously visited locations that are now relevant again.

5. **Prop & Handout Generation**
   - Generate:
     - Letters, contracts, proclamations
     - Rumor lists
     - Shop inventories
     - Clue handouts for mysteries or investigations, including custom/ad-hoc handouts for things that do not have a standard template.

6. **Time & Calendar Management**
   - Maintain an in-world calendar and agenda:
     - Count days since campaign start and since key events.
     - Determine current season and, when appropriate, likely weather for the region (using any rules or tables available).
     - Track disease incubation periods, timed curses, and other time-dependent effects.
     - Schedule specific holidays, festivals, omens, and other recurring events and surface them when they become relevant to upcoming sessions.

### 2.4 Outputs

- Session prep document, including:
  - Recap
  - World/party state updates (including locations, NPC positions, and magic items/loot)
  - Planned scenes and encounters
  - Hooks to introduce or resolve
  - Props/handouts and notes
  - Time & calendar summary (current in-world date/season, upcoming holidays or time-based events)

---

## 3. Stage 3 – Real-Time Session Assistance

### 3.1 Objectives

- Support the DM during live play with:
  - Fast rules answers
  - Improvised content
  - Continuity & name/places recall
  - Pacing suggestions
- Minimize latency and friction.

### 3.2 Inputs

- Current session “live state”:
  - Scene description, location, active NPCs.
  - Party status (HP, conditions, resources) if integrated.
- Ongoing DM queries and commands.

### 3.3 Capabilities

1. **Fast Rules Q&A**
   - Provide simple, concise answers:
     - Rules text distilled with citations.
   - Respect:
     - House rules and table style.
   - Distinguish:
     - RAW (rules as written)
     - Recommended rulings when RAW is unclear or missing.

2. **On-the-Fly Content Generation**
   - Generate on demand:
     - NPCs (name, appearance, voice, quirks, goals, secrets).
     - Location descriptions (rooms, streets, wilderness scenes).
     - Minor items and curiosities.
     - Rumors and small encounters.
     - Context-appropriate weather and environmental details based on current region, season, and calendar; including quick adjustments for sudden changes (storms, eclipses, omens) when desired.
   - Quickly sketch or refresh:
     - The contents and feel of a specific shop, inn, or market stall, drawing from or updating its persistent entry when one exists.
   - Keep generated content consistent with existing setting and tone.

3. **Mechanical Support (Optional / Integration-Dependent)**
   - If connected to a VTT, tracker, or dice roller:
     - Maintain initiative order.
     - Track HP, conditions, and time-based effects (spell durations, disease incubation, curses, etc.).
     - Suggest enemy tactics consistent with intelligence and goals.
     - Facilitate die rolling for mechanics:
       - Trigger or perform secret rolls for PCs (e.g., Perception, Insight, Stealth, saving throws) when requested by the DM.
       - Ensure that players only see the narrative outcome (e.g., “you sense something is off”) while the DM can access the underlying roll results.

4. **Continuity Assistance**
   - Answer questions like:
     - “What did we agree with Lord Seran last time?”
     - “Who was the contact in the thieves’ guild?”
   - Remind DM of:
     - Promises made by NPCs.
     - Foreshadowed events.
     - Unresolved plot points relevant to the current scene.
   - Track:
     - Language capabilities (“Which PCs speak Undercommon?” “Can this NPC talk to the dwarf?”).
     - Current in-world date, how many days have passed since key events, and which holidays or timed events are imminent.
     - Where key NPCs, shops, and items are located at this moment in the timeline.

5. **Pacing & Tension**
   - Suggest:
     - When to offer a clue.
     - When to cut to another scene.
     - Opportunities for rests, reveals, or escalation.
   - Always present as suggestions; never override DM.

### 3.4 Outputs

- Short, focused responses optimized for:
  - Low latency
  - Minimal on-screen clutter
  - Immediate DM usability
- Explicit markers of:
  - Rules citations
  - Uncertainty
  - Raw suggestions vs canonical facts
