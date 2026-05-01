# DMA Promo Overview

The Dungeon Master Assistant (DMA) is an AI-powered co-DM for tabletop RPGs.

It helps a Game Master keep rules, world state, party history, session prep, and live-table
support in one place without replacing the GM's judgment. DMA is designed to be a quiet,
reliable assistant that knows the campaign, remembers continuity, and surfaces useful answers
fast.

## What DMA Does

DMA supports three core phases of play:

1. campaign understanding
2. session preparation
3. live-session assistance

At a high level, DMA can:

- ingest rules, guides, campaign notes, session logs, and character sheets
- answer rules questions with retrieval-backed citations
- build a structured model of locations, NPCs, factions, artifacts, calendars, and PCs
- import and update campaign state from notes, session updates, and sheet versions
- generate session briefs with hooks, continuity checks, and scene seeds
- export campaign state into an Obsidian vault
- support live play with a DM panel, quick commands, continuity lookup, and mechanics snapshots

## Current Feature Set

The current repository includes these concrete capabilities:

- Rules engine:
  document ingestion, search, strict rules Q&A, latency and token-cost metrics
- Campaign model:
  entities, relationships, PC dossiers, session history, batch import from drop zones
- Prep assistant:
  deterministic session brief generation from campaign state and recent sessions
- Obsidian workflow:
  export of campaign entities, notes, sheets, sessions, and prep into a structured vault
- Live assistant:
  live session state, `/scene`, `/rules`, `/search`, `/recap`, `/npc`, and `/prep` responses
- MapTool bridge prototype:
  local bridge, fixture/demo sync, payload-file ingestion, and watched export-folder workflow

## Why It Is Useful

DMA is built for GMs who want:

- faster rules lookups without losing source grounding
- better recall of NPCs, factions, hooks, and timeline details
- cleaner prep from campaign state that already exists in notes and logs
- less context-switching between files, vaults, sheets, and live-session tools
- a system that can grow from solo prep into real-time table support

## Ideal Use Cases

DMA is especially well suited for:

- long-form campaigns with lots of continuity
- prep-heavy games with many factions, locations, and secrets
- rules-dense systems where citation-backed answers matter
- GMs who already keep notes in markdown, spreadsheets, Pathbuilder exports, or Obsidian

## Short Pitch

DMA is a campaign-aware, rules-aware co-DM that helps you ingest your game material, prepare
better sessions, and stay sharp at the table.
