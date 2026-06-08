from __future__ import annotations

import json

import pytest

from backend.services.private_image_intake_service import PrivateImageIntakeService
from backend.services.private_index_service import PrivateIndexService


def _write_fixture_indexes(tmp_path):
    room_root = tmp_path / "room-keys" / "test-campaign"
    room_root.mkdir(parents=True)
    (room_root / "level-1.json").write_text(
        json.dumps(
            {
                "map_id": "level1",
                "rooms": [
                    {
                        "room_id": "A1",
                        "title": "Entry",
                        "player_visible_description": "A damp hall.",
                        "gm_description": "Korlok waits nearby.",
                        "npcs": ["Korlok"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    bestiary_root = tmp_path / "bestiary" / "test-campaign"
    bestiary_root.mkdir(parents=True)
    (bestiary_root / "level-1.json").write_text(
        json.dumps({"entries": [{"id": "korlok", "name": "Korlok", "entry_type": "creature"}]}),
        encoding="utf-8",
    )
    PrivateIndexService().build_all()


def test_image_candidate_uses_nearby_text_for_match(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_fixture_indexes(tmp_path)

    service = PrivateImageIntakeService()
    layout = {
        "pages": [
            {
                "page": 1,
                "text": "Korlok Creature 5",
                "blocks": [
                    {"bbox": [100, 90, 300, 120], "text": "Korlok"},
                ],
            }
        ]
    }
    image = {
        "id": "image:test:p001:i001",
        "source_id": "test",
        "page": 1,
        "private_path": "reference/extracted/test/images/page-001-image-001.png",
        "url": "/api/live/private-file?path=reference/extracted/test/images/page-001-image-001.png",
        "width": 400,
        "height": 600,
        "area": 240000,
        "bboxes": [[100, 130, 300, 500]],
        "sha256": "abc",
    }

    candidate = service._candidate_from_image(image, layout)

    assert candidate["category"] == "portrait_creature"
    assert candidate["confidence"] == "high"
    assert candidate["allocation_status"] == "ready_for_review"
    assert candidate["visual_features"]["flags"] == ["portrait_aspect"]
    assert candidate["proposed_matches"][0]["score"] == 5
    assert candidate["proposed_matches"][0]["entity_name"] == "Korlok"
    assert "nearby_caption_or_label_text" in candidate["proposed_matches"][0]["evidence"]


def test_image_candidate_uses_adjacent_page_as_weaker_match(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_fixture_indexes(tmp_path)

    service = PrivateImageIntakeService()
    layout = {
        "pages": [
            {"page": 1, "text": "Korlok Creature 5", "blocks": []},
            {
                "page": 2,
                "width": 600,
                "height": 800,
                "text": "A full-page portrait follows.",
                "blocks": [],
            },
        ]
    }
    image = {
        "id": "image:test:p002:i001",
        "source_id": "test",
        "page": 2,
        "private_path": "reference/extracted/test/images/page-002-image-001.png",
        "url": "/api/live/private-file?path=reference/extracted/test/images/page-002-image-001.png",
        "width": 400,
        "height": 600,
        "area": 240000,
        "bboxes": [[100, 100, 500, 760]],
        "sha256": "abc",
    }

    candidate = service._candidate_from_image(image, layout)

    assert candidate["confidence"] == "medium"
    assert candidate["allocation_status"] == "ready_for_review"
    assert candidate["proposed_matches"][0]["entity_name"] == "Korlok"
    assert candidate["proposed_matches"][0]["score"] == 2
    assert "adjacent_page_text_match" in candidate["proposed_matches"][0]["evidence"]


def test_image_candidate_classifies_chapter_art_and_duplicate_status():
    service = PrivateImageIntakeService()
    layout = {
        "pages": [
            {
                "page": 1,
                "width": 600,
                "height": 800,
                "text": "Chapter 2: Into the Vaults",
                "blocks": [],
            }
        ]
    }
    image = {
        "id": "image:test:p001:i001",
        "source_id": "test",
        "page": 1,
        "private_path": "reference/extracted/test/images/page-001-image-001.png",
        "url": "/api/live/private-file?path=reference/extracted/test/images/page-001-image-001.png",
        "width": 900,
        "height": 1200,
        "bboxes": [[0, 0, 600, 760]],
        "sha256": "abc",
    }

    candidate = service._candidate_from_image(image, layout)

    assert candidate["category"] == "cover_or_chapter_art"
    assert candidate["allocation_status"] == "needs_identification"
    assert "large_page_coverage" in candidate["visual_features"]["flags"]

    duplicate = service._candidate_from_image({**image, "duplicate": True}, layout)

    assert duplicate["category"] == "duplicate_or_variant"
    assert duplicate["allocation_status"] == "duplicate_review"


def test_image_review_and_promote_confirmed_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    _write_fixture_indexes(tmp_path)
    source_root = tmp_path / "reference" / "extracted" / "test-source"
    image_root = source_root / "images"
    image_root.mkdir(parents=True)
    (image_root / "page-001-image-001.png").write_bytes(b"fake")
    candidate = {
        "id": "image:test-source:p001:i001",
        "source_id": "test-source",
        "page": 1,
        "private_path": "reference/extracted/test-source/images/page-001-image-001.png",
        "url": "/api/live/private-file?path=reference/extracted/test-source/images/page-001-image-001.png",
        "category": "portrait_npc",
        "review_status": "unreviewed",
        "visibility": "copyright_private",
        "confidence": "high",
        "sha256": "abc",
        "proposed_matches": [
            {
                "entity_type": "creature",
                "entity_id": "bestiary:korlok",
                "entity_name": "Korlok",
                "evidence": ["nearby_caption_or_label_text"],
            }
        ],
    }
    (source_root / "image-candidates.json").write_text(
        json.dumps({"items": [candidate]}),
        encoding="utf-8",
    )

    service = PrivateImageIntakeService()
    updated = service.update_image_candidate(
        "image:test-source:p001:i001",
        {"review_status": "confirmed", "proposed_match": candidate["proposed_matches"][0]},
    )
    result = service.promote_confirmed_images()

    assert updated is not None
    assert updated["review_status"] == "confirmed"
    assert result["promoted_count"] == 1
    images = json.loads(
        (tmp_path / "campaigns" / "test-campaign" / "images.json").read_text(
            encoding="utf-8"
        )
    )
    assert images["items"][0]["entity_name"] == "Korlok"


def test_image_intake_reports_missing_source_pdfs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )

    service = PrivateImageIntakeService()

    with pytest.raises(ValueError, match="No source PDFs found"):
        service.create_image_intake_run()


def test_image_intake_run_list_deduplicates_multi_source_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        str(tmp_path),
    )
    extracted_root = tmp_path / "reference" / "extracted"
    for source_id in ["source-one", "source-two"]:
        source_root = extracted_root / source_id
        source_root.mkdir(parents=True)
        (source_root / "image-intake-run.json").write_text(
            json.dumps(
                {
                    "run_id": "20260606-000000",
                    "created_at": "2026-06-06T00:00:00+00:00",
                    "sources": [{"source_id": source_id}],
                }
            ),
            encoding="utf-8",
        )

    runs = PrivateImageIntakeService().list_image_runs()

    assert len(runs) == 1
    assert runs[0]["run_id"] == "20260606-000000"
