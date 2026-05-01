from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Optional
import zipfile
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.document import Document
from backend.services.campaign_note_import_service import (
    ParsedEntityNote,
    campaign_note_import_service,
)
from backend.services.campaign_service import campaign_service
from backend.services.ingestion_governance import ingestion_governance_service
from backend.services.ingestion_service import ingestion_service
from backend.services.pc_sheet_import_service import (
    ParsedPCSheet,
    pc_sheet_import_service,
)
from backend.services.session_update_service import session_update_service


@dataclass(frozen=True)
class DropZoneConfig:
    category: str
    folder_name: str
    import_type: str
    allowed_suffixes: tuple[str, ...]


@dataclass(frozen=True)
class ReferenceCheck:
    label: str
    reference: str
    allowed_types: Optional[set[str]] = None


@dataclass
class ParsedAssetCandidate:
    category: str
    import_type: str
    import_format: str
    document_kind: str
    path: Path
    relative_path: str
    title: str
    source_name: str
    document_url: str
    content: str
    preview: dict[str, Any]
    parsed_summary: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    predicted_refs: dict[str, set[str]] = field(default_factory=dict)
    reference_checks: list[ReferenceCheck] = field(default_factory=list)
    document_governance: dict[str, Any] = field(default_factory=dict)


class CampaignAssetImportService:
    spreadsheet_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    spreadsheet_rel_ns = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    wordprocessing_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    drop_zones = {
        "campaign-notes": DropZoneConfig(
            category="campaign-notes",
            folder_name="campaign-notes",
            import_type="campaign_note",
            allowed_suffixes=(".md", ".markdown", ".txt"),
        ),
        "pathbuilder": DropZoneConfig(
            category="pathbuilder",
            folder_name="pathbuilder",
            import_type="pc_sheet",
            allowed_suffixes=(".json", ".md", ".markdown", ".txt"),
        ),
        "session-logs": DropZoneConfig(
            category="session-logs",
            folder_name="session-logs",
            import_type="session_update",
            allowed_suffixes=(".md", ".markdown", ".txt"),
        ),
        "reference-guides": DropZoneConfig(
            category="reference-guides",
            folder_name="misc/pf2e-reference/raw",
            import_type="guide",
            allowed_suffixes=(
                ".csv",
                ".json",
                ".markdown",
                ".md",
                ".pdf",
                ".tsv",
                ".txt",
                ".xlsx",
            ),
        ),
        "rules": DropZoneConfig(
            category="rules",
            folder_name="misc/aon-rules/raw",
            import_type="rule",
            allowed_suffixes=(".json",),
        ),
        "local-reference": DropZoneConfig(
            category="local-reference",
            folder_name="misc/private-local/reference/raw",
            import_type="local_reference",
            allowed_suffixes=(
                ".csv",
                ".docx",
                ".json",
                ".markdown",
                ".md",
                ".pdf",
                ".tsv",
                ".txt",
                ".xlsx",
            ),
        ),
    }

    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.default_root = self.project_root / "assets" / "imports"

    async def preview_batch(
        self,
        db: AsyncSession,
        *,
        root_path: Optional[str] = None,
        categories: Optional[list[str]] = None,
        store_documents: bool = True,
    ) -> dict[str, Any]:
        candidates, failed_files = await self._load_candidates(
            db, root_path=root_path, categories=categories
        )
        return self._build_batch_response(
            root_path=self._resolve_root(root_path),
            dry_run=True,
            store_documents=store_documents,
            candidates=candidates,
            imported_results=[],
            failed_files=failed_files,
        )

    async def import_batch(
        self,
        db: AsyncSession,
        *,
        root_path: Optional[str] = None,
        categories: Optional[list[str]] = None,
        dry_run: bool = False,
        store_documents: bool = True,
        stop_on_error: bool = False,
    ) -> dict[str, Any]:
        candidates, failed_files = await self._load_candidates(
            db, root_path=root_path, categories=categories
        )
        if dry_run:
            return self._build_batch_response(
                root_path=self._resolve_root(root_path),
                dry_run=True,
                store_documents=store_documents,
                candidates=candidates,
                imported_results=[],
                failed_files=failed_files,
            )

        imported_results: list[dict[str, Any]] = []
        for candidate in candidates:
            try:
                imported_results.append(
                    await self._import_candidate(
                        db,
                        candidate,
                        store_documents=store_documents,
                    )
                )
            except (LookupError, OSError, UnicodeDecodeError, ValueError) as exc:
                imported_results.append(
                    {
                        "path": candidate.relative_path,
                        "category": candidate.category,
                        "import_type": candidate.import_type,
                        "import_format": candidate.import_format,
                        "title": candidate.title,
                        "status": "failed",
                        "error": str(exc),
                        "warnings": list(candidate.warnings),
                        "preview": candidate.preview,
                        "parsed_summary": candidate.parsed_summary,
                    }
                )
                if stop_on_error:
                    break

        return self._build_batch_response(
            root_path=self._resolve_root(root_path),
            dry_run=False,
            store_documents=store_documents,
            candidates=candidates,
            imported_results=imported_results,
            failed_files=failed_files,
        )

    async def _load_candidates(
        self,
        db: AsyncSession,
        *,
        root_path: Optional[str],
        categories: Optional[list[str]],
    ) -> tuple[list[ParsedAssetCandidate], list[dict[str, Any]]]:
        root = self._resolve_root(root_path)
        discovered = self._discover_files(root, categories=categories)
        candidates: list[ParsedAssetCandidate] = []
        failed_files: list[dict[str, Any]] = []
        for path, config in discovered:
            relative_path = path.relative_to(root).as_posix()
            try:
                candidates.append(self._parse_candidate(path, config, root=root))
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                failed_files.append(
                    {
                        "path": relative_path,
                        "category": config.category,
                        "import_type": config.import_type,
                        "import_format": config.import_type,
                        "title": self._humanize_stem(path.stem),
                        "status": "failed",
                        "error": str(exc),
                        "warnings": [],
                        "preview": {},
                        "parsed_summary": {},
                    }
                )
        predicted_refs = self._collect_predicted_refs(candidates)
        for candidate in candidates:
            candidate.warnings.extend(
                await self._preview_reference_warnings(
                    db,
                    candidate.reference_checks,
                    predicted_refs=predicted_refs,
                )
            )
        return candidates, failed_files

    def _discover_files(
        self,
        root: Path,
        *,
        categories: Optional[list[str]],
    ) -> list[tuple[Path, DropZoneConfig]]:
        normalized_categories = self._normalize_categories(categories)
        discovered: list[tuple[Path, DropZoneConfig]] = []
        for category in normalized_categories:
            config = self.drop_zones[category]
            folder = root / config.folder_name
            if not folder.exists():
                continue
            for path in sorted(folder.rglob("*")):
                if not path.is_file() or path.name.startswith("."):
                    continue
                if path.stem.lower() == "readme":
                    continue
                if path.suffix.lower() not in config.allowed_suffixes:
                    continue
                discovered.append((path, config))
        return discovered

    def _parse_candidate(
        self, path: Path, config: DropZoneConfig, *, root: Path
    ) -> ParsedAssetCandidate:
        relative_path = path.relative_to(root).as_posix()
        source_name = relative_path
        document_url = str(path.resolve())
        document_governance = ingestion_governance_service.document_governance_fields(
            root_path=root,
            path=path,
        )

        if config.import_type == "guide":
            return self._build_reference_document_candidate(
                path,
                category=config.category,
                import_type=config.import_type,
                document_kind="guide",
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
                document_governance=document_governance,
            )
        if config.import_type == "rule":
            return self._build_rule_candidate(
                path,
                relative_path=relative_path,
                document_governance=document_governance,
            )
        if config.import_type == "local_reference":
            return self._build_reference_document_candidate(
                path,
                category=config.category,
                import_type=config.import_type,
                document_kind="reference",
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
                document_governance=document_governance,
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        if config.import_type == "campaign_note":
            return self._build_campaign_note_candidate(
                path,
                content,
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
                document_governance=document_governance,
            )
        if config.import_type == "pc_sheet":
            return self._build_pc_sheet_candidate(
                path,
                content,
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
                document_governance=document_governance,
            )
        if config.import_type == "session_update":
            return self._build_session_update_candidate(
                path,
                content,
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
                document_governance=document_governance,
            )
        raise ValueError(f"No importer configured for category '{config.category}'")

    def _build_rule_candidate(
        self,
        path: Path,
        *,
        relative_path: str,
        document_governance: dict[str, Any],
    ) -> ParsedAssetCandidate:
        payload = self._load_json_payload(path)
        title = str(payload.get("title") or "").strip() or self._humanize_stem(
            path.stem
        )
        content = str(payload.get("content") or "").strip()
        if not content:
            raise ValueError("Rule payload is missing content.")

        source_name = str(payload.get("source_name") or "").strip()
        if not source_name:
            source_name = "Archives of Nethys Rules Index"
        document_url = str(
            payload.get("source_url") or payload.get("url") or ""
        ).strip() or str(path.resolve())
        ancestors = payload.get("ancestors") or []
        if not isinstance(ancestors, list):
            ancestors = []

        return ParsedAssetCandidate(
            category="rules",
            import_type="rule",
            import_format="json",
            document_kind="rule",
            path=path,
            relative_path=relative_path,
            title=title,
            source_name=source_name,
            document_url=document_url,
            content=content,
            preview={
                "source_format": "json",
                "char_count": len(content),
                "line_count": sum(1 for line in content.splitlines() if line.strip()),
                "source_url": document_url,
                "ancestor_count": len(ancestors),
            },
            parsed_summary={"parsed_documents": 1},
            document_governance=document_governance,
        )

    def _build_reference_document_candidate(
        self,
        path: Path,
        *,
        category: str,
        import_type: str,
        document_kind: str,
        relative_path: str,
        source_name: str,
        document_url: str,
        document_governance: dict[str, Any],
    ) -> ParsedAssetCandidate:
        content, import_format, preview, parsed_summary = (
            self._extract_reference_document_content(path)
        )
        title = self._humanize_stem(path.stem)
        if import_format == "pdf":
            extracted_title = self._first_non_marker_line(content)
            if extracted_title and extracted_title.casefold() not in {
                "second edition",
                "pathfinder second edition",
                "pathfinder",
            }:
                title = extracted_title
        elif import_format != "xlsx":
            title = self._first_markdown_heading(content) or title
        return ParsedAssetCandidate(
            category=category,
            import_type=import_type,
            import_format=import_format,
            document_kind=document_kind,
            path=path,
            relative_path=relative_path,
            title=title,
            source_name=source_name,
            document_url=document_url,
            content=content,
            preview=preview,
            parsed_summary=parsed_summary,
            document_governance=document_governance,
        )

    def _build_campaign_note_candidate(
        self,
        path: Path,
        content: str,
        *,
        relative_path: str,
        source_name: str,
        document_url: str,
        document_governance: dict[str, Any],
    ) -> ParsedAssetCandidate:
        parsed_entities = campaign_note_import_service.parse_content(content)
        if not parsed_entities:
            raise ValueError(
                "No importable campaign entities found. Use blocks like 'Location: Greyhaven'."
            )

        title = self._first_markdown_heading(content) or self._humanize_stem(path.stem)
        relationship_count = sum(
            len(entity.relationships) for entity in parsed_entities
        )
        preview_entities = [
            {
                "entity_type": entity.entity_type,
                "name": entity.name,
                "stable_key": entity.stable_key,
            }
            for entity in parsed_entities
        ]
        return ParsedAssetCandidate(
            category="campaign-notes",
            import_type="campaign_note",
            import_format="campaign_note_blocks",
            document_kind="campaign_note",
            path=path,
            relative_path=relative_path,
            title=title,
            source_name=source_name,
            document_url=document_url,
            content=content,
            preview={
                "entity_count": len(parsed_entities),
                "entities": preview_entities,
                "relationship_count": relationship_count,
            },
            parsed_summary={
                "parsed_entities": len(parsed_entities),
                "parsed_relationships": relationship_count,
            },
            predicted_refs=self._predicted_refs_from_notes(parsed_entities),
            reference_checks=self._reference_checks_from_notes(parsed_entities),
            document_governance=document_governance,
        )

    def _build_pc_sheet_candidate(
        self,
        path: Path,
        content: str,
        *,
        relative_path: str,
        source_name: str,
        document_url: str,
        document_governance: dict[str, Any],
    ) -> ParsedAssetCandidate:
        parsed = pc_sheet_import_service.parse_content(content)
        title = (
            f"{parsed.name} Pathbuilder Export"
            if parsed.source_format == "pathbuilder2_json"
            else f"{parsed.name} PC Sheet"
        )
        relationship_count = len(parsed.faction_references) + len(
            parsed.relationship_specs
        )
        preview = {
            "name": parsed.name,
            "source_format": parsed.source_format,
            "level": parsed.sheet_payload.get("level"),
            "class_name": parsed.sheet_payload.get("class_name"),
            "current_location_reference": parsed.current_location_reference,
            "factions": parsed.faction_references,
            "notable_items": parsed.notable_items,
            "relationship_count": relationship_count,
        }
        return ParsedAssetCandidate(
            category="pathbuilder",
            import_type="pc_sheet",
            import_format=parsed.source_format,
            document_kind="pc_sheet",
            path=path,
            relative_path=relative_path,
            title=title,
            source_name=source_name,
            document_url=document_url,
            content=content,
            preview=preview,
            parsed_summary={
                "parsed_entities": 1,
                "parsed_relationships": relationship_count,
                "parsed_artifacts": len(parsed.notable_items),
                "parsed_sheet_versions": 1,
            },
            predicted_refs=self._predicted_refs_from_pc(parsed),
            reference_checks=self._reference_checks_from_pc(parsed),
            document_governance=document_governance,
        )

    def _build_session_update_candidate(
        self,
        path: Path,
        content: str,
        *,
        relative_path: str,
        source_name: str,
        document_url: str,
        document_governance: dict[str, Any],
    ) -> ParsedAssetCandidate:
        parsed_meta = session_update_service.parse_metadata(content)
        parsed_entities = session_update_service.parse_entities(content)
        title = (
            parsed_meta.metadata.get("title")
            or self._first_markdown_heading(content)
            or self._humanize_stem(path.stem)
        )
        relationship_count = sum(
            len(entity.relationships) for entity in parsed_entities
        )
        preview = {
            "calendar": parsed_meta.metadata.get("calendar"),
            "current_date": parsed_meta.metadata.get("current date"),
            "timeline_position": parsed_meta.metadata.get("timeline position"),
            "summary": parsed_meta.metadata.get("summary"),
            "entity_count": len(parsed_entities),
            "changelog_count": len(parsed_meta.changelog),
        }
        return ParsedAssetCandidate(
            category="session-logs",
            import_type="session_update",
            import_format="session_update_text",
            document_kind="session_log",
            path=path,
            relative_path=relative_path,
            title=title,
            source_name=source_name,
            document_url=document_url,
            content=content,
            preview=preview,
            parsed_summary={
                "parsed_entities": len(parsed_entities),
                "parsed_relationships": relationship_count,
                "parsed_changelog_entries": len(parsed_meta.changelog),
            },
            predicted_refs=self._predicted_refs_from_notes(parsed_entities),
            reference_checks=self._reference_checks_from_notes(parsed_entities),
            document_governance=document_governance,
        )

    async def _import_candidate(
        self,
        db: AsyncSession,
        candidate: ParsedAssetCandidate,
        *,
        store_documents: bool,
    ) -> dict[str, Any]:
        if candidate.import_type == "campaign_note":
            imported = await campaign_note_import_service.import_note(
                db,
                title=candidate.title,
                content=candidate.content,
                source_name=candidate.source_name,
                document_url=candidate.document_url,
                store_document=store_documents,
                document_governance=candidate.document_governance,
            )
        elif candidate.import_type == "pc_sheet":
            imported = await pc_sheet_import_service.import_sheet(
                db,
                title=candidate.title,
                content=candidate.content,
                source_name=candidate.source_name,
                document_url=candidate.document_url,
                store_document=store_documents,
                document_governance=candidate.document_governance,
            )
        elif candidate.import_type == "session_update":
            imported = await session_update_service.import_session_update(
                db,
                title=candidate.title,
                content=candidate.content,
                source_name=candidate.source_name,
                document_url=candidate.document_url,
                store_document=store_documents,
                document_governance=candidate.document_governance,
            )
        elif candidate.import_type in {"guide", "local_reference", "rule"}:
            return await self._import_reference_document_candidate(
                db,
                candidate,
                store_documents=store_documents,
            )
        else:
            raise ValueError(f"Unsupported import type '{candidate.import_type}'")

        return {
            "path": candidate.relative_path,
            "category": candidate.category,
            "import_type": candidate.import_type,
            "import_format": imported.get("import_format", candidate.import_format),
            "title": candidate.title,
            "status": "imported",
            "summary": imported.get("summary", {}),
            "warnings": [
                *candidate.warnings,
                *imported.get("warnings", []),
            ],
            "document": imported.get("document"),
            "preview": candidate.preview,
            "parsed_summary": candidate.parsed_summary,
        }

    def _build_batch_response(
        self,
        *,
        root_path: Path,
        dry_run: bool,
        store_documents: bool,
        candidates: list[ParsedAssetCandidate],
        imported_results: list[dict[str, Any]],
        failed_files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        files: list[dict[str, Any]]
        if dry_run:
            files = [
                {
                    "path": candidate.relative_path,
                    "category": candidate.category,
                    "import_type": candidate.import_type,
                    "import_format": candidate.import_format,
                    "title": candidate.title,
                    "status": "previewed",
                    "warnings": list(candidate.warnings),
                    "preview": candidate.preview,
                    "parsed_summary": candidate.parsed_summary,
                }
                for candidate in candidates
            ] + failed_files
        else:
            files = imported_results + failed_files

        summary: dict[str, int] = {
            "files_seen": len(candidates) + len(failed_files),
            "files_previewed": sum(
                1 for item in files if item["status"] == "previewed"
            ),
            "files_imported": sum(1 for item in files if item["status"] == "imported"),
            "files_failed": sum(1 for item in files if item["status"] == "failed"),
            "files_skipped": sum(1 for item in files if item["status"] == "skipped"),
        }
        for item in files:
            for key, value in item.get("parsed_summary", {}).items():
                if isinstance(value, int):
                    summary[key] = summary.get(key, 0) + value
            for key, value in item.get("summary", {}).items():
                if isinstance(value, int):
                    summary[key] = summary.get(key, 0) + value

        return {
            "root_path": str(root_path),
            "dry_run": dry_run,
            "store_documents": store_documents,
            "summary": summary,
            "files": files,
        }

    async def _preview_reference_warnings(
        self,
        db: AsyncSession,
        reference_checks: list[ReferenceCheck],
        *,
        predicted_refs: dict[str, set[str]],
    ) -> list[str]:
        warnings: list[str] = []
        seen: set[tuple[str, str]] = set()
        for check in reference_checks:
            key = (check.label, check.reference.casefold())
            if key in seen:
                continue
            seen.add(key)
            if self._reference_is_predicted(
                check.reference,
                allowed_types=check.allowed_types,
                predicted_refs=predicted_refs,
            ):
                continue
            entity = await campaign_service.find_entity_by_reference(
                db,
                check.reference,
                entity_types=check.allowed_types,
            )
            if entity is None:
                warnings.append(
                    f"Could not resolve {check.label} '{check.reference}' from existing data or the current batch."
                )
        return warnings

    async def _import_reference_document_candidate(
        self,
        db: AsyncSession,
        candidate: ParsedAssetCandidate,
        *,
        store_documents: bool,
    ) -> dict[str, Any]:
        warnings = list(candidate.warnings)
        document_kind = candidate.document_kind or "guide"
        if not store_documents:
            warnings.append(
                f"{document_kind.title()} imports are document-only, so this file was skipped because store_documents=false."
            )
            return {
                "path": candidate.relative_path,
                "category": candidate.category,
                "import_type": candidate.import_type,
                "import_format": candidate.import_format,
                "title": candidate.title,
                "status": "skipped",
                "summary": {"skipped_documents": 1},
                "warnings": warnings,
                "document": None,
                "preview": candidate.preview,
                "parsed_summary": candidate.parsed_summary,
            }

        existing = await self._get_document_by_url(
            db,
            kind=document_kind,
            url=candidate.document_url,
        )
        stored_document = await ingestion_service.ingest_document(
            db,
            title=candidate.title,
            kind=document_kind,
            content=candidate.content,
            summary=self._reference_document_summary(candidate),
            source_name=candidate.source_name,
            url=candidate.document_url,
            dedupe_on_url=True,
            **candidate.document_governance,
        )

        return {
            "path": candidate.relative_path,
            "category": candidate.category,
            "import_type": candidate.import_type,
            "import_format": candidate.import_format,
            "title": candidate.title,
            "status": "imported",
            "summary": {
                "created_documents": 1 if existing is None else 0,
                "updated_documents": 0 if existing is None else 1,
            },
            "warnings": warnings,
            "document": self._document_payload(stored_document),
            "preview": candidate.preview,
            "parsed_summary": candidate.parsed_summary,
        }

    async def _get_document_by_url(
        self, db: AsyncSession, *, kind: str, url: str
    ) -> Optional[Document]:
        stmt = select(Document).where(Document.kind == kind).where(Document.url == url)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    def _document_payload(self, document: Document) -> dict[str, Any]:
        return {
            "id": document.id,
            "title": document.title,
            "kind": document.kind,
            "source_name": document.source_name,
            "url": document.url,
            "source_class": document.source_class,
            "privacy_scope": document.privacy_scope,
            "review_status": document.review_status,
            "visibility_scope": document.visibility_scope,
            "rag_eligible": document.rag_eligible,
            "train_eligible": document.train_eligible,
        }

    def _reference_document_summary(self, candidate: ParsedAssetCandidate) -> str:
        source_format = candidate.preview.get("source_format", candidate.import_format)
        details = [f"Imported {source_format} {candidate.document_kind}"]
        if candidate.preview.get("sheet_count"):
            details.append(f"{candidate.preview['sheet_count']} sheet(s)")
        if candidate.preview.get("non_empty_row_count") is not None:
            details.append(
                f"{candidate.preview['non_empty_row_count']} non-empty row(s)"
            )
        if candidate.preview.get("line_count") is not None:
            details.append(f"{candidate.preview['line_count']} non-empty line(s)")
        return "; ".join(details)

    def _extract_reference_document_content(
        self, path: Path
    ) -> tuple[str, str, dict[str, Any], dict[str, int]]:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md", ".markdown", ".json", ".csv", ".tsv"}:
            content = path.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                raise ValueError("Guide file is empty.")
            non_empty_lines = sum(1 for line in content.splitlines() if line.strip())
            import_format = {
                ".txt": "text",
                ".md": "markdown",
                ".markdown": "markdown",
                ".json": "json",
                ".csv": "csv",
                ".tsv": "tsv",
            }[suffix]
            return (
                content,
                import_format,
                {
                    "source_format": import_format,
                    "char_count": len(content),
                    "line_count": non_empty_lines,
                },
                {"parsed_documents": 1},
            )
        if suffix == ".docx":
            content, paragraph_count = self._extract_docx_text(path)
            return (
                content,
                "docx",
                {
                    "source_format": "docx",
                    "char_count": len(content),
                    "line_count": paragraph_count,
                },
                {"parsed_documents": 1},
            )
        if suffix == ".xlsx":
            content, sheet_count, non_empty_row_count = self._extract_xlsx_text(path)
            return (
                content,
                "xlsx",
                {
                    "source_format": "xlsx",
                    "char_count": len(content),
                    "sheet_count": sheet_count,
                    "non_empty_row_count": non_empty_row_count,
                },
                {
                    "parsed_documents": 1,
                    "parsed_spreadsheets": 1,
                    "parsed_spreadsheet_sheets": sheet_count,
                },
            )
        if suffix == ".pdf":
            content, non_empty_lines = self._extract_pdf_text(path)
            return (
                content,
                "pdf",
                {
                    "source_format": "pdf",
                    "char_count": len(content),
                    "line_count": non_empty_lines,
                },
                {"parsed_documents": 1, "parsed_pdfs": 1},
            )
        raise ValueError(f"Unsupported reference file type '{path.suffix}'")

    def _extract_docx_text(self, path: Path) -> tuple[str, int]:
        with zipfile.ZipFile(path) as document_zip:
            try:
                document_xml = document_zip.read("word/document.xml")
            except KeyError as exc:
                raise ValueError("DOCX file is missing word/document.xml") from exc

        root = ET.fromstring(document_xml)
        paragraphs: list[str] = []
        for paragraph in root.findall(f".//{{{self.wordprocessing_ns}}}p"):
            text = "".join(
                fragment.text or ""
                for fragment in paragraph.iterfind(f".//{{{self.wordprocessing_ns}}}t")
            ).strip()
            if text:
                paragraphs.append(text)

        content = "\n\n".join(paragraphs).strip()
        if not content:
            raise ValueError("No importable reference content found in document.")
        return content, len(paragraphs)

    def _extract_xlsx_text(self, path: Path) -> tuple[str, int, int]:
        with zipfile.ZipFile(path) as workbook:
            shared_strings = self._load_xlsx_shared_strings(workbook)
            sheet_specs = self._load_xlsx_sheet_specs(workbook)
            rendered_sheets: list[str] = []
            non_empty_row_count = 0
            for sheet_name, sheet_path in sheet_specs:
                try:
                    sheet_xml = workbook.read(sheet_path)
                except KeyError:
                    continue
                sheet_root = ET.fromstring(sheet_xml)
                rows: list[str] = []
                for row in sheet_root.findall(
                    f".//{{{self.spreadsheet_ns}}}sheetData/"
                    f"{{{self.spreadsheet_ns}}}row"
                ):
                    cells = [
                        value
                        for value in (
                            self._xlsx_cell_text(cell, shared_strings)
                            for cell in row.findall(f"{{{self.spreadsheet_ns}}}c")
                        )
                        if value
                    ]
                    if not cells:
                        continue
                    rows.append("\t".join(cells))
                    non_empty_row_count += 1
                if rows:
                    rendered_sheets.append(f"# Sheet: {sheet_name}\n" + "\n".join(rows))

        content = "\n\n".join(rendered_sheets).strip()
        if not content:
            raise ValueError("No importable guide content found in workbook.")
        return content, len(rendered_sheets), non_empty_row_count

    def _extract_pdf_text(self, path: Path) -> tuple[str, int]:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "PDF import requires the local 'pdftotext' command to be installed."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            message = stderr or "pdftotext failed to extract PDF text."
            raise ValueError(message) from exc

        content = self._normalize_pdf_text(result.stdout)
        if not content:
            raise ValueError("No importable reference content found in PDF.")
        non_empty_lines = sum(1 for line in content.splitlines() if line.strip())
        return content, non_empty_lines

    def _normalize_pdf_text(self, raw_text: str) -> str:
        page_chunks = [chunk.strip() for chunk in raw_text.split("\f")]
        rendered_pages: list[str] = []
        page_number = 1
        for chunk in page_chunks:
            if not chunk:
                continue
            rendered_pages.append(f"[Page {page_number}]\n{chunk}")
            page_number += 1
        return "\n\n".join(rendered_pages).strip()

    def _load_xlsx_shared_strings(self, workbook: zipfile.ZipFile) -> list[str]:
        try:
            shared_strings_xml = workbook.read("xl/sharedStrings.xml")
        except KeyError:
            return []
        root = ET.fromstring(shared_strings_xml)
        shared_strings: list[str] = []
        for string_item in root.findall(f"{{{self.spreadsheet_ns}}}si"):
            text = "".join(
                fragment.text or ""
                for fragment in string_item.iterfind(f".//{{{self.spreadsheet_ns}}}t")
            ).strip()
            shared_strings.append(text)
        return shared_strings

    def _load_xlsx_sheet_specs(
        self, workbook: zipfile.ZipFile
    ) -> list[tuple[str, str]]:
        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in rels_root.findall(
                f"{{{self.package_rel_ns}}}Relationship"
            )
        }
        specs: list[tuple[str, str]] = []
        for sheet in workbook_root.findall(
            f".//{{{self.spreadsheet_ns}}}sheets/{{{self.spreadsheet_ns}}}sheet"
        ):
            name = sheet.attrib.get("name") or "Sheet"
            rel_id = sheet.attrib.get(f"{{{self.spreadsheet_rel_ns}}}id")
            target = rel_map.get(rel_id or "")
            if not target:
                continue
            normalized_target = target.lstrip("/")
            if not normalized_target.startswith("xl/"):
                normalized_target = f"xl/{normalized_target}"
            specs.append((name, normalized_target))
        return specs

    def _xlsx_cell_text(
        self, cell: ET.Element, shared_strings: list[str]
    ) -> Optional[str]:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            value = "".join(
                fragment.text or ""
                for fragment in cell.iterfind(f".//{{{self.spreadsheet_ns}}}t")
            )
            return value.strip() or None

        value_node = cell.find(f"{{{self.spreadsheet_ns}}}v")
        if value_node is None or value_node.text is None:
            return None

        raw_value = value_node.text.strip()
        if not raw_value:
            return None
        if cell_type == "s":
            try:
                return shared_strings[int(raw_value)].strip() or None
            except (IndexError, ValueError):
                return None
        if cell_type == "b":
            return "TRUE" if raw_value == "1" else "FALSE"
        return raw_value

    def _reference_is_predicted(
        self,
        reference: str,
        *,
        allowed_types: Optional[set[str]],
        predicted_refs: dict[str, set[str]],
    ) -> bool:
        predicted_types = predicted_refs.get(reference.strip().casefold())
        if not predicted_types:
            return False
        if allowed_types is None:
            return True
        return bool(predicted_types.intersection(allowed_types))

    def _collect_predicted_refs(
        self, candidates: list[ParsedAssetCandidate]
    ) -> dict[str, set[str]]:
        predicted: dict[str, set[str]] = {}
        for candidate in candidates:
            for reference, entity_types in candidate.predicted_refs.items():
                predicted.setdefault(reference, set()).update(entity_types)
        return predicted

    def _predicted_refs_from_notes(
        self, parsed_entities: list[ParsedEntityNote]
    ) -> dict[str, set[str]]:
        predicted: dict[str, set[str]] = {}
        for entity in parsed_entities:
            self._add_predicted_ref(predicted, entity.name, entity.entity_type)
            if entity.stable_key:
                self._add_predicted_ref(
                    predicted, entity.stable_key, entity.entity_type
                )
        return predicted

    def _predicted_refs_from_pc(self, parsed: ParsedPCSheet) -> dict[str, set[str]]:
        predicted: dict[str, set[str]] = {}
        self._add_predicted_ref(predicted, parsed.name, "pc")
        if parsed.stable_key:
            self._add_predicted_ref(predicted, parsed.stable_key, "pc")
        return predicted

    def _add_predicted_ref(
        self, predicted: dict[str, set[str]], reference: str, entity_type: str
    ) -> None:
        normalized = reference.strip().casefold()
        if not normalized:
            return
        predicted.setdefault(normalized, set()).add(entity_type)

    def _reference_checks_from_notes(
        self, parsed_entities: list[ParsedEntityNote]
    ) -> list[ReferenceCheck]:
        checks: list[ReferenceCheck] = []
        for entity in parsed_entities:
            if entity.parent_reference:
                checks.append(
                    ReferenceCheck("parent reference", entity.parent_reference)
                )
            if entity.owner_reference:
                checks.append(ReferenceCheck("owner reference", entity.owner_reference))
            if entity.current_location_reference:
                checks.append(
                    ReferenceCheck(
                        "location reference",
                        entity.current_location_reference,
                        allowed_types=campaign_service.location_entity_types,
                    )
                )
            for relationship in entity.relationships:
                checks.append(
                    ReferenceCheck(
                        "relationship target",
                        relationship.target_reference,
                    )
                )
        return checks

    def _reference_checks_from_pc(self, parsed: ParsedPCSheet) -> list[ReferenceCheck]:
        checks: list[ReferenceCheck] = []
        for _, target_reference, _ in parsed.relationship_specs:
            checks.append(ReferenceCheck("relationship target", target_reference))
        return checks

    def _normalize_categories(self, categories: Optional[list[str]]) -> list[str]:
        if not categories:
            return sorted(self.drop_zones)
        aliases = {
            "aon-rules": "rules",
            "guide": "reference-guides",
            "guides": "reference-guides",
            "reference-guide": "reference-guides",
            "local-references": "local-reference",
            "local-reference-docs": "local-reference",
            "rule": "rules",
        }
        normalized: list[str] = []
        for category in categories:
            slug = category.strip().lower().replace("_", "-")
            slug = aliases.get(slug, slug)
            if slug not in self.drop_zones:
                raise ValueError(f"Unsupported import category '{category}'")
            if slug not in normalized:
                normalized.append(slug)
        return normalized

    def _resolve_root(self, root_path: Optional[str]) -> Path:
        if not root_path:
            return self.default_root
        return Path(root_path).expanduser().resolve()

    def _first_markdown_heading(self, content: str) -> Optional[str]:
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("# "):
                heading = stripped[2:].strip()
                if heading:
                    return heading
        return None

    def _first_non_empty_line(self, content: str) -> Optional[str]:
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if stripped:
                return stripped
        return None

    def _first_non_marker_line(self, content: str) -> Optional[str]:
        for raw_line in content.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if re.fullmatch(r"\[Page \d+\]", stripped):
                continue
            return stripped
        return None

    def _humanize_stem(self, stem: str) -> str:
        words = re.sub(r"[-_]+", " ", stem).strip()
        words = re.sub(r"\s+", " ", words)
        return words.title() if words else "Imported Asset"

    def _load_json_payload(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object payload.")
        return payload


campaign_asset_import_service = CampaignAssetImportService()
