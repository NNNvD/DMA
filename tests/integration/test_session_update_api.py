import asyncio

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


BASE_WORLD = """
## Location: Greyhaven
Category: city

## PC: Talia Stormborn
Location: Greyhaven

## NPC: Captain Mira
Location: Greyhaven
"""

SESSION_UPDATE = """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=19
Summary: The harbor is recovering after the fire.
Timeline Position: session-12

## NPC: Captain Mira
Status: grateful
Location: Greyhaven
Goals: rebuild the docks
Relationships: ally -> Talia Stormborn

## Artifact: Moonbow
Owner: Talia Stormborn
Location: Greyhaven

## Location: Greyhaven
Summary: Dock 7 is scorched but still open.

## Changelog
- Dock 7 burned during the smuggler attack.
- Lantern Guild now trusts the party.
"""


def test_session_update_import_updates_world_state_calendar_and_changelog():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        seed = client.post(
            "/api/campaign/import/notes",
            json={"title": "Base World", "content": BASE_WORLD},
        )
        assert seed.status_code == 200

        response = client.post(
            "/api/campaign/import/session-update",
            json={
                "title": "Session 12 - Harbor Fire",
                "content": SESSION_UPDATE,
                "source_name": "DM Session Log",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["document"]["kind"] == "session_log"
        assert payload["calendar"]["name"] == "Coast Reckoning"
        assert payload["calendar"]["details"]["current_date"]["day"] == 19
        assert payload["session_event"]["name"] == "Session 12 - Harbor Fire"
        assert payload["changelog"] == [
            "Dock 7 burned during the smuggler attack.",
            "Lantern Guild now trusts the party.",
        ]

        documents = client.get("/api/documents", params={"kind": "session_log"})
        assert documents.status_code == 200
        assert documents.json()["total"] == 1

        talia_query = client.get(
            "/api/campaign/entities",
            params={"entity_type": "pc", "q": "Talia Stormborn"},
        )
        talia = talia_query.json()["items"][0]

        artifacts = client.get(
            "/api/campaign/entities",
            params={"entity_type": "artifact", "owner_entity_id": talia["id"]},
        )
        assert artifacts.status_code == 200
        assert artifacts.json()["items"][0]["name"] == "Moonbow"

        relationships = client.get(
            "/api/campaign/entities", params={"q": "Captain Mira"}
        )
        captain = relationships.json()["items"][0]
        captain_detail = client.get(f"/api/campaign/entities/{captain['id']}")
        assert captain_detail.status_code == 200
        captain_payload = captain_detail.json()
        assert any(
            item["related_entity"]["name"] == "Talia Stormborn"
            and item["relationship_type"] == "ally"
            for item in captain_payload["relationships"]
        )
    finally:
        asyncio.run(engine.dispose())
