from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.campaign import CampaignEntity
from backend.models.document import Document
from backend.services.campaign_service import campaign_service
from backend.services.obsidian_markdown import (
    build_frontmatter,
    safe_note_stem,
    split_frontmatter,
    wikilink_for_path,
)


ENTITY_FOLDER_BY_TYPE = {
    "artifact": Path("Campaign/Artifacts"),
    "calendar": Path("Campaign/Calendars"),
    "event": Path("Campaign/Events"),
    "faction": Path("Campaign/Factions"),
    "holiday": Path("Campaign/Holidays"),
    "location": Path("Campaign/Locations"),
    "npc": Path("Campaign/NPCs"),
    "pc": Path("Campaign/PCs"),
    "shop": Path("Campaign/Shops"),
}

ENTITY_TAG_BY_TYPE = {
    entity_type: f"dma/entity/{entity_type}" for entity_type in ENTITY_FOLDER_BY_TYPE
}

ENTITY_INDEX_LABELS = {
    "artifact": "Artifacts",
    "calendar": "Calendars",
    "event": "Events",
    "faction": "Factions",
    "holiday": "Holidays",
    "location": "Locations",
    "npc": "NPCs",
    "pc": "PCs",
    "shop": "Shops",
}

DOCUMENT_FOLDER_BY_KIND = {
    "campaign_note": Path("Notes"),
    "pc_sheet": Path("Sheets"),
    "reference": Path("Library/References"),
    "session_log": Path("Sessions"),
    "session_prep": Path("Prep"),
}

BASE_FILE_BY_SECTION = {
    "campaign": Path("Bases/Campaign.base"),
    "library": Path("Bases/Library.base"),
    "notes": Path("Bases/Notes.base"),
    "sheets": Path("Bases/Sheets.base"),
    "party_overview": Path("Bases/Party Overview.base"),
    "sessions": Path("Bases/Sessions.base"),
    "prep": Path("Bases/Prep.base"),
    "command_center_timeline": Path("Bases/Timeline.base"),
    "command_center_npcs": Path("Bases/NPC Roster.base"),
    "command_center_locations": Path("Bases/Location Atlas.base"),
}

COMMAND_CENTER_ROOT = Path("Command Center")
REFERENCE_ASSET_ROOT = Path("Library/Assets")
REFERENCE_MAP_SOURCE_ROOT = Path(
    "assets/imports/misc/private-local/media/abomination-vaults/maps"
)
AREA_HEADER_RE = re.compile(
    r"^\s*(?P<area>[A-Z]{1,3}\d+[A-Z]?)\.\s+" r"(?P<title>.+?)(?:\s{2,}.+)?$"
)
CHAPTER_HEADER_RE = re.compile(r"^\s*CHAPTER\s+\d+:?\s*(?P<title>.*)$", re.IGNORECASE)
REFERENCE_LABEL_RE = re.compile(
    r"^(?P<label>Creatures?|Hazards?|Treasure|Story Award):\s*(?P<text>.*)$",
    re.IGNORECASE,
)
REFERENCE_LABEL_ANYWHERE_RE = re.compile(
    r"\b(?:Creatures?|Hazards?|Treasure|Story Award):", re.IGNORECASE
)
AREA_DIFFICULTY_RE = re.compile(
    r"\b(?:TRIVIAL|LOW|MODERATE|SEVERE|EXTREME|VARIABLE)\s+\d+\b.*$",
    re.IGNORECASE,
)
DOT_LEADER_RE = re.compile(r"\.{2,}\s*\d+\b.*$")
PDF_PAGE_MARKER_RE = re.compile(r"^\[Page (?P<page>\d+)\]$", re.MULTILINE)
MANAGED_BLOCK_TEMPLATE = (
    "<!-- dma:managed:start {name} -->\n{content}\n<!-- dma:managed:end {name} -->"
)
EDITABLE_BLOCK_TEMPLATE = (
    "<!-- dma:editable:start {name} -->\n{content}\n<!-- dma:editable:end {name} -->"
)
PDFTOTEXT_TIMEOUT_SECONDS = 30
PDFIMAGES_LIST_TIMEOUT_SECONDS = 30
PDFIMAGES_EXTRACT_TIMEOUT_SECONDS = 30


class ObsidianVaultService:
    def __init__(self) -> None:
        self._pdf_page_cache: dict[str, list[tuple[int, str]]] = {}
        self._pdf_image_spec_cache: dict[str, list[dict[str, int]]] = {}

    async def export_vault(
        self,
        db: AsyncSession,
        *,
        vault_path: str,
        include_inactive: bool = True,
        include_campaign_notes: bool = True,
        include_pc_sheets: bool = True,
        include_session_logs: bool = True,
        include_session_prep: bool = True,
        include_indexes: bool = True,
        include_command_center: bool = True,
        campaign_note_limit: int = 100,
        pc_sheet_limit: int = 50,
        reference_limit: int = 100,
        session_limit: int = 50,
        prep_limit: int = 50,
    ) -> dict[str, Any]:
        root = Path(vault_path).expanduser()
        root.mkdir(parents=True, exist_ok=True)

        entity_payloads = await self._load_entities(
            db, include_inactive=include_inactive
        )
        entity_payload_by_id = {entity["id"]: entity for entity in entity_payloads}
        entity_paths = self._allocate_entity_paths(entity_payloads)

        campaign_notes: list[Document] = []
        if include_campaign_notes:
            campaign_notes = await self._load_documents(
                db, kind="campaign_note", limit=campaign_note_limit
            )

        pc_sheet_documents: list[Document] = []
        if include_pc_sheets:
            pc_sheet_documents = await self._load_documents(
                db, kind="pc_sheet", limit=pc_sheet_limit
            )

        reference_documents: list[Document] = await self._load_documents(
            db, kind="reference", limit=reference_limit
        )

        session_logs: list[Document] = []
        if include_session_logs:
            session_logs = await self._load_documents(
                db, kind="session_log", limit=session_limit
            )

        prep_documents: list[Document] = []
        if include_session_prep:
            prep_documents = await self._load_documents(
                db, kind="session_prep", limit=prep_limit
            )

        document_paths = self._allocate_all_document_paths(
            reference_documents=reference_documents,
            campaign_notes=campaign_notes,
            pc_sheet_documents=pc_sheet_documents,
            session_logs=session_logs,
            prep_documents=prep_documents,
        )
        supporting_documents = [
            *reference_documents,
            *campaign_notes,
            *pc_sheet_documents,
            *session_logs,
            *prep_documents,
        ]

        written_files: list[dict[str, Any]] = []
        for entity in entity_payloads:
            relative_path = entity_paths[entity["id"]]
            content = self._render_entity_note(
                entity,
                entity_paths,
                linkable_entities=entity_payloads,
                supporting_documents=supporting_documents,
                document_paths=document_paths,
            )
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": "campaign_entity",
                    "title": entity["name"],
                }
            )

        for document in campaign_notes:
            relative_path = document_paths[document]
            linkable_entities = self._related_entities_for_document(
                document, entity_payloads, limit=None
            )
            content = self._render_document_note(
                document,
                folder="Notes",
                entity_paths=entity_paths,
                related_entities=linkable_entities[:12],
                linkable_entities=linkable_entities,
                entity_payload_by_id=entity_payload_by_id,
                note_path=relative_path,
            )
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": document.kind,
                    "title": document.title,
                }
            )

        for document in pc_sheet_documents:
            relative_path = document_paths[document]
            linkable_entities = self._related_entities_for_document(
                document, entity_payloads, limit=None
            )
            content = self._render_document_note(
                document,
                folder="Sheets",
                entity_paths=entity_paths,
                related_entities=linkable_entities[:12],
                linkable_entities=linkable_entities,
                entity_payload_by_id=entity_payload_by_id,
                note_path=relative_path,
            )
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": document.kind,
                    "title": document.title,
                }
            )

        for document in reference_documents:
            relative_path = document_paths[document]
            linkable_entities = self._related_entities_for_document(
                document, entity_payloads, limit=None
            )
            extracted_assets = self._extract_reference_assets(document, root=root)
            related_map_assets = self._export_reference_map_assets(document, root=root)
            content = self._render_document_note(
                document,
                folder="Library",
                entity_paths=entity_paths,
                related_entities=linkable_entities[:12],
                linkable_entities=linkable_entities,
                entity_payload_by_id=entity_payload_by_id,
                note_path=relative_path,
                extracted_assets=extracted_assets,
                related_map_assets=related_map_assets,
            )
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": document.kind,
                    "title": document.title,
                }
            )
            for asset_path in [*extracted_assets, *related_map_assets]:
                written_files.append(
                    {
                        "path": asset_path.as_posix(),
                        "kind": "reference_asset",
                        "title": asset_path.name,
                    }
                )

        for document in session_logs:
            relative_path = document_paths[document]
            linkable_entities = self._related_entities_for_document(
                document, entity_payloads, limit=None
            )
            content = self._render_document_note(
                document,
                folder="Sessions",
                entity_paths=entity_paths,
                related_entities=linkable_entities[:12],
                linkable_entities=linkable_entities,
                entity_payload_by_id=entity_payload_by_id,
                note_path=relative_path,
            )
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": document.kind,
                    "title": document.title,
                }
            )

        for document in prep_documents:
            relative_path = document_paths[document]
            linkable_entities = self._related_entities_for_document(
                document, entity_payloads, limit=None
            )
            content = self._render_document_note(
                document,
                folder="Prep",
                entity_paths=entity_paths,
                related_entities=linkable_entities[:12],
                linkable_entities=linkable_entities,
                entity_payload_by_id=entity_payload_by_id,
                note_path=relative_path,
            )
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": document.kind,
                    "title": document.title,
                }
            )

        index_count = 0
        base_count = 0
        command_center_count = 0
        root_note_count = 0
        root_notes = self._build_root_notes()
        for relative_path, content in root_notes.items():
            self._write_note(root, relative_path, content)
            written_files.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": "root_note",
                    "title": relative_path.stem,
                }
            )
        root_note_count = len(root_notes)
        if include_indexes:
            base_files = self._build_base_files(
                has_campaign=bool(entity_payloads),
                has_reference_documents=bool(reference_documents),
                has_campaign_notes=bool(campaign_notes),
                has_pc_sheets=bool(pc_sheet_documents),
                has_session_logs=bool(session_logs),
                has_prep=bool(prep_documents),
            )
            for relative_path, content in base_files.items():
                self._write_note(root, relative_path, content)
                written_files.append(
                    {
                        "path": relative_path.as_posix(),
                        "kind": "base",
                        "title": relative_path.stem,
                    }
                )
            base_count = len(base_files)

            indexes = self._build_index_notes(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
                reference_documents=reference_documents,
                campaign_notes=campaign_notes,
                pc_sheet_documents=pc_sheet_documents,
                session_logs=session_logs,
                prep_documents=prep_documents,
            )
            for relative_path, content in indexes.items():
                self._write_note(root, relative_path, content)
                written_files.append(
                    {
                        "path": relative_path.as_posix(),
                        "kind": "index",
                        "title": relative_path.stem,
                    }
                )
            index_count = len(indexes)

        if include_command_center:
            dashboards = self._build_command_center_notes(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
                reference_documents=reference_documents,
                campaign_notes=campaign_notes,
                pc_sheet_documents=pc_sheet_documents,
                session_logs=session_logs,
                prep_documents=prep_documents,
                document_paths=document_paths,
            )
            for relative_path, content in dashboards.items():
                self._write_note(root, relative_path, content)
                written_files.append(
                    {
                        "path": relative_path.as_posix(),
                        "kind": "command_center",
                        "title": relative_path.stem,
                    }
                )
            command_center_count = len(dashboards)

        return {
            "vault_path": str(root),
            "counts": {
                "campaign_entities": len(entity_payloads),
                "reference_documents": len(reference_documents),
                "campaign_notes": len(campaign_notes),
                "pc_sheets": len(pc_sheet_documents),
                "session_logs": len(session_logs),
                "session_prep": len(prep_documents),
                "indexes": index_count,
                "bases": base_count,
                "command_center": command_center_count,
                "root_notes": root_note_count,
                "files_written": len(written_files),
            },
            "files": written_files,
        }

    def _build_root_notes(self) -> dict[Path, str]:
        return {
            Path("00 Vault Guide.md"): self._vault_guide_note(),
        }

    def _vault_guide_note(self) -> str:
        lines = [
            "# How To Use This Vault",
            "",
            "This Obsidian vault is the human-facing campaign workspace exported from DMA.",
            "Use it to browse the campaign, follow links between people and places, and add supported GM notes without needing DMA installed on the same machine.",
            "",
            "## Open First",
            "- [[Command Center/Start Here|Command Center/Start Here]]",
            "- [[Command Center/Session 1 Prep|Command Center/Session 1 Prep]]",
            "- [[Campaign/Index|Campaign/Index]]",
            "- [[Library/Index|Library/Index]]",
            "",
            "## How The Vault Is Organized",
            "- `Command Center/` contains the main GM dashboards and jump-off pages.",
            "- `Campaign/` contains the canonical notes for NPCs, locations, events, shops, factions, and other structured entities.",
            "- `Library/` contains reference books, extracted images, and map assets.",
            "- `Notes/` contains campaign-specific prep and play-test notes.",
            "",
            "## Recommended Reading Flow",
            "1. Start in [[Command Center/Start Here|Start Here]].",
            "2. Open the current prep page, such as [[Command Center/Session 1 Prep|Session 1 Prep]].",
            "3. Jump into canonical notes from there for NPCs, locations, and events.",
            "4. Open [[Library/Index|Reference Library Index]] when you need book context or source excerpts.",
            "",
            "## Editing Rules",
            "- Safe places to edit are the `DM Working Notes`, `Player-Facing Summary`, `Session Changes`, and `DMA Editable Source` sections.",
            "- Keep the YAML properties at the top of notes intact so DMA can continue to recognize and sync them.",
            "- Do not remove `<!-- dma:managed ... -->` or `<!-- dma:editable ... -->` markers.",
            "",
            "## Images And Links",
            "- Notes may include an `imageLink` property that points to an image in `Library/Assets/` using an Obsidian wikilink.",
            "- Open those asset links directly when you want a portrait, monster image, item image, or map illustration.",
            "- Many dashboard notes embed canonical content with `![[...]]` or `![[...#...]]` instead of duplicating it.",
            "",
            "## Sync Expectations",
            "- This vault is meant to be regenerated from DMA as the campaign evolves.",
            "- Supported note edits can also be synced back into DMA when the sync workflow is run.",
            "- If new source books, session notes, or character sheets are imported, export the vault again to refresh these pages.",
        ]
        return "\n".join(lines).strip() + "\n"

    async def _load_entities(
        self, db: AsyncSession, *, include_inactive: bool
    ) -> list[dict[str, Any]]:
        stmt = (
            select(CampaignEntity)
            .options(*campaign_service._entity_loader_options())
            .order_by(
                CampaignEntity.entity_type, CampaignEntity.name, CampaignEntity.id
            )
        )
        if not include_inactive:
            stmt = stmt.where(CampaignEntity.is_active.is_(True))
        result = await db.execute(stmt)
        entities = list(result.scalars().unique().all())
        return [
            campaign_service.entity_to_dict(
                entity, include_relationships=True, include_sheet_versions=True
            )
            for entity in entities
        ]

    async def _load_documents(
        self, db: AsyncSession, *, kind: str, limit: int
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.kind == kind)
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _allocate_entity_paths(
        self, entity_payloads: list[dict[str, Any]]
    ) -> dict[int, Path]:
        counts = Counter(
            (
                ENTITY_FOLDER_BY_TYPE[entity["entity_type"]].as_posix(),
                safe_note_stem(entity["name"]).casefold(),
            )
            for entity in entity_payloads
        )
        paths: dict[int, Path] = {}
        for entity in entity_payloads:
            folder = ENTITY_FOLDER_BY_TYPE[entity["entity_type"]]
            stem = safe_note_stem(entity["name"])
            if counts[(folder.as_posix(), stem.casefold())] > 1:
                stem = f"{stem} ({entity['stable_key']})"
            paths[entity["id"]] = folder / f"{stem}.md"
        return paths

    def _allocate_document_paths(
        self, documents: list[Document]
    ) -> dict[Document, Path]:
        if not documents:
            return {}

        folder = DOCUMENT_FOLDER_BY_KIND[documents[0].kind]
        counts = Counter(
            safe_note_stem(self._document_export_title(document)).casefold()
            for document in documents
        )
        paths: dict[Document, Path] = {}
        for document in documents:
            stem = safe_note_stem(self._document_export_title(document))
            if counts[stem.casefold()] > 1:
                stem = f"{stem} ({document.id})"
            paths[document] = folder / f"{stem}.md"
        return paths

    def _allocate_all_document_paths(
        self,
        *,
        reference_documents: list[Document],
        campaign_notes: list[Document],
        pc_sheet_documents: list[Document],
        session_logs: list[Document],
        prep_documents: list[Document],
    ) -> dict[Document, Path]:
        return {
            **self._allocate_document_paths(reference_documents),
            **self._allocate_document_paths(campaign_notes),
            **self._allocate_document_paths(pc_sheet_documents),
            **self._allocate_document_paths(session_logs),
            **self._allocate_document_paths(prep_documents),
        }

    def _render_entity_note(
        self,
        entity: dict[str, Any],
        entity_paths: dict[int, Path],
        *,
        linkable_entities: list[dict[str, Any]],
        supporting_documents: list[Document],
        document_paths: dict[Document, Path],
    ) -> str:
        source_references = self._source_references_for_entity(
            entity,
            supporting_documents=supporting_documents,
            document_paths=document_paths,
        )
        image_link = self._entity_image_link(
            entity,
            supporting_documents=supporting_documents,
        )
        detail_payload = self._entity_detail_payload(entity)
        relationship_payload = self._entity_relationship_payload(entity, entity_paths)
        metadata = {
            "dma_kind": "campaign_entity",
            "vault_sync": True,
            "dma_sync_role": "vault-managed",
            "entity_id": entity["id"],
            "entity_type": entity["entity_type"],
            "stable_key": entity["stable_key"],
            "is_active": entity["is_active"],
            "summary": self._inline(entity.get("summary") or ""),
            "tags": self._entity_tags(entity),
            "updated_at": entity["updated_at"],
            "current_location": self._reference_link(
                entity.get("current_location"), entity_paths
            ),
            "parent": self._reference_link(entity.get("parent_entity"), entity_paths),
            "owner": self._reference_link(entity.get("owner_entity"), entity_paths),
            "imageLink": image_link,
            "details": detail_payload,
            "relationships": relationship_payload,
            "source_references": source_references,
        }

        lines = [build_frontmatter(metadata), f"# {entity['name']}", ""]
        managed_sections: list[str] = []
        overview_lines = self._entity_overview_lines(
            entity,
            entity_paths=entity_paths,
            entities=linkable_entities,
        )
        if overview_lines:
            managed_sections.extend(["## Overview", *overview_lines, ""])

        detail_lines = self._entity_detail_section_lines(
            entity,
            entity_paths=entity_paths,
            entities=linkable_entities,
        )
        if detail_lines:
            managed_sections.extend(["## Detailed Notes", *detail_lines, ""])

        relationship_lines = self._entity_relationship_section_lines(
            entity,
            entity_paths=entity_paths,
        )
        if relationship_lines:
            managed_sections.extend(
                ["## Relationship Context", *relationship_lines, ""]
            )

        latest_sheet = entity.get("latest_sheet_version") or {}
        if latest_sheet:
            managed_sections.extend(
                [
                    "## Latest Sheet",
                    (
                        f"Most recent imported sheet version: `{latest_sheet.get('version_number')}`"
                    ),
                ]
            )
            if latest_sheet.get("source_name"):
                managed_sections.append(f"Source: `{latest_sheet['source_name']}`")
            managed_sections.append("")

        if source_references:
            managed_sections.append("## Source References")
            for reference in source_references:
                link = reference["link"]
                managed_sections.append(f"### {link}")
                source_bits = [f"`{reference['source_file']}`"]
                if reference.get("page") is not None:
                    source_bits.append(f"page {reference['page']}")
                managed_sections.append(f"Source: {', '.join(source_bits)}")
                managed_sections.append(reference["excerpt"])
                managed_sections.append("")

        if managed_sections:
            lines.append(
                self._managed_block(
                    "entity-generated", "\n".join(managed_sections).strip()
                )
            )
            lines.append("")

        lines.append("## DM Working Notes")
        lines.append(
            self._editable_block(
                "dm-working-notes",
                self._editable_text(entity.get("details", {}).get("vault_dm_notes")),
            )
        )
        lines.append("")
        lines.append("## Player-Facing Summary")
        lines.append(
            self._editable_block(
                "player-facing-summary",
                self._editable_text(
                    entity.get("details", {}).get("vault_player_summary")
                ),
            )
        )
        lines.append("")
        lines.append("## Session Changes")
        lines.append(
            self._editable_block(
                "session-changes",
                self._editable_list(
                    entity.get("details", {}).get("vault_session_changes")
                ),
            )
        )
        lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _render_document_note(
        self,
        document: Document,
        *,
        folder: str,
        entity_paths: dict[int, Path],
        related_entities: list[dict[str, Any]],
        linkable_entities: list[dict[str, Any]],
        entity_payload_by_id: dict[int, dict[str, Any]],
        note_path: Path,
        extracted_assets: list[Path] | None = None,
        related_map_assets: list[Path] | None = None,
    ) -> str:
        _, body = split_frontmatter(document.content or "")
        body = self._strip_duplicate_title(body, document.title)
        if document.kind == "pc_sheet":
            return self._render_pc_sheet_note(
                document,
                folder=folder,
                body=body,
                entity_paths=entity_paths,
                related_entities=related_entities,
                linkable_entities=linkable_entities,
                entity_payload_by_id=entity_payload_by_id,
                note_path=note_path,
            )
        encounter_entries = self._reference_index_entries(
            body,
            labels={"creatures", "creature", "hazards", "hazard"},
            audience="dm_only",
        )
        treasure_entries = self._reference_index_entries(
            body,
            labels={"treasure", "story award"},
            audience="dm_only",
        )
        related_links = [
            self._reference_link(entity, entity_paths)
            for entity in related_entities
            if self._reference_link(entity, entity_paths)
        ]
        metadata = {
            "dma_kind": "document",
            "vault_sync": document.kind in {"campaign_note", "pc_sheet", "session_log"},
            "dma_sync_role": "vault-managed",
            "document_kind": document.kind,
            "doc_id": document.id,
            "title": document.title,
            "source_name": document.source_name,
            "source_url": document.url,
            "source_class": document.source_class,
            "privacy_scope": document.privacy_scope,
            "review_status": document.review_status,
            "visibility_scope": document.visibility_scope,
            "audience": self._audience_metadata(document.visibility_scope),
            "rag_eligible": document.rag_eligible,
            "train_eligible": document.train_eligible,
            "summary": self._inline(document.summary or ""),
            "imageLink": self._document_image_link(
                extracted_assets=extracted_assets,
                related_map_assets=related_map_assets,
            ),
            "related_entities": related_links,
            "extracted_assets": [path.as_posix() for path in extracted_assets or []],
            "related_map_assets": [
                path.as_posix() for path in related_map_assets or []
            ],
            "encounters": encounter_entries,
            "treasure": treasure_entries,
            "updated_at": document.updated_at.isoformat(),
            "tags": [
                "dma/generated",
                "dma/document",
                f"dma/document/{document.kind}",
                f"dma/folder/{folder.lower()}",
            ],
        }
        lines = [build_frontmatter(metadata), f"# {document.title}", ""]
        managed_sections: list[str] = []
        if related_links:
            managed_sections.append("## Linked Entities")
            for entity_link in related_links:
                managed_sections.append(f"- {entity_link}")
            managed_sections.append("")

        managed_sections.append("## Access And Spoilers")
        managed_sections.extend(self._audience_section_lines(document.visibility_scope))
        managed_sections.append("")

        if related_map_assets:
            managed_sections.append("## Related Maps")
            for asset_path in related_map_assets:
                managed_sections.append(f"- ![[{asset_path.as_posix()}]]")
            managed_sections.append("")

        if extracted_assets:
            managed_sections.append("## Extracted Images")
            for asset_path in extracted_assets:
                managed_sections.append(f"![[{asset_path.as_posix()}]]")
            managed_sections.append("")

        if encounter_entries:
            managed_sections.append("## Encounter Index")
            managed_sections.extend(
                self._reference_index_section_lines(encounter_entries)
            )
            managed_sections.append("")
            for section_title, subtype in (
                ("Monster Index", "monster"),
                ("Trap Index", "trap"),
                ("Haunt Index", "haunt"),
                ("Hazard Index", "hazard"),
            ):
                filtered_entries = self._reference_entries_by_subtype(
                    encounter_entries,
                    subtype=subtype,
                )
                if not filtered_entries:
                    continue
                managed_sections.append(f"## {section_title}")
                managed_sections.extend(
                    self._reference_index_section_lines(filtered_entries)
                )
                managed_sections.append("")

        if treasure_entries:
            managed_sections.append("## Treasure Index")
            managed_sections.extend(
                self._reference_index_section_lines(treasure_entries)
            )
            managed_sections.append("")

        if managed_sections:
            lines.append(
                self._managed_block(
                    "document-generated", "\n".join(managed_sections).strip()
                )
            )
            lines.append("")

        if document.kind in {"campaign_note", "pc_sheet", "session_log"}:
            lines.append("## DMA Editable Source")
            lines.append(
                self._editable_block(
                    "editable-source",
                    body.strip(),
                )
            )
            lines.append("")
            lines.append("## DM Working Notes")
            lines.append(self._editable_block("dm-working-notes", ""))
            lines.append("")

        if body.strip() and document.kind not in {
            "campaign_note",
            "pc_sheet",
            "session_log",
        }:
            lines.append(
                "## Imported Source"
                if document.kind != "reference"
                else "## Extracted Text"
            )
            lines.append(
                self._linkify_markdown_text(
                    body.strip(),
                    entity_paths=entity_paths,
                    entities=linkable_entities,
                )
            )
        return "\n".join(lines).strip() + "\n"

    def _build_index_notes(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
        reference_documents: list[Document],
        campaign_notes: list[Document],
        pc_sheet_documents: list[Document],
        session_logs: list[Document],
        prep_documents: list[Document],
    ) -> dict[Path, str]:
        entity_groups: dict[str, list[dict[str, Any]]] = {}
        for entity in entity_payloads:
            entity_groups.setdefault(entity["entity_type"], []).append(entity)

        indexes: dict[Path, str] = {}
        indexes[Path("Campaign/Index.md")] = self._campaign_index_note(
            entity_groups, entity_paths
        )
        if reference_documents:
            indexes[Path("Library/Index.md")] = self._document_index_note(
                title="Reference Library Index",
                folder_tag="library",
                documents=reference_documents,
                base_path=BASE_FILE_BY_SECTION["library"],
            )
        if campaign_notes:
            indexes[Path("Notes/Index.md")] = self._document_index_note(
                title="Campaign Notes Index",
                folder_tag="notes",
                documents=campaign_notes,
                base_path=BASE_FILE_BY_SECTION["notes"],
            )
        if pc_sheet_documents:
            indexes[Path("Sheets/Index.md")] = self._document_index_note(
                title="PC Sheet Index",
                folder_tag="sheets",
                documents=pc_sheet_documents,
                base_path=BASE_FILE_BY_SECTION["sheets"],
            )
        if session_logs:
            indexes[Path("Sessions/Index.md")] = self._document_index_note(
                title="Session Index",
                folder_tag="sessions",
                documents=session_logs,
                base_path=BASE_FILE_BY_SECTION["sessions"],
            )
        if prep_documents:
            indexes[Path("Prep/Index.md")] = self._document_index_note(
                title="Prep Index",
                folder_tag="prep",
                documents=prep_documents,
                base_path=BASE_FILE_BY_SECTION["prep"],
            )
        return indexes

    def _build_command_center_notes(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
        reference_documents: list[Document],
        campaign_notes: list[Document],
        pc_sheet_documents: list[Document],
        session_logs: list[Document],
        prep_documents: list[Document],
        document_paths: dict[Document, Path],
    ) -> dict[Path, str]:
        notes: dict[Path, str] = {}
        notes[COMMAND_CENTER_ROOT / "Start Here.md"] = self._command_center_start_note(
            entity_payloads=entity_payloads,
            reference_documents=reference_documents,
            campaign_notes=campaign_notes,
            pc_sheet_documents=pc_sheet_documents,
            session_logs=session_logs,
            prep_documents=prep_documents,
            document_paths=document_paths,
        )
        notes[COMMAND_CENTER_ROOT / "Session 1 Prep.md"] = (
            self._command_center_session_one_note(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
                campaign_notes=campaign_notes,
                document_paths=document_paths,
            )
        )
        notes[COMMAND_CENTER_ROOT / "Session Dashboard.md"] = (
            self._command_center_session_dashboard_note(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
                campaign_notes=campaign_notes,
                document_paths=document_paths,
            )
        )
        notes[COMMAND_CENTER_ROOT / "Party Overview.md"] = (
            self._command_center_party_note(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
            )
        )
        notes[COMMAND_CENTER_ROOT / "Session Threat Fit.md"] = (
            self._command_center_session_threat_fit_note(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
            )
        )
        notes[COMMAND_CENTER_ROOT / "Timeline.md"] = self._command_center_timeline_note(
            entity_payloads=entity_payloads,
            entity_paths=entity_paths,
        )
        notes[COMMAND_CENTER_ROOT / "NPC Roster.md"] = self._command_center_npc_note(
            entity_payloads=entity_payloads,
            entity_paths=entity_paths,
        )
        notes[COMMAND_CENTER_ROOT / "Location Atlas.md"] = (
            self._command_center_location_note(
                entity_payloads=entity_payloads,
                entity_paths=entity_paths,
            )
        )
        notes[COMMAND_CENTER_ROOT / "Encounter Tracker.md"] = (
            self._command_center_reference_tracker_note(
                title="Encounter Tracker",
                description=(
                    "A DM-facing rollup of creatures and hazards extracted from "
                    "reference material."
                ),
                documents=reference_documents,
                document_paths=document_paths,
                labels={"creatures", "creature", "hazards", "hazard"},
                tags=["dma/command-center/encounters"],
            )
        )
        notes[COMMAND_CENTER_ROOT / "Monster Tracker.md"] = (
            self._command_center_reference_tracker_note(
                title="Monster Tracker",
                description=(
                    "A DM-facing rollup of creature encounters extracted from "
                    "reference material."
                ),
                documents=reference_documents,
                document_paths=document_paths,
                labels={"creatures", "creature"},
                tags=["dma/command-center/monsters"],
                section="Monster Index",
                subtype="monster",
            )
        )
        notes[COMMAND_CENTER_ROOT / "Trap Tracker.md"] = (
            self._command_center_reference_tracker_note(
                title="Trap Tracker",
                description=(
                    "A DM-facing rollup of trap hazards extracted from reference "
                    "material."
                ),
                documents=reference_documents,
                document_paths=document_paths,
                labels={"hazards", "hazard"},
                tags=["dma/command-center/traps"],
                section="Trap Index",
                subtype="trap",
            )
        )
        notes[COMMAND_CENTER_ROOT / "Haunt Tracker.md"] = (
            self._command_center_reference_tracker_note(
                title="Haunt Tracker",
                description=(
                    "A DM-facing rollup of haunts and haunting-style hazards "
                    "extracted from reference material."
                ),
                documents=reference_documents,
                document_paths=document_paths,
                labels={"hazards", "hazard"},
                tags=["dma/command-center/haunts"],
                section="Haunt Index",
                subtype="haunt",
            )
        )
        notes[COMMAND_CENTER_ROOT / "Treasure Tracker.md"] = (
            self._command_center_reference_tracker_note(
                title="Treasure Tracker",
                description=(
                    "A DM-facing rollup of treasure and story awards extracted "
                    "from reference material."
                ),
                documents=reference_documents,
                document_paths=document_paths,
                labels={"treasure", "story award"},
                tags=["dma/command-center/treasure"],
            )
        )
        return notes

    def _command_center_start_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        reference_documents: list[Document],
        campaign_notes: list[Document],
        pc_sheet_documents: list[Document],
        session_logs: list[Document],
        prep_documents: list[Document],
        document_paths: dict[Document, Path],
    ) -> str:
        counts = Counter(entity["entity_type"] for entity in entity_payloads)
        core_gm_titles = [
            "12 GM Campaign Digest",
            "Abomination Vaults Campaign Timeline",
            "01 Starter Campaign Model",
            "02 Roseguard And Omens",
        ]
        core_gm_links = [
            wikilink_for_path(document_paths[document], alias=document.title)
            for title in core_gm_titles
            for document in campaign_notes
            if document.title.casefold() == title.casefold() and document in document_paths
        ]
        lines = self._command_center_header(
            "DMA Campaign Command Center",
            tags=["dma/command-center/start"],
        )
        lines.extend(
            [
                "Use this folder as the human-facing cockpit for running the campaign.",
                "The generated pages below collect the most useful views without replacing the structured campaign notes.",
                "",
                "## Start Here",
                "- [[Command Center/Session Dashboard|Session Dashboard]]",
                "- [[Command Center/Session 1 Prep|Session 1 Prep]]",
                "- [[Command Center/Party Overview|Party Overview]]",
                "- [[Command Center/Session Threat Fit|Session Threat Fit]]",
                "- [[Command Center/Timeline|Timeline]]",
                "- [[Command Center/NPC Roster|NPC Roster]]",
                "- [[Command Center/Location Atlas|Location Atlas]]",
                "- [[Command Center/Encounter Tracker|Encounter Tracker]]",
                "- [[Command Center/Monster Tracker|Monster Tracker]]",
                "- [[Command Center/Trap Tracker|Trap Tracker]]",
                "- [[Command Center/Haunt Tracker|Haunt Tracker]]",
                "- [[Command Center/Treasure Tracker|Treasure Tracker]]",
                "",
                "## Core GM Briefings",
            ]
        )
        if core_gm_links:
            lines.extend(f"- {link}" for link in core_gm_links)
        else:
            lines.append("- No core GM briefings exported yet.")
        lines.extend(
            [
                "",
                "## Dynamic Vault Views",
                "- [[Campaign/Index|Campaign Index]]",
                "- [[Library/Index|Reference Library Index]]",
                "- [[Notes/Index|Campaign Notes Index]]",
                "- [[Sheets/Index|PC Sheet Index]]",
                "- [[Sessions/Index|Session Index]]",
                "- [[Prep/Index|Prep Index]]",
                "",
                "## Current Export Inventory",
                f"- Campaign entities: {len(entity_payloads)}",
                f"- Reference documents: {len(reference_documents)}",
                f"- Campaign notes: {len(campaign_notes)}",
                f"- PC sheets: {len(pc_sheet_documents)}",
                f"- Session logs: {len(session_logs)}",
                f"- Session prep notes: {len(prep_documents)}",
                "",
                "## Entity Counts",
            ]
        )
        if counts:
            for entity_type, count in sorted(counts.items()):
                label = ENTITY_INDEX_LABELS.get(entity_type, entity_type.title())
                lines.append(f"- {label}: {count}")
        else:
            lines.append("- No campaign entities exported yet.")
        lines.extend(
            [
                "",
                "## Editing Rules",
                "- Edit `DM Working Notes`, `Player-Facing Summary`, and `Session Changes` in entity notes.",
                "- Edit `DMA Editable Source` for campaign notes, PC sheets, and session logs.",
                "- Avoid changing `entity_id`, `doc_id`, `vault_sync`, `dma_sync_role`, or managed block comments.",
                "- Run `make sync-obsidian-vault VAULT=/path/to/vault` when you want DMA to ingest supported edits.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_session_dashboard_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
        campaign_notes: list[Document],
        document_paths: dict[Document, Path],
    ) -> str:
        lines = self._command_center_header(
            "Session Dashboard",
            tags=["dma/command-center/session-dashboard"],
        )
        runbook_embeds = self._document_section_embed_lines(
            campaign_notes,
            document_paths=document_paths,
            titles=["04 Session 1 Runbook", "06 Maptool Session 1 Setup Plan"],
            section="DMA Editable Source",
        )
        handout_embeds = self._document_section_embed_lines(
            campaign_notes,
            document_paths=document_paths,
            titles=["07 Session 1 Player Handout"],
            section="DMA Editable Source",
        )
        lines.extend(
            [
                "A GM-facing play surface that keeps the current party, tonight's prep, and the most useful trackers one click away.",
                "",
                "## Open Alongside This Page",
                "- [[Command Center/Session 1 Prep|Session 1 Prep]]",
                "- [[Command Center/Party Overview|Party Overview]]",
                "- [[Command Center/Session Threat Fit|Session Threat Fit]]",
                "- [[Command Center/NPC Roster|NPC Roster]]",
                "- [[Command Center/Location Atlas|Location Atlas]]",
                "- [[Command Center/Encounter Tracker|Encounter Tracker]]",
                "- [[Command Center/Treasure Tracker|Treasure Tracker]]",
                "",
                "## Party Table",
                *self._callout_lines(
                    "abstract",
                    "Current party overview",
                    [f"![[{BASE_FILE_BY_SECTION['party_overview'].as_posix()}]]"],
                    collapsed=True,
                ),
                "",
                "## Session Threat Fit",
            ]
        )
        threat_fit_lines = self._session_threat_fit_lines(
            [
                entity
                for entity in entity_payloads
                if entity.get("entity_type") == "pc"
            ],
            entity_paths=entity_paths,
        )
        lines.extend(
            self._callout_lines(
                "warning",
                "Session 1 fit summary",
                threat_fit_lines,
                collapsed=True,
            )
        )
        lines.extend(
            [
                "",
                "## Tonight's GM Prep",
            ]
        )
        if runbook_embeds:
            lines.extend(
                self._callout_lines(
                    "info",
                    "Runbook and MapTool setup",
                    runbook_embeds,
                    collapsed=True,
                )
            )
        else:
            lines.append("- No dedicated runbook notes are available yet.")
        lines.extend(
            [
                "",
                "## Player-Facing Handout",
            ]
        )
        if handout_embeds:
            lines.extend(
                self._callout_lines(
                    "success",
                    "Shareable handout",
                    handout_embeds,
                    collapsed=True,
                )
            )
        else:
            lines.append("- No player handout has been exported yet.")
        lines.extend(
            [
                "",
                "## Quick Tracker Links",
                "- [[Command Center/Monster Tracker|Monster Tracker]]",
                "- [[Command Center/Trap Tracker|Trap Tracker]]",
                "- [[Command Center/Haunt Tracker|Haunt Tracker]]",
                "- [[Command Center/Treasure Tracker|Treasure Tracker]]",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_session_threat_fit_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> str:
        lines = self._command_center_header(
            "Session Threat Fit",
            tags=["dma/command-center/session-threat-fit"],
        )
        pc_entities = [
            entity for entity in entity_payloads if entity.get("entity_type") == "pc"
        ]
        lines.extend(
            [
                "A GM-facing read on how the current party matches the practical pressures of Session 1 in Otari, Fogfen, and the Gauntlight approach.",
                "",
                "## Session 1 Pressure Areas",
                "- Social entry: Wrin, Otari townsfolk, and rumor gathering matter more than raw combat power at first.",
                "- Scouting caution: the road to Gauntlight and the exterior approach reward Perception, Stealth, and patient exploration.",
                "- Darkness and atmosphere: low-light or darkvision helps, but not everyone has it.",
                "- Early attrition: Session 1 can still tax healing and confidence even before a full dungeon crawl begins.",
                "- Frontline stability: if the party pushes too far too fast, a solid front rank matters.",
                "",
                "## Fit Summary",
                *self._session_threat_fit_lines(pc_entities, entity_paths=entity_paths),
                "",
                "## GM Takeaways",
                "- Let [[Campaign/PCs/Fahral|Fahral]] notice trouble early and feel useful on the approach.",
                "- Give [[Campaign/PCs/Bonesy McBoner|Bonesy McBoner]] room to stabilize the group after pressure or bad rolls.",
                "- Use [[Campaign/PCs/Dwarf guardian|Dwarf guardian]] and [[Campaign/PCs/Bonesy McBoner|Bonesy McBoner]] as the obvious anchors if the group presses into danger.",
                "- Because two current sheets are still placeholders, treat any “weakness” signal as provisional rather than final.",
                "",
                "## Open With This Note",
                "- [[Command Center/Session Dashboard|Session Dashboard]]",
                "- [[Command Center/Party Overview|Party Overview]]",
                "- [[Command Center/Session 1 Prep|Session 1 Prep]]",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_party_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> str:
        lines = self._command_center_header(
            "Party Overview",
            tags=["dma/command-center/party"],
        )
        pc_entities = [
            entity for entity in entity_payloads if entity.get("entity_type") == "pc"
        ]
        lines.extend(
            [
                "A GM-facing party table for quickly comparing defenses, initiative, senses, languages, and table-critical skills.",
                "",
                "## Dynamic View",
                *self._callout_lines(
                    "abstract",
                    "Party overview table",
                    [f"![[{BASE_FILE_BY_SECTION['party_overview'].as_posix()}]]"],
                    collapsed=True,
                ),
                "",
            ]
        )
        quick_assignments = self._party_quick_assignment_lines(
            pc_entities, entity_paths=entity_paths
        )
        lines.extend(
            [
                "## Quick Assignments",
                *(quick_assignments or ["- Not enough imported sheet detail yet to rank party jobs."]),
                "",
            ]
        )
        coverage_lines = self._party_coverage_lines(pc_entities)
        lines.extend(
            [
                "## Coverage Snapshot",
                *(coverage_lines or ["- No imported PC sheets are available yet."]),
                "",
            ]
        )
        lines.extend(
            [
                "## How To Use This View",
                "- Use `Player` to find the sheet quickly at the table and `PC` to jump to the character entity.",
                "- Use `Init`, `Perception`, `Fort`, `Ref`, and `Will` when staging threats or asking for checks.",
                "- Use `Vision`, `Healing`, `Scout`, and `Frontline` to decide who should lead, patch people up, or absorb the first pressure.",
                "- Use `Languages`, `Resistances`, and `Specials` for exploration and rules reminders.",
                "- Open [[Sheets/Index|PC Sheet Index]] if you want the broader sheet catalog rather than the condensed GM view.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_session_one_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
        campaign_notes: list[Document],
        document_paths: dict[Document, Path],
    ) -> str:
        lines = self._command_center_header(
            "Session 1 Prep",
            tags=["dma/command-center/session-prep"],
        )
        focus_names = [
            "Wrin Sivinxi",
            "Otari",
            "Gauntlight Keep",
            "Abomination Vaults",
            "Wrin Points The Party Toward Gauntlight",
            "Founder's Day",
        ]
        focus_links = self._entity_links_by_name(
            focus_names,
            entity_payloads=entity_payloads,
            entity_paths=entity_paths,
        )
        note_links = [
            wikilink_for_path(document_paths[document], alias=document.title)
            for document in campaign_notes
            if document in document_paths
        ]
        lines.extend(
            [
                "This page is a generated starting-point checklist for launching a fresh campaign.",
                "Use the embeds below as the primary play surface and add table-specific reminders in the canonical notes themselves.",
                "",
                "## Opening Focus",
            ]
        )
        lines.extend(f"- {link}" for link in focus_links)
        if not focus_links:
            lines.append("- No obvious Session 1 focus entities were found yet.")
        lines.extend(
            [
                "",
                "## Read Before Play",
            ]
        )
        lines.extend(f"- {link}" for link in note_links[:8])
        if not note_links:
            lines.append("- No campaign notes exported yet.")
        lines.extend(
            [
                "",
                "## Table Checklist",
                "- Confirm the party character sheets have been imported or added to `Sheets/`.",
                "- Review player-safe summaries before sharing anything from GM-only notes.",
                "- Open [[Command Center/NPC Roster|NPC Roster]] beside [[Command Center/Location Atlas|Location Atlas]] while introducing Otari.",
                "- Keep [[Command Center/Encounter Tracker|Encounter Tracker]] and [[Command Center/Treasure Tracker|Treasure Tracker]] ready for dungeon prep.",
                "",
                "## During The Session",
                "- Put ad-hoc discoveries in the relevant note's `Session Changes` block.",
                "- Put reminders for the next game in `DM Working Notes`.",
                "- After play, sync the vault back into DMA and regenerate session prep if needed.",
            ]
        )
        focus_embeds = self._section_embed_lines_by_name(
            [
                "Wrin Sivinxi",
                "Otari",
                "Gauntlight Keep",
            ],
            section="Overview",
            entity_payloads=entity_payloads,
            entity_paths=entity_paths,
        )
        if focus_embeds:
            lines.extend(
                [
                    "",
                    "## Canonical Focus Embeds",
                    *self._callout_lines(
                        "info",
                        "Canonical focus embeds",
                        focus_embeds,
                        collapsed=True,
                    ),
                ]
            )
        player_safe_embed = self._document_section_embed_lines(
            campaign_notes,
            document_paths=document_paths,
            titles=["07 Session 1 Player Handout"],
            section="DMA Editable Source",
        )
        if player_safe_embed:
            lines.extend(
                [
                    "",
                    "## Player Handout Embed",
                    *self._callout_lines(
                        "success",
                        "Player handout",
                        player_safe_embed,
                        collapsed=True,
                    ),
                ]
            )
        return "\n".join(lines).strip() + "\n"

    def _command_center_timeline_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> str:
        lines = self._command_center_header(
            "Campaign Timeline",
            tags=["dma/command-center/timeline"],
        )
        lines.extend(
            [
                "A dynamic event view backed by canonical event notes.",
                "",
                "## Dynamic View",
                *self._callout_lines(
                    "abstract",
                    "Timeline view",
                    [f"![[{BASE_FILE_BY_SECTION['command_center_timeline'].as_posix()}]]"],
                    collapsed=True,
                ),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_npc_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> str:
        lines = self._command_center_header(
            "NPC Roster",
            tags=["dma/command-center/npcs"],
        )
        lines.extend(
            [
                "A dynamic NPC view backed by the canonical NPC notes.",
                "",
                "## Dynamic View",
                *self._callout_lines(
                    "abstract",
                    "NPC roster view",
                    [f"![[{BASE_FILE_BY_SECTION['command_center_npcs'].as_posix()}]]"],
                    collapsed=True,
                ),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_location_note(
        self,
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> str:
        lines = self._command_center_header(
            "Location Atlas",
            tags=["dma/command-center/locations"],
        )
        lines.extend(
            [
                "A dynamic location view backed by the canonical location notes.",
                "",
                "## Dynamic View",
                *self._callout_lines(
                    "abstract",
                    "Location atlas view",
                    [f"![[{BASE_FILE_BY_SECTION['command_center_locations'].as_posix()}]]"],
                    collapsed=True,
                ),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def _command_center_reference_tracker_note(
        self,
        *,
        title: str,
        description: str,
        documents: list[Document],
        document_paths: dict[Document, Path],
        labels: set[str],
        tags: list[str],
        section: str | None = None,
        subtype: str | None = None,
    ) -> str:
        lines = self._command_center_header(title, tags=tags)
        lines.extend(
            [
                description,
                "Each embed below points back to the canonical reference note section instead of duplicating the extracted rows here.",
                "",
            ]
        )
        embed_count = 0
        for document in documents:
            _, body = split_frontmatter(document.content or "")
            entries = self._reference_index_entries(
                body,
                labels=labels,
                audience="dm_only",
            )
            if subtype:
                entries = self._reference_entries_by_subtype(entries, subtype=subtype)
            if not entries:
                continue
            embed_count += 1
            document_link = wikilink_for_path(
                document_paths[document], alias=document.title
            )
            target_section = section or (
                "Encounter Index" if "encounter" in title.casefold() else "Treasure Index"
            )
            lines.append(f"## {document_link}")
            lines.extend(
                self._callout_lines(
                    "example",
                    f"{document.title} {target_section}",
                    [self._note_embed(document_paths[document], section=target_section)],
                    collapsed=True,
                )
            )
            lines.append("")
        if embed_count == 0:
            lines.append("- No extracted entries yet. Import reference text first.")
        return "\n".join(lines).strip() + "\n"

    def _command_center_header(self, title: str, *, tags: list[str]) -> list[str]:
        return [
            build_frontmatter(
                {
                    "dma_kind": "command_center",
                    "vault_sync": False,
                    "dma_sync_role": "generated-dashboard",
                    "tags": ["dma/generated", "dma/command-center", *tags],
                }
            ),
            f"# {title}",
            "",
        ]

    def _entity_links_by_name(
        self,
        names: list[str],
        *,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> list[str]:
        entities_by_name = {
            entity["name"].casefold(): entity for entity in entity_payloads
        }
        links: list[str] = []
        for name in names:
            entity = entities_by_name.get(name.casefold())
            if entity is None:
                continue
            link = self._reference_link(self._entity_ref(entity), entity_paths)
            if link:
                links.append(link)
        return links

    def _table_cell(self, value: Any) -> str:
        text = self._inline(value)
        text = text.replace("|", "\\|")
        return text

    def _campaign_index_note(
        self,
        entity_groups: dict[str, list[dict[str, Any]]],
        entity_paths: dict[int, Path],
    ) -> str:
        lines = [
            build_frontmatter(
                {
                    "dma_kind": "index",
                    "tags": ["dma/generated", "dma/index", "dma/index/campaign"],
                }
            ),
            "# Campaign Index",
            "",
            "## Dynamic View",
            *self._callout_lines(
                "abstract",
                "Campaign view",
                [f"![[{BASE_FILE_BY_SECTION['campaign'].as_posix()}]]"],
                collapsed=True,
            ),
        ]
        return "\n".join(lines).strip() + "\n"

    def _document_index_note(
        self,
        *,
        title: str,
        folder_tag: str,
        documents: list[Document],
        base_path: Path,
    ) -> str:
        lines = [
            build_frontmatter(
                {
                    "dma_kind": "index",
                    "tags": ["dma/generated", "dma/index", f"dma/index/{folder_tag}"],
                }
            ),
            f"# {title}",
            "",
            "## Dynamic View",
            *self._callout_lines(
                "abstract",
                f"{title} view",
                [f"![[{base_path.as_posix()}]]"],
                collapsed=True,
            ),
        ]
        return "\n".join(lines).strip() + "\n"

    def _note_embed(self, relative_path: Path, *, section: str | None = None) -> str:
        target = relative_path.with_suffix("").as_posix()
        if section:
            return f"![[{target}#{section}]]"
        return f"![[{target}]]"

    def _callout_lines(
        self,
        callout_type: str,
        title: str,
        body_lines: list[str],
        *,
        collapsed: bool = False,
    ) -> list[str]:
        marker = "-" if collapsed else ""
        lines = [f"> [!{callout_type}]{marker} {title}"]
        for body_line in body_lines:
            if body_line:
                lines.append(f"> {body_line}")
            else:
                lines.append(">")
        return lines

    def _section_embed_lines_by_name(
        self,
        names: list[str],
        *,
        section: str,
        entity_payloads: list[dict[str, Any]],
        entity_paths: dict[int, Path],
    ) -> list[str]:
        entities_by_name = {
            entity["name"].casefold(): entity for entity in entity_payloads
        }
        embeds: list[str] = []
        for name in names:
            entity = entities_by_name.get(name.casefold())
            if entity is None:
                continue
            relative_path = entity_paths.get(entity["id"])
            if relative_path is None:
                continue
            embeds.append(self._note_embed(relative_path, section=section))
        return embeds

    def _document_section_embed_lines(
        self,
        documents: list[Document],
        *,
        document_paths: dict[Document, Path],
        titles: list[str],
        section: str,
    ) -> list[str]:
        by_title = {document.title.casefold(): document for document in documents}
        embeds: list[str] = []
        for title in titles:
            document = by_title.get(title.casefold())
            if document is None:
                continue
            relative_path = document_paths.get(document)
            if relative_path is None:
                continue
            embeds.append(self._note_embed(relative_path, section=section))
        return embeds

    def _build_base_files(
        self,
        *,
        has_campaign: bool,
        has_reference_documents: bool,
        has_campaign_notes: bool,
        has_pc_sheets: bool,
        has_session_logs: bool,
        has_prep: bool,
    ) -> dict[Path, str]:
        base_files: dict[Path, str] = {}
        if has_campaign:
            base_files[BASE_FILE_BY_SECTION["campaign"]] = self._base_file_content(
                folder_path="Campaign",
                filter_expression='dma_kind == "campaign_entity"',
                properties={
                    "file.name": "Name",
                    "entity_type": "Type",
                    "current_location": "Location",
                    "parent": "Parent",
                    "owner": "Owner",
                    "details_role": "Role",
                    "details_status": "Status",
                    "details_category": "Category",
                    "summary": "Summary",
                    "updated_at": "Updated",
                },
                view_name="Entities",
                order=[
                    "file.name",
                    "entity_type",
                    "current_location",
                    "parent",
                    "owner",
                    "details_role",
                    "details_status",
                    "details_category",
                    "summary",
                    "updated_at",
                ],
                group_by="entity_type",
            )
            base_files[BASE_FILE_BY_SECTION["command_center_timeline"]] = (
                self._base_file_content(
                    folder_path="Campaign",
                    filter_expression='entity_type == "event"',
                    properties={
                        "file.name": "Event",
                        "details_timeline_position": "Timeline",
                        "details_scheduled_for": "Scheduled",
                        "details_status": "Status",
                        "details_date_label": "Date",
                        "details_consequences": "Consequences",
                        "summary": "Summary",
                        "updated_at": "Updated",
                    },
                    view_name="Timeline",
                    order=[
                        "details_timeline_position",
                        "details_scheduled_for",
                        "details_date_label",
                        "file.name",
                        "details_status",
                        "details_consequences",
                        "summary",
                        "updated_at",
                    ],
                )
            )
            base_files[BASE_FILE_BY_SECTION["command_center_npcs"]] = (
                self._base_file_content(
                    folder_path="Campaign",
                    filter_expression='entity_type == "npc"',
                    properties={
                        "file.name": "NPC",
                        "details_role": "Role",
                        "details_status": "Status",
                        "current_location": "Location",
                        "details_languages": "Languages",
                        "summary": "Summary",
                        "updated_at": "Updated",
                    },
                    view_name="NPC Roster",
                    order=[
                        "file.name",
                        "details_role",
                        "details_status",
                        "current_location",
                        "details_languages",
                        "summary",
                        "updated_at",
                    ],
                )
            )
            base_files[BASE_FILE_BY_SECTION["command_center_locations"]] = (
                self._base_file_content(
                    folder_path="Campaign",
                    filter_expression='entity_type == "location"',
                    properties={
                        "file.name": "Location",
                        "parent": "Parent",
                        "details_category": "Category",
                        "details_region": "Region",
                        "details_environment": "Environment",
                        "summary": "Summary",
                        "updated_at": "Updated",
                    },
                    view_name="Location Atlas",
                    order=[
                        "file.name",
                        "parent",
                        "details_category",
                        "details_region",
                        "details_environment",
                        "summary",
                        "updated_at",
                    ],
                )
            )
        if has_reference_documents:
            base_files[BASE_FILE_BY_SECTION["library"]] = self._base_file_content(
                folder_path="Library",
                filter_expression='document_kind == "reference"',
                properties={
                    "file.name": "Title",
                    "source_name": "Source",
                    "visibility_scope": "Visibility",
                    "review_status": "Review",
                    "source_class": "Source Class",
                    "summary": "Summary",
                    "updated_at": "Updated",
                },
                view_name="Reference Library",
                order=[
                    "file.name",
                    "source_name",
                    "source_class",
                    "visibility_scope",
                    "review_status",
                    "summary",
                    "updated_at",
                ],
            )
        if has_campaign_notes:
            base_files[BASE_FILE_BY_SECTION["notes"]] = self._base_file_content(
                folder_path="Notes",
                filter_expression='document_kind == "campaign_note"',
                properties={
                    "file.name": "Title",
                    "visibility_scope": "Visibility",
                    "audience_intended_reader": "Reader",
                    "summary": "Summary",
                    "updated_at": "Updated",
                },
                view_name="Campaign Notes",
                order=[
                    "file.name",
                    "visibility_scope",
                    "audience_intended_reader",
                    "summary",
                    "updated_at",
                ],
            )
        if has_pc_sheets:
            base_files[BASE_FILE_BY_SECTION["sheets"]] = self._base_file_content(
                folder_path="Sheets",
                filter_expression='document_kind == "pc_sheet"',
                properties={
                    "file.name": "Player",
                    "pc_name": "PC",
                    "class_name": "Class",
                    "level": "Level",
                    "xp": "XP",
                    "alignment": "Alignment",
                    "armor_class": "AC",
                    "class_dc": "Class DC",
                    "initiative": "Init",
                    "perception": "Perception",
                    "fortitude": "Fort",
                    "reflex": "Ref",
                    "will": "Will",
                    "vision": "Vision",
                    "healing_role": "Healing",
                    "scouting_role": "Scout",
                    "frontline_role": "Frontline",
                    "languages": "Languages",
                    "resistances": "Resistances",
                    "speed": "Speed",
                    "key_ability": "Key Ability",
                    "special_abilities": "Specials",
                    "updated_at": "Updated",
                },
                view_name="PC Sheets",
                order=[
                    "file.name",
                    "pc_name",
                    "class_name",
                    "level",
                    "xp",
                    "alignment",
                    "armor_class",
                    "class_dc",
                    "initiative",
                    "perception",
                    "fortitude",
                    "reflex",
                    "will",
                    "vision",
                    "healing_role",
                    "scouting_role",
                    "frontline_role",
                    "languages",
                    "resistances",
                    "speed",
                    "key_ability",
                    "special_abilities",
                    "updated_at",
                ],
            )
            base_files[BASE_FILE_BY_SECTION["party_overview"]] = self._base_file_content(
                folder_path="Sheets",
                filter_expression='document_kind == "pc_sheet"',
                properties={
                    "file.name": "Player",
                    "pc_name": "PC",
                    "class_name": "Class",
                    "level": "Level",
                    "xp": "XP",
                    "alignment": "Alignment",
                    "armor_class": "AC",
                    "class_dc": "Class DC",
                    "initiative": "Init",
                    "perception": "Perception",
                    "fortitude": "Fort",
                    "reflex": "Ref",
                    "will": "Will",
                    "vision": "Vision",
                    "healing_role": "Healing",
                    "scouting_role": "Scout",
                    "frontline_role": "Frontline",
                    "languages": "Languages",
                    "resistances": "Resistances",
                    "medicine": "Medicine",
                    "stealth": "Stealth",
                    "thievery": "Thievery",
                    "athletics": "Athletics",
                    "special_abilities": "Specials",
                    "updated_at": "Updated",
                },
                view_name="Party Overview",
                order=[
                    "file.name",
                    "pc_name",
                    "class_name",
                    "level",
                    "xp",
                    "alignment",
                    "armor_class",
                    "class_dc",
                    "initiative",
                    "perception",
                    "fortitude",
                    "reflex",
                    "will",
                    "vision",
                    "healing_role",
                    "scouting_role",
                    "frontline_role",
                    "languages",
                    "resistances",
                    "medicine",
                    "stealth",
                    "thievery",
                    "athletics",
                    "special_abilities",
                    "updated_at",
                ],
            )
        if has_session_logs:
            base_files[BASE_FILE_BY_SECTION["sessions"]] = self._base_file_content(
                folder_path="Sessions",
                filter_expression='document_kind == "session_log"',
                properties={
                    "file.name": "Title",
                    "source_name": "Source",
                    "visibility_scope": "Visibility",
                    "summary": "Summary",
                    "updated_at": "Updated",
                },
                view_name="Sessions",
                order=[
                    "file.name",
                    "source_name",
                    "visibility_scope",
                    "summary",
                    "updated_at",
                ],
            )
        if has_prep:
            base_files[BASE_FILE_BY_SECTION["prep"]] = self._base_file_content(
                folder_path="Prep",
                filter_expression='document_kind == "session_prep"',
                properties={
                    "file.name": "Title",
                    "source_name": "Source",
                    "visibility_scope": "Visibility",
                    "summary": "Summary",
                    "updated_at": "Updated",
                },
                view_name="Prep",
                order=[
                    "file.name",
                    "source_name",
                    "visibility_scope",
                    "summary",
                    "updated_at",
                ],
            )
        return base_files

    def _base_file_content(
        self,
        *,
        folder_path: str,
        filter_expression: str,
        properties: dict[str, str],
        view_name: str,
        order: list[str],
        group_by: str | None = None,
    ) -> str:
        config: dict[str, Any] = {
            "filters": {
                "and": [
                    'file.ext == "md"',
                    f'file.inFolder("{folder_path}")',
                    filter_expression,
                ]
            },
            "properties": {
                property_name: {"displayName": display_name}
                for property_name, display_name in properties.items()
            },
            "views": [
                {
                    "type": "table",
                    "name": view_name,
                    **(
                        {"groupBy": {"property": group_by, "direction": "ASC"}}
                        if group_by
                        else {}
                    ),
                    "order": order,
                }
            ],
        }
        return json.dumps(config, indent=2) + "\n"

    def _entity_tags(self, entity: dict[str, Any]) -> list[str]:
        tags = [
            "dma/generated",
            "dma/entity",
            ENTITY_TAG_BY_TYPE[entity["entity_type"]],
            *entity.get("tags", []),
        ]
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            cleaned = str(tag).strip().lstrip("#")
            if not cleaned:
                continue
            key = cleaned.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(cleaned)
        return normalized

    def _entity_detail_lines(self, entity: dict[str, Any]) -> dict[str, str]:
        details = entity.get("details") or {}
        lines: dict[str, str] = {}
        for key, value in details.items():
            if value in (None, "", [], {}):
                continue
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                lines[label] = ", ".join(self._inline(item) for item in value)
            elif isinstance(value, dict):
                lines[label] = "; ".join(
                    f"{nested_key}={self._inline(nested_value)}"
                    for nested_key, nested_value in value.items()
                )
            else:
                lines[label] = self._inline(value)
        return lines

    def _relationship_specs(
        self, entity: dict[str, Any], entity_paths: dict[int, Path]
    ) -> list[str]:
        relationships = entity.get("relationships") or []
        specs: list[str] = []
        for relationship in relationships:
            related = relationship.get("related_entity")
            related_link = self._reference_link(related, entity_paths)
            if not related_link:
                continue
            spec = f"{relationship['relationship_type']} -> {related_link}"
            if relationship.get("notes"):
                spec = f"{spec} -> {self._inline(relationship['notes'])}"
            specs.append(spec)
        return specs

    def _reference_link(
        self, reference: dict[str, Any] | None, entity_paths: dict[int, Path]
    ) -> str | None:
        if not reference:
            return None
        relative_path = entity_paths.get(reference["id"])
        if relative_path is None:
            return reference["name"]
        return wikilink_for_path(relative_path, alias=reference["name"])

    def _entity_ref(self, entity: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": entity["id"],
            "entity_type": entity["entity_type"],
            "name": entity["name"],
            "stable_key": entity["stable_key"],
        }

    def _entity_detail_payload(self, entity: dict[str, Any]) -> dict[str, Any]:
        details = entity.get("details") or {}
        payload: dict[str, Any] = {}
        for key, value in details.items():
            if value in (None, "", [], {}):
                continue
            payload[key] = value
        return payload

    def _entity_relationship_payload(
        self, entity: dict[str, Any], entity_paths: dict[int, Path]
    ) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for relationship in entity.get("relationships") or []:
            related = relationship.get("related_entity")
            related_link = self._reference_link(related, entity_paths)
            if not related_link:
                continue
            payload.append(
                {
                    "type": relationship["relationship_type"],
                    "target": related_link,
                    "notes": relationship.get("notes"),
                }
            )
        return payload

    def _entity_overview_lines(
        self,
        entity: dict[str, Any],
        *,
        entity_paths: dict[int, Path],
        entities: list[dict[str, Any]],
    ) -> list[str]:
        lines: list[str] = []
        exclude_entity_ids = {entity["id"]}
        for paragraph in [entity.get("summary"), entity.get("description")]:
            if not paragraph:
                continue
            lines.append(
                self._linkify_text(
                    self._inline(paragraph),
                    entity_paths=entity_paths,
                    entities=entities,
                    exclude_entity_ids=exclude_entity_ids,
                )
            )
            lines.append("")
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def _entity_detail_section_lines(
        self,
        entity: dict[str, Any],
        *,
        entity_paths: dict[int, Path],
        entities: list[dict[str, Any]],
    ) -> list[str]:
        lines: list[str] = []
        exclude_entity_ids = {entity["id"]}
        for field_label, field_value in self._entity_detail_lines(entity).items():
            lines.append(f"### {field_label}")
            lines.append(
                self._linkify_text(
                    field_value,
                    entity_paths=entity_paths,
                    entities=entities,
                    exclude_entity_ids=exclude_entity_ids,
                )
            )
            lines.append("")
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def _entity_relationship_section_lines(
        self,
        entity: dict[str, Any],
        *,
        entity_paths: dict[int, Path],
    ) -> list[str]:
        lines: list[str] = []
        for relationship in entity.get("relationships") or []:
            related = relationship.get("related_entity")
            related_link = self._reference_link(related, entity_paths)
            if not related_link:
                continue
            sentence = f"- `{relationship['relationship_type']}` with {related_link}"
            if relationship.get("notes"):
                sentence += f": {self._inline(relationship['notes'])}"
            lines.append(sentence)
        return lines

    def _source_references_for_entity(
        self,
        entity: dict[str, Any],
        *,
        supporting_documents: list[Document],
        document_paths: dict[Document, Path],
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for document in supporting_documents:
            excerpt_payload = self._document_excerpt_for_entity(
                document, entity["name"]
            )
            if not excerpt_payload:
                continue
            title_key = document.title.casefold()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            path = document_paths.get(document)
            source_name = document.source_name or document.title
            references.append(
                {
                    "title": document.title,
                    "link": (
                        wikilink_for_path(path, alias=document.title)
                        if path is not None
                        else document.title
                    ),
                    "source_name": source_name,
                    "source_file": Path(source_name).name,
                    "page": excerpt_payload.get("page"),
                    "excerpt": excerpt_payload["excerpt"],
                }
            )
            if len(references) >= limit:
                break
        return references

    def _entity_image_link(
        self,
        entity: dict[str, Any],
        *,
        supporting_documents: list[Document],
    ) -> str | None:
        entity_name = str(entity.get("name") or "").strip()
        if not entity_name:
            return None
        for document in supporting_documents:
            excerpt_payload = self._document_excerpt_for_entity(document, entity_name)
            if not excerpt_payload:
                continue
            page = excerpt_payload.get("page")
            if page is None:
                continue
            asset_path = self._reference_asset_for_page(document, page=page)
            if asset_path is None:
                continue
            return self._asset_wikilink(asset_path)
        return None

    def _document_excerpt_for_entity(
        self, document: Document, entity_name: str, *, context_chars: int = 200
    ) -> dict[str, Any] | None:
        for page_number, searchable_text in self._document_text_pages(document):
            if not searchable_text.strip():
                continue
            match = re.search(re.escape(entity_name), searchable_text, re.IGNORECASE)
            if not match:
                continue
            start = max(0, match.start() - context_chars)
            end = min(len(searchable_text), match.end() + context_chars)
            snippet = searchable_text[start:end]
            snippet = re.sub(r"\s+", " ", snippet).strip()
            if start > 0:
                snippet = f"... {snippet}"
            if end < len(searchable_text):
                snippet = f"{snippet} ..."
            return {"excerpt": snippet, "page": page_number}
        return None

    def _document_text_pages(self, document: Document) -> list[tuple[int | None, str]]:
        _, body = split_frontmatter(document.content or "")
        if self._is_pdf_document(document):
            pages = self._pdf_pages_for_document(document, body=body)
            if pages:
                return pages
        searchable_text = "\n\n".join(
            part
            for part in [document.summary or "", body]
            if part and str(part).strip()
        )
        if not searchable_text.strip():
            return []
        return [(None, searchable_text)]

    def _pdf_pages_for_document(
        self, document: Document, *, body: str
    ) -> list[tuple[int, str]]:
        from_content = self._pdf_pages_from_text(body)
        if from_content:
            return from_content

        if not document.url:
            return []
        cache_key = document.url
        if cache_key in self._pdf_page_cache:
            return self._pdf_page_cache[cache_key]

        source_path = Path(document.url).expanduser()
        if not source_path.exists():
            self._pdf_page_cache[cache_key] = []
            return []
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(source_path), "-"],
                check=True,
                capture_output=True,
                text=True,
                timeout=PDFTOTEXT_TIMEOUT_SECONDS,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            self._pdf_page_cache[cache_key] = []
            return []

        pages = self._pdf_pages_from_text(result.stdout)
        self._pdf_page_cache[cache_key] = pages
        return pages

    def _pdf_pages_from_text(self, text: str) -> list[tuple[int, str]]:
        if not text.strip():
            return []
        if "[Page " in text:
            pages: list[tuple[int, str]] = []
            current_page: int | None = None
            current_lines: list[str] = []
            for raw_line in text.splitlines():
                match = PDF_PAGE_MARKER_RE.match(raw_line.strip())
                if match:
                    if current_page is not None:
                        page_text = "\n".join(current_lines).strip()
                        if page_text:
                            pages.append((current_page, page_text))
                    current_page = int(match.group("page"))
                    current_lines = []
                    continue
                current_lines.append(raw_line)
            if current_page is not None:
                page_text = "\n".join(current_lines).strip()
                if page_text:
                    pages.append((current_page, page_text))
            if pages:
                return pages

        chunks = [chunk.strip() for chunk in text.split("\f")]
        pages = [
            (index, chunk)
            for index, chunk in enumerate(chunks, start=1)
            if chunk and chunk.strip()
        ]
        return pages

    def _is_pdf_document(self, document: Document) -> bool:
        candidates = [document.url or "", document.source_name or "", document.title]
        return any(str(candidate).lower().endswith(".pdf") for candidate in candidates)

    def _related_entities_for_document(
        self,
        document: Document,
        entity_payloads: list[dict[str, Any]],
        *,
        limit: int | None = 12,
    ) -> list[dict[str, Any]]:
        _, body = split_frontmatter(document.content or "")
        searchable_text = "\n".join(
            part
            for part in [document.title, document.summary or "", body]
            if part and str(part).strip()
        )
        if not searchable_text.strip():
            return []

        related: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for entity in sorted(
            entity_payloads, key=lambda item: len(item["name"]), reverse=True
        ):
            if entity["id"] in seen_ids:
                continue
            if self._contains_entity_reference(searchable_text, entity["name"]):
                seen_ids.add(entity["id"])
                related.append(self._entity_ref(entity))
        if limit is None:
            return related
        return related[:limit]

    def _contains_entity_reference(self, text: str, entity_name: str) -> bool:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(entity_name)}(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        return pattern.search(text) is not None

    def _strip_duplicate_title(self, body: str, title: str) -> str:
        lines = body.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and lines[0].strip() == f"# {title}":
            lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        return "\n".join(lines).strip()

    def _audience_metadata(self, visibility_scope: str) -> dict[str, Any]:
        gm_only = visibility_scope != "player_safe"
        return {
            "visibility_scope": visibility_scope,
            "intended_reader": "gm" if gm_only else "table",
            "can_share_with_party": not gm_only,
        }

    def _audience_section_lines(self, visibility_scope: str) -> list[str]:
        if visibility_scope == "player_safe":
            return [
                "- This note is marked `player_safe` and can be shared with the table.",
                "- Double-check any linked references before sharing if they point into GM-only material.",
            ]
        return [
            "- This note is marked `gm_only` and should be treated as spoiler-heavy prep material.",
            "- Share paraphrased discoveries, rumors, and outcomes with the party instead of the raw adventure text.",
        ]

    def _reference_index_entries(
        self, body: str, *, labels: set[str], audience: str
    ) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        current_chapter: str | None = None
        current_area: str | None = None
        current_title: str | None = None
        lines = body.splitlines()
        known_chapter_titles = self._chapter_titles_from_lines(lines)

        for index, raw_line in enumerate(lines):
            line = self._inline(raw_line)
            if not line:
                continue

            chapter_title = self._chapter_title_from_lines(
                index, lines, known_titles=known_chapter_titles
            )
            if chapter_title:
                current_chapter = chapter_title
                continue

            area_match = AREA_HEADER_RE.match(raw_line.rstrip())
            if area_match:
                current_area = area_match.group("area")
                current_title = self._clean_area_title(area_match.group("title"))
                continue

            label_match = REFERENCE_LABEL_RE.match(line)
            if not label_match:
                continue
            label = label_match.group("label").casefold()
            if label not in labels:
                continue

            detail_parts = [label_match.group("text").strip()]
            for next_index, look_ahead in enumerate(
                lines[index + 1 : index + 4], start=index + 1
            ):
                next_line = self._inline(look_ahead)
                if not next_line:
                    break
                if self._chapter_title_from_lines(
                    next_index, lines, known_titles=known_chapter_titles
                ) or AREA_HEADER_RE.match(look_ahead.rstrip()):
                    break
                if REFERENCE_LABEL_RE.match(next_line):
                    break
                detail_parts.append(next_line)

            details = self._clean_reference_detail(
                " ".join(part for part in detail_parts if part)
            )
            if not details:
                continue

            entries.append(
                {
                    "kind": self._reference_entry_kind(label),
                    "subtype": self._reference_entry_subtype(
                        label=label,
                        title=current_title or "",
                        details=details,
                    ),
                    "chapter": current_chapter or "",
                    "area": current_area or "",
                    "title": current_title or "",
                    "details": details,
                    "audience": audience,
                }
            )

        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for entry in entries:
            key = (
                entry["kind"].casefold(),
                entry["chapter"].casefold(),
                entry["area"].casefold(),
                entry["details"].casefold(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        return deduped

    def _reference_entry_kind(self, label: str) -> str:
        normalized = label.casefold()
        if normalized.startswith("creature"):
            return "encounter"
        if normalized.startswith("hazard"):
            return "hazard"
        if normalized == "story award":
            return "story_award"
        return normalized.replace(" ", "_")

    def _reference_entry_subtype(self, *, label: str, title: str, details: str) -> str:
        normalized = label.casefold()
        if normalized.startswith("creature"):
            return "monster"
        if not normalized.startswith("hazard"):
            return self._reference_entry_kind(label)
        haystack = f"{title} {details}".casefold()
        if any(
            token in haystack
            for token in (
                "haunt",
                "haunting",
                "ghost",
                "spirit",
                "specter",
                "phantom",
                "poltergeist",
            )
        ):
            return "haunt"
        if any(
            token in haystack
            for token in (
                "trap",
                "rune",
                "scythe",
                "pit",
                "snare",
                "dart",
                "spear",
                "blade",
                "glyph",
            )
        ):
            return "trap"
        return "hazard"

    def _reference_entries_by_subtype(
        self, entries: list[dict[str, str]], *, subtype: str
    ) -> list[dict[str, str]]:
        return [entry for entry in entries if entry.get("subtype") == subtype]

    def _chapter_titles_from_lines(self, lines: list[str]) -> set[str]:
        titles: set[str] = set()
        for raw_line in lines:
            match = CHAPTER_HEADER_RE.match(raw_line.strip())
            if not match:
                continue
            title = self._clean_chapter_title(match.group("title"))
            if title:
                titles.add(title.casefold())
        return titles

    def _chapter_title_from_lines(
        self, index: int, lines: list[str], *, known_titles: set[str]
    ) -> str | None:
        match = CHAPTER_HEADER_RE.match(lines[index].strip())
        if not match:
            return None

        title = self._clean_chapter_title(match.group("title"))
        if title:
            return title

        for look_ahead in lines[index + 1 : index + 4]:
            candidate = self._clean_chapter_title(look_ahead)
            if candidate and (
                not known_titles or candidate.casefold() in known_titles
            ):
                return candidate
        return None

    def _clean_chapter_title(self, value: str) -> str | None:
        if AREA_HEADER_RE.match(value.strip()):
            return None
        text = self._inline(value)
        if not text:
            return None
        text = DOT_LEADER_RE.sub("", text).strip(" :-")
        text = re.sub(r"\b\d+\b$", "", text).strip()
        if not text:
            return None
        if text.casefold() in {"synopsis", "treasure"}:
            return None
        if re.search(r"\b(?:CREATURE|HAZARD)\s+\d+\b", text, re.IGNORECASE):
            return None
        if text.split()[-1].casefold() in {"a", "an", "and", "of", "the", "to"}:
            return None
        if len(text) > 70:
            return None
        return self._title_case_compact(text)

    def _clean_area_title(self, value: str) -> str:
        text = self._inline(value)
        text = AREA_DIFFICULTY_RE.sub("", text)
        text = REFERENCE_LABEL_ANYWHERE_RE.split(text, maxsplit=1)[0]
        text = re.split(r"\bCHAPTER\s+\d+:?", text, maxsplit=1, flags=re.IGNORECASE)[0]
        return self._title_case_compact(text)

    def _clean_reference_detail(self, value: str) -> str:
        text = self._inline(value)
        text = re.split(r"\bCHAPTER\s+\d+:?", text, maxsplit=1, flags=re.IGNORECASE)[0]
        text = re.split(
            r"\b(?:Adventure Toolbox|Gazetteer|Environmental Cues):?",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        embedded_label = REFERENCE_LABEL_ANYWHERE_RE.search(text)
        if embedded_label and embedded_label.start() > 80:
            text = text[: embedded_label.start()].strip()
        return text[:500].strip()

    def _reference_index_section_lines(
        self, entries: list[dict[str, str]]
    ) -> list[str]:
        lines: list[str] = []
        for entry in entries:
            header_bits = [
                bit for bit in [entry.get("area"), entry.get("title")] if bit
            ]
            section_title = " - ".join(header_bits) if header_bits else "Unscoped Entry"
            lines.append(f"### {section_title}")
            context_bits = [f"`{entry['kind']}`"]
            if entry.get("subtype") and entry.get("subtype") != entry.get("kind"):
                context_bits.append(f"Subtype: {entry['subtype']}")
            if entry.get("chapter"):
                context_bits.append(entry["chapter"])
            if entry.get("audience"):
                context_bits.append(f"Audience: {entry['audience']}")
            lines.append(f"- {' | '.join(context_bits)}")
            lines.append(f"- {entry['details']}")
            lines.append("")
        while lines and not lines[-1].strip():
            lines.pop()
        return lines

    def _title_case_compact(self, value: str) -> str:
        text = self._inline(value)
        if not text:
            return ""
        text = re.sub(
            r"\b(?:TRIVIAL|LOW|MODERATE|SEVERE|EXTREME)\s+\d+\b$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        return text.title()

    def _render_pc_sheet_note(
        self,
        document: Document,
        *,
        folder: str,
        body: str,
        entity_paths: dict[int, Path],
        related_entities: list[dict[str, Any]],
        linkable_entities: list[dict[str, Any]],
        entity_payload_by_id: dict[int, dict[str, Any]],
        note_path: Path,
    ) -> str:
        export_title = self._document_export_title(document)
        pc_entity = self._related_pc_entity(
            related_entities=related_entities,
            entity_payload_by_id=entity_payload_by_id,
        )
        latest_sheet = (pc_entity or {}).get("latest_sheet_version") or {}
        payload = latest_sheet.get("payload") or {}
        factions: list[str] = []
        current_location = None
        if pc_entity is not None:
            current_location = self._reference_link(
                pc_entity.get("current_location"), entity_paths
            )
            factions = [
                self._reference_link(relationship.get("related_entity"), entity_paths)
                or ""
                for relationship in pc_entity.get("relationships") or []
                if relationship.get("relationship_type") == "member"
            ]
            factions = [faction for faction in factions if faction]

        metadata = {
            "dma_kind": "document",
            "vault_sync": True,
            "dma_sync_role": "vault-managed",
            "document_kind": document.kind,
            "doc_id": document.id,
            "title": export_title,
            "source_name": document.source_name,
            "source_class": document.source_class,
            "privacy_scope": document.privacy_scope,
            "review_status": document.review_status,
            "visibility_scope": document.visibility_scope,
            "rag_eligible": document.rag_eligible,
            "train_eligible": document.train_eligible,
            "summary": self._inline(document.summary or ""),
            "source_url": document.url,
            "pc_name": (pc_entity or {}).get("name"),
            "version_number": latest_sheet.get("version_number"),
            "class_name": payload.get("class_name"),
            "level": payload.get("level"),
            "xp": payload.get("xp"),
            "alignment": payload.get("alignment"),
            "ancestry": payload.get("ancestry"),
            "heritage": payload.get("heritage"),
            "background": payload.get("background"),
            "key_ability": payload.get("keyability"),
            "size_name": (payload.get("size") or {}).get("name"),
            "speed": (payload.get("vitals") or {}).get("speed"),
            "vision": self._sheet_vision(payload),
            "healing_role": self._sheet_healing_role(payload),
            "scouting_role": self._sheet_scouting_role(payload),
            "frontline_role": self._sheet_frontline_role(payload),
            "languages": payload.get("languages"),
            "resistances": payload.get("resistances"),
            "special_abilities": payload.get("specials"),
            "strength": (payload.get("attributes") or {}).get("str"),
            "dexterity": (payload.get("attributes") or {}).get("dex"),
            "constitution": (payload.get("attributes") or {}).get("con"),
            "intelligence": (payload.get("attributes") or {}).get("int"),
            "wisdom": (payload.get("attributes") or {}).get("wis"),
            "charisma": (payload.get("attributes") or {}).get("cha"),
            "armor_class": (payload.get("ac") or {}).get("acTotal"),
            "shield_bonus": (payload.get("ac") or {}).get("shieldBonus"),
            "class_dc": (payload.get("proficiencies") or {}).get("classDC"),
            "perception": (payload.get("proficiencies") or {}).get("perception"),
            "initiative": (payload.get("proficiencies") or {}).get("perception"),
            "fortitude": (payload.get("proficiencies") or {}).get("fortitude"),
            "reflex": (payload.get("proficiencies") or {}).get("reflex"),
            "will": (payload.get("proficiencies") or {}).get("will"),
            "acrobatics": (payload.get("proficiencies") or {}).get("acrobatics"),
            "arcana": (payload.get("proficiencies") or {}).get("arcana"),
            "athletics": (payload.get("proficiencies") or {}).get("athletics"),
            "crafting": (payload.get("proficiencies") or {}).get("crafting"),
            "deception": (payload.get("proficiencies") or {}).get("deception"),
            "diplomacy": (payload.get("proficiencies") or {}).get("diplomacy"),
            "intimidation": (payload.get("proficiencies") or {}).get("intimidation"),
            "medicine": (payload.get("proficiencies") or {}).get("medicine"),
            "nature": (payload.get("proficiencies") or {}).get("nature"),
            "occultism": (payload.get("proficiencies") or {}).get("occultism"),
            "performance": (payload.get("proficiencies") or {}).get("performance"),
            "religion": (payload.get("proficiencies") or {}).get("religion"),
            "society": (payload.get("proficiencies") or {}).get("society"),
            "stealth": (payload.get("proficiencies") or {}).get("stealth"),
            "survival": (payload.get("proficiencies") or {}).get("survival"),
            "thievery": (payload.get("proficiencies") or {}).get("thievery"),
            "skills": payload.get("skills"),
            "current_location": current_location,
            "factions": factions,
            "related_entities": [
                self._reference_link(entity, entity_paths)
                for entity in related_entities
                if self._reference_link(entity, entity_paths)
            ],
            "updated_at": document.updated_at.isoformat(),
            "tags": [
                "dma/generated",
                "dma/document",
                f"dma/document/{document.kind}",
                f"dma/folder/{folder.lower()}",
            ],
        }
        lines = [build_frontmatter(metadata), f"# {export_title}", ""]
        managed_sections: list[str] = []
        if related_entities:
            managed_sections.append("## Linked Entities")
            for entity in related_entities:
                managed_sections.append(
                    f"- {self._reference_link(entity, entity_paths)}"
                )
            managed_sections.append("")

        if pc_entity is not None:
            sheet_snapshot = self._sheet_snapshot_lines(pc_entity, entity_paths)
            if sheet_snapshot:
                managed_sections.append("## Sheet Snapshot")
                managed_sections.extend(sheet_snapshot)
                managed_sections.append("")

        if managed_sections:
            lines.append(
                self._managed_block(
                    "document-generated", "\n".join(managed_sections).strip()
                )
            )
            lines.append("")

        lines.append("## DMA Editable Source")
        raw_json = self._parse_json_body(body)
        if raw_json is not None:
            editable_source = "\n".join(
                ["```json", json.dumps(raw_json, indent=2, sort_keys=True), "```"]
            )
        else:
            editable_source = body.strip()
        lines.append(self._editable_block("editable-source", editable_source))
        lines.append("")
        lines.append("## DM Working Notes")
        lines.append(self._editable_block("dm-working-notes", ""))
        return "\n".join(lines).strip() + "\n"

    def _document_export_title(self, document: Document) -> str:
        if document.kind == "pc_sheet":
            for candidate in (document.source_name, document.url):
                if not candidate:
                    continue
                source_path = Path(str(candidate))
                if source_path.stem:
                    return source_path.stem
        return document.title

    def _related_pc_entity(
        self,
        *,
        related_entities: list[dict[str, Any]],
        entity_payload_by_id: dict[int, dict[str, Any]],
    ) -> dict[str, Any] | None:
        for entity in related_entities:
            if entity.get("entity_type") != "pc":
                continue
            pc_entity = entity_payload_by_id.get(entity["id"])
            if pc_entity is not None:
                return pc_entity
        return None

    def _sheet_snapshot_lines(
        self, entity: dict[str, Any], entity_paths: dict[int, Path]
    ) -> list[str]:
        latest_sheet = entity.get("latest_sheet_version") or {}
        payload = latest_sheet.get("payload") or {}
        if not payload:
            return []

        lines = [
            f"- PC: {self._reference_link(self._entity_ref(entity), entity_paths)}",
            f"- Version: {latest_sheet.get('version_number')}",
        ]
        for label, value in (
            ("Class", payload.get("class_name")),
            ("Level", payload.get("level")),
            ("Ancestry", payload.get("ancestry")),
            ("Heritage", payload.get("heritage")),
            ("Background", payload.get("background")),
        ):
            if value not in (None, "", [], {}):
                lines.append(f"- {label}: {self._inline(value)}")

        location = self._reference_link(entity.get("current_location"), entity_paths)
        if location:
            lines.append(f"- Location: {location}")

        factions: list[str] = [
            self._reference_link(relationship.get("related_entity"), entity_paths) or ""
            for relationship in entity.get("relationships") or []
            if relationship.get("relationship_type") == "member"
        ]
        factions = [faction for faction in factions if faction]
        if factions:
            lines.append(f"- Factions: {', '.join(factions)}")

        for label, value in (
            ("Languages", payload.get("languages")),
            ("Goals", payload.get("goals")),
            ("Hooks", payload.get("hooks")),
            ("Items", payload.get("items")),
            ("Spells", payload.get("spells")),
            ("Feats", payload.get("feats")),
        ):
            rendered = self._sheet_value_text(value)
            if rendered:
                lines.append(f"- {label}: {rendered}")

        abilities = payload.get("attributes") or {}
        ability_pairs = [
            ("STR", abilities.get("str")),
            ("DEX", abilities.get("dex")),
            ("CON", abilities.get("con")),
            ("INT", abilities.get("int")),
            ("WIS", abilities.get("wis")),
            ("CHA", abilities.get("cha")),
        ]
        rendered_abilities = [
            f"{label} {value}" for label, value in ability_pairs if value not in (None, "")
        ]
        if rendered_abilities:
            lines.append(f"- Ability Scores: {', '.join(rendered_abilities)}")

        ac = payload.get("ac") or {}
        defenses: list[str] = []
        if ac.get("acTotal") not in (None, ""):
            defenses.append(f"AC {ac['acTotal']}")
        if ac.get("shieldBonus") not in (None, "", 0, "0"):
            defenses.append(f"Shield {self._inline(ac['shieldBonus'])}")
        proficiencies = payload.get("proficiencies") or {}
        if proficiencies.get("perception") not in (None, ""):
            defenses.append(f"Perception {proficiencies['perception']}")
            defenses.append(f"Initiative {proficiencies['perception']}")
        if defenses:
            lines.append(f"- Core Defenses: {', '.join(defenses)}")

        saves = [
            ("Fort", proficiencies.get("fortitude")),
            ("Ref", proficiencies.get("reflex")),
            ("Will", proficiencies.get("will")),
        ]
        rendered_saves = [
            f"{label} {value}" for label, value in saves if value not in (None, "")
        ]
        if rendered_saves:
            lines.append(f"- Saves: {', '.join(rendered_saves)}")

        return lines

    def _sheet_value_text(self, value: Any) -> str | None:
        if value in (None, "", [], {}):
            return None
        if isinstance(value, list):
            rendered_items = []
            for item in value:
                if isinstance(item, dict):
                    name = item.get("name")
                    rendered_items.append(
                        self._inline(name or json.dumps(item, sort_keys=True))
                    )
                else:
                    rendered_items.append(self._inline(item))
            rendered_items = [item for item in rendered_items if item]
            if not rendered_items:
                return None
            return ", ".join(rendered_items)
        if isinstance(value, dict):
            if "name" in value:
                return self._inline(value["name"])
            return "; ".join(
                f"{nested_key}={self._inline(nested_value)}"
                for nested_key, nested_value in value.items()
            )
        return self._inline(value)

    def _sheet_vision(self, payload: dict[str, Any]) -> str | None:
        specials = [self._inline(item) for item in payload.get("specials") or []]
        for special in specials:
            lowered = special.casefold()
            if "greater darkvision" in lowered:
                return "Greater Darkvision"
            if "darkvision" in lowered:
                return "Darkvision"
            if "low-light vision" in lowered:
                return "Low-Light Vision"
        return None

    def _sheet_healing_role(self, payload: dict[str, Any]) -> str:
        proficiencies = payload.get("proficiencies") or {}
        class_name = str(payload.get("class_name") or "").casefold()
        medicine = self._int_value(proficiencies.get("medicine"))
        if "cleric" in class_name or "healer" in class_name:
            return "Primary"
        if medicine is not None and medicine >= 2:
            return "Backup"
        return "Limited"

    def _sheet_scouting_role(self, payload: dict[str, Any]) -> str:
        proficiencies = payload.get("proficiencies") or {}
        stealth = self._int_value(proficiencies.get("stealth")) or 0
        perception = self._int_value(proficiencies.get("perception")) or 0
        vision = self._sheet_vision(payload) or ""
        if stealth >= 2 and perception >= 4:
            return "Primary"
        if stealth >= 2 or "Darkvision" in vision or "Low-Light" in vision:
            return "Support"
        return "Limited"

    def _sheet_frontline_role(self, payload: dict[str, Any]) -> str:
        ac = self._int_value((payload.get("ac") or {}).get("acTotal")) or 0
        fort = self._int_value((payload.get("proficiencies") or {}).get("fortitude")) or 0
        class_name = str(payload.get("class_name") or "").casefold()
        if ac >= 18 or fort >= 4 or any(
            token in class_name for token in ("guardian", "fighter", "champion")
        ):
            return "Primary"
        if ac >= 17:
            return "Support"
        return "Backline"

    def _int_value(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    def _party_quick_assignment_lines(
        self,
        pc_entities: list[dict[str, Any]],
        *,
        entity_paths: dict[int, Path],
    ) -> list[str]:
        lines: list[str] = []
        for label, stat_key in (
            ("Best Initiative", "perception"),
            ("Best Perception", "perception"),
            ("Best Medicine", "medicine"),
            ("Best Stealth", "stealth"),
            ("Best Thievery", "thievery"),
            ("Best Athletics", "athletics"),
        ):
            best_line = self._party_best_stat_line(
                pc_entities,
                stat_key=stat_key,
                label=label,
                entity_paths=entity_paths,
            )
            if best_line:
                lines.append(f"- {best_line}")
        return lines

    def _party_best_stat_line(
        self,
        pc_entities: list[dict[str, Any]],
        *,
        stat_key: str,
        label: str,
        entity_paths: dict[int, Path],
    ) -> str | None:
        best_entity: dict[str, Any] | None = None
        best_score: int | None = None
        for entity in pc_entities:
            payload = (entity.get("latest_sheet_version") or {}).get("payload") or {}
            proficiencies = payload.get("proficiencies") or {}
            score = self._int_value(proficiencies.get(stat_key))
            if score is None:
                continue
            if best_score is None or score > best_score:
                best_entity = entity
                best_score = score
        if best_entity is None or best_score is None:
            return None
        entity_link = self._reference_link(self._entity_ref(best_entity), entity_paths)
        if entity_link is None:
            entity_link = str(best_entity.get("name") or "Unknown PC")
        return f"{label}: {entity_link} ({best_score:+d})"

    def _party_coverage_lines(self, pc_entities: list[dict[str, Any]]) -> list[str]:
        if not pc_entities:
            return []
        healing_roles = Counter()
        scouting_roles = Counter()
        frontline_roles = Counter()
        darkvision = 0
        low_light = 0
        for entity in pc_entities:
            payload = (entity.get("latest_sheet_version") or {}).get("payload") or {}
            healing_roles[self._sheet_healing_role(payload)] += 1
            scouting_roles[self._sheet_scouting_role(payload)] += 1
            frontline_roles[self._sheet_frontline_role(payload)] += 1
            vision = self._sheet_vision(payload) or ""
            if vision == "Darkvision":
                darkvision += 1
            elif vision == "Low-Light Vision":
                low_light += 1
        return [
            f"- Healing coverage: Primary {healing_roles['Primary']}, Backup {healing_roles['Backup']}, Limited {healing_roles['Limited']}",
            f"- Scouting coverage: Primary {scouting_roles['Primary']}, Support {scouting_roles['Support']}, Limited {scouting_roles['Limited']}",
            f"- Frontline coverage: Primary {frontline_roles['Primary']}, Support {frontline_roles['Support']}, Backline {frontline_roles['Backline']}",
            f"- Vision coverage: Darkvision {darkvision}, Low-Light {low_light}",
        ]

    def _session_threat_fit_lines(
        self,
        pc_entities: list[dict[str, Any]],
        *,
        entity_paths: dict[int, Path],
    ) -> list[str]:
        if not pc_entities:
            return ["- No imported PC sheets are available yet."]

        coverage_lines = self._party_coverage_lines(pc_entities)
        lines: list[str] = []
        if coverage_lines:
            lines.extend(coverage_lines)

        for label, stat_key in (
            ("Likely social/scout lead", "perception"),
            ("Likely stealth lead", "stealth"),
            ("Likely trap/problem-solver", "thievery"),
            ("Likely recovery lead", "medicine"),
        ):
            best_line = self._party_best_stat_line(
                pc_entities,
                stat_key=stat_key,
                label=label,
                entity_paths=entity_paths,
            )
            if best_line:
                lines.append(f"- {best_line}")

        placeholder_count = 0
        for entity in pc_entities:
            payload = (entity.get("latest_sheet_version") or {}).get("payload") or {}
            class_name = str(payload.get("class_name") or "")
            ancestry = str(payload.get("ancestry") or "")
            if class_name.upper() == "TBD" or ancestry.upper() == "TBD":
                placeholder_count += 1
        if placeholder_count:
            lines.append(
                f"- Party completeness warning: {placeholder_count} sheet(s) are still placeholders, so the fit summary is useful but not final."
            )

        scouting_best = self._party_best_stat_line(
            pc_entities,
            stat_key="stealth",
            label="Scouting strength",
            entity_paths=entity_paths,
        )
        healing_best = self._party_best_stat_line(
            pc_entities,
            stat_key="medicine",
            label="Healing strength",
            entity_paths=entity_paths,
        )
        if scouting_best:
            lines.append(
                "- Session 1 risk note: the party looks capable of careful approach play, so reward cautious scouting around Gauntlight instead of forcing immediate combat."
            )
        else:
            lines.append(
                "- Session 1 risk note: if the party advances quickly, give extra descriptive warning before exterior danger so the table can slow down on purpose."
            )
        if healing_best:
            lines.append(
                "- Session 1 recovery note: the party has enough support to survive early attrition, so chip damage and eerie pressure are fair game."
            )
        return lines

    def _parse_json_body(self, body: str) -> dict[str, Any] | list[Any] | None:
        stripped = body.strip()
        if not stripped:
            return None
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
        return None

    def _linkify_markdown_text(
        self,
        text: str,
        *,
        entity_paths: dict[int, Path],
        entities: list[dict[str, Any]],
        exclude_entity_ids: set[int] | None = None,
    ) -> str:
        lines: list[str] = []
        in_code_fence = False
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                lines.append(raw_line)
                continue
            if in_code_fence:
                lines.append(raw_line)
                continue
            lines.append(
                self._linkify_text(
                    raw_line,
                    entity_paths=entity_paths,
                    entities=entities,
                    exclude_entity_ids=exclude_entity_ids,
                )
            )
        return "\n".join(lines)

    def _linkify_text(
        self,
        text: str,
        *,
        entity_paths: dict[int, Path],
        entities: list[dict[str, Any]],
        exclude_entity_ids: set[int] | None = None,
    ) -> str:
        if not text.strip():
            return text

        filtered_entities: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for entity in sorted(
            entities, key=lambda item: len(item["name"]), reverse=True
        ):
            if exclude_entity_ids and entity["id"] in exclude_entity_ids:
                continue
            name_key = entity["name"].casefold()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)
            filtered_entities.append(entity)
        if not filtered_entities:
            return text

        replacement_by_name = {
            entity["name"].casefold(): self._reference_link(entity, entity_paths)
            or entity["name"]
            for entity in filtered_entities
        }
        alternation = "|".join(
            re.escape(entity["name"]) for entity in filtered_entities
        )
        pattern = re.compile(
            rf"(?<![A-Za-z0-9])({alternation})(?![A-Za-z0-9])",
            re.IGNORECASE,
        )

        segments = re.split(r"(\[\[[^\]]+\]\])", text)
        linked_segments: list[str] = []
        for segment in segments:
            if not segment:
                continue
            if segment.startswith("[[") and segment.endswith("]]"):
                linked_segments.append(segment)
                continue

            linked_segments.append(
                pattern.sub(
                    lambda match: replacement_by_name.get(
                        match.group(0).casefold(), match.group(0)
                    ),
                    segment,
                )
            )
        return "".join(linked_segments)

    def _extract_reference_assets(
        self, document: Document, *, root: Path
    ) -> list[Path]:
        if document.kind != "reference" or not document.url:
            return []

        source_path = Path(document.url).expanduser()
        if source_path.suffix.lower() != ".pdf" or not source_path.exists():
            return []

        specs = self._significant_pdf_image_specs(source_path)
        if not specs:
            return []
        selected_pages = self._selected_pdf_image_pages(specs)
        if not selected_pages:
            return []

        asset_folder = REFERENCE_ASSET_ROOT / safe_note_stem(document.title)
        destination_dir = root / asset_folder
        destination_dir.mkdir(parents=True, exist_ok=True)
        existing_assets = sorted(destination_dir.glob("page-*-image-*.png"))
        if existing_assets:
            return [path.relative_to(root) for path in existing_assets]

        extracted_paths: list[Path] = []
        with tempfile.TemporaryDirectory(prefix="dma-vault-assets-") as tmpdir:
            for page in selected_pages:
                prefix = Path(tmpdir) / f"page-{page:03d}"
                try:
                    subprocess.run(
                        [
                            "pdfimages",
                            "-png",
                            "-f",
                            str(page),
                            "-l",
                            str(page),
                            str(source_path),
                            str(prefix),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=PDFIMAGES_EXTRACT_TIMEOUT_SECONDS,
                    )
                except (
                    FileNotFoundError,
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                ):
                    continue
                candidate_images: list[tuple[int, Path]] = []
                for source_image in sorted(Path(tmpdir).glob(f"page-{page:03d}-*.png")):
                    dimensions = self._png_dimensions(source_image)
                    if dimensions is None:
                        continue
                    width, height = dimensions
                    if width < 240 or height < 120:
                        continue
                    area = width * height
                    if area < 75_000:
                        continue
                    candidate_images.append((area, source_image))

                for index, (_, source_image) in enumerate(
                    sorted(candidate_images, key=lambda item: item[0], reverse=True)[
                        :4
                    ],
                    start=1,
                ):
                    relative_path = asset_folder / (
                        f"page-{page:03d}-image-{index:02d}.png"
                    )
                    shutil.copy2(source_image, root / relative_path)
                    extracted_paths.append(relative_path)
        return extracted_paths

    def _reference_asset_for_page(
        self, document: Document, *, page: int | None
    ) -> Path | None:
        if page is None or document.kind != "reference" or not document.url:
            return None
        source_path = Path(document.url).expanduser()
        if source_path.suffix.lower() != ".pdf" or not source_path.exists():
            return None
        specs = self._significant_pdf_image_specs(source_path)
        if not specs:
            return None
        selected_pages = self._selected_pdf_image_pages(specs)
        if page not in selected_pages:
            return None
        asset_folder = REFERENCE_ASSET_ROOT / safe_note_stem(document.title)
        return asset_folder / f"page-{page:03d}-image-01.png"

    def _document_image_link(
        self,
        *,
        extracted_assets: list[Path] | None,
        related_map_assets: list[Path] | None,
    ) -> str | None:
        for asset_path in [*(extracted_assets or []), *(related_map_assets or [])]:
            return self._asset_wikilink(asset_path)
        return None

    def _export_reference_map_assets(
        self, document: Document, *, root: Path
    ) -> list[Path]:
        if document.kind != "reference":
            return []

        book_number = self._reference_book_number(document.title)
        if book_number is None:
            return []

        source_dir = REFERENCE_MAP_SOURCE_ROOT / f"BOOK {book_number}"
        if not source_dir.exists():
            return []

        asset_folder = REFERENCE_ASSET_ROOT / "Maps" / f"Book {book_number}"
        destination_dir = root / asset_folder
        destination_dir.mkdir(parents=True, exist_ok=True)

        copied_paths: list[Path] = []
        for source_path in sorted(source_dir.iterdir()):
            if not source_path.is_file():
                continue
            if source_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            destination_name = (
                f"{safe_note_stem(source_path.stem)}{source_path.suffix.lower()}"
            )
            relative_path = asset_folder / destination_name
            if not (root / relative_path).exists():
                shutil.copy2(source_path, root / relative_path)
            copied_paths.append(relative_path)
        return copied_paths

    def _asset_wikilink(self, relative_path: Path) -> str:
        return f"[[{relative_path.as_posix()}]]"

    def _reference_book_number(self, title: str) -> int | None:
        match = re.search(r"\bAbomination Vaults\s+(\d+)\b", title, re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _selected_pdf_image_pages(
        self, specs: list[dict[str, int]], *, max_pages: int = 8
    ) -> list[int]:
        chosen: list[int] = []
        seen_pages: set[int] = set()
        for spec in sorted(
            specs, key=lambda item: item["width"] * item["height"], reverse=True
        ):
            page = spec["page"]
            if page in seen_pages:
                continue
            seen_pages.add(page)
            chosen.append(page)
            if len(chosen) >= max_pages:
                break
        return sorted(chosen)

    def _png_dimensions(self, image_path: Path) -> tuple[int, int] | None:
        try:
            with image_path.open("rb") as image_file:
                header = image_file.read(24)
        except OSError:
            return None
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return width, height

    def _significant_pdf_image_specs(self, source_path: Path) -> list[dict[str, int]]:
        cache_key = str(source_path.expanduser())
        if cache_key in self._pdf_image_spec_cache:
            return self._pdf_image_spec_cache[cache_key]
        try:
            result = subprocess.run(
                ["pdfimages", "-list", str(source_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=PDFIMAGES_LIST_TIMEOUT_SECONDS,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            self._pdf_image_spec_cache[cache_key] = []
            return []

        specs: list[dict[str, int]] = []
        for raw_line in result.stdout.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("page") or stripped.startswith("-"):
                continue
            parts = stripped.split()
            if len(parts) < 10:
                continue
            try:
                page = int(parts[0])
                num = int(parts[1])
                image_type = parts[2]
                width = int(parts[3])
                height = int(parts[4])
            except ValueError:
                continue
            if image_type == "smask":
                continue
            if width < 240 or height < 120:
                continue
            if width * height < 75_000:
                continue
            specs.append(
                {
                    "page": page,
                    "num": num,
                    "width": width,
                    "height": height,
                }
            )
        self._pdf_image_spec_cache[cache_key] = specs
        return specs

    def _write_note(self, root: Path, relative_path: Path, content: str) -> None:
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def _managed_block(self, name: str, content: str) -> str:
        rendered = content.strip()
        return MANAGED_BLOCK_TEMPLATE.format(name=name, content=rendered)

    def _editable_block(self, name: str, content: str) -> str:
        return EDITABLE_BLOCK_TEMPLATE.format(name=name, content=content.strip())

    def _editable_text(self, value: Any) -> str:
        if value in (None, "", [], {}):
            return ""
        return str(value).strip()

    def _editable_list(self, value: Any) -> str:
        if not value:
            return ""
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return "\n".join(f"- {item}" for item in items)
        return str(value).strip()

    def _inline(self, value: Any) -> str:
        return " ".join(str(value).split())


obsidian_vault_service = ObsidianVaultService()
