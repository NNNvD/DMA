from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import json
import re
import time
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class AonRuleLink:
    rule_id: int
    title: str
    url: str


@dataclass(frozen=True)
class AonRuleDocument:
    rule_id: int
    title: str
    source_url: str
    source_name: str
    content: str
    summary: str
    ancestors: list[str]
    source_citation: str
    fetched_at: str


class AonRulesFetchService:
    base_url = "https://2e.aonprd.com"
    rules_index_url = f"{base_url}/Rules.aspx"
    source_name = "Archives of Nethys Rules Index"
    user_agent = "DMA AoN Rules Fetcher/1.0"

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = (
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.default_root = (
            self.project_root / "assets" / "imports" / "misc" / "aon-rules"
        )

    def fetch_rules(
        self,
        *,
        root_path: Optional[str] = None,
        ids: Optional[set[int]] = None,
        limit: Optional[int] = None,
        overwrite: bool = True,
        pause_seconds: float = 0.0,
        timeout_seconds: float = 20.0,
    ) -> dict[str, Any]:
        root = self._resolve_root(root_path)
        raw_dir = root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        index_html = self._fetch_text(
            self.rules_index_url, timeout_seconds=timeout_seconds
        )
        links = self.discover_rule_links(index_html)
        if ids:
            links = [link for link in links if link.rule_id in ids]
        if limit is not None:
            links = links[: max(limit, 0)]

        items: list[dict[str, Any]] = []
        files_written = 0
        files_updated = 0
        files_skipped = 0

        for index, link in enumerate(links):
            output_path = raw_dir / self._filename_for(link)
            existed_before = output_path.exists()
            if output_path.exists() and not overwrite:
                files_skipped += 1
                existing = json.loads(output_path.read_text(encoding="utf-8"))
                items.append(
                    {
                        "title": str(existing.get("title") or link.title),
                        "local_path": self._display_path(output_path),
                        "source_url": str(existing.get("source_url") or link.url),
                        "notes": "Fetched from Archives of Nethys for retrieval-only rules lookup.",
                    }
                )
                continue

            page_html = self._fetch_text(link.url, timeout_seconds=timeout_seconds)
            document = self.parse_rule_page(
                page_html,
                source_url=link.url,
                rule_id=link.rule_id,
                fallback_title=link.title,
            )
            payload = {
                **asdict(document),
            }
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            items.append(
                {
                    "title": document.title,
                    "local_path": self._display_path(output_path),
                    "source_url": document.source_url,
                    "notes": "Fetched from Archives of Nethys for retrieval-only rules lookup.",
                }
            )
            if existed_before:
                files_updated += 1
            else:
                files_written += 1

            if pause_seconds > 0 and index < len(links) - 1:
                time.sleep(pause_seconds)

        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "generated_at": self._now_iso(),
                    "source_name": self.source_name,
                    "items": items,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        return {
            "root_path": str(root),
            "rules_discovered": len(self.discover_rule_links(index_html)),
            "rules_selected": len(links),
            "files_written": files_written,
            "files_updated": files_updated,
            "files_skipped": files_skipped,
            "manifest_path": str(manifest_path),
        }

    def discover_rule_links(self, index_html: str) -> list[AonRuleLink]:
        main_fragment = self._extract_main_fragment(index_html)
        seen_ids: set[int] = set()
        links: list[AonRuleLink] = []
        for href, title_html in re.findall(
            r'href="(/Rules\.aspx\?ID=\d+)"[^>]*>(.*?)</a>',
            main_fragment,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            query = parse_qs(urlparse(href).query)
            try:
                rule_id = int(query["ID"][0])
            except (KeyError, TypeError, ValueError):
                continue
            if rule_id in seen_ids:
                continue
            title = self._html_to_text(title_html)
            if not title:
                continue
            seen_ids.add(rule_id)
            links.append(
                AonRuleLink(
                    rule_id=rule_id,
                    title=title,
                    url=urljoin(self.base_url, href),
                )
            )
        links.sort(key=lambda item: item.rule_id)
        return links

    def parse_rule_page(
        self,
        page_html: str,
        *,
        source_url: str,
        rule_id: int,
        fallback_title: str,
    ) -> AonRuleDocument:
        title = self._extract_rule_title(page_html) or fallback_title
        ancestors = self._extract_ancestors(page_html)
        source_citation = self._extract_source_citation(page_html)
        body_text = self._extract_rule_body_text(page_html)
        if not body_text:
            body_text = self._extract_meta_description(page_html)
        if not body_text:
            raise ValueError(f"Could not extract rule text from {source_url}")

        content_parts: list[str] = []
        if ancestors:
            content_parts.append(f"Section Path: {' > '.join(ancestors)}")
        if source_citation:
            content_parts.append(f"Source: {source_citation}")
        content_parts.append(body_text)
        content = "\n\n".join(part for part in content_parts if part).strip()

        return AonRuleDocument(
            rule_id=rule_id,
            title=title,
            source_url=source_url,
            source_name=self.source_name,
            content=content,
            summary=self._build_summary(body_text),
            ancestors=ancestors,
            source_citation=source_citation,
            fetched_at=self._now_iso(),
        )

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
        if end < 0:
            return fragment
        return fragment[:end]

    def _extract_rule_title(self, html_text: str) -> str:
        match = re.search(
            r'<h1 class="title">\s*(.*?)\s*</h1>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return ""
        return self._html_to_text(match.group(1))

    def _extract_ancestors(self, html_text: str) -> list[str]:
        match = re.search(
            r'<div class="rule-ancestors[^"]*">\s*(.*?)\s*</div>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return []
        block = match.group(1)
        ancestors: list[str] = []
        for ancestor_html in re.findall(
            r'<span class="rule-ancestor">\s*(.*?)\s*</span>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            label = self._html_to_text(ancestor_html)
            if label:
                ancestors.append(label)
        return ancestors

    def _extract_source_citation(self, html_text: str) -> str:
        match = re.search(
            r'<div class="sources">\s*(.*?)\s*</div>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return ""
        text = self._html_to_text(match.group(1))
        return re.sub(r"^Source\s*", "", text).strip()

    def _extract_rule_body_text(self, html_text: str) -> str:
        start = html_text.find('<div class="rule">')
        if start < 0:
            return ""
        sibling_markers = (
            '<div class="sibling-navigation hide-on-print">',
            '<div class="clear">',
            '<div class="footer"',
        )
        end_candidates = [
            html_text.find(marker, start + len('<div class="rule">'))
            for marker in sibling_markers
        ]
        end_candidates = [candidate for candidate in end_candidates if candidate >= 0]
        end = min(end_candidates) if end_candidates else len(html_text)
        block = html_text[start:end]
        block = re.sub(
            r'<h1 class="title">\s*.*?\s*</h1>',
            "",
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        block = re.sub(
            r'<div class="sources">\s*.*?\s*</div>',
            "",
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        block = re.sub(
            r'^<div class="rule">\s*',
            "",
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return self._html_to_text(block)

    def _extract_meta_description(self, html_text: str) -> str:
        match = re.search(
            r'<meta name="description" content="(.*?)"\s*/?>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return ""
        return unescape(match.group(1)).strip()

    def _build_summary(self, body_text: str, max_chars: int = 400) -> str:
        for paragraph in body_text.split("\n\n"):
            cleaned = paragraph.strip()
            if cleaned:
                if len(cleaned) <= max_chars:
                    return cleaned
                return cleaned[: max_chars - 3].rstrip() + "..."
        return ""

    def _html_to_text(self, html_fragment: str) -> str:
        fragment = re.sub(
            r"<(script|style)\b[^>]*>.*?</\1>",
            "",
            html_fragment,
            flags=re.IGNORECASE | re.DOTALL,
        )
        fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
        fragment = re.sub(r"<li\b[^>]*>", "- ", fragment, flags=re.IGNORECASE)
        fragment = re.sub(
            r"</(div|p|h1|h2|h3|h4|h5|h6|li|ul|ol|blockquote|section|table|tr)>",
            "\n\n",
            fragment,
            flags=re.IGNORECASE,
        )
        fragment = re.sub(r"<[^>]+>", "", fragment)
        text = unescape(fragment).replace("\r", "")

        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        cleaned_lines: list[str] = []
        previous_blank = True
        for line in lines:
            if line:
                cleaned_lines.append(line)
                previous_blank = False
            elif not previous_blank:
                cleaned_lines.append("")
                previous_blank = True
        return "\n".join(cleaned_lines).strip()

    def _filename_for(self, link: AonRuleLink) -> str:
        return f"{link.rule_id:04d}-{self._slugify(link.title)}.json"

    def _slugify(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
        return normalized or "rule"

    def _resolve_root(self, root_path: Optional[str]) -> Path:
        if not root_path:
            return self.default_root
        return Path(root_path).expanduser().resolve()

    def _display_path(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.project_root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()


aon_rules_fetch_service = AonRulesFetchService()
