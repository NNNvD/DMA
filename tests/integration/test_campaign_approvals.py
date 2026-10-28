import asyncio
import copy
import io
import json
import shutil
import sqlite3

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.agent import approvals
from backend.agent.approvals import ApprovalError, ApprovalWorkflow, validate_request
from backend.agent.reader import CampaignReader
from backend.models.base import Base
from backend.models.document import Document
from backend.services.embedding_service import embedding_service
from backend.services.session_update_service import SessionUpdateService
from scripts.review_campaign_approval import confirm_review

# Register existing model metadata for the disposable full-schema database.
import backend.models.chunk  # noqa: F401
import backend.models.context  # noqa: F401


IDENTITY = {
    "binding_id": "fixture-approval",
    "campaign_id": "fictional-review",
    "recovery_epoch": "epoch-1",
    "role": "gm",
}


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    path = tmp_path_factory.mktemp("approval-template") / "fictional.sqlite3"

    async def seed():
        engine = create_async_engine("sqlite+aiosqlite:///" + path.as_posix())
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
                await connection.exec_driver_sql(
                    "CREATE TABLE alembic_version (version_num TEXT)"
                )
                await connection.exec_driver_sql(
                    "INSERT INTO alembic_version VALUES ('20261028_0007')"
                )
                await connection.exec_driver_sql(
                    "INSERT INTO contexts(key,data,revision,updated_at) VALUES (?,?,1,'2026-10-28')",
                    ("campaign-agent-binding", json.dumps(IDENTITY)),
                )
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            service = SessionUpdateService(campaign_id=IDENTITY["campaign_id"])
            async with sessions() as db:
                await service.create_review_draft(
                    db,
                    title="Fictional bridge session",
                    content="## Location: Silverbridge\nSummary: Confirmed bridge town\n",
                )
        finally:
            await engine.dispose()

    asyncio.run(seed())
    return path


@pytest.fixture
def bound(tmp_path, template, monkeypatch):
    monkeypatch.setattr(embedding_service, "provider", "disabled")
    monkeypatch.setattr(approvals, "operator_identity", lambda: "test-os-operator")
    database = tmp_path / "fictional.sqlite3"
    shutil.copyfile(template, database)
    private = tmp_path / "private"
    campaign = private / "campaigns" / IDENTITY["campaign_id"]
    campaign.mkdir(parents=True)
    (private / ".dma-agent-binding.json").write_text(json.dumps(IDENTITY))
    (campaign / "agent-session-links.json").write_text(
        json.dumps(
            {
                "campaign_id": IDENTITY["campaign_id"],
                "items": [
                    {"id": "session-1", "draft_ids": [1], "log_document_ids": []}
                ],
            }
        )
    )
    binding = tmp_path / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "format": "dma-agent-binding-v1",
                **IDENTITY,
                "schema_revision": "20261028_0007",
                "database": "fictional.sqlite3",
                "private_root": "private",
            }
        )
    )
    return binding, database, private


def request(operation="decide_candidate", revision=1):
    value = {
        "operation": operation,
        "session_id": "session-1",
        "draft_id": 1,
        "expected_revision": revision,
    }
    if operation == "decide_candidate":
        value.update(candidate_id="entity-0", decision="accepted")
    elif operation == "finalize_log":
        value["decision"] = "approved"
    return value


async def granted(workflow, payload):
    proposed = await workflow.propose(payload)
    return await workflow.approve(
        proposed["approval_id"], displayed_hash=proposed["intent_hash"]
    )


def test_approval_is_separate_from_execution_and_each_operation_needs_its_own_receipt(
    bound,
):
    binding, _, _ = bound

    async def scenario():
        workflow = ApprovalWorkflow(binding)
        try:
            pending = await workflow.propose(request())
            assert (await workflow.propose(request()))["approval_id"] == pending[
                "approval_id"
            ]
            with pytest.raises(ApprovalError):
                await workflow.execute(pending["approval_id"])
            approved = await workflow.approve(
                pending["approval_id"], displayed_hash=pending["intent_hash"]
            )
            assert approved["operator_id"] == "test-os-operator"
            reader = CampaignReader(binding)
            assert (
                reader.call("session_read_review", {"draft_id": 1})["data"][0][
                    "decisions"
                ]
                == {}
            )
            result = await workflow.execute(approved["approval_id"])
            assert result["replayed"] is False
            assert reader.call("campaign_read_entities")["data"] == []
            replay = await workflow.execute(approved["approval_id"])
            assert replay["result"] == result["result"] and replay["replayed"] is True
            fresh = ApprovalWorkflow(binding)
            try:
                assert (await fresh.execute(approved["approval_id"]))[
                    "result"
                ] == result["result"]
            finally:
                await fresh.close()
            with pytest.raises(ApprovalError):
                await workflow.propose(request("promote", 1))
            promote = await granted(workflow, request("promote", 2))
            assert (
                len(
                    (await workflow.execute(promote["approval_id"]))["result"][
                        "decisions"
                    ]
                )
                == 1
            )
            assert len(reader.call("campaign_read_entities")["data"]) == 1
            assert reader.call("campaign_read_history")["data"] == []
            final = await granted(workflow, request("finalize_log", 3))
            completed = await workflow.execute(final["approval_id"])
            assert len(reader.call("campaign_read_history")["data"]) == 1
            assert (await workflow.execute(final["approval_id"]))[
                "result"
            ] == completed["result"]
            async with workflow.sessions() as db:
                assert len((await db.execute(select(Document))).scalars().all()) == 1
        finally:
            await workflow.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "damage",
    ["draft", "candidate", "entity", "links", "epoch", "binding", "intent", "actor"],
)
def test_altered_or_foreign_approval_cannot_write(bound, monkeypatch, damage):
    binding, database, private = bound

    async def scenario():
        workflow = ApprovalWorkflow(binding)
        try:
            approved = await granted(workflow, request())
            if damage == "links":
                path = private / "campaigns/fictional-review/agent-session-links.json"
                data = json.loads(path.read_text())
                data["items"][0]["draft_ids"] = []
                path.write_text(json.dumps(data))
            elif damage == "epoch":
                path = private / ".dma-agent-binding.json"
                data = json.loads(path.read_text())
                data["recovery_epoch"] = "restored"
                path.write_text(json.dumps(data))
            elif damage == "binding":
                data = json.loads(binding.read_text())
                data["binding_id"] = "fixture-other"
                binding.write_text(json.dumps(data))
            elif damage == "actor":
                monkeypatch.setattr(
                    approvals, "operator_identity", lambda: "another-os-operator"
                )
            else:
                with sqlite3.connect(database) as db:
                    if damage == "draft":
                        db.execute(
                            "UPDATE session_update_drafts SET content='Changed source'"
                        )
                    elif damage == "candidate":
                        value = json.loads(
                            db.execute(
                                "SELECT candidates FROM session_update_drafts"
                            ).fetchone()[0]
                        )
                        value[0]["payload"]["summary"] = "Changed candidate"
                        db.execute(
                            "UPDATE session_update_drafts SET candidates=?",
                            (json.dumps(value),),
                        )
                    elif damage == "entity":
                        db.execute(
                            "INSERT INTO campaign_entities(stable_key,entity_type,name,details,tags,is_active,created_at,updated_at) VALUES ('changed','location','New place','{}','[]',1,'2026-10-28','2026-10-28')"
                        )
                    else:
                        data = copy.deepcopy(approved["intent"])
                        data["request"]["decision"] = "deferred"
                        db.execute(
                            "UPDATE campaign_approvals SET intent=?",
                            (json.dumps(data),),
                        )
            with pytest.raises((ApprovalError, RuntimeError)):
                await workflow.execute(approved["approval_id"])
            with sqlite3.connect(database) as db:
                assert (
                    json.loads(
                        db.execute(
                            "SELECT decisions FROM session_update_drafts"
                        ).fetchone()[0]
                    )
                    == {}
                )
                assert (
                    db.execute("SELECT status FROM campaign_approvals").fetchone()[0]
                    == "approved"
                )
        finally:
            await workflow.close()

    asyncio.run(scenario())


def test_display_hash_expiry_revocation_and_completed_retry(bound):
    binding, _, _ = bound

    async def scenario():
        now = [1000.0]
        workflow = ApprovalWorkflow(binding, clock=lambda: now[0])
        try:
            pending = await workflow.propose(request())
            with pytest.raises(ApprovalError):
                await workflow.approve(
                    pending["approval_id"], displayed_hash="invented-by-model"
                )
            now[0] += 901
            with pytest.raises(ApprovalError):
                await workflow.approve(
                    pending["approval_id"], displayed_hash=pending["intent_hash"]
                )
            second = await granted(workflow, request())
            await workflow.revoke(second["approval_id"])
            with pytest.raises(ApprovalError):
                await workflow.execute(second["approval_id"])
            third = await granted(workflow, request())
            await workflow.execute(third["approval_id"])
            expiring = await granted(workflow, request("promote", 2))
            now[0] += 901
            with pytest.raises(ApprovalError):
                await workflow.execute(expiring["approval_id"])
            assert (await workflow.execute(third["approval_id"]))["replayed"] is True
        finally:
            await workflow.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("operation", ["decide_candidate", "promote", "finalize_log"])
def test_failure_after_review_write_rolls_back_receipt_and_decision(
    bound, monkeypatch, operation
):
    binding, database, _ = bound

    async def scenario():
        workflow = ApprovalWorkflow(binding)
        try:
            revision = 1
            if operation != "decide_candidate":
                first = await granted(workflow, request())
                await workflow.execute(first["approval_id"])
                revision = 2
            if operation == "finalize_log":
                first = await granted(workflow, request("promote", 2))
                await workflow.execute(first["approval_id"])
                revision = 3
            approved = await granted(workflow, request(operation, revision))
            method = {
                "decide_candidate": "decide_candidate",
                "promote": "promote_accepted_candidates",
                "finalize_log": "finalize_review_draft",
            }[operation]
            original = getattr(workflow.service, method)

            async def fail(*args, **kwargs):
                await original(*args, **kwargs)
                raise RuntimeError("fixture after review write")

            monkeypatch.setattr(workflow.service, method, fail)
            with pytest.raises(RuntimeError, match="fixture after"):
                await workflow.execute(approved["approval_id"])
            with sqlite3.connect(database) as db:
                assert (
                    db.execute("SELECT revision FROM session_update_drafts").fetchone()[
                        0
                    ]
                    == revision
                )
                assert (
                    db.execute(
                        "SELECT status FROM campaign_approvals WHERE id=?",
                        (approved["approval_id"],),
                    ).fetchone()[0]
                    == "approved"
                )
                assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 0
                if operation == "promote":
                    assert (
                        db.execute("SELECT count(*) FROM campaign_entities").fetchone()[
                            0
                        ]
                        == 0
                    )
                    assert (
                        db.execute(
                            "SELECT count(*) FROM campaign_entity_provenance"
                        ).fetchone()[0]
                        == 0
                    )
            monkeypatch.setattr(workflow.service, method, original)
            result = (await workflow.execute(approved["approval_id"]))["result"]
            assert result.get("draft_revision", result.get("revision")) == revision + 1
        finally:
            await workflow.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "extra",
    [
        {"reviewer": "DM"},
        {"actor": "GM"},
        {"database": "elsewhere"},
        {"approval": True},
    ],
)
def test_model_supplied_authority_fields_are_rejected(extra):
    with pytest.raises(ApprovalError):
        validate_request({**request(), **extra})


def test_console_displays_exact_intent_and_refuses_noninteractive_approval():
    view = {"intent_hash": "a" * 64, "intent": {"source": "untrusted\x1b[2J"}}
    source = io.StringIO("APPROVE " + view["intent_hash"] + "\n")
    with pytest.raises(ValueError, match="interactive"):
        confirm_review(view, source=source, destination=io.StringIO())
    source.isatty = lambda: True
    output = io.StringIO()
    assert confirm_review(view, source=source, destination=output)
    assert "\\u001b" in output.getvalue() and "\x1b" not in output.getvalue()
    assert view["intent_hash"] in output.getvalue()


def test_concurrent_execution_consumes_a_receipt_once(bound):
    binding, _, _ = bound

    async def scenario():
        first, second = ApprovalWorkflow(binding), ApprovalWorkflow(binding)
        try:
            approved = await granted(first, request())
            results = await asyncio.gather(
                first.execute(approved["approval_id"]),
                second.execute(approved["approval_id"]),
            )
            assert sorted(item["replayed"] for item in results) == [False, True]
            assert results[0]["result"] == results[1]["result"]
        finally:
            await first.close()
            await second.close()

    asyncio.run(scenario())


def test_staging_requires_approval_retains_session_links_and_deduplicates_retries(
    bound,
):
    binding, database, _ = bound
    payload = {
        "operation": "stage_update",
        "session_id": "session-1",
        "request_key": "dm-message-1",
        "title": "Fictional session capture",
        "content": "## NPC: Ada\nSummary: Uncertain recollection\n",
        "source_name": "DM fixture message",
        "source_refs": ["dm-message://fixture/1"],
    }

    async def scenario():
        workflow = ApprovalWorkflow(binding)
        try:
            pending = await workflow.propose(payload)
            with sqlite3.connect(database) as db:
                assert (
                    db.execute("SELECT count(*) FROM session_update_drafts").fetchone()[
                        0
                    ]
                    == 1
                )
            approved = await workflow.approve(
                pending["approval_id"], displayed_hash=pending["intent_hash"]
            )
            result = await workflow.execute(approved["approval_id"])
            staged = result["result"]
            assert staged["status"] == "pending" and staged["decisions"] == {}
            assert staged["source_refs"] == payload["source_refs"]
            assert (await workflow.propose(payload))["approval_id"] == approved[
                "approval_id"
            ]
            with pytest.raises(ApprovalError, match="retry key"):
                await workflow.propose({**payload, "content": "A different source"})
            reader = CampaignReader(binding)
            saved = reader.call("campaign_read_sessions", {"session_id": "session-1"})
            assert staged["id"] in saved["data"][0]["draft_ids"]
            assert any(ref["store"] == "sql" for ref in saved["sources"])
            followup = {
                "operation": "decide_candidate",
                "draft_id": staged["id"],
                "expected_revision": 1,
                "session_id": "session-1",
                "candidate_id": staged["candidates"][0]["id"],
                "decision": "deferred",
            }
            deferred = await granted(workflow, followup)
            await workflow.execute(deferred["approval_id"])
            assert reader.call("campaign_read_entities")["data"] == []
            assert reader.call("campaign_read_history")["data"] == []
        finally:
            await workflow.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["epoch", "links", "expiry"])
def test_scope_change_during_execution_rolls_back_the_write(bound, monkeypatch, change):
    binding, database, private = bound

    async def scenario():
        now = [1000.0]
        workflow = ApprovalWorkflow(binding, clock=lambda: now[0])
        try:
            approved = await granted(workflow, request())
            original = workflow.service.decide_candidate

            async def mutate_scope(*args, **kwargs):
                result = await original(*args, **kwargs)
                if change == "expiry":
                    now[0] += 901
                else:
                    path = private / (
                        ".dma-agent-binding.json"
                        if change == "epoch"
                        else "campaigns/fictional-review/agent-session-links.json"
                    )
                    payload = json.loads(path.read_text())
                    if change == "epoch":
                        payload["recovery_epoch"] = "restored"
                    else:
                        payload["items"][0]["draft_ids"] = []
                    path.write_text(json.dumps(payload))
                return result

            monkeypatch.setattr(workflow.service, "decide_candidate", mutate_scope)
            with pytest.raises(RuntimeError):
                await workflow.execute(approved["approval_id"])
            with sqlite3.connect(database) as db:
                assert (
                    db.execute("SELECT revision FROM session_update_drafts").fetchone()[
                        0
                    ]
                    == 1
                )
                assert (
                    db.execute("SELECT status FROM campaign_approvals").fetchone()[0]
                    == "approved"
                )
        finally:
            await workflow.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        {"operation": "stage_update"},
        {"expected_revision": True},
        {"decision": "publish"},
        {"candidate_id": ""},
        {"reason": "x" * 2001},
    ],
)
def test_invalid_or_unavailable_operation_arguments_are_rejected(change):
    with pytest.raises(ApprovalError):
        validate_request({**request(), **change})


def test_consistent_restore_epoch_invalidates_receipts_and_staged_link_scope(bound):
    binding, database, private = bound

    async def scenario():
        workflow = ApprovalWorkflow(binding)
        payload = {
            "operation": "stage_update",
            "session_id": "session-1",
            "request_key": "epoch-fixture-1",
            "title": "Epoch fixture",
            "content": "## NPC: Epoch fixture NPC\nSummary: Pending\n",
            "source_name": "Fixture DM message",
            "source_refs": ["dm-message://epoch/1"],
        }
        try:
            approved = await granted(workflow, payload)
            result = await workflow.execute(approved["approval_id"])
            staged_id = result["result"]["id"]
        finally:
            await workflow.close()
        identity = {**IDENTITY, "recovery_epoch": "restored-epoch-2"}
        manifest = json.loads(binding.read_text())
        manifest["recovery_epoch"] = identity["recovery_epoch"]
        binding.write_text(json.dumps(manifest))
        (private / ".dma-agent-binding.json").write_text(json.dumps(identity))
        with sqlite3.connect(database) as db:
            db.execute(
                "UPDATE contexts SET data=? WHERE key='campaign-agent-binding'",
                (json.dumps(identity),),
            )
        fresh = ApprovalWorkflow(binding)
        try:
            with pytest.raises(ApprovalError, match="epoch changed"):
                await fresh.execute(approved["approval_id"])
            links = fresh.reader.call(
                "campaign_read_sessions", {"session_id": "session-1"}
            )
            assert staged_id not in links["data"][0]["draft_ids"]
        finally:
            await fresh.close()

    asyncio.run(scenario())
