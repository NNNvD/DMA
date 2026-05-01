import asyncio

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


FIRST_IMPORT = """
## Location: Greyhaven
Category: city
Region: Sapphire Coast
Languages: Common, Dwarvish
Summary: A salt-swept trade city.

## Faction: Lantern Guild
Agenda: Protect trade routes
Languages: Common

## PC: Talia Stormborn
Role: ranger
Location: Greyhaven
Goals: Find the vanished warden
Relationships: member -> Lantern Guild

## NPC: Captain Mira
Role: harbor master
Location: Greyhaven
Languages: Common, Varisian
Relationships: ally -> Lantern Guild; contact -> Talia Stormborn

## Shop: Brass Lantern Outfitters
Location: Greyhaven
Owner Name: Sella Vane
Stock Summary: Rope, Lantern oil, Climbing kits
"""

SECOND_IMPORT = """
## NPC: Captain Mira
Role: harbor master
Location: Greyhaven
Languages: Common, Varisian, Elven
Relationships: contact -> Talia Stormborn
"""


def test_campaign_note_import_creates_entities_relationships_and_document():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/campaign/import/notes",
            json={
                "title": "Greyhaven Setup",
                "content": FIRST_IMPORT,
                "source_name": "DM Notes",
                "default_tags": ["session-zero"],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["document"]["kind"] == "campaign_note"
        assert payload["summary"]["created_entities"] == 5
        assert payload["summary"]["created_relationships"] == 3
        assert not payload["warnings"]

        documents = client.get("/api/documents", params={"kind": "campaign_note"})
        assert documents.status_code == 200
        assert documents.json()["total"] == 1

        location = client.get(
            "/api/campaign/entities",
            params={"entity_type": "location", "q": "Greyhaven"},
        )
        assert location.status_code == 200
        greyhaven = location.json()["items"][0]

        npc_query = client.get(
            "/api/campaign/entities",
            params={"entity_type": "npc", "current_location_id": greyhaven["id"]},
        )
        assert npc_query.status_code == 200
        npc_payload = npc_query.json()
        assert npc_payload["total"] == 1
        assert npc_payload["items"][0]["name"] == "Captain Mira"

        pc_query = client.get("/api/campaign/entities", params={"q": "Talia Stormborn"})
        assert pc_query.status_code == 200
        talia = pc_query.json()["items"][0]
        faction_ties = client.get(
            "/api/campaign/entities",
            params={
                "relationship_type": "member",
                "related_entity_id": talia["id"],
            },
        )
        assert faction_ties.status_code == 200
        assert faction_ties.json()["items"][0]["name"] == "Lantern Guild"
    finally:
        asyncio.run(engine.dispose())


def test_campaign_note_import_reuses_existing_entities_on_reimport():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        first_response = client.post(
            "/api/campaign/import/notes",
            json={"title": "Greyhaven Setup", "content": FIRST_IMPORT},
        )
        assert first_response.status_code == 200

        second_response = client.post(
            "/api/campaign/import/notes",
            json={
                "title": "Greyhaven Update",
                "content": SECOND_IMPORT,
                "store_document": False,
            },
        )
        assert second_response.status_code == 200
        payload = second_response.json()
        assert payload["document"] is None
        assert payload["summary"]["created_entities"] == 0
        assert payload["summary"]["updated_entities"] == 1

        npc_query = client.get(
            "/api/campaign/entities", params={"entity_type": "npc", "q": "Captain Mira"}
        )
        assert npc_query.status_code == 200
        npc_payload = npc_query.json()
        assert npc_payload["total"] == 1
        assert npc_payload["items"][0]["details"]["languages"] == [
            "Common",
            "Varisian",
            "Elven",
        ]
    finally:
        asyncio.run(engine.dispose())
