import hashlib
import json
import sqlite3

import pytest

from backend.agent.reader import AgentReadError, CampaignReader, TOOL_NAMES
from tests.support.campaign_agent_fixtures import make_reader_fixture


def test_bound_reads_are_citable_and_do_not_modify_sources(tmp_path):
    binding, database, private = make_reader_fixture(tmp_path)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    reader = CampaignReader(binding)
    assert (
        reader.call("campaign_describe", {})["data"]["campaign_id"]
        == "fixture-campaign"
    )
    entity = reader.call("campaign_read_entities", {"entity_id": 42})
    assert entity["data"][0]["name"] == "SQL Bridge"
    assert entity["sources"][0]["citation"].startswith("dma://fixture-binding/")
    assert entity["sources"][0]["store"] == "sql"
    assert entity["sources"][0]["updated_at"]
    assert reader.call("session_read_live", {})["data"]["revision"] == 9
    assert (
        reader.call("session_read_review", {"draft_id": 7})["data"][0]["source_hash"]
        == "abc123"
    )
    assert len(reader.call("campaign_read_provenance", {"entity_id": 42})["data"]) == 1
    assert reader.call("campaign_read_sessions", {})["data"][0]["id"] == "session-1"
    assert len(TOOL_NAMES) == 8
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before} == before
    # Fresh conversations reconstruct the same references from saved records.
    assert (
        CampaignReader(binding).call("campaign_read_entities", {"entity_id": 42})
        == entity
    )


def test_store_namespace_and_review_eligibility_are_preserved(tmp_path):
    binding, _, _ = make_reader_fixture(tmp_path)
    reader = CampaignReader(binding)
    history = reader.call("campaign_read_history", {})
    assert [row["id"] for row in history["data"]] == [3]
    overlay = reader.call("campaign_read_notes", {"note_type": "npc", "item_id": "42"})
    assert overlay["data"]["name"] == "Overlay Keeper"
    assert overlay["sources"][0]["store"] == "overlay"
    assert overlay["sources"][0]["content_sha256"]
    assert (
        reader.call("campaign_read_entities", {"entity_id": 42})["data"][0]["name"]
        == "SQL Bridge"
    )


@pytest.mark.parametrize(
    "name,args",
    [
        ("review_promote", {"draft_id": 7}),
        ("execute_sql", {"sql": "DELETE FROM campaign_entities"}),
        ("campaign_read_entities", {"database": "/another.db"}),
        ("campaign_read_notes", {"note_type": "../../.env", "item_id": "42"}),
        ("campaign_read_entities", {"limit": 100000}),
    ],
)
def test_unavailable_writes_and_unbounded_arguments_are_rejected(tmp_path, name, args):
    binding, database, _ = make_reader_fixture(tmp_path)
    reader = CampaignReader(binding)
    with pytest.raises(AgentReadError):
        reader.call(name, args)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM campaign_entities").fetchone()[0] == 1


@pytest.mark.parametrize("damage", ["player_role", "schema", "epoch", "foreign_draft"])
def test_binding_guard_is_rechecked_on_each_call(tmp_path, damage):
    binding, database, private = make_reader_fixture(tmp_path)
    reader = CampaignReader(binding)
    if damage in {"epoch", "player_role"}:
        marker_path = private / ".dma-agent-binding.json"
        marker = json.loads(marker_path.read_text())
        marker["role" if damage == "player_role" else "recovery_epoch"] = "changed"
        marker_path.write_text(json.dumps(marker))
    else:
        with sqlite3.connect(database) as db:
            if damage == "schema":
                db.execute("UPDATE alembic_version SET version_num='unknown'")
            else:
                db.execute(
                    "UPDATE session_update_drafts SET campaign_id='another-campaign'"
                )
    with pytest.raises(AgentReadError, match="binding"):
        reader.call("campaign_read_entities", {})


def test_missing_and_invalid_overlay_records_never_fall_back(tmp_path):
    binding, _, private = make_reader_fixture(tmp_path)
    reader = CampaignReader(binding)
    path = private / "campaigns/fixture-campaign/npcs.json"
    path.unlink()
    assert (
        reader.call("campaign_read_notes", {"note_type": "npc", "item_id": "42"})[
            "status"
        ]
        == "missing"
    )
    assert not path.exists()
    path.write_text("{bad json")
    with pytest.raises(AgentReadError, match="source"):
        reader.call("campaign_read_notes", {"note_type": "npc", "item_id": "42"})
    path.write_text(json.dumps({"campaign_id": "wrong", "items": []}))
    with pytest.raises(AgentReadError):
        reader.call("campaign_read_notes", {"note_type": "npc", "item_id": "42"})


def test_sqlite_connection_itself_is_read_only(tmp_path):
    binding, _, _ = make_reader_fixture(tmp_path)
    with CampaignReader(binding)._connection() as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("DELETE FROM campaign_entities")


def test_epoch_rotation_during_read_does_not_return_old_binding_result(
    tmp_path, monkeypatch
):
    binding, _, private = make_reader_fixture(tmp_path)
    reader = CampaignReader(binding)
    original = reader._campaign_read_entities

    def rotated(db, **kwargs):
        result = original(db, **kwargs)
        path = private / ".dma-agent-binding.json"
        payload = json.loads(path.read_text())
        payload["recovery_epoch"] = "new-epoch"
        path.write_text(json.dumps(payload))
        return result

    monkeypatch.setattr(reader, "_campaign_read_entities", rotated)
    with pytest.raises(AgentReadError, match="binding"):
        reader.call("campaign_read_entities", {})


def test_changed_fact_gets_new_content_citation_even_without_timestamp_update(tmp_path):
    binding, database, _ = make_reader_fixture(tmp_path)
    reader = CampaignReader(binding)
    first = reader.call("campaign_read_entities", {"entity_id": 42})
    with sqlite3.connect(database) as db:
        db.execute("UPDATE campaign_entities SET summary='New DM observation'")
    second = reader.call("campaign_read_entities", {"entity_id": 42})
    assert first["sources"][0]["updated_at"] == second["sources"][0]["updated_at"]
    assert first["sources"][0]["citation"] != second["sources"][0]["citation"]


def test_saved_session_and_log_ids_resolve_beyond_the_listing_window(tmp_path):
    binding, _, private = make_reader_fixture(tmp_path)
    links_path = private / "campaigns/fixture-campaign/agent-session-links.json"
    links = json.loads(links_path.read_text())
    original = links["items"][0]
    links["items"] = [{"id": f"another-{index}"} for index in range(55)] + [original]
    links_path.write_text(json.dumps(links))
    reader = CampaignReader(binding)
    assert original not in reader.call("campaign_read_sessions", {"limit": 50})["data"]
    assert reader.call("campaign_read_sessions", {"session_id": "session-1"})[
        "data"
    ] == [original]
    assert (
        reader.call("campaign_read_history", {"document_id": 3})["data"][0]["id"] == 3
    )
    for excluded_id in (4, 5, 999):
        assert (
            reader.call("campaign_read_history", {"document_id": excluded_id})["status"]
            == "missing"
        )
