# Pathfinder 2e Phase 1 Acceptance Corpus

This package contains a compact Phase 1 acceptance corpus shaped to the project guide.

## Status

This is the active Phase 1 acceptance fixture used by `tests/acceptance/test_phase1_acceptance.py`.

## Contents

- `assets/fixtures/phase1/phase1_corpus.json`
  - 10 short documents
  - 7 `rule` entries
  - 3 `lore` decoys
- `tests/acceptance/phase1_questions.json`
  - 15 representative questions
  - rules retrieval
  - strict-mode abstention
  - decoy resistance

## Notes

- The rules entries are concise paraphrases based on Pathfinder 2e rules pages on Archives of Nethys, with source URLs included per entry.
- The lore entries are intentionally non-rule distractors that overlap in vocabulary with the rules.
- The expected snippets are designed to make acceptance assertions straightforward after chunking and retrieval.
- This package follows the structure recommended in the project guide: a compact JSON corpus plus a separate question fixture.
- The acceptance test loads the corpus JSON and question fixture directly from this package rather than using inline placeholder data.
