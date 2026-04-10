from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.models.campaign import (
    CampaignEntity,
    CampaignRelationship,
    CharacterSheetVersion,
)
from backend.models.document import Document


class CampaignService:
    allowed_entity_types = {
        "artifact",
        "calendar",
        "event",
        "faction",
        "holiday",
        "location",
        "npc",
        "pc",
        "shop",
    }
    stable_key_prefixes = {
        "artifact": "ART",
        "calendar": "CAL",
        "event": "EVT",
        "faction": "FAC",
        "holiday": "HOL",
        "location": "LOC",
        "npc": "NPC",
        "pc": "PC",
        "shop": "SHOP",
    }
    location_entity_types = {"location", "shop"}

    async def create_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        name: str,
        stable_key: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        is_active: bool = True,
        parent_entity_id: Optional[int] = None,
        current_location_id: Optional[int] = None,
        owner_entity_id: Optional[int] = None,
    ) -> CampaignEntity:
        normalized_type = self._normalize_entity_type(entity_type)
        await self._validate_references(
            db,
            parent_entity_id=parent_entity_id,
            current_location_id=current_location_id,
            owner_entity_id=owner_entity_id,
        )
        entity = CampaignEntity(
            stable_key=stable_key or await self._next_stable_key(normalized_type, db),
            entity_type=normalized_type,
            name=name.strip(),
            summary=summary,
            description=description,
            details=self._normalize_details(details),
            tags=self._normalize_strings(tags),
            is_active=is_active,
            parent_entity_id=parent_entity_id,
            current_location_id=current_location_id,
            owner_entity_id=owner_entity_id,
        )
        db.add(entity)
        await self._commit(db, "Campaign entity already exists")
        loaded = await self.get_entity(entity.id, db)
        if loaded is None:
            raise LookupError("Campaign entity was created but could not be reloaded")
        return loaded

    async def update_entity(
        self,
        entity_id: int,
        db: AsyncSession,
        *,
        name: Optional[str] = None,
        stable_key: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        is_active: Optional[bool] = None,
        parent_entity_id: Optional[int] = None,
        current_location_id: Optional[int] = None,
        owner_entity_id: Optional[int] = None,
        clear_parent_entity: bool = False,
        clear_current_location: bool = False,
        clear_owner_entity: bool = False,
    ) -> CampaignEntity:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            raise LookupError("Campaign entity not found")

        requested_parent = None if clear_parent_entity else parent_entity_id
        requested_location = None if clear_current_location else current_location_id
        requested_owner = None if clear_owner_entity else owner_entity_id
        await self._validate_references(
            db,
            entity_id=entity.id,
            parent_entity_id=requested_parent,
            current_location_id=requested_location,
            owner_entity_id=requested_owner,
        )

        if name is not None:
            entity.name = name.strip()
        if stable_key is not None:
            entity.stable_key = stable_key.strip()
        if summary is not None:
            entity.summary = summary
        if description is not None:
            entity.description = description
        if details is not None:
            entity.details = self._normalize_details(details)
        if tags is not None:
            entity.tags = self._normalize_strings(tags)
        if is_active is not None:
            entity.is_active = is_active
        if clear_parent_entity:
            entity.parent_entity_id = None
        elif parent_entity_id is not None:
            entity.parent_entity_id = parent_entity_id
        if clear_current_location:
            entity.current_location_id = None
        elif current_location_id is not None:
            entity.current_location_id = current_location_id
        if clear_owner_entity:
            entity.owner_entity_id = None
        elif owner_entity_id is not None:
            entity.owner_entity_id = owner_entity_id

        await self._commit(db, "Campaign entity update conflicts with existing data")
        loaded = await self.get_entity(entity.id, db)
        if loaded is None:
            raise LookupError("Campaign entity disappeared during update")
        return loaded

    async def delete_entity(self, entity_id: int, db: AsyncSession) -> bool:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            return False
        await db.delete(entity)
        await db.commit()
        return True

    async def get_entity(
        self, entity_id: int, db: AsyncSession
    ) -> Optional[CampaignEntity]:
        stmt = (
            select(CampaignEntity)
            .where(CampaignEntity.id == entity_id)
            .options(*self._entity_loader_options())
        )
        result = await db.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def find_entity_by_reference(
        self,
        db: AsyncSession,
        reference: str,
        *,
        entity_types: Optional[Iterable[str]] = None,
    ) -> Optional[CampaignEntity]:
        normalized_reference = reference.strip()
        if not normalized_reference:
            return None

        stmt = select(CampaignEntity).options(*self._entity_loader_options())
        if entity_types:
            normalized_types = [
                self._normalize_entity_type(entity_type) for entity_type in entity_types
            ]
            stmt = stmt.where(CampaignEntity.entity_type.in_(normalized_types))

        result = await db.execute(
            stmt.where(CampaignEntity.stable_key == normalized_reference)
        )
        entity = result.scalars().unique().one_or_none()
        if entity is not None:
            return entity

        result = await db.execute(
            stmt.where(CampaignEntity.name.ilike(normalized_reference))
        )
        return result.scalars().unique().one_or_none()

    async def upsert_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        name: str,
        stable_key: Optional[str] = None,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        is_active: bool = True,
        parent_entity_id: Optional[int] = None,
        current_location_id: Optional[int] = None,
        owner_entity_id: Optional[int] = None,
    ) -> tuple[CampaignEntity, bool]:
        existing = None
        if stable_key:
            existing = await self.find_entity_by_reference(db, stable_key)
        if existing is None:
            existing = await self.find_entity_by_reference(
                db, name, entity_types=[entity_type]
            )

        if existing is None:
            entity = await self.create_entity(
                db,
                entity_type=entity_type,
                name=name,
                stable_key=stable_key,
                summary=summary,
                description=description,
                details=details,
                tags=tags,
                is_active=is_active,
                parent_entity_id=parent_entity_id,
                current_location_id=current_location_id,
                owner_entity_id=owner_entity_id,
            )
            return entity, True

        entity = await self.update_entity(
            existing.id,
            db,
            name=name,
            stable_key=stable_key or existing.stable_key,
            summary=summary if summary is not None else existing.summary,
            description=(
                description if description is not None else existing.description
            ),
            details=self._merge_details(existing.details, details),
            tags=self._normalize_strings([*(existing.tags or []), *(tags or [])]),
            is_active=is_active,
            current_location_id=current_location_id,
            owner_entity_id=owner_entity_id,
            parent_entity_id=parent_entity_id,
        )
        return entity, False

    async def list_entities(
        self,
        db: AsyncSession,
        *,
        entity_type: Optional[str] = None,
        q: Optional[str] = None,
        language: Optional[str] = None,
        current_location_id: Optional[int] = None,
        owner_entity_id: Optional[int] = None,
        relationship_type: Optional[str] = None,
        related_entity_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        stmt = select(CampaignEntity).options(*self._entity_loader_options())
        if entity_type:
            stmt = stmt.where(
                CampaignEntity.entity_type == self._normalize_entity_type(entity_type)
            )
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    CampaignEntity.name.ilike(like),
                    CampaignEntity.stable_key.ilike(like),
                    CampaignEntity.summary.ilike(like),
                    CampaignEntity.description.ilike(like),
                )
            )
        if current_location_id is not None:
            stmt = stmt.where(CampaignEntity.current_location_id == current_location_id)
        if owner_entity_id is not None:
            stmt = stmt.where(CampaignEntity.owner_entity_id == owner_entity_id)
        if is_active is not None:
            stmt = stmt.where(CampaignEntity.is_active == is_active)

        if relationship_type or related_entity_id is not None:
            stmt = stmt.join(
                CampaignRelationship,
                or_(
                    CampaignRelationship.source_entity_id == CampaignEntity.id,
                    CampaignRelationship.target_entity_id == CampaignEntity.id,
                ),
            )
            if relationship_type:
                stmt = stmt.where(
                    CampaignRelationship.relationship_type == relationship_type.strip()
                )
            if related_entity_id is not None:
                stmt = stmt.where(
                    or_(
                        and_(
                            CampaignRelationship.source_entity_id == CampaignEntity.id,
                            CampaignRelationship.target_entity_id == related_entity_id,
                        ),
                        and_(
                            CampaignRelationship.target_entity_id == CampaignEntity.id,
                            CampaignRelationship.source_entity_id == related_entity_id,
                        ),
                    )
                ).where(CampaignEntity.id != related_entity_id)

        stmt = stmt.order_by(CampaignEntity.entity_type, CampaignEntity.name)
        result = await db.execute(stmt)
        entities = list(result.scalars().unique().all())

        if language:
            language_key = language.strip().casefold()
            entities = [
                entity
                for entity in entities
                if self._entity_languages(entity)
                and language_key in self._entity_languages(entity)
            ]

        total = len(entities)
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "items": [self.entity_to_dict(entity) for entity in entities[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    async def create_relationship(
        self,
        db: AsyncSession,
        *,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        strength: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> CampaignRelationship:
        if source_entity_id == target_entity_id:
            raise ValueError("Relationships must connect two different entities")
        source = await self.get_entity(source_entity_id, db)
        target = await self.get_entity(target_entity_id, db)
        if source is None or target is None:
            raise LookupError("Relationship source or target entity was not found")

        relationship = CampaignRelationship(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type.strip(),
            strength=strength,
            notes=notes,
        )
        db.add(relationship)
        await self._commit(db, "Relationship already exists")

        stmt = (
            select(CampaignRelationship)
            .where(CampaignRelationship.id == relationship.id)
            .options(
                joinedload(CampaignRelationship.source_entity),
                joinedload(CampaignRelationship.target_entity),
            )
        )
        result = await db.execute(stmt)
        loaded = result.scalars().one_or_none()
        if loaded is None:
            raise LookupError("Relationship was created but could not be reloaded")
        return loaded

    async def ensure_relationship(
        self,
        db: AsyncSession,
        *,
        source_entity_id: int,
        target_entity_id: int,
        relationship_type: str,
        strength: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> tuple[CampaignRelationship, bool]:
        stmt = (
            select(CampaignRelationship)
            .where(CampaignRelationship.source_entity_id == source_entity_id)
            .where(CampaignRelationship.target_entity_id == target_entity_id)
            .where(CampaignRelationship.relationship_type == relationship_type.strip())
            .options(
                joinedload(CampaignRelationship.source_entity),
                joinedload(CampaignRelationship.target_entity),
            )
        )
        result = await db.execute(stmt)
        existing = result.scalars().one_or_none()
        if existing is None:
            relationship = await self.create_relationship(
                db,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                relationship_type=relationship_type,
                strength=strength,
                notes=notes,
            )
            return relationship, True

        if strength is not None:
            existing.strength = strength
        if notes:
            existing.notes = notes
        await self._commit(db, "Relationship update conflicts with existing data")
        refreshed = await self._get_relationship(existing.id, db)
        if refreshed is None:
            raise LookupError("Relationship disappeared during update")
        return refreshed, False

    async def list_relationships(
        self, entity_id: int, db: AsyncSession
    ) -> list[dict[str, Any]]:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            raise LookupError("Campaign entity not found")
        relationships = [
            self.relationship_to_dict(relationship, perspective_entity_id=entity_id)
            for relationship in entity.outgoing_relationships
        ] + [
            self.relationship_to_dict(relationship, perspective_entity_id=entity_id)
            for relationship in entity.incoming_relationships
        ]
        relationships.sort(
            key=lambda item: (
                item["relationship_type"],
                item["related_entity"]["entity_type"],
                item["related_entity"]["name"],
            )
        )
        return relationships

    async def add_sheet_version(
        self,
        entity_id: int,
        db: AsyncSession,
        *,
        payload: dict[str, Any],
        source_name: Optional[str] = None,
    ) -> CharacterSheetVersion:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            raise LookupError("Campaign entity not found")
        if entity.entity_type != "pc":
            raise ValueError("Character sheet versions can only be attached to PCs")

        next_version = (
            max(
                (version.version_number for version in entity.sheet_versions), default=0
            )
            + 1
        )
        version = CharacterSheetVersion(
            entity_id=entity.id,
            version_number=next_version,
            source_name=source_name,
            payload=payload,
        )
        db.add(version)
        entity.details = self._sync_pc_details(entity.details, payload)
        await self._commit(db, "Character sheet version conflicts with existing data")

        stmt = (
            select(CharacterSheetVersion)
            .where(CharacterSheetVersion.id == version.id)
            .options(joinedload(CharacterSheetVersion.entity))
        )
        result = await db.execute(stmt)
        loaded = result.scalars().one_or_none()
        if loaded is None:
            raise LookupError(
                "Character sheet version was created but could not be reloaded"
            )
        return loaded

    async def list_sheet_versions(
        self, entity_id: int, db: AsyncSession
    ) -> list[dict[str, Any]]:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            raise LookupError("Campaign entity not found")
        if entity.entity_type != "pc":
            raise ValueError("Only PCs have character sheet versions")
        return [
            self.sheet_version_to_dict(version) for version in entity.sheet_versions
        ]

    async def get_overview(self, db: AsyncSession) -> dict[str, Any]:
        result = await db.execute(
            select(CampaignEntity).options(*self._entity_loader_options())
        )
        entities = list(result.scalars().unique().all())
        entities.sort(key=lambda entity: (entity.entity_type, entity.name))
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entity in entities:
            grouped.setdefault(entity.entity_type, []).append(
                self.entity_to_dict(entity)
            )

        counts = {entity_type: len(items) for entity_type, items in grouped.items()}
        return {
            "counts": counts,
            "pcs": grouped.get("pc", []),
            "npcs": grouped.get("npc", []),
            "factions": grouped.get("faction", []),
            "locations": grouped.get("location", []),
            "shops": grouped.get("shop", []),
            "artifacts": grouped.get("artifact", []),
            "events": grouped.get("event", []),
            "calendars": grouped.get("calendar", []),
            "holidays": grouped.get("holiday", []),
        }

    async def get_pc_dossier(self, entity_id: int, db: AsyncSession) -> dict[str, Any]:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            raise LookupError("Campaign entity not found")
        if entity.entity_type != "pc":
            raise ValueError("Dossiers are only available for PCs")

        artifact_stmt = (
            select(CampaignEntity)
            .where(CampaignEntity.entity_type == "artifact")
            .where(CampaignEntity.owner_entity_id == entity.id)
            .options(*self._entity_loader_options())
            .order_by(CampaignEntity.name)
        )
        artifact_result = await db.execute(artifact_stmt)
        artifacts = list(artifact_result.scalars().unique().all())

        relationships = await self.list_relationships(entity.id, db)
        relationship_groups: dict[str, list[dict[str, Any]]] = {}
        factions: list[dict[str, Any]] = []
        for relationship in relationships:
            relationship_groups.setdefault(
                relationship["relationship_type"], []
            ).append(relationship)
            related = relationship["related_entity"]
            if (
                relationship["relationship_type"] == "member"
                and related["entity_type"] == "faction"
            ):
                factions.append(related)

        return {
            "pc": self.entity_to_dict(
                entity,
                include_relationships=True,
                include_sheet_versions=True,
            ),
            "factions": factions,
            "owned_artifacts": [
                self.entity_to_dict(artifact) for artifact in artifacts
            ],
            "relationship_groups": relationship_groups,
            "sheet_version_count": len(entity.sheet_versions),
            "languages": self._normalize_strings(entity.details.get("languages")),
            "scripts": self._normalize_strings(entity.details.get("scripts")),
            "goals": self._normalize_strings(entity.details.get("goals")),
            "hooks": self._normalize_strings(entity.details.get("hooks")),
        }

    async def get_session_history(
        self,
        db: AsyncSession,
        *,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        event_result = await db.execute(
            select(CampaignEntity)
            .where(CampaignEntity.entity_type == "event")
            .options(*self._entity_loader_options())
        )
        events = list(event_result.scalars().unique().all())

        document_result = await db.execute(
            select(Document)
            .where(Document.kind == "session_log")
            .order_by(Document.updated_at.desc())
        )
        documents = list(document_result.scalars().all())

        documents_by_title: dict[str, list[Document]] = {}
        for document in documents:
            documents_by_title.setdefault(document.title.strip().casefold(), []).append(
                document
            )

        items: list[dict[str, Any]] = []
        matched_document_ids: set[int] = set()
        for event in events:
            matched_document = None
            candidates = documents_by_title.get(event.name.strip().casefold(), [])
            for document in candidates:
                if document.id not in matched_document_ids:
                    matched_document = document
                    matched_document_ids.add(document.id)
                    break

            item = {
                "title": event.name,
                "event": self.entity_to_dict(event),
                "document": self._document_ref(matched_document),
                "timeline_position": (event.details or {}).get("timeline_position"),
                "scheduled_for": (event.details or {}).get("scheduled_for"),
                "summary": event.summary,
                "_sort_at": max(
                    event.updated_at,
                    (
                        matched_document.updated_at
                        if matched_document
                        else event.updated_at
                    ),
                ),
            }
            if self._session_history_matches_query(item, q):
                items.append(item)

        for document in documents:
            if document.id in matched_document_ids:
                continue
            item = {
                "title": document.title,
                "event": None,
                "document": self._document_ref(document),
                "timeline_position": None,
                "scheduled_for": None,
                "summary": document.summary,
                "_sort_at": document.updated_at,
            }
            if self._session_history_matches_query(item, q):
                items.append(item)

        items.sort(key=lambda item: item["_sort_at"], reverse=True)
        total = len(items)
        pages = (total + page_size - 1) // page_size if page_size > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size
        paginated = items[start:end]
        for item in paginated:
            item.pop("_sort_at", None)

        return {
            "items": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

    def entity_to_dict(
        self,
        entity: CampaignEntity,
        *,
        include_relationships: bool = False,
        include_sheet_versions: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "id": entity.id,
            "stable_key": entity.stable_key,
            "entity_type": entity.entity_type,
            "name": entity.name,
            "summary": entity.summary,
            "description": entity.description,
            "details": entity.details or {},
            "tags": entity.tags or [],
            "is_active": entity.is_active,
            "parent_entity": self._entity_ref(entity.parent_entity),
            "current_location": self._entity_ref(entity.current_location),
            "owner_entity": self._entity_ref(entity.owner_entity),
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
        if entity.sheet_versions:
            payload["latest_sheet_version"] = self.sheet_version_to_dict(
                entity.sheet_versions[-1]
            )
        else:
            payload["latest_sheet_version"] = None
        if include_relationships:
            payload["relationships"] = [
                self.relationship_to_dict(relationship, perspective_entity_id=entity.id)
                for relationship in sorted(
                    entity.outgoing_relationships + entity.incoming_relationships,
                    key=lambda item: (
                        item.relationship_type,
                        min(item.source_entity_id, item.target_entity_id),
                        max(item.source_entity_id, item.target_entity_id),
                    ),
                )
            ]
        if include_sheet_versions:
            payload["sheet_versions"] = [
                self.sheet_version_to_dict(version) for version in entity.sheet_versions
            ]
        return payload

    def relationship_to_dict(
        self,
        relationship: CampaignRelationship,
        *,
        perspective_entity_id: Optional[int] = None,
    ) -> dict[str, Any]:
        related_entity = relationship.target_entity
        direction = "outgoing"
        if perspective_entity_id == relationship.target_entity_id:
            related_entity = relationship.source_entity
            direction = "incoming"
        return {
            "id": relationship.id,
            "relationship_type": relationship.relationship_type,
            "strength": relationship.strength,
            "notes": relationship.notes,
            "created_at": relationship.created_at.isoformat(),
            "direction": direction,
            "source_entity": self._entity_ref(relationship.source_entity),
            "target_entity": self._entity_ref(relationship.target_entity),
            "related_entity": self._entity_ref(related_entity),
        }

    def sheet_version_to_dict(self, version: CharacterSheetVersion) -> dict[str, Any]:
        return {
            "id": version.id,
            "entity_id": version.entity_id,
            "version_number": version.version_number,
            "source_name": version.source_name,
            "payload": version.payload,
            "created_at": version.created_at.isoformat(),
        }

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ValueError(error_message) from exc

    async def _next_stable_key(self, entity_type: str, db: AsyncSession) -> str:
        prefix = self.stable_key_prefixes[entity_type]
        stmt = (
            select(CampaignEntity.stable_key)
            .where(CampaignEntity.entity_type == entity_type)
            .where(CampaignEntity.stable_key.like(f"{prefix}-%"))
            .order_by(CampaignEntity.stable_key.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        next_number = 1
        if existing:
            try:
                next_number = int(existing.rsplit("-", 1)[1]) + 1
            except (IndexError, ValueError):
                next_number = 1
        return f"{prefix}-{next_number:04d}"

    async def _validate_references(
        self,
        db: AsyncSession,
        *,
        entity_id: Optional[int] = None,
        parent_entity_id: Optional[int],
        current_location_id: Optional[int],
        owner_entity_id: Optional[int],
    ) -> None:
        if parent_entity_id is not None:
            if entity_id is not None and parent_entity_id == entity_id:
                raise ValueError("An entity cannot be its own parent")
            await self._require_entity(parent_entity_id, db)
        if current_location_id is not None:
            if entity_id is not None and current_location_id == entity_id:
                raise ValueError("An entity cannot be its own current location")
            location = await self._require_entity(current_location_id, db)
            if location.entity_type not in self.location_entity_types:
                raise ValueError("Current location must reference a location or shop")
        if owner_entity_id is not None:
            if entity_id is not None and owner_entity_id == entity_id:
                raise ValueError("An entity cannot own itself")
            await self._require_entity(owner_entity_id, db)

    async def _require_entity(self, entity_id: int, db: AsyncSession) -> CampaignEntity:
        entity = await self.get_entity(entity_id, db)
        if entity is None:
            raise LookupError(f"Referenced entity {entity_id} was not found")
        return entity

    def _normalize_entity_type(self, entity_type: str) -> str:
        normalized = entity_type.strip().lower()
        if normalized not in self.allowed_entity_types:
            raise ValueError(f"Unsupported entity_type '{entity_type}'")
        return normalized

    def _normalize_details(self, details: Optional[dict[str, Any]]) -> dict[str, Any]:
        if not details:
            return {}
        return {str(key): value for key, value in details.items()}

    def _merge_details(
        self,
        current_details: Optional[dict[str, Any]],
        incoming_details: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        merged = dict(current_details or {})
        for key, value in (incoming_details or {}).items():
            if isinstance(value, list):
                existing = merged.get(key)
                if isinstance(existing, list):
                    merged[key] = self._normalize_strings([*existing, *value])
                else:
                    merged[key] = self._normalize_strings(value)
            elif isinstance(value, dict):
                existing = merged.get(key)
                if isinstance(existing, dict):
                    merged[key] = {**existing, **value}
                else:
                    merged[key] = value
            elif value is not None:
                merged[key] = value
        return merged

    def _normalize_strings(self, values: Optional[Iterable[Any]]) -> list[str]:
        if not values:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(text)
        return normalized

    def _sync_pc_details(
        self, current_details: Optional[dict[str, Any]], payload: dict[str, Any]
    ) -> dict[str, Any]:
        merged = dict(current_details or {})
        for field in ("ancestry", "background", "class_name", "subclass", "notes"):
            value = payload.get(field)
            if value:
                merged[field] = value
        if payload.get("level") is not None:
            merged["level"] = payload["level"]
        for field in ("languages", "scripts", "goals", "hooks"):
            merged[field] = self._normalize_strings(payload.get(field))
        merged["notable_items"] = self._normalize_strings(
            self._item_labels(payload.get("items"))
        )
        return merged

    def _item_labels(self, items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        labels: list[str] = []
        for item in items:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict):
                name = item.get("name")
                if name:
                    labels.append(str(name))
        return labels

    def _entity_languages(self, entity: CampaignEntity) -> set[str]:
        values: set[str] = set()
        details = entity.details or {}
        for field in ("languages", "scripts", "dialects"):
            field_value = details.get(field)
            if isinstance(field_value, list):
                values.update(
                    str(value).strip().casefold()
                    for value in field_value
                    if str(value).strip()
                )
            elif isinstance(field_value, str) and field_value.strip():
                values.add(field_value.strip().casefold())
        return values

    def _entity_loader_options(self) -> list[Any]:
        return [
            joinedload(CampaignEntity.parent_entity),
            joinedload(CampaignEntity.current_location),
            joinedload(CampaignEntity.owner_entity),
            selectinload(CampaignEntity.outgoing_relationships).joinedload(
                CampaignRelationship.target_entity
            ),
            selectinload(CampaignEntity.incoming_relationships).joinedload(
                CampaignRelationship.source_entity
            ),
            selectinload(CampaignEntity.sheet_versions),
        ]

    def _entity_ref(self, entity: Optional[CampaignEntity]) -> Optional[dict[str, Any]]:
        if entity is None:
            return None
        return {
            "id": entity.id,
            "stable_key": entity.stable_key,
            "entity_type": entity.entity_type,
            "name": entity.name,
        }

    def _document_ref(self, document: Optional[Document]) -> Optional[dict[str, Any]]:
        if document is None:
            return None
        return {
            "id": document.id,
            "title": document.title,
            "kind": document.kind,
            "summary": document.summary,
            "source_name": document.source_name,
            "url": document.url,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
        }

    def _session_history_matches_query(
        self, item: dict[str, Any], q: Optional[str]
    ) -> bool:
        if not q:
            return True
        needle = q.strip().casefold()
        haystack = [
            item.get("title"),
            item.get("summary"),
            item.get("timeline_position"),
            item.get("scheduled_for"),
        ]
        event = item.get("event") or {}
        document = item.get("document") or {}
        haystack.extend(
            [
                event.get("name"),
                event.get("summary"),
                document.get("title"),
                document.get("summary"),
                document.get("source_name"),
            ]
        )
        return any(
            isinstance(value, str) and needle in value.casefold() for value in haystack
        )

    async def _get_relationship(
        self, relationship_id: int, db: AsyncSession
    ) -> Optional[CampaignRelationship]:
        stmt = (
            select(CampaignRelationship)
            .where(CampaignRelationship.id == relationship_id)
            .options(
                joinedload(CampaignRelationship.source_entity),
                joinedload(CampaignRelationship.target_entity),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().one_or_none()


campaign_service = CampaignService()
