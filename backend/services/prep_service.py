from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.campaign import CampaignEntity
from backend.models.document import Document
from backend.services.campaign_service import campaign_service
from backend.services.ingestion_service import ingestion_service


class PrepService:
    async def generate_session_brief(
        self,
        db: AsyncSession,
        *,
        title: Optional[str] = None,
        focus: Optional[str] = None,
        current_location_id: Optional[int] = None,
        session_count: int = 3,
        include_inactive: bool = False,
        store_document: bool = True,
        source_name: Optional[str] = None,
    ) -> dict[str, Any]:
        entities = await self._load_entities(db)
        active_entities = (
            entities
            if include_inactive
            else [entity for entity in entities if entity.is_active]
        )
        entity_by_id = {entity.id: entity for entity in entities}

        location = None
        if current_location_id is not None:
            location = entity_by_id.get(current_location_id)
            if location is None:
                raise LookupError("Prep location was not found")
            if location.entity_type not in campaign_service.location_entity_types:
                raise ValueError("Prep location must reference a location or shop")
        else:
            location = self._infer_focus_location(active_entities, entity_by_id)

        calendar_entity = self._select_current_calendar(active_entities)
        current_date = self._extract_current_date(calendar_entity)
        upcoming = self._collect_upcoming_items(active_entities, current_date)
        recent_sessions = await self._recent_sessions(db, session_count=session_count)
        spotlight = self._build_spotlight(
            active_entities,
            location=location,
            focus=focus,
            entity_by_id=entity_by_id,
        )
        focus_entities = self._collect_focus_entities(
            active_entities,
            focus=focus,
            location=location,
        )
        active_hooks = self._collect_active_hooks(
            active_entities,
            location=location,
            focus_entities=focus_entities,
        )
        continuity_flags = self._collect_continuity_flags(
            active_entities,
            current_date=current_date,
        )
        scene_seeds = self._build_scene_seeds(
            recent_sessions=recent_sessions,
            active_hooks=active_hooks,
            upcoming=upcoming,
            spotlight=spotlight,
            focus=focus,
            location=location,
        )

        resolved_title = title or self._default_title(
            focus=focus, location=location, recent_sessions=recent_sessions
        )
        payload = {
            "title": resolved_title,
            "focus": focus,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "location": self._entity_ref(location),
            "calendar": {
                "calendar": self._entity_ref(calendar_entity),
                "current_date": current_date,
                "upcoming": upcoming,
            },
            "recent_sessions": recent_sessions,
            "focus_entities": focus_entities,
            "spotlight": spotlight,
            "active_hooks": active_hooks,
            "continuity_flags": continuity_flags,
            "scene_seeds": scene_seeds,
        }
        markdown = self.render_markdown(payload)
        payload["markdown"] = markdown

        stored_document = None
        if store_document:
            stored_document = await ingestion_service.ingest_document(
                db,
                title=resolved_title,
                kind="session_prep",
                content=markdown,
                summary=self._document_summary(payload),
                source_name=source_name or "Phase 3 Prep Assistant",
                url=f"prep://session-brief/{self._slugify(resolved_title)}",
                dedupe_on_url=True,
            )
        payload["document"] = self._document_ref(stored_document)
        return payload

    def render_markdown(self, payload: dict[str, Any]) -> str:
        lines = [f"# {payload['title']}"]
        focus = payload.get("focus")
        location = payload.get("location")
        current_date = (payload.get("calendar") or {}).get("current_date") or {}
        if focus:
            lines.append(f"Focus: {focus}")
        if location:
            lines.append(f"Location: {location['name']}")
        if current_date:
            lines.append(f"Current Date: {self._format_current_date(current_date)}")
        lines.append("")

        lines.append("## Recap")
        recent_sessions = payload.get("recent_sessions") or []
        if recent_sessions:
            for item in recent_sessions:
                summary = item.get("summary") or "No summary recorded."
                lines.append(f"- {item['title']}: {summary}")
                event = item.get("event") or {}
                consequences = ((event.get("details") or {}).get("consequences")) or []
                for consequence in consequences[:2]:
                    lines.append(f"  - Consequence: {consequence}")
        else:
            lines.append("- No prior session history is available yet.")
        lines.append("")

        lines.append("## Spotlight")
        spotlight = payload.get("spotlight") or {}
        for label, items in (
            ("PCs", spotlight.get("pcs") or []),
            ("NPCs", spotlight.get("npcs") or []),
            ("Factions", spotlight.get("factions") or []),
            ("Artifacts", spotlight.get("artifacts") or []),
            ("Shops", spotlight.get("shops") or []),
        ):
            lines.append(f"### {label}")
            if items:
                for item in items:
                    details = item.get("details") or {}
                    summary_bits = []
                    if item.get("summary"):
                        summary_bits.append(item["summary"])
                    for field in ("goals", "hooks", "agenda", "stock_summary"):
                        values = details.get(field)
                        if isinstance(values, list) and values:
                            summary_bits.append(
                                ", ".join(str(value) for value in values[:2])
                            )
                            break
                    if summary_bits:
                        lines.append(f"- {item['name']}: {summary_bits[0]}")
                    else:
                        lines.append(f"- {item['name']}")
            else:
                lines.append("- None highlighted.")
        lines.append("")

        lines.append("## Active Hooks")
        hooks = payload.get("active_hooks") or []
        if hooks:
            for hook in hooks:
                owner = hook.get("entity")
                owner_name = owner["name"] if owner else "Campaign"
                lines.append(f"- {owner_name} ({hook['kind']}): {hook['text']}")
        else:
            lines.append("- No active hooks surfaced from the current campaign state.")
        lines.append("")

        lines.append("## Continuity Flags")
        flags = payload.get("continuity_flags") or []
        if flags:
            for flag in flags:
                lines.append(f"- [{flag['severity']}] {flag['message']}")
        else:
            lines.append("- No continuity flags detected.")
        lines.append("")

        lines.append("## Scene Seeds")
        scene_seeds = payload.get("scene_seeds") or []
        if scene_seeds:
            for seed in scene_seeds:
                location_name = (
                    seed["location"]["name"]
                    if isinstance(seed.get("location"), dict)
                    else "Flexible location"
                )
                lines.append(f"- {seed['title']} ({location_name})")
                lines.append(f"  - {seed['summary']}")
        else:
            lines.append("- No scene seeds available yet.")
        lines.append("")

        lines.append("## Calendar Watch")
        calendar = payload.get("calendar") or {}
        upcoming = calendar.get("upcoming") or []
        if upcoming:
            for item in upcoming:
                timing = item.get("timing") or "notable"
                when = (
                    item.get("scheduled_for") or item.get("date_label") or "unscheduled"
                )
                lines.append(f"- {item['name']} [{timing}] on {when}")
        else:
            lines.append("- No upcoming dates or events surfaced.")

        return "\n".join(lines).strip() + "\n"

    async def _load_entities(self, db: AsyncSession) -> list[CampaignEntity]:
        stmt = select(CampaignEntity).options(
            *campaign_service._entity_loader_options()
        )
        result = await db.execute(
            stmt.order_by(CampaignEntity.entity_type, CampaignEntity.name)
        )
        return list(result.scalars().unique().all())

    async def _recent_sessions(
        self, db: AsyncSession, *, session_count: int
    ) -> list[dict[str, Any]]:
        history = await campaign_service.get_session_history(
            db, page=1, page_size=max(1, session_count)
        )
        return history["items"]

    def _select_current_calendar(
        self, entities: list[CampaignEntity]
    ) -> Optional[CampaignEntity]:
        calendars = [entity for entity in entities if entity.entity_type == "calendar"]
        if not calendars:
            return None
        return max(calendars, key=lambda entity: entity.updated_at)

    def _extract_current_date(
        self, calendar_entity: Optional[CampaignEntity]
    ) -> dict[str, Any]:
        if calendar_entity is None:
            return {}
        details = calendar_entity.details or {}
        current_date = details.get("current_date")
        return current_date if isinstance(current_date, dict) else {}

    def _infer_focus_location(
        self,
        entities: list[CampaignEntity],
        entity_by_id: dict[int, CampaignEntity],
    ) -> Optional[CampaignEntity]:
        counts: Counter[int] = Counter()
        for entity in entities:
            if entity.current_location_id is not None and entity.entity_type in {
                "pc",
                "npc",
                "shop",
                "artifact",
            }:
                counts[entity.current_location_id] += 1
        if not counts:
            return None
        location_id, _ = counts.most_common(1)[0]
        location = entity_by_id.get(location_id)
        if location and location.entity_type in campaign_service.location_entity_types:
            return location
        return None

    def _collect_focus_entities(
        self,
        entities: list[CampaignEntity],
        *,
        focus: Optional[str],
        location: Optional[CampaignEntity],
    ) -> list[dict[str, Any]]:
        matching_entities = []
        for entity in entities:
            if focus and not self._entity_matches_focus(entity, focus):
                continue
            if location is not None and not self._entity_is_in_location(
                entity, location.id
            ):
                if entity.id != location.id and entity.entity_type != "faction":
                    continue
            matching_entities.append(entity)
        matching_entities.sort(key=lambda entity: (entity.entity_type, entity.name))
        refs: list[dict[str, Any]] = []
        for entity in matching_entities[:6]:
            entity_ref = self._entity_ref(entity)
            if entity_ref is not None:
                refs.append(entity_ref)
        return refs

    def _build_spotlight(
        self,
        entities: list[CampaignEntity],
        *,
        location: Optional[CampaignEntity],
        focus: Optional[str],
        entity_by_id: dict[int, CampaignEntity],
    ) -> dict[str, list[dict[str, Any]]]:
        scoped_entities = [
            entity
            for entity in entities
            if self._include_in_spotlight(entity, location=location, focus=focus)
        ]
        pcs = [entity for entity in scoped_entities if entity.entity_type == "pc"]
        npcs = [entity for entity in scoped_entities if entity.entity_type == "npc"]
        shops = [entity for entity in scoped_entities if entity.entity_type == "shop"]
        artifacts = [
            entity
            for entity in entities
            if entity.entity_type == "artifact"
            and (
                (location is not None and entity.current_location_id == location.id)
                or (
                    entity.owner_entity_id is not None
                    and entity_by_id.get(entity.owner_entity_id) in pcs + npcs
                )
            )
        ]

        faction_ids: set[int] = set()
        for entity in pcs + npcs:
            for relationship in (
                entity.outgoing_relationships + entity.incoming_relationships
            ):
                related = (
                    relationship.target_entity
                    if relationship.source_entity_id == entity.id
                    else relationship.source_entity
                )
                if related.entity_type == "faction":
                    faction_ids.add(related.id)

        if focus:
            for entity in entities:
                if entity.entity_type == "faction" and self._entity_matches_focus(
                    entity, focus
                ):
                    faction_ids.add(entity.id)

        factions = [entity_by_id[faction_id] for faction_id in sorted(faction_ids)]
        return {
            "pcs": [campaign_service.entity_to_dict(entity) for entity in pcs[:5]],
            "npcs": [campaign_service.entity_to_dict(entity) for entity in npcs[:5]],
            "factions": [
                campaign_service.entity_to_dict(entity) for entity in factions[:5]
            ],
            "artifacts": [
                campaign_service.entity_to_dict(entity)
                for entity in sorted(artifacts, key=lambda item: item.name)[:5]
            ],
            "shops": [campaign_service.entity_to_dict(entity) for entity in shops[:5]],
        }

    def _collect_active_hooks(
        self,
        entities: list[CampaignEntity],
        *,
        location: Optional[CampaignEntity],
        focus_entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        focus_entity_ids = {
            entity["id"] for entity in focus_entities if isinstance(entity, dict)
        }
        hooks: list[dict[str, Any]] = []
        for entity in entities:
            if entity.entity_type not in {"pc", "npc", "faction", "location"}:
                continue
            if location is not None and not self._entity_is_in_location(
                entity, location.id
            ):
                if entity.id != location.id and entity.id not in focus_entity_ids:
                    continue
            for field, kind in (("hooks", "hook"), ("goals", "goal")):
                for value in self._string_list((entity.details or {}).get(field)):
                    hooks.append(
                        {
                            "kind": kind,
                            "text": value,
                            "entity": self._entity_ref(entity),
                            "location": self._entity_ref(
                                entity.current_location or location
                            ),
                        }
                    )
        return hooks[:8]

    def _collect_continuity_flags(
        self,
        entities: list[CampaignEntity],
        *,
        current_date: dict[str, Any],
    ) -> list[dict[str, Any]]:
        flags: list[dict[str, Any]] = []
        for entity in entities:
            if entity.entity_type == "artifact":
                if (
                    entity.owner_entity_id is None
                    and entity.current_location_id is None
                ):
                    flags.append(
                        self._flag(
                            "warning",
                            f"Artifact {entity.name} has no owner or current location.",
                            entity,
                        )
                    )
            if (
                entity.entity_type in {"pc", "npc"}
                and entity.current_location_id is None
            ):
                flags.append(
                    self._flag(
                        "warning",
                        f"{entity.entity_type.upper()} {entity.name} has no current location.",
                        entity,
                    )
                )
            if entity.entity_type == "event":
                status = str((entity.details or {}).get("status") or "").strip().lower()
                scheduled_for = (entity.details or {}).get("scheduled_for")
                if status and status != "resolved" and scheduled_for:
                    comparison = self._compare_to_current_date(
                        scheduled_for, current_date
                    )
                    if comparison == -1:
                        flags.append(
                            self._flag(
                                "warning",
                                f"Event {entity.name} is past due for {scheduled_for} and still marked {status}.",
                                entity,
                            )
                        )
        return flags[:8]

    def _collect_upcoming_items(
        self, entities: list[CampaignEntity], current_date: dict[str, Any]
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entity in entities:
            if entity.entity_type == "event":
                status = str((entity.details or {}).get("status") or "").strip().lower()
                if status == "resolved":
                    continue
                scheduled_for = (entity.details or {}).get("scheduled_for")
                if scheduled_for:
                    timing = self._timing_label(
                        self._compare_to_current_date(scheduled_for, current_date)
                    )
                    items.append(
                        {
                            "name": entity.name,
                            "entity_type": entity.entity_type,
                            "scheduled_for": scheduled_for,
                            "summary": entity.summary,
                            "timing": timing,
                            "entity": self._entity_ref(entity),
                        }
                    )
            if entity.entity_type == "holiday":
                date_label = (entity.details or {}).get("date_label")
                if date_label:
                    timing = self._timing_label(
                        self._compare_to_current_date(date_label, current_date)
                    )
                    items.append(
                        {
                            "name": entity.name,
                            "entity_type": entity.entity_type,
                            "date_label": date_label,
                            "summary": entity.summary,
                            "timing": timing,
                            "entity": self._entity_ref(entity),
                        }
                    )
        items.sort(
            key=lambda item: (
                {"overdue": 0, "today": 1, "upcoming": 2, "notable": 3}.get(
                    item.get("timing") or "notable", 9
                ),
                item.get("scheduled_for") or item.get("date_label") or item["name"],
            )
        )
        return items[:6]

    def _build_scene_seeds(
        self,
        *,
        recent_sessions: list[dict[str, Any]],
        active_hooks: list[dict[str, Any]],
        upcoming: list[dict[str, Any]],
        spotlight: dict[str, list[dict[str, Any]]],
        focus: Optional[str],
        location: Optional[CampaignEntity],
    ) -> list[dict[str, Any]]:
        seeds: list[dict[str, Any]] = []
        participants = [
            *(spotlight.get("pcs") or []),
            *(spotlight.get("npcs") or []),
        ]
        participant_refs = [
            {
                "id": item["id"],
                "stable_key": item["stable_key"],
                "entity_type": item["entity_type"],
                "name": item["name"],
            }
            for item in participants[:3]
        ]

        if recent_sessions:
            latest = recent_sessions[0]
            seeds.append(
                {
                    "title": f"Aftermath: {latest['title']}",
                    "summary": latest.get("summary")
                    or "Review the fallout from the last session before moving forward.",
                    "source": "recent_session",
                    "location": self._entity_ref(location),
                    "participants": participant_refs,
                }
            )

        for hook in active_hooks[:3]:
            seeds.append(
                {
                    "title": f"Follow Up: {hook['text']}",
                    "summary": self._hook_seed_summary(hook, focus=focus),
                    "source": hook["kind"],
                    "location": hook.get("location") or self._entity_ref(location),
                    "participants": [
                        hook["entity"],
                        *[
                            participant
                            for participant in participant_refs
                            if participant["id"] != hook["entity"]["id"]
                        ][:2],
                    ],
                }
            )

        for item in upcoming[:2]:
            seeds.append(
                {
                    "title": f"Countdown: {item['name']}",
                    "summary": item.get("summary")
                    or "Bring this upcoming development on-screen before it goes stale.",
                    "source": item["entity_type"],
                    "location": self._entity_ref(location),
                    "participants": participant_refs,
                }
            )

        deduped: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for seed in seeds:
            title_key = seed["title"].casefold()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            deduped.append(seed)
        return deduped[:5]

    def _default_title(
        self,
        *,
        focus: Optional[str],
        location: Optional[CampaignEntity],
        recent_sessions: list[dict[str, Any]],
    ) -> str:
        if focus:
            return f"Prep Brief - {focus.title()}"
        if location is not None:
            return f"Prep Brief - {location.name}"
        if recent_sessions:
            return f"Prep Brief - {recent_sessions[0]['title']}"
        return "Prep Brief"

    def _document_summary(self, payload: dict[str, Any]) -> str:
        return (
            f"Session prep with {len(payload['scene_seeds'])} scene seeds, "
            f"{len(payload['active_hooks'])} active hooks, and "
            f"{len(payload['continuity_flags'])} continuity flags."
        )

    def _entity_matches_focus(self, entity: CampaignEntity, focus: str) -> bool:
        needle = focus.strip().casefold()
        if not needle:
            return False
        details = entity.details or {}
        haystack: list[str] = [
            entity.name,
            entity.summary or "",
            entity.description or "",
        ]
        for value in details.values():
            if isinstance(value, list):
                haystack.extend(str(item) for item in value)
            elif isinstance(value, dict):
                haystack.extend(str(item) for item in value.values())
            elif value is not None:
                haystack.append(str(value))
        return any(needle in value.casefold() for value in haystack if value)

    def _entity_is_in_location(self, entity: CampaignEntity, location_id: int) -> bool:
        return entity.id == location_id or entity.current_location_id == location_id

    def _include_in_spotlight(
        self,
        entity: CampaignEntity,
        *,
        location: Optional[CampaignEntity],
        focus: Optional[str],
    ) -> bool:
        if entity.entity_type not in {"pc", "npc", "shop"}:
            return False
        if location is not None and self._entity_is_in_location(entity, location.id):
            return True
        if focus and self._entity_matches_focus(entity, focus):
            return True
        return location is None and entity.entity_type == "pc"

    def _compare_to_current_date(
        self, candidate: Any, current_date: dict[str, Any]
    ) -> Optional[int]:
        current_parts = self._date_parts(current_date)
        candidate_parts = self._date_parts(candidate)
        if current_parts is None or candidate_parts is None:
            return None

        current_year, current_month, current_day = current_parts
        candidate_year, candidate_month, candidate_day = candidate_parts
        if (
            current_month
            and candidate_month
            and current_month.casefold() != candidate_month.casefold()
        ):
            return None
        if (
            current_year is not None
            and candidate_year is not None
            and current_year != candidate_year
        ):
            return -1 if candidate_year < current_year else 1
        if current_day is None or candidate_day is None:
            return None
        if candidate_day == current_day:
            return 0
        return -1 if candidate_day < current_day else 1

    def _date_parts(
        self, value: Any
    ) -> Optional[tuple[Optional[int], Optional[str], Optional[int]]]:
        if isinstance(value, dict):
            year = self._maybe_int(value.get("year"))
            month_value = value.get("month")
            month = str(month_value).strip() if month_value else None
            day = self._maybe_int(value.get("day"))
            if year is None and month is None and day is None:
                return None
            return year, month, day

        if isinstance(value, str):
            mapping = {}
            if "=" in value:
                for part in value.split(";"):
                    if "=" not in part:
                        continue
                    key, raw = part.split("=", 1)
                    mapping[key.strip().lower()] = raw.strip()
                return self._date_parts(mapping)

            match = re.match(
                r"^(?P<month>[A-Za-z' -]+)\s+(?P<day>\d{1,2})$", value.strip()
            )
            if match:
                return None, match.group("month").strip(), int(match.group("day"))
        return None

    def _timing_label(self, comparison: Optional[int]) -> str:
        if comparison == -1:
            return "overdue"
        if comparison == 0:
            return "today"
        if comparison == 1:
            return "upcoming"
        return "notable"

    def _hook_seed_summary(self, hook: dict[str, Any], *, focus: Optional[str]) -> str:
        owner = hook.get("entity") or {}
        owner_name = owner.get("name") or "the party"
        if focus:
            return f"Use {owner_name}'s {hook['kind']} to advance the session focus on {focus}."
        return f"Use {owner_name}'s {hook['kind']} to drive the next session beat."

    def _flag(
        self, severity: str, message: str, entity: Optional[CampaignEntity]
    ) -> dict[str, Any]:
        return {
            "severity": severity,
            "message": message,
            "entity": self._entity_ref(entity),
        }

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

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _format_current_date(self, current_date: dict[str, Any]) -> str:
        parts = []
        year = current_date.get("year")
        month = current_date.get("month")
        day = current_date.get("day")
        if year is not None:
            parts.append(str(year))
        if month:
            parts.append(str(month))
        if day is not None:
            parts.append(str(day))
        return " ".join(parts) if parts else "Unknown"

    def _slugify(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
        return normalized.strip("-") or "session-brief"

    def _maybe_int(self, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


prep_service = PrepService()
