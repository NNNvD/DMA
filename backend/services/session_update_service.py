from __future__ import annotations

import hashlib
import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import wraps
import sqlite3
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from backend.config.settings import settings
from backend.models.session_update_draft import SessionUpdateDraft
from backend.models.campaign import CampaignEntityProvenance
from backend.services.campaign_note_import_service import (
    ENTITY_HEADER_RE,
    ParsedEntityNote,
    ParsedRelationship,
    campaign_note_import_service,
)
from backend.services.campaign_service import campaign_service
from backend.services.ingestion_service import ingestion_service
from backend.services.obsidian_markdown import (
    extract_tags,
    replace_wikilinks,
    split_frontmatter,
)


@dataclass
class ParsedSessionUpdate:
    metadata: dict[str, str] = field(default_factory=dict)
    changelog: list[str] = field(default_factory=list)


class SessionUpdateConflict(Exception):
    """A reviewed draft or campaign target changed before the write completed."""


def _review_write(method):
    """Roll back the complete review operation, including staged log ingestion."""

    @wraps(method)
    async def guarded(self, db, *args, **kwargs):
        try:
            return await method(self, db, *args, **kwargs)
        except StaleDataError as exc:
            await db.rollback()
            raise SessionUpdateConflict(
                "The draft changed during review. Reload it and review the changes."
            ) from exc
        except OperationalError as exc:
            await db.rollback()
            # SQLite extended codes retain the primary result in the low byte.
            code = getattr(exc.orig, "sqlite_errorcode", None)
            if code is not None and code & 0xFF in {
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            }:
                raise SessionUpdateConflict(
                    "A competing write prevented review. Reload the current state."
                ) from exc
            raise
        except Exception:
            await db.rollback()
            raise

    return guarded


class SessionUpdateService:
    def __init__(self, *, campaign_id: Optional[str] = None):
        self._campaign_id = campaign_id

    @property
    def campaign_id(self) -> str:
        return self._campaign_id or str(
            settings.dma_campaign_id or "abomination-vaults"
        )

    async def _finish(self, db: AsyncSession, draft: SessionUpdateDraft, commit: bool):
        if commit:
            await db.commit()
        else:
            await db.flush()
        await db.refresh(draft)

    async def preview_review_draft(
        self,
        db: AsyncSession,
        *,
        title: str,
        content: str,
        source_name: Optional[str] = None,
        default_tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        parsed_meta = self.parse_metadata(content)
        parsed_entities = self.parse_entities(content, default_tags=default_tags)
        candidates: list[dict[str, Any]] = [
            {
                "id": f"entity-{index}",
                "candidate_type": "entity",
                "payload": asdict(entity),
            }
            for index, entity in enumerate(parsed_entities)
        ]
        current_date = self._parse_mapping(parsed_meta.metadata.get("current date"))
        if current_date or parsed_meta.metadata.get("calendar"):
            candidates.append(
                {
                    "id": "calendar",
                    "candidate_type": "calendar",
                    "payload": {
                        "name": parsed_meta.metadata.get("calendar")
                        or "Campaign Calendar",
                        "current_date": current_date,
                    },
                }
            )
        if parsed_meta.changelog:
            candidates.append(
                {
                    "id": "session-event",
                    "candidate_type": "session_event",
                    "payload": {
                        "name": title,
                        "summary": parsed_meta.metadata.get("summary"),
                        "details": {
                            "timeline_position": parsed_meta.metadata.get(
                                "timeline position"
                            )
                            or "session-update",
                            "scheduled_for": parsed_meta.metadata.get("scheduled for")
                            or parsed_meta.metadata.get("current date"),
                            "status": "resolved",
                            "consequences": parsed_meta.changelog,
                        },
                        "tags": default_tags or [],
                    },
                }
            )
        for candidate in candidates:
            payload = candidate["payload"]
            entity_type = self._candidate_entity_type(candidate)
            reference = payload.get("stable_key") or payload["name"]
            existing = await campaign_service.find_entity_by_reference(
                db, reference, entity_types=[entity_type]
            )
            candidate["baseline"] = (
                {
                    "id": existing.id,
                    "stable_key": existing.stable_key,
                    "updated_at": existing.updated_at.isoformat(),
                }
                if existing is not None
                else None
            )
        return dict(
            title=title,
            campaign_id=self.campaign_id,
            source_name=source_name,
            content=content,
            source_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            candidates=candidates,
            default_tags=default_tags or [],
            decisions={},
        )

    async def create_review_draft(
        self,
        db: AsyncSession,
        *,
        title: str,
        content: str,
        source_name: Optional[str] = None,
        default_tags: Optional[list[str]] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        draft = SessionUpdateDraft(
            **await self.preview_review_draft(
                db,
                title=title,
                content=content,
                source_name=source_name,
                default_tags=default_tags,
            )
        )
        db.add(draft)
        await self._finish(db, draft, commit)
        return self.draft_to_dict(draft)

    async def get_review_draft(
        self, db: AsyncSession, draft_id: int
    ) -> SessionUpdateDraft:
        result = await db.execute(
            select(SessionUpdateDraft)
            .where(SessionUpdateDraft.id == draft_id)
            .where(SessionUpdateDraft.campaign_id == self.campaign_id)
            .execution_options(populate_existing=True)
        )
        draft = result.scalars().one_or_none()
        if draft is None:
            raise LookupError("Session update draft was not found")
        return draft

    async def _lock_review_draft(
        self, db: AsyncSession, draft_id: int, expected_revision: Optional[int]
    ) -> SessionUpdateDraft:
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision < 1
        ):
            raise ValueError("Expected revision must be a positive integer")
        draft = await self.get_review_draft(db, draft_id)
        revision = draft.revision
        if expected_revision is not None and revision != expected_revision:
            raise SessionUpdateConflict(
                "The draft changed since it was displayed. Reload it and review the changes."
            )
        # A conditional no-op reserves the SQLite writer before baseline reads.
        # Explicitly preserve updated_at and revision: retries do not change tokens.
        # The version predicate also detects a change between SELECT and UPDATE.
        reserved = await db.execute(
            update(SessionUpdateDraft)
            .where(
                SessionUpdateDraft.id == draft.id,
                SessionUpdateDraft.campaign_id == draft.campaign_id,
                SessionUpdateDraft.revision == revision,
            )
            .values(
                revision=SessionUpdateDraft.revision,
                updated_at=SessionUpdateDraft.updated_at,
            )
            .execution_options(synchronize_session=False)
        )
        if reserved.rowcount != 1:
            raise SessionUpdateConflict(
                "The draft changed during review. Reload it and review the changes."
            )
        return draft

    async def list_review_drafts(
        self,
        db: AsyncSession,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(SessionUpdateDraft)
            .where(SessionUpdateDraft.campaign_id == self.campaign_id)
            .order_by(
                SessionUpdateDraft.updated_at.desc(), SessionUpdateDraft.id.desc()
            )
        )
        if status:
            stmt = stmt.where(SessionUpdateDraft.status == status)
        result = await db.execute(stmt.limit(limit))
        return [self.draft_to_dict(item) for item in result.scalars().all()]

    @_review_write
    async def decide_candidate(
        self,
        db: AsyncSession,
        *,
        draft_id: int,
        candidate_id: str,
        decision: str,
        reason: Optional[str] = None,
        reviewer: Optional[str] = None,
        expected_revision: Optional[int] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        if decision not in {"accepted", "rejected", "deferred"}:
            raise ValueError(
                "Candidate decision must be accepted, rejected, or deferred"
            )
        if decision == "rejected" and not (reason or "").strip():
            raise ValueError("A reason is required when rejecting a candidate")
        draft = await self._lock_review_draft(db, draft_id, expected_revision)
        if draft.status != "pending":
            raise ValueError("Finalized session update drafts cannot be changed")
        candidate = next(
            (item for item in draft.candidates if item["id"] == candidate_id), None
        )
        if candidate is None:
            raise LookupError("Session update candidate was not found")
        decisions = copy.deepcopy(draft.decisions or {})
        existing = decisions.get(candidate_id, {})
        if existing.get("decision") in {"accepted", "rejected", "deferred"}:
            if existing["decision"] == decision:
                return {
                    "candidate": candidate,
                    "decision": existing,
                    "promotion": existing.get("promotion"),
                    "draft_revision": draft.revision,
                    "source_hash": draft.source_hash,
                }
            raise ValueError("Accepted or rejected candidate decisions are final")
        decisions[candidate_id] = {
            "decision": decision,
            "reason": reason,
            "reviewer": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        draft.decisions = decisions
        await self._finish(db, draft, commit)
        return {
            "candidate": candidate,
            "decision": decisions[candidate_id],
            "promotion": None,
            "draft_status": draft.status,
            "draft_revision": draft.revision,
            "source_hash": draft.source_hash,
        }

    @_review_write
    async def promote_accepted_candidates(
        self,
        db: AsyncSession,
        *,
        draft_id: int,
        expected_revision: Optional[int] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        draft = await self._lock_review_draft(db, draft_id, expected_revision)
        decisions = copy.deepcopy(draft.decisions or {})
        unresolved = [
            candidate["id"]
            for candidate in draft.candidates
            if decisions.get(candidate["id"], {}).get("decision")
            not in {"accepted", "rejected", "deferred"}
        ]
        if unresolved:
            raise ValueError("Decide every extracted candidate before promotion")
        accepted = [
            candidate
            for candidate in draft.candidates
            if decisions[candidate["id"]]["decision"] == "accepted"
        ]
        if not accepted:
            return self.draft_to_dict(draft)

        existing_rows = await db.execute(
            select(CampaignEntityProvenance).where(
                CampaignEntityProvenance.draft_id == draft.id
            )
        )
        provenance_by_candidate = {
            item.candidate_id: item for item in existing_rows.scalars().all()
        }
        if all(item["id"] in provenance_by_candidate for item in accepted):
            if all(
                decisions[candidate["id"]].get("provenance_id")
                == provenance_by_candidate[candidate["id"]].id
                and decisions[candidate["id"]].get("promotion")
                for candidate in accepted
            ):
                return self.draft_to_dict(draft)
            for candidate in accepted:
                row = provenance_by_candidate[candidate["id"]]
                decisions[candidate["id"]]["provenance_id"] = row.id
                decisions[candidate["id"]]["promotion"] = {
                    "entity_id": row.entity_id,
                    "entity_type": row.entity_type,
                    "created_entities": 0,
                    "updated_entities": 0,
                    "warnings": [],
                    "recovered_from_provenance": True,
                }
            draft.decisions = decisions
            await self._finish(db, draft, commit)
            return self.draft_to_dict(draft)
        if draft.status != "pending":
            raise ValueError("Finalized session update drafts cannot be promoted")
        if any(item["id"] in provenance_by_candidate for item in accepted):
            raise ValueError(
                "Partial prior promotion record found; manual review required"
            )

        try:
            # Check every reviewed baseline before the first campaign write.
            for candidate in accepted:
                await self._assert_candidate_baseline(db, candidate)
            for candidate in accepted:
                promotion = await self._promote_candidate(
                    db, draft, candidate, commit=False
                )
                entity = await campaign_service.get_entity(promotion["entity_id"], db)
                if entity is None:
                    raise LookupError("Promoted campaign entity could not be reloaded")
                decision = decisions[candidate["id"]]
                provenance = CampaignEntityProvenance(
                    entity_id=entity.id,
                    draft_id=draft.id,
                    candidate_id=candidate["id"],
                    source_hash=draft.source_hash,
                    source_name=draft.source_name,
                    candidate_type=candidate["candidate_type"],
                    reviewer=decision.get("reviewer"),
                    accepted_at=datetime.fromisoformat(decision["reviewed_at"]),
                    candidate_payload=candidate["payload"],
                    entity_stable_key=entity.stable_key,
                    entity_type=entity.entity_type,
                    entity_name=entity.name,
                )
                db.add(provenance)
                await db.flush()
                decision["promotion"] = promotion
                decision["provenance_id"] = provenance.id
            draft.decisions = decisions
            await self._finish(db, draft, commit)
        except Exception:
            await db.rollback()
            raise
        return self.draft_to_dict(draft)

    def _candidate_entity_type(self, candidate: dict[str, Any]) -> str:
        if candidate["candidate_type"] == "entity":
            return str(candidate["payload"]["entity_type"])
        if candidate["candidate_type"] == "calendar":
            return "calendar"
        return "event"

    async def _assert_candidate_baseline(
        self, db: AsyncSession, candidate: dict[str, Any]
    ) -> None:
        payload = candidate["payload"]
        reference = payload.get("stable_key") or payload["name"]
        current = await campaign_service.find_entity_by_reference(
            db, reference, entity_types=[self._candidate_entity_type(candidate)]
        )
        baseline = candidate.get("baseline")
        if baseline is None and current is None:
            return
        if (
            baseline is not None
            and current is not None
            and baseline["id"] == current.id
            and baseline["updated_at"] == current.updated_at.isoformat()
        ):
            return
        raise SessionUpdateConflict(
            "The target campaign entity changed after preview. Review the current "
            "entity and create a fresh draft before promoting this candidate."
        )

    async def _promote_candidate(
        self,
        db: AsyncSession,
        draft: SessionUpdateDraft,
        candidate: dict[str, Any],
        *,
        commit: bool = True,
    ) -> dict[str, Any]:
        candidate_type = candidate["candidate_type"]
        payload = candidate["payload"]
        if candidate_type == "entity":
            relationships = [
                ParsedRelationship(**item) for item in payload.get("relationships", [])
            ]
            parsed = ParsedEntityNote(**{**payload, "relationships": relationships})
            result = await campaign_note_import_service.apply_parsed_entities(
                db, [parsed], commit=commit
            )
            if not result["entities"]:
                raise LookupError("Promoted entity was not returned by importer")
            return {
                "entity_id": result["entities"][0]["id"],
                "entity_type": result["entities"][0]["entity_type"],
                "created_entities": result["summary"]["created_entities"],
                "updated_entities": result["summary"]["updated_entities"],
                "warnings": result["warnings"],
            }
        entity, created = await campaign_service.upsert_entity(
            db,
            entity_type="calendar" if candidate_type == "calendar" else "event",
            name=payload["name"],
            summary=payload.get("summary"),
            details=payload.get("details")
            or {"current_date": payload.get("current_date", {})},
            tags=payload.get("tags", draft.default_tags),
            commit=commit,
        )
        return {
            "entity_id": entity.id,
            "entity_type": entity.entity_type,
            "created": created,
        }

    @_review_write
    async def finalize_review_draft(
        self,
        db: AsyncSession,
        *,
        draft_id: int,
        decision: str,
        reason: Optional[str] = None,
        reviewer: Optional[str] = None,
        expected_revision: Optional[int] = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("Session log decision must be approved or rejected")
        if decision == "rejected" and not (reason or "").strip():
            raise ValueError("A reason is required when rejecting a session log")
        draft = await self._lock_review_draft(db, draft_id, expected_revision)
        if draft.status == "finalized":
            if draft.session_log_decision == decision:
                return self.draft_to_dict(draft)
            raise ValueError("Finalized session log decisions are final")
        pending = [
            item["id"]
            for item in draft.candidates
            if (draft.decisions or {}).get(item["id"], {}).get("decision")
            in {None, "promoting"}
        ]
        if pending:
            raise ValueError(
                "Decide every extracted candidate before finalizing the session log"
            )
        unpromoted = [
            item["id"]
            for item in draft.candidates
            if (draft.decisions or {}).get(item["id"], {}).get("decision") == "accepted"
            and not (draft.decisions or {}).get(item["id"], {}).get("provenance_id")
        ]
        if unpromoted:
            raise ValueError(
                "Promote accepted candidates before finalizing the session log"
            )
        document = await ingestion_service.ingest_document(
            db,
            title=draft.title,
            kind="session_log",
            content=draft.content,
            summary=self._document_summary(
                draft.title, self.parse_metadata(draft.content)
            ),
            source_name=draft.source_name,
            url=f"session-update-draft://{draft.id}",
            dedupe_on_url=True,
            source_class="private_local",
            privacy_scope="private_local",
            review_status=decision,
            visibility_scope="gm_only",
            rag_eligible=decision == "approved",
            train_eligible=False,
            commit=False,
        )
        draft.status = "finalized"
        draft.session_log_decision = decision
        draft.session_log_document_id = document.id
        decisions = dict(draft.decisions or {})
        decisions["session_log"] = {
            "decision": decision,
            "reason": reason,
            "reviewer": reviewer,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        draft.decisions = decisions
        await self._finish(db, draft, commit)
        return self.draft_to_dict(draft)

    def draft_to_dict(
        self, draft: SessionUpdateDraft, *, include_content: bool = False
    ) -> dict[str, Any]:
        payload = {
            "id": draft.id,
            "title": draft.title,
            "campaign_id": draft.campaign_id,
            "source_name": draft.source_name,
            "source_hash": draft.source_hash,
            "candidates": draft.candidates,
            "decisions": draft.decisions or {},
            "status": draft.status,
            "session_log_decision": draft.session_log_decision,
            "session_log_document_id": draft.session_log_document_id,
            "revision": draft.revision,
        }
        if include_content:
            payload["content"] = draft.content
        return payload

    async def import_session_update(
        self,
        db: AsyncSession,
        *,
        title: str,
        content: str,
        source_name: Optional[str] = None,
        document_url: Optional[str] = None,
        default_tags: Optional[list[str]] = None,
        store_document: bool = True,
        document_governance: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        parsed_meta = self.parse_metadata(content)
        parsed_entities = self.parse_entities(content, default_tags=default_tags)
        entity_result = (
            await campaign_note_import_service.apply_parsed_entities(
                db, parsed_entities
            )
            if parsed_entities
            else {
                "summary": {
                    "created_entities": 0,
                    "updated_entities": 0,
                    "created_relationships": 0,
                    "updated_relationships": 0,
                },
                "entities": [],
                "warnings": [],
            }
        )

        stored_document = None
        if store_document:
            stored_document = await ingestion_service.ingest_document(
                db,
                title=title,
                kind="session_log",
                content=content,
                summary=self._document_summary(title, parsed_meta),
                source_name=source_name,
                url=document_url,
                dedupe_on_url=bool(document_url),
                **(document_governance or {}),
            )

        created_entities = entity_result["summary"]["created_entities"]
        updated_entities = entity_result["summary"]["updated_entities"]
        warnings = list(entity_result["warnings"])

        calendar_payload = None
        current_date = self._parse_mapping(parsed_meta.metadata.get("current date"))
        if current_date or parsed_meta.metadata.get("calendar"):
            calendar_name = parsed_meta.metadata.get("calendar") or "Campaign Calendar"
            calendar, created = await campaign_service.upsert_entity(
                db,
                entity_type="calendar",
                name=calendar_name,
                details={"current_date": current_date} if current_date else {},
            )
            calendar_payload = campaign_service.entity_to_dict(calendar)
            if created:
                created_entities += 1
            else:
                updated_entities += 1

        session_event = None
        if parsed_meta.changelog:
            session_event, created = await campaign_service.upsert_entity(
                db,
                entity_type="event",
                name=title,
                summary=parsed_meta.metadata.get("summary"),
                details={
                    "timeline_position": parsed_meta.metadata.get("timeline position")
                    or "session-update",
                    "scheduled_for": parsed_meta.metadata.get("scheduled for")
                    or parsed_meta.metadata.get("current date"),
                    "status": "resolved",
                    "consequences": parsed_meta.changelog,
                },
                tags=default_tags,
            )
            if created:
                created_entities += 1
            else:
                updated_entities += 1

        return {
            "document": (
                {
                    "id": stored_document.id,
                    "title": stored_document.title,
                    "kind": stored_document.kind,
                    "source_name": stored_document.source_name,
                    "source_class": stored_document.source_class,
                    "privacy_scope": stored_document.privacy_scope,
                    "review_status": stored_document.review_status,
                    "visibility_scope": stored_document.visibility_scope,
                    "rag_eligible": stored_document.rag_eligible,
                    "train_eligible": stored_document.train_eligible,
                }
                if stored_document is not None
                else None
            ),
            "summary": {
                "created_entities": created_entities,
                "updated_entities": updated_entities,
                "created_relationships": entity_result["summary"][
                    "created_relationships"
                ],
                "updated_relationships": entity_result["summary"][
                    "updated_relationships"
                ],
            },
            "entities": entity_result["entities"],
            "calendar": calendar_payload,
            "session_event": (
                campaign_service.entity_to_dict(session_event)
                if session_event is not None
                else None
            ),
            "changelog": parsed_meta.changelog,
            "warnings": warnings,
        }

    def parse_metadata(self, content: str) -> ParsedSessionUpdate:
        frontmatter, body = split_frontmatter(content)
        normalized_body = replace_wikilinks(body)
        metadata: dict[str, str] = {}
        changelog: list[str] = []
        in_changelog = False
        seen_entity_header = False
        for raw_line in normalized_body.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("##") and ENTITY_HEADER_RE.match(stripped):
                seen_entity_header = True
                in_changelog = False
                continue
            if stripped.lower() == "## changelog":
                in_changelog = True
                continue
            if in_changelog:
                changelog.append(
                    stripped[2:].strip() if stripped.startswith("- ") else stripped
                )
                continue
            if seen_entity_header:
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                metadata[key.strip().lower()] = value.strip()
        for key, value in frontmatter.items():
            normalized_key = key.strip().lower().replace("_", " ")
            if normalized_key == "tags" or normalized_key in metadata:
                continue
            if isinstance(value, list):
                metadata[normalized_key] = ", ".join(str(item) for item in value)
            elif value is not None:
                metadata[normalized_key] = str(value)
        return ParsedSessionUpdate(metadata=metadata, changelog=changelog)

    def parse_entities(
        self, content: str, *, default_tags: Optional[list[str]] = None
    ) -> list[Any]:
        frontmatter, body = split_frontmatter(content)
        normalized_tags = campaign_service._normalize_strings(
            [*(default_tags or []), *extract_tags(frontmatter)]
        )
        normalized_body = replace_wikilinks(body)
        entity_lines: list[str] = []
        capture = False
        for raw_line in normalized_body.splitlines():
            stripped = raw_line.strip()
            if stripped.lower() == "## changelog":
                capture = False
                continue
            if stripped.startswith("##") and ENTITY_HEADER_RE.match(stripped):
                capture = True
            if capture:
                entity_lines.append(raw_line)
        if not entity_lines:
            return []
        return campaign_note_import_service.parse_content(
            "\n".join(entity_lines),
            default_tags=normalized_tags,
        )

    def _parse_mapping(self, value: Optional[str]) -> dict[str, Any]:
        if not value:
            return {}
        return campaign_note_import_service._parse_mapping(value)

    def _document_summary(self, title: str, parsed_meta: ParsedSessionUpdate) -> str:
        if parsed_meta.changelog:
            return f"Session update '{title}' with {len(parsed_meta.changelog)} changelog entries."
        return f"Session update '{title}'."


session_update_service = SessionUpdateService()
