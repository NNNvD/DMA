"""Copy/verify explicit private inputs into an isolated rehearsal, never live use."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "20260411_0003"
HEAD = "20261028_0007"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(root, campaign):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Private sources must not contain symlinks")
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts[0] == "campaigns" and (
            len(rel.parts) < 2 or rel.parts[1] != campaign
        ):
            continue
        result[rel.as_posix()] = sha(path)
    return result


def schema(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        names = [
            r[0]
            for r in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence')"
            )
        ]
        return {
            name: sorted(
                (r[1], r[2].upper(), r[3], r[5])
                for r in db.execute('PRAGMA table_info("' + name + '")')
            )
            for name in names
        }


def prepare(
    source_db,
    source_private,
    workspace,
    agent_python,
    campaign,
    session,
    resume_snapshot=False,
):
    source_db, source_private = (
        Path(source_db).absolute(),
        Path(source_private).absolute(),
    )
    workspace = Path(workspace).absolute()
    if (
        source_db.is_symlink()
        or source_private.is_symlink()
        or (workspace.exists() and not resume_snapshot)
        or (workspace / "REHEARSAL_READY.json").exists()
        or not workspace.resolve().is_relative_to((ROOT / ".codex-temp").resolve())
    ):
        raise ValueError(
            "Select real source paths and a new ignored .codex-temp workspace"
        )
    source_db, source_private = source_db.resolve(), source_private.resolve()
    if workspace.resolve().is_relative_to(
        source_private
    ) or source_private.is_relative_to(workspace.resolve()):
        raise ValueError("Source and rehearsal paths must be disjoint")
    if not Path(agent_python).is_file():
        raise ValueError("Select the installed isolated MCP Python")
    items = json.loads(
        (source_private / "campaigns" / campaign / "sessions.json").read_text(
            encoding="utf-8"
        )
    )["items"]
    selected = [item for item in items if item.get("id") == session]
    if len(selected) != 1:
        raise ValueError("Select one exact existing overlay session ID")
    before = inventory(source_private, campaign)
    db_hash = sha(source_db)
    snapshot = workspace / "snapshot"
    private_snapshot = snapshot / "private"
    if resume_snapshot:
        saved = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        if (
            saved["source_database"] != str(source_db)
            or saved["source_private"] != str(source_private)
            or saved["files"] != before
            or saved["database_sha256"] != sha(snapshot / "source.sqlite3")
        ):
            raise ValueError("Snapshot/source mismatch; use a fresh destination")
        with closing(
            sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True)
        ) as src, closing(
            sqlite3.connect(
                (snapshot / "source.sqlite3").as_uri() + "?mode=ro", uri=True
            )
        ) as saved_db:
            if list(src.iterdump()) != list(saved_db.iterdump()):
                raise ValueError("Source database changed since snapshot")
    else:
        private_snapshot.mkdir(parents=True)
        for rel in before:
            target = private_snapshot / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_private / rel, target)
        with closing(
            sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True)
        ) as src, closing(sqlite3.connect(snapshot / "source.sqlite3")) as dst:
            if src.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Source database integrity check failed")
            src.backup(dst)
    if (
        inventory(source_private, campaign) != before
        or sha(source_db) != db_hash
        or inventory(private_snapshot, campaign) != before
    ):
        raise ValueError(
            "Source changed during snapshot or copy verification failed; do not activate"
        )
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "source_database": str(source_db),
                "source_private": str(source_private),
                "database_sha256": sha(snapshot / "source.sqlite3"),
                "files": before,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    working = workspace / "rehearsal"
    private = (
        working / "local-private-overlay/project-root/assets/imports/misc/private-local"
    )
    if resume_snapshot:
        if inventory(private, campaign) != before:
            raise ValueError("Working overlay changed; do not resume this snapshot")
    else:
        shutil.copytree(private_snapshot, private)
    database = working / "database.sqlite3"
    if not resume_snapshot:
        shutil.copyfile(snapshot / "source.sqlite3", database)
    elif sha(database) != sha(snapshot / "source.sqlite3"):
        raise ValueError("Working database changed; do not resume this snapshot")
    env = {**os.environ, "EMBEDDING_PROVIDER": "disabled", "DEBUG": "false"}
    baseline = workspace / "baseline-schema.sqlite3"
    env["DATABASE_URL"] = "sqlite+aiosqlite:///" + baseline.as_posix()

    def alembic(*args):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    alembic("upgrade", BASELINE)
    if schema(database) != schema(baseline):
        raise ValueError(
            "Legacy schema does not exactly match inspected baseline; copied data retained, not activated"
        )
    env["DATABASE_URL"] = "sqlite+aiosqlite:///" + database.as_posix()
    alembic("stamp", BASELINE)
    alembic("upgrade", HEAD)
    identity = {
        "binding_id": "rehearsal-" + uuid4().hex,
        "campaign_id": campaign,
        "role": "gm",
        "recovery_epoch": uuid4().hex,
    }
    room_catalog = []
    for path in (private / "room-keys").rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if any(
            str(room.get("room_id", "")).casefold() == "c9"
            for room in payload.get("rooms", [])
        ):
            room_catalog.append(payload.get("map_id"))
    map_id = room_catalog[0] if len(room_catalog) == 1 else ""
    with closing(sqlite3.connect(database)) as db:
        if (
            db.execute("PRAGMA quick_check").fetchone() != ("ok",)
            or db.execute("PRAGMA foreign_key_check").fetchall()
        ):
            raise ValueError("Rehearsal database verification failed")
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO contexts(key,data,revision,updated_at) VALUES (?,?,1,?)",
            ("campaign-agent-binding", json.dumps(identity), now),
        )
        row = db.execute(
            "SELECT data FROM contexts WHERE key='live-session-state'"
        ).fetchone()
        state = json.loads(row[0]) if row else {}
        state["in_game_state"] = {
            "location_name": "Level 3 — C9",
            "map_id": map_id,
            "location_type": "underground",
        }
        state["combat_state"] = {
            "roomId": "C9",
            "round": 1,
            "activeIndex": 0,
            "combatants": [],
            "afflictions": [],
        }
        if row:
            db.execute(
                "UPDATE contexts SET data=?,revision=revision+1 WHERE key='live-session-state'",
                (json.dumps(state),),
            )
        else:
            db.execute(
                "INSERT INTO contexts(key,data,revision,updated_at) VALUES (?,?,1,?)",
                ("live-session-state", json.dumps(state), now),
            )
        db.commit()
    (private / ".dma-agent-binding.json").write_text(
        json.dumps(identity), encoding="utf-8"
    )
    links = {
        "campaign_id": campaign,
        "items": [
            {
                "id": session,
                "overlay_session_id": session,
                "draft_ids": [],
                "log_document_ids": [],
            }
        ],
    }
    (private / "campaigns" / campaign / "agent-session-links.json").write_text(
        json.dumps(links, indent=2), encoding="utf-8"
    )
    binding = workspace / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "format": "dma-agent-binding-v1",
                **identity,
                "schema_revision": HEAD,
                "database": database.relative_to(workspace).as_posix(),
                "private_root": private.relative_to(workspace).as_posix(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    agent_workspace = workspace / "campaign-workspace"
    agent_workspace.mkdir()
    shutil.copyfile(
        ROOT / "agent/campaign-review-agent.md", agent_workspace / "AGENTS.md"
    )
    from backend.agent.reader import TOOL_NAMES
    from backend.agent.gateway_client import REVIEW_TOOL_NAMES

    config = workspace / "codex-config.example.toml"
    config.write_text(
        'sandbox_mode="read-only"\nweb_search="disabled"\n[mcp_servers.dma_campaign]\ncommand='
        + json.dumps(Path(agent_python).resolve().as_posix())
        + "\nargs="
        + json.dumps(
            [
                "-m",
                "backend.agent.mcp_server",
                "--binding",
                binding.as_posix(),
                "--operator-python",
                Path(sys.executable).as_posix(),
            ]
        )
        + "\ncwd="
        + json.dumps(ROOT.as_posix())
        + "\nenabled_tools="
        + json.dumps(list(TOOL_NAMES + REVIEW_TOOL_NAMES))
        + '\nrequired=true\nstartup_timeout_sec=20\ntool_timeout_sec=40\n[mcp_servers.dma_campaign.tools.review_execute]\napproval_mode="approve"\n',
        encoding="utf-8",
    )
    onboarding = {
        "fixture_only": False,
        "mode": "private-rehearsal",
        "publication_enabled": False,
        "binding_file": str(binding),
        "database": str(database),
        "private_root": str(private),
        "source_database": str(source_db),
        "source_private": str(source_private),
        "agent_workspace": str(agent_workspace),
        "config_template": str(config),
        "session_id": session,
        "session_path": selected[0].get("path") or session,
        "map_id": map_id,
    }
    (workspace / "agent-onboarding.json").write_text(
        json.dumps(onboarding, indent=2), encoding="utf-8"
    )
    if inventory(source_private, campaign) != before or sha(source_db) != db_hash:
        raise ValueError("Source changed during preparation; activation withheld")
    ready = {
        "identity": identity,
        "database": str(database),
        "private_root": str(private),
        "source_database": str(source_db),
        "source_private": str(source_private),
        "source_unchanged": True,
        "snapshot_verified": True,
        "file_count": len(before),
    }
    (workspace / "REHEARSAL_READY.json").write_text(
        json.dumps(ready, indent=2), encoding="utf-8"
    )
    return {
        "workspace": str(workspace),
        "binding": str(binding),
        "source_unchanged": True,
        "files_verified": len(before),
        "session": session,
        "map_id": map_id,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--resume-snapshot", action="store_true")
    for key in (
        "source-db",
        "source-private",
        "workspace",
        "agent-python",
        "campaign",
        "session",
    ):
        p.add_argument("--" + key, required=True)
    a = p.parse_args()
    print(
        json.dumps(
            prepare(
                a.source_db,
                a.source_private,
                a.workspace,
                a.agent_python,
                a.campaign,
                a.session,
                a.resume_snapshot,
            ),
            indent=2,
        )
    )
