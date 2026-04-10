from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_note_import_service import (
    ENTITY_HEADER_RE,
    campaign_note_import_service,
)
from backend.services.campaign_service import campaign_service
from backend.services.ingestion_service import ingestion_service


@dataclass
class ParsedSessionUpdate:
    metadata: dict[str, str] = field(default_factory=dict)
    changelog: list[str] = field(default_factory=list)


class SessionUpdateService:
    async def import_session_update(
        self,
        db: AsyncSession,
        *,
        title: str,
        content: str,
        source_name: Optional[str] = None,
        document_url: Optional[str] = None,
        default_tags: Optional[list[str]] = None,
        store_document: bool = True,
    ) -> dict[str, Any]:
        parsed_meta = self.parse_metadata(content)
        parsed_entities = self.parse_entities(content, default_tags=default_tags)
        entity_result = (
            await campaign_note_import_service.apply_parsed_entities(
                db, parsed_entities
            )
            if parsed_entities
            else {
                "summary": {
                    "created_entities": 0,
                    "updated_entities": 0,
                    "created_relationships": 0,
                    "updated_relationships": 0,
                },
                "entities": [],
                "warnings": [],
            }
        )

        stored_document = None
        if store_document:
            stored_document = await ingestion_service.ingest_document(
                db,
                title=title,
                kind="session_log",
                content=content,
                summary=self._document_summary(title, parsed_meta),
                source_name=source_name,
                url=document_url,
                dedupe_on_url=bool(document_url),
            )

        created_entities = entity_result["summary"]["created_entities"]
        updated_entities = entity_result["summary"]["updated_entities"]
        warnings = list(entity_result["warnings"])

        calendar_payload = None
        current_date = self._parse_mapping(parsed_meta.metadata.get("current date"))
        if current_date or parsed_meta.metadata.get("calendar"):
            calendar_name = parsed_meta.metadata.get("calendar") or "Campaign Calendar"
            calendar, created = await campaign_service.upsert_entity(
                db,
                entity_type="calendar",
                name=calendar_name,
                details={"current_date": current_date} if current_date else {},
            )
            calendar_payload = campaign_service.entity_to_dict(calendar)
            if created:
                created_entities += 1
            else:
                updated_entities += 1

        session_event = None
        if parsed_meta.changelog:
            session_event, created = await campaign_service.upsert_entity(
                db,
                entity_type="event",
                name=title,
                summary=parsed_meta.metadata.get("summary"),
                details={
                    "timeline_position": parsed_meta.metadata.get("timeline position")
                    or "session-update",
                    "scheduled_for": parsed_meta.metadata.get("scheduled for")
                    or parsed_meta.metadata.get("current date"),
                    "status": "resolved",
                    "consequences": parsed_meta.changelog,
                },
                tags=default_tags,
            )
            if created:
                created_entities += 1
            else:
                updated_entities += 1

        return {
            "document": (
                {
                    "id": stored_document.id,
                    "title": stored_document.title,
                    "kind": stored_document.kind,
                    "source_name": stored_document.source_name,
                }
                if stored_document is not None
                else None
            ),
            "summary": {
                "created_entities": created_entities,
                "updated_entities": updated_entities,
                "created_relationships": entity_result["summary"][
                    "created_relationships"
                ],
                "updated_relationships": entity_result["summary"][
                    "updated_relationships"
                ],
            },
            "entities": entity_result["entities"],
            "calendar": calendar_payload,
            "session_event": (
                campaign_service.entity_to_dict(session_event)
                if session_event is not None
                else None
            ),
            "changelog": parsed_meta.changelog,
            "warnings": warnings,
        }

    def parse_metadata(self, content: str) -> ParsedSessionUpdate:
        metadata: dict[str, str] = {}
        changelog: list[str] = []
        in_changelog = False
        seen_entity_header = False
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("##") and ENTITY_HEADER_RE.match(stripped):
                seen_entity_header = True
                in_changelog = False
                continue
            if stripped.lower() == "## changelog":
                in_changelog = True
                continue
            if in_changelog:
                changelog.append(
                    stripped[2:].strip() if stripped.startswith("- ") else stripped
                )
                continue
            if seen_entity_header:
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                metadata[key.strip().lower()] = value.strip()
        return ParsedSessionUpdate(metadata=metadata, changelog=changelog)

    def parse_entities(
        self, content: str, *, default_tags: Optional[list[str]] = None
    ) -> list[Any]:
        entity_lines: list[str] = []
        capture = False
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if stripped.lower() == "## changelog":
                capture = False
                continue
            if stripped.startswith("##") and ENTITY_HEADER_RE.match(stripped):
                capture = True
            if capture:
                entity_lines.append(raw_line)
        if not entity_lines:
            return []
        return campaign_note_import_service.parse_content(
            "\n".join(entity_lines),
            default_tags=default_tags,
        )

    def _parse_mapping(self, value: Optional[str]) -> dict[str, Any]:
        if not value:
            return {}
        return campaign_note_import_service._parse_mapping(value)

    def _document_summary(self, title: str, parsed_meta: ParsedSessionUpdate) -> str:
        if parsed_meta.changelog:
            return f"Session update '{title}' with {len(parsed_meta.changelog)} changelog entries."
        return f"Session update '{title}'."


session_update_service = SessionUpdateService()
