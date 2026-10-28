import json
import sqlite3
import sys

import pytest

from scripts.rehearse_campaign_recovery import (
    restore_fixture_pair,
    run_rehearsal,
    snapshot_fixture_pair,
)


def _fixture_pair(tmp_path):
    database = tmp_path / "source.sqlite3"
    overlay = tmp_path / "source-overlay"
    campaign = overlay / "assets/imports/misc/private-local/campaigns/fixture-recovery"
    campaign.mkdir(parents=True)
    identity = {
        "fixture_only": True,
        "campaign_id": "fixture-recovery",
        "session_id": "fixture-session-1",
        "recovery_set_id": "test-pair-1",
    }
    (campaign / "sessions.json").write_text(json.dumps(identity), encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE contexts (key TEXT, data TEXT)")
        connection.execute(
            "INSERT INTO contexts VALUES (?, ?)",
            ("w0-recovery-set", json.dumps(identity)),
        )
    return database, overlay


def test_pair_snapshot_captures_wal_and_restores_both_stores(tmp_path):
    database, overlay = _fixture_pair(tmp_path)
    bundle = tmp_path / "snapshot"
    restored = tmp_path / "restored"
    # Keep the WAL connection open: copying only the main DB file loses this row.
    with sqlite3.connect(database) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE facts (value TEXT)")
        writer.execute("INSERT INTO facts VALUES ('Bridge repaired')")
        writer.commit()
        snapshot_fixture_pair(database, overlay, bundle)
    # Changes after the snapshot must not leak into the restored pair.
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE facts SET value='Later event'")
    restored_db, restored_overlay = restore_fixture_pair(bundle, restored)
    with sqlite3.connect(restored_db) as connection:
        assert (
            connection.execute("SELECT value FROM facts").fetchone()[0]
            == "Bridge repaired"
        )
    source_file = next(overlay.rglob("sessions.json"))
    restored_file = next(restored_overlay.rglob("sessions.json"))
    assert restored_file.read_bytes() == source_file.read_bytes()
    assert (restored / "RESTORE_COMPLETE.json").is_file()


@pytest.mark.parametrize("damage", ["corrupt", "missing", "path_escape"])
def test_restore_rejects_damaged_bundle_before_creating_destination(tmp_path, damage):
    database, overlay = _fixture_pair(tmp_path)
    bundle = tmp_path / "snapshot"
    snapshot_fixture_pair(database, overlay, bundle)
    member = next((bundle / "local-private-overlay").rglob("sessions.json"))
    if damage == "corrupt":
        member.write_text("{}", encoding="utf-8")
    elif damage == "missing":
        member.unlink()
    else:
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["../outside"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    destination = tmp_path / "restored"
    with pytest.raises(ValueError):
        restore_fixture_pair(bundle, destination)
    assert not destination.exists()


def test_restore_refuses_existing_destination_and_preserves_original(tmp_path):
    database, overlay = _fixture_pair(tmp_path)
    bundle = tmp_path / "snapshot"
    snapshot_fixture_pair(database, overlay, bundle)
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("retain me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        restore_fixture_pair(bundle, destination)
    assert sentinel.read_text(encoding="utf-8") == "retain me"


def test_snapshot_refuses_mismatched_sql_and_overlay_identity(tmp_path):
    database, overlay = _fixture_pair(tmp_path)
    session_file = next(overlay.rglob("sessions.json"))
    payload = json.loads(session_file.read_text(encoding="utf-8"))
    payload["recovery_set_id"] = "different-pair"
    session_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        snapshot_fixture_pair(database, overlay, tmp_path / "snapshot")


def test_rehearsal_refuses_preloaded_backend_settings(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "backend.config.settings", object())
    workspace = tmp_path / "must-not-create"
    with pytest.raises(RuntimeError, match="fresh Python subprocess"):
        run_rehearsal(workspace)
    assert not workspace.exists()
