from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_service import campaign_service
from backend.services.ingestion_service import ingestion_service

ENTITY_HEADER_RE = re.compile(
    r"^(?:##\s*)?"
    r"(artifact|calendar|event|faction|holiday|location|npc|pc|shop)"
    r"\s*:\s*(.+)$",
    re.IGNORECASE,
)

DETAIL_FIELD_MAP = {
    "location": {
        "category": "category",
        "environment": "environment",
        "languages": "languages",
        "region": "region",
        "secrets": "secrets",
    },
    "faction": {
        "agenda": "agenda",
        "fronts": "fronts",
        "headquarters": "headquarters",
        "languages": "languages",
        "reputation": "reputation",
    },
    "pc": {
        "goals": "goals",
        "hooks": "hooks",
        "languages": "languages",
        "pronouns": "pronouns",
        "role": "role",
        "scripts": "scripts",
        "status": "status",
    },
    "npc": {
        "goals": "goals",
        "hooks": "hooks",
        "languages": "languages",
        "pronouns": "pronouns",
        "role": "role",
        "scripts": "scripts",
        "status": "status",
    },
    "artifact": {
        "artifact type": "artifact_type",
        "attuned to": "attuned_to",
        "properties": "properties",
        "rarity": "rarity",
    },
    "event": {
        "consequences": "consequences",
        "scheduled for": "scheduled_for",
        "status": "status",
        "timeline position": "timeline_position",
    },
    "calendar": {
        "current date": "current_date",
        "months": "months",
        "seasons": "seasons",
        "weekdays": "weekdays",
    },
    "holiday": {
        "date label": "date_label",
        "recurrence": "recurrence",
        "traditions": "traditions",
    },
    "shop": {
        "category": "category",
        "owner name": "owner_name",
        "services": "services",
        "stock summary": "stock_summary",
    },
}

LIST_DETAIL_FIELDS = {
    "attuned_to",
    "consequences",
    "fronts",
    "goals",
    "hooks",
    "languages",
    "months",
    "properties",
    "scripts",
    "seasons",
    "services",
    "secrets",
    "stock_summary",
    "traditions",
    "weekdays",
}


@dataclass
class ParsedRelationship:
    relationship_type: str
    target_reference: str
    notes: Optional[str] = None


@dataclass
class ParsedEntityNote:
    entity_type: str
    name: str
    stable_key: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    current_location_reference: Optional[str] = None
    parent_reference: Optional[str] = None
    owner_reference: Optional[str] = None
    relationships: list[ParsedRelationship] = field(default_factory=list)


class CampaignNoteImportService:
    async def import_note(
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
        parsed_entities = self.parse_content(content, default_tags=default_tags)
        if not parsed_entities:
            raise ValueError(
                "No importable campaign entities found. Use blocks like 'Location: Greyhaven'."
            )

        result = await self.apply_parsed_entities(db, parsed_entities)

        stored_document = None
        if store_document:
            stored_document = await ingestion_service.ingest_document(
                db,
                title=title,
                kind="campaign_note",
                content=content,
                summary=self._document_summary(parsed_entities),
                source_name=source_name,
                url=document_url,
                dedupe_on_url=bool(document_url),
            )

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
            **result,
        }

    async def apply_parsed_entities(
        self, db: AsyncSession, parsed_entities: list[ParsedEntityNote]
    ) -> dict[str, Any]:
        created_entities = 0
        updated_entities = 0
        imported_entities = []
        for parsed_entity in parsed_entities:
            entity, created = await campaign_service.upsert_entity(
                db,
                entity_type=parsed_entity.entity_type,
                name=parsed_entity.name,
                stable_key=parsed_entity.stable_key,
                summary=parsed_entity.summary,
                description=parsed_entity.description,
                details=parsed_entity.details,
                tags=parsed_entity.tags,
            )
            imported_entities.append(entity)
            if created:
                created_entities += 1
            else:
                updated_entities += 1

        created_relationships = 0
        updated_relationships = 0
        warnings: list[str] = []
        finalized_entities = []
        for parsed_entity, entity in zip(parsed_entities, imported_entities):
            parent_entity_id = await self._resolve_reference_id(
                db, parsed_entity.parent_reference
            )
            current_location_id = await self._resolve_reference_id(
                db,
                parsed_entity.current_location_reference,
                entity_types=campaign_service.location_entity_types,
            )
            owner_entity_id = await self._resolve_reference_id(
                db, parsed_entity.owner_reference
            )

            if parsed_entity.parent_reference and parent_entity_id is None:
                warnings.append(
                    f"Could not resolve parent reference '{parsed_entity.parent_reference}' for {parsed_entity.name}."
                )
            if parsed_entity.current_location_reference and current_location_id is None:
                warnings.append(
                    f"Could not resolve location reference '{parsed_entity.current_location_reference}' for {parsed_entity.name}."
                )
            if parsed_entity.owner_reference and owner_entity_id is None:
                warnings.append(
                    f"Could not resolve owner reference '{parsed_entity.owner_reference}' for {parsed_entity.name}."
                )

            if (
                parent_entity_id is not None
                or current_location_id is not None
                or owner_entity_id is not None
            ):
                entity = await campaign_service.update_entity(
                    entity.id,
                    db,
                    parent_entity_id=parent_entity_id,
                    current_location_id=current_location_id,
                    owner_entity_id=owner_entity_id,
                )

            for relationship in parsed_entity.relationships:
                target = await campaign_service.find_entity_by_reference(
                    db, relationship.target_reference
                )
                if target is None:
                    warnings.append(
                        f"Could not resolve relationship target '{relationship.target_reference}' for {parsed_entity.name}."
                    )
                    continue
                _, created = await campaign_service.ensure_relationship(
                    db,
                    source_entity_id=entity.id,
                    target_entity_id=target.id,
                    relationship_type=relationship.relationship_type,
                    notes=relationship.notes,
                )
                if created:
                    created_relationships += 1
                else:
                    updated_relationships += 1

            reloaded = await campaign_service.get_entity(entity.id, db)
            if reloaded is not None:
                finalized_entities.append(
                    campaign_service.entity_to_dict(
                        reloaded, include_relationships=True
                    )
                )

        return {
            "summary": {
                "created_entities": created_entities,
                "updated_entities": updated_entities,
                "created_relationships": created_relationships,
                "updated_relationships": updated_relationships,
            },
            "entities": finalized_entities,
            "warnings": warnings,
        }

    def parse_content(
        self, content: str, *, default_tags: Optional[list[str]] = None
    ) -> list[ParsedEntityNote]:
        blocks = self._split_blocks(content)
        parsed_entities: list[ParsedEntityNote] = []
        for block in blocks:
            parsed = self._parse_block(block, default_tags=default_tags)
            if parsed is not None:
                parsed_entities.append(parsed)
        return parsed_entities

    def _split_blocks(self, content: str) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        ready_for_header = True
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                if current:
                    current.append(line)
                ready_for_header = True
                continue
            if ready_for_header and ENTITY_HEADER_RE.match(stripped):
                if current:
                    blocks.append(current)
                current = [line]
                ready_for_header = False
                continue
            if current:
                current.append(line)
                ready_for_header = False
        if current:
            blocks.append(current)
        return blocks

    def _parse_block(
        self, lines: list[str], *, default_tags: Optional[list[str]] = None
    ) -> Optional[ParsedEntityNote]:
        if not lines:
            return None
        header = lines[0].strip()
        header_match = ENTITY_HEADER_RE.match(header)
        if not header_match:
            return None

        entity_type = header_match.group(1).lower()
        name = header_match.group(2).strip()
        raw_fields: dict[str, str] = {}
        description_lines: list[str] = []
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("- "):
                stripped = stripped[2:].strip()
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                normalized_key = key.strip().lower()
                existing = raw_fields.get(normalized_key)
                raw_fields[normalized_key] = (
                    f"{existing}; {value.strip()}" if existing else value.strip()
                )
            else:
                description_lines.append(stripped)

        details = self._extract_details(entity_type, raw_fields)
        description = raw_fields.get("description")
        if description_lines:
            extra_description = " ".join(description_lines)
            description = (
                f"{description}\n{extra_description}"
                if description
                else extra_description
            )

        tags = campaign_service._normalize_strings(
            [*(default_tags or []), *self._split_items(raw_fields.get("tags"))]
        )
        return ParsedEntityNote(
            entity_type=entity_type,
            name=name,
            stable_key=raw_fields.get("stable key") or raw_fields.get("stable_key"),
            summary=raw_fields.get("summary"),
            description=description,
            details=details,
            tags=tags,
            current_location_reference=(
                raw_fields.get("current location") or raw_fields.get("location")
            ),
            parent_reference=raw_fields.get("parent"),
            owner_reference=raw_fields.get("owner"),
            relationships=self._parse_relationships(raw_fields.get("relationships")),
        )

    def _extract_details(
        self, entity_type: str, raw_fields: dict[str, str]
    ) -> dict[str, Any]:
        detail_keys = DETAIL_FIELD_MAP.get(entity_type, {})
        details: dict[str, Any] = {}
        for raw_key, detail_key in detail_keys.items():
            value = raw_fields.get(raw_key)
            if not value:
                continue
            if detail_key in LIST_DETAIL_FIELDS:
                details[detail_key] = self._split_items(value)
            elif detail_key == "current_date":
                details[detail_key] = self._parse_mapping(value)
            else:
                details[detail_key] = value
        return details

    def _parse_relationships(self, value: Optional[str]) -> list[ParsedRelationship]:
        if not value:
            return []
        relationships: list[ParsedRelationship] = []
        for chunk in re.split(r"\s*;\s*", value):
            if not chunk:
                continue
            parts = [part.strip() for part in chunk.split("->", 2)]
            if len(parts) >= 2 and parts[0] and parts[1]:
                relationships.append(
                    ParsedRelationship(
                        relationship_type=parts[0],
                        target_reference=parts[1],
                        notes=parts[2] if len(parts) == 3 and parts[2] else None,
                    )
                )
        return relationships

    def _split_items(self, value: Optional[str]) -> list[str]:
        if not value:
            return []
        return campaign_service._normalize_strings(re.split(r"\s*[;,]\s*", value))

    def _parse_mapping(self, value: str) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for chunk in re.split(r"\s*[;,]\s*", value):
            if not chunk:
                continue
            if "=" in chunk:
                key, raw_value = chunk.split("=", 1)
            elif ":" in chunk:
                key, raw_value = chunk.split(":", 1)
            else:
                mapping.setdefault("label", chunk.strip())
                continue
            parsed_value = raw_value.strip()
            if parsed_value.isdigit():
                mapping[key.strip()] = int(parsed_value)
            else:
                mapping[key.strip()] = parsed_value
        return mapping

    async def _resolve_reference_id(
        self,
        db: AsyncSession,
        reference: Optional[str],
        *,
        entity_types: Optional[set[str]] = None,
    ) -> Optional[int]:
        if not reference:
            return None
        entity = await campaign_service.find_entity_by_reference(
            db,
            reference,
            entity_types=entity_types,
        )
        return entity.id if entity is not None else None

    def _document_summary(self, parsed_entities: list[ParsedEntityNote]) -> str:
        preview = ", ".join(
            f"{entity.entity_type}:{entity.name}" for entity in parsed_entities[:5]
        )
        return (
            f"Imported {len(parsed_entities)} campaign entities from notes. "
            f"Preview: {preview}"
        )


campaign_note_import_service = CampaignNoteImportService()
