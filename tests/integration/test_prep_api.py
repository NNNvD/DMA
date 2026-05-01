import asyncio

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


def _create_entity(client: TestClient, **payload):
    response = client.post("/api/campaign/entities", json=payload)
    assert response.status_code == 200
    return response.json()


def test_session_brief_api_generates_prep_artifact_and_scene_seeds():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        docks = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven Docks",
            details={"category": "harbor"},
        )
        _create_entity(
            client,
            entity_type="pc",
            name="Talia Stormborn",
            current_location_id=docks["id"],
            details={
                "hooks": ["Investigate the smuggler ledger"],
                "goals": ["Protect Greyhaven"],
            },
        )
        _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            current_location_id=docks["id"],
            details={"goals": ["Rebuild Dock 7"]},
        )
        _create_entity(
            client,
            entity_type="shop",
            name="Brass Lantern Outfitters",
            current_location_id=docks["id"],
            details={"category": "outfitter"},
        )
        _create_entity(
            client,
            entity_type="artifact",
            name="Storm Ledger",
        )
        _create_entity(
            client,
            entity_type="calendar",
            name="Coast Reckoning",
            details={"current_date": {"year": 4726, "month": "Dawnswell", "day": 20}},
        )
        _create_entity(
            client,
            entity_type="event",
            name="Guild Tribunal",
            summary="The guild will question captured smugglers.",
            details={
                "scheduled_for": "year=4726; month=Dawnswell; day=21",
                "status": "active",
            },
        )

        session_update = client.post(
            "/api/campaign/import/session-update",
            json={
                "title": "Session 12 - Harbor Fire",
                "content": """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=20
Summary: Dock 7 burned during the smuggler attack.
Timeline Position: session-12

## NPC: Captain Mira
Status: exhausted
Location: Greyhaven Docks

## Changelog
- Captain Mira owes Talia a favor.
- The smugglers may return for the ledger.
""",
            },
        )
        assert session_update.status_code == 200

        response = client.post(
            "/api/prep/session-brief",
            json={
                "title": "Session 13 Prep",
                "focus": "harbor fallout",
                "current_location_id": docks["id"],
                "session_count": 2,
            },
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["title"] == "Session 13 Prep"
        assert payload["document"]["kind"] == "session_prep"
        assert payload["location"]["name"] == "Greyhaven Docks"
        assert payload["calendar"]["current_date"]["day"] == 20
        assert payload["recent_sessions"][0]["title"] == "Session 12 - Harbor Fire"
        assert any(
            hook["text"] == "Investigate the smuggler ledger"
            for hook in payload["active_hooks"]
        )
        assert any(
            "Storm Ledger" in flag["message"] for flag in payload["continuity_flags"]
        )
        assert any(
            seed["location"]["name"] == "Greyhaven Docks"
            for seed in payload["scene_seeds"]
            if seed["location"] is not None
        )
        assert "## Scene Seeds" in payload["markdown"]

        prep_docs = client.get("/api/documents", params={"kind": "session_prep"})
        assert prep_docs.status_code == 200
        assert prep_docs.json()["total"] == 1
        assert prep_docs.json()["items"][0]["title"] == "Session 13 Prep"
    finally:
        asyncio.run(engine.dispose())
