import json

import pytest

from backend.agent.reader import CampaignReader, AgentReadError
from tests.support.campaign_agent_fixtures import make_reader_fixture
from scripts import review_campaign_approval as operator


def test_material_catalog_and_exact_room_are_citable(tmp_path):
    binding, _, private = make_reader_fixture(tmp_path)
    folder = private / "room-keys"
    folder.mkdir()
    (folder / "rooms.json").write_text(
        json.dumps(
            {
                "campaign_id": "fixture-campaign",
                "map_id": "test-map",
                "rooms": [
                    {
                        "room_id": "R1",
                        "title": "Synthetic chamber",
                        "gm_notes": "Synthetic private detail",
                    }
                ],
            }
        )
    )
    reader = CampaignReader(binding)
    catalog = reader.call(
        "campaign_read_notes", {"note_type": "room", "item_id": "catalog"}
    )
    assert catalog["data"] == [{"id": "test-map/R1", "name": "Synthetic chamber"}]
    assert "private detail" not in str(catalog)
    room = reader.call(
        "campaign_read_notes", {"note_type": "room", "item_id": "test-map/R1"}
    )
    assert room["data"]["gm_notes"] == "Synthetic private detail"
    assert room["sources"][0]["file_sha256"]
    assert (
        reader.call("campaign_read_notes", {"note_type": "room", "item_id": "../R1"})[
            "status"
        ]
        == "missing"
    )


def test_material_rejects_foreign_campaign_and_ambiguous_ids(tmp_path):
    binding, _, private = make_reader_fixture(tmp_path)
    folder = private / "bestiary"
    folder.mkdir()
    payload = {
        "campaign_id": "foreign",
        "entries": [{"id": "test", "name": "Synthetic opponent"}],
    }
    (folder / "a.json").write_text(json.dumps(payload))
    reader = CampaignReader(binding)
    assert (
        reader.call(
            "campaign_read_notes", {"note_type": "bestiary", "item_id": "test"}
        )["status"]
        == "missing"
    )
    payload["campaign_id"] = "fixture-campaign"
    for name in ("a", "b"):
        (folder / (name + ".json")).write_text(json.dumps(payload))
    with pytest.raises(AgentReadError, match="Ambiguous"):
        reader.call("campaign_read_notes", {"note_type": "bestiary", "item_id": "test"})


def test_note_catalog_is_headers_only(tmp_path):
    binding, _, _ = make_reader_fixture(tmp_path)
    result = CampaignReader(binding).call(
        "campaign_read_notes", {"note_type": "session", "item_id": "catalog"}
    )
    assert result["data"]
    assert all(set(row) == {"id", "name"} for row in result["data"])


def test_private_rehearsal_marker_cannot_authorize_source_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(operator, "__file__", str(tmp_path / "scripts/operator.py"))
    workspace = tmp_path / ".codex-temp/rehearsal"
    workspace.mkdir(parents=True)
    binding, database, private = make_reader_fixture(workspace)
    value = json.loads(binding.read_text())
    value["binding_id"] = "rehearsal-test"
    binding.write_text(json.dumps(value))
    identity = {
        key: value[key]
        for key in ("binding_id", "campaign_id", "recovery_epoch", "role")
    }
    source_db = tmp_path / "live.db"
    source_private = tmp_path / "live-private"
    onboarding = {
        "mode": "private-rehearsal",
        "fixture_only": False,
        "publication_enabled": False,
        "binding_file": str(binding),
        "source_database": str(source_db),
        "source_private": str(source_private),
    }
    ready = {
        "identity": identity,
        "database": str(database),
        "private_root": str(private),
        "source_database": str(source_db),
        "source_private": str(source_private),
        "source_unchanged": True,
        "snapshot_verified": True,
    }
    (workspace / "agent-onboarding.json").write_text(json.dumps(onboarding))
    (workspace / "REHEARSAL_READY.json").write_text(json.dumps(ready))
    assert operator.fixture_binding(binding).binding_id == "rehearsal-test"
    onboarding["source_private"] = str(private)
    ready["source_private"] = str(private)
    (workspace / "agent-onboarding.json").write_text(json.dumps(onboarding))
    (workspace / "REHEARSAL_READY.json").write_text(json.dumps(ready))
    with pytest.raises(ValueError, match="live paths"):
        operator.fixture_binding(binding)
