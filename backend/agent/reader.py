"""Read-only, explicitly bound campaign data access. No backend settings imports."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
from urllib.parse import quote


SUPPORTED_SCHEMA = "20261007_0006"
SUPPORTED_SCHEMAS = {SUPPORTED_SCHEMA, "20261028_0007"}
IDENTITY_FIELDS = ("binding_id", "campaign_id", "recovery_epoch", "role")
TOOL_NAMES = (
    "campaign_describe",
    "campaign_read_entities",
    "campaign_read_history",
    "campaign_read_provenance",
    "campaign_read_notes",
    "campaign_read_sessions",
    "session_read_live",
    "session_read_review",
)
NOTE_FILES = {
    "campaign_overview": ("campaign-overview.json", "tabs"),
    "session": ("sessions.json", "items"),
    "npc": ("npcs.json", "items"),
    "pc": ("pcs.json", "items"),
    "settlement": ("settlements.json", "items"),
}
JSON_FIELDS = {
    "details",
    "tags",
    "data",
    "candidates",
    "decisions",
    "candidate_payload",
    "default_tags",
}


class AgentReadError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _json_file(path: Path) -> tuple[dict, str]:
    try:
        # Bound results and avoid loading arbitrary-sized files into model context.
        with path.open("rb") as handle:
            content = handle.read(1_000_001)
        if len(content) > 1_000_000:
            raise AgentReadError(
                "source_unavailable", "Selected source exceeds the reader size limit"
            )
        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("Expected JSON object")
        return payload, hashlib.sha256(content).hexdigest()
    except FileNotFoundError as exc:
        raise AgentReadError(
            "source_missing", "Selected source does not exist"
        ) from exc
    except (OSError, ValueError) as exc:
        raise AgentReadError(
            "source_invalid", "Selected source cannot be read as valid JSON"
        ) from exc


@dataclass(frozen=True)
class CampaignBinding:
    binding_id: str
    campaign_id: str
    recovery_epoch: str
    role: str
    schema_revision: str
    database: Path
    private_root: Path

    @property
    def identity(self) -> dict:
        return {key: getattr(self, key) for key in IDENTITY_FIELDS}

    @classmethod
    def load(cls, filename: Path) -> CampaignBinding:
        filename = filename.resolve()
        payload, _ = _json_file(filename)
        required = {
            "format",
            *IDENTITY_FIELDS,
            "schema_revision",
            "database",
            "private_root",
        }
        if set(payload) != required or payload.get("format") != "dma-agent-binding-v1":
            raise AgentReadError(
                "binding_invalid", "Unsupported campaign binding manifest"
            )
        if (
            payload["role"] != "gm"
            or not isinstance(payload["schema_revision"], str)
            or payload["schema_revision"] not in SUPPORTED_SCHEMAS
            or not isinstance(payload["binding_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", payload["binding_id"])
            or not isinstance(payload["campaign_id"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", payload["campaign_id"])
            or not isinstance(payload["recovery_epoch"], str)
            or not 1 <= len(payload["recovery_epoch"]) <= 128
        ):
            raise AgentReadError(
                "binding_invalid",
                "Campaign binding identity, role, or schema is invalid",
            )
        paths = {}
        for key in ("database", "private_root"):
            if not isinstance(payload[key], str) or not payload[key]:
                raise AgentReadError(
                    "binding_invalid", "Explicit source paths are required"
                )
            candidate = filename.parent / payload[key]
            if candidate.is_symlink():
                raise AgentReadError(
                    "binding_invalid", "Bound source must not be a symlink"
                )
            paths[key] = candidate.resolve()
        if not paths["database"].is_file() or not paths["private_root"].is_dir():
            raise AgentReadError(
                "binding_invalid", "Bound database or private root is unavailable"
            )
        return cls(
            **{key: payload[key] for key in (*IDENTITY_FIELDS, "schema_revision")},
            **paths,
        )


class CampaignReader:
    def __init__(self, binding_file: Path):
        self.binding = CampaignBinding.load(binding_file)
        with self._connection():
            pass

    def _private_path(self, relative: str) -> Path:
        root = self.binding.private_root
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise AgentReadError(
                "source_denied", "Selected source escapes the bound root"
            )
        current = path
        while current != root:
            if current.is_symlink():
                raise AgentReadError(
                    "source_denied", "Selected source contains a symlink"
                )
            current = current.parent
        if root.is_symlink():
            raise AgentReadError("binding_mismatch", "Bound root changed")
        return path

    @contextmanager
    def _connection(self):
        connection = None
        try:
            if self.binding.database.is_symlink():
                raise AgentReadError("binding_mismatch", "Bound database changed")
            identity_before = self.binding.database.stat()
            connection = sqlite3.connect(
                self.binding.database.as_uri() + "?mode=ro", uri=True
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            versions = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchall()
            row = connection.execute(
                "SELECT data FROM contexts WHERE key='campaign-agent-binding'"
            ).fetchone()
            try:
                sql_identity = json.loads(row[0]) if row else {}
                overlay_identity, _ = _json_file(
                    self._private_path(".dma-agent-binding.json")
                )
            except (ValueError, AgentReadError) as exc:
                raise AgentReadError(
                    "binding_mismatch", "Campaign binding identity is unavailable"
                ) from exc
            foreign = connection.execute(
                "SELECT 1 FROM session_update_drafts WHERE campaign_id IS NULL OR campaign_id != ? LIMIT 1",
                (self.binding.campaign_id,),
            ).fetchone()
            if (
                len(versions) != 1
                or versions[0][0] != self.binding.schema_revision
                or sql_identity != self.binding.identity
                or overlay_identity != self.binding.identity
                or foreign is not None
            ):
                raise AgentReadError(
                    "binding_mismatch",
                    "Campaign binding identity, epoch, or schema changed",
                )
            yield connection
            overlay_after, _ = _json_file(self._private_path(".dma-agent-binding.json"))
            identity_after = self.binding.database.stat()
            if overlay_after != self.binding.identity or (
                identity_before.st_dev,
                identity_before.st_ino,
            ) != (identity_after.st_dev, identity_after.st_ino):
                raise AgentReadError(
                    "binding_mismatch", "Campaign binding changed during the read"
                )
        except sqlite3.Error as exc:
            raise AgentReadError(
                "binding_unavailable",
                "Bound database source is unavailable or incompatible",
            ) from exc
        except OSError as exc:
            raise AgentReadError(
                "binding_unavailable", "Bound source is unavailable"
            ) from exc
        finally:
            if connection is not None:
                connection.rollback()
                connection.close()

    def _result(self, data: Any, sources: list[dict]) -> dict:
        if len(json.dumps(data, ensure_ascii=False).encode()) > 500_000:
            raise AgentReadError(
                "source_unavailable", "Selected result exceeds the reader size limit"
            )
        return {
            "status": "missing" if data is None or data == [] else "ok",
            **self.binding.identity,
            "audience": "gm_only",
            "sources": sources,
            "data": data,
        }

    def _source(
        self, store: str, kind: str, identifier: Any, payload: dict, **metadata
    ) -> dict:
        digest = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        source = {
            "campaign_id": self.binding.campaign_id,
            "store": store,
            "kind": kind,
            "id": identifier,
            "content_sha256": digest,
            **metadata,
        }
        token = source.get("file_sha256", digest)
        source["citation"] = (
            f"dma://{self.binding.binding_id}/{self.binding.campaign_id}/{store}/{kind}/"
            f"{quote(str(identifier), safe='')}?sha256={token}"
        )
        return source

    def _sql_result(self, rows, kind: str) -> dict:
        data, sources = [], []
        for row in rows:
            item = dict(row)
            try:
                for key in JSON_FIELDS & item.keys():
                    if isinstance(item[key], str):
                        item[key] = json.loads(item[key])
            except ValueError as exc:
                raise AgentReadError(
                    "source_invalid", "Selected SQL record has invalid JSON"
                ) from exc
            sources.append(
                self._source(
                    "sql",
                    kind,
                    item.get("id", item.get("key")),
                    item,
                    **{
                        key: item[key]
                        for key in ("revision", "updated_at", "stable_key")
                        if key in item
                    },
                )
            )
            data.append(item)
        return self._result(data, sources)

    @staticmethod
    def _limit(value: int) -> int:
        if type(value) is not int or not 1 <= value <= 50:
            raise AgentReadError("invalid_arguments", "Limit must be between 1 and 50")
        return value

    @staticmethod
    def _id(value: int) -> int:
        if type(value) is not int or not 0 < value < 2**63:
            raise AgentReadError(
                "invalid_arguments", "A positive integer source ID is required"
            )
        return value

    def _overlay(self, filename: str) -> tuple[dict | None, str | None, str]:
        relative = f"campaigns/{self.binding.campaign_id}/{filename}"
        try:
            data, digest = _json_file(self._private_path(relative))
        except AgentReadError as exc:
            if exc.code == "source_missing":
                return None, None, relative
            raise
        if data.get("campaign_id") != self.binding.campaign_id:
            raise AgentReadError(
                "source_denied", "Selected overlay source belongs to another campaign"
            )
        return data, digest, relative

    def _campaign_describe(self, db) -> dict:
        links, _, _ = self._overlay("agent-session-links.json")
        data = {
            **self.binding.identity,
            "deployment_mode": (
                "private-rehearsal"
                if self.binding.binding_id.startswith("rehearsal-")
                else "bound-campaign"
            ),
            "note_types": [*NOTE_FILES, "room", "bestiary"],
            "material_access": "Use item_id=catalog for bounded headers, then an exact ID. Room IDs are map_id/room_id. Raw PDFs are not a reader tool.",
            "schema_revision": self.binding.schema_revision,
            "tools": list(TOOL_NAMES),
            "mutations_enabled": False,
            "session_linkage": "available" if links else "missing",
            "unavailable": [
                "staging",
                "review decisions",
                "promotion",
                "publication",
                "prep preview",
            ],
        }
        return self._result(
            data,
            [
                self._source(
                    "sql", "binding", self.binding.binding_id, self.binding.identity
                )
            ],
        )

    def _campaign_read_entities(
        self, db, entity_id: int | None = None, limit: int = 20
    ) -> dict:
        limit = self._limit(limit)
        if entity_id is not None:
            rows = db.execute(
                "SELECT * FROM campaign_entities WHERE id=?", (self._id(entity_id),)
            )
        else:
            rows = db.execute(
                "SELECT * FROM campaign_entities ORDER BY id LIMIT ?", (limit,)
            )
        return self._sql_result(rows, "campaign_entity")

    def _campaign_read_history(
        self, db, document_id: int | None = None, limit: int = 20
    ) -> dict:
        limit = self._limit(limit)
        selected = " AND id=?" if document_id is not None else ""
        parameters = (
            (self._id(document_id), limit) if document_id is not None else (limit,)
        )
        rows = db.execute(
            "SELECT id,kind,title,content,summary,source_name,review_status,visibility_scope,rag_eligible,updated_at FROM documents WHERE kind='session_log' AND review_status='approved' AND rag_eligible=1 AND visibility_scope IN ('gm_only','player_safe')"
            + selected
            + " ORDER BY updated_at DESC,id DESC LIMIT ?",
            parameters,
        )
        return self._sql_result(rows, "session_log")

    def _campaign_read_provenance(self, db, entity_id: int, limit: int = 20) -> dict:
        rows = db.execute(
            "SELECT p.* FROM campaign_entity_provenance p JOIN session_update_drafts d ON d.id=p.draft_id WHERE p.entity_id=? AND d.campaign_id=? ORDER BY p.id LIMIT ?",
            (self._id(entity_id), self.binding.campaign_id, self._limit(limit)),
        )
        return self._sql_result(rows, "entity_provenance")

    def _session_read_review(
        self, db, draft_id: int | None = None, limit: int = 20
    ) -> dict:
        limit = self._limit(limit)
        if draft_id is None:
            rows = db.execute(
                "SELECT id,campaign_id,title,source_hash,revision,status,session_log_document_id,session_log_decision FROM session_update_drafts WHERE campaign_id=? AND status='pending' ORDER BY id DESC LIMIT ?",
                (self.binding.campaign_id, limit),
            )
        else:
            rows = db.execute(
                "SELECT * FROM session_update_drafts WHERE id=? AND campaign_id=?",
                (self._id(draft_id), self.binding.campaign_id),
            )
        return self._sql_result(rows, "session_update_draft")

    def _session_read_live(self, db) -> dict:
        result = self._sql_result(
            db.execute(
                "SELECT key,data,revision,updated_at FROM contexts WHERE key='live-session-state'"
            ),
            "live_state",
        )
        result["data"] = result["data"][0] if result["data"] else None
        return result

    def _campaign_read_sessions(
        self, db, session_id: str | None = None, limit: int = 20
    ) -> dict:
        limit = self._limit(limit)
        if session_id is not None and (
            not isinstance(session_id, str) or not 1 <= len(session_id) <= 128
        ):
            raise AgentReadError(
                "invalid_arguments", "Select an exact saved session ID"
            )
        payload, digest, relative = self._overlay("agent-session-links.json")
        if payload is None:
            return self._result([], [])
        items = payload.get("items")
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), str)
            for item in items
        ):
            raise AgentReadError(
                "source_invalid", "Session association records require stable IDs"
            )
        if len({item["id"] for item in items}) != len(items):
            raise AgentReadError("source_invalid", "Duplicate session association IDs")
        selected = (
            [item for item in items if item["id"] == session_id]
            if session_id is not None
            else items[:limit]
        )
        sources = [
            self._source(
                "overlay",
                "session_association",
                item["id"],
                item,
                file=relative,
                file_sha256=digest,
            )
            for item in selected
        ]
        if selected and self.binding.schema_revision == "20261028_0007":
            selected_by_id = {item["id"]: item for item in selected}
            rows = db.execute(
                "SELECT id,intent_hash,json_extract(intent,'$.request.session_id') AS session_id,"
                "json_extract(result,'$.id') AS draft_id FROM campaign_approvals "
                "WHERE status='completed' AND json_extract(intent,'$.request.operation')='stage_update' "
                "AND json_extract(intent,'$.scope.binding_id')=? "
                "AND json_extract(intent,'$.scope.campaign_id')=? "
                "AND json_extract(intent,'$.scope.recovery_epoch')=? "
                "AND json_extract(intent,'$.scope.target.database')=? "
                "AND json_extract(intent,'$.scope.target.private_root')=? ORDER BY created_at,id",
                (
                    self.binding.binding_id,
                    self.binding.campaign_id,
                    self.binding.recovery_epoch,
                    str(self.binding.database),
                    str(self.binding.private_root),
                ),
            )
            for row in rows:
                if row["session_id"] not in selected_by_id:
                    continue
                item = selected_by_id[row["session_id"]]
                draft_id = self._id(row["draft_id"])
                if draft_id not in item.setdefault("draft_ids", []):
                    item["draft_ids"].append(draft_id)
                sources.append(
                    self._source(
                        "sql", "staged_session_association", row["id"], dict(row)
                    )
                )
        return self._result(selected, sources)

    def _campaign_read_notes(self, db, note_type: str, item_id: str) -> dict:
        if note_type in {"room", "bestiary"}:
            return self._read_material(note_type, item_id)
        if (
            note_type not in NOTE_FILES
            or not isinstance(item_id, str)
            or not 1 <= len(item_id) <= 128
        ):
            raise AgentReadError(
                "invalid_arguments", "Select a supported note type and exact item ID"
            )
        filename, collection = NOTE_FILES[note_type]
        payload, digest, relative = self._overlay(filename)
        if payload is None:
            return self._result(None, [])
        items = payload.get(collection)
        if not isinstance(items, list) or any(
            not isinstance(item, dict) for item in items
        ):
            raise AgentReadError(
                "source_invalid", "Selected note collection is invalid"
            )
        if item_id == "catalog":
            headers = [
                {
                    "id": item.get("id"),
                    "name": item.get("name")
                    or item.get("title")
                    or item.get("character_name"),
                }
                for item in items[:50]
            ]
            return self._result(
                headers,
                [
                    self._source(
                        "overlay",
                        note_type + "_catalog",
                        "catalog",
                        headers,
                        file=relative,
                        file_sha256=digest,
                    )
                ],
            )
        matches = [
            item
            for item in items
            if item.get("id") is not None and str(item["id"]) == item_id
        ]
        if len(matches) > 1:
            raise AgentReadError("source_invalid", "Selected note ID is ambiguous")
        if not matches:
            return self._result(None, [])
        item = matches[0]
        return self._result(
            item,
            [
                self._source(
                    "overlay",
                    note_type,
                    item_id,
                    item,
                    file=relative,
                    file_sha256=digest,
                )
            ],
        )

    def _read_material(self, note_type, item_id):
        if not isinstance(item_id, str) or not 1 <= len(item_id) <= 128:
            raise AgentReadError(
                "invalid_arguments", "Select an exact material ID or catalog"
            )
        folder = "room-keys" if note_type == "room" else "bestiary"
        root = self._private_path(folder)
        headers, found = [], []
        for path in sorted(root.rglob("*.json"))[:100]:
            relative = path.relative_to(self.binding.private_root).as_posix()
            safe = self._private_path(relative)
            payload, token = _json_file(safe)
            if (
                payload.get("campaign_id")
                not in (
                    None,
                    self.binding.campaign_id,
                )
                or str(payload.get("campaign") or self.binding.campaign_id)
                .casefold()
                .replace(" ", "-")
                != self.binding.campaign_id
            ):
                continue
            key = "rooms" if note_type == "room" else "entries"
            for entry in payload.get(key) or []:
                if not isinstance(entry, dict):
                    continue
                identifier = (
                    f"{payload.get('map_id')}/{entry.get('room_id')}"
                    if note_type == "room"
                    else str(entry.get("id", ""))
                )
                headers.append(
                    {"id": identifier, "name": entry.get("title") or entry.get("name")}
                )
                if identifier == item_id:
                    found.append((entry, relative, token))
        if item_id == "catalog":
            return self._result(
                headers[:100],
                [
                    self._source(
                        "overlay", note_type + "_catalog", "catalog", headers[:100]
                    )
                ],
            )
        if len(found) > 1:
            raise AgentReadError("source_invalid", "Ambiguous material ID")
        if not found:
            return self._result(None, [])
        entry, relative, token = found[0]
        return self._result(
            entry,
            [
                self._source(
                    "overlay",
                    note_type,
                    item_id,
                    entry,
                    file=relative,
                    file_sha256=token,
                )
            ],
        )

    def call(self, name: str, arguments: dict | None = None) -> dict:
        # A closed registry; never resolve arbitrary method names supplied by a model.
        if name not in TOOL_NAMES:
            raise AgentReadError(
                "tool_unavailable", "Requested tool is not available to this reader"
            )
        if arguments is not None and not isinstance(arguments, dict):
            raise AgentReadError(
                "invalid_arguments", "Tool arguments must be an object"
            )
        handler = {
            "campaign_describe": self._campaign_describe,
            "campaign_read_entities": self._campaign_read_entities,
            "campaign_read_history": self._campaign_read_history,
            "campaign_read_provenance": self._campaign_read_provenance,
            "campaign_read_notes": self._campaign_read_notes,
            "campaign_read_sessions": self._campaign_read_sessions,
            "session_read_live": self._session_read_live,
            "session_read_review": self._session_read_review,
        }[name]
        with self._connection() as db:
            try:
                return handler(db, **(arguments or {}))
            except TypeError as exc:
                raise AgentReadError(
                    "invalid_arguments",
                    "Tool arguments do not match the allowed schema",
                ) from exc
