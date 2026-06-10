# Public Repo And Private Overlay

This project is designed to be pushed to GitHub without redistributing copyrighted adventure assets.

## What Goes To GitHub

- DMA source code, tests, scripts, and documentation.
- Obsidian vault notes written for campaign operation.
- Metadata, manifests, and placeholders that explain where local assets should be placed.
- Player and GM prep notes written in our own words.

## What Stays Local

The following material must stay out of the public repository:

- Purchased adventure PDFs.
- Official map image files.
- Images extracted from PDFs.
- NPC, monster, item, cover, or illustration images from books.
- Generated PDF/HTML handouts that include protected setting/adventure text or styling built from such material.
- Archived third-party or older campaign assets.

These paths are intentionally ignored:

- `assets/imports/misc/private-local/`
- `assets/archive/`
- `obsidian-abomination-vaults-vault/Library/Assets/`
- `obsidian-abomination-vaults-vault/Exports/Handouts/*.pdf`
- `obsidian-abomination-vaults-vault/Exports/Handouts/*.html`
- `local-private-overlay/`

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
      obsidian-abomination-vaults-vault/
```

When `.env` leaves the standard local paths at their defaults, DMA automatically
prefers matching paths under `local-private-overlay/project-root/`. This lets a
fresh GitHub pull update public code while the ignored overlay remains a separate
manual private update.

Collaborators must manually acquire the latest `local-private-overlay/` bundle
from the GM or approved private distribution channel. GitHub updates alone will
never update private maps, PDFs, monster portraits, room keys, or campaign-only
data.

If a helper, LLM, or merge tool suggests copying `local-private-overlay/` into
`assets/`, reject that suggestion unless the GM explicitly asks for a one-off
migration.

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
