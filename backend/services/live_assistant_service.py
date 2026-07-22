from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_service import campaign_service
from backend.services.live_session_service import live_session_service
from backend.services.prep_service import prep_service
from backend.services.private_index_service import private_index_service
from backend.services.rules_service import rules_service


LiveAssistantMode = Literal[
    "auto",
    "scene",
    "rules",
    "continuity",
    "recap",
    "npc",
    "prep",
    "memory",
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
        "memory": "memory",
        "remember": "memory",
        "update": "memory",
        "log": "memory",
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
    memory_keyword_patterns = (
        "remember that",
        "note that",
        "record that",
        "log that",
        "update memory",
        "campaign update",
        "session update",
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
        elif resolved_mode == "memory":
            response = await self._memory_response(db, snapshot, query)
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
        if any(pattern in lowered for pattern in self.memory_keyword_patterns):
            return "memory", message
        if self._looks_like_campaign_update(lowered):
            return "memory", message
        if self._looks_like_rules_query(lowered):
            return "rules", message
        return "continuity", message

    def _slash_command(self, message: str) -> tuple[LiveAssistantMode | None, str]:
        normalized = message.strip()
        if not normalized.startswith("/"):
            return None, normalized
        match = re.match(r"^/(\S+)(?:\s+([\s\S]*))?$", normalized)
        if not match:
            return None, normalized
        command = match.group(1)
        remainder = match.group(2) or ""
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

    def _looks_like_campaign_update(self, message: str) -> bool:
        actor_pattern = r"\b(players|pcs|party|they|characters)\b"
        event_pattern = (
            r"\b(cleared|entered|left|killed|defeated|fled|retreated|rested|"
            r"found|took|opened|triggered|spoke|promised|learned|discovered)\b"
        )
        room_pattern = r"\b[a-d]\d{1,2}\b"
        return bool(
            re.search(actor_pattern, message)
            and (re.search(event_pattern, message) or re.search(room_pattern, message))
        )

    def _looks_like_location_lookup(self, message: str) -> bool:
        return bool(
            re.search(
                r"\b(where|located|location|find|hidden|stored)\b",
                message,
                flags=re.IGNORECASE,
            )
        )

    def _private_search_matches(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        terms = self._search_terms(query)
        if not terms:
            return []
        path = private_index_service.indexes_root() / "campaign-search.jsonl"
        if not path.exists():
            return []

        try:
            rows = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

        scored: list[tuple[int, dict[str, Any]]] = []
        for line in rows:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            text = str(item.get("text") or item.get("content") or "")
            searchable = self._normalized_search_text(f"{title} {text}")
            score = self._private_match_score(terms, searchable, title)
            dependency_payload = self._dependency_payload(item)
            dependency_kind = str(dependency_payload.get("kind") or "")
            if score <= 0:
                continue
            if dependency_kind in {"item", "quest_item"}:
                score += 8
            if dependency_payload.get("sources"):
                score += 2
            scored.append(
                (
                    score,
                    {
                        "id": item.get("id"),
                        "kind": item.get("kind"),
                        "title": title,
                        "source_path": item.get("source_path"),
                        "metadata": item.get("metadata") or {},
                        "dependency_kind": dependency_kind or None,
                        "sources": dependency_payload.get("sources") or [],
                        "snippet": self._private_match_snippet(
                            text,
                            terms,
                            dependency_payload=dependency_payload,
                        ),
                        "score": score,
                    },
                )
            )
        scored.sort(
            key=lambda pair: (
                -pair[0],
                str(pair[1].get("kind") or ""),
                str(pair[1].get("title") or ""),
            )
        )
        return [item for _score, item in scored[:limit]]

    def _search_terms(self, query: str) -> list[str]:
        stopwords = {
            "and",
            "are",
            "can",
            "find",
            "for",
            "from",
            "how",
            "is",
            "located",
            "location",
            "of",
            "the",
            "there",
            "to",
            "what",
            "where",
            "who",
        }
        terms = []
        for token in re.findall(r"[a-z0-9]+", query.casefold()):
            if token in stopwords or len(token) < 3:
                continue
            terms.append(token[:-1] if token.endswith("s") and len(token) > 4 else token)
        return sorted(set(terms), key=terms.index)

    def _normalized_search_text(self, value: str) -> str:
        tokens = []
        for token in re.findall(r"[a-z0-9]+", value.casefold()):
            tokens.append(token)
            if token.endswith("s") and len(token) > 4:
                tokens.append(token[:-1])
        return " ".join(tokens)

    def _private_match_score(
        self,
        terms: list[str],
        searchable: str,
        title: str,
    ) -> int:
        score = 0
        title_search = self._normalized_search_text(title)
        for term in terms:
            if re.search(rf"\b{re.escape(term)}\b", searchable):
                score += 2
            if re.search(rf"\b{re.escape(term)}\b", title_search):
                score += 3
        if all(re.search(rf"\b{re.escape(term)}\b", searchable) for term in terms):
            score += 6
        return score

    def _snippet_for_terms(
        self,
        text: str,
        terms: list[str],
        *,
        max_chars: int = 240,
    ) -> str:
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            return ""
        normalized = self._normalized_search_text(cleaned)
        positions = [normalized.find(term) for term in terms if normalized.find(term) >= 0]
        start = max(0, min(positions) - 80) if positions else 0
        snippet = cleaned[start : start + max_chars].strip()
        if start > 0:
            snippet = "..." + snippet
        if start + max_chars < len(cleaned):
            snippet += "..."
        return snippet

    def _private_match_snippet(
        self,
        text: str,
        terms: list[str],
        *,
        dependency_payload: dict[str, Any],
    ) -> str:
        if dependency_payload:
            name = str(dependency_payload.get("name") or "").strip()
            kind = str(dependency_payload.get("kind") or "").strip()
            source_labels = []
            for source in dependency_payload.get("sources") or []:
                if not isinstance(source, dict):
                    continue
                if source.get("entity_type") == "room" and source.get("entity_id"):
                    source_labels.append(
                        f"{source.get('entity_id')}"
                        + (
                            f" ({source.get('map_id')})"
                            if source.get("map_id")
                            else ""
                        )
                    )
            parts = [name]
            if kind:
                parts.append(f"type: {kind}")
            if source_labels:
                parts.append("source room: " + ", ".join(source_labels))
            return "; ".join(part for part in parts if part)
        return self._snippet_for_terms(text, terms)

    def _private_match_label(self, item: dict[str, Any]) -> str:
        metadata = item.get("metadata") or {}
        room_id = metadata.get("room_id")
        title = str(item.get("title") or item.get("id") or "Private match")
        if room_id:
            suffix = title.replace(str(room_id), "", 1).strip()
            return f"{room_id} {suffix}".strip()
        for source in item.get("sources") or []:
            if not isinstance(source, dict):
                continue
            if source.get("entity_type") == "room" and source.get("entity_id"):
                room_title = self._source_room_title(source)
                if room_title:
                    return room_title
                return f"{source.get('entity_id')} {title}".strip()
        return title

    def _dependency_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        if item.get("kind") != "dependency":
            return {}
        text = item.get("text") or item.get("content") or ""
        try:
            payload = json.loads(str(text))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _source_room_title(self, source: dict[str, Any]) -> str | None:
        room_id = str(source.get("entity_id") or "").strip()
        map_id = str(source.get("map_id") or "").strip()
        if not room_id:
            return None
        path = private_index_service.indexes_root() / "campaign-search.jsonl"
        if not path.exists():
            return None
        try:
            rows = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        expected_id = f"room:{map_id}:{room_id}".casefold() if map_id else ""
        for line in rows:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            metadata = item.get("metadata") if isinstance(item, dict) else {}
            if not isinstance(metadata, dict):
                continue
            if expected_id and str(item.get("id") or "").casefold() != expected_id:
                continue
            if str(metadata.get("room_id") or "").casefold() != room_id.casefold():
                continue
            title = str(item.get("title") or "").strip()
            return title or room_id
        return room_id

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
        private_matches = self._private_search_matches(
            normalized_query,
            limit=3 if frugal_mode else 5,
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

        if (
            primary_payload is None
            and not session_matches["items"]
            and not private_matches
        ):
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

        if private_matches:
            if self._looks_like_location_lookup(normalized_query):
                lines.append(f"Likely location: {self._private_match_label(private_matches[0])}.")
            lines.append("Private campaign matches:")
            for item in private_matches[:3]:
                lines.append(
                    f"- {self._private_match_label(item)}: {item.get('snippet') or ''}"
                )

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": [
                *search_items,
                *[
                    {
                        "name": self._private_match_label(item),
                        "entity_type": item.get("kind") or "private",
                    }
                    for item in private_matches
                ],
            ],
            "recent_sessions": session_matches["items"],
            "prep": None,
            "private_matches": private_matches,
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

    async def _memory_response(
        self,
        db: AsyncSession,
        snapshot: dict[str, Any],
        query: str,
    ) -> dict[str, Any]:
        normalized_query = self._normalize_message(query)
        if normalized_query is None:
            raise ValueError(
                "Memory mode needs a table update, for example '/memory PCs cleared C7 and left ghoul bodies.'"
            )

        state = snapshot.get("state") or {}
        existing_notes = self._normalize_optional_multiline(state.get("notes")) or ""
        entry = self._format_memory_entry(normalized_query)
        updated_notes = "\n\n".join(part for part in [existing_notes, entry] if part)
        updated_snapshot = await live_session_service.save_state(
            db,
            scene_title=state.get("scene_title"),
            focus=state.get("focus"),
            current_location_id=state.get("current_location_id"),
            active_pc_ids=state.get("active_pc_ids") or [],
            active_npc_ids=state.get("active_npc_ids") or [],
            maptool_map_id=state.get("maptool_map_id"),
            notes=updated_notes,
            frugal_mode=bool(state.get("frugal_mode")),
            combat_state=state.get("combat_state"),
        )

        extracted = self._memory_extracts(normalized_query)
        lines = [
            "Saved to live campaign memory.",
            f"Update: {normalized_query}",
        ]
        if extracted:
            lines.append("Detected: " + "; ".join(extracted))
        lines.append(
            "This is now part of the live scene notes used by /scene, /prep, and contextual answers."
        )

        return {
            "answer": "\n".join(lines),
            "citations": [],
            "entities": [],
            "recent_sessions": updated_snapshot.get("recent_sessions") or [],
            "prep": updated_snapshot.get("latest_prep"),
            "memory": {
                "entry": entry,
                "detected": extracted,
                "notes": updated_notes,
            },
            "scene_context": self._scene_context(updated_snapshot),
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
        normalized = str(message).replace("\r\n", "\n").replace("\r", "\n")
        lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in normalized.split("\n")
        ]
        cleaned = "\n".join(lines).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned or None

    def _normalize_optional_multiline(self, value: Any) -> str | None:
        if value is None:
            return None
        return self._normalize_message(str(value))

    def _format_memory_entry(self, text: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"[{timestamp}] {text}"

    def _memory_extracts(self, text: str) -> list[str]:
        extracts: list[str] = []
        rooms = sorted(
            set(re.findall(r"\b[A-D]\d{1,2}\b", text, flags=re.IGNORECASE)),
            key=lambda item: (item[0].upper(), int(item[1:])),
        )
        if rooms:
            extracts.append("rooms " + ", ".join(room.upper() for room in rooms))
        if re.search(r"\bcleared|defeated|killed\b", text, flags=re.IGNORECASE):
            extracts.append("cleared/defeated state")
        if re.search(r"\bbod(?:y|ies|ys)\b|corpse|corpses", text, flags=re.IGNORECASE):
            extracts.append("bodies/corpses left behind")
        if re.search(r"\bretreat|recuperate|rest|town|otari\b", text, flags=re.IGNORECASE):
            extracts.append("party rest/retreat context")
        return extracts

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
