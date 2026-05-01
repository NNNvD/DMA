from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_note_import_service import ParsedEntityNote, ParsedRelationship
from backend.services.campaign_note_import_service import campaign_note_import_service
from backend.services.obsidian_markdown import replace_wikilinks, split_frontmatter
from backend.services.pc_sheet_import_service import pc_sheet_import_service
from backend.services.session_update_service import session_update_service


MANAGED_BLOCK_RE = re.compile(
    r"<!--\s*dma:(?P<kind>managed|editable):start\s+(?P<name>[\w-]+)\s*-->\n?"
    r"(?P<content>.*?)"
    r"<!--\s*dma:(?P=kind):end\s+(?P=name)\s*-->",
    re.DOTALL,
)
HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass
class VaultSyncCounts:
    files_seen: int = 0
    files_synced: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    entity_notes: int = 0
    document_notes: int = 0


class ObsidianVaultSyncService:
    def iter_vault_notes(self, vault_path: str) -> list[Path]:
        root = Path(vault_path).expanduser()
        if not root.exists():
            raise ValueError(f"Vault path does not exist: {root}")
        return sorted(
            path
            for path in root.rglob("*.md")
            if path.is_file() and path.name != "Index.md"
        )

    async def import_vault(
        self,
        db: AsyncSession,
        *,
        vault_path: str,
        include_campaign_entities: bool = True,
        include_campaign_notes: bool = True,
        include_pc_sheets: bool = True,
        include_session_logs: bool = True,
    ) -> dict[str, Any]:
        root = Path(vault_path).expanduser()
        counts = VaultSyncCounts()
        files: list[dict[str, Any]] = []
        notes = sorted(
            self.iter_vault_notes(vault_path),
            key=lambda path: self._sync_order(path),
        )
        for path in notes:
            counts.files_seen += 1
            if path.suffix != ".md" or path.name.endswith(".base"):
                counts.files_skipped += 1
                continue
            relative = path.relative_to(root).as_posix()
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                counts.files_failed += 1
                files.append({"path": relative, "status": "failed", "error": str(exc)})
                continue

            frontmatter, body = split_frontmatter(content)
            if not frontmatter.get("vault_sync"):
                counts.files_skipped += 1
                files.append({"path": relative, "status": "skipped", "reason": "vault_sync disabled"})
                continue

            dma_kind = str(frontmatter.get("dma_kind") or "").strip().lower()
            document_kind = str(frontmatter.get("document_kind") or "").strip().lower()
            try:
                if dma_kind == "campaign_entity":
                    if not include_campaign_entities:
                        counts.files_skipped += 1
                        files.append({"path": relative, "status": "skipped", "reason": "campaign entities disabled"})
                        continue
                    result = await self._sync_entity_note(db, path=path, frontmatter=frontmatter, body=body)
                    counts.entity_notes += 1
                elif dma_kind == "document":
                    if document_kind == "campaign_note" and not include_campaign_notes:
                        counts.files_skipped += 1
                        files.append({"path": relative, "status": "skipped", "reason": "campaign notes disabled"})
                        continue
                    if document_kind == "pc_sheet" and not include_pc_sheets:
                        counts.files_skipped += 1
                        files.append({"path": relative, "status": "skipped", "reason": "pc sheets disabled"})
                        continue
                    if document_kind == "session_log" and not include_session_logs:
                        counts.files_skipped += 1
                        files.append({"path": relative, "status": "skipped", "reason": "session logs disabled"})
                        continue
                    result = await self._sync_document_note(
                        db,
                        path=path,
                        frontmatter=frontmatter,
                        body=body,
                    )
                    if result is None:
                        counts.files_skipped += 1
                        files.append({"path": relative, "status": "skipped", "reason": f"document kind {document_kind or 'unknown'} not sync-enabled"})
                        continue
                    counts.document_notes += 1
                else:
                    counts.files_skipped += 1
                    files.append({"path": relative, "status": "skipped", "reason": "unsupported note kind"})
                    continue
            except (LookupError, OSError, ValueError) as exc:
                counts.files_failed += 1
                files.append({"path": relative, "status": "failed", "error": str(exc)})
                continue

            counts.files_synced += 1
            files.append({"path": relative, "status": "synced", **result})

        return {
            "vault_path": str(root),
            "summary": {
                "files_seen": counts.files_seen,
                "files_synced": counts.files_synced,
                "files_skipped": counts.files_skipped,
                "files_failed": counts.files_failed,
                "entity_notes": counts.entity_notes,
                "document_notes": counts.document_notes,
            },
            "files": files,
        }

    async def _sync_entity_note(
        self,
        db: AsyncSession,
        *,
        path: Path,
        frontmatter: dict[str, Any],
        body: str,
    ) -> dict[str, Any]:
        entity_type = str(frontmatter.get("entity_type") or "").strip().lower()
        if not entity_type:
            raise ValueError("Entity note missing entity_type.")
        name = self._note_title(frontmatter, body=body, path=path)
        parsed = ParsedEntityNote(
            entity_type=entity_type,
            name=name,
            stable_key=self._optional_text(frontmatter.get("stable_key")),
            summary=self._optional_text(frontmatter.get("summary")),
            description=self._optional_text(self._editable_block(body, "dm-working-notes")),
            details=self._entity_details_from_note(frontmatter, body=body),
            tags=self._string_list(frontmatter.get("tags")),
            current_location_reference=self._reference_name(frontmatter.get("current_location")),
            parent_reference=self._reference_name(frontmatter.get("parent")),
            owner_reference=self._reference_name(frontmatter.get("owner")),
            relationships=self._relationship_payload(frontmatter),
        )
        result = await campaign_note_import_service.apply_parsed_entities(db, [parsed])
        return {
            "kind": "campaign_entity",
            "entity_type": entity_type,
            "name": name,
            "warnings": result["warnings"],
        }

    async def _sync_document_note(
        self,
        db: AsyncSession,
        *,
        path: Path,
        frontmatter: dict[str, Any],
        body: str,
    ) -> dict[str, Any] | None:
        document_kind = str(frontmatter.get("document_kind") or "").strip().lower()
        title = self._note_title(frontmatter, body=body, path=path)
        source_name = path.as_posix()
        document_url = str(path.resolve())
        if document_kind == "campaign_note":
            editable = self._editable_block(body, "editable-source")
            if not editable:
                raise ValueError("Campaign note is missing DMA editable source block.")
            result = await campaign_note_import_service.import_note(
                db,
                title=title,
                content=editable,
                source_name=source_name,
                document_url=document_url,
                default_tags=self._string_list(frontmatter.get("tags")),
                store_document=True,
            )
            return {"kind": "campaign_note", "title": title, "warnings": result.get("warnings", [])}
        if document_kind == "pc_sheet":
            editable = self._editable_block(body, "editable-source")
            if not editable:
                raise ValueError("PC sheet note is missing DMA editable source block.")
            result = await pc_sheet_import_service.import_sheet(
                db,
                title=title,
                content=editable,
                source_name=source_name,
                document_url=document_url,
                default_tags=self._string_list(frontmatter.get("tags")),
                store_document=True,
            )
            return {"kind": "pc_sheet", "title": title, "warnings": result.get("warnings", [])}
        if document_kind == "session_log":
            editable = self._editable_block(body, "editable-source")
            if not editable:
                raise ValueError("Session log note is missing DMA editable source block.")
            result = await session_update_service.import_session_update(
                db,
                title=title,
                content=editable,
                source_name=source_name,
                document_url=document_url,
                default_tags=self._string_list(frontmatter.get("tags")),
                store_document=True,
            )
            return {"kind": "session_log", "title": title, "warnings": result.get("warnings", [])}
        return None

    def _entity_details_from_note(
        self, frontmatter: dict[str, Any], *, body: str
    ) -> dict[str, Any]:
        details = self._flattened_prefix_payload(frontmatter, "details")
        dm_working_notes = self._editable_block(body, "dm-working-notes")
        if dm_working_notes:
            details["vault_dm_notes"] = dm_working_notes
        player_summary = self._editable_block(body, "player-facing-summary")
        if player_summary:
            details["vault_player_summary"] = player_summary
        session_changes = self._editable_block(body, "session-changes")
        if session_changes:
            details["vault_session_changes"] = self._bullet_or_line_list(session_changes)
        return details

    def _relationship_payload(self, frontmatter: dict[str, Any]) -> list[ParsedRelationship]:
        relationships: list[ParsedRelationship] = []
        items: list[dict[str, Any]] = []
        value = frontmatter.get("relationships")
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
        for item in self._flattened_indexed_payloads(frontmatter, "relationships"):
            items.append(item)
        for item in items:
            if not isinstance(item, dict):
                continue
            relationship_type = self._optional_text(item.get("type"))
            target_reference = self._reference_name(item.get("target"))
            if not relationship_type or not target_reference:
                continue
            relationships.append(
                ParsedRelationship(
                    relationship_type=relationship_type,
                    target_reference=target_reference,
                    notes=self._optional_text(item.get("notes")),
                )
            )
        return relationships

    def _note_title(self, frontmatter: dict[str, Any], *, body: str, path: Path) -> str:
        explicit = self._optional_text(frontmatter.get("title"))
        if explicit:
            return explicit
        match = HEADING_RE.search(body)
        if match:
            return match.group(1).strip()
        return path.stem

    def _editable_block(self, body: str, name: str) -> str:
        for match in MANAGED_BLOCK_RE.finditer(body):
            if match.group("kind") != "editable":
                continue
            if match.group("name") != name:
                continue
            return match.group("content").strip()
        return ""

    def _reference_name(self, value: Any) -> str | None:
        text = self._optional_text(value)
        if not text:
            return None
        return replace_wikilinks(text).strip()

    def _optional_text(self, value: Any) -> str | None:
        if value in (None, "", [], {}):
            return None
        text = str(value).strip()
        return text or None

    def _string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    def _bullet_or_line_list(self, text: str) -> list[str]:
        values: list[str] = []
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                stripped = stripped[2:].strip()
            values.append(stripped)
        return values

    def _flattened_prefix_payload(
        self, frontmatter: dict[str, Any], prefix: str
    ) -> dict[str, Any]:
        payload = dict(frontmatter.get(prefix) or {})
        needle = f"{prefix}_"
        for key, value in frontmatter.items():
            if not key.startswith(needle):
                continue
            nested_key = key[len(needle) :]
            if nested_key:
                payload[nested_key] = value
        return payload

    def _flattened_indexed_payloads(
        self, frontmatter: dict[str, Any], prefix: str
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        needle = f"{prefix}_"
        for key, value in frontmatter.items():
            if not key.startswith(needle):
                continue
            remainder = key[len(needle) :]
            index, separator, field_name = remainder.partition("_")
            if not separator or not index or not field_name:
                continue
            grouped.setdefault(index, {})[field_name] = value
        return [grouped[index] for index in sorted(grouped)]

    def _sync_order(self, path: Path) -> tuple[int, str]:
        parts = path.parts
        if "Campaign" in parts:
            return (20, path.as_posix())
        if "Notes" in parts or "Sheets" in parts or "Sessions" in parts:
            return (10, path.as_posix())
        return (30, path.as_posix())


obsidian_vault_sync_service = ObsidianVaultSyncService()
