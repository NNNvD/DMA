"""Rehearse a paired SQL/overlay recovery using generated fictional data only.

This command has no live database or overlay input. It creates a new workspace,
retains every intermediate copy, and never restores over an existing directory.
Run from the repository: python -m scripts.rehearse_campaign_recovery
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import sys
import tempfile
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ID = "fixture-recovery"
OVERLAY_NAME = "local-private-overlay/project-root"
PRIVATE_CHILD = "assets/imports/misc/private-local"
SESSION_FILE = f"{PRIVATE_CHILD}/campaigns/{CAMPAIGN_ID}/sessions.json"
FORMAT = "dma-paired-fixture-v1"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, check: str) -> None:
    if not condition:
        raise RuntimeError(f"Recovery verification failed: {check}")


def _readonly(database: Path):
    return sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)


def _identity(database: Path, overlay: Path) -> dict:
    try:
        with closing(_readonly(database)) as connection:
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Fixture database integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("Fixture database foreign-key check failed")
            row = connection.execute(
                "SELECT data FROM contexts WHERE key='w0-recovery-set'"
            ).fetchone()
        sql_identity = json.loads(row[0]) if row else {}
        if (
            not isinstance(sql_identity, dict)
            or sql_identity.get("fixture_only") is not True
        ):
            raise ValueError("Database is not marked as a generated fixture")
        overlay_identity = json.loads(
            (overlay / SESSION_FILE).read_text(encoding="utf-8")
        )
        if not isinstance(overlay_identity, dict):
            raise ValueError("Overlay fixture identity is invalid")
    except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
        raise ValueError("Cannot read paired fixture identity") from exc
    fields = ("fixture_only", "campaign_id", "session_id", "recovery_set_id")
    identity = {key: sql_identity.get(key) for key in fields}
    if (
        identity["fixture_only"] is not True
        or identity["campaign_id"] != CAMPAIGN_ID
        or not identity["session_id"]
        or not identity["recovery_set_id"]
        or identity != {key: overlay_identity.get(key) for key in fields}
    ):
        raise ValueError("SQL and overlay fixture identity must match")
    return identity


def snapshot_fixture_pair(database: Path, overlay: Path, bundle: Path) -> dict:
    """Snapshot an explicitly marked fictional pair with writers quiesced."""
    if bundle.resolve().is_relative_to(overlay.resolve()):
        raise ValueError("Fixture snapshot must be outside the source overlay")
    if database.is_symlink() or overlay.is_symlink():
        raise ValueError("Fixture inputs must not be symlinks")
    members = sorted(overlay.rglob("*"))
    if any(path.is_symlink() for path in members):
        raise ValueError("Fixture overlay must not contain symlinks")
    identity = _identity(database, overlay)
    bundle.mkdir(parents=True, exist_ok=False)
    # SQLite backup includes committed WAL content; copying just the DB does not.
    with closing(_readonly(database)) as source, closing(
        sqlite3.connect(bundle / "database.sqlite3")
    ) as target:
        source.backup(target)
        target.commit()
        target.execute("PRAGMA journal_mode=DELETE")
    shutil.copytree(overlay, bundle / OVERLAY_NAME)
    if _identity(bundle / "database.sqlite3", bundle / OVERLAY_NAME) != identity:
        raise ValueError("Snapshot pair identity changed during copy")
    files = {"database.sqlite3": _digest(bundle / "database.sqlite3")}
    files.update(
        {
            path.relative_to(bundle).as_posix(): _digest(path)
            for path in sorted((bundle / OVERLAY_NAME).rglob("*"))
            if path.is_file()
        }
    )
    manifest = {"format": FORMAT, "identity": identity, "files": files}
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def restore_fixture_pair(bundle: Path, destination: Path) -> tuple[Path, Path]:
    """Validate the complete fixture bundle before restoring to a fresh target."""
    if destination.exists():
        raise FileExistsError("Restore destination must not already exist")
    try:
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Cannot read fixture snapshot manifest") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Unsupported fixture snapshot manifest")
    files = manifest.get("files")
    if manifest.get("format") != FORMAT or not isinstance(files, dict):
        raise ValueError("Unsupported fixture snapshot manifest")
    required = {"database.sqlite3", f"{OVERLAY_NAME}/{SESSION_FILE}"}
    if not required.issubset(files):
        raise ValueError("Fixture snapshot is missing paired store members")
    for relative, expected in files.items():
        parts = PurePosixPath(relative)
        if (
            parts.is_absolute()
            or ".." in parts.parts
            or "\\" in relative
            or ":" in relative
            or not (
                relative == "database.sqlite3"
                or relative.startswith(OVERLAY_NAME + "/")
            )
        ):
            raise ValueError("Invalid fixture snapshot member path")
        path = bundle / relative
        if (
            not path.resolve().is_relative_to(bundle.resolve())
            or path.is_symlink()
            or any(
                parent.is_symlink()
                for parent in path.parents
                if parent != bundle.parent
            )
            or not path.is_file()
            or _digest(path) != expected
        ):
            raise ValueError("Fixture snapshot member is missing, unsafe, or corrupt")
    identity = _identity(bundle / "database.sqlite3", bundle / OVERLAY_NAME)
    if identity != manifest.get("identity"):
        raise ValueError("Fixture snapshot manifest identity mismatch")
    destination.mkdir(parents=True, exist_ok=False)
    for relative, expected in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle / relative, target)
        if _digest(target) != expected:
            raise ValueError("Restored fixture member checksum mismatch")
    database, overlay = destination / "database.sqlite3", destination / OVERLAY_NAME
    if _identity(database, overlay) != identity:
        raise ValueError("Restored fixture pair identity mismatch")
    (destination / "RESTORE_COMPLETE.json").write_text(
        json.dumps({"identity": identity, "verified_members": len(files)}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return database, overlay


def _configure_fixture(database: Path, overlay: Path) -> None:
    # Set before importing backend settings. Never inherit real DB/overlay paths.
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + database.as_posix()
    os.environ["DMA_CAMPAIGN_ID"] = CAMPAIGN_ID
    os.environ["DMA_PRIVATE_DATA_ROOT"] = str(overlay / PRIVATE_CHILD)
    for key, suffix in (
        ("DUNGEON_MAP_ROOT", "media"),
        ("DUNGEON_ROOM_KEY_ROOT", "room-keys"),
        ("REFERENCE_PDF_ROOT", "reference/raw"),
        ("OBSIDIAN_VAULT_PATH", "legacy-disabled"),
    ):
        os.environ[key] = str(overlay / suffix)
    os.environ["EMBEDDING_PROVIDER"] = "disabled"


@contextmanager
def _fixture_api(database: Path, overlay: Path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from backend.api.routes.campaign import router as campaign_router
    from backend.api.routes.live import router as live_router
    from backend.api.routes.prep import router as prep_router
    from backend.config.settings import settings
    from backend.models.base import get_db

    settings.dma_private_data_root = str(overlay / PRIVATE_CHILD)
    engine = create_async_engine("sqlite+aiosqlite:///" + database.as_posix())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(campaign_router, prefix="/api/campaign")
    app.include_router(live_router, prefix="/api/live")
    app.include_router(prep_router, prefix="/api/prep")

    async def database_session():
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = database_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        asyncio.run(engine.dispose())


def _response(client, method: str, route: str, *, expected=200, **kwargs):
    response = client.request(method, route, **kwargs)
    if response.status_code != expected:
        raise RuntimeError(
            f"Fixture {method} {route}: {response.status_code}, expected {expected}"
        )
    return response.json()


def _draft(client, title: str, name: str, decision: str | None = None):
    draft = _response(
        client,
        "POST",
        "/api/campaign/session-update-drafts",
        expected=201,
        json={
            "title": title,
            "content": f"## Location: {name}\nSummary: Fictional reviewed observation\n",
        },
    )
    if decision:
        _response(
            client,
            "POST",
            f"/api/campaign/session-update-drafts/{draft['id']}/candidates/entity-0/decision",
            json={
                "decision": decision,
                "reason": "Fixture DM decision",
                "reviewer": "Fixture DM",
            },
        )
    return draft


def run_rehearsal(workspace: Path) -> dict:
    if "backend.config.settings" in sys.modules:
        raise RuntimeError("Run the fixture rehearsal in a fresh Python subprocess")
    workspace = workspace.resolve()
    for protected in (
        PROJECT_ROOT / "local-private-overlay",
        PROJECT_ROOT / "assets/imports",
        PROJECT_ROOT / ".git",
    ):
        if workspace.is_relative_to(protected.resolve()):
            raise ValueError(
                "Rehearsal workspace must be outside data and Git metadata roots"
            )
    workspace.mkdir(parents=True, exist_ok=False)
    source = workspace / "source"
    source.mkdir()
    database, overlay = source / "database.sqlite3", source / OVERLAY_NAME
    _configure_fixture(database, overlay)
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    expected_schema = ScriptDirectory.from_config(config).get_current_head()
    command.upgrade(config, "head")
    identity = {
        "fixture_only": True,
        "campaign_id": CAMPAIGN_ID,
        "session_id": "fixture-session-1",
        "recovery_set_id": str(uuid4()),
    }
    campaign = overlay / PRIVATE_CHILD / "campaigns" / CAMPAIGN_ID
    campaign.mkdir(parents=True)
    session_payload = {
        **identity,
        "items": [
            {
                "id": "fixture-session-1",
                "title": "Bridge session",
                "body_markdown": "GM-only fictional lighthouse secret",
            }
        ],
    }
    (campaign / "sessions.json").write_text(
        json.dumps(session_payload), encoding="utf-8"
    )
    (campaign / "settlements.json").write_text(
        json.dumps(
            {
                "campaign_id": CAMPAIGN_ID,
                "items": [{"id": "harborpost", "name": "Harborpost"}],
            }
        ),
        encoding="utf-8",
    )
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "INSERT INTO contexts (key,data,revision,updated_at) VALUES (?,?,?,?)",
            (
                "w0-recovery-set",
                json.dumps(identity),
                1,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()
    with _fixture_api(database, overlay) as client:
        entity = _response(
            client,
            "POST",
            "/api/campaign/entities",
            json={
                "entity_type": "location",
                "name": "Harborpost",
                "summary": "Before the session",
            },
        )
        approved = _draft(client, "Approved bridge session", "Harborpost", "accepted")
        _response(
            client,
            "POST",
            f"/api/campaign/session-update-drafts/{approved['id']}/promote",
        )
        _response(
            client,
            "POST",
            f"/api/campaign/session-update-drafts/{approved['id']}/finalize",
            json={"decision": "approved"},
        )
        rejected = _draft(client, "Rejected rumour", "False Harbour", "rejected")
        _response(
            client,
            "POST",
            f"/api/campaign/session-update-drafts/{rejected['id']}/finalize",
            json={"decision": "rejected", "reason": "Unverified rumour"},
        )
        deferred = _draft(client, "Deferred uncertainty", "Mist Tower", "deferred")
        pending = _draft(client, "Pending review", "Unseen Ferry")
        conflict = _draft(client, "Conflict recovery", "Harborpost", "accepted")
        saved = _response(
            client,
            "PUT",
            "/api/live/session-state",
            json={
                "expected_revision": 0,
                "scene_title": "Lantern Bridge",
                "current_location_id": entity["id"],
                "notes": "Fixture GM reminder",
            },
        )
    bundle = workspace / "snapshot"
    manifest = snapshot_fixture_pair(database, overlay, bundle)
    with _fixture_api(database, overlay) as client:
        later = _response(
            client,
            "PUT",
            "/api/live/session-state",
            json={
                "expected_revision": saved["revision"],
                "scene_title": "Unsnapshotted later scene",
            },
        )
    (campaign / "sessions.json").write_text(
        json.dumps({**session_payload, "changed_after_snapshot": True}),
        encoding="utf-8",
    )
    restored_db, restored_overlay = restore_fixture_pair(bundle, workspace / "restored")
    checks = []
    with closing(_readonly(restored_db)) as connection:
        schema_revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
    _require(schema_revision == expected_schema, "restored schema revision")
    checks.append("database_schema_and_integrity_restored")
    with _fixture_api(restored_db, restored_overlay) as client:
        live = _response(client, "GET", "/api/live/session-state")
        _require(live["state"]["scene_title"] == "Lantern Bridge", "live scene")
        _require(live["revision"] == saved["revision"], "live revision")
        checks.append("live_state_and_revision_restored")
        _require(
            json.loads((restored_overlay / SESSION_FILE).read_text())
            == session_payload,
            "overlay session content",
        )
        _require(
            (
                restored_overlay
                / PRIVATE_CHILD
                / "campaigns"
                / CAMPAIGN_ID
                / "settlements.json"
            ).read_bytes()
            == (campaign / "settlements.json").read_bytes(),
            "campaign-relative settlement data",
        )
        checks.append("paired_overlay_and_settlement_paths_restored")
        _require(
            _response(client, "GET", "/api/campaign/entities")["total"] == 1,
            "accepted entity set",
        )
        for draft, expected_decision in [(deferred, "deferred"), (pending, None)]:
            current = _response(
                client, "GET", f"/api/campaign/session-update-drafts/{draft['id']}"
            )
            _require(
                current["decisions"].get("entity-0", {}).get("decision")
                == expected_decision,
                "retained candidate decision",
            )
        history = _response(client, "GET", "/api/campaign/session-history")
        _require(
            history["total"] == 1
            and history["items"][0]["title"] == "Approved bridge session",
            "approved history only",
        )
        prep = _response(
            client, "POST", "/api/prep/session-brief", json={"store_document": False}
        )
        _require(
            [item["title"] for item in prep["recent_sessions"]]
            == ["Approved bridge session"],
            "prep history eligibility",
        )
        checks.append("only_accepted_facts_and_approved_history_reach_prep")
        provenance = _response(
            client, "GET", f"/api/campaign/entities/{entity['id']}/provenance"
        )
        _require(
            len(provenance) == 1 and provenance[0]["draft_id"] == approved["id"],
            "retained provenance",
        )
        _response(
            client,
            "POST",
            f"/api/campaign/session-update-drafts/{approved['id']}/promote",
        )
        _require(
            _response(
                client, "GET", f"/api/campaign/entities/{entity['id']}/provenance"
            )
            == provenance,
            "idempotent promotion retry",
        )
        checks.append("provenance_and_idempotent_retry_survive_restore")
        _response(
            client,
            "PUT",
            "/api/live/session-state",
            expected=409,
            json={
                "expected_revision": later["revision"],
                "scene_title": "Stale client overwrite",
            },
        )
        _require(
            _response(client, "GET", "/api/live/session-state")["state"]
            == live["state"],
            "stale save leaves live state unchanged",
        )
        _response(
            client,
            "PUT",
            "/api/live/session-state",
            json={
                "expected_revision": live["revision"],
                "scene_title": "Reconciled scene",
            },
        )
        checks.append("stale_live_write_rejected_and_fresh_save_succeeds")
        _response(
            client,
            "PATCH",
            f"/api/campaign/entities/{entity['id']}",
            json={"summary": "New DM edit after restore"},
        )
        _response(
            client,
            "POST",
            f"/api/campaign/session-update-drafts/{conflict['id']}/promote",
            expected=409,
        )
        _require(
            _response(client, "GET", f"/api/campaign/entities/{entity['id']}")[
                "summary"
            ]
            == "New DM edit after restore",
            "conflict leaves newer entity unchanged",
        )
        _require(
            len(
                _response(
                    client, "GET", f"/api/campaign/entities/{entity['id']}/provenance"
                )
            )
            == 1,
            "conflict leaves provenance unchanged",
        )
        checks.append("stale_candidate_baseline_preserves_newer_fact")
    report = {
        "fixture_only": True,
        "workspace": str(workspace),
        "identity": identity,
        "verified_members": len(manifest["files"]),
        "schema_revision": schema_revision,
        "checks": checks,
        "limitations": [
            "quiesced fixture stores, not a live backup tool",
            "reopen clients and discard cached approvals after any restore",
        ],
    }
    (workspace / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        help="New, non-existing output directory; default is a fresh temp workspace",
    )
    args = parser.parse_args()
    workspace = (
        args.workspace or Path(tempfile.mkdtemp(prefix="dma-recovery-")) / "rehearsal"
    )
    print(json.dumps(run_rehearsal(workspace), indent=2))


if __name__ == "__main__":
    main()
