from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Header, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import settings
from backend.models.base import get_db
from backend.services.campaign_service import campaign_service
from backend.services.aon_creature_service import aon_creature_service
from backend.services.ingestion_service import ingestion_service
from backend.services.live_assistant_service import live_assistant_service
from backend.services.live_maptool_service import live_maptool_service
from backend.services.live_session_service import live_session_service
from backend.services.metrics_service import metrics_service
from backend.services.obsidian_markdown import split_frontmatter
from backend.services.private_campaign_data_service import private_campaign_data_service
from backend.services.private_image_intake_service import private_image_intake_service
from backend.services.private_index_service import private_index_service
from backend.services.private_import_audit_service import private_import_audit_service
from backend.services.reference_corpus_service import reference_corpus_service


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
    combat_state: Optional[dict[str, Any]] = None


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


ALLOWED_PORTRAIT_CONTENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class LiveCommandCenterNoteUpdate(BaseModel):
    content: str


class LivePlayerHandoutExportRequest(BaseModel):
    path: str = Field(min_length=1)
    basename: Optional[str] = None
    html_only: bool = False


class LiveTTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    voice: Optional[str] = None
    rate: Optional[float] = Field(default=None, ge=0.5, le=1.6)
    pitch: Optional[float] = Field(default=None, ge=0.5, le=1.6)


class AonCreatureSearchResponse(BaseModel):
    items: list[dict]


class AonCreatureResponse(BaseModel):
    creature: dict


class CampaignBestiarySearchResponse(BaseModel):
    items: list[dict]


class CampaignBestiaryEntryResponse(BaseModel):
    entry: dict


class ImportRunCreateRequest(BaseModel):
    title: Optional[str] = None
    map_id: Optional[str] = None


class ImportRoomDraftUpdate(BaseModel):
    review_status: Optional[str] = None
    reviewer_notes: Optional[str] = None
    fields: Optional[dict[str, Any]] = None


class DependencyReviewUpdate(BaseModel):
    action: Literal["ignore", "mark_custom", "link_aon", "needs_review"]
    resolved_id: Optional[str] = None
    reviewer_notes: Optional[str] = None


class ImageIntakeCreateRequest(BaseModel):
    source_id: Optional[str] = None


class ImageCandidateUpdate(BaseModel):
    category: Optional[str] = None
    review_status: Optional[str] = None
    visibility: Optional[str] = None
    proposed_match: Optional[dict[str, Any]] = None
    reviewer_notes: Optional[str] = None


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


def _bestiary_root() -> Path:
    return (_room_key_root().parent / "bestiary").resolve()


def _settlements_payload() -> dict[str, Any]:
    return private_campaign_data_service.read_json(
        "settlements.json",
        {"campaign_id": private_campaign_data_service.campaign_id(), "items": []},
    )


def _vault_root() -> Path:
    return _configured_path(settings.obsidian_vault_path)


def _map_id_from_path(path: Path) -> str:
    return path.stem.strip().casefold().replace(" ", "-")


def _text_matches(query: str, *values: object) -> bool:
    if not query:
        return True
    haystack = " ".join(str(value or "") for value in values).casefold()
    return query in haystack


def _settlement_search_text(settlement: dict[str, Any]) -> str:
    values = [
        settlement.get("id"),
        settlement.get("name"),
        settlement.get("title"),
        settlement.get("summary"),
        settlement.get("look_and_feel"),
        settlement.get("demographics"),
        *(settlement.get("quest_hooks") or []),
        *(settlement.get("gather_information") or []),
    ]
    for location in settlement.get("locations") or []:
        if not isinstance(location, dict):
            continue
        values.extend(
            [
                location.get("id"),
                location.get("name"),
                location.get("type"),
                location.get("summary"),
                *(location.get("services") or []),
                *(location.get("npcs") or []),
                *(location.get("quest_hooks") or []),
                *(location.get("gather_information") or []),
            ]
        )
    return " ".join(str(value) for value in values if value).casefold()


def _settlement_view(settlement: dict[str, Any]) -> dict[str, Any]:
    item = dict(settlement)
    map_path = str(item.get("map_path") or "").strip()
    item["map_url"] = private_campaign_data_service.private_file_url(map_path)
    item["locations"] = [
        dict(location)
        for location in item.get("locations") or []
        if isinstance(location, dict)
    ]
    return item


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
        words = [re.escape(part) for part in re.findall(r"[A-Za-z0-9]+", title)]
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


def _find_titled_room_heading(
    text: str,
    room_id: str,
    title: str | None = None,
) -> re.Match[str] | None:
    if not title:
        return None
    return _room_heading_pattern(room_id, title).search(text)


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

CANONICAL_DUNGEON_MAPS = [
    {
        "path": "abomination-vaults/maps/BOOK 1/Graveyard.webp",
        "map_id": "graveyard",
        "title": "Graveyard",
    },
    {
        "path": "abomination-vaults/maps/BOOK 1/Level1.jpg",
        "map_id": "level1",
        "title": "Level 1",
    },
    {
        "path": "abomination-vaults/maps/BOOK 1/Level2.jpg",
        "map_id": "level2",
        "title": "Level 2",
    },
    {
        "path": "abomination-vaults/maps/BOOK 1/Level3.jpg",
        "map_id": "level3",
        "title": "Level 3",
    },
    {
        "path": "abomination-vaults/maps/BOOK 1/level4.webp",
        "map_id": "level4",
        "title": "Level 4",
    },
    {
        "path": "abomination-vaults/maps/BOOK 2/level5.webp",
        "map_id": "level5",
        "title": "Level 5",
    },
    {
        "path": "abomination-vaults/maps/BOOK 2/level6.webp",
        "map_id": "level6",
        "title": "Level 6",
    },
    {
        "path": "abomination-vaults/maps/BOOK 2/level7.webp",
        "map_id": "level7",
        "title": "Level 7",
    },
    {
        "path": "abomination-vaults/maps/BOOK 3/level8.webp",
        "map_id": "level8",
        "title": "Level 8",
    },
    {
        "path": "abomination-vaults/maps/BOOK 3/level9-100px.webp",
        "map_id": "level9",
        "title": "Level 9",
    },
    {
        "path": "abomination-vaults/maps/BOOK 3/level10.webp",
        "map_id": "level10",
        "title": "Level 10",
    },
]


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


ROOM_ENCOUNTER_SPLIT_MARKERS = {
    "C34": "NHAKAZARIN",
    "C36": "CHANDRIU INVISAR",
}


ROOM_ENCOUNTER_TAIL_MARKERS = {
    "C34": "The Statue:",
    "C36": "Treasure:",
}


def _trim_stat_leak(text: str, marker: str) -> str:
    index = text.find(marker)
    return text[:index].strip() if index > -1 else text


def _split_embedded_room_encounter(
    literal: dict[str, str],
    *,
    encounter_marker: str,
    tail_marker: str | None = None,
) -> dict[str, str]:
    general = literal.get("general_text") or ""
    if not general or literal.get("encounter_text"):
        return literal
    marker_index = general.find(encounter_marker)
    if marker_index < 0:
        return literal

    before = general[:marker_index].strip()
    encounter = general[marker_index:].strip()
    tail = ""
    if tail_marker:
        tail_index = encounter.find(tail_marker)
        if tail_index > -1:
            tail = encounter[tail_index:].strip()
            encounter = encounter[:tail_index].strip()

    if before or tail:
        literal["general_text"] = "\n\n".join(part for part in [before, tail] if part)
    else:
        literal.pop("general_text", None)
    if encounter:
        literal["encounter_text"] = _format_encounter_text(encounter)
    return literal


def _apply_room_literal_fixes(
    room_id: str | None,
    literal: dict[str, str],
) -> dict[str, str]:
    if not room_id:
        return literal
    if room_id in ROOM_ENCOUNTER_FALLBACKS and not literal.get("encounter_text"):
        literal["encounter_text"] = ROOM_ENCOUNTER_FALLBACKS[room_id]
    if room_id in ROOM_ENCOUNTER_SPLIT_MARKERS:
        literal = _split_embedded_room_encounter(
            literal,
            encounter_marker=ROOM_ENCOUNTER_SPLIT_MARKERS[room_id],
            tail_marker=ROOM_ENCOUNTER_TAIL_MARKERS.get(room_id),
        )
    if room_id == "A10" and literal.get("general_text"):
        literal["general_text"] = _trim_stat_leak(literal["general_text"], "BITE BITE")
    if room_id == "A23" and literal.get("general_text"):
        literal["general_text"] = _trim_stat_leak(literal["general_text"], "CE elite")
    if room_id == "A24" and literal.get("general_text"):
        literal["general_text"] = _trim_stat_leak(literal["general_text"], "FLICKERWISP")
    if room_id == "C37" and literal.get("read_aloud"):
        literal["read_aloud"] = re.sub(
            r"\(see cavern chamber\. The air is cold and damp, and to the east area C8\)\.",
            "(see area C8).",
            literal["read_aloud"],
        )
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
    first_room = next(
        (
            room
            for room in rooms
            if isinstance(room, dict)
            and str(room.get("room_id") or "").strip()
            and str(room.get("title") or "").strip()
        ),
        None,
    )
    if first_room:
        first_match = _find_titled_room_heading(
            text,
            str(first_room.get("room_id") or "").strip(),
            str(first_room.get("title") or "").strip(),
        )
        if first_match:
            text = text[first_match.start() :]
    matches: list[tuple[int, dict]] = []
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id") or "").strip()
        if not room_id:
            continue
        title = str(room.get("title") or "")
        match = _find_titled_room_heading(text, room_id, title)
        if not match:
            match = _find_room_heading(text, room_id, title)
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


def _campaign_bestiary_files() -> list[Path]:
    root = _bestiary_root()
    if not root.exists():
        return []
    return sorted(root.rglob("*.json"))


def _load_campaign_bestiary_payloads() -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    root = _bestiary_root()
    for path in _campaign_bestiary_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        payload["_path"] = path.relative_to(root).as_posix()
        payloads.append(payload)
    return payloads


def _campaign_bestiary_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for payload in _load_campaign_bestiary_payloads():
        campaign = payload.get("campaign")
        level = payload.get("level")
        source_file = payload.get("_path")
        for entry in payload.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            normalized = dict(entry)
            normalized.setdefault("campaign", campaign)
            normalized.setdefault("level_scope", level)
            normalized.setdefault("source_file", source_file)
            entries.append(normalized)
    return entries


def _campaign_bestiary_summary(entry: dict[str, Any]) -> dict[str, Any]:
    portrait = entry.get("portrait") or ""
    return {
        "id": entry.get("id"),
        "name": entry.get("name"),
        "entry_type": entry.get("entry_type"),
        "level": entry.get("level"),
        "source": entry.get("source"),
        "source_file": entry.get("source_file"),
        "source_page": entry.get("source_page"),
        "rooms": entry.get("rooms") or [],
        "traits": entry.get("traits") or [],
        "summary": entry.get("summary") or "",
        "campaign": entry.get("campaign"),
        "level_scope": entry.get("level_scope"),
        "aon_creature_id": entry.get("aon_creature_id"),
        "base_creature": entry.get("base_creature"),
        "combat": entry.get("combat") or {},
        "portrait": _private_media_url(portrait) or portrait,
        "image": {
            "ref": portrait,
            "url": _private_media_url(portrait),
            "status": "local" if portrait else "missing",
            "source": entry.get("image_source"),
        },
    }


def _campaign_bestiary_search_text(entry: dict[str, Any]) -> str:
    values = [
        entry.get("id"),
        entry.get("name"),
        entry.get("entry_type"),
        entry.get("source"),
        entry.get("summary"),
        entry.get("base_creature"),
        *(entry.get("rooms") or []),
        *(entry.get("traits") or []),
    ]
    return " ".join(str(value) for value in values if value).casefold()


def _campaign_bestiary_entry(entry_id: str) -> dict[str, Any] | None:
    normalized_id = entry_id.strip().casefold()
    for entry in _campaign_bestiary_entries():
        if str(entry.get("id") or "").strip().casefold() == normalized_id:
            detail = dict(entry)
            portrait = detail.get("portrait") or ""
            detail["portrait"] = _private_media_url(portrait) or portrait
            detail["image"] = {
                "ref": portrait,
                "url": _private_media_url(portrait),
                "status": "local" if portrait else "missing",
                "source": detail.get("image_source"),
            }
            return detail
    return None


def _update_campaign_bestiary_entry(
    entry_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    normalized_id = entry_id.strip().casefold()
    root = _bestiary_root()
    for path in _campaign_bestiary_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "").strip().casefold() != normalized_id:
                continue
            entry.update(updates)
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            updated = dict(entry)
            updated.setdefault("campaign", payload.get("campaign"))
            updated.setdefault("level_scope", payload.get("level"))
            updated.setdefault("source_file", path.relative_to(root).as_posix())
            return updated
    return None


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


def _extract_json_block(body: str) -> dict[str, Any]:
    match = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", body)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _source_json_payload(frontmatter: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    source_url = frontmatter.get("source_url")
    if isinstance(source_url, str) and source_url.strip():
        candidates.append(Path(source_url.strip()))
    source_name = frontmatter.get("source_name")
    if isinstance(source_name, str) and source_name.strip():
        candidates.append(Path("assets/imports") / source_name.strip())
    for candidate in candidates:
        if candidate.suffix.lower() != ".json" or not candidate.exists():
            continue
        try:
            parsed = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return None


def _vault_pc_payload(frontmatter: dict[str, Any], body: str) -> dict[str, Any]:
    raw_sheet = _extract_json_block(body) or _source_json_payload(frontmatter)
    build = raw_sheet.get("build") if isinstance(raw_sheet.get("build"), dict) else {}
    abilities = build.get("abilities") if isinstance(build.get("abilities"), dict) else {}
    attributes = (
        build.get("attributes") if isinstance(build.get("attributes"), dict) else {}
    )
    ac_total = build.get("acTotal") if isinstance(build.get("acTotal"), dict) else {}

    def _fm_int(key: str) -> int | None:
        return _int_value(frontmatter.get(key))

    def _first(key: str, fallback: Any = None) -> Any:
        return build.get(key) if build.get(key) not in (None, "") else fallback

    return {
        "name": _first("name", frontmatter.get("pc_name")),
        "class_name": _first("class", frontmatter.get("class_name")),
        "level": _int_value(_first("level", frontmatter.get("level"))) or 1,
        "xp": _int_value(_first("xp", frontmatter.get("xp"))),
        "ancestry": _first("ancestry", frontmatter.get("ancestry")),
        "heritage": _first("heritage", frontmatter.get("heritage")),
        "background": _first("background", frontmatter.get("background")),
        "alignment": _first("alignment", frontmatter.get("alignment")),
        "gender": _first("gender"),
        "age": _first("age"),
        "deity": _first("deity"),
        "keyability": _first("keyability", frontmatter.get("key_ability")),
        "languages": _first("languages", frontmatter.get("languages") or []),
        "attributes": {
            "str": _int_value(abilities.get("str")) or _fm_int("strength"),
            "dex": _int_value(abilities.get("dex")) or _fm_int("dexterity"),
            "con": _int_value(abilities.get("con")) or _fm_int("constitution"),
            "int": _int_value(abilities.get("int")) or _fm_int("intelligence"),
            "wis": _int_value(abilities.get("wis")) or _fm_int("wisdom"),
            "cha": _int_value(abilities.get("cha")) or _fm_int("charisma"),
        },
        "vitals": {
            "ancestry_hp": _int_value(attributes.get("ancestryhp"))
            or _fm_int("ancestry_hp"),
            "class_hp": _int_value(attributes.get("classhp"))
            or _fm_int("class_hp"),
            "bonus_hp": _int_value(attributes.get("bonushp")) or 0,
            "bonus_hp_per_level": _int_value(attributes.get("bonushpPerLevel")) or 0,
            "speed": _int_value(attributes.get("speed")) or _fm_int("speed"),
        },
        "ac": {
            "total": _int_value(ac_total.get("acTotal")) or _fm_int("armor_class"),
            "shield_bonus": _int_value(ac_total.get("shieldBonus"))
            or _fm_int("shield_bonus"),
        },
        "proficiencies": {
            "classDC": _fm_int("class_dc"),
            "perception": _fm_int("perception"),
            "fortitude": _fm_int("fortitude"),
            "reflex": _fm_int("reflex"),
            "will": _fm_int("will"),
            "acrobatics": _fm_int("acrobatics"),
            "arcana": _fm_int("arcana"),
            "athletics": _fm_int("athletics"),
            "crafting": _fm_int("crafting"),
            "deception": _fm_int("deception"),
            "diplomacy": _fm_int("diplomacy"),
            "intimidation": _fm_int("intimidation"),
            "medicine": _fm_int("medicine"),
            "nature": _fm_int("nature"),
            "occultism": _fm_int("occultism"),
            "performance": _fm_int("performance"),
            "religion": _fm_int("religion"),
            "society": _fm_int("society"),
            "stealth": _fm_int("stealth"),
            "survival": _fm_int("survival"),
            "thievery": _fm_int("thievery"),
        },
        "lores": _first("lores", []),
        "weapons": _first("weapons", []),
        "armor": _first("armor", []),
        "feats": _first("feats", []),
        "specials": _first(
            "specials",
            frontmatter.get("special_abilities") or frontmatter.get("specials") or [],
        ),
        "resistances": _first("resistances", frontmatter.get("resistances") or []),
        "items": _first("equipment", []),
        "money": _first("money", {}),
        "spellcasters": _first("spellCasters", []),
        "focus_points": _first("focusPoints"),
        "raw": raw_sheet,
    }


def _vault_pc_sheet_view(path: Path) -> dict[str, Any] | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    frontmatter, body = split_frontmatter(content)
    if frontmatter.get("document_kind") != "pc_sheet":
        return None
    doc_id = _int_value(frontmatter.get("doc_id"))
    payload = _vault_pc_payload(frontmatter, body)
    entity = {
        "id": doc_id or abs(hash(path.as_posix())),
        "stable_key": f"vault-pc-sheet-{path.stem.casefold()}",
        "entity_type": "pc",
        "name": frontmatter.get("pc_name") or payload.get("name") or path.stem,
        "summary": frontmatter.get("summary"),
        "description": body,
        "details": {
            "portrait": frontmatter.get("portrait")
            or frontmatter.get("imageLink")
            or frontmatter.get("image_link"),
            "image_status": frontmatter.get("image_status"),
            "image_source": frontmatter.get("image_source"),
            "image_attribution": frontmatter.get("image_attribution"),
            "image_notes": frontmatter.get("image_notes"),
            "class_name": frontmatter.get("class_name"),
            "level": frontmatter.get("level"),
            "ancestry": frontmatter.get("ancestry"),
            "heritage": frontmatter.get("heritage"),
            "background": frontmatter.get("background"),
            "alignment": frontmatter.get("alignment"),
            "size_name": frontmatter.get("size_name"),
            "languages": frontmatter.get("languages") or [],
            "specials": frontmatter.get("special_abilities") or [],
            "notable_items": frontmatter.get("related_entities") or [],
        },
        "latest_sheet_version": {
            "payload": payload,
            "source_name": frontmatter.get("source_name") or path.name,
        },
    }
    sheet = _pc_sheet_view(entity)
    sheet["id"] = entity["id"]
    sheet["vault_path"] = path.relative_to(_vault_root()).as_posix()
    sheet["player_name"] = str(frontmatter.get("title") or path.stem)
    sheet["character_name"] = str(entity["name"])
    return sheet


def _vault_pc_sheets() -> list[dict[str, Any]]:
    root = _vault_root() / "Sheets"
    if not root.exists():
        return []
    sheets = []
    for path in sorted(root.glob("*.md")):
        sheet = _vault_pc_sheet_view(path)
        if sheet:
            sheets.append(sheet)
    return sheets


def _vault_npc_frontmatter(name: str | None) -> dict[str, Any]:
    if not name:
        return {}
    root = _vault_root()
    npc_root = root / "Campaign" / "NPCs"
    if not npc_root.exists():
        return {}

    candidates = [npc_root / f"{name}.md"]
    normalized = name.casefold()
    candidates.extend(
        path
        for path in sorted(npc_root.glob("*.md"))
        if path.stem.casefold() == normalized and path not in candidates
    )

    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            frontmatter, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        return frontmatter
    return {}


def _merge_vault_npc_image_metadata(entity: dict) -> dict:
    frontmatter = _vault_npc_frontmatter(entity.get("name"))
    if not frontmatter:
        return entity

    merged = dict(entity)
    details = dict(merged.get("details") or {})
    for key in (
        "portrait",
        "portrait_url",
        "imageLink",
        "image_link",
        "imageUrl",
        "image_url",
        "image_status",
        "image_source",
        "image_attribution",
        "image_notes",
    ):
        value = frontmatter.get(key)
        if value:
            details[key] = value
    merged["details"] = details
    return merged


def _portrait_ref(details: dict) -> str | None:
    for key in (
        "portrait",
        "portrait_url",
        "image",
        "imageLink",
        "image_link",
        "imageUrl",
        "image_url",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _portrait_filename(name: str | None, npc_id: int, suffix: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", str(name or "").casefold()).strip("-")
    if not stem:
        stem = f"npc-{npc_id}"
    return f"{stem}-{npc_id}{suffix}"


def _bestiary_portrait_filename(name: str | None, entry_id: str, suffix: str) -> str:
    base = name or entry_id
    stem = re.sub(r"[^a-z0-9]+", "-", str(base).casefold()).strip("-")
    entry_slug = re.sub(r"[^a-z0-9]+", "-", str(entry_id).casefold()).strip("-")
    if not stem:
        stem = entry_slug or "bestiary-entry"
    if entry_slug and entry_slug not in stem:
        stem = f"{stem}-{entry_slug}"
    return f"{stem}{suffix}"


def _private_media_url(ref: str | None) -> str | None:
    if not ref:
        return None
    value = ref.strip()
    if value.startswith(("http://", "https://", "/")):
        return value
    return private_campaign_data_service.private_file_url(value)


def _vault_image_url(ref: str | None) -> str | None:
    if not ref:
        return None
    value = ref.strip()
    if value.startswith(("http://", "https://", "/")):
        return value
    if value.startswith("private-local:"):
        return private_campaign_data_service.private_file_url(
            value.split(":", 1)[1].strip()
        )
    if Path(value).suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".svg",
    }:
        return private_campaign_data_service.private_file_url(value)
    match = re.fullmatch(r"!?\[\[([^\]]+)\]\]", value)
    if not match:
        return None
    target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
    if Path(target).suffix.lower() not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
        ".svg",
    }:
        return None
    return f"/api/live/vault/file?path={quote(target)}"


def _image_view(details: dict) -> dict[str, Any]:
    ref = _portrait_ref(details)
    url = _vault_image_url(ref)
    status = details.get("image_status")
    if not status:
        if url and ref and ref.startswith(("http://", "https://")):
            status = "remote"
        elif url:
            status = "local"
        elif ref and re.fullmatch(r"!?\[\[[^\]]+\]\]", ref.strip()):
            status = "needs review"
        else:
            status = "missing"
    return {
        "ref": ref,
        "url": url,
        "status": status,
        "source": details.get("image_source"),
        "attribution": details.get("image_attribution"),
        "notes": details.get("image_notes"),
    }


def _private_campaign_item_view(item: dict[str, Any]) -> dict[str, Any]:
    """Return a private-local item with browser-ready media URLs."""
    view = dict(item)
    details = dict(view.get("details") or {})
    image = {**_image_view(details), **dict(view.get("image") or {})}
    portrait = view.get("portrait")
    if isinstance(portrait, str) and portrait and not portrait.startswith(
        ("http://", "https://", "/")
    ):
        image.setdefault("ref", portrait)
        image["url"] = private_campaign_data_service.private_file_url(portrait)
        view["portrait"] = image["url"]
    elif portrait and not image.get("url"):
        image["url"] = portrait
    if image:
        view["image"] = image
    return view


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
        "portrait": _vault_image_url(_portrait_ref(details)) or _portrait_ref(details),
        "image": _image_view(details),
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
    entity = _merge_vault_npc_image_metadata(entity)
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
        "portrait": _vault_image_url(_portrait_ref(details)) or _portrait_ref(details),
        "image": _image_view(details),
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
            combat_state=payload.combat_state,
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
    query = (q or "").strip().casefold()
    items = []
    private_items = private_campaign_data_service.pc_items()
    if private_items:
        for sheet in private_items:
            sheet = _private_campaign_item_view(sheet)
            if not _text_matches(
                query,
                sheet.get("player_name"),
                sheet.get("character_name"),
                sheet.get("summary"),
                sheet.get("identity", {}).get("class_name"),
                sheet.get("identity", {}).get("ancestry"),
            ):
                continue
            items.append(sheet)
        return {"items": items, "total": len(items), "source": "private-local"}

    vault_items = _vault_pc_sheets()
    if vault_items:
        for sheet in vault_items:
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
                    "image": sheet["image"],
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
        return {"items": items, "total": len(items), "source": "obsidian_vault"}

    overview = await campaign_service.get_overview(db)
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
                "image": sheet["image"],
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
    for sheet in private_campaign_data_service.pc_items():
        if int(sheet.get("id") or 0) == id:
            return _private_campaign_item_view(sheet)

    for sheet in _vault_pc_sheets():
        if sheet.get("id") == id:
            return sheet

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
    query = (q or "").strip().casefold()
    items = []
    private_items = private_campaign_data_service.npc_items()
    if private_items:
        for dossier in private_items:
            dossier = _private_campaign_item_view(dossier)
            details = dossier.get("details") or {}
            if not _text_matches(
                query,
                dossier.get("name"),
                dossier.get("summary"),
                dossier.get("role"),
                details.get("role"),
                dossier.get("status"),
            ):
                continue
            items.append(
                {
                    "id": dossier.get("id"),
                    "name": dossier.get("name"),
                    "summary": dossier.get("summary"),
                    "role": dossier.get("role"),
                    "status": dossier.get("status"),
                    "status_detail": dossier.get("status_detail"),
                    "portrait": dossier.get("portrait"),
                    "image": dossier.get("image"),
                    "current_location": dossier.get("current_location"),
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
        return {"items": items, "total": len(items), "source": "private-local"}

    overview = await campaign_service.get_overview(db)
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
                "portrait": dossier.get("portrait"),
                "image": dossier.get("image"),
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
    for dossier in private_campaign_data_service.npc_items():
        if int(dossier.get("id") or 0) == id:
            return _private_campaign_item_view(dossier)

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
    private_updated = private_campaign_data_service.update_npc(
        id,
        payload.model_dump(exclude_unset=True),
    )
    if private_updated:
        return _private_campaign_item_view(private_updated)

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


@router.post("/npc-sheet/portrait")
async def upload_live_npc_portrait(
    id: int = Query(gt=0),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    suffix = ALLOWED_PORTRAIT_CONTENT_TYPES.get(content_type)
    if not suffix:
        raise _bad_request("Portrait must be a PNG, JPEG, WEBP, or GIF image.")
    data = await file.read()
    if not data:
        raise _bad_request("Portrait image was empty.")
    if len(data) > 12 * 1024 * 1024:
        raise _bad_request("Portrait image is too large; keep it under 12 MB.")

    private_dossier = None
    for dossier in private_campaign_data_service.npc_items():
        if int(dossier.get("id") or 0) == id:
            private_dossier = dossier
            break

    entity = None
    if private_dossier is None:
        entity = await campaign_service.get_entity(id, db)
        if entity is None:
            raise _not_found("NPC was not found")
        if entity.entity_type != "npc":
            raise _bad_request("Requested entity is not an NPC")

    name = (private_dossier or {}).get("name") if private_dossier else entity.name
    relative_path = (
        Path("media")
        / private_campaign_data_service.campaign_id()
        / "portraits"
        / "NPCs"
        / "manual"
        / _portrait_filename(name, id, suffix)
    )
    target = private_campaign_data_service.private_root() / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    portrait_ref = relative_path.as_posix()

    if private_dossier is not None:
        updated = private_campaign_data_service.update_npc(
            id,
            {
                "portrait": portrait_ref,
                "image_status": "local",
                "image_source": "manual upload",
            },
        )
        return _private_campaign_item_view(updated or private_dossier)

    current_details = dict(entity.details or {})
    current_details.update(
        {
            "portrait": portrait_ref,
            "image_status": "local",
            "image_source": "manual upload",
        }
    )
    updated = await campaign_service.update_entity(id, db, details=current_details)
    return _npc_dossier_view(
        campaign_service.entity_to_dict(
            updated,
            include_relationships=True,
        )
    )


@router.get("/campaign-overview")
async def get_campaign_overview(tab: str = Query(default="overview")):
    private_note = private_campaign_data_service.campaign_note_payload(
        tab,
        DEFAULT_CAMPAIGN_OVERVIEW,
    )
    if private_note:
        return private_note

    root = _vault_root()
    note_path = _ensure_vault_note(
        CAMPAIGN_OVERVIEW_PATH,
        DEFAULT_CAMPAIGN_OVERVIEW,
    )
    return _note_payload(root, note_path)


@router.patch("/campaign-overview")
async def update_campaign_overview(
    payload: LiveCommandCenterNoteUpdate,
    tab: str = Query(default="overview"),
):
    return private_campaign_data_service.update_campaign_note(
        tab,
        payload.content,
        tab.replace("-", " ").title(),
    )


@router.get("/session-overviews")
async def list_session_overviews():
    private_items = private_campaign_data_service.session_items()
    if private_items:
        return {
            "source": "private-local",
            "root_path": str(private_campaign_data_service.private_root()),
            "items": [
                {
                    "id": item.get("id"),
                    "path": item.get("path") or item.get("id"),
                    "title": item.get("title") or item.get("label") or item.get("id"),
                    "updated_at": item.get("updated_at"),
                }
                for item in private_items
            ],
            "total": len(private_items),
        }

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
    private_note = private_campaign_data_service.session_payload(path)
    if private_note:
        return private_note

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
    private_note = private_campaign_data_service.update_session(path, payload.content)
    if private_note:
        return private_note

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


@router.get("/private-file")
async def get_private_file(path: str = Query(min_length=1)):
    root = private_campaign_data_service.private_root()
    if not root.exists():
        raise _not_found("Configured private-local folder was not found")
    try:
        file_path = private_campaign_data_service.safe_child(root, path)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if not file_path.exists() or not file_path.is_file():
        raise _not_found("Private-local file was not found")
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
        ".json": "application/json",
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
    canonical_items = []
    for spec in CANONICAL_DUNGEON_MAPS:
        path = root / spec["path"]
        if not path.exists():
            continue
        item = _dungeon_map_item(root, path, spec)
        searchable = f"{item['path']} {item['title']} {item['map_id']}".casefold()
        if query and query not in searchable:
            continue
        canonical_items.append(item)
    if canonical_items:
        return {
            "root_path": str(root),
            "items": canonical_items,
            "total": len(canonical_items),
        }

    items = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        relative_parts = [part.casefold() for part in path.relative_to(root).parts]
        if root.name.casefold() != "maps" and "maps" not in relative_parts:
            continue
        if any(part in {"portraits", "portrait", "tokens"} for part in relative_parts):
            continue
        relative = path.relative_to(root).as_posix()
        searchable = f"{relative} {path.stem}".casefold()
        if query and query not in searchable:
            continue
        items.append(_dungeon_map_item(root, path))
    return {"root_path": str(root), "items": items, "total": len(items)}


def _dungeon_map_item(
    root: Path,
    path: Path,
    spec: dict[str, str] | None = None,
) -> dict[str, str]:
    relative = path.relative_to(root).as_posix()
    return {
        "map_id": (spec or {}).get("map_id") or _map_id_from_path(path),
        "path": relative,
        "title": (spec or {}).get("title") or path.stem,
        "folder": (
            path.parent.relative_to(root).as_posix()
            if path.parent != root
            else ""
        ),
        "url": f"/api/live/dungeon-map?path={quote(relative)}",
    }


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


@router.get("/town-square/settlements")
async def list_town_square_settlements(q: Optional[str] = Query(default=None)):
    payload = _settlements_payload()
    query = (q or "").strip().casefold()
    items = []
    for settlement in payload.get("items") or []:
        if not isinstance(settlement, dict):
            continue
        if query and query not in _settlement_search_text(settlement):
            continue
        view = _settlement_view(settlement)
        items.append(
            {
                "id": view.get("id"),
                "name": view.get("name") or view.get("title"),
                "title": view.get("title") or view.get("name"),
                "summary": view.get("summary") or "",
                "map_path": view.get("map_path") or "",
                "map_url": view.get("map_url"),
                "location_count": len(view.get("locations") or []),
            }
        )
    return {
        "campaign_id": payload.get("campaign_id") or private_campaign_data_service.campaign_id(),
        "items": items,
        "total": len(items),
    }


@router.get("/town-square/settlement")
async def get_town_square_settlement(id: str = Query(min_length=1)):
    normalized = id.strip().casefold()
    payload = _settlements_payload()
    for settlement in payload.get("items") or []:
        if not isinstance(settlement, dict):
            continue
        candidates = [settlement.get("id"), settlement.get("name"), settlement.get("title")]
        if any(str(candidate or "").strip().casefold() == normalized for candidate in candidates):
            return {
                "campaign_id": payload.get("campaign_id") or private_campaign_data_service.campaign_id(),
                "settlement": _settlement_view(settlement),
            }
    raise _not_found("Town Square settlement was not found")


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


@router.get("/campaign-bestiary", response_model=CampaignBestiarySearchResponse)
async def list_campaign_bestiary(
    q: Optional[str] = Query(default=None),
    entry_type: Optional[str] = Query(default=None),
    room_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    query = (q or "").strip().casefold()
    type_filter = (entry_type or "").strip().casefold()
    room_filter = (room_id or "").strip().casefold()
    items = []
    for entry in _campaign_bestiary_entries():
        if type_filter and str(entry.get("entry_type") or "").casefold() != type_filter:
            continue
        if room_filter and room_filter not in [
            str(room).casefold() for room in entry.get("rooms") or []
        ]:
            continue
        if query and query not in _campaign_bestiary_search_text(entry):
            continue
        items.append(_campaign_bestiary_summary(entry))
    items.sort(
        key=lambda item: (
            str(item.get("entry_type") or ""),
            int(item.get("level") or 999),
            str(item.get("name") or "").casefold(),
        )
    )
    return {"items": items[:limit]}


@router.get("/campaign-bestiary-entry", response_model=CampaignBestiaryEntryResponse)
async def get_campaign_bestiary_entry(id: str = Query(min_length=1)):
    entry = _campaign_bestiary_entry(id)
    if entry is None:
        raise _not_found("Campaign bestiary entry was not found")
    return {"entry": entry}


@router.post("/campaign-bestiary-entry/portrait", response_model=CampaignBestiaryEntryResponse)
async def upload_campaign_bestiary_portrait(
    id: str = Query(min_length=1),
    file: UploadFile = File(...),
):
    entry = _campaign_bestiary_entry(id)
    if entry is None:
        raise _not_found("Campaign bestiary entry was not found")
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    suffix = ALLOWED_PORTRAIT_CONTENT_TYPES.get(content_type)
    if not suffix:
        raise _bad_request("Portrait must be a PNG, JPEG, WEBP, or GIF image.")
    data = await file.read()
    if not data:
        raise _bad_request("Portrait image was empty.")
    if len(data) > 12 * 1024 * 1024:
        raise _bad_request("Portrait image is too large; keep it under 12 MB.")

    relative_path = (
        Path("media")
        / private_campaign_data_service.campaign_id()
        / "portraits"
        / "Bestiary"
        / "manual"
        / _bestiary_portrait_filename(entry.get("name"), id, suffix)
    )
    target = private_campaign_data_service.private_root() / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    updated = _update_campaign_bestiary_entry(
        id,
        {
            "portrait": relative_path.as_posix(),
            "image_status": "local",
            "image_source": "manual upload",
        },
    )
    if updated is None:
        raise _not_found("Campaign bestiary entry was not found")
    return {"entry": _campaign_bestiary_entry(id)}


@router.get("/import-runs")
async def list_import_runs():
    runs = private_import_audit_service.list_import_runs()
    return {"items": runs, "total": len(runs)}


@router.post("/import-runs")
async def create_import_run(payload: ImportRunCreateRequest):
    try:
        run = private_import_audit_service.create_import_run(
            title=payload.title,
            map_id=payload.map_id,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    return {"run": run}


@router.get("/import-run")
async def get_import_run(run_id: str = Query(min_length=1)):
    run = private_import_audit_service.get_import_run(run_id)
    if run is None:
        raise _not_found("Import run was not found")
    return {"run": run}


@router.get("/import-room-drafts")
async def list_import_room_drafts(
    run_id: str = Query(min_length=1),
    review_status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
):
    payload = private_import_audit_service.room_drafts(
        run_id,
        review_status=review_status,
        q=q,
    )
    if payload is None:
        raise _not_found("Import run room drafts were not found")
    return payload


@router.patch("/import-room-draft")
async def update_import_room_draft(
    payload: ImportRoomDraftUpdate,
    run_id: str = Query(min_length=1),
    draft_id: str = Query(min_length=1),
):
    try:
        draft = private_import_audit_service.update_room_draft(
            run_id,
            draft_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if draft is None:
        raise _not_found("Import room draft was not found")
    return {"draft": draft}


@router.get("/import-audit-summary")
async def get_import_audit_summary(run_id: str = Query(min_length=1)):
    summary = private_import_audit_service.audit_summary(run_id)
    if summary is None:
        raise _not_found("Import audit summary was not found")
    return summary


@router.post("/import-promote-rooms")
async def promote_import_rooms(run_id: str = Query(min_length=1)):
    result = private_import_audit_service.promote_reviewed_rooms(run_id)
    if result is None:
        raise _not_found("Import room drafts were not found")
    return result


@router.get("/image-intake-runs")
async def list_image_intake_runs():
    runs = private_image_intake_service.list_image_runs()
    return {"items": runs, "total": len(runs)}


@router.post("/image-intake-runs")
async def create_image_intake_run(payload: ImageIntakeCreateRequest):
    try:
        run = private_image_intake_service.create_image_intake_run(
            source_id=payload.source_id,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    return {"run": run}


@router.get("/image-candidates")
async def list_image_candidates(
    source_id: Optional[str] = Query(default=None),
    review_status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=300, ge=1, le=1000),
):
    return private_image_intake_service.image_candidates(
        source_id=source_id,
        review_status=review_status,
        category=category,
        q=q,
        limit=limit,
    )


@router.patch("/image-candidate")
async def update_image_candidate(
    payload: ImageCandidateUpdate,
    image_id: str = Query(min_length=1),
):
    try:
        item = private_image_intake_service.update_image_candidate(
            image_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if item is None:
        raise _not_found("Image candidate was not found")
    return {"image": item}


@router.get("/image-audit")
async def get_image_audit():
    return private_image_intake_service.image_audit()


@router.post("/image-promote")
async def promote_images():
    return private_image_intake_service.promote_confirmed_images()


@router.get("/private-index/status")
async def get_private_index_status():
    return private_index_service.status()


@router.post("/private-index/rebuild")
async def rebuild_private_indexes():
    reference_corpus_service.ensure_corpus_structure()
    return {"manifest": private_index_service.build_all()}


@router.get("/private-index/audit")
async def get_private_index_audit():
    return private_index_service.audit()


@router.get("/private-index/dependencies")
async def get_private_index_dependencies(
    unresolved_only: bool = Query(default=False),
):
    if unresolved_only:
        items = private_index_service.unresolved_dependencies()
        return {"items": items, "total": len(items)}
    payload = private_index_service.dependency_audit()
    return {
        "items": payload.get("items") or [],
        "summary": payload.get("summary") or {},
        "updated_at": payload.get("updated_at"),
    }


@router.patch("/private-index/dependency")
async def update_private_index_dependency(
    payload: DependencyReviewUpdate,
    dependency_id: str = Query(min_length=1),
):
    try:
        item = private_index_service.update_dependency(
            dependency_id,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if item is None:
        raise _not_found("Dependency was not found")
    return {"dependency": item}


@router.get("/reference-corpus/status")
async def get_reference_corpus_status():
    return reference_corpus_service.ensure_corpus_structure()


@router.post("/reference-corpus/normalize")
async def normalize_reference_corpus():
    return reference_corpus_service.normalize_local_corpus()


@router.get("/reference-corpus/search")
async def search_reference_corpus(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    try:
        return {
            "items": reference_corpus_service.search(
                q=q or "",
                category=category,
                limit=limit,
            )
        }
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc


@router.post("/private-index/mirror-rag")
async def mirror_private_index_to_search_db(db: AsyncSession = Depends(get_db)):
    status = private_index_service.status()
    rag_file = next(
        (item for item in status.get("files") or [] if item.get("name") == "rag-documents.jsonl"),
        None,
    )
    if rag_file is None:
        raise _bad_request("Build private indexes before mirroring RAG documents.")
    rag_path = private_campaign_data_service.private_root() / str(rag_file.get("path") or "")
    imported = 0
    for line in rag_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        await ingestion_service.ingest_document(
            db,
            title=str(row.get("title") or row.get("external_id") or "Private Index Document"),
            kind=str(row.get("kind") or "campaign_index"),
            content=str(row.get("content") or ""),
            summary=None,
            source_name="private-local-index",
            url=f"private-index:{row.get('external_id')}",
            dedupe_on_url=True,
            source_class="private_local",
            privacy_scope="private_local",
            review_status="approved",
            visibility_scope="gm_only",
            rag_eligible=True,
            train_eligible=False,
        )
        imported += 1
    return {
        "status": "mirrored",
        "message": f"Mirrored {imported} private-local RAG documents into the search database.",
        "rag_documents_path": rag_file.get("path"),
        "imported": imported,
    }


def _tts_provider() -> str:
    return str(settings.tts_provider or "browser").strip().casefold()


def _piper_command(output_path: Path) -> list[str]:
    binary = str(settings.piper_binary_path or "piper").strip() or "piper"
    voice_path = str(settings.piper_voice_path or "").strip()
    if not voice_path:
        raise RuntimeError("PIPER_VOICE_PATH is not configured")
    model = Path(voice_path).expanduser()
    if not model.exists():
        raise RuntimeError(f"Piper voice model was not found: {model}")

    command = [
        binary,
        "--model",
        str(model),
        "--output_file",
        str(output_path),
    ]
    if settings.piper_speaker_id is not None:
        command.extend(["--speaker", str(settings.piper_speaker_id)])
    if settings.piper_length_scale is not None:
        command.extend(["--length_scale", str(settings.piper_length_scale)])
    if settings.piper_noise_scale is not None:
        command.extend(["--noise_scale", str(settings.piper_noise_scale)])
    if settings.piper_noise_w is not None:
        command.extend(["--noise_w", str(settings.piper_noise_w)])
    return command


def _synthesize_with_piper(text: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="dma-piper-") as temp_dir:
        output_path = Path(temp_dir) / "speech.wav"
        command = _piper_command(output_path)
        try:
            result = subprocess.run(
                command,
                input=text,
                text=True,
                capture_output=True,
                timeout=45,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Piper binary was not found: {settings.piper_binary_path or 'piper'}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Piper synthesis timed out") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Piper failed").strip()
            raise RuntimeError(detail[-500:])
        if not output_path.exists():
            raise RuntimeError("Piper did not create an audio file")
        return output_path.read_bytes()


@router.get("/tts/status")
async def get_tts_status():
    provider = _tts_provider()
    piper_ready = False
    piper_detail = "Piper is not selected."
    if provider == "piper":
        try:
            _piper_command(Path("dma-tts-check.wav"))
            piper_ready = True
            piper_detail = "Piper appears configured."
        except RuntimeError as exc:
            piper_detail = str(exc)
    return {
        "provider": provider,
        "browser_available": True,
        "piper_ready": piper_ready,
        "piper_detail": piper_detail,
    }


@router.post("/tts/synthesize")
async def synthesize_tts(request: LiveTTSRequest):
    provider = _tts_provider()
    if provider != "piper":
        raise _bad_request("Server TTS is not enabled; use browser speech synthesis")
    text = re.sub(r"\s+", " ", request.text).strip()
    if not text:
        raise _bad_request("No text was provided for synthesis")
    try:
        audio = _synthesize_with_piper(text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )


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
    name: Optional[str] = Query(default=None),
    level: Optional[int] = Query(default=None),
    source: Optional[str] = Query(default=None),
    traits: Optional[str] = Query(default=None),
):
    try:
        document = aon_creature_service.get_creature(
            creature_id,
            refresh=refresh,
            fallback_name=name,
            fallback_level=level,
            fallback_source=source,
            fallback_traits=[
                trait.strip()
                for trait in (traits or "").split(",")
                if trait.strip()
            ],
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
            "image_url": document.image_url,
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
