# Public Repo And Private Overlay

This project is designed to be pushed to GitHub without redistributing copyrighted adventure assets.

## What Goes To GitHub

- DMA source code, tests with synthetic fixtures, scripts, and documentation.
- Generic metadata, manifests, and placeholders that explain where local assets should be placed.
- User-created campaign notes only when explicitly approved for public release and scrubbed of private and identifying details.

## What Stays Local

The following material must stay out of the public repository:

- Purchased adventure PDFs.
- Text extracted from those PDFs, including room descriptions and encounter stat blocks.
- Official map image files.
- Images extracted from PDFs.
- NPC, monster, item, cover, or illustration images from books.
- Generated PDF/HTML handouts that include protected setting/adventure text or styling built from such material.
- Archived third-party or older campaign assets.
- The private campaign overlay and its JSON, notes, imports, manifests, and generated indexes.

These paths are intentionally ignored:

- `assets/imports/misc/private-local/`
- `assets/archive/`
- `obsidian-abomination-vaults-vault/Library/Assets/`
- `obsidian-abomination-vaults-vault/Exports/Handouts/*.pdf`
- `obsidian-abomination-vaults-vault/Exports/Handouts/*.html`
- `local-private-overlay/`
- `.codex-temp/`, `tmp/`, and `pytest-cache-files-*/` scratch folders

Keep PDF parsing rules, data schemas, and validation checks in public code. Put
the extracted output in the ignored local overlay, not in source files, docs,
or test fixtures. Public tests should use invented room text and stat blocks;
optional campaign-data assertions require explicit permission to use the local
overlay and `DMA_TEST_PRIVATE_OVERLAY=1`. Routine test runs use synthetic fixtures.

## Local Overlay Folder

For collaborators who legally have access to the same source material, use:

`local-private-overlay/project-root/`

That folder mirrors the private parts of the project root, but it should stay in
place as an ignored root overlay. Do **not** copy its contents into
`assets/imports/...`, and do **not** unpack it over the repository root during
normal updates.

Required local layout:

```text
DMA-main/
  local-private-overlay/
    project-root/
      assets/imports/misc/private-local/
```

When `.env` leaves the standard private-data paths at their defaults, DMA
automatically prefers matching paths under `local-private-overlay/project-root/`.
The overlay remains separate from Git and must be acquired through the approved
private distribution channel. The active campaign workflow does not require an
Obsidian vault; compatibility code and legacy export/import guides are retired
unless a workflow is explicitly reinstated.

Collaborators must manually acquire the latest `local-private-overlay/` bundle
from the GM or approved private distribution channel. GitHub updates alone will
never update private maps, PDFs, portraits, room keys, or campaign-only data.

Do not copy or unpack the overlay into `assets/imports/...` or over the
repository root. A migration requires a reviewed copy map, retained originals,
and a recovery path.

## Combat UI Guardrail

Current Combat is intentionally card-based. The older table-based combat UI is
removed and should not be restored during merges or updates. Any new combat
features must be implemented in the card-based module.

## Legal / Policy Note

This repository should remain a tool and preparation workspace, not a replacement for owning the adventure books. Do not publish Paizo PDFs, official maps, extracted artwork, or long verbatim adventure text.

For public releases, use only:

- original code
- original explanatory docs
- short summaries in our own words
- user-created campaign notes
- placeholders for local purchased assets
