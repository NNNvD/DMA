from backend.services.obsidian_markdown import (
    build_frontmatter,
    extract_tags,
    replace_wikilinks,
    safe_note_stem,
    split_frontmatter,
    wikilink_for_path,
)


def test_split_frontmatter_extracts_tags_and_body():
    content = """---
tags:
  - session-log
  - greyhaven
review_status: approved
---
# Session 12

Location: [[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]
"""

    frontmatter, body = split_frontmatter(content)

    assert frontmatter["tags"] == ["session-log", "greyhaven"]
    assert frontmatter["review_status"] == "approved"
    assert body.startswith("# Session 12")
    assert extract_tags(frontmatter) == ["session-log", "greyhaven"]


def test_split_frontmatter_supports_nested_yaml_structures():
    content = """---
details:
  role: "captain"
relationships:
  - type: "ally"
    target: "[[Campaign/PCs/Talia Stormborn|Talia Stormborn]]"
---
# Captain Mira
"""

    frontmatter, _ = split_frontmatter(content)

    assert frontmatter["details"]["role"] == "captain"
    assert frontmatter["relationships"][0]["type"] == "ally"


def test_split_frontmatter_supports_flattened_obsidian_properties():
    content = """---
details_role: "captain"
audience_visibility_scope: "gm_only"
tags: ["session-log", "greyhaven"]
relationships_01_type: "ally"
relationships_01_target: "[[Campaign/PCs/Talia Stormborn|Talia Stormborn]]"
---
# Captain Mira
"""

    frontmatter, _ = split_frontmatter(content)

    assert frontmatter["details_role"] == "captain"
    assert frontmatter["audience_visibility_scope"] == "gm_only"
    assert frontmatter["tags"] == ["session-log", "greyhaven"]
    assert frontmatter["relationships_01_type"] == "ally"


def test_replace_wikilinks_uses_alias_or_note_name():
    content = (
        "Location: [[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]\n"
        "Contact: [[Campaign/NPCs/Captain Mira]]"
    )

    normalized = replace_wikilinks(content)

    assert "Location: Greyhaven Docks" in normalized
    assert "Contact: Captain Mira" in normalized


def test_frontmatter_builder_and_wikilinks_are_obsidian_friendly():
    frontmatter = build_frontmatter(
        {
            "dma_kind": "campaign_entity",
            "entity_type": "npc",
            "tags": ["dma/generated", "harbor"],
            "is_active": True,
            "relationships": [
                {
                    "type": "ally",
                    "target": "[[Campaign/PCs/Talia Stormborn|Talia Stormborn]]",
                    "notes": "Trusts her judgment",
                }
            ],
        }
    )

    assert frontmatter.startswith("---\n")
    assert 'entity_type: "npc"' in frontmatter
    assert 'tags: ["dma/generated", "harbor"]' in frontmatter
    assert "is_active: true" in frontmatter
    assert 'relationships_01_type: "ally"' in frontmatter
    assert 'relationships_01_target: "[[Campaign/PCs/Talia Stormborn|Talia Stormborn]]"' in frontmatter
    assert 'relationships_01_notes: "Trusts her judgment"' in frontmatter
    assert "\n  -" not in frontmatter
    assert wikilink_for_path("Campaign/NPCs/Captain Mira.md", alias="Captain Mira") == (
        "[[Campaign/NPCs/Captain Mira|Captain Mira]]"
    )
    assert safe_note_stem("Captain: Mira / Harbor?") == "Captain Mira Harbor"
