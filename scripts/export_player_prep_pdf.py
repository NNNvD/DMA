#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "obsidian-abomination-vaults-vault"
    / "Notes"
    / "14 Gauntlight Arrival Player Prep.md"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "obsidian-abomination-vaults-vault" / "Exports" / "Handouts"
)
DEFAULT_CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def _strip_frontmatter(markdown: str) -> str:
    if markdown.startswith("---"):
        end = markdown.find("\n---", 3)
        if end != -1:
            return markdown[end + 4 :].lstrip()
    return markdown


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "player-session-prep"


def _parse_markdown(markdown: str) -> tuple[str, list[tuple[str, list[str]]]]:
    markdown = _strip_frontmatter(markdown)
    title = "Player Session Prep"
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            if current_heading is not None:
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip()
            current_lines = []
            continue
        if current_heading is not None:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, current_lines))

    return title, sections


def _render_inline(text: str) -> str:
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return html.escape(text)


def _render_blocks(lines: list[str], *, highlight_first_paragraph: bool) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    highlighted = False

    def flush_paragraph() -> None:
        nonlocal highlighted
        if not paragraph:
            return
        text = " ".join(part.strip() for part in paragraph if part.strip())
        if text:
            class_name = (
                "arrival" if highlight_first_paragraph and not highlighted else None
            )
            class_attr = f' class="{class_name}"' if class_name else ""
            blocks.append(f"<p{class_attr}>{_render_inline(text)}</p>")
            highlighted = highlighted or bool(class_name)
        paragraph.clear()

    def flush_list() -> None:
        if not list_items:
            return
        rendered_items = "\n".join(
            f"            <li>{_render_inline(item)}</li>" for item in list_items
        )
        blocks.append(f"          <ul>\n{rendered_items}\n          </ul>")
        list_items.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(stripped[2:].strip())
            continue
        flush_list()
        paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def build_html(markdown: str) -> str:
    title, sections = _parse_markdown(markdown)
    section_html: list[str] = []
    numerals = ["I", "II", "III", "IV", "V", "VI"]

    for index, (heading, lines) in enumerate(sections):
        numeral = numerals[index] if index < len(numerals) else str(index + 1)
        highlight = "gauntlight looks" in heading.lower()
        body = _render_blocks(lines, highlight_first_paragraph=highlight)
        section_html.append(
            f"""        <section>
          <h2><span class="mark">{numeral}</span>{html.escape(heading)}</h2>
{body}
        </section>"""
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    @page {{
      size: A4;
      margin: 0;
    }}

    :root {{
      --ink: #2d2118;
      --muted-ink: #5d4a39;
      --ember: #8f3d24;
      --moss: #536646;
      --gold: #b88a43;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      width: 210mm;
      color: var(--ink);
      font-family: "Avenir Next", "Trebuchet MS", sans-serif;
      font-size: 10.25pt;
      line-height: 1.42;
      background:
        radial-gradient(circle at 18% 14%, rgba(255, 255, 255, 0.75), transparent 28%),
        radial-gradient(circle at 85% 18%, rgba(184, 138, 67, 0.16), transparent 24%),
        linear-gradient(135deg, #efe0bd 0%, #f8efd9 46%, #e7d1a8 100%);
    }}

    .page {{
      width: 210mm;
      height: 297mm;
      padding: 10mm;
      position: relative;
    }}

    .sheet {{
      height: 277mm;
      padding: 11mm 12mm 10mm;
      position: relative;
      overflow: hidden;
      border: 2px solid rgba(95, 67, 36, 0.34);
      border-radius: 18px;
      background:
        linear-gradient(rgba(255, 248, 232, 0.92), rgba(247, 235, 207, 0.92)),
        repeating-linear-gradient(98deg, rgba(92, 68, 43, 0.035) 0 2px, transparent 2px 9px);
      box-shadow:
        0 18px 42px rgba(64, 42, 24, 0.22),
        inset 0 0 44px rgba(126, 88, 42, 0.17);
    }}

    .sheet::before,
    .sheet::after {{
      content: "";
      position: absolute;
      pointer-events: none;
      border: 1px solid rgba(143, 61, 36, 0.28);
      border-radius: 12px;
    }}

    .sheet::before {{
      inset: 7mm;
    }}

    .sheet::after {{
      inset: 10mm;
      border-color: rgba(184, 138, 67, 0.22);
    }}

    header,
    main,
    footer {{
      position: relative;
      z-index: 1;
    }}

    header {{
      margin-bottom: 6mm;
      text-align: center;
    }}

    .eyebrow {{
      margin: 0 0 2mm;
      color: var(--moss);
      font-size: 9pt;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0;
      color: #24170f;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 27pt;
      line-height: 1;
      letter-spacing: 0.01em;
    }}

    .subtitle {{
      max-width: 150mm;
      margin: 3mm auto 0;
      color: var(--muted-ink);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 11.5pt;
      font-style: italic;
    }}

    .divider {{
      display: flex;
      align-items: center;
      gap: 4mm;
      margin: 4mm auto 0;
      max-width: 120mm;
      color: var(--gold);
      font-size: 14pt;
    }}

    .divider::before,
    .divider::after {{
      content: "";
      flex: 1;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(143, 61, 36, 0.58), transparent);
    }}

    section {{
      margin: 0 0 4.2mm;
      padding: 0 0 0 7mm;
      border-left: 3px solid rgba(143, 61, 36, 0.36);
    }}

    h2 {{
      margin: 0 0 1.8mm -7mm;
      color: var(--ember);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 14.5pt;
      line-height: 1.1;
    }}

    h2 .mark {{
      display: inline-grid;
      place-items: center;
      width: 7mm;
      height: 7mm;
      margin-right: 1.5mm;
      border: 1px solid rgba(143, 61, 36, 0.42);
      border-radius: 999px;
      color: var(--moss);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 10pt;
      background: rgba(255, 248, 232, 0.7);
    }}

    p {{
      margin: 0 0 2.2mm;
    }}

    .arrival {{
      margin: 3mm 0 4mm;
      padding: 4mm 5mm;
      border: 1px solid rgba(83, 102, 70, 0.32);
      border-radius: 14px;
      color: #34261c;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 11.2pt;
      background:
        linear-gradient(90deg, rgba(83, 102, 70, 0.12), rgba(255, 248, 232, 0.78)),
        radial-gradient(circle at top left, rgba(184, 138, 67, 0.22), transparent 42%);
    }}

    ul {{
      margin: 0;
      padding-left: 0;
      list-style: none;
    }}

    li {{
      position: relative;
      margin: 0 0 1.8mm;
      padding-left: 7mm;
    }}

    li::before {{
      content: "\\2726";
      position: absolute;
      left: 0;
      top: 0;
      color: var(--gold);
      font-size: 10pt;
      line-height: 1.6;
    }}

    .closing {{
      margin-top: 5mm;
      padding: 3mm 5mm;
      border-top: 1px solid rgba(143, 61, 36, 0.22);
      border-bottom: 1px solid rgba(143, 61, 36, 0.22);
      color: var(--muted-ink);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 10.8pt;
      font-style: italic;
      text-align: center;
    }}

    footer {{
      margin-top: 5mm;
      color: rgba(45, 33, 24, 0.56);
      font-size: 8.5pt;
      text-align: center;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
  </style>
</head>
<body>
  <div class="page">
    <article class="sheet">
      <header>
        <p class="eyebrow">Player Handout</p>
        <h1>{html.escape(title)}</h1>
        <p class="subtitle">A one-page player-safe session prep handout.</p>
        <div class="divider" aria-hidden="true">&#10022;</div>
      </header>

      <main>
{chr(10).join(section_html)}
        <p class="closing">The fog thins for a moment. The next choice belongs to the party.</p>
      </main>

      <footer>DMA Player Session Prep Export</footer>
    </article>
  </div>
</body>
</html>
"""


def _find_chrome(explicit_path: str | None) -> str:
    candidates = [explicit_path] if explicit_path else DEFAULT_CHROME_PATHS
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError(
        "Could not find Chrome/Chromium. Install Google Chrome or pass --chrome-path."
    )


def export_pdf(html_path: Path, pdf_path: Path, *, chrome_path: str | None) -> None:
    chrome = _find_chrome(chrome_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export a player-safe session prep Markdown note as a styled one-page PDF."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Markdown source note. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Folder for HTML/PDF output. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--basename",
        default=None,
        help="Output basename without extension. Defaults to a slug from the title.",
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Write styled HTML but skip PDF rendering.",
    )
    parser.add_argument(
        "--chrome-path",
        default=None,
        help="Optional explicit Chrome/Chromium executable path.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    markdown_path = args.input
    if not markdown_path.exists():
        parser.error(f"Input Markdown file does not exist: {markdown_path}")

    markdown = markdown_path.read_text(encoding="utf-8")
    title, _sections = _parse_markdown(markdown)
    basename = args.basename or _slugify(title)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{basename}.html"
    pdf_path = output_dir / f"{basename}.pdf"
    html_path.write_text(build_html(markdown), encoding="utf-8")

    result = {
        "input": str(markdown_path),
        "html": str(html_path),
        "pdf": None if args.html_only else str(pdf_path),
    }

    if not args.html_only:
        export_pdf(html_path, pdf_path, chrome_path=args.chrome_path)

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
