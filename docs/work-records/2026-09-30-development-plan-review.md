# Development plan review — 2026-09-30

## Scope and acceptance criteria

Update the development plan from the current-code assessment. Sufficient
completion requires prioritized milestones covering the identified retroactive
improvements, dependencies, acceptance evidence, and explicit verification gaps.
Excellent completion also aligns the README, quality guidance, and collaboration
workboard while retaining the original capability catalogue and historical records.

This is a planning change. Implementation, migration, source ingestion, and
publication are separate work.

## Decision

Adopt M1–M5: reliable combat; consistent campaign data; maintainable baseline;
grounded assistant capability; then validated integrations and reviewed expansion.
Start with condition/turn correctness and persistence/recovery. Apply quality gates
from the first slice, with wider consolidation in M3.

The review identified magnitude/duration conflation, unversioned overlapping
combat saves, 32 duplicate frontend function names, remaining vault defaults and
fallbacks, legacy AoN approval classification, incomplete live-memory-to-prep
integration, and a latest-500-document retrieval candidate restriction. These
are the reasons for revisiting existing implementation before broadening scope.
Concurrency risks were identified by inspection, not reproduced data-loss events.

## Evidence baseline

- Review scope: local `codex/aon-monster-loading` working tree, including existing
  uncommitted changes; no current remote synchronization claim is made.
- The preceding development review reported 139 passing Python tests. This
  documentation update did not rerun the suite or establish browser behavior.
- September 30 static checks reported 11 Ruff errors; Black and MyPy were missing
  from the active Python environment. Full quality acceptance remains open.
- CI specifies Python 3.11 on Ubuntu; the review environment used Python 3.14 on
  Windows. Runtime alignment and Windows CI are planned work.
- September 2 browser work records and April synthetic bridge records remain
  historical evidence, with their original scope and limitations.

## Changes and verification

- Updated the roadmap with milestones, dependencies, acceptance criteria, evidence
  dimensions, and the current baseline; retained original phase definitions.
- Updated the README delivery order and added milestone-specific quality guidance.
- Marked the collaboration workboard's older requests as historical and linked the
  active plan without changing their recorded completion state.
- Reviewed the documentation diff and checked changed Markdown links and required
  milestone/evidence sections. No application behavior changed.

## Completion and follow-up

Excellent completion for this planning scope. All implementation milestones remain
open. Before M1 coding, define condition expiry semantics, backwards-navigation
behavior, migration handling for ambiguous existing values, and exact save/recovery
acceptance cases in a focused implementation work record.
