"""Small synthetic reader-schema fixture; not a full DMA application database."""

import json
from pathlib import Path
import sqlite3


def make_reader_fixture(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    private = root / "private"
    campaign = private / "campaigns/fixture-campaign"
    campaign.mkdir(parents=True)
    marker = {
        "binding_id": "fixture-binding",
        "campaign_id": "fixture-campaign",
        "recovery_epoch": "fixture-epoch-1",
        "role": "gm",
    }
    (private / ".dma-agent-binding.json").write_text(
        json.dumps(marker), encoding="utf-8"
    )
    for filename, payload in {
        "sessions.json": {
            "items": [
                {
                    "id": "notes-1",
                    "title": "Lantern session",
                    "body_markdown": "Fictional GM-only bridge note.",
                }
            ]
        },
        "npcs.json": {
            "items": [
                {
                    "id": 42,
                    "name": "Overlay Keeper",
                    "details": {"appearance_description": "Blue cloak"},
                }
            ]
        },
        "agent-session-links.json": {
            "items": [
                {
                    "id": "session-1",
                    "overlay_session_id": "notes-1",
                    "draft_ids": [7],
                    "log_document_ids": [3],
                }
            ]
        },
    }.items():
        (campaign / filename).write_text(
            json.dumps({"campaign_id": marker["campaign_id"], **payload}),
            encoding="utf-8",
        )
    database = root / "campaign.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript(
            """
            CREATE TABLE alembic_version (version_num TEXT);
            INSERT INTO alembic_version VALUES ('20261007_0006');
            CREATE TABLE contexts (key TEXT, data TEXT, revision INTEGER, updated_at TEXT);
            CREATE TABLE campaign_entities (id INTEGER, stable_key TEXT, entity_type TEXT, name TEXT, summary TEXT, details TEXT, updated_at TEXT);
            INSERT INTO campaign_entities VALUES (42,'LOC-0042','location','SQL Bridge','Accepted bridge fact','{}','2026-10-27T10:00:00');
            CREATE TABLE documents (id INTEGER, kind TEXT, title TEXT, content TEXT, summary TEXT, source_name TEXT, review_status TEXT, visibility_scope TEXT, rag_eligible INTEGER, updated_at TEXT);
            INSERT INTO documents VALUES (3,'session_log','Approved bridge log','Bridge repaired.','Accepted outcome','fixture','approved','gm_only',1,'2026-10-27T10:00:00');
            INSERT INTO documents VALUES (4,'session_log','Rejected log','Unconfirmed','Do not use','fixture','rejected','gm_only',1,'2026-10-27T10:00:00');
            INSERT INTO documents VALUES (5,'session_log','Pending log','Unconfirmed','Do not use','fixture','pending','gm_only',1,'2026-10-27T10:00:00');
            CREATE TABLE session_update_drafts (id INTEGER, campaign_id TEXT, title TEXT, content TEXT, source_hash TEXT, revision INTEGER, status TEXT, candidates TEXT, decisions TEXT, session_log_document_id INTEGER, session_log_decision TEXT);
            INSERT INTO session_update_drafts VALUES (7,'fixture-campaign','Bridge review','Fictional source','abc123',2,'pending','[]','{}',NULL,'pending');
            CREATE TABLE campaign_entity_provenance (id INTEGER, entity_id INTEGER, draft_id INTEGER, candidate_id TEXT, source_hash TEXT, candidate_payload TEXT);
            INSERT INTO campaign_entity_provenance VALUES (1,42,7,'entity-0','abc123','{}');
        """
        )
        db.execute(
            "INSERT INTO contexts VALUES (?,?,?,?)",
            ("campaign-agent-binding", json.dumps(marker), 1, "2026-10-27T10:00:00"),
        )
        db.execute(
            "INSERT INTO contexts VALUES (?,?,?,?)",
            (
                "live-session-state",
                json.dumps(
                    {
                        "scene_title": "Lantern Bridge",
                        "combat_state": {"combatants": []},
                    }
                ),
                9,
                "2026-10-27T10:00:00",
            ),
        )
    binding = root / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "format": "dma-agent-binding-v1",
                **marker,
                "database": "campaign.sqlite3",
                "private_root": "private",
                "schema_revision": "20261007_0006",
            }
        ),
        encoding="utf-8",
    )
    return binding, database, private
