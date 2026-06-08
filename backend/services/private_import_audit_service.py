from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import time
from typing import Any

from backend.services.private_campaign_data_service import private_campaign_data_service


REVIEW_STATUSES = {
    "confirmed",
    "likely",
    "uncertain",
    "missing",
    "conflict",
    "rejected",
    "approved",
    "promoted",
    "unreviewed",
}


class PrivateImportAuditService:
    """Create and manage private-local import review runs."""

    def __init__(self) -> None:
        self.data = private_campaign_data_service

    def private_root(self) -> Path:
        return self.data.private_root()

    def campaign_id(self) -> str:
        return self.data.campaign_id()

    def imports_root(self) -> Path:
        return self.private_root() / "imports" / self.campaign_id()

    def import_recipes_root(self) -> Path:
        return self.private_root() / "import-recipes"

    def raw_reference_root(self) -> Path:
        return self.private_root() / "reference" / "raw"

    def extracted_reference_root(self) -> Path:
        return self.private_root() / "reference" / "extracted"

    def room_key_root(self) -> Path:
        return self.private_root() / "room-keys" / self.campaign_id()

    def campaign_root(self) -> Path:
        return self.private_root() / "campaigns" / self.campaign_id()

    def list_import_runs(self) -> list[dict[str, Any]]:
        root = self.imports_root()
        if not root.exists():
            return []
        runs = []
        for manifest_path in sorted(root.glob("*/import-manifest.json"), reverse=True):
            try:
                runs.append(json.loads(manifest_path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return runs

    def get_import_run(self, run_id: str) -> dict[str, Any] | None:
        path = self._run_root(run_id) / "import-manifest.json"
        if not path.exists():
            return None
        return self._read_json(path, {})

    def create_import_run(
        self,
        *,
        title: str | None = None,
        map_id: str | None = None,
    ) -> dict[str, Any]:
        run_id = self._new_run_id()
        run_root = self._run_root(run_id)
        run_root.mkdir(parents=True, exist_ok=True)
        source_manifest = self.register_sources()
        self.ensure_default_recipe()
        room_drafts = self._build_room_drafts(map_id=map_id)
        field_audit = self._audit_room_drafts(room_drafts)
        unresolved = [
            issue
            for issue in field_audit["issues"]
            if issue.get("severity") in {"warning", "error"}
        ]
        manifest = {
            "run_id": run_id,
            "campaign_id": self.campaign_id(),
            "title": title or f"Room Import Review {run_id}",
            "status": "draft",
            "scope": "rooms-first",
            "created_at": self._now_iso(),
            "updated_at": time(),
            "source_ids": [source["source_id"] for source in source_manifest["sources"]],
            "room_draft_count": len(room_drafts["items"]),
            "reviewed_count": 0,
            "approved_count": 0,
            "promoted_count": 0,
            "promotion_required_status": "approved",
        }
        self._write_run_json(run_id, "import-manifest.json", manifest)
        self._write_run_json(run_id, "entity-candidates.json", self._entity_candidates(room_drafts))
        self._write_run_json(run_id, "room-drafts.json", room_drafts)
        self._write_run_json(run_id, "field-audit.json", field_audit)
        self._write_run_json(run_id, "image-match-audit.json", self._image_match_audit(room_drafts))
        self._write_run_json(
            run_id,
            "unresolved-issues.json",
            {"campaign_id": self.campaign_id(), "run_id": run_id, "items": unresolved},
        )
        self._write_run_json(
            run_id,
            "human-review-log.json",
            {"campaign_id": self.campaign_id(), "run_id": run_id, "items": []},
        )
        return manifest

    def room_drafts(
        self,
        run_id: str,
        *,
        review_status: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any] | None:
        payload = self._read_run_json(run_id, "room-drafts.json")
        if payload is None:
            return None
        query = (q or "").strip().casefold()
        status = (review_status or "").strip().casefold()
        items = []
        for item in payload.get("items") or []:
            if status and str(item.get("review_status") or "").casefold() != status:
                continue
            if query and query not in self._draft_search_text(item):
                continue
            items.append(item)
        return {**payload, "items": items, "total": len(items)}

    def update_room_draft(
        self,
        run_id: str,
        draft_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = self._read_run_json(run_id, "room-drafts.json")
        if payload is None:
            return None
        for item in payload.get("items") or []:
            if item.get("draft_id") != draft_id:
                continue
            review_status = updates.get("review_status")
            if review_status is not None:
                status = str(review_status).strip().casefold()
                if status not in REVIEW_STATUSES:
                    raise ValueError(f"Unsupported review status: {review_status}")
                item["review_status"] = status
            if "reviewer_notes" in updates:
                item["reviewer_notes"] = str(updates.get("reviewer_notes") or "").strip()
            editable_fields = updates.get("fields")
            if isinstance(editable_fields, dict):
                self._apply_field_updates(item, editable_fields)
            item["updated_at"] = time()
            self._write_run_json(run_id, "room-drafts.json", payload)
            self._append_review_log(run_id, draft_id, updates)
            self._refresh_run_counts(run_id)
            self._write_run_json(run_id, "field-audit.json", self._audit_room_drafts(payload))
            return item
        return None

    def audit_summary(self, run_id: str) -> dict[str, Any] | None:
        manifest = self.get_import_run(run_id)
        if manifest is None:
            return None
        room_drafts = self._read_run_json(run_id, "room-drafts.json") or {"items": []}
        field_audit = self._read_run_json(run_id, "field-audit.json") or {"issues": []}
        image_audit = self._read_run_json(run_id, "image-match-audit.json") or {"issues": []}
        status_counts: dict[str, int] = {}
        for draft in room_drafts.get("items") or []:
            status = str(draft.get("review_status") or "unreviewed")
            status_counts[status] = status_counts.get(status, 0) + 1
        severity_counts: dict[str, int] = {}
        for issue in field_audit.get("issues") or []:
            severity = str(issue.get("severity") or "info")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return {
            "run": manifest,
            "status_counts": status_counts,
            "severity_counts": severity_counts,
            "field_issues": field_audit.get("issues") or [],
            "image_issues": image_audit.get("issues") or [],
        }

    def promote_reviewed_rooms(self, run_id: str) -> dict[str, Any] | None:
        payload = self._read_run_json(run_id, "room-drafts.json")
        if payload is None:
            return None
        approved = [
            draft
            for draft in payload.get("items") or []
            if draft.get("review_status") in {"approved", "promoted"}
        ]
        promoted_ids = []
        by_map: dict[str, list[dict[str, Any]]] = {}
        for draft in approved:
            by_map.setdefault(str(draft.get("map_id") or "unknown"), []).append(draft)

        for map_id, drafts in by_map.items():
            room_key_path = self._room_key_path_for_map(map_id)
            existing = self._read_json(
                room_key_path,
                {
                    "map_id": map_id,
                    "title": map_id,
                    "campaign": self.campaign_id(),
                    "rooms": [],
                },
            )
            rooms = list(existing.get("rooms") or [])
            room_index = {
                str(room.get("room_id") or "").casefold(): index
                for index, room in enumerate(rooms)
            }
            for draft in drafts:
                room = self._promoted_room_from_draft(draft)
                key = str(room.get("room_id") or "").casefold()
                if key in room_index:
                    rooms[room_index[key]] = room
                else:
                    rooms.append(room)
                if draft.get("review_status") != "promoted":
                    draft["review_status"] = "promoted"
                    draft["promoted_at"] = self._now_iso()
                promoted_ids.append(draft["draft_id"])
            rooms.sort(key=lambda room: self._room_sort_key(str(room.get("room_id") or "")))
            existing["rooms"] = rooms
            existing["updated_at"] = time()
            self._write_json(room_key_path, existing)

        self._write_run_json(run_id, "room-drafts.json", payload)
        self._refresh_run_counts(run_id)
        return {
            "run_id": run_id,
            "promoted_count": len(promoted_ids),
            "promoted_draft_ids": promoted_ids,
        }

    def register_sources(self) -> dict[str, Any]:
        sources = []
        raw_root = self.raw_reference_root()
        raw_root.mkdir(parents=True, exist_ok=True)
        for path in sorted(raw_root.rglob("*.pdf")):
            source_id = self._source_id(path)
            extracted = self._ensure_extracted_manifest(path, source_id)
            sources.append(
                {
                    "source_id": source_id,
                    "title": path.stem,
                    "path": path.relative_to(self.private_root()).as_posix(),
                    "sha256": self._sha256(path),
                    "role": self._infer_source_role(path),
                    "privacy": "private-local",
                    "extraction_status": extracted.get("status"),
                    "page_count": extracted.get("page_count"),
                    "warnings": extracted.get("warnings") or [],
                }
            )
        payload = {
            "campaign_id": self.campaign_id(),
            "updated_at": time(),
            "sources": sources,
        }
        self.campaign_root().mkdir(parents=True, exist_ok=True)
        self._write_json(self.campaign_root() / "sources.json", payload)
        return payload

    def ensure_default_recipe(self) -> None:
        self.import_recipes_root().mkdir(parents=True, exist_ok=True)
        path = self.import_recipes_root() / "paizo-adventure-path-v1.json"
        if path.exists():
            return
        payload = {
            "recipe_id": "paizo-adventure-path-v1",
            "version": 1,
            "room_heading_patterns": [
                r"^[A-Z][0-9]+\\.\\s+.+",
                r"^[A-Z][0-9]+[A-Z]?\\s+.+",
            ],
            "stat_block_markers": ["CREATURE", "HAZARD", "Initiative", "AC", "HP"],
            "read_aloud_markers": ["boxed text", "read-aloud"],
            "known_false_positive_markers": [
                "Adventure Toolbox",
                "Wandering Monsters",
                "Beyond Gauntlight",
            ],
        }
        self._write_json(path, payload)

    def _build_room_drafts(self, *, map_id: str | None) -> dict[str, Any]:
        room_key_paths = self._room_key_paths(map_id)
        items = []
        for path in room_key_paths:
            payload = self._read_json(path, {})
            current_map_id = str(payload.get("map_id") or path.stem)
            for room in payload.get("rooms") or []:
                items.append(self._draft_from_room(room, current_map_id, path, payload))
        return {
            "campaign_id": self.campaign_id(),
            "source": "promoted-room-key-seed",
            "items": items,
            "total": len(items),
            "updated_at": time(),
        }

    def _draft_from_room(
        self,
        room: dict[str, Any],
        map_id: str,
        path: Path,
        room_key_payload: dict[str, Any],
    ) -> dict[str, Any]:
        room_id = str(room.get("room_id") or "").strip()
        literal = room.get("literal_text") if isinstance(room.get("literal_text"), dict) else {}
        content_flags = self._content_flags(room)
        source_refs = self._source_refs(room, room_key_payload)
        issues = self._room_issue_codes(room, literal)
        confidence = "likely" if issues else "confirmed"
        return {
            "draft_id": f"{map_id}:{room_id}",
            "campaign_id": self.campaign_id(),
            "map_id": map_id,
            "room_id": room_id,
            "title": room.get("title") or room_id,
            "level": self._level_from_map_id(map_id),
            "source_room_key_path": path.relative_to(self.private_root()).as_posix(),
            "source_refs": source_refs,
            "confidence": confidence,
            "review_status": "unreviewed",
            "promotion_status": "draft",
            "reviewer_notes": "",
            "content_flags": content_flags,
            "fields": {
                "likely_order": room.get("likely_order"),
                "player_visible_description": room.get("player_visible_description") or "",
                "gm_description": room.get("gm_description") or "",
                "read_aloud": literal.get("read_aloud") or "",
                "general_text": literal.get("general_text") or "",
                "encounter_text": literal.get("encounter_text") or "",
                "monsters": room.get("monsters") or [],
                "npcs": room.get("npcs") or [],
                "traps": room.get("traps") or [],
                "haunts": room.get("haunts") or [],
                "hazards": room.get("hazards") or [],
                "afflictions": room.get("afflictions") or [],
                "loot": room.get("loot") or [],
                "quest_items": room.get("quest_items") or [],
                "secret_doors": room.get("secret_doors") or [],
                "visibility_notes": room.get("visibility_notes") or "",
                "detection_notes": room.get("detection_notes") or "",
                "dependencies": room.get("dependencies") or [],
                "encounter_refs": room.get("encounter_refs") or [],
                "image_candidates": room.get("image_candidates") or [],
            },
            "audit_codes": issues,
            "created_at": self._now_iso(),
            "updated_at": time(),
        }

    def _audit_room_drafts(self, payload: dict[str, Any]) -> dict[str, Any]:
        issues = []
        seen: dict[str, str] = {}
        room_ids = []
        for draft in payload.get("items") or []:
            room_id = str(draft.get("room_id") or "")
            room_ids.append(room_id)
            duplicate_key = f"{draft.get('map_id')}:{room_id}".casefold()
            if duplicate_key in seen:
                issues.append(self._issue(draft, "duplicate_room_id", "error", "Room ID appears more than once in this import run."))
            seen[duplicate_key] = draft.get("draft_id")
            fields = draft.get("fields") or {}
            if not fields.get("player_visible_description") and not fields.get("read_aloud"):
                issues.append(self._issue(draft, "missing_player_description", "warning", "No player-visible description or read-aloud text was extracted."))
            if not fields.get("gm_description") and not fields.get("general_text"):
                issues.append(self._issue(draft, "missing_gm_description", "warning", "No GM description or general source text was extracted."))
            if fields.get("secret_doors") and not fields.get("detection_notes"):
                issues.append(self._issue(draft, "secret_without_detection", "warning", "Secret content exists but detection notes are empty."))
            if fields.get("monsters") and not fields.get("encounter_refs"):
                issues.append(self._issue(draft, "monster_without_structured_ref", "info", "Monsters are listed but no structured encounter references were found."))
            if fields.get("hazards") and not fields.get("encounter_refs"):
                issues.append(self._issue(draft, "hazard_without_structured_ref", "info", "Hazards are listed but no structured encounter references were found."))
            source_text = " ".join(
                str(fields.get(key) or "")
                for key in ("read_aloud", "general_text", "encounter_text")
            )
            for marker in ("Adventure Toolbox", "Wandering Monsters", "Beyond Gauntlight"):
                if marker.casefold() in source_text.casefold():
                    issues.append(self._issue(draft, "possible_text_bleed", "error", f"Possible PDF bleed marker found: {marker}."))
        missing_gap_issues = self._room_gap_issues(payload.get("items") or [])
        issues.extend(missing_gap_issues)
        return {
            "campaign_id": self.campaign_id(),
            "run_id": payload.get("run_id"),
            "updated_at": time(),
            "summary": {
                "room_count": len(room_ids),
                "issue_count": len(issues),
            },
            "issues": issues,
        }

    def _image_match_audit(self, payload: dict[str, Any]) -> dict[str, Any]:
        issues = []
        for draft in payload.get("items") or []:
            fields = draft.get("fields") or {}
            if not fields.get("image_candidates"):
                issues.append(self._issue(draft, "no_image_candidate", "info", "No image candidate is linked to this room draft."))
        return {
            "campaign_id": self.campaign_id(),
            "issues": issues,
            "updated_at": time(),
        }

    def _entity_candidates(self, room_drafts: dict[str, Any]) -> dict[str, Any]:
        buckets: dict[str, set[str]] = {
            "rooms": set(),
            "monsters": set(),
            "npcs": set(),
            "traps": set(),
            "hazards": set(),
            "haunts": set(),
            "afflictions": set(),
            "quest_items": set(),
            "loot": set(),
        }
        for draft in room_drafts.get("items") or []:
            fields = draft.get("fields") or {}
            buckets["rooms"].add(str(draft.get("room_id") or ""))
            for key in buckets:
                if key == "rooms":
                    continue
                values = fields.get(key) or []
                if key == "loot":
                    values = list(values) + list(fields.get("quest_items") or [])
                for value in values:
                    buckets[key].add(str(value))
        return {
            "campaign_id": self.campaign_id(),
            "items": {
                key: sorted(value for value in values if value)
                for key, values in buckets.items()
            },
            "updated_at": time(),
        }

    def _promoted_room_from_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        fields = draft.get("fields") or {}
        room = {
            "room_id": draft.get("room_id"),
            "title": draft.get("title"),
            "likely_order": fields.get("likely_order"),
            "player_visible_description": fields.get("player_visible_description") or fields.get("read_aloud") or "",
            "gm_description": fields.get("gm_description") or fields.get("general_text") or "",
            "monsters": fields.get("monsters") or [],
            "npcs": fields.get("npcs") or [],
            "traps": fields.get("traps") or [],
            "haunts": fields.get("haunts") or [],
            "hazards": fields.get("hazards") or [],
            "afflictions": fields.get("afflictions") or [],
            "loot": fields.get("loot") or [],
            "quest_items": fields.get("quest_items") or [],
            "secret_doors": fields.get("secret_doors") or [],
            "visibility_notes": fields.get("visibility_notes") or "",
            "detection_notes": fields.get("detection_notes") or "",
            "dependencies": fields.get("dependencies") or [],
            "source": "; ".join(
                ref.get("label") or ref.get("path") or ""
                for ref in draft.get("source_refs") or []
                if ref
            ),
            "literal_text": {
                "read_aloud": fields.get("read_aloud") or "",
                "general_text": fields.get("general_text") or "",
                "encounter_text": fields.get("encounter_text") or "",
            },
            "encounter_refs": fields.get("encounter_refs") or [],
            "review": {
                "import_run_id": draft.get("run_id"),
                "draft_id": draft.get("draft_id"),
                "review_status": "promoted",
                "reviewer_notes": draft.get("reviewer_notes") or "",
                "promoted_at": self._now_iso(),
            },
        }
        return {key: value for key, value in room.items() if value not in (None, [], {})}

    def _apply_field_updates(self, item: dict[str, Any], updates: dict[str, Any]) -> None:
        fields = dict(item.get("fields") or {})
        allowed = set(fields.keys()) | {"title"}
        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "title":
                item["title"] = str(value or "").strip()
            else:
                fields[key] = value
        item["fields"] = fields

    def _append_review_log(self, run_id: str, draft_id: str, updates: dict[str, Any]) -> None:
        payload = self._read_run_json(run_id, "human-review-log.json") or {
            "campaign_id": self.campaign_id(),
            "run_id": run_id,
            "items": [],
        }
        payload.setdefault("items", []).append(
            {
                "draft_id": draft_id,
                "updates": updates,
                "created_at": self._now_iso(),
            }
        )
        self._write_run_json(run_id, "human-review-log.json", payload)

    def _refresh_run_counts(self, run_id: str) -> None:
        manifest = self.get_import_run(run_id)
        room_drafts = self._read_run_json(run_id, "room-drafts.json")
        if not manifest or not room_drafts:
            return
        items = room_drafts.get("items") or []
        manifest["room_draft_count"] = len(items)
        manifest["reviewed_count"] = len([item for item in items if item.get("review_status") != "unreviewed"])
        manifest["approved_count"] = len([item for item in items if item.get("review_status") == "approved"])
        manifest["promoted_count"] = len([item for item in items if item.get("review_status") == "promoted"])
        manifest["updated_at"] = time()
        if manifest["promoted_count"]:
            manifest["status"] = "partially_promoted"
        self._write_run_json(run_id, "import-manifest.json", manifest)

    def _ensure_extracted_manifest(self, pdf_path: Path, source_id: str) -> dict[str, Any]:
        root = self.extracted_reference_root() / source_id
        root.mkdir(parents=True, exist_ok=True)
        manifest_path = root / "manifest.json"
        current_hash = self._sha256(pdf_path)
        if manifest_path.exists():
            manifest = self._read_json(manifest_path, {})
            if manifest.get("sha256") == current_hash:
                return manifest
        warnings = []
        pages = []
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(pdf_path))
            for index, page in enumerate(reader.pages, start=1):
                pages.append(
                    {
                        "page_number": index,
                        "text": page.extract_text() or "",
                    }
                )
        except Exception as exc:  # pragma: no cover - optional dependency path
            warnings.append(f"Text extraction unavailable or failed: {exc}")
        pages_payload = {
            "source_id": source_id,
            "source_path": pdf_path.relative_to(self.private_root()).as_posix(),
            "pages": pages,
            "updated_at": time(),
        }
        self._write_json(root / "pages.json", pages_payload)
        pages_dir = root / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        for page in pages:
            page_path = pages_dir / f"page-{int(page['page_number']):03d}.txt"
            page_path.write_text(page.get("text") or "", encoding="utf-8")
        manifest = {
            "source_id": source_id,
            "source_path": pdf_path.relative_to(self.private_root()).as_posix(),
            "sha256": current_hash,
            "extractor": "pypdf-optional",
            "status": "extracted" if pages else "registered",
            "page_count": len(pages) or None,
            "warnings": warnings,
            "updated_at": time(),
        }
        self._write_json(manifest_path, manifest)
        return manifest

    def _room_key_paths(self, map_id: str | None) -> list[Path]:
        root = self.room_key_root()
        if not root.exists():
            return []
        paths = []
        normalized = (map_id or "").strip().casefold()
        for path in sorted(root.glob("*.json")):
            payload = self._read_json(path, {})
            if normalized and str(payload.get("map_id") or "").strip().casefold() != normalized:
                continue
            paths.append(path)
        return paths

    def _room_key_path_for_map(self, map_id: str) -> Path:
        for path in self._room_key_paths(map_id):
            return path
        slug = map_id.replace("level", "level-") if map_id.startswith("level") else map_id
        return self.room_key_root() / f"{slug}.json"

    def _source_refs(self, room: dict[str, Any], room_key_payload: dict[str, Any]) -> list[dict[str, Any]]:
        refs = []
        if room.get("source"):
            refs.append({"label": room.get("source"), "kind": "room-source"})
        for ref in room_key_payload.get("source_references") or []:
            if isinstance(ref, dict):
                refs.append(ref)
            else:
                refs.append({"label": str(ref), "kind": "room-key-source"})
        return refs

    def _content_flags(self, room: dict[str, Any]) -> dict[str, bool]:
        return {
            "monsters": bool(room.get("monsters")),
            "npcs": bool(room.get("npcs")),
            "traps": bool(room.get("traps")),
            "hazards": bool(room.get("hazards")),
            "haunts": bool(room.get("haunts")),
            "afflictions": bool(room.get("afflictions")),
            "loot": bool(room.get("loot") or room.get("quest_items")),
            "secret": bool(room.get("secret_doors")),
        }

    def _room_issue_codes(self, room: dict[str, Any], literal: dict[str, Any]) -> list[str]:
        issues = []
        if not room.get("player_visible_description") and not literal.get("read_aloud"):
            issues.append("missing_player_description")
        if not room.get("gm_description") and not literal.get("general_text"):
            issues.append("missing_gm_description")
        if room.get("secret_doors") and not room.get("detection_notes"):
            issues.append("secret_without_detection")
        return issues

    def _room_gap_issues(self, drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        issues = []
        by_prefix: dict[str, set[int]] = {}
        sample_draft: dict[str, Any] | None = None
        for draft in drafts:
            match = re.match(r"^([A-Z]+)(\d+)$", str(draft.get("room_id") or ""))
            if not match:
                continue
            by_prefix.setdefault(match.group(1), set()).add(int(match.group(2)))
            sample_draft = draft
        for prefix, numbers in by_prefix.items():
            if not numbers:
                continue
            for missing in sorted(set(range(min(numbers), max(numbers) + 1)) - numbers):
                issues.append(
                    {
                        "id": f"missing-room-{prefix}{missing}",
                        "entity_type": "room",
                        "entity_id": f"{prefix}{missing}",
                        "field": "room_id",
                        "severity": "warning",
                        "status": "missing",
                        "message": f"Room numbering skips {prefix}{missing}. Confirm whether this is intentional.",
                        "map_id": sample_draft.get("map_id") if sample_draft else None,
                    }
                )
        return issues

    def _issue(self, draft: dict[str, Any], code: str, severity: str, message: str) -> dict[str, Any]:
        return {
            "id": f"{draft.get('draft_id')}:{code}",
            "entity_type": "room",
            "entity_id": draft.get("room_id"),
            "draft_id": draft.get("draft_id"),
            "map_id": draft.get("map_id"),
            "field": code,
            "severity": severity,
            "status": "uncertain" if severity != "error" else "conflict",
            "message": message,
        }

    def _draft_search_text(self, draft: dict[str, Any]) -> str:
        fields = draft.get("fields") or {}
        values = [draft.get("room_id"), draft.get("title"), draft.get("review_status")]
        values.extend(fields.values())
        return json.dumps(values, ensure_ascii=False, default=str).casefold()

    def _level_from_map_id(self, map_id: str) -> str | None:
        match = re.search(r"(\d+)", map_id)
        return f"level-{match.group(1)}" if match else None

    def _source_id(self, path: Path) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", path.stem.casefold()).strip("-")
        return slug or hashlib.sha1(str(path).encode()).hexdigest()[:12]

    def _infer_source_role(self, path: Path) -> str:
        value = path.name.casefold()
        if "player" in value and "guide" in value:
            return "players-guide"
        if "bestiary" in value or "monster" in value:
            return "bestiary"
        return "adventure"

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _new_run_id(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _run_root(self, run_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", run_id).strip("-")
        return self.imports_root() / safe

    def _read_run_json(self, run_id: str, filename: str) -> dict[str, Any] | None:
        path = self._run_root(run_id) / filename
        if not path.exists():
            return None
        return self._read_json(path, {})

    def _write_run_json(self, run_id: str, filename: str, payload: dict[str, Any]) -> None:
        self._write_json(self._run_root(run_id) / filename, payload)

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

    def _room_sort_key(self, room_id: str) -> tuple[str, int, str]:
        match = re.match(r"^([A-Za-z]+)(\d+)(.*)$", room_id)
        if not match:
            return (room_id, 0, "")
        return (match.group(1), int(match.group(2)), match.group(3))


private_import_audit_service = PrivateImportAuditService()
