from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import json
import re
import ssl
from typing import Any, Optional
from urllib.request import Request, urlopen

import certifi


@dataclass(frozen=True)
class AonCreatureIndexItem:
    creature_id: int
    name: str
    level: int
    source: str
    traits: list[str]
    remastered: bool = False
    legacy: bool = False
    note: str = ""

    @property
    def url(self) -> str:
        return f"https://2e.aonprd.com/Monsters.aspx?ID={self.creature_id}&NoRedirect=1"


@dataclass(frozen=True)
class AonCreatureDocument:
    creature_id: int
    name: str
    level: int
    source_url: str
    source: str
    traits: list[str]
    content: str
    remastered: bool
    legacy: bool
    ac: str
    hp: str
    fort: str
    ref: str
    will: str
    speed: str
    perception: str
    senses: str
    languages: str
    skills: list[str]
    ability_mods: dict[str, str]
    immunities: str
    weaknesses: str
    resistances: str
    attacks: list[str]
    actions: list[str]
    spells: list[str]
    image_url: str
    fetched_at: str


class AonCreatureService:
    base_url = "https://2e.aonprd.com"
    source_name = "Archives of Nethys PF2e Creatures"
    user_agent = "DMA AoN PF2e Creature Fetcher/1.0"

    # A curated PF2e starter list for the Abomination Vaults early levels and
    # common low-level additions. Remastered IDs are preferred where AoN has them.
    creature_index = [
        AonCreatureIndexItem(3031, "Mitflit", -1, "Monster Core", ["Fey", "Gremlin"], True),
        AonCreatureIndexItem(672, "Giant Maggot", 0, "Bestiary 2", ["Animal"], False, True),
        AonCreatureIndexItem(673, "Giant Fly", 1, "Bestiary 2", ["Animal"], False, True),
        AonCreatureIndexItem(575, "Brownie", 1, "Bestiary 2", ["Fey"], False, True),
        AonCreatureIndexItem(809, "Giant Solifugid", 1, "Bestiary 2", ["Animal"], False, True),
        AonCreatureIndexItem(378, "Slurk", 2, "Monster Core", ["Animal"], True),
        AonCreatureIndexItem(383, "Soulbound Doll", 2, "Monster Core", ["Construct", "Soulbound"], True),
        AonCreatureIndexItem(1035, "Corpselight", 2, "Ruins of Gauntlight", ["Undead"], False, True),
        AonCreatureIndexItem(1036, "Flickerwisp", 2, "Ruins of Gauntlight", ["Aberration", "Air"], False, True),
        AonCreatureIndexItem(3175, "Giant Scorpion", 3, "Monster Core", ["Animal"], True),
        AonCreatureIndexItem(845, "Vampiric Mist", 3, "Bestiary 2", ["Aberration"], False, True),
        AonCreatureIndexItem(218, "Ghoul", 1, "Bestiary", ["Ghoul", "Undead"], False, True),
        AonCreatureIndexItem(4391, "Mist Stalker", 4, "Monster Core 2", ["Aberration", "Air"], True),
        AonCreatureIndexItem(110, "Barbazu", 5, "Bestiary", ["Devil", "Fiend"], False, True),
        AonCreatureIndexItem(227, "Gibbering Mouther", 5, "Bestiary", ["Aberration"], False, True),
        AonCreatureIndexItem(726, "Lurker In Light", 5, "Bestiary 2", ["Fey"], False, True),
        AonCreatureIndexItem(684, "Wood Golem", 6, "Bestiary 2", ["Construct", "Golem"], False, True),
        AonCreatureIndexItem(853, "Violet Fungus", 3, "Bestiary 2", ["Fungus"], False, True),
    ]

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = (
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.cache_root = (
            self.project_root / "assets" / "imports" / "misc" / "aon-creatures" / "raw"
        )

    def search_creatures(self, query: str = "", limit: int = 30) -> list[dict[str, Any]]:
        terms = [term for term in re.split(r"\s+", query.lower().strip()) if term]
        matches = []
        for item in self.creature_index:
            haystack = " ".join(
                [item.name, item.source, *item.traits, "remastered" if item.remastered else ""]
            ).lower()
            if terms and not all(term in haystack for term in terms):
                continue
            matches.append(
                {
                    **asdict(item),
                    "source_url": item.url,
                    "ruleset": "pf2e",
                }
            )
        matches.sort(key=lambda item: (item["level"], item["name"]))
        return matches[: max(1, min(limit, 100))]

    def get_creature(
        self,
        creature_id: int,
        *,
        timeout_seconds: float = 20.0,
        refresh: bool = False,
        fallback_name: str | None = None,
        fallback_level: int | None = None,
        fallback_source: str | None = None,
        fallback_traits: list[str] | None = None,
    ) -> AonCreatureDocument:
        try:
            item = self._index_item(creature_id)
        except ValueError:
            if not fallback_name:
                raise
            item = AonCreatureIndexItem(
                creature_id,
                fallback_name,
                fallback_level if fallback_level is not None else 0,
                fallback_source or "Archives of Nethys",
                fallback_traits or [],
            )
        cache_path = self._cache_path(item)
        if cache_path.exists() and not refresh:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if "image_url" in payload:
                self._backfill_document_payload(payload)
                return AonCreatureDocument(**payload)

        try:
            html_text = self._fetch_text(item.url, timeout_seconds=timeout_seconds)
        except Exception:
            if cache_path.exists() and not refresh:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                self._backfill_document_payload(payload)
                return AonCreatureDocument(**payload)
            raise
        document = self.parse_creature_page(html_text, item)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(asdict(document), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return document

    def parse_creature_page(
        self,
        html_text: str,
        item: AonCreatureIndexItem,
    ) -> AonCreatureDocument:
        text = self._html_to_text(self._extract_main_fragment(html_text))
        content = self._extract_creature_content(text, item.name)
        source = self._stat_value(content, "Source") or item.source
        legacy = item.legacy or "Legacy Content" in content
        remastered = item.remastered or self._is_remastered_source(source)
        level = self._extract_level(content, item.name, item.level)
        traits = self._extract_traits(content, item.traits)

        return AonCreatureDocument(
            creature_id=item.creature_id,
            name=item.name,
            level=level,
            source_url=item.url,
            source=source,
            traits=traits,
            content=content,
            remastered=remastered,
            legacy=legacy and not remastered,
            ac=self._stat_value(content, "AC"),
            hp=self._stat_value(content, "HP"),
            fort=self._stat_value(content, "Fort"),
            ref=self._stat_value(content, "Ref"),
            will=self._stat_value(content, "Will"),
            speed=self._stat_value(content, "Speed"),
            perception=self._stat_value(content, "Perception"),
            senses=self._senses(content),
            languages=self._stat_value(content, "Languages"),
            skills=self._skills(content),
            ability_mods=self._ability_mods(content),
            immunities=self._stat_value(content, "Immunities"),
            weaknesses=self._stat_value(content, "Weaknesses"),
            resistances=self._stat_value(content, "Resistances"),
            attacks=self._attack_lines(content),
            actions=self._action_lines(content),
            spells=self._spell_lines(content),
            image_url=self._image_url(html_text),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def _index_item(self, creature_id: int) -> AonCreatureIndexItem:
        for item in self.creature_index:
            if item.creature_id == creature_id:
                return item
        raise ValueError(f"Unknown PF2e AoN creature id: {creature_id}")

    def _cache_path(self, item: AonCreatureIndexItem) -> Path:
        slug = re.sub(r"[^a-z0-9]+", "-", item.name.lower()).strip("-")
        return self.cache_root / f"{item.creature_id}-{slug}.json"

    def _backfill_document_payload(self, payload: dict[str, Any]) -> None:
        content = str(payload.get("content") or "")
        payload.setdefault("image_url", "")
        payload.setdefault("senses", "")
        payload.setdefault("languages", "")
        payload.setdefault("skills", [])
        payload.setdefault("ability_mods", {})
        payload.setdefault("immunities", "")
        payload.setdefault("weaknesses", "")
        payload.setdefault("resistances", "")
        payload["attacks"] = self._normalize_attack_lines(payload.get("attacks") or [])
        if not payload.get("actions") and content:
            payload["actions"] = self._action_lines(content)
        else:
            payload.setdefault("actions", [])
        if not payload.get("spells") and content:
            payload["spells"] = self._spell_lines(content)
        else:
            payload.setdefault("spells", [])

    def _fetch_text(self, url: str, *, timeout_seconds: float) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=timeout_seconds, context=context) as response:
            return response.read().decode("utf-8", errors="replace")

    def _extract_main_fragment(self, html_text: str) -> str:
        start = html_text.find('<div class="main" id="main">')
        if start < 0:
            return html_text
        fragment = html_text[start:]
        end = fragment.find('<div class="clear">')
        return fragment if end < 0 else fragment[:end]

    def _image_url(self, html_text: str) -> str:
        candidates = re.findall(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            html_text,
            flags=re.IGNORECASE,
        )
        for candidate in candidates:
            normalized_candidate = candidate.replace("\\", "/")
            if (
                "Images/Monsters/" in normalized_candidate
                or "Images/Creatures/" in normalized_candidate
            ):
                return (
                    normalized_candidate
                    if normalized_candidate.startswith(("http://", "https://"))
                    else f"{self.base_url}/{normalized_candidate.lstrip('/')}"
                )
        return ""

    def _html_to_text(self, html_text: str) -> str:
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html_text)
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</?(p|div|section|article|table|tr|h[1-6]|li|ul|ol)[^>]*>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text).replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = self._separate_inline_stat_labels(text)
        return text.strip()

    def _separate_inline_stat_labels(self, text: str) -> str:
        labels = (
            "Source|Perception|Languages|Skills|Str|Items|AC|HP|Immunities|"
            "Weaknesses|Resistances|Speed|Melee|Ranged|Damage|Effect|Saving Throw|"
            "Critical Success|Success|Failure|Critical Failure|Frequency|Requirement|"
            "Requirements|Trigger|Prerequisites|Effect"
        )
        text = re.sub(rf" (?=({labels})\b)", "\n", text)
        text = re.sub(r"(?<=[a-z0-9).])(?=(Melee|Ranged|Occult|Primal|Arcane|Divine) \[)", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text)

    def _extract_creature_content(self, text: str, name: str) -> str:
        pattern = re.compile(
            rf"{re.escape(name)}\s*Creature\s*-?\d+[\s\S]*?(?=\nAll Monsters in|\nSite Owner:|$)",
            flags=re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
        return text.strip()

    def _extract_level(self, content: str, name: str, fallback: int) -> int:
        match = re.search(rf"{re.escape(name)}\s*Creature\s*(-?\d+)", content, re.IGNORECASE)
        if not match:
            return fallback
        try:
            return int(match.group(1))
        except ValueError:
            return fallback

    def _extract_traits(self, content: str, fallback: list[str]) -> list[str]:
        source_match = re.search(r"\nSource\b", content)
        before_source = content[: source_match.start()] if source_match else content[:300]
        lines = [line.strip() for line in before_source.splitlines() if line.strip()]
        if len(lines) < 2:
            return fallback
        candidates = re.split(r"\s{2,}| ", lines[-1])
        traits = [
            trait
            for trait in candidates
            if trait and trait not in {"Legacy", "Content", "N", "NE", "CE", "LE", "CN", "LN", "NG", "LG", "CG", "Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"}
        ]
        return traits or fallback

    def _stat_value(self, content: str, label: str) -> str:
        if label in {"Fort", "Ref", "Will"}:
            match = re.search(
                rf"\b{re.escape(label)}\s+([+-]\d+(?:\s*\([^)]+\))?)",
                content,
                re.IGNORECASE,
            )
            return match.group(1).strip() if match else ""
        match = re.search(rf"\b{re.escape(label)}\s+([^;\n]+)", content, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _attack_lines(self, content: str) -> list[str]:
        return self._normalize_attack_lines(content.splitlines())

    def _normalize_attack_lines(self, lines: list[Any]) -> list[str]:
        attacks: list[str] = []
        for line in (str(line).strip() for line in lines):
            if re.match(r"^(Melee|Ranged)", line, re.IGNORECASE):
                attacks.append(line)
                continue
            if re.match(r"^Damage\b", line, re.IGNORECASE):
                if attacks:
                    attacks[-1] = f"{attacks[-1]} {self._clean_attack_damage_continuation(line)}"
        return attacks[:8]

    def _clean_attack_damage_continuation(self, line: str) -> str:
        text = str(line or "").strip()
        match = re.search(
            r"\s+(Consume Flesh|Swift Leap)\b",
            text,
        )
        if match and match.start() > 0:
            return text[: match.start()].strip()
        return text

    def _action_lines(self, content: str) -> list[str]:
        action_re = re.compile(
            r"^(Reactive|Free|Frequency|Trigger|Requirements?|"
            r"Effect|Grab|Constrict|Rend|Pounce|Baffling|Vengeful|Consume|Flicker|"
            r"Claim|Death|Blood|Breath|Poison|Paralysis|Ghoul Fever|Sneak Attack|"
            r"Attack of Opportunity|Reactive Strike)",
            re.IGNORECASE,
        )
        actions = [
            line.strip()
            for line in content.splitlines()
            if action_re.match(line.strip())
        ]
        compact = re.sub(r"\s+", " ", content).strip()
        self._append_named_action_block(
            actions,
            compact,
            "Consume Flesh",
            ["Ghoul Fever", "Paralysis", "Swift Leap"],
            fallback_start="Requirements",
        )
        self._append_named_action_block(
            actions,
            compact,
            "Ghoul Fever",
            ["Paralysis", "Swift Leap"],
        )
        self._append_named_action_block(
            actions,
            compact,
            "Paralysis",
            ["Swift Leap"],
        )
        self._append_named_action_block(actions, compact, "Swift Leap", [])
        deduped: list[str] = []
        seen: set[str] = set()
        for action in actions:
            key = re.sub(r"\s+", " ", action).strip().casefold()
            if not key or key in seen:
                continue
            if (
                key.startswith(("requirements ", "effect "))
                and any(item.casefold().startswith("consume flesh") for item in actions)
            ):
                continue
            deduped.append(action)
            seen.add(key)
        return deduped[:12]

    def _append_named_action_block(
        self,
        actions: list[str],
        content: str,
        name: str,
        stop_names: list[str],
        *,
        fallback_start: str | None = None,
    ) -> None:
        start = re.search(rf"\b{re.escape(name)}\b", content)
        prefix = name
        if not start and fallback_start:
            start = re.search(rf"\b{re.escape(fallback_start)}\b", content)
            prefix = name
        if not start:
            return
        stop_positions = [
            match.start()
            for stop_name in stop_names
            for match in [re.search(rf"\b{re.escape(stop_name)}\b", content[start.end() :])]
            if match
        ]
        end = start.end() + min(stop_positions) if stop_positions else min(len(content), start.start() + 700)
        block = content[start.start() : end].strip(" ;")
        if prefix != name or not block.casefold().startswith(name.casefold()):
            block = f"{prefix} {block}"
        actions.append(block)

    def _spell_lines(self, content: str) -> list[str]:
        spell_re = re.compile(
            r"^(Occult|Primal|Arcane|Divine|Spells?|Cantrips?|Constant|Focus|Rituals?)\b",
            re.IGNORECASE,
        )
        return [
            line.strip()
            for line in content.splitlines()
            if spell_re.match(line.strip())
        ][:12]

    def _skills(self, content: str) -> list[str]:
        skills = self._stat_value(content, "Skills")
        if not skills:
            return []
        return [part.strip() for part in re.split(r",\s*", skills) if part.strip()]

    def _ability_mods(self, content: str) -> dict[str, str]:
        match = re.search(
            r"\bStr\s+([+-]\d+).*?\bDex\s+([+-]\d+).*?\bCon\s+([+-]\d+).*?"
            r"\bInt\s+([+-]\d+).*?\bWis\s+([+-]\d+).*?\bCha\s+([+-]\d+)",
            content,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return {}
        keys = ("str", "dex", "con", "int", "wis", "cha")
        return {key: match.group(index + 1) for index, key in enumerate(keys)}

    def _senses(self, content: str) -> str:
        perception = self._stat_value(content, "Perception")
        if not perception:
            return ""
        parts = [part.strip() for part in perception.split(",")[1:] if part.strip()]
        return ", ".join(parts)

    def _is_remastered_source(self, source: str) -> bool:
        return any(name in source for name in ("Monster Core", "Player Core", "GM Core", "NPC Core"))


aon_creature_service = AonCreatureService()
