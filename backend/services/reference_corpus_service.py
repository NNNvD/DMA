from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from time import time
from typing import Any

from backend.services.private_campaign_data_service import private_campaign_data_service


AON_REFERENCE_CATEGORIES = [
    "creatures",
    "rules",
    "conditions",
    "actions",
    "spells",
    "feats",
    "items",
    "equipment",
    "treasure",
    "hazards",
    "afflictions",
    "diseases",
    "traits",
    "rituals",
    "subsystems",
]


class ReferenceCorpusService:
    """Normalize and search local private-reference corpus entries."""

    def __init__(self) -> None:
        self.data = private_campaign_data_service

    def private_root(self) -> Path:
        return self.data.private_root()

    def corpus_root(self) -> Path:
        return self.private_root() / "reference" / "aon"

    def list_categories(self) -> list[str]:
        return list(AON_REFERENCE_CATEGORIES)

    def ensure_corpus_structure(self) -> dict[str, Any]:
        root = self.corpus_root()
        root.mkdir(parents=True, exist_ok=True)
        categories = []
        for category in self.list_categories():
            category_root = root / category
            raw_root = category_root / "raw"
            raw_root.mkdir(parents=True, exist_ok=True)
            normalized_path = category_root / "normalized.json"
            if not normalized_path.exists():
                self._write_json(
                    normalized_path,
                    {
                        "category": category,
                        "items": [],
                        "updated_at": time(),
                        "parse_warnings": [],
                    },
                )
            categories.append(self.category_status(category))
        manifest = {
            "source": "Archives of Nethys",
            "mode": "local-cache",
            "categories": categories,
            "updated_at": time(),
            "notes": (
                "This corpus is deterministic local cache/index data. "
                "Populate raw category files explicitly before live lookup depends on them."
            ),
        }
        self._write_json(root / "manifest.json", manifest)
        return manifest

    def category_status(self, category: str) -> dict[str, Any]:
        normalized_path = self.corpus_root() / category / "normalized.json"
        payload = self._read_json(normalized_path, {"items": []})
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        return {
            "category": category,
            "item_count": len(items),
            "updated_at": payload.get("updated_at"),
            "parse_warning_count": len(payload.get("parse_warnings") or []),
        }

    def normalize_local_corpus(self) -> dict[str, Any]:
        self.ensure_corpus_structure()
        statuses = []
        for category in self.list_categories():
            statuses.append(self.normalize_category(category))
        manifest = {
            "source": "Archives of Nethys",
            "mode": "local-cache",
            "categories": statuses,
            "updated_at": time(),
        }
        self._write_json(self.corpus_root() / "manifest.json", manifest)
        return manifest

    def normalize_category(self, category: str) -> dict[str, Any]:
        if category not in self.list_categories():
            raise ValueError(f"Unsupported AoN reference category: {category}")
        category_root = self.corpus_root() / category
        raw_root = category_root / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, Any]] = []
        warnings: list[str] = []
        seen: set[str] = set()
        for path in sorted(raw_root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                warnings.append(f"{path.name}: invalid JSON: {exc}")
                continue
            raw_items = payload.get("items") if isinstance(payload, dict) else None
            if raw_items is None:
                raw_items = [payload]
            if not isinstance(raw_items, list):
                warnings.append(f"{path.name}: expected an object or items list")
                continue
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = self.normalize_entry(raw, category=category, source_path=path)
                if not item.get("name"):
                    warnings.append(f"{path.name}: skipped unnamed entry")
                    continue
                key = str(item["id"])
                if key in seen:
                    warnings.append(f"{path.name}: duplicate normalized id {key}")
                    continue
                seen.add(key)
                items.append(item)
        items.sort(key=lambda item: (str(item.get("name") or "").casefold(), str(item.get("id") or "")))
        payload = {
            "category": category,
            "items": items,
            "parse_warnings": warnings,
            "updated_at": time(),
        }
        self._write_json(category_root / "normalized.json", payload)
        return {
            "category": category,
            "item_count": len(items),
            "updated_at": payload["updated_at"],
            "parse_warning_count": len(warnings),
        }

    def normalize_entry(
        self,
        raw: dict[str, Any],
        *,
        category: str,
        source_path: Path | None = None,
    ) -> dict[str, Any]:
        name = str(raw.get("name") or raw.get("title") or "").strip()
        url = str(raw.get("url") or raw.get("source_url") or "").strip()
        aon_id = raw.get("aon_id") or raw.get("id") or self._id_from_url(url)
        normalized_id = self._stable_id(category, name, aon_id, url)
        rules_text = self._text_from_raw(raw)
        summary = str(raw.get("summary") or raw.get("summary_text") or "").strip()
        if not summary:
            summary = self._first_sentence(rules_text)
        item = {
            "id": normalized_id,
            "aon_id": str(aon_id or "").strip() or None,
            "name": name,
            "category": category,
            "level": raw.get("level"),
            "traits": self._listify(raw.get("traits")),
            "source": raw.get("source") or raw.get("book") or "Archives of Nethys",
            "url": url,
            "summary_text": summary,
            "rules_text": rules_text,
            "stat_block": raw.get("stat_block") or raw.get("content") or "",
            "image_url": raw.get("image_url") or raw.get("image") or None,
            "parse_warnings": self._listify(raw.get("parse_warnings")),
        }
        if source_path is not None:
            item["cache_path"] = source_path.relative_to(self.private_root()).as_posix()
        return {key: value for key, value in item.items() if value not in (None, "", [], {})}

    def search(
        self,
        *,
        q: str = "",
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = q.strip().casefold()
        categories = [category] if category else self.list_categories()
        items: list[dict[str, Any]] = []
        for cat in categories:
            payload = self._read_json(self.corpus_root() / cat / "normalized.json", {"items": []})
            for item in payload.get("items") or []:
                if query and query not in self._search_text(item):
                    continue
                items.append(item)
        items.sort(key=lambda item: (0 if str(item.get("name") or "").casefold() == query else 1, str(item.get("name") or "")))
        return items[:limit]

    def get(self, reference_id: str) -> dict[str, Any] | None:
        normalized = reference_id.strip().casefold()
        for item in self.search(limit=100000):
            if str(item.get("id") or "").casefold() == normalized:
                return item
        return None

    def _stable_id(self, category: str, name: str, aon_id: Any, url: str) -> str:
        if aon_id:
            return f"aon:{category}:{aon_id}"
        slug = re.sub(r"[^a-z0-9]+", "-", (name or url or "entry").casefold()).strip("-")
        return f"aon:{category}:{slug or 'entry'}"

    def _id_from_url(self, url: str) -> str | None:
        match = re.search(r"[?&]ID=(\d+)", url)
        return match.group(1) if match else None

    def _text_from_raw(self, raw: dict[str, Any]) -> str:
        candidates = [
            raw.get("rules_text"),
            raw.get("text"),
            raw.get("content"),
            raw.get("body"),
            raw.get("description"),
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return re.sub(r"\s+", " ", value).strip()
        return ""

    def _first_sentence(self, text: str) -> str:
        if not text:
            return ""
        match = re.search(r"^(.{1,220}?)(?:\.|\n|$)", text)
        return (match.group(1) if match else text[:220]).strip()

    def _listify(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]
        return [str(value).strip()]

    def _search_text(self, item: dict[str, Any]) -> str:
        return json.dumps(
            [
                item.get("id"),
                item.get("name"),
                item.get("category"),
                item.get("traits"),
                item.get("source"),
                item.get("summary_text"),
                item.get("rules_text"),
            ],
            ensure_ascii=False,
            default=str,
        ).casefold()

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


reference_corpus_service = ReferenceCorpusService()
