# Ingestion Governance

This document adapts the PF2e ingestion protocol to the current DMA codebase.

## Why It Is Adjusted

The pasted protocol is directionally strong, but it mixes two separate concerns:

- whether content is legally and operationally safe to train on
- whether content is public or private

In DMA we treat those as separate axes:

1. `source_class`
   - `retrieval_only`
   - `trainable_open`
   - `trainable_with_review`
   - `private_local`
2. `privacy_scope`
   - `public`
   - `private_local`

`private_local` remains available as a source class, but in DMA we use it as a quarantine bucket
for local material whose reuse status is still unclear. That keeps privacy and reuse mostly
separate without losing compatibility with the original proposal.

That lets us represent cases like:

- user-authored session notes: `trainable_open` + `private_local`
- public guide pages with unclear reuse rights: `trainable_with_review` + `public`
- purchased PDFs supplied by the user: `retrieval_only` + `private_local`

We still default `train_eligible = false` unless a later review explicitly approves it.

## Current Repo Fit

DMA already uses `assets/imports/` as the raw drop-zone and the database as the normalized
document store. Rather than introducing a second top-level raw-data tree, we keep governance
artifacts next to the existing import root:

- `assets/imports/metadata/source_registry.json`
- `assets/imports/metadata/license_flags.json`
- `assets/imports/metadata/review_queue.jsonl`
- `assets/imports/metadata/ingestion_log.jsonl`
- `assets/imports/metadata/sidecars/**/*.json`
- `assets/imports/manifests/corpus_manifest.csv`
- `assets/imports/manifests/rag_manifest.csv`
- `assets/imports/manifests/train_manifest.csv`
- `assets/imports/reports/ingestion_reports/latest.json`

## What The Exporter Does

`python3 -m scripts.export_ingestion_metadata` scans the current `assets/imports/` tree and
generates:

- deterministic sidecar metadata for every raw file
- a source registry grouped by source family
- a review queue for ambiguous public material
- a corpus manifest for all tracked files
- a RAG manifest for files currently eligible for retrieval
- a train manifest for files explicitly eligible for training

The exporter does not change the database. It governs raw imports and provenance.

## Current Classification Rules

- `campaign-notes/` and `session-logs/`
  - treated as user-authored local content
  - `privacy_scope = private_local`
  - `rag_eligible = true`
  - `train_eligible = false` until deliberately approved
- `pathbuilder/`
  - treated as local character imports
  - `gm_only` by default because they may contain player-specific information
- `misc/pf2e-reference/raw/`
  - treated as public guides imported for retrieval/reference
  - `source_class = trainable_with_review`
  - `review_status = pending`
  - `train_eligible = false`
- `misc/aon-rules/raw/`
  - treated as public Pathfinder 2e rules content fetched from Archives of Nethys
  - imported as `kind = "rule"`
  - `source_class = retrieval_only`
  - `review_status = approved`
  - `train_eligible = false`
- `misc/private-local/reference/raw/player/`
  - treated as private player-safe local reference
  - imported as `kind = "reference"`
  - `source_class = private_local`
  - `visibility_scope = player_safe`
  - `train_eligible = false`
- `misc/private-local/reference/raw/gm/`
  - treated as private GM-only local reference
  - imported as `kind = "reference"`
  - `source_class = private_local`
  - `visibility_scope = gm_only`
  - `train_eligible = false`
- `misc/private-local/library/`, `misc/private-local/media/`, `misc/private-local/maptool-campaigns/`, and `misc/private-local/character-sheets/`
  - tracked for provenance with campaign-aware metadata
  - not automatically marked RAG-eligible unless a format-specific importer exists
  - kept private by default

## Relationship To Strict Rules Retrieval

Strict rules answers still query `kind = "rule"` documents only.
Guide/reference imports are intentionally kept separate as `kind = "guide"` so public guides
can help broad retrieval work without weakening rules grounding.
AoN-backed rules payloads are the intended retrieval source for strict rules answers.

## Next Good Steps

If we want to push this further, the next upgrades that fit the current architecture are:

1. add sidecar-aware import preview in the API
2. add a manual approval flow for promoting files into `train_manifest.csv`
3. decide whether any private-local PDFs should get a local-only text extraction path
4. add richer campaign-note normalization for freeform notes that are not yet entity-block structured
