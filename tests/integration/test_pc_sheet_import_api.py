import asyncio

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


PC_SHEET = """
Name: Talia Stormborn
Class: Ranger
Level: 4
Background: Sailor
Ancestry: Human
Languages: Common, Elven
Scripts: Common
Goals: Find the vanished warden
Hooks: Lantern Guild owes her a favor
Attributes: STR=12, DEX=18, CON=14, INT=10, WIS=16, CHA=8
Skills: Acrobatics, Perception, Survival
Spells: Hunter's Mark, Misty Step
Items: Moonbow, Healing Potion
Notable Items: Moonbow, Wayfinder Compass
Location: Greyhaven
Factions: Lantern Guild
Relationships: contact -> Captain Mira
Tags: player, main-party
"""

UPDATED_PC_SHEET = """
Name: Talia Stormborn
Class: Ranger
Level: 5
Background: Sailor
Languages: Common, Elven, Dwarvish
Items: Moonbow, Healing Potion, Cloak of Protection
Notable Items: Moonbow, Wayfinder Compass, Cloak of Protection
Location: Greyhaven
Factions: Lantern Guild
Relationships: contact -> Captain Mira
"""

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


def _create_entity(client: TestClient, **payload):
    response = client.post("/api/campaign/entities", json=payload)
    assert response.status_code == 200
    return response.json()


def test_pc_sheet_import_creates_versions_relationships_and_artifacts():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _create_entity(client, entity_type="location", name="Greyhaven")
        _create_entity(client, entity_type="npc", name="Captain Mira")

        first = client.post(
            "/api/campaign/import/pc-sheet",
            json={
                "title": "Talia Sheet",
                "content": PC_SHEET,
                "source_name": "Player 1",
            },
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["document"]["kind"] == "pc_sheet"
        assert first_payload["summary"]["created_pc"] is True
        assert first_payload["sheet_version"]["version_number"] == 1
        assert first_payload["pc"]["details"]["level"] == 4

        second = client.post(
            "/api/campaign/import/pc-sheet",
            json={
                "title": "Talia Sheet Update",
                "content": UPDATED_PC_SHEET,
                "store_document": False,
            },
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["document"] is None
        assert second_payload["summary"]["created_pc"] is False
        assert second_payload["sheet_version"]["version_number"] == 2
        assert second_payload["pc"]["details"]["level"] == 5
        assert "Dwarvish" in second_payload["pc"]["details"]["languages"]

        pc_query = client.get(
            "/api/campaign/entities",
            params={"entity_type": "pc", "q": "Talia Stormborn"},
        )
        assert pc_query.status_code == 200
        talia = pc_query.json()["items"][0]
        assert talia["latest_sheet_version"]["version_number"] == 2

        faction_ties = client.get(
            "/api/campaign/entities",
            params={"relationship_type": "member", "related_entity_id": talia["id"]},
        )
        assert faction_ties.status_code == 200
        assert faction_ties.json()["items"][0]["name"] == "Lantern Guild"

        artifacts = client.get(
            "/api/campaign/entities",
            params={"entity_type": "artifact", "owner_entity_id": talia["id"]},
        )
        assert artifacts.status_code == 200
        artifact_names = {item["name"] for item in artifacts.json()["items"]}
        assert artifact_names == {
            "Moonbow",
            "Wayfinder Compass",
            "Cloak of Protection",
        }
    finally:
        asyncio.run(engine.dispose())


def test_pc_sheet_import_accepts_pathbuilder_json_exports():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/campaign/import/pc-sheet",
            json={
                "title": "Conan Pathbuilder Export",
                "content": PATHBUILDER_EXPORT,
                "source_name": "Pathbuilder 2",
            },
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["document"]["kind"] == "pc_sheet"
        assert payload["import_format"] == "pathbuilder2_json"
        assert payload["summary"]["created_pc"] is True
        assert payload["summary"]["created_artifacts"] == 3
        assert payload["pc"]["name"] == "Conan"
        assert payload["pc"]["details"]["role"] == "fighter"
        assert payload["pc"]["details"]["heritage"] == "Dromaar"
        assert payload["sheet_version"]["payload"]["source_system"] == "pathbuilder2"
        assert payload["sheet_version"]["payload"]["attributes"]["str"] == 18
        assert payload["sheet_version"]["payload"]["ac"]["shieldBonus"] == 2

        artifacts = client.get(
            "/api/campaign/entities",
            params={"entity_type": "artifact", "owner_entity_id": payload["pc"]["id"]},
        )
        assert artifacts.status_code == 200
        assert {item["name"] for item in artifacts.json()["items"]} == {
            "Longsword",
            "Splint Mail",
            "Steel Shield",
        }
    finally:
        asyncio.run(engine.dispose())
