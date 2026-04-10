import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


CAMPAIGN_NOTE = """
## Location: Greyhaven
Category: city

## NPC: Captain Mira
Location: Greyhaven
Role: harbor master
Relationships: ally -> Talia Stormborn
"""

PC_SHEET = """
Name: Talia Stormborn
Class: Ranger
Level: 4
Location: Greyhaven
Factions: Lantern Guild
Relationships: contact -> Captain Mira
"""

SESSION_LOG = """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=19
Summary: The harbor calms after the attack.
Timeline Position: session-12

## Changelog
- Captain Mira owes Talia a favor.
"""


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def test_dropzone_preview_resolves_cross_file_references(tmp_path: Path):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write(tmp_path, "campaign-notes/greyhaven.md", CAMPAIGN_NOTE)
        _write(tmp_path, "pathbuilder/talia.txt", PC_SHEET)
        _write(tmp_path, "session-logs/session-12-harbor.md", SESSION_LOG)

        response = client.get(
            "/api/campaign/import/dropzone",
            params={"root_path": str(tmp_path)},
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["dry_run"] is True
        assert payload["summary"]["files_previewed"] == 3
        assert payload["summary"]["parsed_entities"] == 3
        assert payload["summary"]["parsed_sheet_versions"] == 1
        assert payload["summary"]["parsed_changelog_entries"] == 1

        note_preview = next(
            item for item in payload["files"] if item["category"] == "campaign-notes"
        )
        assert note_preview["warnings"] == []
        assert note_preview["preview"]["entity_count"] == 2

        pc_preview = next(
            item for item in payload["files"] if item["category"] == "pathbuilder"
        )
        assert pc_preview["import_format"] == "text"
        assert pc_preview["preview"]["name"] == "Talia Stormborn"
    finally:
        asyncio.run(engine.dispose())


def test_batch_import_is_repeatable_and_exposes_dossier_and_session_history(
    tmp_path: Path,
):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write(tmp_path, "campaign-notes/greyhaven.md", CAMPAIGN_NOTE)
        _write(tmp_path, "pathbuilder/talia.txt", PC_SHEET)
        _write(tmp_path, "session-logs/session-12-harbor.md", SESSION_LOG)

        first = client.post(
            "/api/campaign/import/batch",
            json={"root_path": str(tmp_path)},
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["summary"]["files_imported"] == 3
        assert first_payload["summary"]["created_sheet_versions"] == 1

        second = client.post(
            "/api/campaign/import/batch",
            json={"root_path": str(tmp_path)},
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["summary"]["files_imported"] == 3
        assert second_payload["summary"]["created_sheet_versions"] == 0
        assert second_payload["summary"]["reused_sheet_versions"] == 1

        note_docs = client.get("/api/documents", params={"kind": "campaign_note"})
        pc_docs = client.get("/api/documents", params={"kind": "pc_sheet"})
        session_docs = client.get("/api/documents", params={"kind": "session_log"})
        assert note_docs.json()["total"] == 1
        assert pc_docs.json()["total"] == 1
        assert session_docs.json()["total"] == 1

        pcs = client.get(
            "/api/campaign/entities",
            params={"entity_type": "pc", "q": "Talia Stormborn"},
        )
        assert pcs.status_code == 200
        pc = pcs.json()["items"][0]
        assert pc["latest_sheet_version"]["version_number"] == 1

        dossier = client.get(f"/api/campaign/pcs/{pc['id']}/dossier")
        assert dossier.status_code == 200
        dossier_payload = dossier.json()
        assert dossier_payload["pc"]["name"] == "Talia Stormborn"
        assert dossier_payload["sheet_version_count"] == 1
        assert dossier_payload["factions"][0]["name"] == "Lantern Guild"
        assert "contact" in dossier_payload["relationship_groups"]

        history = client.get("/api/campaign/session-history")
        assert history.status_code == 200
        history_payload = history.json()
        assert history_payload["total"] == 1
        item = history_payload["items"][0]
        assert item["document"]["kind"] == "session_log"
        assert item["event"]["entity_type"] == "event"

        events = client.get("/api/campaign/entities", params={"entity_type": "event"})
        assert events.status_code == 200
        assert events.json()["total"] == 1
    finally:
        asyncio.run(engine.dispose())
