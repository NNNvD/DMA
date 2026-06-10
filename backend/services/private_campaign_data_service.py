from __future__ import annotations

import json
import tempfile
from pathlib import Path
from time import time
from typing import Any

from backend.config.local_paths import private_data_root
from backend.config.settings import settings


class PrivateCampaignDataService:
    """Read and write DMA live campaign data from private-local JSON files."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()

    def private_root(self) -> Path:
        return private_data_root(self.project_root, settings.dma_private_data_root)

    def campaign_id(self) -> str:
        return str(settings.dma_campaign_id or "abomination-vaults").strip()

    def campaign_root(self) -> Path:
        return self.private_root() / "campaigns" / self.campaign_id()

    def private_file_url(self, relative_path: str | None) -> str | None:
        if not relative_path:
            return None
        value = relative_path.strip()
        if value.startswith(("http://", "https://", "/")):
            return value
        return f"/api/live/private-file?path={value}"

    def safe_child(self, root: Path, relative_path: str) -> Path:
        root = root.resolve()
        target = (root / relative_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("Requested path is outside the configured private root") from exc
        return target

    def read_json(self, filename: str, default: dict[str, Any]) -> dict[str, Any]:
        path = self.campaign_root() / filename
        if not path.exists():
            return dict(default)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else dict(default)

    def write_json(self, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = self.campaign_root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / filename
        payload = dict(payload)
        payload.setdefault("campaign_id", self.campaign_id())
        payload["updated_at"] = time()
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=root,
            delete=False,
        ) as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
        return payload

    def campaign_overview(self) -> dict[str, Any]:
        return self.read_json(
            "campaign-overview.json",
            {"campaign_id": self.campaign_id(), "tabs": []},
        )

    def write_campaign_overview(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.write_json("campaign-overview.json", payload)

    def campaign_note_payload(self, tab_id: str, default_content: str) -> dict[str, Any] | None:
        payload = self.campaign_overview()
        tabs = payload.get("tabs") if isinstance(payload.get("tabs"), list) else []
        for tab in tabs:
            if str(tab.get("id") or "") == tab_id:
                return self._note_payload(tab)
        if tab_id == "overview":
            return self._note_payload(
                {
                    "id": "overview",
                    "title": "Campaign Overview",
                    "body_markdown": default_content,
                    "path": "campaign-overview.json#overview",
                    "updated_at": payload.get("updated_at"),
                }
            )
        return None

    def update_campaign_note(self, tab_id: str, content: str, default_title: str) -> dict[str, Any]:
        payload = self.campaign_overview()
        tabs = payload.get("tabs") if isinstance(payload.get("tabs"), list) else []
        for tab in tabs:
            if str(tab.get("id") or "") == tab_id:
                tab["body_markdown"] = content.rstrip() + "\n"
                tab["updated_at"] = time()
                break
        else:
            tab = {
                "id": tab_id,
                "label": default_title,
                "title": default_title,
                "path": f"campaign-overview.json#{tab_id}",
                "body_markdown": content.rstrip() + "\n",
                "updated_at": time(),
            }
            tabs.append(tab)
        payload["tabs"] = tabs
        self.write_campaign_overview(payload)
        return self._note_payload(tab)

    def sessions(self) -> dict[str, Any]:
        return self.read_json(
            "sessions.json",
            {"campaign_id": self.campaign_id(), "items": []},
        )

    def write_sessions(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.write_json("sessions.json", payload)

    def session_items(self) -> list[dict[str, Any]]:
        payload = self.sessions()
        items = payload.get("items")
        return items if isinstance(items, list) else []

    def session_payload(self, identifier: str) -> dict[str, Any] | None:
        normalized = identifier.strip().casefold()
        for item in self.session_items():
            candidates = [
                item.get("id"),
                item.get("path"),
                item.get("title"),
            ]
            if any(str(candidate or "").strip().casefold() == normalized for candidate in candidates):
                return self._note_payload(item)
        return None

    def update_session(self, identifier: str, content: str) -> dict[str, Any] | None:
        payload = self.sessions()
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        normalized = identifier.strip().casefold()
        for item in items:
            candidates = [item.get("id"), item.get("path"), item.get("title")]
            if any(str(candidate or "").strip().casefold() == normalized for candidate in candidates):
                item["body_markdown"] = content.rstrip() + "\n"
                item["updated_at"] = time()
                payload["items"] = items
                self.write_sessions(payload)
                return self._note_payload(item)
        return None

    def pcs(self) -> dict[str, Any]:
        return self.read_json("pcs.json", {"campaign_id": self.campaign_id(), "items": []})

    def npcs(self) -> dict[str, Any]:
        return self.read_json("npcs.json", {"campaign_id": self.campaign_id(), "items": []})

    def write_npcs(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.write_json("npcs.json", payload)

    def pc_items(self) -> list[dict[str, Any]]:
        items = self.pcs().get("items")
        return items if isinstance(items, list) else []

    def npc_items(self) -> list[dict[str, Any]]:
        items = self.npcs().get("items")
        return items if isinstance(items, list) else []

    def update_npc(self, npc_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
        payload = self.npcs()
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        for item in items:
            if int(item.get("id") or 0) != npc_id:
                continue
            details = dict(item.get("details") or {})
            for key, value in updates.items():
                if key == "campaign_encounters":
                    details[key] = [
                        entry.strip()
                        for entry in value
                        if isinstance(entry, str) and entry.strip()
                    ]
                    item[key] = details[key]
                elif key in {"vault_dm_notes", "vault_player_summary"}:
                    if value:
                        details[key] = value
                    else:
                        details.pop(key, None)
                elif isinstance(value, str):
                    if value.strip():
                        details[key] = value.strip()
                    else:
                        details.pop(key, None)
                    item[key] = details.get(key)
                elif value is None:
                    details.pop(key, None)
                    item.pop(key, None)
                else:
                    details[key] = value
                    item[key] = value
            item["details"] = details
            item["dm_notes"] = details.get("vault_dm_notes")
            item["player_facing"] = (
                details.get("vault_player_summary")
                or details.get("player_facing")
                or details.get("public_summary")
            )
            item["updated_at"] = time()
            payload["items"] = items
            self.write_npcs(payload)
            return item
        return None

    def _note_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        content = item.get("body_markdown") or item.get("content") or ""
        return {
            "source": "private-local",
            "root_path": str(self.private_root()),
            "path": item.get("path") or item.get("id") or "",
            "id": item.get("id"),
            "title": item.get("title") or item.get("label") or item.get("id") or "Untitled",
            "content": content,
            "updated_at": item.get("updated_at"),
        }


private_campaign_data_service = PrivateCampaignDataService()
