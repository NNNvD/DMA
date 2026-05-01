from __future__ import annotations

import hashlib
import re
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_service import campaign_service
from backend.services.live_session_service import live_session_service
from backend.services.prep_service import prep_service
from backend.services.rules_service import rules_service


LiveAssistantMode = Literal[
    "auto",
    "scene",
    "rules",
    "continuity",
    "recap",
    "npc",
    "prep",
]


class LiveAssistantService:
    command_aliases: dict[str, LiveAssistantMode] = {
        "scene": "scene",
        "state": "scene",
        "rules": "rules",
        "rule": "rules",
        "continuity": "continuity",
        "search": "continuity",
        "entity": "continuity",
        "recap": "recap",
        "history": "recap",
        "npc": "npc",
        "improv": "npc",
        "prep": "prep",
        "brief": "prep",
    }
    scene_keyword_patterns = (
        "who is here",
        "who's here",
        "where are we",
        "what scene",
        "current scene",
        "scene state",
    )
    recap_keyword_patterns = (
        "what happened",
        "where did we leave off",
        "last session",
        "recent session",
        "recap",
    )
    prep_keyword_patterns = (
        "prep",
        "brief me",
        "session brief",
        "what should i prep",
    )
    npc_keyword_patterns = (
        "make up an npc",
        "improv npc",
        "new npc",
        "npc idea",
        "who could this be",
    )
    rules_keyword_patterns = (
        "how does",
        "what is the rule",
        "what's the rule",
        "what does",
        "can i",
        "when do",
        "does ",
        "do i ",
    )
    rules_terms = {
        "action",
        "actions",
        "attack",
        "bonus",
        "condition",
        "conditions",
        "dc",
        "demoralize",
        "feat",
        "flat-footed",
        "frightened",
        "grabbed",
        "initiative",
        "penalty",
        "persistent damage",
        "reaction",
        "spell",
        "spells",
        "status bonus",
        "trait",
        "traits",
    }

    async def respond(
        self,
        db: AsyncSession,
        *,
        message: str,
        mode: LiveAssistantMode = "auto",
    ) -> dict[str, Any]:
        normalized_message = self._normalize_message(message)
        if normalized_message is None:
            raise ValueError("Live assistant needs a command or question")

        snapshot = await live_session_service.load_snapshot(db)
        resolved_mode, query = self._resolve_mode(mode, normalized_message)

        if resolved_mode == "scene":
            response = self._scene_response(snapshot)
        elif resolved_mode == "rules":
            response = await self._rules_response(db, snapshot, query)
        elif resolved_mode == "continuity":
            response = await self._continuity_response(db, snapshot, query)
        elif resolved_mode == "recap":
            response = await self._recap_response(db, snapshot, query)
        elif resolved_mode == "npc":
            response = self._npc_response(snapshot, query)
        elif resolved_mode == "prep":
            response = await self._prep_response(db, snapshot, query)
        else:
            raise ValueError(f"Unsupported live assistant mode: {resolved_mode}")

        return {
            "message": normalized_message,
            "mode": resolved_mode,
            "query": query or None,
            "scene_context": self._scene_context(snapshot),
            **response,
        }

    def _resolve_mode(
        self, mode: LiveAssistantMode, message: str
    ) -> tuple[LiveAssistantMode, str]:
        explicit_mode = mode if mode != "auto" else None
        if explicit_mode is not None:
            return explicit_mode, self._strip_command_prefix(message, explicit_mode)

        slash_mode, slash_query = self._slash_command(message)
        if slash_mode is not None:
            return slash_mode, slash_query

        lowered = message.casefold()
        if any(pattern in lowered for pattern in self.scene_keyword_patterns):
            return "scene", message
        if any(pattern in lowered for pattern in self.recap_keyword_patterns):
            return "recap", message
        if any(pattern in lowered for pattern in self.npc_keyword_patterns):
            return "npc", message
        if any(pattern in lowered for pattern in self.prep_keyword_patterns):
            return "prep", message
        if self._looks_like_rules_query(lowered):
            return "rules", message
        return "continuity", message

    def _slash_command(self, message: str) -> tuple[LiveAssistantMode | None, str]:
        normalized = message.strip()
        if not normalized.startswith("/"):
            return None, normalized
        command, _, remainder = normalized[1:].partition(" ")
        mode = self.command_aliases.get(command.casefold())
        return mode, remainder.strip()

    def _strip_command_prefix(self, message: str, mode: LiveAssistantMode) -> str:
        slash_mode, remainder = self._slash_command(message)
        if slash_mode == mode:
            return remainder
        return message.strip()

    def _looks_like_rules_query(self, message: str) -> bool:
        if any(pattern in message for pattern in self.rules_keyword_patterns):
            return True
        return any(term in message for term in self.rules_terms)

    def _scene_response(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        state = snapshot.get("state") or {}
        active_pcs = snapshot.get("active_pcs") or []
        active_npcs = snapshot.get("active_npcs") or []
        current_location = snapshot.get("current_location")
        current_date = snapshot.get("current_date")

        if not any(
            [
                state.get("scene_title"),
                state.get("focus"),
                current_location,
                active_pcs,
                active_npcs,
                state.get("notes"),
            ]
        ):
            return {
                "answer": (
                    "No live scene state is saved yet. Fill in the Current Scene panel "
                    "to anchor live answers."
                ),
                "citations": [],
                "entities": [],
                "recent_sessions": [],
                "prep": None,
            }

        lines = []
        if state.get("scene_title"):
            lines.append(f"Scene: {state['scene_title']}")
        if state.get("focus"):
            lines.append(f"Focus: {state['focus']}")
        if current_location:
            lines.append(f"Location: {current_location['name']}")
        if current_date:
            lines.append(f"Current Date: {self._format_current_date(current_date)}")
        if active_pcs:
            lines.append(
                "Active PCs: " + ", ".join(item["name"] for item in active_pcs)
            )
        if active_npcs:
            lines.append(
                "Active NPCs: " + ", ".join(item["name"] for item in active_npcs)
            )
        if state.get("notes"):
            lines.append(f"Live Notes: {state['notes']}")

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": [*active_pcs, *active_npcs],
            "recent_sessions": snapshot.get("recent_sessions") or [],
            "prep": snapshot.get("latest_prep"),
        }

    async def _rules_response(
        self,
        db: AsyncSession,
        snapshot: dict[str, Any],
        query: str,
    ) -> dict[str, Any]:
        normalized_query = self._normalize_message(query)
        if normalized_query is None:
            raise ValueError(
                "Rules mode needs a query, for example '/rules frightened'"
            )

        frugal_mode = bool((snapshot.get("state") or {}).get("frugal_mode"))
        top_k = 2 if frugal_mode else 4
        result = await rules_service.answer_question(
            normalized_query,
            db,
            top_k=top_k,
            strict=True,
        )
        context_line = self._scene_anchor_line(snapshot)
        answer = result["answer"]
        if context_line:
            answer = f"{answer}\n\nLive context: {context_line}"

        return {
            "answer": answer,
            "citations": result.get("citations") or [],
            "entities": [],
            "recent_sessions": [],
            "prep": None,
        }

    async def _continuity_response(
        self,
        db: AsyncSession,
        snapshot: dict[str, Any],
        query: str,
    ) -> dict[str, Any]:
        normalized_query = self._normalize_message(query)
        if normalized_query is None:
            raise ValueError(
                "Continuity mode needs a name or topic, for example '/search Captain Mira'"
            )

        frugal_mode = bool((snapshot.get("state") or {}).get("frugal_mode"))
        page_size = 3 if frugal_mode else 5

        exact_entity = await campaign_service.find_entity_by_reference(
            db, normalized_query
        )
        search_payload = await campaign_service.list_entities(
            db,
            q=normalized_query,
            page=1,
            page_size=page_size,
        )
        search_items = search_payload["items"]
        session_matches = await campaign_service.get_session_history(
            db,
            q=normalized_query,
            page=1,
            page_size=2 if frugal_mode else 3,
        )

        primary_payload = None
        if exact_entity is not None:
            primary_payload = campaign_service.entity_to_dict(
                exact_entity,
                include_relationships=True,
                include_sheet_versions=exact_entity.entity_type == "pc",
            )
        elif search_items:
            entity = await campaign_service.get_entity(search_items[0]["id"], db)
            if entity is not None:
                primary_payload = campaign_service.entity_to_dict(
                    entity,
                    include_relationships=True,
                    include_sheet_versions=entity.entity_type == "pc",
                )

        if primary_payload is None and not session_matches["items"]:
            return {
                "answer": f"No continuity match found for '{normalized_query}'.",
                "citations": [],
                "entities": [],
                "recent_sessions": [],
                "prep": None,
            }

        lines = []
        if primary_payload is not None:
            lines.append(
                f"Best match: {primary_payload['name']} ({primary_payload['entity_type']})"
            )
            if primary_payload.get("summary"):
                lines.append(str(primary_payload["summary"]))
            if primary_payload.get("current_location"):
                lines.append(
                    "Current location: " + primary_payload["current_location"]["name"]
                )
            detail_bits = self._detail_bits(primary_payload.get("details") or {})
            if detail_bits:
                lines.append("Key details: " + "; ".join(detail_bits))
            relationship_bits = self._relationship_bits(
                primary_payload.get("relationships") or []
            )
            if relationship_bits:
                lines.append("Relationships: " + "; ".join(relationship_bits))

        other_matches = [
            item["name"]
            for item in search_items
            if primary_payload is None or item["id"] != primary_payload["id"]
        ][:3]
        if other_matches:
            lines.append("Other close matches: " + ", ".join(other_matches))

        session_titles = [item["title"] for item in session_matches["items"][:3]]
        if session_titles:
            lines.append("Matching sessions: " + ", ".join(session_titles))

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": search_items,
            "recent_sessions": session_matches["items"],
            "prep": None,
        }

    async def _recap_response(
        self,
        db: AsyncSession,
        snapshot: dict[str, Any],
        query: str,
    ) -> dict[str, Any]:
        normalized_query = self._normalize_message(query)
        frugal_mode = bool((snapshot.get("state") or {}).get("frugal_mode"))
        page_size = 2 if frugal_mode else 3

        if normalized_query:
            sessions = await campaign_service.get_session_history(
                db,
                q=normalized_query,
                page=1,
                page_size=page_size,
            )
            items = sessions["items"]
        else:
            items = (snapshot.get("recent_sessions") or [])[:page_size]

        if not items:
            return {
                "answer": "No session history is available yet.",
                "citations": [],
                "entities": [],
                "recent_sessions": [],
                "prep": None,
            }

        lines = []
        current_date = snapshot.get("current_date")
        if current_date:
            lines.append(f"Current Date: {self._format_current_date(current_date)}")
        for item in items:
            summary = item.get("summary") or "No summary recorded."
            lines.append(f"- {item['title']}: {self._truncate(summary, 220)}")

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": [],
            "recent_sessions": items,
            "prep": None,
        }

    async def _prep_response(
        self,
        db: AsyncSession,
        snapshot: dict[str, Any],
        query: str,
    ) -> dict[str, Any]:
        state = snapshot.get("state") or {}
        focus = self._normalize_message(query) or state.get("focus")
        current_location_id = state.get("current_location_id")
        frugal_mode = bool(state.get("frugal_mode"))
        payload = await prep_service.generate_session_brief(
            db,
            title="Live Session Brief",
            focus=focus,
            current_location_id=current_location_id,
            session_count=2 if frugal_mode else 3,
            store_document=False,
            source_name="Phase 4 Live Assistant",
        )

        lines = [payload["title"]]
        if payload.get("focus"):
            lines.append(f"Focus: {payload['focus']}")
        if payload.get("location"):
            lines.append(f"Location: {payload['location']['name']}")

        hooks = [
            hook["text"]
            for hook in (payload.get("active_hooks") or [])
            if hook.get("text")
        ][:3]
        if hooks:
            lines.append("Hooks: " + "; ".join(hooks))

        flags = [
            f"[{flag['severity']}] {flag['message']}"
            for flag in (payload.get("continuity_flags") or [])
        ][:2]
        if flags:
            lines.append("Continuity flags: " + "; ".join(flags))

        seeds = [
            f"{seed['title']}: {seed['summary']}"
            for seed in (payload.get("scene_seeds") or [])
        ][:2]
        if seeds:
            lines.append("Scene seeds: " + "; ".join(seeds))

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": payload.get("focus_entities") or [],
            "recent_sessions": payload.get("recent_sessions") or [],
            "prep": {
                "title": payload["title"],
                "focus": payload.get("focus"),
                "location": payload.get("location"),
                "markdown": payload.get("markdown"),
            },
        }

    def _npc_response(self, snapshot: dict[str, Any], query: str) -> dict[str, Any]:
        normalized_query = self._normalize_message(query) or "local contact"
        state = snapshot.get("state") or {}
        current_location = snapshot.get("current_location")
        active_npcs = snapshot.get("active_npcs") or []

        name = self._extract_name_candidate(normalized_query) or self._generated_name(
            normalized_query,
            snapshot,
        )
        role = self._npc_role(normalized_query)
        demeanor = self._pick_option(
            normalized_query,
            "demeanor",
            [
                "guarded and watchful",
                "warm until pressed",
                "dryly amused by danger",
                "eager to please the strongest person in the room",
                "tired, sharp, and one bad question from snapping",
                "measured and almost too calm",
            ],
        )
        motive = self._pick_option(
            normalized_query,
            "motive",
            [
                "protect their own skin first",
                "keep a valuable secret buried",
                "turn the current crisis into leverage",
                "pay off a debt before dawn",
                "prove they belong in the room",
                "quietly test whether the party can be trusted",
            ],
        )
        leverage = self._pick_option(
            normalized_query,
            "leverage",
            [
                "knows who moved through the area an hour ago",
                "has access to a key, ledger, or sealed room",
                "heard the wrong conversation at exactly the right time",
                "can point the party toward a hidden witness",
                "is protecting someone the party already cares about",
                "owes money to the wrong faction",
            ],
        )
        voice = self._pick_option(
            normalized_query,
            "voice",
            [
                "short answers, clipped cadence, watches every reaction",
                "too-polite phrases wrapped around quiet contempt",
                "soft voice, but never apologizes for anything",
                "talks fast when nervous, then abruptly goes silent",
                "drops local slang to sound more rooted than they are",
                "speaks plainly and expects everyone else to keep up",
            ],
        )

        scene_bits = []
        if state.get("scene_title"):
            scene_bits.append(state["scene_title"])
        if current_location:
            scene_bits.append(current_location["name"])
        if state.get("focus"):
            scene_bits.append(state["focus"])
        scene_anchor = ", ".join(scene_bits) or "the current scene"
        opening_line = self._opening_line(name, role, scene_anchor, leverage)

        npc_payload = {
            "name": name,
            "role": role,
            "demeanor": demeanor,
            "motive": motive,
            "leverage": leverage,
            "voice": voice,
            "scene_anchor": scene_anchor,
            "current_location": current_location,
        }

        lines = [
            f"Improvised NPC: {name}",
            f"Role: {role}",
            f"Demeanor: {demeanor}",
            f"Wants: {motive}",
            f"Useful leverage: {leverage}",
            f"Voice: {voice}",
            f'Opening line: "{opening_line}"',
            f"Use in scene: fold them into {scene_anchor}.",
        ]
        if active_npcs:
            lines.append(
                "Avoid overlap with: "
                + ", ".join(item["name"] for item in active_npcs[:3])
            )

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": active_npcs,
            "recent_sessions": snapshot.get("recent_sessions") or [],
            "prep": None,
            "npc": npc_payload,
        }

    def _scene_context(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        state = snapshot.get("state") or {}
        return {
            "scene_title": state.get("scene_title"),
            "focus": state.get("focus"),
            "frugal_mode": bool(state.get("frugal_mode")),
            "maptool_map_id": state.get("maptool_map_id"),
            "current_location": snapshot.get("current_location"),
            "active_pcs": snapshot.get("active_pcs") or [],
            "active_npcs": snapshot.get("active_npcs") or [],
            "current_date": snapshot.get("current_date"),
            "maptool": snapshot.get("maptool"),
        }

    def _scene_anchor_line(self, snapshot: dict[str, Any]) -> str | None:
        parts = []
        state = snapshot.get("state") or {}
        current_location = snapshot.get("current_location")
        if state.get("scene_title"):
            parts.append(state["scene_title"])
        if state.get("focus"):
            parts.append(state["focus"])
        if current_location:
            parts.append(current_location["name"])
        if not parts:
            return None
        return " | ".join(parts)

    def _detail_bits(self, details: dict[str, Any], *, limit: int = 3) -> list[str]:
        bits: list[str] = []
        for key, value in details.items():
            if key in {"body", "content", "markdown", "notes", "raw", "text"}:
                continue
            label = key.replace("_", " ")
            normalized = self._format_detail_value(value)
            if normalized is None:
                continue
            bits.append(f"{label}: {normalized}")
            if len(bits) >= limit:
                break
        return bits

    def _relationship_bits(
        self, relationships: list[dict[str, Any]], *, limit: int = 3
    ) -> list[str]:
        bits = []
        for relationship in relationships[:limit]:
            related = relationship.get("related_entity") or {}
            related_name = related.get("name")
            if not related_name:
                continue
            relation = str(relationship.get("relationship_type") or "related to")
            relation = relation.replace("_", " ").replace("-", " ").strip()
            bits.append(f"{relation} {related_name}")
        return bits

    def _format_current_date(self, current_date: dict[str, Any]) -> str:
        label = current_date.get("label")
        if label:
            return str(label)
        parts = [
            str(current_date[key])
            for key in ("year", "month", "day")
            if current_date.get(key) is not None
        ]
        if current_date.get("calendar_name"):
            parts.append(f"({current_date['calendar_name']})")
        return " ".join(parts).strip() or "Unknown date"

    def _format_detail_value(self, value: Any) -> str | None:
        if value in (None, "", [], {}):
            return None
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return self._truncate(value, 100)
        if isinstance(value, list):
            items = [self._format_detail_value(item) for item in value[:3]]
            normalized_items = [item for item in items if item]
            if normalized_items:
                return ", ".join(normalized_items)
            return None
        if isinstance(value, dict):
            scalar_pairs = []
            for key, item in value.items():
                normalized_item = self._format_detail_value(item)
                if normalized_item is None:
                    continue
                scalar_pairs.append(f"{key.replace('_', ' ')}: {normalized_item}")
                if len(scalar_pairs) >= 2:
                    break
            if scalar_pairs:
                return ", ".join(scalar_pairs)
        return None

    def _normalize_message(self, message: str | None) -> str | None:
        if message is None:
            return None
        cleaned = re.sub(r"\s+", " ", str(message)).strip()
        return cleaned or None

    def _extract_name_candidate(self, prompt: str) -> str | None:
        match = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)\b", prompt)
        if match:
            return match.group(1)
        return None

    def _generated_name(self, prompt: str, snapshot: dict[str, Any]) -> str:
        state = snapshot.get("state") or {}
        current_location = snapshot.get("current_location") or {}
        seed = "|".join(
            [
                prompt.casefold(),
                str(state.get("scene_title") or ""),
                str(current_location.get("name") or ""),
            ]
        )
        first_names = [
            "Aveline",
            "Bren",
            "Calia",
            "Dain",
            "Elsbet",
            "Hollis",
            "Iria",
            "Joran",
            "Mira",
            "Nessa",
            "Orin",
            "Tavian",
        ]
        last_names = [
            "Ashdown",
            "Briar",
            "Dunmere",
            "Fen",
            "Hart",
            "Keel",
            "Morrow",
            "Pell",
            "Reeve",
            "Thorne",
            "Vale",
            "Wren",
        ]
        return (
            f"{self._pick_option(seed, 'first-name', first_names)} "
            f"{self._pick_option(seed, 'last-name', last_names)}"
        )

    def _npc_role(self, prompt: str) -> str:
        cleaned = prompt.strip()
        if cleaned.startswith(("a ", "an ", "the ")):
            return cleaned
        if len(cleaned.split()) <= 5:
            return cleaned
        return self._truncate(cleaned, 48)

    def _opening_line(
        self,
        name: str,
        role: str,
        scene_anchor: str,
        leverage: str,
    ) -> str:
        snippets = [
            f"I am {name}, and if this is about {scene_anchor}, we should speak quietly.",
            f"If you came to question a {role}, ask quickly.",
            "I can help, but only if you understand this: someone is lying.",
            "You want answers. I want to survive the hour. We may be able to help each other.",
            f"Before you accuse anyone, know this: {leverage}.",
        ]
        return self._pick_option(name + role + scene_anchor, "opening-line", snippets)

    def _pick_option(self, seed_text: str, salt: str, options: list[str]) -> str:
        if not options:
            return ""
        digest = hashlib.sha256(f"{seed_text}|{salt}".encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % len(options)
        return options[index]

    def _truncate(self, value: str, max_chars: int) -> str:
        cleaned = " ".join(str(value).split())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."


live_assistant_service = LiveAssistantService()
