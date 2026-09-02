# Repository checkpoint — 2026-09-02

## Purpose

Create a recoverable public-repository checkpoint before beginning the AoN
monster-loading work in the card-based Current Combat module.

## Context

The local `main` commit matched `origin/main` at `924a03e`. The working tree
contained tracked changes related to campaign-overview routing, player-prep
PDF presentation, private-overlay installation, and integration coverage, plus
an untracked `assets/imports (1)/` tree.

## Scope of this checkpoint

The public tracked changes and this work record are eligible for version
control. The `assets/imports (1)/` tree is deliberately excluded: it contains
private campaign material, extracted assets, PDFs, and generated metadata. It
must remain outside public GitHub and should be handled through the private
overlay distribution process.

## Why

This checkpoint preserves the current public implementation state before a
focused Combat investigation. It also prevents private campaign data from
being included accidentally in the public repository.

## Verification still required

- Run the relevant integration tests before committing.
- Push the checkpoint to GitHub after the commit succeeds.
- Add a link to this record, or an equivalent summary, to the canonical
  Obsidian note `M:\Obsidian\Projects\Dungeon Master Assistant.md`.

## Next work

Investigate and verify AoN monster loading in the card-based Current Combat
module. Record the reproduction, decision, tests, and remaining work in a
follow-up dated work record.
