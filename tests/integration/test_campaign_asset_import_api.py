import asyncio
import json
from pathlib import Path
import subprocess
from xml.sax.saxutils import escape
import zipfile

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


CAMPAIGN_NOTE = """
## Location: Greyhaven
Category: city

## NPC: Captain Mira
Location: Greyhaven
Role: harbor master
Relationships: ally -> Talia Stormborn
"""

PC_SHEET = """
Name: Talia Stormborn
Class: Ranger
Level: 4
Location: Greyhaven
Factions: Lantern Guild
Relationships: contact -> Captain Mira
"""

SESSION_LOG = """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=19
Summary: The harbor calms after the attack.
Timeline Position: session-12

## Changelog
- Captain Mira owes Talia a favor.
"""

REFERENCE_GUIDE = """
# Beginner Spell Notes

Fireball is strongest when enemies are clustered together.
This is player strategy advice rather than primary rules text.
"""

RULE_PAYLOAD = {
    "rule_id": 97,
    "title": "Law and Chaos",
    "source_url": "https://2e.aonprd.com/Rules.aspx?ID=97",
    "source_name": "Archives of Nethys Rules Index",
    "summary": "Lawful characters value stability and predictability over flexibility.",
    "ancestors": [
        "Core Rulebook",
        "Chapter 1: Introduction",
        "Character Creation",
        "Alignment",
    ],
    "source_citation": "Core Rulebook pg. 29",
    "content": (
        "Section Path: Core Rulebook > Chapter 1: Introduction > Character Creation > Alignment\n\n"
        "Source: Core Rulebook pg. 29\n\n"
        "Your character has a lawful alignment if they value consistency, stability, "
        "and predictability over flexibility. Chaotic characters value spontaneity."
    ),
}


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _write_json(root: Path, relative_path: str, payload: dict) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _column_name(index: int) -> str:
    letters: list[str] = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _write_xlsx(root: Path, relative_path: str, rows: list[list[str]]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)

    row_xml: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(row_xml)}</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Gear" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    with zipfile.ZipFile(path, "w") as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", root_rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", worksheet_xml)


def _write_docx(root: Path, relative_path: str, paragraphs: list[str]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)

    paragraph_xml = "".join(
        (
            '<w:p><w:r><w:t xml:space="preserve">'
            f"{escape(paragraph)}"
            "</w:t></w:r></w:p>"
        )
        for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraph_xml}</w:body>"
        "</w:document>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    document_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )

    with zipfile.ZipFile(path, "w") as document:
        document.writestr("[Content_Types].xml", content_types_xml)
        document.writestr("_rels/.rels", root_rels_xml)
        document.writestr("word/document.xml", document_xml)
        document.writestr("word/_rels/document.xml.rels", document_rels_xml)


def test_dropzone_preview_resolves_cross_file_references(tmp_path: Path):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write(tmp_path, "campaign-notes/greyhaven.md", CAMPAIGN_NOTE)
        _write(tmp_path, "pathbuilder/talia.txt", PC_SHEET)
        _write(tmp_path, "session-logs/session-12-harbor.md", SESSION_LOG)

        response = client.get(
            "/api/campaign/import/dropzone",
            params={"root_path": str(tmp_path)},
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["dry_run"] is True
        assert payload["summary"]["files_previewed"] == 3
        assert payload["summary"]["parsed_entities"] == 3
        assert payload["summary"]["parsed_sheet_versions"] == 1
        assert payload["summary"]["parsed_changelog_entries"] == 1

        note_preview = next(
            item for item in payload["files"] if item["category"] == "campaign-notes"
        )
        assert note_preview["warnings"] == []
        assert note_preview["preview"]["entity_count"] == 2

        pc_preview = next(
            item for item in payload["files"] if item["category"] == "pathbuilder"
        )
        assert pc_preview["import_format"] == "text"
        assert pc_preview["preview"]["name"] == "Talia Stormborn"
    finally:
        asyncio.run(engine.dispose())


def test_batch_import_is_repeatable_and_exposes_dossier_and_session_history(
    tmp_path: Path,
):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write(tmp_path, "campaign-notes/greyhaven.md", CAMPAIGN_NOTE)
        _write(tmp_path, "pathbuilder/talia.txt", PC_SHEET)
        _write(tmp_path, "session-logs/session-12-harbor.md", SESSION_LOG)

        first = client.post(
            "/api/campaign/import/batch",
            json={"root_path": str(tmp_path)},
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["summary"]["files_imported"] == 3
        assert first_payload["summary"]["created_sheet_versions"] == 1

        second = client.post(
            "/api/campaign/import/batch",
            json={"root_path": str(tmp_path)},
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["summary"]["files_imported"] == 3
        assert second_payload["summary"]["created_sheet_versions"] == 0
        assert second_payload["summary"]["reused_sheet_versions"] == 1

        note_docs = client.get("/api/documents", params={"kind": "campaign_note"})
        pc_docs = client.get("/api/documents", params={"kind": "pc_sheet"})
        session_docs = client.get("/api/documents", params={"kind": "session_log"})
        assert note_docs.json()["total"] == 1
        assert pc_docs.json()["total"] == 1
        assert session_docs.json()["total"] == 1

        pcs = client.get(
            "/api/campaign/entities",
            params={"entity_type": "pc", "q": "Talia Stormborn"},
        )
        assert pcs.status_code == 200
        pc = pcs.json()["items"][0]
        assert pc["latest_sheet_version"]["version_number"] == 1

        dossier = client.get(f"/api/campaign/pcs/{pc['id']}/dossier")
        assert dossier.status_code == 200
        dossier_payload = dossier.json()
        assert dossier_payload["pc"]["name"] == "Talia Stormborn"
        assert dossier_payload["sheet_version_count"] == 1
        assert dossier_payload["factions"][0]["name"] == "Lantern Guild"
        assert "contact" in dossier_payload["relationship_groups"]

        history = client.get("/api/campaign/session-history")
        assert history.status_code == 200
        history_payload = history.json()
        assert history_payload["total"] == 1
        item = history_payload["items"][0]
        assert item["document"]["kind"] == "session_log"
        assert item["event"]["entity_type"] == "event"

        events = client.get("/api/campaign/entities", params={"entity_type": "event"})
        assert events.status_code == 200
        assert events.json()["total"] == 1
    finally:
        asyncio.run(engine.dispose())


def test_reference_guides_import_as_searchable_documents_without_affecting_rules(
    tmp_path: Path,
):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write(
            tmp_path,
            "misc/pf2e-reference/raw/beginner-spell-notes.md",
            REFERENCE_GUIDE,
        )
        _write_xlsx(
            tmp_path,
            "misc/pf2e-reference/raw/equipment-guide.xlsx",
            [
                ["Item", "Notes"],
                ["Cold Iron Sword", "Reliable backup weapon"],
                ["Healing Potion", "Emergency recovery"],
            ],
        )

        preview = client.get(
            "/api/campaign/import/dropzone",
            params={
                "root_path": str(tmp_path),
                "category": "reference-guides",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["summary"]["files_previewed"] == 2
        assert preview_payload["summary"]["parsed_documents"] == 2
        assert preview_payload["summary"]["parsed_spreadsheets"] == 1

        text_preview = next(
            item
            for item in preview_payload["files"]
            if item["path"] == "misc/pf2e-reference/raw/beginner-spell-notes.md"
        )
        assert text_preview["title"] == "Beginner Spell Notes"
        assert text_preview["import_format"] == "markdown"

        workbook_preview = next(
            item
            for item in preview_payload["files"]
            if item["path"] == "misc/pf2e-reference/raw/equipment-guide.xlsx"
        )
        assert workbook_preview["import_format"] == "xlsx"
        assert workbook_preview["preview"]["sheet_count"] == 1
        assert workbook_preview["preview"]["non_empty_row_count"] == 3

        first = client.post(
            "/api/campaign/import/batch",
            json={
                "root_path": str(tmp_path),
                "categories": ["reference-guides"],
            },
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["summary"]["files_imported"] == 2
        assert first_payload["summary"]["created_documents"] == 2
        assert first_payload["summary"]["updated_documents"] == 0

        second = client.post(
            "/api/campaign/import/batch",
            json={
                "root_path": str(tmp_path),
                "categories": ["guides"],
            },
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["summary"]["files_imported"] == 2
        assert second_payload["summary"]["created_documents"] == 0
        assert second_payload["summary"]["updated_documents"] == 2

        guide_docs = client.get("/api/documents", params={"kind": "guide"})
        assert guide_docs.status_code == 200
        assert guide_docs.json()["total"] == 2
        guide_items = guide_docs.json()["items"]
        assert all(
            item["source_class"] == "trainable_with_review" for item in guide_items
        )
        assert all(item["review_status"] == "pending" for item in guide_items)
        assert all(item["visibility_scope"] == "player_safe" for item in guide_items)

        search = client.get(
            "/api/documents/search",
            params={
                "q": "cold iron sword",
                "kind": "guide",
                "top_k": 3,
                "source_class": "trainable_with_review",
                "visibility_scope": "player_safe",
                "review_status": "pending",
                "rag_eligible": True,
            },
        )
        assert search.status_code == 200
        search_payload = search.json()
        assert search_payload["results"]
        assert search_payload["results"][0]["document"]["kind"] == "guide"
        assert search_payload["results"][0]["document"]["title"] == "Equipment Guide"
        assert (
            search_payload["results"][0]["document"]["source_class"]
            == "trainable_with_review"
        )

        strict_miss = client.post(
            "/api/documents/rules/query",
            json={"query": "What does this say about fireball?", "strict": True},
        )
        assert strict_miss.status_code == 200
        miss_payload = strict_miss.json()
        assert miss_payload["citations"] == []
        assert "couldn't find a confident answer" in miss_payload["answer"].lower()
    finally:
        asyncio.run(engine.dispose())


def test_local_reference_import_supports_docx_and_respects_visibility(
    tmp_path: Path,
):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write_docx(
            tmp_path,
            "misc/private-local/reference/raw/player/talingarde-common-knowledge.docx",
            [
                "Talingarde Common Knowledge",
                "Talingarde is an island kingdom ruled by House Darius.",
            ],
        )
        _write_xlsx(
            tmp_path,
            "misc/private-local/reference/raw/gm/rise-of-the-runelords/rounds.xlsx",
            [
                ["Encounter", "Rounds"],
                ["Glassworks", "5"],
                ["Seven's Sawmill", "7"],
            ],
        )

        preview = client.get(
            "/api/campaign/import/dropzone",
            params={
                "root_path": str(tmp_path),
                "category": "local-reference",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["summary"]["files_previewed"] == 2
        assert preview_payload["summary"]["parsed_documents"] == 2
        assert preview_payload["summary"]["parsed_spreadsheets"] == 1

        player_preview = next(
            item
            for item in preview_payload["files"]
            if item["path"]
            == "misc/private-local/reference/raw/player/talingarde-common-knowledge.docx"
        )
        assert player_preview["import_format"] == "docx"
        assert player_preview["title"] == "Talingarde Common Knowledge"

        imported = client.post(
            "/api/campaign/import/batch",
            json={
                "root_path": str(tmp_path),
                "categories": ["local-reference"],
            },
        )
        assert imported.status_code == 200
        payload = imported.json()
        assert payload["summary"]["files_imported"] == 2
        assert payload["summary"]["created_documents"] == 2

        reference_docs = client.get("/api/documents", params={"kind": "reference"})
        assert reference_docs.status_code == 200
        assert reference_docs.json()["total"] == 2

        player_search = client.get(
            "/api/documents/search",
            params={
                "q": "House Darius",
                "kind": "reference",
                "visibility_scope": "player_safe",
                "source_class": "private_local",
                "rag_eligible": True,
            },
        )
        assert player_search.status_code == 200
        player_results = player_search.json()["results"]
        assert len(player_results) == 1
        assert player_results[0]["document"]["title"] == "Talingarde Common Knowledge"
        assert player_results[0]["document"]["visibility_scope"] == "player_safe"

        gm_search = client.get(
            "/api/documents/search",
            params={
                "q": "Seven's Sawmill",
                "kind": "reference",
                "visibility_scope": "gm_only",
                "source_class": "private_local",
                "rag_eligible": True,
            },
        )
        assert gm_search.status_code == 200
        gm_results = gm_search.json()["results"]
        assert len(gm_results) == 1
        assert gm_results[0]["document"]["title"] == "Rounds"
        assert gm_results[0]["document"]["visibility_scope"] == "gm_only"
    finally:
        asyncio.run(engine.dispose())


def test_local_reference_import_supports_pdf_via_pdftotext(
    tmp_path: Path,
    monkeypatch,
):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    pdf_path = (
        tmp_path
        / "misc/private-local/reference/raw/player/abomination-vaults/players-guide.pdf"
    )
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.6 test pdf")

    def fake_run(cmd, check, capture_output, text):
        assert cmd[0] == "pdftotext"
        assert str(pdf_path) in cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=(
                "Abomination Vaults Player's Guide\n\n"
                "Otari stands on the Isle of Kortos.\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(
        "backend.services.campaign_asset_import_service.subprocess.run",
        fake_run,
    )

    try:
        preview = client.get(
            "/api/campaign/import/dropzone",
            params={
                "root_path": str(tmp_path),
                "category": "local-reference",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["summary"]["files_previewed"] == 1
        assert preview_payload["summary"]["parsed_pdfs"] == 1
        file_payload = preview_payload["files"][0]
        assert file_payload["import_format"] == "pdf"
        assert file_payload["title"] == "Abomination Vaults Player's Guide"

        imported = client.post(
            "/api/campaign/import/batch",
            json={
                "root_path": str(tmp_path),
                "categories": ["local-reference"],
            },
        )
        assert imported.status_code == 200
        imported_payload = imported.json()
        assert imported_payload["summary"]["files_imported"] == 1
        assert imported_payload["summary"]["parsed_pdfs"] == 1

        reference_docs = client.get("/api/documents", params={"kind": "reference"})
        assert reference_docs.status_code == 200
        items = reference_docs.json()["items"]
        assert len(items) == 1
        assert items[0]["title"] == "Abomination Vaults Player's Guide"
        assert items[0]["visibility_scope"] == "player_safe"
        assert items[0]["source_class"] == "private_local"
    finally:
        asyncio.run(engine.dispose())


def test_rules_import_from_aon_payloads_supports_strict_rules_query(tmp_path: Path):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        _write_json(
            tmp_path,
            "misc/aon-rules/raw/0097-law-and-chaos.json",
            RULE_PAYLOAD,
        )

        preview = client.get(
            "/api/campaign/import/dropzone",
            params={"root_path": str(tmp_path), "category": "rules"},
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["summary"]["files_previewed"] == 1
        assert preview_payload["summary"]["parsed_documents"] == 1
        preview_item = preview_payload["files"][0]
        assert preview_item["import_format"] == "json"
        assert preview_item["title"] == "Law and Chaos"

        imported = client.post(
            "/api/campaign/import/batch",
            json={"root_path": str(tmp_path), "categories": ["rules"]},
        )
        assert imported.status_code == 200
        imported_payload = imported.json()
        assert imported_payload["summary"]["files_imported"] == 1
        item = imported_payload["files"][0]
        assert item["document"]["kind"] == "rule"
        assert item["document"]["source_class"] == "retrieval_only"
        assert item["document"]["privacy_scope"] == "public"
        assert item["document"]["visibility_scope"] == "player_safe"
        assert item["document"]["rag_eligible"] is True
        assert item["document"]["train_eligible"] is False

        rules = client.get("/api/documents", params={"kind": "rule"})
        assert rules.status_code == 200
        assert rules.json()["total"] == 1

        strict_query = client.post(
            "/api/documents/rules/query",
            json={"query": "What does lawful alignment mean?", "strict": True},
        )
        assert strict_query.status_code == 200
        strict_payload = strict_query.json()
        assert strict_payload["citations"]
        assert "lawful alignment" in strict_payload["answer"].lower()
    finally:
        asyncio.run(engine.dispose())
