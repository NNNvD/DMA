import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.services.metrics_service import metrics_service
from tests.support.app_factory import create_documents_test_app

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2"


def test_campaign_api_supports_manual_upserts_and_relationship_queries():
    metrics_service.reset()
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        for payload in (
            {
                "entity_type": "location",
                "entity_key": "otari",
                "name": "Otari",
                "summary": "A coastal town.",
                "location_type": "settlement",
                "region": "Isle of Kortos",
            },
            {
                "entity_type": "faction",
                "entity_key": "dawnwatch",
                "name": "Dawnwatch",
                "summary": "Otari's town watch.",
                "category": "militia",
            },
            {
                "entity_type": "npc",
                "entity_key": "captain-mira",
                "name": "Captain Mira",
                "summary": "Guard captain.",
                "role": "Guard Captain",
                "relationships": [
                    {
                        "target_key": "otari",
                        "target_type": "location",
                        "relationship_type": "located_in",
                    },
                    {
                        "target_key": "dawnwatch",
                        "target_type": "faction",
                        "relationship_type": "leads",
                    },
                ],
            },
        ):
            response = client.post("/api/campaign/entities", json=payload)
            assert response.status_code == 200, response.text

        search_response = client.get(
            "/api/campaign/entities/search",
            params={"type": "npc", "location": "otari"},
        )
        assert search_response.status_code == 200
        results = search_response.json()["results"]
        assert [item["entity_key"] for item in results] == ["captain-mira"]

        npc_response = client.get("/api/campaign/entities/captain-mira")
        assert npc_response.status_code == 200
        npc_payload = npc_response.json()
        assert npc_payload["details"]["role"] == "Guard Captain"
        assert any(
            relation["relationship_type"] == "located_in"
            and relation["entity"]["entity_key"] == "otari"
            for relation in npc_payload["relationships"]
        )
    finally:
        metrics_service.reset()
        asyncio.run(engine.dispose())


def test_campaign_import_endpoints_support_phase2_queries_and_consistency():
    metrics_service.reset()
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)
    notes = (FIXTURE_ROOT / "sample_campaign_notes.md").read_text()
    pc_sheet = json.loads((FIXTURE_ROOT / "sample_pc_sheet.json").read_text())

    try:
        notes_response = client.post(
            "/api/campaign/import/notes",
            json={"source_id": "sample-notes-v1", "markdown": notes},
        )
        assert notes_response.status_code == 200, notes_response.text
        assert notes_response.json()["status"] == "applied"

        pc_response = client.post("/api/campaign/import/pc-sheet", json=pc_sheet)
        assert pc_response.status_code == 200, pc_response.text
        assert pc_response.json()["status"] == "applied"

        npcs_response = client.get("/api/campaign/npcs", params={"location": "otari"})
        assert npcs_response.status_code == 200
        npc_keys = [item["entity_key"] for item in npcs_response.json()["results"]]
        assert npc_keys == ["captain-mira"]

        factions_response = client.get("/api/campaign/pcs/talia-storm/factions")
        assert factions_response.status_code == 200
        factions_payload = factions_response.json()
        assert factions_payload["pc"]["entity_key"] == "talia-storm"
        assert factions_payload["factions"][0]["entity"]["entity_key"] == "dawnwatch"

        detail_response = client.get("/api/campaign/entities/talia-storm")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["details"]["character_class"] == "Ranger"
        assert any(
            relation["relationship_type"] == "ally_of"
            and relation["entity"]["entity_key"] == "captain-mira"
            for relation in detail_payload["relationships"]
        )

        consistency_response = client.get("/api/campaign/consistency")
        assert consistency_response.status_code == 200
        assert consistency_response.json()["ok"] is True

        metrics_response = client.get("/api/admin/metrics")
        assert metrics_response.status_code == 200
        operations = metrics_response.json()["operations"]
        assert operations["campaign.import.notes"]["count"] == 1
        assert operations["campaign.import.pc_sheet"]["count"] == 1
        assert operations["campaign.npcs.by_location"]["count"] == 1
    finally:
        metrics_service.reset()
        asyncio.run(engine.dispose())
