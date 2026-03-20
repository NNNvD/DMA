# Phase 1 Acceptance Corpus Guide

This guide explains how to create a small, realistic corpus for Phase 1 acceptance testing.

The goal is not to commit full rulebooks. The goal is to provide a compact, representative mini-corpus that lets us verify:

- ingestion
- chunking
- retrieval quality
- citation quality
- strict-mode abstention
- resistance to false positives

## What To Add

Create a small set of short rule documents or excerpts.

Recommended size:

- `5-8` rule documents
- `2-5` lore decoys
- `10-15` representative questions

Preferred sources:

- SRD or other openly licensed rules text
- homebrew rules you wrote
- campaign notes you wrote

Avoid committing copyrighted full rulebooks to the repository.

## Corpus Shape

Either of these formats is fine:

1. A single JSON fixture containing many small entries
2. A folder of small `.md` files plus a question list

For automated tests, the easiest format is usually JSON.

Each document should include:

- `title`
- `kind`
- `source_name`
- `content`
- optional `url`

Use `kind: "rule"` for rules material.
Use `kind: "lore"` for distractor documents.

## What Counts As A Good Rule Document

Each rule document should focus on one topic or a tightly related set of topics.

Good examples:

- combat basics
- spellcasting basics
- conditions
- movement and opportunity attacks
- cover and visibility
- a few example spells

Keep each file small and readable. A few paragraphs is enough.

## What Lore Decoys Are

Lore decoys are non-rule documents that share vocabulary with real rules.

They exist so we can verify that retrieval does not grab the wrong document just because the keywords overlap.

Examples:

- a tavern named Fireball Tavern
- an NPC note mentioning a character becoming invisible
- a session log describing a grapple during a fight
- a world-lore note mentioning shields, charms, or curses

## Suggested Corpus Contents

Recommended starter set:

- `combat-basics`
- `spellcasting-basics`
- `conditions`
- `movement-and-opportunity-attacks`
- `cover-and-visibility`
- `example-spells`
- `lore-fireball-tavern`
- `lore-session-log-combat`

## Representative Questions

These are the kinds of questions the corpus should support.

Rules retrieval:

- What area does fireball affect?
- What happens when a creature is invisible?
- Who can I grapple?
- When do opportunity attacks happen?
- What does half cover do?
- How far can I move on my turn?
- What does prone do?
- What is needed to cast a spell?

Strict-mode abstention:

- How does underwater basket weaving work?
- What are the tax laws of the Moon Kingdom?
- What bonus does the Ruby Crown of Ashes give?

Decoy resistance:

- What does fireball do?
- Tell me the rule for invisibility.
- What are the grapple rules?

Those should still resolve to `rule` documents even if lore files mention the same words.

## Recommended Question File

If you want a separate question fixture, use a shape like this:

```json
[
  {
    "query": "What area does fireball affect?",
    "expected_kind": "rule",
    "expected_snippet": "20-foot-radius sphere"
  },
  {
    "query": "What happens when a creature is invisible?",
    "expected_kind": "rule",
    "expected_snippet": "impossible to see"
  },
  {
    "query": "How does underwater basket weaving work?",
    "expected_strict_abstain": true
  }
]
```

## Example Document Entry

```json
{
  "title": "Spellcasting Rules",
  "kind": "rule",
  "source_name": "SRD",
  "content": "Fireball explodes in a 20-foot-radius sphere. Creatures in the area take fire damage on a failed save."
}
```

## Quality Checklist

Before we wire the corpus into acceptance tests, try to make sure:

- each rule question has a clear supporting snippet
- decoy docs share some vocabulary with rule docs
- out-of-scope questions do not have near-matches in the corpus
- rule documents are short enough to make expected hits obvious
- document titles are descriptive and stable

## Where To Put The Files

Recommended location:

- `assets/fixtures/phase1/` for the corpus itself
- `tests/acceptance/` for question fixtures or acceptance docs

This file lives in `tests/acceptance/` because it documents the acceptance-test data.

The active fixture is the Pathfinder 2e corpus package under `tests/acceptance/pf2e_phase1_acceptance_corpus/`, and `tests/acceptance/test_phase1_acceptance.py` loads that corpus directly.
