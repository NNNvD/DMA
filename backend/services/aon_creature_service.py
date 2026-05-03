from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import json
import re
from typing import Any, Optional
from urllib.request import Request, urlopen


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
    attacks: list[str]
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
    ) -> AonCreatureDocument:
        item = self._index_item(creature_id)
        cache_path = self._cache_path(item)
        if cache_path.exists() and not refresh:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return AonCreatureDocument(**payload)

        html_text = self._fetch_text(item.url, timeout_seconds=timeout_seconds)
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
            attacks=self._attack_lines(content),
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

    def _fetch_text(self, url: str, *, timeout_seconds: float) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")

    def _extract_main_fragment(self, html_text: str) -> str:
        start = html_text.find('<div class="main" id="main">')
        if start < 0:
            return html_text
        fragment = html_text[start:]
        end = fragment.find('<div class="clear">')
        return fragment if end < 0 else fragment[:end]

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
        return [
            line.strip()
            for line in content.splitlines()
            if re.match(r"^(Melee|Ranged|Damage|Occult|Primal|Arcane|Divine|Reactive|Grab|Constrict|Rend|Pounce|Baffling|Vengeful|Consume|Flicker|Claim|Death|Blood)", line.strip(), re.IGNORECASE)
        ][:8]

    def _is_remastered_source(self, source: str) -> bool:
        return any(name in source for name in ("Monster Core", "Player Core", "GM Core", "NPC Core"))


aon_creature_service = AonCreatureService()
