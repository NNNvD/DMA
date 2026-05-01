from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.maptool import CampaignMapState
from backend.services.context_service import context_service
from backend.services.maptool_adapter import maptool_adapter


LIVE_MAPTOOL_CONTEXT_KEY = "live-maptool-state"


class LiveMapToolService:
    async def load_snapshot(self, db: AsyncSession) -> dict[str, Any] | None:
        entry = await context_service.load(LIVE_MAPTOOL_CONTEXT_KEY, db)
        if entry is None:
            return None
        snapshot = dict(entry.data or {})
        snapshot["tokens"] = self._normalize_tokens(snapshot.get("tokens"))
        snapshot["mechanics"] = self._normalize_mechanics(snapshot.get("mechanics"))
        return snapshot

    async def sync_map_state(
        self,
        db: AsyncSession,
        *,
        map_id: str,
        auth_header: str | None = None,
        retries: int | None = None,
    ) -> dict[str, Any]:
        normalized_map_id = (map_id or "").strip()
        if not normalized_map_id:
            raise ValueError("MapTool sync needs a map_id")

        map_state = await maptool_adapter.pull_map_state(
            normalized_map_id,
            auth_header=auth_header,
            retries=retries,
        )
        snapshot = self._build_snapshot(map_state)
        await context_service.save(LIVE_MAPTOOL_CONTEXT_KEY, snapshot, db)
        return snapshot

    async def reset(self, db: AsyncSession) -> bool:
        return await context_service.delete(LIVE_MAPTOOL_CONTEXT_KEY, db)

    def _build_snapshot(self, map_state: CampaignMapState) -> dict[str, Any]:
        token_payloads = [token.model_dump() for token in map_state.tokens]
        mechanics = self._build_mechanics(token_payloads)
        return {
            "map_id": map_state.map_id,
            "name": map_state.name,
            "fog_state": map_state.fog_state,
            "light_state": map_state.light_state,
            "tokens": token_payloads,
            "mechanics": mechanics,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_mechanics(self, tokens: list[dict[str, Any]]) -> dict[str, Any]:
        combatants = [self._combatant_payload(token) for token in tokens]
        initiative_order = sorted(
            [item for item in combatants if item["initiative"] is not None],
            key=lambda item: (-float(item["initiative"]), item["label"].casefold()),
        )
        conditioned = [
            item for item in combatants if item.get("conditions") or item["low_hp"]
        ]
        return {
            "combatants": combatants,
            "initiative_order": initiative_order,
            "conditioned_tokens": conditioned,
            "summary": {
                "token_count": len(combatants),
                "initiative_count": len(initiative_order),
                "condition_count": sum(
                    len(item.get("conditions") or []) for item in combatants
                ),
                "low_hp_count": sum(1 for item in combatants if item["low_hp"]),
            },
        }

    def _combatant_payload(self, token: dict[str, Any]) -> dict[str, Any]:
        hp_current = self._coerce_int(token.get("hp_current"))
        hp_max = self._coerce_int(token.get("hp_max"))
        hp_trackable = hp_current is not None and hp_max is not None and hp_max > 0
        hp_percent = None
        low_hp = False
        if hp_trackable:
            assert hp_current is not None
            assert hp_max is not None
            hp_percent = round((hp_current / hp_max) * 100, 1)
            low_hp = (hp_current / hp_max) <= 0.5
        conditions = [str(item) for item in (token.get("conditions") or []) if item]
        return {
            **token,
            "hp_current": hp_current,
            "hp_max": hp_max,
            "initiative": self._coerce_float(token.get("initiative")),
            "conditions": conditions,
            "hp_percent": hp_percent,
            "low_hp": low_hp,
        }

    def _normalize_tokens(self, tokens: Any) -> list[dict[str, Any]]:
        if not isinstance(tokens, list):
            return []
        return [
            self._combatant_payload(token)
            for token in tokens
            if isinstance(token, dict)
        ]

    def _normalize_mechanics(self, mechanics: Any) -> dict[str, Any]:
        if not isinstance(mechanics, dict):
            return self._build_mechanics([])
        combatants = self._normalize_tokens(mechanics.get("combatants"))
        initiative_order = sorted(
            [item for item in combatants if item["initiative"] is not None],
            key=lambda item: (-float(item["initiative"]), item["label"].casefold()),
        )
        conditioned = [
            item for item in combatants if item.get("conditions") or item["low_hp"]
        ]
        summary = mechanics.get("summary")
        if not isinstance(summary, dict):
            summary = {}
        return {
            "combatants": combatants,
            "initiative_order": initiative_order,
            "conditioned_tokens": conditioned,
            "summary": {
                "token_count": int(summary.get("token_count") or len(combatants)),
                "initiative_count": int(
                    summary.get("initiative_count") or len(initiative_order)
                ),
                "condition_count": int(
                    summary.get("condition_count")
                    or sum(len(item.get("conditions") or []) for item in combatants)
                ),
                "low_hp_count": int(
                    summary.get("low_hp_count")
                    or sum(1 for item in combatants if item["low_hp"])
                ),
            },
        }

    def _coerce_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _coerce_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


live_maptool_service = LiveMapToolService()
