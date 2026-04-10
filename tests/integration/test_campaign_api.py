import asyncio

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


def _create_entity(client: TestClient, **payload):
    response = client.post("/api/campaign/entities", json=payload)
    assert response.status_code == 200
    return response.json()


def test_campaign_queries_cover_location_language_and_relationship_filters():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        city = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven",
            details={
                "category": "city",
                "region": "The Sapphire Coast",
                "languages": ["Common", "Dwarvish"],
            },
        )
        faction = _create_entity(
            client,
            entity_type="faction",
            name="Lantern Guild",
            details={
                "agenda": "Protect trade routes",
                "languages": ["Common"],
            },
        )
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Talia Stormborn",
            current_location_id=city["id"],
            details={
                "role": "ranger",
                "languages": ["Common"],
                "hooks": ["Find the vanished warden"],
            },
        )
        _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            current_location_id=city["id"],
            details={
                "role": "harbor master",
                "languages": ["Common", "Varisian"],
            },
        )

        response = client.post(
            "/api/campaign/relationships",
            json={
                "source_entity_id": pc["id"],
                "target_entity_id": faction["id"],
                "relationship_type": "member",
                "notes": "Talia scouts for the guild when ships go missing.",
            },
        )
        assert response.status_code == 200

        response = client.post(
            f"/api/campaign/entities/{pc['id']}/sheet-versions",
            json={
                "source_name": "Level 3 update",
                "sheet": {
                    "class_name": "Ranger",
                    "level": 3,
                    "languages": ["Common", "Elven"],
                    "items": ["Moonbow", {"name": "Wayfinder Compass"}],
                    "goals": ["Find the vanished warden"],
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["version_number"] == 1

        location_query = client.get(
            "/api/campaign/entities",
            params={"entity_type": "npc", "current_location_id": city["id"]},
        )
        assert location_query.status_code == 200
        payload = location_query.json()
        assert payload["total"] == 1
        assert payload["items"][0]["name"] == "Captain Mira"

        language_query = client.get(
            "/api/campaign/entities", params={"language": "Elven"}
        )
        assert language_query.status_code == 200
        language_payload = language_query.json()
        assert {item["name"] for item in language_payload["items"]} == {
            "Talia Stormborn"
        }

        faction_ties_query = client.get(
            "/api/campaign/entities",
            params={"relationship_type": "member", "related_entity_id": pc["id"]},
        )
        assert faction_ties_query.status_code == 200
        ties_payload = faction_ties_query.json()
        assert ties_payload["total"] == 1
        assert ties_payload["items"][0]["name"] == "Lantern Guild"

        relationships = client.get(f"/api/campaign/entities/{pc['id']}/relationships")
        assert relationships.status_code == 200
        relationship_payload = relationships.json()
        assert relationship_payload["relationships"][0]["related_entity"]["name"] == (
            "Lantern Guild"
        )
    finally:
        asyncio.run(engine.dispose())


def test_campaign_overview_includes_artifacts_calendar_and_shop_state():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        city = _create_entity(
            client,
            entity_type="location",
            name="Saltmarket",
            details={"category": "port town"},
        )
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Iria Vale",
            current_location_id=city["id"],
            details={"role": "bard"},
        )
        _create_entity(
            client,
            entity_type="artifact",
            name="Moonwake Lute",
            owner_entity_id=pc["id"],
            current_location_id=city["id"],
            details={"rarity": "rare", "artifact_type": "instrument"},
        )
        _create_entity(
            client,
            entity_type="shop",
            name="Brass Lantern Outfitters",
            current_location_id=city["id"],
            details={
                "category": "outfitter",
                "owner_name": "Sella Vane",
                "stock_summary": ["Rope", "Lantern oil", "Climbing kits"],
            },
        )
        _create_entity(
            client,
            entity_type="calendar",
            name="Coast Reckoning",
            details={
                "months": ["Dawnswell", "Tidewane"],
                "weekdays": ["Moonday", "Stormday"],
                "current_date": {"year": 4726, "month": "Dawnswell", "day": 18},
            },
        )
        _create_entity(
            client,
            entity_type="holiday",
            name="Night of Tides",
            current_location_id=city["id"],
            details={"date_label": "Dawnswell 21", "recurrence": "annual"},
        )

        response = client.get("/api/campaign/overview")
        assert response.status_code == 200
        payload = response.json()

        assert payload["counts"]["artifact"] == 1
        assert payload["counts"]["calendar"] == 1
        assert payload["counts"]["holiday"] == 1
        assert payload["artifacts"][0]["owner_entity"]["name"] == "Iria Vale"
        assert payload["shops"][0]["current_location"]["name"] == "Saltmarket"
        assert payload["calendars"][0]["details"]["current_date"]["day"] == 18
    finally:
        asyncio.run(engine.dispose())


def test_pc_sheet_versions_increment_and_update_latest_sheet_state():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Neris Vale",
            details={"role": "wizard"},
        )

        first = client.post(
            f"/api/campaign/entities/{pc['id']}/sheet-versions",
            json={
                "source_name": "Level 1 sheet",
                "sheet": {
                    "class_name": "Wizard",
                    "level": 1,
                    "languages": ["Common", "Draconic"],
                    "items": ["Spellbook"],
                },
            },
        )
        assert first.status_code == 200
        assert first.json()["version_number"] == 1

        second = client.post(
            f"/api/campaign/entities/{pc['id']}/sheet-versions",
            json={
                "source_name": "Level 2 sheet",
                "sheet": {
                    "class_name": "Wizard",
                    "level": 2,
                    "languages": ["Common", "Draconic", "Elven"],
                    "items": ["Spellbook", {"name": "Pearl of Power"}],
                },
            },
        )
        assert second.status_code == 200
        assert second.json()["version_number"] == 2

        versions = client.get(f"/api/campaign/entities/{pc['id']}/sheet-versions")
        assert versions.status_code == 200
        payload = versions.json()
        assert [version["version_number"] for version in payload["versions"]] == [1, 2]

        entity = client.get(f"/api/campaign/entities/{pc['id']}")
        assert entity.status_code == 200
        entity_payload = entity.json()
        assert entity_payload["latest_sheet_version"]["version_number"] == 2
        assert entity_payload["details"]["level"] == 2
        assert entity_payload["details"]["languages"] == [
            "Common",
            "Draconic",
            "Elven",
        ]
        assert "Pearl of Power" in entity_payload["details"]["notable_items"]
    finally:
        asyncio.run(engine.dispose())
