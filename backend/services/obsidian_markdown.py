from __future__ import annotations

from pathlib import Path
import re
from typing import Any
import yaml


WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")
UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*]+')


def split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content:
        return {}, ""

    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized

    lines = normalized.split("\n")
    frontmatter_lines: list[str] = []
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in {"---", "..."}:
            end_index = index
            break
        frontmatter_lines.append(line)

    if end_index is None:
        return {}, normalized

    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    parsed = _parse_frontmatter_yaml(frontmatter_lines)
    if parsed is None:
        parsed = _parse_frontmatter_lines(frontmatter_lines)
    return parsed, body


def extract_tags(frontmatter: dict[str, Any]) -> list[str]:
    for key, value in frontmatter.items():
        if key.strip().lower() != "tags":
            continue
        if isinstance(value, list):
            return _normalize_tags(value)
        if isinstance(value, str):
            return _normalize_tags(re.split(r"\s*[,;]\s*", value))
    return []


def replace_wikilinks(text: str) -> str:
    def _replacement(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        alias = (match.group(2) or "").strip()
        if alias:
            return alias

        cleaned_target = target.split("#", 1)[0].strip()
        if cleaned_target.lower().endswith(".md"):
            cleaned_target = cleaned_target[:-3]
        cleaned_target = cleaned_target.rsplit("/", 1)[-1]
        return cleaned_target

    return WIKILINK_RE.sub(_replacement, text)


def build_frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in _flatten_frontmatter_metadata(metadata).items():
        if value is None or value == [] or value == {}:
            continue
        lines.append(f"{key}: {_yaml_inline_value(value)}")
    lines.append("---")
    return "\n".join(lines)


def safe_note_stem(value: str) -> str:
    cleaned = UNSAFE_FILENAME_RE.sub(" ", value).strip().rstrip(".")
    collapsed = re.sub(r"\s+", " ", cleaned)
    return collapsed or "Untitled"


def wikilink_for_path(relative_path: str | Path, *, alias: str | None = None) -> str:
    target = Path(relative_path).with_suffix("").as_posix()
    if alias and alias.strip():
        return f"[[{target}|{alias.strip()}]]"
    return f"[[{target}]]"


def _parse_frontmatter_lines(lines: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        if ":" not in stripped:
            index += 1
            continue

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value:
            data[key] = _parse_scalar(value)
            index += 1
            continue

        items: list[Any] = []
        look_ahead = index + 1
        while look_ahead < len(lines):
            nested = lines[look_ahead]
            nested_stripped = nested.strip()
            if not nested_stripped:
                look_ahead += 1
                continue
            if len(nested) - len(nested.lstrip(" ")) < 2:
                break
            if nested_stripped.startswith("- "):
                items.append(_parse_scalar(nested_stripped[2:].strip()))
            look_ahead += 1
        data[key] = items
        index = look_ahead
    return data


def _parse_frontmatter_yaml(lines: list[str]) -> dict[str, Any] | None:
    raw = "\n".join(lines).strip()
    if not raw:
        return {}
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if not stripped:
        return ""
    if stripped.startswith("[") and stripped.endswith("]"):
        parts = [part.strip() for part in stripped[1:-1].split(",") if part.strip()]
        return [_parse_scalar(part) for part in parts]
    if stripped.lower() in {"true", "false"}:
        return stripped.lower() == "true"
    if stripped.isdigit():
        return int(stripped)
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _normalize_tags(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip().lstrip("#")
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _flatten_frontmatter_metadata(
    metadata: dict[str, Any], *, prefix: str = ""
) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None or value == [] or value == {}:
            continue
        normalized_key = f"{prefix}{key}" if not prefix else f"{prefix}_{key}"
        if isinstance(value, dict):
            flattened.update(
                _flatten_frontmatter_metadata(value, prefix=normalized_key)
            )
            continue
        if isinstance(value, list) and any(
            isinstance(item, (dict, list)) for item in value
        ):
            for index, item in enumerate(value, start=1):
                item_key = f"{normalized_key}_{index:02d}"
                if isinstance(item, dict):
                    flattened.update(
                        _flatten_frontmatter_metadata(item, prefix=item_key)
                    )
                elif isinstance(item, list):
                    flattened[item_key] = item
                else:
                    flattened[item_key] = item
            continue
        flattened[normalized_key] = value
    return flattened


def _yaml_inline_value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_yaml_scalar(item) for item in value) + "]"
    return _yaml_scalar(value)


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\n", " ").strip()
    return f'"{text}"'
