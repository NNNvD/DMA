from __future__ import annotations

import json
from pathlib import Path

from backend.services.private_index_service import PrivateIndexService
from backend.services.reference_corpus_service import ReferenceCorpusService


def _write_private_fixture(root: Path) -> None:
    campaign_root = root / "campaigns" / "test-campaign"
    campaign_root.mkdir(parents=True)
    (campaign_root / "sessions.json").write_text(
        json.dumps(
            {
                "campaign_id": "test-campaign",
                "items": [
                    {
                        "id": "session-1",
                        "title": "Session 1",
                        "body_markdown": "The party found a silver key.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    room_root = root / "room-keys" / "test-campaign"
    room_root.mkdir(parents=True)
    (room_root / "level-1.json").write_text(
        json.dumps(
            {
                "map_id": "level1",
                "rooms": [
                    {
                        "room_id": "A1",
                        "title": "Entrance",
                        "player_visible_description": "A damp hall.",
                        "gm_description": "Mitflits wait here.",
                        "monsters": ["Mitflit"],
                        "hazards": ["Spear Launcher"],
                        "afflictions": ["Ghoul Fever"],
                        "loot": ["minor healing potion"],
                        "literal_text": {
                            "read_aloud": "The air is wet.",
                            "general_text": "Creatures hide in shadows.",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    bestiary_root = root / "bestiary" / "test-campaign"
    bestiary_root.mkdir(parents=True)
    (bestiary_root / "level-1.json").write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "spear-launcher",
                        "name": "Spear Launcher",
                        "entry_type": "hazard",
                        "rooms": ["A1"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    raw_creatures = root / "reference" / "aon" / "creatures" / "raw"
    raw_creatures.mkdir(parents=True)
    (raw_creatures / "mitflit.json").write_text(
        json.dumps(
            {
                "id": "245",
                "name": "Mitflit",
                "url": "https://2e.aonprd.com/Monsters.aspx?ID=245",
                "traits": ["Fey"],
                "content": "Mitflits are gremlin pests.",
            }
        ),
        encoding="utf-8",
    )
    raw_diseases = root / "reference" / "aon" / "diseases" / "raw"
    raw_diseases.mkdir(parents=True)
    (raw_diseases / "ghoul-fever.json").write_text(
        json.dumps(
            {
                "id": "1",
                "name": "Ghoul Fever",
                "url": "https://2e.aonprd.com/Diseases.aspx?ID=1",
                "content": "Ghoul fever is a disease.",
            }
        ),
        encoding="utf-8",
    )


def test_reference_corpus_normalizes_local_raw_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_private_fixture(tmp_path)

    service = ReferenceCorpusService()
    manifest = service.normalize_local_corpus()
    mitflit = service.search(q="Mitflit", category="creatures")

    assert manifest["categories"]
    assert mitflit[0]["id"] == "aon:creatures:245"
    assert mitflit[0]["summary_text"] == "Mitflits are gremlin pests"


def test_private_index_builds_indexes_and_dependency_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_private_fixture(tmp_path)
    ReferenceCorpusService().normalize_local_corpus()

    service = PrivateIndexService()
    manifest = service.build_all()
    dependency_index = json.loads(
        (tmp_path / "indexes" / "dependency-index.json").read_text(encoding="utf-8")
    )
    room_index = json.loads(
        (tmp_path / "indexes" / "room-index.json").read_text(encoding="utf-8")
    )

    assert manifest["counts"]["rooms"] == 1
    assert room_index["items"][0]["room_id"] == "A1"
    statuses = {
        item["name"]: item["resolution_status"]
        for item in dependency_index["items"]
    }
    assert statuses["Mitflit"] == "aon_resolved"
    assert statuses["Spear Launcher"] == "campaign_custom"
    assert statuses["Ghoul Fever"] == "aon_resolved"
    assert (tmp_path / "indexes" / "campaign-search.jsonl").exists()
    assert (tmp_path / "indexes" / "rag-documents.jsonl").exists()


def test_private_index_dependency_review_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_private_fixture(tmp_path)

    service = PrivateIndexService()
    service.build_all()
    missing = service.unresolved_dependencies()
    assert missing

    updated = service.update_dependency(missing[0]["id"], {"action": "ignore"})

    assert updated is not None
    assert updated["resolution_status"] == "ignored"
