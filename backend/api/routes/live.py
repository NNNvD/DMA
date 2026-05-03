from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import settings
from backend.models.base import get_db
from backend.services.campaign_service import campaign_service
from backend.services.aon_creature_service import aon_creature_service
from backend.services.live_assistant_service import live_assistant_service
from backend.services.live_maptool_service import live_maptool_service
from backend.services.live_session_service import live_session_service
from backend.services.metrics_service import metrics_service


router = APIRouter()
page_router = APIRouter(include_in_schema=False)


class LiveSessionStateUpdate(BaseModel):
    scene_title: Optional[str] = None
    focus: Optional[str] = None
    current_location_id: Optional[int] = None
    active_pc_ids: list[int] = Field(default_factory=list)
    active_npc_ids: list[int] = Field(default_factory=list)
    maptool_map_id: Optional[str] = None
    notes: Optional[str] = None
    frugal_mode: bool = False


class LiveAssistantRequest(BaseModel):
    message: str
    mode: Literal["auto", "scene", "rules", "continuity", "recap", "npc", "prep"] = (
        "auto"
    )


class LiveMapToolSyncRequest(BaseModel):
    map_id: Optional[str] = None
    retries: Optional[int] = Field(default=None, ge=1)
    remember_map_id: bool = True


class LiveVaultSyncRequest(BaseModel):
    vault_path: Optional[str] = None


class LiveNPCDossierUpdate(BaseModel):
    appearance_description: Optional[str] = None
    gm_summary: Optional[str] = None
    pc_encountered: Optional[bool] = None
    pc_relationship_status: Optional[str] = None
    status: Optional[str] = None
    status_detail: Optional[str] = None
    campaign_encounters: list[str] = Field(default_factory=list)
    vault_dm_notes: Optional[str] = None
    vault_player_summary: Optional[str] = None


class LiveCommandCenterNoteUpdate(BaseModel):
    content: str


class LivePlayerHandoutExportRequest(BaseModel):
    path: str = Field(min_length=1)
    basename: Optional[str] = None
    html_only: bool = False


class AonCreatureSearchResponse(BaseModel):
    items: list[dict]


class AonCreatureResponse(BaseModel):
    creature: dict


CAMPAIGN_OVERVIEW_PATH = "Command Center/Campaign Overview.md"
SESSION_OVERVIEW_DIR = "Command Center/Sessions"
HANDOUT_EXPORT_DIR = "Exports/Handouts"

DEFAULT_CAMPAIGN_OVERVIEW = """# Campaign Overview

## Campaign Premise

The heroes are drawn from Otari toward the ruined Gauntlight Keep after strange lights and old dangers begin stirring in the Fogfen. The campaign is about uncovering why Gauntlight still matters, how Belcorra Haruvex's legacy threatens Otari, and what must be done before the dungeon's deeper powers reach the town.

## Backstory / Hidden Truth

Belcorra Haruvex once used Gauntlight as the center of a revenge-driven occult project against Otari and its founders. The Roseguard defeated her, but the site and the vaults beneath it still preserve enough of her work, allies, servants, and hatred to become dangerous again.

## Current Campaign State

The party is preparing to investigate Gauntlight Keep and the upper levels of the Abomination Vaults. Otari is the home base, Wrin Sivinxi is the most important early patron, and the dungeon itself is the main source of discovery, danger, and escalating revelations.

## Major Threats

- Belcorra Haruvex and the lingering purpose of Gauntlight.
- The monsters, factions, haunts, and hazards inhabiting each dungeon level.
- The possibility that threats below Gauntlight can reach or manipulate Otari.

## Future Trajectory

The campaign should move from local investigation to dungeon exploration, then from dungeon exploration to understanding the larger occult machinery beneath Gauntlight. The party should gradually learn that individual rooms and monsters are part of a larger campaign-scale danger.

## Open Threads

- What exactly is Gauntlight doing now?
- What does Wrin know, suspect, or fear?
- Which dungeon inhabitants are isolated threats, and which belong to wider factions?
- What clues point from the upper vaults to the middle and deeper levels?

## DM Notes

Add table-specific notes here.
"""

DEFAULT_NEXT_SESSION_OVERVIEW = """# Next Session

## Session Goal

Start with the party arriving at Gauntlight Keep and establish the ruin as dangerous, strange, and worth investigating.

## Starting Situation

The PCs have reached the ruined keep in the Fogfen. They know enough to suspect Gauntlight is connected to recent strange events, but they do not yet understand the scale of the threat beneath it.

## Likely Scenes / Rooms

- Approach and first look at Gauntlight Keep.
- Initial scouting around the ruin.
- First entry into the upper dungeon level.
- Early encounters, hazards, and clues that teach the party how this campaign will feel.

## Important NPCs

- Wrin Sivinxi: early patron and occult-minded contact in Otari.
- Belcorra Haruvex: hidden campaign antagonist whose history should emerge gradually.

## Monsters / Hazards / Treasure

Use the Map Room and Level 1 room key while running exploration. Update this section after choosing the most likely first rooms.

## Secrets / Reveals

- Gauntlight is not just an abandoned ruin.
- The dungeon contains traces of older conflicts and current danger.
- Otari may become threatened if the party ignores what they find.

## If The PCs Do Something Unexpected

Keep the situation grounded in place: the Fogfen, the ruined keep, signs of danger, retreat routes to Otari, and clues that point back toward investigation rather than forcing a single route.

## Session Notes

Add live DM notes here.

## After-Session Recap

Fill this in after play.
"""


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _configured_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _project_root() / path
    return path.resolve()


def _safe_child(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Requested path is outside the configured root") from exc
    return target


def _vault_root() -> Path:
    return _configured_path(settings.obsidian_vault_path)


def _ensure_vault_note(relative_path: str, default_content: str) -> Path:
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    try:
        note_path = _safe_child(root, relative_path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    note_path.parent.mkdir(parents=True, exist_ok=True)
    if not note_path.exists():
        note_path.write_text(default_content.rstrip() + "\n", encoding="utf-8")
    return note_path


def _note_payload(root: Path, path: Path) -> dict:
    return {
        "vault_path": str(root),
        "path": path.relative_to(root).as_posix(),
        "title": path.stem,
        "content": path.read_text(encoding="utf-8"),
        "updated_at": path.stat().st_mtime,
    }


def _content_disposition_filename(path: Path) -> str:
    return path.name.replace('"', "")


def _session_note_paths(root: Path) -> list[Path]:
    sessions_root = root / SESSION_OVERVIEW_DIR
    paths = list(sessions_root.glob("*.md")) if sessions_root.exists() else []
    paths.extend((root / "Command Center").glob("Session *.md"))
    unique = {path.resolve(): path for path in paths if path.is_file()}
    return sorted(unique.values(), key=lambda item: item.name.casefold())


def _split_wikilink_target(target: str) -> tuple[str, str | None]:
    note_target, _, heading = target.partition("#")
    return note_target.strip(), heading.strip() or None


def _normalize_link_text(value: str) -> str:
    return value.strip().removesuffix(".md").replace("\\", "/").casefold()


def _resolve_vault_note(root: Path, target: str) -> Path | None:
    note_target, _heading = _split_wikilink_target(target)
    if not note_target:
        return None
    candidates = [
        note_target,
        note_target if note_target.endswith(".md") else f"{note_target}.md",
    ]
    for candidate in candidates:
        try:
            path = _safe_child(root, candidate)
        except ValueError:
            continue
        if path.exists() and path.suffix.lower() == ".md":
            return path

    normalized = _normalize_link_text(note_target)
    title_matches: list[Path] = []
    suffix_matches: list[Path] = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root).as_posix()
        if _normalize_link_text(path.stem) == normalized:
            title_matches.append(path)
        elif _normalize_link_text(relative) == normalized:
            return path
        elif _normalize_link_text(relative).endswith(f"/{normalized}"):
            suffix_matches.append(path)
    matches = title_matches or suffix_matches
    return (
        sorted(matches, key=lambda item: item.relative_to(root).as_posix())[0]
        if matches
        else None
    )


def _pdf_root() -> Path:
    return _configured_path(settings.reference_pdf_root)


def _map_root() -> Path:
    return _configured_path(settings.dungeon_map_root)


def _room_key_root() -> Path:
    return _configured_path(settings.dungeon_room_key_root)


def _vault_root() -> Path:
    return _configured_path(settings.obsidian_vault_path)


def _map_id_from_path(path: Path) -> str:
    return path.stem.strip().casefold().replace(" ", "-")


def _text_matches(query: str, *values: object) -> bool:
    if not query:
        return True
    haystack = " ".join(str(value or "") for value in values).casefold()
    return query in haystack


def _path_stem(value: str | None) -> str | None:
    if not value:
        return None
    return Path(value).stem or value


def _normalize_source_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _literal_source_reference(room: dict) -> str | None:
    candidates = [room.get("source"), *(room.get("source_references") or [])]
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        match = re.search(r"([^,]+?\.pdf)", candidate, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _reference_markdown_for_source(source_pdf: str | None) -> Path | None:
    if not source_pdf:
        return None
    references_root = _vault_root() / "Library" / "References"
    if not references_root.exists():
        return None
    normalized_source = _normalize_source_name(Path(source_pdf).stem)
    for path in sorted(references_root.rglob("*.md")):
        if _normalize_source_name(path.stem) == normalized_source:
            return path
    for path in sorted(references_root.rglob("*.md")):
        normalized_path = _normalize_source_name(path.stem)
        if normalized_source in normalized_path or normalized_path in normalized_source:
            return path
    return None


def _room_heading_pattern(room_id: str, title: str | None = None) -> re.Pattern[str]:
    title_pattern = ""
    if title:
        words = [re.escape(part) for part in re.findall(r"[A-Za-z0-9']+", title)]
        if words:
            title_pattern = r"\s+" + r"[\s\W_]+".join(words[:6])
    return re.compile(
        rf"\b{re.escape(room_id)}\.\s*{title_pattern}",
        flags=re.IGNORECASE,
    )


def _find_room_heading(text: str, room_id: str, title: str | None = None) -> re.Match[str] | None:
    if title:
        match = _room_heading_pattern(room_id, title).search(text)
        if match:
            return match
    return _room_heading_pattern(room_id).search(text)


def _strip_reference_markup(text: str) -> str:
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(
        r"\[\[([^\]]+)\]\]",
        lambda match: match.group(1).split("/")[-1],
        text,
    )
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def _linearize_pdf_columns(text: str) -> str:
    left_lines: list[str] = []
    right_lines: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            left_lines.append("")
            if right_lines and right_lines[-1]:
                right_lines.append("")
            continue
        if re.match(r"^\s{40,}\S", line):
            right_lines.append(line.strip())
            continue
        match = re.search(r"(?<=\S)\s{4,}(?=\S)", line)
        if not match:
            left_lines.append(line)
            continue
        left = line[: match.start()].rstrip()
        right = line[match.end() :].strip()
        if left:
            left_lines.append(left)
        if right:
            right_lines.append(right)
    if not right_lines:
        return text
    return "\n".join(left_lines).rstrip() + "\n\n" + "\n".join(right_lines).strip()


def _linearize_pdf_pages(text: str) -> str:
    pages: list[list[str]] = [[]]
    for line in text.splitlines():
        if re.match(r"^\s*\d+\s*$", line) and pages[-1]:
            pages.append([line])
            continue
        pages[-1].append(line)
    return "\n\n".join(_linearize_pdf_columns("\n".join(page)) for page in pages)


def _drop_room_heading(text: str, room_id: str, title: str | None = None) -> str:
    match = _find_room_heading(text, room_id, title)
    if not match or match.start() > 10:
        return text
    line_end = text.find("\n", match.start())
    if line_end == -1:
        return ""
    return text[line_end + 1 :]


PDF_NAVIGATION_LINES = {
    "ruins",
    "of",
    "gauntlight",
    "chapter 1:",
    "a light in",
    "the fog",
    "chapter 2:",
    "the forgotten",
    "dungeon",
    "chapter 3:",
    "cult of",
    "the canker",
    "chapter 4:",
    "long dream",
    "the dead",
    "otari",
    "gazetteer",
    "adventure",
    "toolbox",
    "mister beak",
}


def _is_pdf_navigation_line(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    return normalized in PDF_NAVIGATION_LINES


def _remove_pdf_navigation_fragments(line: str) -> str:
    parts = [part.strip() for part in re.split(r"\s{4,}", line) if part.strip()]
    if len(parts) < 2:
        return line
    kept = [part for part in parts if not _is_pdf_navigation_line(part)]
    return " ".join(kept)


def _clean_literal_room_text(text: str) -> str:
    text = _strip_reference_markup(text)
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        line = _remove_pdf_navigation_fragments(line)
        stripped = re.sub(r"\s+", " ", line).strip()
        if not stripped:
            if current:
                paragraphs.append(current)
                current = []
            continue
        if stripped.casefold() in {"chapter 1:", "ruins", "gauntlight"}:
            continue
        if _is_pdf_navigation_line(stripped):
            continue
        if re.fullmatch(r"\d{1,4}", stripped):
            continue
        if re.fullmatch(
            r"(?:LOW|MODERATE|SEVERE|EXTREME)\s+\d+(?:\s+Gazetteer)?",
            stripped,
        ):
            continue
        if re.fullmatch(
            r"(?:CREATURE|HAZARD|TRAP)\s+[â€“âˆ’-]?\d+",
            stripped,
        ):
            continue
        current.append(stripped)
    if current:
        paragraphs.append(current)

    cleaned_paragraphs = []
    for paragraph in paragraphs:
        text = " ".join(paragraph)
        text = re.sub(
            r"\b(?:TRIVIAL|LOW|MODERATE|SEVERE|EXTREME)\s+\d+\s+",
            "",
            text,
        )
        text = re.sub(
            r"\b(?:LOW|MODERATE|SEVERE|EXTREME)\s+\d+\b(?:\s+Gazetteer)?",
            "",
            text,
        )
        text = re.sub(r"\bCREATURE\s+[â€“âˆ’-]?\d+\s+(?=defeating\b)", "", text)
        text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        if text:
            cleaned_paragraphs.append(text)
    return "\n\n".join(cleaned_paragraphs)


def _remove_between(text: str, start: str, end: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start)}.*?(?={re.escape(end)})",
        flags=re.DOTALL,
    )
    return pattern.sub("", text)


def _clean_room_bleed(text: str) -> str:
    text = _remove_between(text, "BEYOND GAUNTLIGHT", "Treasure:")
    text = _remove_between(text, "WANDERING MONSTERS", "Most of the doors")
    text = _remove_between(text, "SIDE QUESTS", "Spear Frog Poison")
    text = re.sub(r"\bPathfinder Bestiary 301\s+", "", text)
    text = re.sub(r"\bCREATURE\s+3\s+(?=value\b)", "", text)
    text = re.sub(r"\bHAZARD\s+3\s+(?=A hero Searching\b)", "", text)
    text = text.replace(
        "display rack near Volluk caused",
        "display rack near the southern wall has survived the devastation. Volluk caused",
    )
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _first_gm_marker_index(text: str, starters: tuple[str, ...]) -> int | None:
    indexes = []
    for starter in starters:
        index = text.find(f". {starter}")
        if index > -1:
            indexes.append(index + 1)
    return min(indexes) if indexes else None


def _split_intro_room_text(text: str) -> tuple[str, str]:
    parts = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not parts:
        return "", ""
    gm_starters = (
        "Once ",
        "The opaque ",
        "The room ",
        "This room ",
        "True to appearances,",
        "A successful ",
        "Any hero ",
        "Characters ",
        "Heroes ",
    )
    first = parts[0]
    split_at = _first_gm_marker_index(first, gm_starters)
    if split_at is not None:
        general_parts = [first[split_at:].strip(), *parts[1:]]
        return first[:split_at].strip(), "\n\n".join(
            part for part in general_parts if part
        )
    for starter in gm_starters:
        marker = f". {starter}"
        index = first.find(marker)
        if index > -1:
            split_at = index + 1
            general_parts = [first[split_at:].strip(), *parts[1:]]
            return first[:split_at].strip(), "\n\n".join(
                part for part in general_parts if part
            )
    if len(parts) > 1:
        if not re.search(r"[.!?][\"”')\]]?$", parts[0]):
            parts[0] = f"{parts[0]} {parts.pop(1)}"
            split_at = _first_gm_marker_index(parts[0], gm_starters)
            if split_at is not None:
                general_parts = [parts[0][split_at:].strip(), *parts[1:]]
                return parts[0][:split_at].strip(), "\n\n".join(
                    part for part in general_parts if part
                )
            for starter in gm_starters:
                marker = f". {starter}"
                index = parts[0].find(marker)
                if index > -1:
                    split_at = index + 1
                    general_parts = [parts[0][split_at:].strip(), *parts[1:]]
                    return parts[0][:split_at].strip(), "\n\n".join(
                        part for part in general_parts if part
                    )
        if len(parts) > 1:
            return parts[0], "\n\n".join(parts[1:])

    single = parts[0]
    split_at = _first_gm_marker_index(single, gm_starters)
    if split_at is not None:
        return single[:split_at].strip(), single[split_at:].strip()
    for starter in gm_starters:
        marker = f". {starter}"
        index = single.find(marker)
        if index > -1:
            split_at = index + 1
            return single[:split_at].strip(), single[split_at:].strip()
    return single, ""


ROOM_READ_ALOUD_END_MARKERS = {
    "A3": "The water of this pond",
    "A4": "Many years ago",
    "A5": "This massive frog",
    "A6": "This roomâ€™s ceiling",
    "A10": "The mitflits chose",
    "A12": "A hero Searching this room",
    "A14": "This room serves",
    "A15": "Belcorra made no secret",
    "A17": "The rowboat",
    "A20": "These supplies",
    "A22": "The 5-foot-tall paintings",
    "A23": "Volluk caused",
    "A24": "The pier is just as dangerous",
    "A25": "The locked trap door",
}


def _split_at_sentence_before(text: str, marker: str) -> tuple[str, str] | None:
    index = text.find(marker)
    if index <= 0:
        return None
    split_at = index
    while split_at > 0 and text[split_at - 1].isspace():
        split_at -= 1
    return text[:split_at].strip(), text[split_at:].strip()


def _split_room_intro_by_room(room_id: str | None, text: str) -> tuple[str, str]:
    if room_id == "A9":
        split = _split_at_sentence_before(text, "The skeletal")
        if split:
            return split
    if room_id == "A19":
        read_marker = "This study features"
        read_start = text.find(read_marker)
        if read_start > -1:
            prefix = text[:read_start].strip()
            read_and_rest = text[read_start:].strip()
            general_marker = "Volluk once pursued"
            split = _split_at_sentence_before(read_and_rest, general_marker)
            if split:
                read_aloud, general = split
                return read_aloud, f"{prefix}\n\n{general}".strip()
    if room_id == "A6":
        split = _split_at_sentence_before(text, "This room")
        if split:
            return split
    if room_id == "A8":
        read_marker = "Almost the entire ceiling"
        read_start = text.find(read_marker)
        if read_start > -1:
            prefix = text[:read_start].strip()
            read_and_rest = text[read_start:].strip()
            general_marker = "The ancient battle"
            split = _split_at_sentence_before(read_and_rest, general_marker)
            if split:
                read_aloud, general = split
                return read_aloud, f"{prefix}\n\n{general}".strip()
    if room_id == "A11":
        read_marker = "The smooth walls"
        read_start = text.find(read_marker)
        if read_start > -1:
            prefix = text[:read_start].strip()
            read_and_rest = text[read_start:].strip()
            general_marker = "The Roseguard"
            split = _split_at_sentence_before(read_and_rest, general_marker)
            if split:
                read_aloud, general = split
                return read_aloud, f"{prefix}\n\n{general}".strip()
    marker = ROOM_READ_ALOUD_END_MARKERS.get(room_id or "")
    if marker:
        split = _split_at_sentence_before(text, marker)
        if split:
            return split
    return _split_intro_room_text(text)


ROOM_ENCOUNTER_FALLBACKS = {
    "A3": "SLURK CREATURE 2\nPathfinder Bestiary 301\nInitiative Perception +6",
    "A6": (
        "GIANT FLIES (2) CREATURE 1\n"
        "Pathfinder Bestiary 2 120\n"
        "Initiative Perception +8"
    ),
    "A10": (
        "BITE BITE CREATURE 1\n"
        "Giant solifugid (Pathfinder Bestiary 2 246)\n"
        "Initiative Perception +7\n\n"
        "MITFLITS (2) CREATURE -1\n"
        "Pathfinder Bestiary 192\n"
        "Initiative Perception +4\n\n"
        "BOSS SKRAWNG CREATURE 1\n"
        "Male mitflit gang boss (Pathfinder Bestiary 192)"
    ),
    "A23": (
        "MISTER BEAK CREATURE 3\n"
        "CE elite soulbound doll (Pathfinder Bestiary 6, 304)\n"
        "Initiative Perception +10\n"
        "Speed 20 feet, fly 20 feet"
    ),
    "A24": "FLICKERWISP CREATURE 2\nPage 83\nInitiative Perception +9",
}


def _trim_stat_leak(text: str, marker: str) -> str:
    index = text.find(marker)
    return text[:index].strip() if index > -1 else text


def _apply_room_literal_fixes(
    room_id: str | None,
    literal: dict[str, str],
) -> dict[str, str]:
    if not room_id:
        return literal
    if room_id in ROOM_ENCOUNTER_FALLBACKS and not literal.get("encounter_text"):
        literal["encounter_text"] = ROOM_ENCOUNTER_FALLBACKS[room_id]
    if room_id == "A10" and literal.get("general_text"):
        literal["general_text"] = _trim_stat_leak(literal["general_text"], "BITE BITE")
    if room_id == "A23" and literal.get("general_text"):
        literal["general_text"] = _trim_stat_leak(literal["general_text"], "CE elite")
    if room_id == "A24" and literal.get("general_text"):
        literal["general_text"] = _trim_stat_leak(literal["general_text"], "FLICKERWISP")
    return literal


def _format_encounter_text(text: str) -> str:
    text = re.sub(
        r"\b([A-Z][A-Z'â€™ -]{2,})\n\n([A-Z][A-Z'â€™ -]{2,}\s+CREATURE\b)",
        r"\1 \2",
        text,
    )
    text = re.sub(
        r"\s+\b(Creatures?|Hazards?|Traps?|Haunts?|Treasure|Development|Morale|Tactics|"
        r"Rewards?|Secret Doors?|Side Quest|Environmental Cues):",
        r"\n\n\1:",
        text,
    )
    text = re.sub(
        r"\s+(\b[A-Z][A-Z0-9'’(), -]{2,}\s+CREATURE\s+[–−-]?\d+)",
        r"\n\n\1",
        text,
    )
    text = re.sub(
        r"\s+\b(AC|Fort|Ref|Will|HP|Speed|Melee|Ranged|Damage|Initiative)\b",
        r"\n\1",
        text,
    )
    text = re.sub(r"\bVAMPIRIC\s+MIST\s+CREATURE\b", "VAMPIRIC MIST CREATURE", text)
    return text.strip()


STAT_BLOCK_RE = re.compile(
    r"\b[A-Z][A-Z0-9'’(), -]{2,}\s+"
    r"(?:CREATURE|HAZARD|TRAP)\s+[–−-]?\d+",
)

SECTION_LABEL_RE = re.compile(
    r"\b(Creatures?|Hazards?|Traps?|Haunts?|Treasure|Development|Morale|Tactics|"
    r"Rewards?|Secret Doors?|Side Quest|Environmental Cues):"
)

NON_ROOM_SECTION_RE = re.compile(
    r"^\s*(?:"
    r"CHAPTER\s+\d+\s*:"
    r"|CHAPTER\s+\d+\s+SYNOPSIS\b"
    r"|CHAPTER\s+\d+\s+TREASURE\b"
    r"|LEVEL\s+\d+\s*:"
    r"|ADVENTURE\s+TOOLBOX\b"
    r")",
    flags=re.MULTILINE,
)


def _extract_stat_blocks(text: str) -> tuple[str, str]:
    stat_blocks: list[str] = []
    general_parts: list[str] = []
    cursor = 0
    while True:
        match = STAT_BLOCK_RE.search(text, cursor)
        if not match:
            general_parts.append(text[cursor:])
            break
        general_parts.append(text[cursor : match.start()])
        next_label = SECTION_LABEL_RE.search(text, match.end())
        next_stat = STAT_BLOCK_RE.search(text, match.end())
        end_candidates = [len(text)]
        if next_label:
            end_candidates.append(next_label.start())
        if next_stat:
            end_candidates.append(next_stat.start())
        end = min(end_candidates)
        stat_blocks.append(text[match.start() : end].strip())
        cursor = end
    general = "".join(general_parts).strip()
    general = re.sub(r"[ \t]{2,}", " ", general)
    general = re.sub(r"\n{3,}", "\n\n", general).strip()
    encounter = "\n\n".join(_format_encounter_text(block) for block in stat_blocks if block)
    return general, encounter


def _split_literal_room_text(
    block: str,
    *,
    room_id: str | None = None,
    title: str | None = None,
) -> dict[str, str]:
    if room_id:
        block = _drop_room_heading(block, room_id, title)
    cleaned = _clean_literal_room_text(block)
    cleaned = _clean_room_bleed(cleaned)
    if not cleaned:
        return {}
    marker = re.search(
        r"\b(Creatures?|Hazards?|Traps?|Haunts?|Treasure|Development|Morale|Tactics|"
        r"Rewards?|Secret Doors?|Side Quest|Environmental Cues):"
        r"|\b[A-Z][A-Z0-9'’(), -]{2,}\s+CREATURE\s+[–−-]?\d+",
        cleaned,
    )
    if not marker:
        read_aloud, general = _split_intro_room_text(cleaned)
        literal: dict[str, str] = {}
        if read_aloud:
            literal["read_aloud"] = read_aloud
        if general:
            literal["general_text"] = general
        elif not read_aloud:
            literal["general_text"] = cleaned
        return literal
    player = cleaned[: marker.start()].strip()
    gm = cleaned[marker.start() :].strip()
    literal: dict[str, str] = {}
    if player:
        read_aloud, general = _split_intro_room_text(player)
        if read_aloud:
            literal["read_aloud"] = read_aloud
        if general:
            literal["general_text"] = general
        player = ""
    if player:
        player_parts = [part.strip() for part in player.split("\n\n") if part.strip()]
        if len(player_parts) > 1 and not re.search(r"[.!?][\"”')\]]?$", player_parts[0]):
            player_parts[0] = f"{player_parts[0]} {player_parts.pop(1)}"
        literal["read_aloud"] = player_parts[0]
        if len(player_parts) > 1:
            literal["additional_text"] = "\n\n".join(player_parts[1:])
    if gm:
        literal["room_information"] = gm
        literal["encounter_text"] = _format_encounter_text(literal.pop("room_information"))
    return literal


def _split_literal_room_text(
    block: str,
    *,
    room_id: str | None = None,
    title: str | None = None,
) -> dict[str, str]:
    if room_id:
        block = _drop_room_heading(block, room_id, title)
    cleaned = _clean_literal_room_text(block)
    cleaned = _clean_room_bleed(cleaned)
    if not cleaned:
        return {}

    general_source, encounter = _extract_stat_blocks(cleaned)
    marker = SECTION_LABEL_RE.search(general_source)
    literal: dict[str, str] = {}

    if not marker:
        read_aloud, general = _split_room_intro_by_room(room_id, general_source)
        if read_aloud:
            literal["read_aloud"] = read_aloud
        if general:
            literal["general_text"] = general
        elif not read_aloud and general_source:
            literal["general_text"] = general_source
        if encounter:
            literal["encounter_text"] = encounter
        return _apply_room_literal_fixes(room_id, literal)

    intro = general_source[: marker.start()].strip()
    general_after_intro = general_source[marker.start() :].strip()
    if intro:
        read_aloud, general = _split_room_intro_by_room(room_id, intro)
        if read_aloud:
            literal["read_aloud"] = read_aloud
        if general:
            literal["general_text"] = general
    if general_after_intro:
        literal["general_text"] = (
            f"{literal.get('general_text', '')}\n\n{general_after_intro}".strip()
        )
    if encounter:
        literal["encounter_text"] = encounter
    return _apply_room_literal_fixes(room_id, literal)


def _literal_room_texts_from_reference(payload: dict) -> dict[str, dict[str, str]]:
    rooms = payload.get("rooms")
    if not isinstance(rooms, list) or not rooms:
        return {}
    source_path = None
    for room in rooms:
        if isinstance(room, dict):
            source_path = _reference_markdown_for_source(_literal_source_reference(room))
            if source_path:
                break
    if not source_path:
        return {}
    text = _linearize_pdf_pages(source_path.read_text(encoding="utf-8", errors="ignore"))
    matches: list[tuple[int, dict]] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id") or "").strip()
        if not room_id:
            continue
        match = _find_room_heading(text, room_id, str(room.get("title") or ""))
        if match:
            matches.append((match.start(), room))
    matches.sort(key=lambda item: item[0])
    literal_by_room: dict[str, dict[str, str]] = {}
    for index, (start, room) in enumerate(matches):
        room_id = str(room.get("room_id") or "").strip()
        candidate_ends = [min(len(text), start + 8000)]
        if index + 1 < len(matches):
            candidate_ends.append(matches[index + 1][0])
        next_non_room_section = NON_ROOM_SECTION_RE.search(text, start + 1)
        if next_non_room_section:
            candidate_ends.append(next_non_room_section.start())
        end = min(candidate_ends)
        block = text[start:end]
        literal = _split_literal_room_text(
            block,
            room_id=room_id,
            title=str(room.get("title") or ""),
        )
        if room_id and literal:
            literal_by_room[room_id] = literal
    return literal_by_room


def _enrich_room_key_literal_text(payload: dict) -> dict:
    literal_by_room = _literal_room_texts_from_reference(payload)
    if not literal_by_room:
        return payload
    for room in payload.get("rooms") or []:
        if not isinstance(room, dict) or room.get("literal_text"):
            continue
        room_id = str(room.get("room_id") or "").strip()
        literal = literal_by_room.get(room_id)
        if literal:
            room["literal_text"] = literal
    return payload


def _modifier(score: int | None) -> int | None:
    if score is None:
        return None
    return (score - 10) // 2


def _score(payload: dict, key: str) -> int | None:
    value = (payload.get("attributes") or {}).get(key)
    return value if isinstance(value, int) else None


def _proficiency_label(rank: int | None) -> str:
    return {
        0: "untrained",
        2: "trained",
        4: "expert",
        6: "master",
        8: "legendary",
    }.get(rank, f"rank {rank}" if rank is not None else "not listed")


def _check_total(payload: dict, proficiency_key: str, ability_key: str) -> int | None:
    proficiencies = payload.get("proficiencies") or {}
    rank = proficiencies.get(proficiency_key)
    score = _score(payload, ability_key)
    level = payload.get("level")
    if not all(isinstance(value, int) for value in [rank, score, level]):
        return None
    return int(rank) + int(level) + int(_modifier(score))


def _class_dc(payload: dict) -> int | None:
    proficiencies = payload.get("proficiencies") or {}
    keyability = payload.get("keyability")
    rank = proficiencies.get("classDC")
    score = _score(payload, keyability) if isinstance(keyability, str) else None
    level = payload.get("level")
    if not all(isinstance(value, int) for value in [rank, score, level]):
        return None
    return 10 + int(rank) + int(level) + int(_modifier(score))


def _pc_hit_points(payload: dict) -> int | None:
    vitals = payload.get("vitals") or {}
    level = payload.get("level")
    ancestry_hp = vitals.get("ancestry_hp")
    class_hp = vitals.get("class_hp")
    bonus_hp = vitals.get("bonus_hp") or 0
    bonus_per_level = vitals.get("bonus_hp_per_level") or 0
    if not all(isinstance(value, int) for value in [level, ancestry_hp, class_hp]):
        return None
    return ancestry_hp + (class_hp * level) + bonus_hp + (bonus_per_level * level)


def _skill_ability(skill_key: str) -> str:
    return {
        "acrobatics": "dex",
        "arcana": "int",
        "athletics": "str",
        "crafting": "int",
        "deception": "cha",
        "diplomacy": "cha",
        "intimidation": "cha",
        "medicine": "wis",
        "nature": "wis",
        "occultism": "int",
        "performance": "cha",
        "religion": "wis",
        "society": "int",
        "stealth": "dex",
        "survival": "wis",
        "thievery": "dex",
    }.get(skill_key, "")


def _sheet_payload(entity: dict) -> dict:
    latest = entity.get("latest_sheet_version") or {}
    payload = latest.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def _portrait_ref(details: dict) -> str | None:
    for key in ("portrait", "portrait_url", "image", "imageLink", "image_link"):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pc_sheet_view(entity: dict) -> dict:
    details = entity.get("details") or {}
    payload = _sheet_payload(entity)
    source_name = (entity.get("latest_sheet_version") or {}).get("source_name")
    abilities = payload.get("attributes") or {}
    proficiencies = payload.get("proficiencies") or {}
    skill_keys = [
        "acrobatics",
        "arcana",
        "athletics",
        "crafting",
        "deception",
        "diplomacy",
        "intimidation",
        "medicine",
        "nature",
        "occultism",
        "performance",
        "religion",
        "society",
        "stealth",
        "survival",
        "thievery",
    ]
    skills = []
    for key in skill_keys:
        rank = proficiencies.get(key)
        if not isinstance(rank, int) or rank <= 0:
            continue
        ability_key = _skill_ability(key)
        skills.append(
            {
                "key": key,
                "name": key.title(),
                "ability": ability_key.upper(),
                "rank": rank,
                "proficiency": _proficiency_label(rank),
                "total": _check_total(payload, key, ability_key),
            }
        )

    return {
        "id": entity.get("id"),
        "stable_key": entity.get("stable_key"),
        "player_name": _path_stem(source_name),
        "character_name": entity.get("name"),
        "portrait": _portrait_ref(details),
        "summary": entity.get("summary"),
        "description": entity.get("description"),
        "has_imported_sheet": bool(payload),
        "source_name": source_name,
        "identity": {
            "class_name": payload.get("class_name") or details.get("class_name"),
            "level": payload.get("level") or details.get("level"),
            "xp": payload.get("xp"),
            "ancestry": payload.get("ancestry") or details.get("ancestry"),
            "heritage": payload.get("heritage") or details.get("heritage"),
            "background": payload.get("background") or details.get("background"),
            "alignment": payload.get("alignment") or details.get("alignment"),
            "gender": payload.get("gender"),
            "age": payload.get("age"),
            "deity": payload.get("deity") or details.get("deity"),
            "size": (
                (payload.get("size") or {}).get("name")
                if isinstance(payload.get("size"), dict)
                else details.get("size_name")
            ),
            "keyability": payload.get("keyability") or details.get("keyability"),
            "languages": payload.get("languages") or details.get("languages") or [],
        },
        "combat": {
            "hp": _pc_hit_points(payload),
            "ac": (
                (payload.get("ac") or {}).get("total")
                if isinstance(payload.get("ac"), dict)
                else None
            ),
            "shield_bonus": (
                (payload.get("ac") or {}).get("shield_bonus")
                if isinstance(payload.get("ac"), dict)
                else None
            ),
            "speed": (payload.get("vitals") or {}).get("speed"),
            "initiative": _check_total(payload, "perception", "wis"),
            "perception": _check_total(payload, "perception", "wis"),
            "class_dc": _class_dc(payload),
            "fortitude": _check_total(payload, "fortitude", "con"),
            "reflex": _check_total(payload, "reflex", "dex"),
            "will": _check_total(payload, "will", "wis"),
        },
        "abilities": [
            {
                "key": key,
                "name": key.upper(),
                "score": abilities.get(key),
                "modifier": (
                    _modifier(abilities.get(key))
                    if isinstance(abilities.get(key), int)
                    else None
                ),
            }
            for key in ["str", "dex", "con", "int", "wis", "cha"]
        ],
        "proficiencies": {
            key: {"rank": value, "label": _proficiency_label(value)}
            for key, value in proficiencies.items()
            if isinstance(value, int)
        },
        "skills": skills,
        "lores": payload.get("lores") or [],
        "attacks": payload.get("weapons") or [],
        "armor": payload.get("armor") or [],
        "feats": payload.get("feats") or [],
        "specials": payload.get("specials") or details.get("specials") or [],
        "resistances": payload.get("resistances") or [],
        "items": payload.get("items") or details.get("notable_items") or [],
        "money": payload.get("money") or {},
        "spellcasters": payload.get("spellcasters") or [],
        "focus_points": payload.get("focus_points"),
        "raw_sheet": payload,
    }


def _npc_dossier_view(entity: dict) -> dict:
    details = entity.get("details") or {}
    relationships = entity.get("relationships") or []
    grouped_relationships: dict[str, list[dict]] = {}
    for relationship in relationships:
        grouped_relationships.setdefault(
            relationship.get("relationship_type") or "related",
            [],
        ).append(relationship)
    return {
        "id": entity.get("id"),
        "stable_key": entity.get("stable_key"),
        "name": entity.get("name"),
        "portrait": _portrait_ref(details),
        "summary": entity.get("summary"),
        "description": entity.get("description"),
        "role": details.get("role") or details.get("occupation"),
        "status": details.get("status"),
        "status_detail": details.get("status_detail"),
        "appearance_description": details.get("appearance_description"),
        "gm_summary": details.get("gm_summary"),
        "pc_encountered": bool(details.get("pc_encountered")),
        "pc_relationship_status": details.get("pc_relationship_status"),
        "campaign_encounters": details.get("campaign_encounters") or [],
        "dm_notes": details.get("vault_dm_notes"),
        "current_location": entity.get("current_location"),
        "details": details,
        "tags": entity.get("tags") or [],
        "relationships": relationships,
        "relationship_groups": grouped_relationships,
        "combat": details.get("combat") or details.get("statblock") or {},
        "secrets": details.get("secrets") or [],
        "goals": details.get("goals") or [],
        "clues": details.get("clues") or [],
        "player_facing": details.get("vault_player_summary")
        or details.get("player_facing")
        or details.get("public_summary"),
    }


@router.get("/session-state")
async def get_live_session_state(db: AsyncSession = Depends(get_db)):
    return await live_session_service.load_snapshot(db)


@router.put("/session-state")
async def update_live_session_state(
    payload: LiveSessionStateUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await live_session_service.save_state(
            db,
            scene_title=payload.scene_title,
            focus=payload.focus,
            current_location_id=payload.current_location_id,
            active_pc_ids=payload.active_pc_ids,
            active_npc_ids=payload.active_npc_ids,
            maptool_map_id=payload.maptool_map_id,
            notes=payload.notes,
            frugal_mode=payload.frugal_mode,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc


@router.delete("/session-state")
async def reset_live_session_state(db: AsyncSession = Depends(get_db)):
    return await live_session_service.reset_state(db)


@router.post("/maptool-sync")
async def sync_live_maptool_state(
    payload: LiveMapToolSyncRequest,
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        snapshot = await live_session_service.load_snapshot(db)
        resolved_map_id = payload.map_id or (snapshot.get("state") or {}).get(
            "maptool_map_id"
        )
        if not resolved_map_id:
            raise ValueError("MapTool sync needs a map_id or a saved live map id")
        map_snapshot = await live_maptool_service.sync_map_state(
            db,
            map_id=resolved_map_id,
            auth_header=authorization,
            retries=payload.retries,
        )
        if payload.remember_map_id:
            await live_session_service.set_maptool_map_id(
                db,
                map_snapshot["map_id"],
                reset_maptool_snapshot=False,
            )
        response_payload = await live_session_service.load_snapshot(db)
        success = True
        return response_payload
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        metrics_service.record(
            "live.maptool_sync",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(payload.model_dump()),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.post("/respond")
async def respond_live(
    payload: LiveAssistantRequest,
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = await live_assistant_service.respond(
            db,
            message=payload.message,
            mode=payload.mode,
        )
        success = True
        return response_payload
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    finally:
        metrics_service.record(
            "live.respond",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(payload.model_dump()),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/pc-sheets")
async def list_live_pc_sheets(
    q: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    overview = await campaign_service.get_overview(db)
    query = (q or "").strip().casefold()
    items = []
    for entity in overview.get("pcs") or []:
        sheet = _pc_sheet_view(entity)
        if not _text_matches(
            query,
            sheet.get("player_name"),
            sheet.get("character_name"),
            sheet.get("summary"),
            sheet.get("identity", {}).get("class_name"),
            sheet.get("identity", {}).get("ancestry"),
        ):
            continue
        items.append(
            {
                "id": sheet["id"],
                "player_name": sheet["player_name"],
                "character_name": sheet["character_name"],
                "summary": sheet["summary"],
                "portrait": sheet["portrait"],
                "has_imported_sheet": sheet["has_imported_sheet"],
                "class_name": sheet["identity"].get("class_name"),
                "level": sheet["identity"].get("level"),
                "identity": sheet["identity"],
                "combat": sheet["combat"],
                "abilities": sheet["abilities"],
                "skills": sheet["skills"],
                "lores": sheet["lores"],
                "attacks": sheet["attacks"],
                "armor": sheet["armor"],
                "specials": sheet["specials"],
                "resistances": sheet["resistances"],
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/pc-sheet")
async def get_live_pc_sheet(
    id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    entity = await campaign_service.get_entity(id, db)
    if entity is None:
        raise _not_found("PC was not found")
    if entity.entity_type != "pc":
        raise _bad_request("Requested entity is not a PC")
    return _pc_sheet_view(
        campaign_service.entity_to_dict(
            entity,
            include_relationships=True,
            include_sheet_versions=True,
        )
    )


@router.get("/npc-sheets")
async def list_live_npc_sheets(
    q: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    overview = await campaign_service.get_overview(db)
    query = (q or "").strip().casefold()
    items = []
    for entity in overview.get("npcs") or []:
        details = entity.get("details") or {}
        dossier = _npc_dossier_view(entity)
        if not _text_matches(
            query,
            entity.get("name"),
            entity.get("summary"),
            details.get("role"),
            details.get("status"),
        ):
            continue
        items.append(
            {
                "id": entity.get("id"),
                "name": entity.get("name"),
                "summary": entity.get("summary"),
                "role": dossier.get("role"),
                "status": dossier.get("status"),
                "status_detail": dossier.get("status_detail"),
                "portrait": _portrait_ref(details),
                "current_location": entity.get("current_location"),
                "appearance_description": dossier.get("appearance_description"),
                "gm_summary": dossier.get("gm_summary"),
                "pc_encountered": dossier.get("pc_encountered"),
                "pc_relationship_status": dossier.get("pc_relationship_status"),
                "campaign_encounters": dossier.get("campaign_encounters"),
                "player_facing": dossier.get("player_facing"),
                "goals": dossier.get("goals"),
                "secrets": dossier.get("secrets"),
                "clues": dossier.get("clues"),
                "combat": dossier.get("combat"),
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/npc-sheet")
async def get_live_npc_sheet(
    id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    entity = await campaign_service.get_entity(id, db)
    if entity is None:
        raise _not_found("NPC was not found")
    if entity.entity_type != "npc":
        raise _bad_request("Requested entity is not an NPC")
    return _npc_dossier_view(
        campaign_service.entity_to_dict(
            entity,
            include_relationships=True,
        )
    )


@router.patch("/npc-sheet")
async def update_live_npc_sheet(
    payload: LiveNPCDossierUpdate,
    id: int = Query(gt=0),
    db: AsyncSession = Depends(get_db),
):
    entity = await campaign_service.get_entity(id, db)
    if entity is None:
        raise _not_found("NPC was not found")
    if entity.entity_type != "npc":
        raise _bad_request("Requested entity is not an NPC")

    current_details = dict(entity.details or {})
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "campaign_encounters":
            current_details[key] = [
                item.strip() for item in value if isinstance(item, str) and item.strip()
            ]
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped:
                current_details[key] = stripped
            else:
                current_details.pop(key, None)
        elif value is None:
            current_details.pop(key, None)
        else:
            current_details[key] = value

    updated = await campaign_service.update_entity(
        id,
        db,
        details=current_details,
    )
    return _npc_dossier_view(
        campaign_service.entity_to_dict(
            updated,
            include_relationships=True,
        )
    )


@router.get("/campaign-overview")
async def get_campaign_overview():
    root = _vault_root()
    note_path = _ensure_vault_note(
        CAMPAIGN_OVERVIEW_PATH,
        DEFAULT_CAMPAIGN_OVERVIEW,
    )
    return _note_payload(root, note_path)


@router.patch("/campaign-overview")
async def update_campaign_overview(payload: LiveCommandCenterNoteUpdate):
    root = _vault_root()
    note_path = _ensure_vault_note(
        CAMPAIGN_OVERVIEW_PATH,
        DEFAULT_CAMPAIGN_OVERVIEW,
    )
    note_path.write_text(payload.content.rstrip() + "\n", encoding="utf-8")
    return _note_payload(root, note_path)


@router.get("/session-overviews")
async def list_session_overviews():
    root = _vault_root()
    _ensure_vault_note(
        f"{SESSION_OVERVIEW_DIR}/Next Session.md",
        DEFAULT_NEXT_SESSION_OVERVIEW,
    )
    paths = _session_note_paths(root)
    return {
        "vault_path": str(root),
        "items": [
            {
                "path": path.relative_to(root).as_posix(),
                "title": path.stem,
                "updated_at": path.stat().st_mtime,
            }
            for path in paths
        ],
        "total": len(paths),
    }


@router.get("/session-overview")
async def get_session_overview(path: str = Query(min_length=1)):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    try:
        note_path = _safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not note_path.exists() or note_path.suffix.lower() != ".md":
        raise _not_found("Session overview was not found")
    relative = note_path.relative_to(root).as_posix()
    if not (
        relative.startswith(f"{SESSION_OVERVIEW_DIR}/")
        or (
            relative.startswith("Command Center/Session ")
            and note_path.parent.name == "Command Center"
        )
    ):
        raise _bad_request("Requested note is not a session overview")
    return _note_payload(root, note_path)


@router.patch("/session-overview")
async def update_session_overview(
    payload: LiveCommandCenterNoteUpdate,
    path: str = Query(min_length=1),
):
    root = _vault_root()
    current = await get_session_overview(path)
    note_path = _safe_child(root, current["path"])
    note_path.write_text(payload.content.rstrip() + "\n", encoding="utf-8")
    return _note_payload(root, note_path)


@router.get("/vault/notes")
async def list_vault_notes(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=80, ge=1, le=300),
):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    query = (q or "").strip().casefold()
    notes = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root).as_posix()
        if query and query not in relative.casefold():
            continue
        notes.append(
            {
                "path": relative,
                "title": path.stem,
                "folder": (
                    path.parent.relative_to(root).as_posix()
                    if path.parent != root
                    else ""
                ),
                "updated_at": path.stat().st_mtime,
            }
        )
        if len(notes) >= limit:
            break
    return {"vault_path": str(root), "items": notes, "total": len(notes)}


@router.get("/vault/note")
async def get_vault_note(path: str = Query(min_length=1)):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    try:
        note_path = _safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not note_path.exists() or note_path.suffix.lower() != ".md":
        raise _not_found("Vault note was not found")
    return {
        "vault_path": str(root),
        "path": note_path.relative_to(root).as_posix(),
        "title": note_path.stem,
        "content": note_path.read_text(encoding="utf-8"),
        "updated_at": note_path.stat().st_mtime,
    }


@router.patch("/vault/note")
async def update_vault_note(
    payload: LiveCommandCenterNoteUpdate,
    path: str = Query(min_length=1),
):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    try:
        note_path = _safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not note_path.exists() or note_path.suffix.lower() != ".md":
        raise _not_found("Vault note was not found")
    note_path.write_text(payload.content.rstrip() + "\n", encoding="utf-8")
    return _note_payload(root, note_path)


@router.get("/vault/file")
async def get_vault_file(path: str = Query(min_length=1)):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    try:
        file_path = _safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not file_path.exists() or not file_path.is_file():
        raise _not_found("Vault file was not found")
    media_types = {
        ".pdf": "application/pdf",
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
    }
    return FileResponse(
        file_path,
        media_type=media_types.get(
            file_path.suffix.lower(), "application/octet-stream"
        ),
        filename=_content_disposition_filename(file_path),
    )


@router.post("/player-handout-export")
async def export_player_handout(payload: LivePlayerHandoutExportRequest):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    try:
        note_path = _safe_child(root, payload.path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not note_path.exists() or note_path.suffix.lower() != ".md":
        raise _not_found("Player handout source note was not found")

    try:
        from scripts.export_player_prep_pdf import (
            _parse_markdown,
            _slugify,
            build_html,
            export_pdf,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load player handout exporter: {exc}",
        ) from exc

    markdown = note_path.read_text(encoding="utf-8")
    title, _sections = _parse_markdown(markdown)
    basename = payload.basename or _slugify(title)
    output_dir = _safe_child(root, HANDOUT_EXPORT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{basename}.html"
    pdf_path = output_dir / f"{basename}.pdf"
    html_path.write_text(build_html(markdown), encoding="utf-8")

    pdf_relative = None
    if not payload.html_only:
        try:
            export_pdf(html_path, pdf_path, chrome_path=None)
            pdf_relative = pdf_path.relative_to(root).as_posix()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not render PDF with Chrome/Chromium: {exc}",
            ) from exc

    html_relative = html_path.relative_to(root).as_posix()
    return {
        "vault_path": str(root),
        "input_path": note_path.relative_to(root).as_posix(),
        "title": title,
        "html_path": html_relative,
        "html_url": f"/api/live/vault/file?path={quote(html_relative)}",
        "pdf_path": pdf_relative,
        "pdf_url": (
            f"/api/live/vault/file?path={quote(pdf_relative)}" if pdf_relative else None
        ),
    }


@router.get("/vault/resolve-link")
async def resolve_vault_link(target: str = Query(min_length=1)):
    root = _vault_root()
    if not root.exists():
        raise _not_found("Configured Obsidian vault was not found")
    note_target, heading = _split_wikilink_target(target)
    note_path = _resolve_vault_note(root, note_target)
    if note_path is None:
        raise _not_found("Vault wikilink target was not found")
    return {
        "vault_path": str(root),
        "path": note_path.relative_to(root).as_posix(),
        "title": note_path.stem,
        "heading": heading,
        "target": target,
    }


@router.get("/reference-pdfs")
async def list_reference_pdfs(q: Optional[str] = Query(default=None)):
    root = _pdf_root()
    if not root.exists():
        return {"root_path": str(root), "items": [], "total": 0}
    query = (q or "").strip().casefold()
    items = []
    for path in sorted(root.rglob("*.pdf")):
        relative = path.relative_to(root).as_posix()
        if (
            query
            and query not in relative.casefold()
            and query not in path.stem.casefold()
        ):
            continue
        items.append(
            {
                "path": relative,
                "title": path.stem,
                "folder": (
                    path.parent.relative_to(root).as_posix()
                    if path.parent != root
                    else ""
                ),
                "url": f"/api/live/reference-pdf?path={quote(relative)}",
            }
        )
    return {"root_path": str(root), "items": items, "total": len(items)}


@router.get("/reference-pdf")
async def get_reference_pdf(path: str = Query(min_length=1)):
    root = _pdf_root()
    try:
        pdf_path = _safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        raise _not_found("Reference PDF was not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


@router.get("/dungeon-maps")
async def list_dungeon_maps(q: Optional[str] = Query(default=None)):
    root = _map_root()
    if not root.exists():
        return {"root_path": str(root), "items": [], "total": 0}
    query = (q or "").strip().casefold()
    items = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        relative = path.relative_to(root).as_posix()
        searchable = f"{relative} {path.stem}".casefold()
        if query and query not in searchable:
            continue
        items.append(
            {
                "map_id": _map_id_from_path(path),
                "path": relative,
                "title": path.stem,
                "folder": (
                    path.parent.relative_to(root).as_posix()
                    if path.parent != root
                    else ""
                ),
                "url": f"/api/live/dungeon-map?path={quote(relative)}",
            }
        )
    return {"root_path": str(root), "items": items, "total": len(items)}


@router.get("/dungeon-map")
async def get_dungeon_map(path: str = Query(min_length=1)):
    root = _map_root()
    try:
        map_path = _safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if map_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise _not_found("Dungeon map was not found")
    if not map_path.exists():
        raise _not_found("Dungeon map was not found")
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }[map_path.suffix.lower()]
    return FileResponse(map_path, media_type=media_type, filename=map_path.name)


@router.get("/dungeon-room-key")
async def get_dungeon_room_key(map_id: str = Query(min_length=1)):
    root = _room_key_root()
    if not root.exists():
        raise _not_found("Configured dungeon room-key root was not found")
    normalized_map_id = map_id.strip().casefold()
    for path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if str(payload.get("map_id", "")).strip().casefold() == normalized_map_id:
            payload["path"] = path.relative_to(root).as_posix()
            return _enrich_room_key_literal_text(payload)
    raise _not_found("Dungeon room key was not found")


@router.get("/aon-creatures", response_model=AonCreatureSearchResponse)
async def list_aon_creatures(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
):
    return {
        "items": aon_creature_service.search_creatures(q or "", limit=limit),
    }


@router.get("/aon-creature", response_model=AonCreatureResponse)
async def get_aon_creature(
    creature_id: int = Query(ge=1),
    refresh: bool = Query(default=False),
):
    try:
        document = aon_creature_service.get_creature(
            creature_id,
            refresh=refresh,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch PF2e creature data from Archives of Nethys: {exc}",
        ) from exc
    return {
        "creature": {
            "creature_id": document.creature_id,
            "name": document.name,
            "level": document.level,
            "source_url": document.source_url,
            "source": document.source,
            "traits": document.traits,
            "content": document.content,
            "remastered": document.remastered,
            "legacy": document.legacy,
            "ac": document.ac,
            "hp": document.hp,
            "fort": document.fort,
            "ref": document.ref,
            "will": document.will,
            "speed": document.speed,
            "perception": document.perception,
            "attacks": document.attacks,
            "fetched_at": document.fetched_at,
            "ruleset": "pf2e",
        },
    }


@page_router.get("/dm-panel", response_class=HTMLResponse)
async def get_dm_panel():
    return HTMLResponse(
        _load_panel_html(),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def _load_panel_html() -> str:
    panel_path = Path(__file__).resolve().parent.parent / "static" / "dm_panel.html"
    return panel_path.read_text(encoding="utf-8")
