import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_rehearsal_uses_generated_pair_and_verifies_restarted_services(tmp_path):
    output = tmp_path / "rehearsal"
    env = os.environ.copy()
    # Deliberately supplied paths must never become the rehearsal's inputs.
    sentinel_db = tmp_path / "do-not-open.db"
    sentinel_overlay = tmp_path / "do-not-open-overlay"
    env["DATABASE_URL"] = "sqlite+aiosqlite:///" + sentinel_db.as_posix()
    env["DMA_PRIVATE_DATA_ROOT"] = str(sentinel_overlay)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.rehearse_campaign_recovery",
            "--workspace",
            str(output),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["fixture_only"] is True
    assert report["schema_revision"] == "20261028_0007"
    assert set(report["checks"]) == {
        "database_schema_and_integrity_restored",
        "live_state_and_revision_restored",
        "paired_overlay_and_settlement_paths_restored",
        "only_accepted_facts_and_approved_history_reach_prep",
        "provenance_and_idempotent_retry_survive_restore",
        "stale_live_write_rejected_and_fresh_save_succeeds",
        "stale_candidate_baseline_preserves_newer_fact",
    }
    assert (output / "snapshot/manifest.json").is_file()
    assert (output / "restored/RESTORE_COMPLETE.json").is_file()
    assert not sentinel_db.exists()
    assert not sentinel_overlay.exists()


def test_rehearsal_refuses_to_reuse_existing_workspace(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.rehearse_campaign_recovery",
            "--workspace",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
    assert list(output.iterdir()) == [sentinel]
