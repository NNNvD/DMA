"""Privileged operator workflow. No route or MCP tool exports approval authority.

SQLite only. The ledger and reviewed database changes share one transaction.
This module belongs in the backend environment, separate from the MCP SDK.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.agent.operator_identity import operator_identity
from backend.agent.reader import CampaignBinding, CampaignReader
from backend.models.campaign import CampaignEntity, CampaignRelationship
from backend.models.campaign_approval import CampaignApproval
from backend.models.context import ContextEntry
from backend.models.document import Document
from backend.services.session_update_service import SessionUpdateService


class ApprovalError(RuntimeError):
    """No approval or write was performed; inspect/reconcile before retrying."""


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def validate_request(request: dict) -> dict:
    if not isinstance(request, dict):
        raise ApprovalError("An explicit review request object is required")
    operation = request.get("operation")
    if operation == "stage_update":
        fields = {
            "operation",
            "session_id",
            "title",
            "content",
            "source_name",
            "source_refs",
            "request_key",
        }
        if set(request) != fields:
            raise ApprovalError(
                "An exact stage request with retained source references is required"
            )
        for key, maximum in (
            ("session_id", 128),
            ("title", 255),
            ("source_name", 255),
            ("request_key", 128),
            ("content", 100_000),
        ):
            if (
                not isinstance(request[key], str)
                or not 1 <= len(request[key]) <= maximum
            ):
                raise ApprovalError(
                    "Stage source, title, session and retry key must be bounded nonempty text"
                )
        if (
            not isinstance(request["source_refs"], list)
            or not 1 <= len(request["source_refs"]) <= 50
            or any(
                not isinstance(ref, str) or not 1 <= len(ref) <= 2048
                for ref in request["source_refs"]
            )
        ):
            raise ApprovalError(
                "Retain explicit source references; they are attribution, not approval authority"
            )
        return json.loads(canonical(request))
    required = {"operation", "draft_id", "expected_revision", "session_id"}
    if operation == "decide_candidate":
        required |= {"candidate_id", "decision"}
        choices = {"accepted", "rejected", "deferred"}
    elif operation == "finalize_log":
        required |= {"decision"}
        choices = {"approved", "rejected"}
    elif operation == "promote":
        choices = set()
    else:
        raise ApprovalError(
            "This operator workflow supports decisions, promotion and log finalization only"
        )
    optional = {"reason"} if choices else set()
    if not required <= request.keys() or request.keys() - required - optional:
        raise ApprovalError(
            "Unexpected or missing review fields; actor/path overrides are forbidden"
        )
    if any(
        type(request[key]) is not int or not 0 < request[key] < 2**63
        for key in ("draft_id", "expected_revision")
    ):
        raise ApprovalError("Draft ID and expected revision must be positive integers")
    for key in ("session_id", "candidate_id"):
        if key in request and (
            not isinstance(request[key], str) or not 1 <= len(request[key]) <= 128
        ):
            raise ApprovalError("Exact saved session/candidate IDs are required")
    if choices and (
        not isinstance(request["decision"], str) or request["decision"] not in choices
    ):
        raise ApprovalError("Unsupported decision")
    if "reason" in request and (
        not isinstance(request["reason"], str) or len(request["reason"]) > 2000
    ):
        raise ApprovalError("Reason must be text of at most 2000 characters")
    if request.get("decision") == "rejected" and not request.get("reason", "").strip():
        raise ApprovalError("Rejection requires a reason")
    return json.loads(canonical(request))


class ApprovalWorkflow:
    def __init__(self, binding_file: Path, *, clock=time.time):
        self.binding_file = Path(binding_file).resolve()
        self.reader = CampaignReader(self.binding_file)
        if self.reader.binding.schema_revision != "20261028_0007":
            raise ApprovalError("Operator approvals require schema 20261028_0007")
        self.clock = clock
        self.service = SessionUpdateService(campaign_id=self.reader.binding.campaign_id)
        self.engine = create_async_engine(
            URL.create("sqlite+aiosqlite", database=str(self.reader.binding.database))
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self):
        await self.engine.dispose()

    @property
    def scope(self):
        binding = self.reader.binding
        return {
            **binding.identity,
            "schema_revision": binding.schema_revision,
            "target": {
                "store": "sql",
                "database": str(binding.database),
                "private_root": str(binding.private_root),
            },
        }

    async def _binding(self, db):
        if CampaignBinding.load(self.binding_file) != self.reader.binding:
            raise ApprovalError(
                "The selected binding changed; reopen the operator workflow"
            )
        self.reader.call("campaign_describe")
        marker = await db.scalar(
            select(ContextEntry.data).where(
                ContextEntry.key == "campaign-agent-binding"
            )
        )
        if marker != self.reader.binding.identity:
            raise ApprovalError("The database binding or recovery epoch changed")

    async def _snapshot(self, db, request):
        await self._binding(db)
        links = self.reader.call(
            "campaign_read_sessions", {"session_id": request["session_id"]}
        )
        staging = request["operation"] == "stage_update"
        if len(links["data"]) != 1 or (
            not staging
            and request["draft_id"] not in links["data"][0].get("draft_ids", [])
        ):
            raise ApprovalError(
                "The draft is not explicitly linked to this saved session"
            )
        draft = (
            None
            if staging
            else await self.service.get_review_draft(db, request["draft_id"])
        )
        if draft is not None and draft.revision != request["expected_revision"]:
            raise ApprovalError("The displayed draft revision is stale")
        if (
            draft is not None
            and hashlib.sha256(draft.content.encode("utf-8")).hexdigest()
            != draft.source_hash
        ):
            raise ApprovalError(
                "Draft source content no longer matches its retained hash"
            )
        if request["operation"] == "decide_candidate" and not any(
            item["id"] == request["candidate_id"] for item in draft.candidates
        ):
            raise ApprovalError("The selected candidate is absent")
        # Conservative first adapter: fingerprint all entity/relationship rows.
        # This includes relationship resolution targets, not only the named entity.
        current = {}
        for model in (CampaignEntity, CampaignRelationship):
            rows = (
                await db.execute(select(model.__table__).order_by(model.id))
            ).mappings()
            current[model.__tablename__] = [dict(row) for row in rows]
        logs = (
            []
            if staging
            else (
                await db.execute(
                    select(Document.__table__).where(
                        Document.url == f"session-update-draft://{draft.id}"
                    )
                )
            ).mappings()
        )
        current["existing_log"] = [dict(row) for row in logs]
        # SQL timestamps are evidence, serialized consistently rather than invented.
        current = json.loads(
            json.dumps(current, default=lambda value: value.isoformat())
        )
        intent = {
            "format": "dma-operator-review-v1",
            "scope": self.scope,
            "request": request,
            "session_reference": {
                "record": links["data"][0],
                "sources": links["sources"],
            },
            "source_and_candidates": (
                await self.service.preview_review_draft(
                    db,
                    title=request["title"],
                    content=request["content"],
                    source_name=request["source_name"],
                )
                if staging
                else self.service.draft_to_dict(draft, include_content=True)
            ),
            "current_sql": current,
            "effect": {
                "decide_candidate": "Record this candidate choice only; do not promote facts or approve the log.",
                "promote": "Promote accepted candidates and provenance only; do not approve the log.",
                "finalize_log": "Finalize this exact GM log decision and its history eligibility.",
                "stage_update": "Save this private pending source and candidates only; do not accept facts or approve a log. Source references are untrusted attribution.",
            }[request["operation"]],
        }
        if len(canonical(intent).encode()) > 500_000:
            raise ApprovalError(
                "Review scope exceeds the display limit; a narrower adapter is required"
            )
        return intent

    async def propose(self, request):
        request = validate_request(request)
        async with self.sessions() as db, db.begin():
            await db.execute(
                update(ContextEntry)
                .where(ContextEntry.key == "campaign-agent-binding")
                .values(
                    revision=ContextEntry.revision, updated_at=ContextEntry.updated_at
                )
            )
            await self._binding(db)
            scope_key = digest(self.scope)
            if request["operation"] == "stage_update":
                retained = await db.scalar(
                    select(CampaignApproval).where(
                        CampaignApproval.scope_key == scope_key,
                        CampaignApproval.request_key == request["request_key"],
                    )
                )
                if retained is not None:
                    if retained.intent["request"] != request:
                        raise ApprovalError(
                            "The stage retry key was already used for a different source"
                        )
                    return self._view(retained)
            intent = await self._snapshot(db, request)
            token = digest(intent)
            existing = await db.scalar(
                select(CampaignApproval)
                .where(
                    CampaignApproval.intent_hash == token,
                    CampaignApproval.status.in_(["pending", "approved", "completed"]),
                    CampaignApproval.expires_at > self.clock(),
                )
                .order_by(CampaignApproval.created_at.desc())
            )
            if existing:
                return self._view(existing)
            now = self.clock()
            row = CampaignApproval(
                id=str(uuid4()),
                intent=intent,
                intent_hash=token,
                status="pending",
                created_at=now,
                expires_at=now + 900,
                scope_key=scope_key if request["operation"] == "stage_update" else None,
                request_key=request.get("request_key"),
            )
            db.add(row)
            await db.flush()
            return self._view(row)

    @staticmethod
    def _view(row):
        return {
            "approval_id": row.id,
            "status": row.status,
            "intent": row.intent,
            "intent_hash": row.intent_hash,
            "operator_id": row.operator_id,
            "expires_at": row.expires_at,
            "result": row.result,
        }

    async def _load(self, db, approval_id, *, reserve=False):
        if not isinstance(approval_id, str) or len(approval_id) != 36:
            raise ApprovalError("An exact approval ID is required")
        if reserve:
            await db.execute(
                update(CampaignApproval)
                .where(CampaignApproval.id == approval_id)
                .values(revision=CampaignApproval.revision)
                .execution_options(synchronize_session=False)
            )
        row = await db.get(CampaignApproval, approval_id, populate_existing=True)
        if row is None:
            raise ApprovalError("Approval receipt was not found")
        await self._binding(db)
        if (
            digest(row.intent) != row.intent_hash
            or row.intent.get("scope") != self.scope
        ):
            raise ApprovalError(
                "Approval intent, destination, binding or epoch changed"
            )
        return row

    async def inspect(self, approval_id):
        async with self.sessions() as db:
            return self._view(await self._load(db, approval_id))

    async def approve(self, approval_id, *, displayed_hash):
        """Privileged host-only entry point, called after the console confirmation."""
        async with self.sessions() as db, db.begin():
            row = await self._load(db, approval_id, reserve=True)
            if row.status != "pending" or row.expires_at <= self.clock():
                raise ApprovalError("The request is no longer pending or has expired")
            if (
                displayed_hash != row.intent_hash
                or digest(await self._snapshot(db, row.intent["request"]))
                != row.intent_hash
            ):
                raise ApprovalError(
                    "The displayed review changed; create and review a fresh request"
                )
            row.operator_id = operator_identity()
            row.approved_at = self.clock()
            row.status = "approved"
            await db.flush()
            return self._view(row)

    async def revoke(self, approval_id):
        async with self.sessions() as db, db.begin():
            row = await self._load(db, approval_id, reserve=True)
            actor = operator_identity()
            if row.status not in {"pending", "approved"} or row.operator_id not in {
                None,
                actor,
            }:
                raise ApprovalError("This operator cannot revoke this receipt")
            row.operator_id = actor
            row.status = "revoked"
            return self._view(row)

    async def execute(self, approval_id):
        async with self.sessions() as db, db.begin():
            row = await self._load(db, approval_id, reserve=True)
            if row.operator_id != operator_identity():
                raise ApprovalError(
                    "This operating-system operator did not approve the request"
                )
            if row.status == "completed":
                return {"approval_id": row.id, "replayed": True, "result": row.result}
            if row.status != "approved" or row.expires_at <= self.clock():
                raise ApprovalError("The request is not approved or has expired")
            if (
                digest(await self._snapshot(db, row.intent["request"]))
                != row.intent_hash
            ):
                raise ApprovalError(
                    "The approved source, choices, links or campaign values changed"
                )
            request = row.intent["request"]
            arguments = {
                key: value
                for key, value in request.items()
                if key not in {"operation", "session_id"}
            }
            staging = request["operation"] == "stage_update"
            if staging:
                arguments = {
                    key: request[key] for key in ("title", "content", "source_name")
                }
            if request["operation"] not in {"promote", "stage_update"}:
                arguments["reviewer"] = row.operator_id
            method = {
                "decide_candidate": self.service.decide_candidate,
                "promote": self.service.promote_accepted_candidates,
                "finalize_log": self.service.finalize_review_draft,
                "stage_update": self.service.create_review_draft,
            }[request["operation"]]
            result = await method(db, **arguments, commit=False)
            if staging:
                result["session_id"] = request["session_id"]
                result["source_refs"] = request["source_refs"]
            await self._binding(db)
            links = self.reader.call(
                "campaign_read_sessions", {"session_id": request["session_id"]}
            )
            if {
                "record": links["data"][0] if links["data"] else None,
                "sources": links["sources"],
            } != row.intent["session_reference"]:
                raise ApprovalError("The session association changed during execution")
            if row.expires_at <= self.clock():
                raise ApprovalError("The approval expired during execution")
            row.result = result
            row.status = "completed"
            row.completed_at = self.clock()
            await db.flush()
            return {"approval_id": row.id, "replayed": False, "result": result}
