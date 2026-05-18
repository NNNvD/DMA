# Image Curation Workflow

DMA supports three image paths:

- `imageLink:` for a local Obsidian-vault image such as `[[Library/Assets/Portraits/PCs/Daan.png]]`
- `image_url:` or `portrait_url:` for a remote image
- no image, which displays a clear placeholder

Recommended metadata beside the image:

```yaml
imageLink: "[[Library/Assets/Portraits/PCs/Daan.png]]"
image_status: "confirmed"
image_source: "player supplied"
image_attribution: "Daan"
image_notes: "Approved PC portrait"
```

## PCs

Put player-supplied portraits under:

`obsidian-abomination-vaults-vault/Library/Assets/Portraits/PCs/`

Then add the portrait metadata to the matching note in `Sheets/`.

## NPCs

Do not assign extracted campaign images automatically from their filenames alone.
Build the review gallery:

```bash
python3 scripts/build_image_curation_index.py
```

Then open:

`Command Center/Assets/NPC Image Curation.md`

Use the gallery to confirm which extracted image belongs to which NPC, then add the
chosen `imageLink:` and metadata to the canonical NPC note.

Suggested statuses:

- `needs review`
- `confirmed`
- `decorative`
- `wrong match`
- `missing`

### Recommended NPC Matching Scheme

Use a four-step workflow:

1. **Page candidates**: start with extracted images from the same PDF page as the NPC's source reference, then the adjacent pages.
2. **Text candidates**: compare the nearby source text, captions, headings, and NPC appearance description against the image.
3. **Human confirmation**: a GM confirms the visual match once; never promote a guess directly to `confirmed`.
4. **Canonical assignment**: store only the confirmed result on the NPC note, with the evidence used to choose it.

Recommended metadata once confirmed:

```yaml
imageLink: "[[Library/Assets/Abomination Vaults 1 Ruins Of Gauntlight/page-090-image-01.png]]"
image_status: "confirmed"
image_source: "Abomination Vaults 1 - Ruins of Gauntlight.pdf"
image_source_page: 90
image_match_basis: "same-page NPC entry and visual description"
image_confidence: "high"
```

This gives us a useful automation path later:

- generate candidate images from `source_references_*_page`
- show same-page and adjacent-page images first in the review queue
- let the GM mark `confirmed`, `wrong match`, or `decorative`
- only then write `imageLink:` back to the canonical NPC note

This is safer than trusting the current extracted filenames. For example, two different NPC notes can accidentally point to the same art if we assign images only from page order without review.

## Monsters

DMA can display a remote monster image URL returned with an Archives of Nethys creature
record when one is available. Keep these as remote references first; do not download or
redistribute monster art unless the reuse rights have been reviewed separately.

Use local monster images only when you have a campaign-specific asset you are allowed to
store locally.
