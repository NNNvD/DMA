from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field


class SourceClass(str, Enum):
    retrieval_only = "retrieval_only"
    trainable_open = "trainable_open"
    trainable_with_review = "trainable_with_review"
    private_local = "private_local"


class PrivacyScope(str, Enum):
    public = "public"
    private_local = "private_local"


class DocumentType(str, Enum):
    rule_page = "rule_page"
    gm_reference = "gm_reference"
    player_guide = "player_guide"
    character_sheet_blank = "character_sheet_blank"
    character_sheet_filled = "character_sheet_filled"
    character_export_json = "character_export_json"
    session_recap = "session_recap"
    dm_note = "dm_note"
    campaign_note = "campaign_note"
    house_rule = "house_rule"
    table_log = "table_log"


class LicenseConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class ReviewStatus(str, Enum):
    approved = "approved"
    pending = "pending"
    rejected = "rejected"


class VisibilityScope(str, Enum):
    player_safe = "player_safe"
    gm_only = "gm_only"
    admin_only = "admin_only"


class DocumentSidecar(BaseModel):
    doc_id: str
    title: str
    source_name: str
    source_url: str
    source_class: SourceClass
    privacy_scope: PrivacyScope
    document_type: DocumentType
    license: str
    license_confidence: LicenseConfidence
    author: str = ""
    created_at: str
    retrieved_at: str
    campaign_name: str = ""
    system: str = "Pathfinder 2e"
    edition: str = "PF2e"
    is_official: bool = False
    is_user_authored: bool = False
    is_private: bool = False
    contains_rules_text: bool = False
    contains_spoilers: bool = False
    contains_pii: bool = False
    review_status: ReviewStatus
    train_eligible: bool = False
    rag_eligible: bool = True
    chunking_profile: str
    visibility_scope: VisibilityScope
    local_path: str
    raw_sha256: str
    notes: str = ""


class SourceRegistryEntry(BaseModel):
    source_id: str
    source_name: str
    source_class: SourceClass
    privacy_scope: PrivacyScope
    license: str
    license_confidence: LicenseConfidence
    default_review_status: ReviewStatus
    default_train_eligible: bool
    default_rag_eligible: bool
    acquisition_mode: str
    paths: list[str] = Field(default_factory=list)
    notes: str = ""


class CorpusManifestEntry(BaseModel):
    doc_id: str
    relative_path: str
    title: str
    source_name: str
    source_class: SourceClass
    privacy_scope: PrivacyScope
    document_type: DocumentType
    review_status: ReviewStatus
    rag_eligible: bool
    train_eligible: bool
    visibility_scope: VisibilityScope
    local_path: str


@dataclass(frozen=True)
class ManifestMetadata:
    title: str
    source_url: str
    notes: str


@dataclass(frozen=True)
class Classification:
    source_name: str
    source_class: SourceClass
    privacy_scope: PrivacyScope
    document_type: DocumentType
    license: str
    license_confidence: LicenseConfidence
    review_status: ReviewStatus
    rag_eligible: bool
    train_eligible: bool
    visibility_scope: VisibilityScope
    chunking_profile: str
    is_official: bool = False
    is_user_authored: bool = False
    contains_rules_text: bool = False
    contains_spoilers: bool = False
    contains_pii: bool = False
    notes: str = ""


class IngestionGovernanceService:
    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.project_root = (
            project_root or Path(__file__).resolve().parents[2]
        ).resolve()
        self.default_root = self.project_root / "assets" / "imports"

    def export_artifacts(self, root_path: Optional[str] = None) -> dict[str, Any]:
        root = self._resolve_root(root_path)
        generated_at = self._now_iso()
        raw_files = self._discover_raw_files(root)
        manifest_metadata = self._load_manifest_metadata(root)

        sidecars: list[DocumentSidecar] = []
        registry_entries: dict[str, SourceRegistryEntry] = {}
        review_queue: list[dict[str, Any]] = []
        license_flags: list[dict[str, Any]] = []

        for path in raw_files:
            relative_path = path.relative_to(root).as_posix()
            manifest_meta = manifest_metadata.get(relative_path)
            sidecar = self._build_sidecar(
                root,
                path,
                relative_path=relative_path,
                manifest_meta=manifest_meta,
                retrieved_at=generated_at,
            )
            sidecars.append(sidecar)
            self._merge_registry_entry(registry_entries, sidecar)
            if sidecar.review_status == ReviewStatus.pending:
                review_queue.append(
                    {
                        "doc_id": sidecar.doc_id,
                        "title": sidecar.title,
                        "local_path": sidecar.local_path,
                        "source_name": sidecar.source_name,
                        "source_class": sidecar.source_class,
                        "license_confidence": sidecar.license_confidence,
                        "notes": sidecar.notes,
                    }
                )
            if sidecar.license_confidence != LicenseConfidence.high:
                license_flags.append(
                    {
                        "doc_id": sidecar.doc_id,
                        "title": sidecar.title,
                        "local_path": sidecar.local_path,
                        "license": sidecar.license,
                        "license_confidence": sidecar.license_confidence,
                        "train_eligible": sidecar.train_eligible,
                    }
                )

        manifest_entries = [
            CorpusManifestEntry(
                doc_id=sidecar.doc_id,
                relative_path=Path(sidecar.local_path)
                .relative_to(root.resolve())
                .as_posix(),
                title=sidecar.title,
                source_name=sidecar.source_name,
                source_class=sidecar.source_class,
                privacy_scope=sidecar.privacy_scope,
                document_type=sidecar.document_type,
                review_status=sidecar.review_status,
                rag_eligible=sidecar.rag_eligible,
                train_eligible=sidecar.train_eligible,
                visibility_scope=sidecar.visibility_scope,
                local_path=sidecar.local_path,
            )
            for sidecar in sidecars
        ]

        metadata_dir = root / "metadata"
        manifests_dir = root / "manifests"
        reports_dir = root / "reports" / "ingestion_reports"
        sidecar_dir = metadata_dir / "sidecars"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        manifests_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        sidecar_dir.mkdir(parents=True, exist_ok=True)

        self._write_sidecars(sidecar_dir, root, sidecars)
        self._write_json(
            metadata_dir / "source_registry.json",
            {
                "generated_at": generated_at,
                "sources": [
                    entry.model_dump(mode="json")
                    for entry in sorted(
                        registry_entries.values(), key=lambda item: item.source_name
                    )
                ],
            },
        )
        self._write_json(
            metadata_dir / "license_flags.json",
            {
                "generated_at": generated_at,
                "flagged_documents": license_flags,
            },
        )
        self._write_jsonl(metadata_dir / "review_queue.jsonl", review_queue)
        self._append_jsonl(
            metadata_dir / "ingestion_log.jsonl",
            {
                "generated_at": generated_at,
                "root_path": str(root),
                "files_seen": len(sidecars),
                "review_queue_count": len(review_queue),
                "rag_manifest_count": sum(
                    1 for item in manifest_entries if item.rag_eligible
                ),
                "train_manifest_count": sum(
                    1 for item in manifest_entries if item.train_eligible
                ),
            },
        )
        self._write_manifest(
            manifests_dir / "corpus_manifest.csv",
            [entry.model_dump(mode="json") for entry in manifest_entries],
        )
        self._write_manifest(
            manifests_dir / "rag_manifest.csv",
            [
                entry.model_dump(mode="json")
                for entry in manifest_entries
                if entry.rag_eligible
            ],
        )
        self._write_manifest(
            manifests_dir / "train_manifest.csv",
            [
                entry.model_dump(mode="json")
                for entry in manifest_entries
                if entry.train_eligible
            ],
        )
        self._write_json(
            reports_dir / "latest.json",
            {
                "generated_at": generated_at,
                "files_seen": len(sidecars),
                "review_queue_count": len(review_queue),
                "rag_manifest_count": sum(
                    1 for item in manifest_entries if item.rag_eligible
                ),
                "train_manifest_count": sum(
                    1 for item in manifest_entries if item.train_eligible
                ),
                "sources": len(registry_entries),
            },
        )

        return {
            "root_path": str(root),
            "generated_at": generated_at,
            "files_seen": len(sidecars),
            "sidecars_written": len(sidecars),
            "sources_registered": len(registry_entries),
            "review_queue_count": len(review_queue),
            "rag_manifest_count": sum(
                1 for item in manifest_entries if item.rag_eligible
            ),
            "train_manifest_count": sum(
                1 for item in manifest_entries if item.train_eligible
            ),
        }

    def document_governance_fields(
        self, *, root_path: str | Path, path: str | Path
    ) -> dict[str, Any]:
        root = Path(root_path).expanduser().resolve()
        resolved_path = Path(path).expanduser().resolve()
        relative_path = resolved_path.relative_to(root).as_posix()
        manifest_meta = self._load_manifest_metadata(root).get(relative_path)
        classification = self._classify(
            resolved_path,
            relative_path,
            manifest_meta=manifest_meta,
        )
        return {
            "source_class": classification.source_class.value,
            "privacy_scope": classification.privacy_scope.value,
            "review_status": classification.review_status.value,
            "visibility_scope": classification.visibility_scope.value,
            "rag_eligible": classification.rag_eligible,
            "train_eligible": classification.train_eligible,
        }

    def _resolve_root(self, root_path: Optional[str]) -> Path:
        if not root_path:
            return self.default_root
        return Path(root_path).expanduser().resolve()

    def _discover_raw_files(self, root: Path) -> list[Path]:
        excluded_roots = {"metadata", "manifests", "reports"}
        discovered: list[Path] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if path.relative_to(root).parts[0] in excluded_roots:
                continue
            relative_path = path.relative_to(root).as_posix()
            if path.stem.lower() == "readme":
                continue
            if relative_path in {
                "misc/aon-rules/manifest.json",
                "misc/pf2e-reference/manifest.json",
            }:
                continue
            discovered.append(path)
        return discovered

    def _load_manifest_metadata(self, root: Path) -> dict[str, ManifestMetadata]:
        metadata: dict[str, ManifestMetadata] = {}
        manifest_paths = (
            root / "misc" / "pf2e-reference" / "manifest.json",
            root / "misc" / "aon-rules" / "manifest.json",
        )
        for manifest_path in manifest_paths:
            if not manifest_path.exists():
                continue
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            for item in payload.get("items", []):
                local_path = str(item.get("local_path") or "").strip()
                if not local_path:
                    continue
                relative_path = local_path
                prefix = "assets/imports/"
                if relative_path.startswith(prefix):
                    relative_path = relative_path[len(prefix) :]
                metadata[relative_path] = ManifestMetadata(
                    title=str(item.get("title") or "").strip(),
                    source_url=str(item.get("source_url") or "").strip(),
                    notes=str(item.get("notes") or "").strip(),
                )
        return metadata

    def _build_sidecar(
        self,
        root: Path,
        path: Path,
        *,
        relative_path: str,
        manifest_meta: Optional[ManifestMetadata],
        retrieved_at: str,
    ) -> DocumentSidecar:
        title = manifest_meta.title if manifest_meta else self._humanize_stem(path.stem)
        classification = self._classify(
            path, relative_path, manifest_meta=manifest_meta
        )
        stat = path.stat()
        source_url = (
            manifest_meta.source_url
            if manifest_meta and manifest_meta.source_url
            else str(path.resolve())
        )
        doc_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{root.resolve().as_posix()}::{relative_path}::{self._sha256(path)}",
            )
        )
        notes = classification.notes
        if manifest_meta and manifest_meta.notes:
            notes = f"{notes} {manifest_meta.notes}".strip()

        return DocumentSidecar(
            doc_id=doc_id,
            title=title,
            source_name=classification.source_name,
            source_url=source_url,
            source_class=classification.source_class,
            privacy_scope=classification.privacy_scope,
            document_type=classification.document_type,
            license=classification.license,
            license_confidence=classification.license_confidence,
            created_at=datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
            retrieved_at=retrieved_at,
            campaign_name=self._campaign_name(relative_path),
            is_official=classification.is_official,
            is_user_authored=classification.is_user_authored,
            is_private=classification.privacy_scope == PrivacyScope.private_local,
            contains_rules_text=classification.contains_rules_text,
            contains_spoilers=classification.contains_spoilers,
            contains_pii=classification.contains_pii,
            review_status=classification.review_status,
            train_eligible=classification.train_eligible,
            rag_eligible=classification.rag_eligible,
            chunking_profile=classification.chunking_profile,
            visibility_scope=classification.visibility_scope,
            local_path=str(path.resolve()),
            raw_sha256=self._sha256(path),
            notes=notes,
        )

    def _classify(
        self,
        path: Path,
        relative_path: str,
        *,
        manifest_meta: Optional[ManifestMetadata],
    ) -> Classification:
        parts = Path(relative_path).parts
        suffix = path.suffix.lower()
        lower_name = path.name.lower()

        if parts and parts[0] == "campaign-notes":
            rag_eligible = suffix in {".md", ".markdown", ".txt"}
            notes = (
                "User-authored content stays local and is not auto-marked trainable."
            )
            if not rag_eligible:
                notes += " Current campaign-note importer does not normalize this file type yet."
            return Classification(
                source_name="User Campaign Notes Dropzone",
                source_class=SourceClass.trainable_open,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.campaign_note,
                license="User-provided local campaign notes",
                license_confidence=LicenseConfidence.high,
                review_status=ReviewStatus.approved,
                rag_eligible=rag_eligible,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="entity_aware",
                is_user_authored=True,
                notes=notes,
            )

        if parts and parts[0] == "session-logs":
            rag_eligible = suffix in {".md", ".markdown", ".txt"}
            notes = "Private session history remains local and reviewable."
            if not rag_eligible:
                notes += " Current session-log importer does not normalize this file type yet."
            return Classification(
                source_name="User Session Logs Dropzone",
                source_class=SourceClass.trainable_open,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.session_recap,
                license="User-provided local session notes",
                license_confidence=LicenseConfidence.high,
                review_status=ReviewStatus.approved,
                rag_eligible=rag_eligible,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="session_scene",
                is_user_authored=True,
                notes=notes,
            )

        if parts and parts[0] == "pathbuilder":
            document_type = (
                DocumentType.character_export_json
                if suffix == ".json"
                else DocumentType.character_sheet_filled
            )
            rag_eligible = suffix in {".json", ".md", ".markdown", ".txt"}
            notes = (
                "Character imports may include player data, so they are kept gm_only."
            )
            if not rag_eligible:
                notes += " Current pathbuilder importer does not normalize this file type yet."
            return Classification(
                source_name="User Character Imports Dropzone",
                source_class=SourceClass.trainable_open,
                privacy_scope=PrivacyScope.private_local,
                document_type=document_type,
                license="User-provided character export or sheet",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=rag_eligible,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="character_snapshot",
                is_user_authored=True,
                contains_pii=True,
                notes=notes,
            )

        if relative_path.startswith("misc/pf2e-reference/raw/"):
            gm_keywords = (
                "damage",
                "proficiency",
                "settlement",
                "tactica",
            )
            document_type = (
                DocumentType.gm_reference
                if any(keyword in lower_name for keyword in gm_keywords)
                else DocumentType.player_guide
            )
            return Classification(
                source_name="Zenith Games PF2e Guide Index",
                source_class=SourceClass.trainable_with_review,
                privacy_scope=PrivacyScope.public,
                document_type=document_type,
                license="Public guide or spreadsheet; reuse rights require review",
                license_confidence=LicenseConfidence.low,
                review_status=ReviewStatus.pending,
                rag_eligible=True,
                train_eligible=False,
                visibility_scope=VisibilityScope.player_safe,
                chunking_profile="section_heading",
                contains_rules_text=True,
                contains_spoilers="spoiler"
                in (manifest_meta.notes.lower() if manifest_meta else ""),
                notes="Imported for retrieval/reference only unless a later review approves broader reuse.",
            )

        if relative_path.startswith("misc/aon-rules/raw/"):
            return Classification(
                source_name="Archives of Nethys Rules Index",
                source_class=SourceClass.retrieval_only,
                privacy_scope=PrivacyScope.public,
                document_type=DocumentType.rule_page,
                license="Archives of Nethys rules page used for retrieval-only lookup",
                license_confidence=LicenseConfidence.low,
                review_status=ReviewStatus.approved,
                rag_eligible=True,
                train_eligible=False,
                visibility_scope=VisibilityScope.player_safe,
                chunking_profile="section_heading",
                is_official=False,
                contains_rules_text=True,
                notes=(
                    "AoN rules content is tracked for retrieval-only rules lookup and is "
                    "not eligible for training."
                ),
            )

        if relative_path.startswith("misc/private-local/reference/raw/player/"):
            rag_eligible = suffix in {
                ".csv",
                ".docx",
                ".json",
                ".markdown",
                ".md",
                ".pdf",
                ".tsv",
                ".txt",
                ".xlsx",
            }
            notes = "Local player-safe reference kept private and excluded from training by default."
            if not rag_eligible:
                notes += " Current local-reference importer does not normalize this file type yet."
            return Classification(
                source_name="Private Local Player Reference",
                source_class=SourceClass.private_local,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.player_guide,
                license="User-supplied local reference material",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=rag_eligible,
                train_eligible=False,
                visibility_scope=VisibilityScope.player_safe,
                chunking_profile="section_heading",
                contains_pii=suffix in {".xlsx"},
                notes=notes,
            )

        if relative_path.startswith("misc/private-local/reference/raw/gm/"):
            rag_eligible = suffix in {
                ".csv",
                ".docx",
                ".json",
                ".markdown",
                ".md",
                ".pdf",
                ".tsv",
                ".txt",
                ".xlsx",
            }
            notes = (
                "Local GM reference kept private and excluded from training by default."
            )
            if not rag_eligible:
                notes += " Current local-reference importer does not normalize this file type yet."
            return Classification(
                source_name="Private Local GM Reference",
                source_class=SourceClass.private_local,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.gm_reference,
                license="User-supplied local reference material",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=rag_eligible,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="section_heading",
                contains_spoilers=True,
                contains_pii=suffix in {".xlsx"},
                notes=notes,
            )

        if relative_path.startswith("misc/private-local/library/player-guides/"):
            return Classification(
                source_name="Private Local Player Guide Library",
                source_class=SourceClass.retrieval_only,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.player_guide,
                license="User-supplied proprietary or purchased player-facing material",
                license_confidence=LicenseConfidence.low,
                review_status=ReviewStatus.approved,
                rag_eligible=False,
                train_eligible=False,
                visibility_scope=VisibilityScope.player_safe,
                chunking_profile="manual_review_required",
                contains_rules_text=True,
                notes="Archived locally for provenance; outside the active text importer.",
            )

        if relative_path.startswith("misc/private-local/library/gm-reference/"):
            return Classification(
                source_name="Private Local GM Reference Library",
                source_class=SourceClass.retrieval_only,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.gm_reference,
                license="User-supplied proprietary or purchased GM material",
                license_confidence=LicenseConfidence.low,
                review_status=ReviewStatus.approved,
                rag_eligible=False,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="manual_review_required",
                contains_spoilers=True,
                notes="Archived locally for provenance; outside the active text importer.",
            )

        if relative_path.startswith("misc/private-local/character-sheets/"):
            rag_eligible = suffix in {".json", ".markdown", ".md", ".txt"}
            notes = "Legacy character sheet archive kept local pending format-specific normalization."
            if not rag_eligible:
                notes += " Current structured character importer does not normalize this file type yet."
            return Classification(
                source_name="Private Local Character Sheet Archive",
                source_class=SourceClass.private_local,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.character_sheet_filled,
                license="User-supplied local character sheet",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=rag_eligible,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="character_snapshot",
                contains_pii=True,
                notes=notes,
            )

        if relative_path.startswith("misc/private-local/media/"):
            return Classification(
                source_name="Private Local Campaign Media Archive",
                source_class=SourceClass.private_local,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.gm_reference,
                license="User-supplied local media asset",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=False,
                train_eligible=False,
                visibility_scope=VisibilityScope.admin_only,
                chunking_profile="binary_asset",
                contains_spoilers=True,
                notes="Binary map, handout, token, or audio asset kept outside text retrieval.",
            )

        if relative_path.startswith("misc/private-local/maptool-campaigns/"):
            return Classification(
                source_name="Private Local MapTool Campaign Archive",
                source_class=SourceClass.private_local,
                privacy_scope=PrivacyScope.private_local,
                document_type=DocumentType.gm_reference,
                license="User-supplied local MapTool campaign file",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=False,
                train_eligible=False,
                visibility_scope=VisibilityScope.admin_only,
                chunking_profile="binary_asset",
                contains_spoilers=True,
                notes="Archived MapTool campaign bundle; outside the active text importer.",
            )

        if lower_name.endswith(".pdf"):
            document_type = (
                DocumentType.player_guide
                if "player" in lower_name and "guide" in lower_name
                else DocumentType.gm_reference
            )
            return Classification(
                source_name="Legacy Local Proprietary Imports",
                source_class=SourceClass.retrieval_only,
                privacy_scope=PrivacyScope.private_local,
                document_type=document_type,
                license="User-supplied proprietary or purchased local material",
                license_confidence=LicenseConfidence.low,
                review_status=ReviewStatus.approved,
                rag_eligible=False,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="manual_review_required",
                contains_rules_text=document_type == DocumentType.player_guide,
                contains_spoilers=document_type == DocumentType.gm_reference,
                notes="Tracked for provenance, but outside the active drop-zone importer.",
            )

        if lower_name.endswith(".xlsx"):
            document_type = (
                DocumentType.character_sheet_filled
                if "character" in lower_name
                else DocumentType.table_log
            )
            return Classification(
                source_name="Legacy Local Spreadsheet Imports",
                source_class=SourceClass.private_local,
                privacy_scope=PrivacyScope.private_local,
                document_type=document_type,
                license="User-supplied local spreadsheet",
                license_confidence=LicenseConfidence.medium,
                review_status=ReviewStatus.approved,
                rag_eligible=False,
                train_eligible=False,
                visibility_scope=VisibilityScope.gm_only,
                chunking_profile="table_rows",
                contains_pii=document_type == DocumentType.character_sheet_filled,
                notes="Legacy spreadsheet outside the active importer; keep local until normalized.",
            )

        return Classification(
            source_name="Unclassified Local Import",
            source_class=SourceClass.private_local,
            privacy_scope=PrivacyScope.private_local,
            document_type=DocumentType.dm_note,
            license="User-supplied local material",
            license_confidence=LicenseConfidence.unknown,
            review_status=ReviewStatus.pending,
            rag_eligible=False,
            train_eligible=False,
            visibility_scope=VisibilityScope.admin_only,
            chunking_profile="manual_review_required",
            notes="Needs manual review before entering any manifest beyond corpus tracking.",
        )

    def _merge_registry_entry(
        self, registry_entries: dict[str, SourceRegistryEntry], sidecar: DocumentSidecar
    ) -> None:
        source_id = str(uuid5(NAMESPACE_URL, sidecar.source_name))
        entry = registry_entries.get(source_id)
        if entry is None:
            registry_entries[source_id] = SourceRegistryEntry(
                source_id=source_id,
                source_name=sidecar.source_name,
                source_class=sidecar.source_class,
                privacy_scope=sidecar.privacy_scope,
                license=sidecar.license,
                license_confidence=sidecar.license_confidence,
                default_review_status=sidecar.review_status,
                default_train_eligible=sidecar.train_eligible,
                default_rag_eligible=sidecar.rag_eligible,
                acquisition_mode=self._acquisition_mode(sidecar),
                paths=[self._display_path(sidecar.local_path)],
                notes=sidecar.notes,
            )
            return

        merged_paths = sorted({*entry.paths, self._display_path(sidecar.local_path)})
        registry_entries[source_id] = entry.model_copy(update={"paths": merged_paths})

    def _acquisition_mode(self, sidecar: DocumentSidecar) -> str:
        if sidecar.source_url.startswith("http"):
            return "web_fetch_or_manual_export"
        return "user_provided_local_file"

    def _write_sidecars(
        self, sidecar_root: Path, imports_root: Path, sidecars: list[DocumentSidecar]
    ) -> None:
        expected_paths: set[Path] = set()
        for sidecar in sidecars:
            relative = Path(sidecar.local_path).relative_to(imports_root.resolve())
            output_path = sidecar_root / relative.parent / f"{relative.name}.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            expected_paths.add(output_path.resolve())
            self._write_json(output_path, sidecar.model_dump(mode="json"))
        for existing_path in sidecar_root.rglob("*.json"):
            if existing_path.resolve() not in expected_paths:
                existing_path.unlink()

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, default=self._json_default) + "\n",
            encoding="utf-8",
        )

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, default=self._json_default) + "\n")

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=self._json_default) + "\n")

    def _write_manifest(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "doc_id",
            "relative_path",
            "title",
            "source_name",
            "source_class",
            "privacy_scope",
            "document_type",
            "review_status",
            "rag_eligible",
            "train_eligible",
            "visibility_scope",
            "local_path",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _campaign_name(self, relative_path: str) -> str:
        lowered = relative_path.lower()
        if "wofw" in lowered or "way of the wicked" in lowered:
            return "Way of the Wicked"
        if "wotbs" in lowered or "war_of_the_burning_sky" in lowered:
            return "War of the Burning Sky"
        if (
            "rise of the runelords" in lowered
            or "rise-of-the-runelords" in lowered
            or "rotr" in lowered
        ):
            return "Rise of the Runelords"
        return ""

    def _display_path(self, local_path: str) -> str:
        resolved = Path(local_path).resolve()
        try:
            return resolved.relative_to(self.project_root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        raise TypeError(
            f"Object of type {type(value).__name__} is not JSON serializable"
        )

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _humanize_stem(self, stem: str) -> str:
        words = stem.replace("_", " ").replace("-", " ").strip()
        return " ".join(words.split()).title() if words else "Imported Document"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()


ingestion_governance_service = IngestionGovernanceService()
