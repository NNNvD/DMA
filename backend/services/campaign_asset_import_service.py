from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.campaign_note_import_service import (
    ParsedEntityNote,
    campaign_note_import_service,
)
from backend.services.campaign_service import campaign_service
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


class CampaignAssetImportService:
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
                if path.suffix.lower() not in config.allowed_suffixes:
                    continue
                discovered.append((path, config))
        return discovered

    def _parse_candidate(
        self, path: Path, config: DropZoneConfig, *, root: Path
    ) -> ParsedAssetCandidate:
        content = path.read_text(encoding="utf-8", errors="replace")
        relative_path = path.relative_to(root).as_posix()
        source_name = relative_path
        document_url = str(path.resolve())

        if config.import_type == "campaign_note":
            return self._build_campaign_note_candidate(
                path,
                content,
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
            )
        if config.import_type == "pc_sheet":
            return self._build_pc_sheet_candidate(
                path,
                content,
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
            )
        if config.import_type == "session_update":
            return self._build_session_update_candidate(
                path,
                content,
                relative_path=relative_path,
                source_name=source_name,
                document_url=document_url,
            )
        raise ValueError(f"No importer configured for category '{config.category}'")

    def _build_campaign_note_candidate(
        self,
        path: Path,
        content: str,
        *,
        relative_path: str,
        source_name: str,
        document_url: str,
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
        )

    def _build_pc_sheet_candidate(
        self,
        path: Path,
        content: str,
        *,
        relative_path: str,
        source_name: str,
        document_url: str,
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
        )

    def _build_session_update_candidate(
        self,
        path: Path,
        content: str,
        *,
        relative_path: str,
        source_name: str,
        document_url: str,
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
            )
        elif candidate.import_type == "pc_sheet":
            imported = await pc_sheet_import_service.import_sheet(
                db,
                title=candidate.title,
                content=candidate.content,
                source_name=candidate.source_name,
                document_url=candidate.document_url,
                store_document=store_documents,
            )
        elif candidate.import_type == "session_update":
            imported = await session_update_service.import_session_update(
                db,
                title=candidate.title,
                content=candidate.content,
                source_name=candidate.source_name,
                document_url=candidate.document_url,
                store_document=store_documents,
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
        normalized: list[str] = []
        for category in categories:
            slug = category.strip().lower().replace("_", "-")
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

    def _humanize_stem(self, stem: str) -> str:
        words = re.sub(r"[-_]+", " ", stem).strip()
        words = re.sub(r"\s+", " ", words)
        return words.title() if words else "Imported Asset"


campaign_asset_import_service = CampaignAssetImportService()
