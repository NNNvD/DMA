from __future__ import annotations

import json
from pathlib import Path

from backend.services.private_import_audit_service import PrivateImportAuditService


def _write_room_key(root: Path) -> None:
    room_key_root = root / "room-keys" / "test-campaign"
    room_key_root.mkdir(parents=True)
    (room_key_root / "level-1.json").write_text(
        json.dumps(
            {
                "map_id": "level1",
                "title": "Level 1",
                "rooms": [
                    {
                        "room_id": "A1",
                        "title": "Damp Entrance",
                        "player_visible_description": "Wet stone.",
                        "gm_description": "Mitflits watch the entrance.",
                        "monsters": ["Mitflit"],
                        "hazards": [],
                        "loot": ["Minor potion"],
                        "source": "Test PDF, p. 1",
                        "literal_text": {
                            "read_aloud": "Wet stone glistens.",
                            "general_text": "Creatures wait nearby.",
                        },
                        "encounter_refs": [{"id": "mitflit", "type": "aon_reference"}],
                    },
                    {
                        "room_id": "A3",
                        "title": "Skipped Room",
                        "player_visible_description": "",
                        "gm_description": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_import_audit_run_creates_room_drafts_and_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    (tmp_path / "reference" / "raw").mkdir(parents=True)
    (tmp_path / "reference" / "raw" / "Adventure.pdf").write_bytes(b"%PDF fake")
    _write_room_key(tmp_path)

    service = PrivateImportAuditService()
    run = service.create_import_run(map_id="level1")

    assert run["room_draft_count"] == 2
    sources = json.loads(
        (tmp_path / "campaigns" / "test-campaign" / "sources.json").read_text(
            encoding="utf-8"
        )
    )
    assert sources["sources"][0]["sha256"]
    drafts = service.room_drafts(run["run_id"])
    assert drafts is not None
    assert [item["room_id"] for item in drafts["items"]] == ["A1", "A3"]
    summary = service.audit_summary(run["run_id"])
    assert summary is not None
    issue_fields = {issue["field"] for issue in summary["field_issues"]}
    assert "missing_player_description" in issue_fields
    assert "missing-room-A2" in {issue["id"] for issue in summary["field_issues"]}


def test_import_audit_review_and_promote_only_approved_rooms(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_room_key(tmp_path)

    service = PrivateImportAuditService()
    run = service.create_import_run(map_id="level1")
    updated = service.update_room_draft(
        run["run_id"],
        "level1:A1",
        {"review_status": "approved", "reviewer_notes": "Looks good."},
    )

    assert updated is not None
    assert updated["review_status"] == "approved"
    result = service.promote_reviewed_rooms(run["run_id"])
    assert result is not None
    assert result["promoted_count"] == 1
    promoted = json.loads(
        (tmp_path / "room-keys" / "test-campaign" / "level-1.json").read_text(
            encoding="utf-8"
        )
    )
    rooms = {room["room_id"]: room for room in promoted["rooms"]}
    assert rooms["A1"]["review"]["review_status"] == "promoted"
    assert "review" not in rooms["A3"]
