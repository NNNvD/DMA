from backend.services.session_update_service import session_update_service


def test_session_update_parser_extracts_metadata_and_changelog():
    content = """
    Calendar: Coast Reckoning
    Current Date: year=4726; month=Dawnswell; day=19
    Summary: The harbor is recovering.
    Timeline Position: session-12

    ## NPC: Captain Mira
    Status: grateful
    Location: Greyhaven

    ## Changelog
    - Dock 7 burned during the attack.
    - Lantern Guild now trusts the party.
    """

    parsed = session_update_service.parse_metadata(content)

    assert parsed.metadata["calendar"] == "Coast Reckoning"
    assert parsed.metadata["current date"] == "year=4726; month=Dawnswell; day=19"
    assert parsed.metadata["timeline position"] == "session-12"
    assert parsed.changelog == [
        "Dock 7 burned during the attack.",
        "Lantern Guild now trusts the party.",
    ]


def test_session_update_entity_parser_ignores_metadata_lines():
    content = """
    Calendar: Coast Reckoning
    Current Date: year=4726; month=Dawnswell; day=19

    ## NPC: Captain Mira
    Status: grateful
    Location: Greyhaven
    """

    parsed = session_update_service.parse_entities(content)

    assert len(parsed) == 1
    assert parsed[0].entity_type == "npc"
    assert parsed[0].name == "Captain Mira"


def test_session_update_parser_accepts_obsidian_frontmatter_and_wikilinks():
    content = """---
tags:
  - session-log
calendar: Coast Reckoning
summary: The harbor is recovering.
---
# Session 12 - Harbor Fire

Current Date: year=4726; month=Dawnswell; day=19
Timeline Position: session-12

## NPC: Captain Mira
Status: grateful
Location: [[Campaign/Locations/Greyhaven|Greyhaven]]

## Changelog
- Dock 7 burned during the attack.
"""

    parsed = session_update_service.parse_metadata(content)
    entities = session_update_service.parse_entities(content)

    assert parsed.metadata["calendar"] == "Coast Reckoning"
    assert parsed.metadata["summary"] == "The harbor is recovering."
    assert parsed.metadata["current date"] == "year=4726; month=Dawnswell; day=19"
    assert parsed.changelog == ["Dock 7 burned during the attack."]
    assert entities[0].current_location_reference == "Greyhaven"
    assert entities[0].tags == ["session-log"]
