from __future__ import annotations

import json

from backend.services.private_campaign_data_service import PrivateCampaignDataService


def test_private_campaign_data_service_loads_defaults_for_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        "private-local",
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    service = PrivateCampaignDataService(project_root=tmp_path)

    assert service.campaign_overview() == {
        "campaign_id": "test-campaign",
        "tabs": [],
    }
    assert service.session_items() == []
    assert service.pc_items() == []
    assert service.npc_items() == []


def test_private_campaign_data_service_writes_and_updates_campaign_note(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        "private-local",
    )
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_campaign_id",
        "test-campaign",
    )
    service = PrivateCampaignDataService(project_root=tmp_path)

    note = service.update_campaign_note("gm-summary", "# GM\n\nSecrets.", "GM Summary")

    assert note["source"] == "private-local"
    assert note["id"] == "gm-summary"
    assert note["content"] == "# GM\n\nSecrets.\n"
    path = tmp_path / "private-local" / "campaigns" / "test-campaign" / "campaign-overview.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["campaign_id"] == "test-campaign"
    assert payload["tabs"][0]["body_markdown"] == "# GM\n\nSecrets.\n"


def test_private_campaign_data_service_rejects_paths_outside_private_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.services.private_campaign_data_service.settings.dma_private_data_root",
        "private-local",
    )
    service = PrivateCampaignDataService(project_root=tmp_path)

    try:
        service.safe_child(service.private_root(), "../secret.txt")
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("Expected path traversal to be rejected")
