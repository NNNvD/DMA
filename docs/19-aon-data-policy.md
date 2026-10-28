# AoN and Pathfinder data policy

This policy governs Pathfinder reference data used by DMA. It is designed for
the private campaign overlay and the public GitHub repository to have distinct,
auditable boundaries.

## Source classes

### ORC-licensed material

ORC-licensed rules material may be included in the public repository only when
the source and applicable license notice are recorded with the data. Preserve
required notices and do not imply Paizo endorsement.

### Private user-provided material

Files manually supplied or manually obtained by the campaign owner may be
stored in `local-private-overlay/project-root/` for local use. They must not be
committed to the public repository or copied into public fixtures without a
separate redistribution review.

### Reference-only material

Archives of Nethys may be used as a human-facing reference. When redistribution
rights are unclear, DMA should store structured metadata, a source citation,
and a direct URL rather than copying the page text.

## Explicit exclusions

Do not import or redistribute the following into the public repository or its
fixtures:

- Archives of Nethys or Paizo artwork
- maps, tokens, or other image assets
- adventure-path text or boxed read-aloud text
- Golarion setting lore, named characters, locations, organizations, or events
- bulk page copies obtained through automated scraping without explicit
  permission

## One-category intake checklist

Before adding a category such as rules, conditions, spells, items, or hazards:

1. Identify the exact source and source URL or file.
2. Record whether the source is ORC-licensed, private campaign material, or
   reference-only.
3. Confirm that the intended destination is the private overlay unless public
   redistribution has been reviewed.
4. Keep source files in that category's `raw/` directory and preserve the
   source identifier in each normalized record.
5. Normalize only that category and inspect parse warnings.
6. Regenerate the derived manifest/indexes.
7. Run tests and verify the relevant frontend/API behavior.
8. Record the decision, provenance, and remaining limitations in a dated work
   record.

## DMA implementation rule

The default workflow is: private local cache for approved campaign use,
source links for reference and fallback, and no unreviewed source text or art
in GitHub. When uncertain, stop the intake and request a source/licensing
decision before processing the files.

This is project guidance, not legal advice. Public or commercial distribution
requires a separate legal review.
