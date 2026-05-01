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

That folder mirrors the project root. To install the private assets into a fresh checkout, copy the contents of `local-private-overlay/project-root/` into the repository root.

Example:

```bash
cp -R local-private-overlay/project-root/. .
```

After copying, the DMA should find maps, PDFs, extracted local images, and handout exports at the expected local paths, while Git continues to ignore them.

## Legal / Policy Note

This repository should remain a tool and preparation workspace, not a replacement for owning the adventure books. Do not publish Paizo PDFs, official maps, extracted artwork, or long verbatim adventure text.

For public releases, use only:

- original code
- original explanatory docs
- short summaries in our own words
- user-created campaign notes
- placeholders for local purchased assets

