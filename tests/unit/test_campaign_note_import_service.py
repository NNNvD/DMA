from backend.services.campaign_note_import_service import (
    campaign_note_import_service,
)


def test_campaign_note_parser_extracts_entities_lists_and_relationships():
    content = """
    ## NPC: Captain Mira
    Role: harbor master
    Location: Greyhaven
    Languages: Common, Varisian
    Tags: harbor, guard
    Relationships: ally -> Lantern Guild; contact -> Talia Stormborn -> Trusts her instincts
    Description: Keeps the docks running.
    """

    parsed = campaign_note_import_service.parse_content(
        content, default_tags=["imported"]
    )

    assert len(parsed) == 1
    entity = parsed[0]
    assert entity.entity_type == "npc"
    assert entity.name == "Captain Mira"
    assert entity.current_location_reference == "Greyhaven"
    assert entity.details["role"] == "harbor master"
    assert entity.details["languages"] == ["Common", "Varisian"]
    assert entity.tags == ["imported", "harbor", "guard"]
    assert entity.relationships[0].relationship_type == "ally"
    assert entity.relationships[0].target_reference == "Lantern Guild"
    assert entity.relationships[1].notes == "Trusts her instincts"


def test_campaign_note_parser_accepts_obsidian_frontmatter_and_wikilinks():
    content = """---
tags:
  - imported
  - harbor
---
# Captain Mira

## NPC: Captain Mira
Location: [[Campaign/Locations/Greyhaven|Greyhaven]]
Relationships: ally -> [[Campaign/Factions/Lantern Guild|Lantern Guild]]
Languages: Common, Varisian
"""

    parsed = campaign_note_import_service.parse_content(content)

    assert len(parsed) == 1
    entity = parsed[0]
    assert entity.current_location_reference == "Greyhaven"
    assert entity.tags == ["imported", "harbor"]
    assert entity.relationships[0].target_reference == "Lantern Guild"
