import asyncio

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


def test_in_game_state_is_revisioned_and_survives_legacy_combat_writes():
    app, engine, _ = create_documents_test_app()
    try:
        with TestClient(app) as client:
            initial = client.get("/api/live/session-state").json()
            save = client.patch(
                "/api/live/in-game-state",
                json={
                    "expected_revision": initial["revision"],
                    "state": {
                        "location_name": "Old Bridge",
                        "calendar_name": "Lantern Reckoning",
                        "weekday": "Bellday",
                        "year": 12,
                        "month": "Bloom",
                        "day": 2,
                        "season": "spring",
                        "time_of_day": "morning",
                    },
                },
            )
            assert save.status_code == 200
            saved = save.json()
            assert saved["in_game_state"]["location_name"] == "Old Bridge"
            assert saved["in_game_state"]["weekday"] == "Bellday"
            assert saved["revision"] > initial["revision"]
            stale = client.patch(
                "/api/live/in-game-state",
                json={
                    "expected_revision": initial["revision"],
                    "state": {"location_name": "Wrong"},
                },
            )
            assert stale.status_code == 409
            combat = client.put(
                "/api/live/session-state",
                json={
                    "expected_revision": saved["revision"],
                    "combat_state": {"combatants": [{"name": "Guard", "hpTrack": [8]}]},
                },
            )
            assert combat.status_code == 200
            assert combat.json()["in_game_state"]["location_name"] == "Old Bridge"
            patch = client.patch(
                "/api/live/in-game-state",
                json={
                    "expected_revision": combat.json()["revision"],
                    "state": {
                        **saved["in_game_state"]["inputs"],
                        "weather_mode": "manual",
                        "weather_text": "Dense fog",
                        "time_of_day": "night",
                    },
                },
            )
            assert patch.status_code == 200
            assert (
                patch.json()["state"]["combat_state"]["combatants"][0]["name"]
                == "Guard"
            )
            loaded = client.get("/api/live/session-state").json()
            assert loaded["in_game_state"]["weather"] == "Dense fog"
            assert (
                "visibility" in loaded["in_game_state"]["environmental_effects"].lower()
            )
            reset = client.delete(
                "/api/live/session-state", headers={"If-Match": str(loaded["revision"])}
            )
            assert reset.status_code == 200
            assert reset.json()["in_game_state"]["location_name"] == ""
    finally:
        asyncio.run(engine.dispose())


def test_game_state_rejects_invalid_context_without_mutating_revision():
    app, engine, _ = create_documents_test_app()
    try:
        with TestClient(app) as client:
            initial = client.get("/api/live/session-state").json()
            for state in (
                {"day": 0},
                {"day": 31, "month": "Bloom", "calendar_id": 999},
                {"location_type": "ocean"},
                {"weather_mode": "automatic"},
                {"weather_seed": -1},
            ):
                response = client.patch(
                    "/api/live/in-game-state",
                    json={"expected_revision": initial["revision"], "state": state},
                )
                assert response.status_code in (400, 422)
                assert (
                    client.get("/api/live/session-state").json()["revision"]
                    == initial["revision"]
                )
    finally:
        asyncio.run(engine.dispose())


def test_campaign_calendar_metadata_and_location_profiles_drive_live_state():
    app, engine, _ = create_documents_test_app()
    try:
        with TestClient(app) as client:
            calendar = client.post(
                "/api/campaign/entities",
                json={
                    "entity_type": "calendar",
                    "name": "Belltide Reckoning",
                    "details": {
                        "months": [
                            {"name": "Bloom", "days": 30, "season": "spring"},
                            {"name": "Frost", "days": 30, "season": "winter"},
                        ],
                        "weekdays": ["Emberday", "Tideday", "Bellday"],
                        "current_date": {
                            "year": 12,
                            "month": "Bloom",
                            "day": 1,
                            "weekday": "Emberday",
                        },
                    },
                },
            )
            assert calendar.status_code == 200
            location = client.post(
                "/api/campaign/entities",
                json={
                    "entity_type": "location",
                    "name": "Library",
                    "details": {"location_type": "indoors", "climate": "cold"},
                },
            )
            assert location.status_code == 200
            initial = client.put(
                "/api/live/session-state",
                json={"current_location_id": location.json()["id"]},
            ).json()
            assert initial["in_game_state"]["location_type"] == "indoors"
            assert initial["in_game_state"]["climate"] == "cold"
            assert initial["in_game_state"]["weekday"] == "Emberday"
            update = client.patch(
                "/api/live/in-game-state",
                json={
                    "expected_revision": initial["revision"],
                    "state": {
                        "calendar_id": calendar.json()["id"],
                        "year": 12,
                        "month": "Frost",
                        "day": 2,
                        "location_name": "Road",
                    },
                },
            )
            assert update.status_code == 200
            assert update.json()["in_game_state"]["weekday"] == "Tideday"
            assert update.json()["in_game_state"]["resolved_season"] == "winter"
            invalid = client.patch(
                "/api/live/in-game-state",
                json={
                    "expected_revision": update.json()["revision"],
                    "state": {
                        "calendar_id": calendar.json()["id"],
                        "year": 12,
                        "month": "Frost",
                        "day": 31,
                    },
                },
            )
            assert invalid.status_code == 400
    finally:
        asyncio.run(engine.dispose())
