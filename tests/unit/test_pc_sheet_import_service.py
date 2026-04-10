import json

from backend.services.pc_sheet_import_service import pc_sheet_import_service


def test_pc_sheet_parser_extracts_sheet_payload_and_relationships():
    content = """
    Name: Talia Stormborn
    Class: Ranger
    Level: 4
    Background: Sailor
    Ancestry: Human
    Languages: Common, Elven
    Scripts: Common
    Attributes: STR=12, DEX=18, CON=14
    Skills: Acrobatics, Perception
    Items: Moonbow, Healing Potion
    Notable Items: Moonbow, Wayfinder Compass
    Factions: Lantern Guild
    Relationships: contact -> Captain Mira -> Trusts her judgment
    Location: Greyhaven
    """

    parsed = pc_sheet_import_service.parse_content(content, default_tags=["player"])

    assert parsed.name == "Talia Stormborn"
    assert parsed.tags == ["player"]
    assert parsed.current_location_reference == "Greyhaven"
    assert parsed.faction_references == ["Lantern Guild"]
    assert parsed.sheet_payload["class_name"] == "Ranger"
    assert parsed.sheet_payload["level"] == 4
    assert parsed.sheet_payload["attributes"]["dex"] == 18
    assert "Wayfinder Compass" in parsed.notable_items
    assert parsed.relationship_specs[0] == (
        "contact",
        "Captain Mira",
        "Trusts her judgment",
    )


PATHBUILDER_EXPORT = {
    "success": True,
    "build": {
        "name": "Conan",
        "class": "Fighter",
        "dualClass": None,
        "level": 4,
        "xp": 25,
        "ancestry": "Human",
        "heritage": "Dromaar",
        "background": "Barkeep",
        "alignment": "N",
        "gender": "Not set",
        "age": "Not set",
        "deity": "Not set",
        "size": 2,
        "sizeName": "Medium",
        "keyability": "str",
        "languages": ["None selected"],
        "rituals": [],
        "resistances": [],
        "abilities": {
            "str": 18,
            "dex": 14,
            "con": 14,
            "int": 12,
            "wis": 10,
            "cha": 10,
            "breakdown": {"classBoosts": ["Str"]},
        },
        "attributes": {
            "ancestryhp": 8,
            "classhp": 10,
            "bonushp": 0,
            "bonushpPerLevel": 0,
            "speed": 25,
            "speedBonus": 0,
        },
        "proficiencies": {
            "classDC": 2,
            "perception": 4,
            "fortitude": 4,
            "reflex": 4,
            "will": 4,
            "martial": 4,
            "simple": 4,
            "unarmed": 4,
            "acrobatics": 2,
            "athletics": 4,
            "diplomacy": 2,
            "medicine": 2,
            "performance": 2,
        },
        "feats": [
            ["Shield Block", None, "Awarded Feat", 1],
            ["Double Slice", None, "Class Feat", 2],
        ],
        "specials": ["Reactive Strike", "Low-Light Vision"],
        "lores": [["Alcohol", 2]],
        "equipmentContainers": {
            "pack-1": {
                "containerName": "Backpack",
                "bagOfHolding": False,
                "backpack": True,
                "augmentations": False,
            }
        },
        "equipment": [
            ["Backpack", 1, "Invested"],
            ["Bedroll", 1, "pack-1", "Invested"],
            ["Repair Kit", 1, "Invested"],
        ],
        "weapons": [
            {
                "name": "Longsword",
                "qty": 1,
                "prof": "martial",
                "die": "d8",
                "display": "Longsword",
                "runes": [],
                "damageType": "S",
                "attack": 12,
                "damageBonus": 4,
                "grade": "",
            }
        ],
        "money": {"cp": 92, "sp": 100, "gp": 150, "pp": 3},
        "armor": [
            {
                "name": "Splint Mail",
                "qty": 1,
                "prof": "heavy",
                "display": "Splint Mail",
                "worn": True,
                "runes": [],
                "grade": "",
            },
            {
                "name": "Steel Shield",
                "qty": 1,
                "prof": "shield",
                "display": "",
                "worn": True,
                "runes": [],
                "grade": "",
            },
        ],
        "spellCasters": [],
        "focusPoints": 0,
        "acTotal": {
            "acProfBonus": 6,
            "acAbilityBonus": 1,
            "acItemBonus": 5,
            "acTotal": 22,
            "shieldBonus": "2",
        },
    },
}


def test_pc_sheet_parser_detects_pathbuilder_json_exports():
    parsed = pc_sheet_import_service.parse_content(
        json.dumps(PATHBUILDER_EXPORT),
        default_tags=["sample"],
    )

    assert parsed.name == "Conan"
    assert parsed.source_format == "pathbuilder2_json"
    assert parsed.tags == ["sample", "pathbuilder2", "pf2e"]
    assert parsed.entity_details["role"] == "fighter"
    assert parsed.entity_details["heritage"] == "Dromaar"
    assert parsed.sheet_payload["source_system"] == "pathbuilder2"
    assert parsed.sheet_payload["class_name"] == "Fighter"
    assert parsed.sheet_payload["attributes"]["str"] == 18
    assert parsed.sheet_payload["skills"] == [
        "Acrobatics",
        "Athletics",
        "Diplomacy",
        "Medicine",
        "Performance",
    ]
    assert parsed.sheet_payload["feats"] == ["Shield Block", "Double Slice"]
    assert parsed.sheet_payload["ac"]["shieldBonus"] == 2
    assert parsed.notable_items == ["Longsword", "Splint Mail", "Steel Shield"]
