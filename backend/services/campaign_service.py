from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.campaign import (
    CampaignEntity,
    CampaignEvent,
    CampaignFaction,
    CampaignImport,
    CampaignLocation,
    CampaignNPC,
    CampaignPC,
    CampaignRelationship,
)

SUPPORTED_ENTITY_TYPES = {"pc", "npc", "faction", "location", "event"}
ACYCLIC_RELATIONSHIP_TYPES = {"located_in", "part_of"}
LOCATION_RELATIONSHIP_TYPES = {"located_in", "occurs_at", "headquartered_in"}
PC_TO_FACTION_RELATIONSHIPS = {
    "member_of",
    "affiliated_with",
    "allied_with",
    "opposed_to",
}
SECTION_HEADING_RE = re.compile(r"^##\s+(?P<heading>.+?)\s*$", re.MULTILINE)
ENTITY_HEADING_RE = re.compile(
    r"^(?P<entity_type>pc|npc|faction|location|event)\s*:\s*(?P<name>.+)$",
    re.IGNORECASE,
)
RELATIONSHIP_LINE_RE = re.compile(r"^\|\s*(?P<content>.+?)\s*\|$")
METADATA_LINE_RE = re.compile(r"^\s*-\s*(?P<key>[^:]+):\s*(?P<value>.+?)\s*$")
MULTISPACE_RE = re.compile(r"\s+")
NON_SLUG_RE = re.compile(r"[^a-z0-9-]+")

DETAIL_FIELDS: dict[str, tuple[str, ...]] = {
    "pc": (
        "ancestry",
        "character_class",
        "level",
        "background",
        "backstory",
        "homeland",
        "languages",
        "notable_items",
    ),
    "npc": ("role", "appearance", "goal", "disposition"),
    "faction": ("category", "goals", "influence", "alignment"),
    "location": ("location_type", "region", "environment"),
    "event": ("event_date", "phase", "details"),
}
DETAIL_MODELS = {
    "pc": CampaignPC,
    "npc": CampaignNPC,
    "faction": CampaignFaction,
    "location": CampaignLocation,
    "event": CampaignEvent,
}
DETAIL_REL_ATTR = {
    "pc": "pc_detail",
    "npc": "npc_detail",
    "faction": "faction_detail",
    "location": "location_detail",
    "event": "event_detail",
}
ENTITY_FIELD_MAPS: dict[str, dict[str, str]] = {
    "pc": {
        "key": "entity_key",
        "entity key": "entity_key",
        "summary": "summary",
        "status": "status",
        "tags": "tags",
        "ancestry": "ancestry",
        "class": "character_class",
        "character class": "character_class",
        "level": "level",
        "background": "background",
        "backstory": "backstory",
        "homeland": "homeland",
        "languages": "languages",
        "notable items": "notable_items",
    },
    "npc": {
        "key": "entity_key",
        "entity key": "entity_key",
        "summary": "summary",
        "status": "status",
        "tags": "tags",
        "role": "role",
        "appearance": "appearance",
        "goal": "goal",
        "disposition": "disposition",
    },
    "faction": {
        "key": "entity_key",
        "entity key": "entity_key",
        "summary": "summary",
        "status": "status",
        "tags": "tags",
        "category": "category",
        "goals": "goals",
        "influence": "influence",
        "alignment": "alignment",
    },
    "location": {
        "key": "entity_key",
        "entity key": "entity_key",
        "summary": "summary",
        "status": "status",
        "tags": "tags",
        "type": "location_type",
        "location type": "location_type",
        "region": "region",
        "environment": "environment",
    },
    "event": {
        "key": "entity_key",
        "entity key": "entity_key",
        "summary": "summary",
        "status": "status",
        "tags": "tags",
        "event date": "event_date",
        "phase": "phase",
        "details": "details",
    },
}


class CampaignValidationError(ValueError):
    pass


class CampaignService:
    async def get_entity(
        self, entity_key: str, db: AsyncSession
    ) -> CampaignEntity | None:
        result = await db.execute(
            select(CampaignEntity)
            .options(*self._entity_load_options())
            .where(CampaignEntity.entity_key == self._normalize_entity_key(entity_key))
        )
        return result.scalars().unique().one_or_none()

    async def get_required_entity(
        self, entity_key: str, db: AsyncSession, expected_type: str | None = None
    ) -> CampaignEntity:
        entity = await self.get_entity(entity_key, db)
        if not entity:
            raise CampaignValidationError(f"Unknown entity: {entity_key}")
        if expected_type and entity.entity_type != expected_type:
            raise CampaignValidationError(
                f"Entity {entity_key!r} is {entity.entity_type}, expected {expected_type}"
            )
        return entity

    async def upsert_entity(
        self,
        payload: dict[str, Any],
        db: AsyncSession,
        *,
        replace_relationships: bool = True,
    ) -> CampaignEntity:
        entity_type = self._normalize_entity_type(payload["entity_type"])
        name = payload["name"].strip()
        entity_key = self._normalize_entity_key(
            payload.get("entity_key") or self._build_entity_key(entity_type, name)
        )

        entity = await self.get_entity(entity_key, db)
        if entity and entity.entity_type != entity_type:
            raise CampaignValidationError(
                f"Entity key {entity_key!r} already belongs to a {entity.entity_type}"
            )

        if entity is None:
            entity = CampaignEntity(
                entity_key=entity_key,
                entity_type=entity_type,
                name=name,
            )
            db.add(entity)

        entity.name = name
        entity.summary = self._optional_text(payload.get("summary"))
        entity.status = self._optional_text(payload.get("status")) or "active"
        entity.tags = self._normalize_list(payload.get("tags"))
        await db.flush()

        detail_values = {
            field: payload.get(field) for field in DETAIL_FIELDS.get(entity_type, ())
        }
        created_detail = self._apply_detail_values(entity, entity_type, detail_values)
        if created_detail is not None:
            db.add(created_detail)
        await db.flush()

        if replace_relationships and "relationships" in payload:
            await self.replace_outgoing_relationships(
                entity.entity_key,
                payload.get("relationships") or [],
                db,
            )

        refreshed = await self.get_required_entity(entity_key, db)
        return refreshed

    async def replace_outgoing_relationships(
        self,
        entity_key: str,
        relationships: list[dict[str, Any]],
        db: AsyncSession,
    ) -> None:
        entity = await self.get_required_entity(entity_key, db)
        await db.execute(
            delete(CampaignRelationship).where(
                CampaignRelationship.from_entity_id == entity.id,
                CampaignRelationship.import_id.is_(None),
            )
        )
        await db.flush()

        for relationship in relationships:
            await self._create_relationship(
                from_entity=entity,
                relationship=relationship,
                db=db,
                import_id=None,
            )

        await db.flush()

    async def search_entities(
        self,
        db: AsyncSession,
        *,
        q: str | None = None,
        entity_type: str | None = None,
        location: str | None = None,
        related_to: str | None = None,
        relationship_type: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(CampaignEntity).options(*self._entity_load_options())
        if entity_type:
            stmt = stmt.where(
                CampaignEntity.entity_type == self._normalize_entity_type(entity_type)
            )
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                CampaignEntity.name.ilike(like)
                | CampaignEntity.summary.ilike(like)
                | CampaignEntity.entity_key.ilike(like)
            )

        entities = list((await db.execute(stmt)).scalars().unique().all())
        if location:
            location_entity = await self.resolve_entity(
                location, db, expected_type="location"
            )
            if not location_entity:
                return []
            entities = [
                entity
                for entity in entities
                if any(
                    relationship.relationship_type in LOCATION_RELATIONSHIP_TYPES
                    and relationship.to_entity_id == location_entity.id
                    for relationship in entity.outgoing_relationships
                )
            ]

        if related_to:
            related_entity = await self.resolve_entity(related_to, db)
            if not related_entity:
                return []
            entities = [
                entity
                for entity in entities
                if self._is_related(entity, related_entity.id, relationship_type)
            ]
        elif relationship_type:
            entities = [
                entity
                for entity in entities
                if any(
                    rel.relationship_type == relationship_type
                    for rel in entity.outgoing_relationships
                    + entity.incoming_relationships
                )
            ]

        entities.sort(key=lambda item: (item.entity_type, item.name.lower()))
        return [self.serialize_entity(entity) for entity in entities]

    async def list_npcs_by_location(
        self, location: str, db: AsyncSession
    ) -> list[dict[str, Any]]:
        return await self.search_entities(
            db,
            entity_type="npc",
            location=location,
        )

    async def list_pc_factions(
        self, entity_key: str, db: AsyncSession
    ) -> dict[str, Any]:
        pc = await self.get_required_entity(entity_key, db, expected_type="pc")
        factions = []
        for relationship in pc.outgoing_relationships:
            if (
                relationship.relationship_type in PC_TO_FACTION_RELATIONSHIPS
                and relationship.to_entity.entity_type == "faction"
            ):
                factions.append(
                    {
                        "relationship_type": relationship.relationship_type,
                        "note": relationship.note,
                        "entity": self.serialize_entity_summary(relationship.to_entity),
                    }
                )

        return {"pc": self.serialize_entity(pc), "factions": factions}

    async def import_notes(
        self, *, source_id: str, markdown: str, db: AsyncSession
    ) -> dict[str, Any]:
        import_record = await self._get_or_create_import_record(
            source_kind="notes",
            source_id=source_id,
            db=db,
        )
        content_hash = self._hash_content(markdown)
        if import_record.content_hash == content_hash:
            return {
                "status": "unchanged",
                "source_kind": "notes",
                "source_id": source_id,
                "entity_keys": import_record.entity_keys,
                "relationship_count": len(import_record.relationship_specs),
            }

        parsed = self.parse_markdown_notes(markdown)
        stored_keys: list[str] = []
        for entity_payload in parsed["entities"]:
            stored = await self.upsert_entity(
                entity_payload,
                db,
                replace_relationships=False,
            )
            stored_keys.append(stored.entity_key)

        await self._replace_import_relationships(
            import_record=import_record,
            relationship_specs=parsed["relationships"],
            db=db,
        )

        import_record.content_hash = content_hash
        import_record.status = "applied"
        import_record.entity_keys = sorted(set(stored_keys))
        import_record.relationship_specs = parsed["relationships"]
        import_record.last_result = {
            "entity_count": len(import_record.entity_keys),
            "relationship_count": len(parsed["relationships"]),
        }
        await db.flush()

        return {
            "status": "applied",
            "source_kind": "notes",
            "source_id": source_id,
            "entity_keys": import_record.entity_keys,
            "relationship_count": len(parsed["relationships"]),
        }

    async def import_pc_sheet(
        self, *, source_id: str, payload: dict[str, Any], db: AsyncSession
    ) -> dict[str, Any]:
        import_record = await self._get_or_create_import_record(
            source_kind="pc_sheet",
            source_id=source_id,
            db=db,
        )
        content_hash = self._hash_content(payload)
        if import_record.content_hash == content_hash:
            return {
                "status": "unchanged",
                "source_kind": "pc_sheet",
                "source_id": source_id,
                "entity_keys": import_record.entity_keys,
                "relationship_count": len(import_record.relationship_specs),
            }

        entity_payload = dict(payload)
        entity_payload["entity_type"] = "pc"
        relationships = list(entity_payload.pop("relationships", []))
        if entity_payload.get("current_location"):
            relationships.append(
                {
                    "target_key": entity_payload.pop("current_location"),
                    "target_type": "location",
                    "relationship_type": "located_in",
                }
            )
        for faction_key in entity_payload.pop("factions", []):
            relationships.append(
                {
                    "target_key": faction_key,
                    "target_type": "faction",
                    "relationship_type": "member_of",
                }
            )

        stored_pc = await self.upsert_entity(
            entity_payload,
            db,
            replace_relationships=False,
        )
        relationship_specs = [
            {
                "from_key": stored_pc.entity_key,
                "from_type": "pc",
                "to_key": self._normalize_entity_key(
                    relationship.get("target_key")
                    or self._build_entity_key(
                        relationship["target_type"], relationship["target_name"]
                    )
                ),
                "to_type": self._normalize_entity_type(relationship["target_type"]),
                "to_name": relationship.get("target_name"),
                "relationship_type": self._normalize_relationship_type(
                    relationship["relationship_type"]
                ),
                "note": self._optional_text(relationship.get("note")),
            }
            for relationship in relationships
        ]

        await self._replace_import_relationships(
            import_record=import_record,
            relationship_specs=relationship_specs,
            db=db,
        )

        import_record.content_hash = content_hash
        import_record.status = "applied"
        import_record.entity_keys = [stored_pc.entity_key]
        import_record.relationship_specs = relationship_specs
        import_record.last_result = {
            "entity_count": 1,
            "relationship_count": len(relationship_specs),
        }
        await db.flush()

        return {
            "status": "applied",
            "source_kind": "pc_sheet",
            "source_id": source_id,
            "entity_keys": [stored_pc.entity_key],
            "relationship_count": len(relationship_specs),
        }

    async def get_consistency_report(self, db: AsyncSession) -> dict[str, Any]:
        duplicate_rows = await db.execute(
            select(CampaignEntity.entity_key, func.count(CampaignEntity.id))
            .group_by(CampaignEntity.entity_key)
            .having(func.count(CampaignEntity.id) > 1)
        )
        duplicate_entity_keys = [
            {"entity_key": entity_key, "count": count}
            for entity_key, count in duplicate_rows.all()
        ]

        relationship_rows = (
            (
                await db.execute(
                    select(CampaignRelationship).options(
                        selectinload(CampaignRelationship.from_entity),
                        selectinload(CampaignRelationship.to_entity),
                    )
                )
            )
            .scalars()
            .all()
        )

        self_relationships = [
            {
                "entity_key": relationship.from_entity.entity_key,
                "relationship_type": relationship.relationship_type,
            }
            for relationship in relationship_rows
            if relationship.from_entity_id == relationship.to_entity_id
        ]

        forbidden_cycles = self._detect_forbidden_cycles(list(relationship_rows))
        return {
            "ok": not duplicate_entity_keys
            and not self_relationships
            and not forbidden_cycles,
            "duplicate_entity_keys": duplicate_entity_keys,
            "self_relationships": self_relationships,
            "forbidden_cycles": forbidden_cycles,
        }

    async def resolve_entity(
        self,
        value: str,
        db: AsyncSession,
        *,
        expected_type: str | None = None,
    ) -> CampaignEntity | None:
        normalized_key = self._normalize_entity_key(value)
        stmt = (
            select(CampaignEntity)
            .options(*self._entity_load_options())
            .where(CampaignEntity.entity_key == normalized_key)
        )
        if expected_type:
            stmt = stmt.where(
                CampaignEntity.entity_type == self._normalize_entity_type(expected_type)
            )
        by_key = (await db.execute(stmt)).scalars().unique().one_or_none()
        if by_key:
            return by_key

        name_stmt = (
            select(CampaignEntity)
            .options(*self._entity_load_options())
            .where(func.lower(CampaignEntity.name) == value.strip().lower())
        )
        if expected_type:
            name_stmt = name_stmt.where(
                CampaignEntity.entity_type == self._normalize_entity_type(expected_type)
            )
        results = list((await db.execute(name_stmt)).scalars().unique().all())
        if len(results) > 1:
            raise CampaignValidationError(
                f"Ambiguous entity reference {value!r}; use entity_key instead"
            )
        return results[0] if results else None

    def parse_markdown_notes(self, markdown: str) -> dict[str, list[dict[str, Any]]]:
        sections = self._split_markdown_sections(markdown)
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []

        for heading, body in sections:
            entity_match = ENTITY_HEADING_RE.match(heading)
            if entity_match:
                entity_type = self._normalize_entity_type(
                    entity_match.group("entity_type")
                )
                name = entity_match.group("name").strip()
                entities.append(self._parse_entity_section(entity_type, name, body))
                continue

            if heading.strip().lower() == "relationships":
                relationships.extend(self._parse_relationship_section(body))

        return {"entities": entities, "relationships": relationships}

    def serialize_entity(self, entity: CampaignEntity) -> dict[str, Any]:
        relationships = []
        for relationship in sorted(
            entity.outgoing_relationships,
            key=lambda rel: (rel.relationship_type, rel.to_entity.name.lower()),
        ):
            relationships.append(
                {
                    "direction": "outgoing",
                    "relationship_type": relationship.relationship_type,
                    "note": relationship.note,
                    "entity": self.serialize_entity_summary(relationship.to_entity),
                }
            )
        for relationship in sorted(
            entity.incoming_relationships,
            key=lambda rel: (rel.relationship_type, rel.from_entity.name.lower()),
        ):
            relationships.append(
                {
                    "direction": "incoming",
                    "relationship_type": relationship.relationship_type,
                    "note": relationship.note,
                    "entity": self.serialize_entity_summary(relationship.from_entity),
                }
            )

        return {
            "entity_key": entity.entity_key,
            "entity_type": entity.entity_type,
            "name": entity.name,
            "summary": entity.summary,
            "status": entity.status,
            "tags": entity.tags or [],
            "details": self._serialize_details(entity),
            "relationships": relationships,
        }

    def serialize_entity_summary(self, entity: CampaignEntity) -> dict[str, Any]:
        return {
            "entity_key": entity.entity_key,
            "entity_type": entity.entity_type,
            "name": entity.name,
            "summary": entity.summary,
            "status": entity.status,
        }

    async def _get_or_create_import_record(
        self,
        *,
        source_kind: str,
        source_id: str,
        db: AsyncSession,
    ) -> CampaignImport:
        result = await db.execute(
            select(CampaignImport).where(
                CampaignImport.source_kind == source_kind,
                CampaignImport.source_id == source_id,
            )
        )
        import_record = result.scalar_one_or_none()
        if import_record:
            return import_record

        import_record = CampaignImport(
            source_kind=source_kind,
            source_id=source_id,
            content_hash="",
            status="pending",
            entity_keys=[],
            relationship_specs=[],
        )
        db.add(import_record)
        await db.flush()
        return import_record

    async def _replace_import_relationships(
        self,
        *,
        import_record: CampaignImport,
        relationship_specs: list[dict[str, Any]],
        db: AsyncSession,
    ) -> None:
        await db.execute(
            delete(CampaignRelationship).where(
                CampaignRelationship.import_id == import_record.id
            )
        )
        await db.flush()

        for relationship in relationship_specs:
            from_entity = await self.get_required_entity(
                relationship["from_key"],
                db,
                expected_type=relationship.get("from_type"),
            )
            await self._create_relationship(
                from_entity=from_entity,
                relationship={
                    "target_key": relationship["to_key"],
                    "target_type": relationship["to_type"],
                    "target_name": relationship.get("to_name"),
                    "relationship_type": relationship["relationship_type"],
                    "note": relationship.get("note"),
                },
                db=db,
                import_id=import_record.id,
            )

        await db.flush()

    async def _create_relationship(
        self,
        *,
        from_entity: CampaignEntity,
        relationship: dict[str, Any],
        db: AsyncSession,
        import_id: int | None,
    ) -> None:
        relationship_type = self._normalize_relationship_type(
            relationship["relationship_type"]
        )
        target_type = relationship.get("target_type")
        if target_type:
            target_type = self._normalize_entity_type(target_type)
        target_key = relationship.get("target_key")
        target_name = relationship.get("target_name")
        if not target_key and not target_name:
            raise CampaignValidationError(
                "Relationships require target_key or target_name"
            )

        reference_value = target_key or target_name
        if reference_value is None:
            raise CampaignValidationError(
                "Relationships require target_key or target_name"
            )
        to_entity = await self.resolve_entity(
            reference_value,
            db,
            expected_type=target_type,
        )
        if to_entity is None:
            if not target_type or not target_name:
                raise CampaignValidationError(
                    "Missing target_type/target_name for new relationship target"
                )
            to_entity = await self.upsert_entity(
                {
                    "entity_type": target_type,
                    "entity_key": target_key,
                    "name": target_name,
                    "summary": None,
                    "status": "active",
                    "tags": [],
                },
                db,
                replace_relationships=False,
            )

        self._validate_relationship_edge(
            from_entity_key=from_entity.entity_key,
            from_entity_id=from_entity.id,
            to_entity=to_entity,
            relationship_type=relationship_type,
        )

        existing = await db.execute(
            select(CampaignRelationship).where(
                CampaignRelationship.from_entity_id == from_entity.id,
                CampaignRelationship.to_entity_id == to_entity.id,
                CampaignRelationship.relationship_type == relationship_type,
            )
        )
        if existing.scalar_one_or_none():
            return

        db.add(
            CampaignRelationship(
                from_entity_id=from_entity.id,
                to_entity_id=to_entity.id,
                relationship_type=relationship_type,
                note=self._optional_text(relationship.get("note")),
                import_id=import_id,
            )
        )

    def _validate_relationship_edge(
        self,
        *,
        from_entity_key: str,
        from_entity_id: int,
        to_entity: CampaignEntity,
        relationship_type: str,
    ) -> None:
        if from_entity_id == to_entity.id:
            raise CampaignValidationError(
                f"Self relationships are not allowed: {from_entity_key}"
            )
        if (
            relationship_type in LOCATION_RELATIONSHIP_TYPES
            and to_entity.entity_type != "location"
        ):
            raise CampaignValidationError(
                f"Relationship {relationship_type!r} must point to a location"
            )

    def _apply_detail_values(
        self,
        entity: CampaignEntity,
        entity_type: str,
        detail_values: dict[str, Any],
    ) -> Any | None:
        detail_attr = DETAIL_REL_ATTR[entity_type]
        detail = entity.__dict__.get(detail_attr)
        created_detail = None
        if detail is None:
            detail = DETAIL_MODELS[entity_type](entity=entity)
            setattr(entity, detail_attr, detail)
            created_detail = detail

        for field in DETAIL_FIELDS[entity_type]:
            value = detail_values.get(field)
            if field in {"languages", "notable_items"}:
                setattr(detail, field, self._normalize_list(value))
            elif field == "level":
                setattr(detail, field, self._optional_int(value))
            else:
                setattr(detail, field, self._optional_text(value))
        return created_detail

    def _parse_entity_section(
        self, entity_type: str, name: str, body: str
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "entity_type": entity_type,
            "name": name,
        }
        free_text: list[str] = []
        field_map = ENTITY_FIELD_MAPS[entity_type]

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            metadata_match = METADATA_LINE_RE.match(line)
            if metadata_match:
                raw_key = metadata_match.group("key").strip().lower()
                mapped_key = field_map.get(raw_key)
                if mapped_key:
                    metadata[mapped_key] = metadata_match.group("value").strip()
                continue
            free_text.append(line)

        if "entity_key" not in metadata:
            metadata["entity_key"] = self._build_entity_key(entity_type, name)
        if "tags" in metadata:
            metadata["tags"] = self._normalize_list(metadata["tags"])
        if "level" in metadata:
            metadata["level"] = self._optional_int(metadata["level"])
        if "languages" in metadata:
            metadata["languages"] = self._normalize_list(metadata["languages"])
        if "notable_items" in metadata:
            metadata["notable_items"] = self._normalize_list(metadata["notable_items"])

        free_text_block = "\n".join(free_text).strip()
        if free_text_block:
            if entity_type == "pc":
                metadata.setdefault("backstory", free_text_block)
            elif entity_type == "event":
                metadata.setdefault("details", free_text_block)
            metadata.setdefault("summary", free_text_block)

        metadata.setdefault("summary", None)
        metadata.setdefault("status", "active")
        metadata.setdefault("tags", [])
        metadata.setdefault("relationships", [])
        return metadata

    def _parse_relationship_section(self, body: str) -> list[dict[str, Any]]:
        rows = [
            match.group("content")
            for line in body.splitlines()
            if (match := RELATIONSHIP_LINE_RE.match(line.strip()))
        ]
        if len(rows) < 2:
            return []

        headers = [column.strip().lower() for column in rows[0].split("|")]
        relationships = []
        for raw_row in rows[2:]:
            values = [column.strip() for column in raw_row.split("|")]
            if len(values) != len(headers):
                continue
            row = dict(zip(headers, values))
            relationships.append(
                {
                    "from_key": self._normalize_entity_key(row["from"]),
                    "to_key": self._normalize_entity_key(row["to"]),
                    "relationship_type": self._normalize_relationship_type(row["type"]),
                    "note": self._optional_text(row.get("note")),
                    "from_type": row.get("from_type") or None,
                    "to_type": row.get("to_type") or None,
                    "to_name": row.get("to_name") or None,
                }
            )

        return relationships

    def _detect_forbidden_cycles(
        self, relationships: list[CampaignRelationship]
    ) -> list[dict[str, Any]]:
        graph: dict[int, list[tuple[int, str]]] = defaultdict(list)
        labels: dict[int, str] = {}
        for relationship in relationships:
            if relationship.relationship_type in ACYCLIC_RELATIONSHIP_TYPES:
                graph[relationship.from_entity_id].append(
                    (relationship.to_entity_id, relationship.relationship_type)
                )
                labels[relationship.from_entity_id] = (
                    relationship.from_entity.entity_key
                )
                labels[relationship.to_entity_id] = relationship.to_entity.entity_key

        visited: set[int] = set()
        stack: list[int] = []
        in_stack: set[int] = set()
        cycles: set[tuple[str, ...]] = set()

        def dfs(node: int) -> None:
            visited.add(node)
            stack.append(node)
            in_stack.add(node)
            for neighbor, relationship_type in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                    continue
                if neighbor in in_stack:
                    cycle_nodes = stack[stack.index(neighbor) :] + [neighbor]
                    cycle_labels = tuple(labels[item] for item in cycle_nodes)
                    cycles.add(cycle_labels + (relationship_type,))
            stack.pop()
            in_stack.remove(node)

        for node in graph:
            if node not in visited:
                dfs(node)

        return [
            {
                "path": list(cycle[:-1]),
                "relationship_type": cycle[-1],
            }
            for cycle in sorted(cycles)
        ]

    def _is_related(
        self,
        entity: CampaignEntity,
        related_entity_id: int,
        relationship_type: str | None,
    ) -> bool:
        normalized_type = (
            self._normalize_relationship_type(relationship_type)
            if relationship_type
            else None
        )
        for relationship in entity.outgoing_relationships:
            if relationship.to_entity_id == related_entity_id and (
                normalized_type is None
                or relationship.relationship_type == normalized_type
            ):
                return True
        for relationship in entity.incoming_relationships:
            if relationship.from_entity_id == related_entity_id and (
                normalized_type is None
                or relationship.relationship_type == normalized_type
            ):
                return True
        return False

    def _serialize_details(self, entity: CampaignEntity) -> dict[str, Any]:
        detail = getattr(entity, DETAIL_REL_ATTR[entity.entity_type])
        if detail is None:
            return {}
        return {
            field: getattr(detail, field)
            for field in DETAIL_FIELDS[entity.entity_type]
            if getattr(detail, field) not in (None, [], "")
        }

    def _split_markdown_sections(self, markdown: str) -> list[tuple[str, str]]:
        matches = list(SECTION_HEADING_RE.finditer(markdown))
        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(markdown)
            )
            sections.append(
                (match.group("heading").strip(), markdown[start:end].strip())
            )
        return sections

    def _entity_load_options(self):
        return (
            selectinload(CampaignEntity.pc_detail),
            selectinload(CampaignEntity.npc_detail),
            selectinload(CampaignEntity.faction_detail),
            selectinload(CampaignEntity.location_detail),
            selectinload(CampaignEntity.event_detail),
            selectinload(CampaignEntity.outgoing_relationships).selectinload(
                CampaignRelationship.to_entity
            ),
            selectinload(CampaignEntity.incoming_relationships).selectinload(
                CampaignRelationship.from_entity
            ),
        )

    def _normalize_entity_type(self, entity_type: str) -> str:
        normalized = entity_type.strip().lower()
        if normalized not in SUPPORTED_ENTITY_TYPES:
            raise CampaignValidationError(
                f"Unsupported entity type {entity_type!r}; expected one of {sorted(SUPPORTED_ENTITY_TYPES)}"
            )
        return normalized

    def _normalize_relationship_type(self, relationship_type: str) -> str:
        normalized = relationship_type.strip().lower().replace(" ", "_")
        if not normalized:
            raise CampaignValidationError("Relationship type cannot be empty")
        return normalized

    def _normalize_entity_key(self, entity_key: str) -> str:
        key = entity_key.strip().lower()
        key = key.replace("_", "-").replace(":", "-")
        key = MULTISPACE_RE.sub("-", key)
        key = NON_SLUG_RE.sub("-", key)
        return key.strip("-")

    def _build_entity_key(self, entity_type: str, name: str) -> str:
        return f"{entity_type}-{self._normalize_entity_key(name)}"

    def _normalize_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",")]
            return [item for item in parts if item]
        return [str(value).strip()]

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _optional_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    def _hash_content(self, value: Any) -> str:
        if isinstance(value, str):
            payload = value.encode("utf-8")
        else:
            payload = repr(value).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


campaign_service = CampaignService()
