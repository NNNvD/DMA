from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.document import Document
from backend.services.campaign_service import campaign_service
from backend.services.context_service import context_service
from backend.services.live_maptool_service import live_maptool_service


LIVE_SESSION_CONTEXT_KEY = "live-session-state"


class LiveSessionService:
    default_state: dict[str, Any] = {
        "scene_title": None,
        "focus": None,
        "current_location_id": None,
        "active_pc_ids": [],
        "active_npc_ids": [],
        "maptool_map_id": None,
        "notes": None,
        "frugal_mode": False,
        "combat_state": {
            "roomId": "",
            "roomTitle": "",
            "round": 1,
            "activeIndex": 0,
            "combatants": [],
            "afflictions": [],
        },
    }

    async def load_snapshot(self, db: AsyncSession) -> dict[str, Any]:
        state = await self._load_state(db)
        current_location = await self._resolve_location(
            db, state.get("current_location_id")
        )
        active_pcs = await self._resolve_entities(
            db,
            state.get("active_pc_ids") or [],
            entity_type="pc",
        )
        active_npcs = await self._resolve_entities(
            db,
            state.get("active_npc_ids") or [],
            entity_type="npc",
        )
        overview = await campaign_service.get_overview(db)
        calendars = overview.get("calendars") or []
        recent_sessions = (
            await campaign_service.get_session_history(db, page=1, page_size=5)
        )["items"]
        latest_prep = await self._latest_prep_document(db)
        maptool = await live_maptool_service.load_snapshot(db)

        locations = sorted(
            [*(overview.get("locations") or []), *(overview.get("shops") or [])],
            key=lambda item: item["name"],
        )
        return {
            "state": state,
            "current_location": current_location,
            "active_pcs": active_pcs,
            "active_npcs": active_npcs,
            "available": {
                "locations": locations,
                "pcs": overview.get("pcs") or [],
                "npcs": overview.get("npcs") or [],
            },
            "current_date": self._current_date(calendars),
            "recent_sessions": recent_sessions,
            "latest_prep": latest_prep,
            "maptool": maptool,
        }

    async def save_state(
        self,
        db: AsyncSession,
        *,
        scene_title: str | None = None,
        focus: str | None = None,
        current_location_id: int | None = None,
        active_pc_ids: list[int] | None = None,
        active_npc_ids: list[int] | None = None,
        maptool_map_id: str | None = None,
        notes: str | None = None,
        frugal_mode: bool = False,
        combat_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing_state = await self._load_state(db)
        location_id = await self._validate_location_id(db, current_location_id)
        pc_ids = await self._validate_entity_ids(
            db, active_pc_ids or [], entity_type="pc"
        )
        npc_ids = await self._validate_entity_ids(
            db, active_npc_ids or [], entity_type="npc"
        )
        normalized_maptool_map_id = self._normalize_optional_text(maptool_map_id)
        if existing_state.get("maptool_map_id") != normalized_maptool_map_id:
            await live_maptool_service.reset(db)
        state = {
            "scene_title": self._normalize_optional_text(scene_title),
            "focus": self._normalize_optional_text(focus),
            "current_location_id": location_id,
            "active_pc_ids": pc_ids,
            "active_npc_ids": npc_ids,
            "maptool_map_id": normalized_maptool_map_id,
            "notes": self._normalize_optional_text(notes),
            "frugal_mode": bool(frugal_mode),
            "combat_state": self._normalize_combat_state(
                combat_state
                if combat_state is not None
                else existing_state.get("combat_state")
            ),
        }
        await context_service.save(LIVE_SESSION_CONTEXT_KEY, state, db)
        return await self.load_snapshot(db)

    async def set_maptool_map_id(
        self,
        db: AsyncSession,
        maptool_map_id: str | None,
        *,
        reset_maptool_snapshot: bool = True,
    ) -> dict[str, Any]:
        state = await self._load_state(db)
        normalized_maptool_map_id = self._normalize_optional_text(maptool_map_id)
        if (
            reset_maptool_snapshot
            and state.get("maptool_map_id") != normalized_maptool_map_id
        ):
            await live_maptool_service.reset(db)
        state["maptool_map_id"] = normalized_maptool_map_id
        await context_service.save(LIVE_SESSION_CONTEXT_KEY, state, db)
        return await self.load_snapshot(db)

    async def reset_state(self, db: AsyncSession) -> dict[str, Any]:
        await context_service.delete(LIVE_SESSION_CONTEXT_KEY, db)
        await live_maptool_service.reset(db)
        return await self.load_snapshot(db)

    async def _load_state(self, db: AsyncSession) -> dict[str, Any]:
        entry = await context_service.load(LIVE_SESSION_CONTEXT_KEY, db)
        state: dict[str, Any] = dict(self.default_state)
        if entry:
            state.update(dict(entry.data or {}))
        state["active_pc_ids"] = self._dedupe_ids(
            self._coerce_list(state.get("active_pc_ids"))
        )
        state["active_npc_ids"] = self._dedupe_ids(
            self._coerce_list(state.get("active_npc_ids"))
        )
        state["scene_title"] = self._normalize_optional_text(state.get("scene_title"))
        state["focus"] = self._normalize_optional_text(state.get("focus"))
        state["notes"] = self._normalize_optional_text(state.get("notes"))
        state["maptool_map_id"] = self._normalize_optional_text(
            state.get("maptool_map_id")
        )
        state["current_location_id"] = self._coerce_optional_int(
            state.get("current_location_id")
        )
        state["frugal_mode"] = bool(state.get("frugal_mode"))
        state["combat_state"] = self._normalize_combat_state(
            state.get("combat_state")
        )
        return state

    async def _resolve_location(
        self, db: AsyncSession, location_id: int | None
    ) -> dict[str, Any] | None:
        if location_id is None:
            return None
        entity = await campaign_service.get_entity(location_id, db)
        if (
            entity is None
            or entity.entity_type not in campaign_service.location_entity_types
        ):
            return None
        return campaign_service.entity_to_dict(entity)

    async def _resolve_entities(
        self, db: AsyncSession, entity_ids: list[int], *, entity_type: str
    ) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []
        for entity_id in self._dedupe_ids(entity_ids):
            entity = await campaign_service.get_entity(entity_id, db)
            if entity is None or entity.entity_type != entity_type:
                continue
            resolved.append(campaign_service.entity_to_dict(entity))
        return resolved

    async def _validate_location_id(
        self, db: AsyncSession, location_id: int | None
    ) -> int | None:
        if location_id is None:
            return None
        entity = await campaign_service.get_entity(location_id, db)
        if entity is None:
            raise LookupError("Current location was not found")
        if entity.entity_type not in campaign_service.location_entity_types:
            raise ValueError("Current location must reference a location or shop")
        return entity.id

    async def _validate_entity_ids(
        self, db: AsyncSession, entity_ids: list[int], *, entity_type: str
    ) -> list[int]:
        validated: list[int] = []
        for entity_id in self._dedupe_ids(entity_ids):
            entity = await campaign_service.get_entity(entity_id, db)
            if entity is None:
                raise LookupError(f"Campaign entity {entity_id} was not found")
            if entity.entity_type != entity_type:
                raise ValueError(
                    f"Expected {entity_type} entity for id {entity_id}, got {entity.entity_type}"
                )
            validated.append(entity.id)
        return validated

    async def _latest_prep_document(self, db: AsyncSession) -> dict[str, Any] | None:
        stmt = (
            select(Document)
            .where(Document.kind == "session_prep")
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            return None
        return {
            "id": document.id,
            "title": document.title,
            "summary": document.summary,
            "updated_at": document.updated_at.isoformat(),
        }

    def _current_date(self, calendars: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not calendars:
            return None
        sorted_calendars = sorted(
            calendars,
            key=lambda item: item.get("updated_at") or "",
            reverse=True,
        )
        for calendar in sorted_calendars:
            details = calendar.get("details") or {}
            current_date = details.get("current_date")
            if isinstance(current_date, dict) and current_date:
                return {
                    "calendar_name": calendar["name"],
                    **current_date,
                }
        return None

    def _normalize_optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _dedupe_ids(self, values: list[Any]) -> list[int]:
        seen: set[int] = set()
        deduped: list[int] = []
        for value in values:
            try:
                normalized = int(value)
            except (TypeError, ValueError):
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _coerce_list(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        return []

    def _coerce_optional_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize_combat_state(self, value: Any) -> dict[str, Any]:
        default = dict(self.default_state["combat_state"])
        if not isinstance(value, dict):
            return default

        combatants = value.get("combatants")
        if not isinstance(combatants, list):
            combatants = []
        afflictions = value.get("afflictions")
        if not isinstance(afflictions, list):
            afflictions = []

        try:
            round_number = max(1, int(value.get("round") or 1))
        except (TypeError, ValueError):
            round_number = 1

        try:
            active_index = max(0, int(value.get("activeIndex") or 0))
        except (TypeError, ValueError):
            active_index = 0

        if combatants and active_index >= len(combatants):
            active_index = len(combatants) - 1

        return {
            "roomId": self._normalize_optional_text(value.get("roomId")) or "",
            "roomTitle": self._normalize_optional_text(value.get("roomTitle")) or "",
            "round": round_number,
            "activeIndex": active_index,
            "combatants": combatants,
            "afflictions": afflictions,
        }


live_session_service = LiveSessionService()
