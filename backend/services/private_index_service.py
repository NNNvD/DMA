from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from time import time
from typing import Any

from backend.services.private_campaign_data_service import private_campaign_data_service
from backend.services.reference_corpus_service import reference_corpus_service


DEPENDENCY_CATEGORIES = {
    "creature": "creatures",
    "aon_reference": "creatures",
    "monster": "creatures",
    "npc": "creatures",
    "hazard": "hazards",
    "trap": "hazards",
    "haunt": "hazards",
    "affliction": "afflictions",
    "disease": "diseases",
    "item": "items",
    "loot": "items",
    "quest_item": "items",
    "spell": "spells",
    "feat": "feats",
    "condition": "conditions",
    "action": "actions",
    "trait": "traits",
    "ritual": "rituals",
    "rule": "rules",
    "subsystem": "subsystems",
}


class DependencyResolverService:
    """Resolve campaign references against custom campaign data and AoN cache."""

    def __init__(self) -> None:
        self.data = private_campaign_data_service
        self.reference = reference_corpus_service

    def resolve_all(self, indexes: dict[str, Any]) -> dict[str, Any]:
        candidates = self._dependency_candidates(indexes)
        custom_names = self._custom_bestiary_names(indexes)
        resolved = []
        for candidate in candidates:
            resolved.append(self.resolve_candidate(candidate, custom_names=custom_names))
        return {
            "campaign_id": self.data.campaign_id(),
            "items": resolved,
            "summary": self._summary(resolved),
            "updated_at": time(),
        }

    def resolve_candidate(
        self,
        candidate: dict[str, Any],
        *,
        custom_names: set[str] | None = None,
    ) -> dict[str, Any]:
        name = str(candidate.get("name") or "").strip()
        kind = str(candidate.get("kind") or "rule").strip().casefold()
        category = DEPENDENCY_CATEGORIES.get(kind, kind)
        normalized_name = self._normalize_name(name)
        if custom_names and normalized_name in custom_names:
            return {
                **candidate,
                "category": category,
                "resolution_status": "campaign_custom",
                "resolved_id": f"campaign:{normalized_name}",
                "review_status": "confirmed",
            }
        matches = self._reference_matches(name, category)
        exact = [
            item
            for item in matches
            if self._normalize_name(str(item.get("name") or "")) == normalized_name
        ]
        if len(exact) == 1:
            match = exact[0]
            return {
                **candidate,
                "category": category,
                "resolution_status": "aon_resolved",
                "resolved_id": match.get("id"),
                "resolved_name": match.get("name"),
                "url": match.get("url"),
                "review_status": "confirmed",
            }
        if len(exact) > 1 or len(matches) > 1:
            return {
                **candidate,
                "category": category,
                "resolution_status": "aon_ambiguous",
                "candidate_matches": [
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "url": item.get("url"),
                    }
                    for item in matches
                ],
                "review_status": "uncertain",
            }
        if len(matches) == 1:
            match = matches[0]
            return {
                **candidate,
                "category": category,
                "resolution_status": "needs_review",
                "candidate_matches": [
                    {
                        "id": match.get("id"),
                        "name": match.get("name"),
                        "url": match.get("url"),
                    }
                ],
                "review_status": "uncertain",
            }
        return {
            **candidate,
            "category": category,
            "resolution_status": "missing",
            "review_status": "missing",
        }

    def _reference_matches(self, name: str, category: str) -> list[dict[str, Any]]:
        categories = [category]
        if category == "afflictions":
            categories.append("diseases")
        elif category == "diseases":
            categories.append("afflictions")
        elif category == "items":
            categories.extend(["equipment", "treasure"])
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()
        for current in categories:
            for item in self.reference.search(q=name, category=current, limit=8):
                item_id = str(item.get("id") or "")
                if item_id in seen:
                    continue
                seen.add(item_id)
                matches.append(item)
        return matches

    def _dependency_candidates(self, indexes: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}
        for room in indexes.get("rooms") or []:
            source = {"entity_type": "room", "entity_id": room.get("room_id"), "map_id": room.get("map_id")}
            for key, kind in [
                ("monsters", "creature"),
                ("npcs", "npc"),
                ("hazards", "hazard"),
                ("traps", "trap"),
                ("haunts", "haunt"),
                ("afflictions", "affliction"),
                ("loot", "item"),
                ("quest_items", "quest_item"),
            ]:
                for value in room.get(key) or []:
                    self._add_candidate(candidates, str(value), kind, source)
            for ref in room.get("encounter_refs") or []:
                if isinstance(ref, dict):
                    self._add_candidate(
                        candidates,
                        str(ref.get("name") or ref.get("id") or ""),
                        str(ref.get("type") or "creature"),
                        source,
                    )
            for dep in room.get("dependencies") or []:
                if isinstance(dep, dict):
                    self._add_candidate(
                        candidates,
                        str(dep.get("name") or dep.get("id") or ""),
                        str(dep.get("kind") or dep.get("type") or "rule"),
                        source,
                    )
                else:
                    self._add_candidate(candidates, str(dep), "rule", source)
        for entry in indexes.get("bestiary") or []:
            source = {"entity_type": "bestiary", "entity_id": entry.get("id")}
            if entry.get("entry_type") == "aon_reference":
                self._add_candidate(
                    candidates,
                    str(entry.get("aon_name") or entry.get("name") or ""),
                    "creature",
                    source,
                )
            for trait in entry.get("traits") or []:
                self._add_candidate(candidates, str(trait), "trait", source)
        return sorted(candidates.values(), key=lambda item: (item["kind"], item["name"].casefold()))

    def _add_candidate(
        self,
        candidates: dict[str, dict[str, Any]],
        name: str,
        kind: str,
        source: dict[str, Any],
    ) -> None:
        name = name.strip()
        if not name:
            return
        key = f"{kind}:{self._normalize_name(name)}"
        existing = candidates.setdefault(
            key,
            {
                "id": f"dependency:{key}",
                "name": name,
                "kind": kind,
                "sources": [],
            },
        )
        if source not in existing["sources"]:
            existing["sources"].append(source)

    def _custom_bestiary_names(self, indexes: dict[str, Any]) -> set[str]:
        return {
            self._normalize_name(str(entry.get("name") or ""))
            for entry in indexes.get("bestiary") or []
            if entry.get("entry_type") in {"creature", "hazard", "affliction"}
        }

    def _summary(self, items: list[dict[str, Any]]) -> dict[str, int]:
        summary: dict[str, int] = {}
        for item in items:
            status = str(item.get("resolution_status") or "missing")
            summary[status] = summary.get(status, 0) + 1
        return summary

    def _normalize_name(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


class PrivateIndexService:
    """Build private-local runtime indexes from promoted campaign JSON."""

    def __init__(self) -> None:
        self.data = private_campaign_data_service
        self.resolver = DependencyResolverService()

    def private_root(self) -> Path:
        return self.data.private_root()

    def campaign_id(self) -> str:
        return self.data.campaign_id()

    def indexes_root(self) -> Path:
        return self.private_root() / "indexes"

    def campaign_root(self) -> Path:
        return self.private_root() / "campaigns" / self.campaign_id()

    def room_key_root(self) -> Path:
        return self.private_root() / "room-keys" / self.campaign_id()

    def bestiary_root(self) -> Path:
        return self.private_root() / "bestiary" / self.campaign_id()

    def status(self) -> dict[str, Any]:
        root = self.indexes_root()
        expected = [
            "campaign-search.jsonl",
            "entity-catalog.json",
            "room-index.json",
            "encounter-index.json",
            "item-loot-index.json",
            "image-index.json",
            "dependency-index.json",
            "rag-documents.jsonl",
        ]
        files = []
        missing = []
        for name in expected:
            path = root / name
            if path.exists():
                files.append(
                    {
                        "name": name,
                        "path": path.relative_to(self.private_root()).as_posix(),
                        "size": path.stat().st_size,
                        "updated_at": path.stat().st_mtime,
                    }
                )
            else:
                missing.append(name)
        manifest = self._read_json(root / "manifest.json", {})
        return {
            "campaign_id": self.campaign_id(),
            "ready": not missing,
            "missing": missing,
            "files": files,
            "manifest": manifest,
        }

    def build_all(self) -> dict[str, Any]:
        self.indexes_root().mkdir(parents=True, exist_ok=True)
        data = {
            "campaign": self._load_campaign_files(),
            "rooms": self._load_rooms(),
            "bestiary": self._load_bestiary_entries(),
            "images": self._load_json(self.campaign_root() / "images.json", {"items": []}).get("items") or [],
        }
        entity_catalog = self._build_entity_catalog(data)
        room_index = self._build_room_index(data["rooms"])
        encounter_index = self._build_encounter_index(data["rooms"])
        item_index = self._build_item_index(data["rooms"])
        image_index = self._build_image_index(data)
        dependency_index = self.resolver.resolve_all(data)
        search_docs = self._build_search_documents(data, entity_catalog, dependency_index)
        rag_docs = self._build_rag_documents(search_docs)

        self._write_json(self.indexes_root() / "entity-catalog.json", entity_catalog)
        self._write_json(self.indexes_root() / "room-index.json", room_index)
        self._write_json(self.indexes_root() / "encounter-index.json", encounter_index)
        self._write_json(self.indexes_root() / "item-loot-index.json", item_index)
        self._write_json(self.indexes_root() / "image-index.json", image_index)
        self._write_json(self.indexes_root() / "dependency-index.json", dependency_index)
        self._write_jsonl(self.indexes_root() / "campaign-search.jsonl", search_docs)
        self._write_jsonl(self.indexes_root() / "rag-documents.jsonl", rag_docs)
        audit = self.audit()
        manifest = {
            "campaign_id": self.campaign_id(),
            "updated_at": time(),
            "counts": {
                "rooms": len(data["rooms"]),
                "bestiary": len(data["bestiary"]),
                "entities": len(entity_catalog["items"]),
                "dependencies": len(dependency_index["items"]),
                "search_documents": len(search_docs),
                "rag_documents": len(rag_docs),
            },
            "audit": audit["summary"],
        }
        self._write_json(self.indexes_root() / "manifest.json", manifest)
        return manifest

    def audit(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        room_index = self._read_json(self.indexes_root() / "room-index.json", {"items": []})
        dependency_index = self._read_json(self.indexes_root() / "dependency-index.json", {"items": []})
        entity_catalog = self._read_json(self.indexes_root() / "entity-catalog.json", {"items": []})
        seen: set[str] = set()
        for entity in entity_catalog.get("items") or []:
            entity_id = str(entity.get("id") or "")
            if not entity_id:
                issues.append(self._issue("entity", "missing_id", "error", "Entity is missing an id."))
            elif entity_id in seen:
                issues.append(self._issue("entity", "duplicate_id", "error", f"Duplicate entity id: {entity_id}"))
            seen.add(entity_id)
        for room in room_index.get("items") or []:
            if not room.get("search_text"):
                issues.append(self._issue("room", "empty_search_text", "warning", f"{room.get('room_id')} has no searchable text."))
        for dependency in dependency_index.get("items") or []:
            if dependency.get("resolution_status") in {"missing", "aon_ambiguous", "needs_review"}:
                issues.append(
                    self._issue(
                        "dependency",
                        str(dependency.get("resolution_status")),
                        "warning",
                        f"{dependency.get('name')} requires reference review.",
                    )
                )
        summary: dict[str, int] = {}
        for issue in issues:
            severity = str(issue.get("severity") or "info")
            summary[severity] = summary.get(severity, 0) + 1
        return {
            "campaign_id": self.campaign_id(),
            "summary": summary,
            "issues": issues,
            "updated_at": time(),
        }

    def dependency_audit(self) -> dict[str, Any]:
        path = self.indexes_root() / "dependency-index.json"
        if not path.exists():
            self.build_all()
        return self._read_json(path, {"items": [], "summary": {}})

    def unresolved_dependencies(self) -> list[dict[str, Any]]:
        payload = self.dependency_audit()
        return [
            item
            for item in payload.get("items") or []
            if item.get("resolution_status") in {"missing", "aon_ambiguous", "needs_review"}
        ]

    def update_dependency(self, dependency_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        path = self.indexes_root() / "dependency-index.json"
        if not path.exists():
            self.build_all()
        payload = self._read_json(path, {"items": []})
        for item in payload.get("items") or []:
            if str(item.get("id") or "") != dependency_id:
                continue
            action = str(updates.get("action") or "").strip().casefold()
            if action == "ignore":
                item["resolution_status"] = "ignored"
                item["review_status"] = "confirmed"
            elif action == "mark_custom":
                item["resolution_status"] = "campaign_custom"
                item["review_status"] = "confirmed"
                item["resolved_id"] = updates.get("resolved_id") or f"campaign:{self._slug(item.get('name'))}"
            elif action == "link_aon":
                resolved_id = str(updates.get("resolved_id") or "").strip()
                if not resolved_id:
                    raise ValueError("resolved_id is required for link_aon")
                reference = reference_corpus_service.get(resolved_id)
                item["resolution_status"] = "aon_resolved"
                item["review_status"] = "confirmed"
                item["resolved_id"] = resolved_id
                if reference:
                    item["resolved_name"] = reference.get("name")
                    item["url"] = reference.get("url")
            elif action == "needs_review":
                item["resolution_status"] = "needs_review"
                item["review_status"] = "uncertain"
            else:
                raise ValueError(f"Unsupported dependency action: {action}")
            if "reviewer_notes" in updates:
                item["reviewer_notes"] = str(updates.get("reviewer_notes") or "").strip()
            item["updated_at"] = time()
            payload["updated_at"] = time()
            payload["summary"] = self.resolver._summary(payload.get("items") or [])
            self._write_json(path, payload)
            self._write_json(self.indexes_root() / "index-audit.json", self.audit())
            return item
        return None

    def _load_campaign_files(self) -> list[dict[str, Any]]:
        files = []
        for name in [
            "campaign-overview.json",
            "campaign-recaps.json",
            "sessions.json",
            "treasure-tracker.json",
            "pcs.json",
            "npcs.json",
        ]:
            path = self.campaign_root() / name
            if path.exists():
                files.append({"name": name, "payload": self._read_json(path, {})})
        return files

    def _load_rooms(self) -> list[dict[str, Any]]:
        rooms = []
        root = self.room_key_root()
        if not root.exists():
            return rooms
        for path in sorted(root.glob("*.json")):
            payload = self._read_json(path, {})
            map_id = str(payload.get("map_id") or path.stem)
            for room in payload.get("rooms") or []:
                if not isinstance(room, dict):
                    continue
                normalized = dict(room)
                normalized["map_id"] = map_id
                normalized["room_key_path"] = path.relative_to(self.private_root()).as_posix()
                rooms.append(normalized)
        return rooms

    def _load_bestiary_entries(self) -> list[dict[str, Any]]:
        entries = []
        root = self.bestiary_root()
        if not root.exists():
            return entries
        for path in sorted(root.glob("*.json")):
            payload = self._read_json(path, {})
            for entry in payload.get("entries") or []:
                if isinstance(entry, dict):
                    normalized = dict(entry)
                    normalized["source_file"] = path.relative_to(self.private_root()).as_posix()
                    entries.append(normalized)
        return entries

    def _build_entity_catalog(self, data: dict[str, Any]) -> dict[str, Any]:
        items = []
        for room in data["rooms"]:
            room_id = str(room.get("room_id") or "")
            items.append(
                {
                    "id": f"room:{room.get('map_id')}:{room_id}",
                    "entity_type": "room",
                    "name": f"{room_id} {room.get('title') or ''}".strip(),
                    "room_id": room_id,
                    "map_id": room.get("map_id"),
                    "source_path": room.get("room_key_path"),
                }
            )
        for entry in data["bestiary"]:
            items.append(
                {
                    "id": f"bestiary:{entry.get('id')}",
                    "entity_type": entry.get("entry_type") or "bestiary",
                    "name": entry.get("name"),
                    "rooms": entry.get("rooms") or [],
                    "source_path": entry.get("source_file"),
                }
            )
        for file in data["campaign"]:
            payload = file["payload"]
            for item in payload.get("items") or payload.get("tabs") or []:
                if not isinstance(item, dict):
                    continue
                items.append(
                    {
                        "id": f"{file['name']}:{item.get('id') or item.get('path') or item.get('title')}",
                        "entity_type": file["name"].replace(".json", ""),
                        "name": item.get("title") or item.get("name") or item.get("label"),
                        "source_path": file["name"],
                    }
                )
        return {"campaign_id": self.campaign_id(), "items": items, "updated_at": time()}

    def _build_room_index(self, rooms: list[dict[str, Any]]) -> dict[str, Any]:
        items = []
        for room in rooms:
            literal = room.get("literal_text") if isinstance(room.get("literal_text"), dict) else {}
            fields = [
                room.get("title"),
                room.get("player_visible_description"),
                room.get("gm_description"),
                literal.get("read_aloud"),
                literal.get("general_text"),
                literal.get("encounter_text"),
            ]
            tags = [
                key
                for key in ("monsters", "npcs", "hazards", "traps", "haunts", "afflictions", "loot", "quest_items", "secret_doors")
                if room.get(key)
            ]
            items.append(
                {
                    "id": f"room:{room.get('map_id')}:{room.get('room_id')}",
                    "map_id": room.get("map_id"),
                    "room_id": room.get("room_id"),
                    "title": room.get("title"),
                    "tags": tags,
                    "creatures": list(room.get("monsters") or []) + list(room.get("npcs") or []),
                    "hazards": list(room.get("hazards") or []) + list(room.get("traps") or []) + list(room.get("haunts") or []),
                    "afflictions": room.get("afflictions") or [],
                    "loot": list(room.get("loot") or []) + list(room.get("quest_items") or []),
                    "source_refs": room.get("source_references") or room.get("source") or [],
                    "search_text": self._compact_text(fields),
                }
            )
        return {"campaign_id": self.campaign_id(), "items": items, "updated_at": time()}

    def _build_encounter_index(self, rooms: list[dict[str, Any]]) -> dict[str, Any]:
        items = []
        for room in rooms:
            refs = list(room.get("encounter_refs") or [])
            for name in room.get("monsters") or []:
                refs.append({"type": "creature", "name": name})
            for name in room.get("hazards") or []:
                refs.append({"type": "hazard", "name": name})
            for name in room.get("afflictions") or []:
                refs.append({"type": "affliction", "name": name})
            if refs:
                items.append(
                    {
                        "room_id": room.get("room_id"),
                        "map_id": room.get("map_id"),
                        "title": room.get("title"),
                        "refs": refs,
                    }
                )
        return {"campaign_id": self.campaign_id(), "items": items, "updated_at": time()}

    def _build_item_index(self, rooms: list[dict[str, Any]]) -> dict[str, Any]:
        items = []
        seen: set[str] = set()
        for room in rooms:
            for key, item_type in [("loot", "loot"), ("quest_items", "quest_item")]:
                for name in room.get(key) or []:
                    item_id = f"{item_type}:{self._slug(name)}:{room.get('room_id')}"
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                    items.append(
                        {
                            "id": item_id,
                            "name": name,
                            "item_type": item_type,
                            "room_id": room.get("room_id"),
                            "map_id": room.get("map_id"),
                            "status": "unknown",
                        }
                    )
        return {"campaign_id": self.campaign_id(), "items": items, "updated_at": time()}

    def _build_image_index(self, data: dict[str, Any]) -> dict[str, Any]:
        items = list(data.get("images") or [])
        for room in data["rooms"]:
            for image in room.get("image_candidates") or []:
                items.append(
                    {
                        "entity_type": "room",
                        "entity_id": room.get("room_id"),
                        "map_id": room.get("map_id"),
                        "candidate": image,
                        "status": "candidate",
                    }
                )
        return {"campaign_id": self.campaign_id(), "items": items, "updated_at": time()}

    def _build_search_documents(
        self,
        data: dict[str, Any],
        entity_catalog: dict[str, Any],
        dependency_index: dict[str, Any],
    ) -> list[dict[str, Any]]:
        docs = []
        for room in data["rooms"]:
            literal = room.get("literal_text") if isinstance(room.get("literal_text"), dict) else {}
            text = self._compact_text(
                [
                    room.get("player_visible_description"),
                    room.get("gm_description"),
                    literal.get("read_aloud"),
                    literal.get("general_text"),
                    literal.get("encounter_text"),
                ]
            )
            docs.append(
                {
                    "id": f"room:{room.get('map_id')}:{room.get('room_id')}",
                    "kind": "room",
                    "title": f"{room.get('room_id')} {room.get('title') or ''}".strip(),
                    "text": text,
                    "source_path": room.get("room_key_path"),
                    "metadata": {"map_id": room.get("map_id"), "room_id": room.get("room_id")},
                }
            )
        for file in data["campaign"]:
            for item in file["payload"].get("items") or file["payload"].get("tabs") or []:
                if not isinstance(item, dict):
                    continue
                text = item.get("body_markdown") or item.get("content") or item.get("summary") or ""
                if text:
                    docs.append(
                        {
                            "id": f"{file['name']}:{item.get('id') or item.get('path') or item.get('title')}",
                            "kind": file["name"].replace(".json", ""),
                            "title": item.get("title") or item.get("name") or item.get("label") or file["name"],
                            "text": text,
                            "source_path": file["name"],
                            "metadata": {},
                        }
                    )
        for dep in dependency_index.get("items") or []:
            docs.append(
                {
                    "id": dep.get("id"),
                    "kind": "dependency",
                    "title": dep.get("name"),
                    "text": json.dumps(dep, ensure_ascii=False),
                    "source_path": "indexes/dependency-index.json",
                    "metadata": {"resolution_status": dep.get("resolution_status")},
                }
            )
        return [doc for doc in docs if doc.get("text")]

    def _build_rag_documents(self, search_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rag_docs = []
        for doc in search_docs:
            rag_docs.append(
                {
                    "external_id": doc.get("id"),
                    "title": doc.get("title"),
                    "kind": doc.get("kind"),
                    "source": "private-local-index",
                    "source_path": doc.get("source_path"),
                    "content": doc.get("text"),
                    "metadata": doc.get("metadata") or {},
                }
            )
        return rag_docs

    def _compact_text(self, values: list[Any]) -> str:
        return re.sub(r"\s+", " ", " ".join(str(value or "") for value in values)).strip()

    def _slug(self, value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-") or "item"

    def _issue(self, entity_type: str, code: str, severity: str, message: str) -> dict[str, Any]:
        return {
            "entity_type": entity_type,
            "code": code,
            "severity": severity,
            "message": message,
        }

    def _load_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        return self._read_json(path, default)

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return dict(default)
        return payload if isinstance(payload, dict) else dict(default)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)


dependency_resolver_service = DependencyResolverService()
private_index_service = PrivateIndexService()
