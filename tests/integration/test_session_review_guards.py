import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.base import Base
from backend.models.campaign import CampaignEntity
from backend.models.chunk import DocumentChunk
from backend.models.document import Document
from backend.models.session_update_draft import SessionUpdateDraft
from backend.services.campaign_service import campaign_service
from backend.services.embedding_service import embedding_service
from backend.services.ingestion_service import ingestion_service
from backend.services.session_update_service import (
    SessionUpdateConflict,
    session_update_service,
)
from tests.support.app_factory import create_documents_test_app


@pytest.fixture(autouse=True)
def disable_external_embeddings(monkeypatch):
    monkeypatch.setattr(embedding_service, "provider", "disabled")


def test_revision_bound_review_rejects_stale_choices_and_preserves_separate_steps():
    app, engine, _ = create_documents_test_app()
    try:
        with TestClient(app) as client:
            draft = client.post(
                "/api/campaign/session-update-drafts",
                json={
                    "title": "Fictional review",
                    "content": "## Location: Greyhaven\nSummary: A harbor\n\n"
                    "## Location: Blackstone\nSummary: Unconfirmed\n",
                },
            ).json()
            base = f"/api/campaign/session-update-drafts/{draft['id']}"
            first, second = draft["candidates"]
            initial = draft["revision"]
            accepted = client.post(
                f"{base}/candidates/{first['id']}/decision",
                json={"decision": "accepted", "expected_revision": initial},
            )
            assert accepted.status_code == 200
            assert accepted.json()["draft_revision"] == initial + 1
            assert (
                client.post(
                    f"{base}/candidates/{second['id']}/decision",
                    json={"decision": "accepted", "expected_revision": initial},
                ).status_code
                == 409
            )
            assert (
                client.post(
                    f"{base}/promote", json={"expected_revision": initial}
                ).status_code
                == 409
            )
            assert (
                client.post(
                    f"{base}/finalize",
                    json={"decision": "approved", "expected_revision": initial},
                ).status_code
                == 409
            )
            current = client.get(base).json()
            assert set(current["decisions"]) == {first["id"]}
            assert client.get("/api/campaign/entities").json()["total"] == 0
            rejected = client.post(
                f"{base}/candidates/{second['id']}/decision",
                json={
                    "decision": "rejected",
                    "reason": "Not established",
                    "expected_revision": current["revision"],
                },
            )
            assert rejected.status_code == 200
            revision = rejected.json()["draft_revision"]
            promoted = client.post(
                f"{base}/promote", json={"expected_revision": revision}
            )
            assert promoted.status_code == 200
            assert promoted.json()["revision"] == revision + 1
            assert client.get("/api/campaign/session-history").json()["total"] == 0
            # A stale token is rejected even if the operation previously completed.
            assert (
                client.post(
                    f"{base}/promote", json={"expected_revision": revision}
                ).status_code
                == 409
            )
            current_revision = promoted.json()["revision"]
            replay = client.post(
                f"{base}/promote", json={"expected_revision": current_revision}
            )
            assert replay.json() == promoted.json()
            finalized = client.post(
                f"{base}/finalize",
                json={"decision": "approved", "expected_revision": current_revision},
            )
            assert finalized.status_code == 200
            assert finalized.json()["revision"] == current_revision + 1
            assert (
                client.post(
                    f"{base}/finalize",
                    json={
                        "decision": "approved",
                        "expected_revision": current_revision,
                    },
                ).status_code
                == 409
            )
            assert client.get("/api/campaign/entities").json()["total"] == 1
            assert client.get("/api/campaign/session-history").json()["total"] == 1
    finally:
        asyncio.run(engine.dispose())


@pytest.mark.parametrize("invalid", [0, -1, True, "1"])
@pytest.mark.parametrize("operation", ["decision", "promote", "finalize"])
def test_expected_revision_requires_a_positive_integer(invalid, operation):
    app, engine, _ = create_documents_test_app()
    try:
        with TestClient(app) as client:
            suffix = (
                "candidates/entity-0/decision" if operation == "decision" else operation
            )
            payload = {"expected_revision": invalid}
            if operation != "promote":
                payload["decision"] = (
                    "accepted" if operation == "decision" else "approved"
                )
            response = client.post(
                f"/api/campaign/session-update-drafts/1/{suffix}", json=payload
            )
            assert response.status_code == 422
    finally:
        asyncio.run(engine.dispose())


@pytest.mark.parametrize("existing_log", [False, True])
@pytest.mark.parametrize("failure", ["interruption", "stale_flush"])
def test_failed_finalization_rolls_back_log_chunks_and_draft(
    monkeypatch, existing_log, failure
):
    app, engine, session_local = create_documents_test_app()
    original = ingestion_service.ingest_document
    try:
        with TestClient(app) as client:
            draft = client.post(
                "/api/campaign/session-update-drafts",
                json={"title": "Fictional atomic log", "content": "GM-only account."},
            ).json()
            base = f"/api/campaign/session-update-drafts/{draft['id']}"

            async def state():
                async with session_local() as db:
                    docs = (await db.execute(select(Document))).scalars().all()
                    chunks = await db.scalar(
                        select(func.count()).select_from(DocumentChunk)
                    )
                    return [
                        (d.id, d.title, d.content, d.review_status) for d in docs
                    ], chunks

            if existing_log:

                async def seed_existing():
                    async with session_local() as db:
                        await original(
                            db,
                            title="Earlier private draft",
                            kind="session_log",
                            content="Earlier source",
                            url=f"session-update-draft://{draft['id']}",
                            review_status="pending",
                            rag_eligible=False,
                        )

                asyncio.run(seed_existing())
            before = asyncio.run(state())

            async def fail_after_ingestion(*args, **kwargs):
                document = await original(*args, **kwargs)
                if failure == "interruption":
                    raise RuntimeError("fixture interruption after log ingestion")
                # Force a genuine ORM version conflict after log/chunk flush.
                await args[0].execute(
                    update(SessionUpdateDraft)
                    .where(SessionUpdateDraft.id == draft["id"])
                    .values(revision=SessionUpdateDraft.revision + 1)
                    .execution_options(synchronize_session=False)
                )
                return document

            monkeypatch.setattr(
                ingestion_service, "ingest_document", fail_after_ingestion
            )
            payload = {"decision": "approved", "expected_revision": draft["revision"]}
            if failure == "interruption":
                with pytest.raises(RuntimeError, match="fixture interruption"):
                    client.post(f"{base}/finalize", json=payload)
            else:
                assert (
                    client.post(
                        f"{base}/finalize",
                        json=payload,
                    ).status_code
                    == 409
                )
            assert asyncio.run(state()) == before
            assert client.get(base).json()["revision"] == draft["revision"]
            assert client.get(base).json()["status"] == "pending"
            assert client.get("/api/campaign/session-history").json()["total"] == 0
            monkeypatch.setattr(ingestion_service, "ingest_document", original)
            assert (
                client.post(
                    f"{base}/finalize",
                    json={
                        "decision": "approved",
                        "expected_revision": draft["revision"],
                    },
                ).status_code
                == 200
            )
            docs, chunks = asyncio.run(state())
            assert len(docs) == 1
            assert chunks == 1
    finally:
        asyncio.run(engine.dispose())


def test_sqlite_promotion_holds_write_reservation_through_baseline_and_commit(
    tmp_path, monkeypatch
):
    original = session_update_service._assert_candidate_baseline

    async def scenario():
        engine = create_async_engine(
            "sqlite+aiosqlite:///" + (tmp_path / "fictional.db").as_posix()
        )
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as db:
                entity, _ = await campaign_service.upsert_entity(
                    db, entity_type="location", name="Greyhaven", summary="Original"
                )
                entity_id = entity.id
            async with sessions() as db:
                draft = await session_update_service.create_review_draft(
                    db,
                    title="Fictional competing writers",
                    content="## Location: Greyhaven\nSummary: Reviewed source\n",
                )
                await session_update_service.decide_candidate(
                    db,
                    draft_id=draft["id"],
                    candidate_id="entity-0",
                    decision="accepted",
                )
            checked, release, attempted, written = (asyncio.Event() for _ in range(4))

            async def paused_check(db, candidate):
                await original(db, candidate)
                checked.set()
                await asyncio.wait_for(release.wait(), timeout=5)

            monkeypatch.setattr(
                session_update_service, "_assert_candidate_baseline", paused_check
            )

            async def promote():
                async with sessions() as db:
                    return await session_update_service.promote_accepted_candidates(
                        db, draft_id=draft["id"]
                    )

            async def competing_write():
                async with sessions() as db:
                    attempted.set()
                    await db.execute(
                        update(CampaignEntity)
                        .where(CampaignEntity.id == entity_id)
                        .values(summary="Later DM edit")
                    )
                    await db.commit()
                    written.set()

            promotion = asyncio.create_task(promote())
            await asyncio.wait_for(checked.wait(), timeout=5)
            writer = asyncio.create_task(competing_write())
            try:
                await asyncio.wait_for(attempted.wait(), timeout=5)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(written.wait(), timeout=0.1)
            finally:
                release.set()
                await asyncio.gather(promotion, writer)
            async with sessions() as db:
                assert (
                    await db.get(CampaignEntity, entity_id)
                ).summary == "Later DM edit"
                with pytest.raises(SessionUpdateConflict):
                    await session_update_service.promote_accepted_candidates(
                        db, draft_id=draft["id"], expected_revision=draft["revision"]
                    )

            # Two reviewers can both read revision 1; only the first write wins.
            async with sessions() as db:
                race = await session_update_service.create_review_draft(
                    db,
                    title="Fictional reviewer race",
                    content="## Location: Sandwall\nSummary: Unconfirmed\n",
                )
            observed, resume = asyncio.Event(), asyncio.Event()
            original_get = session_update_service.get_review_draft
            async with sessions() as first:

                async def paused_get(db, draft_id):
                    loaded = await original_get(db, draft_id)
                    if db is first:
                        observed.set()
                        await asyncio.wait_for(resume.wait(), timeout=5)
                    return loaded

                monkeypatch.setattr(
                    session_update_service, "get_review_draft", paused_get
                )
                stale = asyncio.create_task(
                    session_update_service.decide_candidate(
                        first,
                        draft_id=race["id"],
                        candidate_id="entity-0",
                        decision="accepted",
                        expected_revision=race["revision"],
                    )
                )
                try:
                    await asyncio.wait_for(observed.wait(), timeout=5)
                    async with sessions() as second:
                        await session_update_service.decide_candidate(
                            second,
                            draft_id=race["id"],
                            candidate_id="entity-0",
                            decision="rejected",
                            reason="Not established",
                            expected_revision=race["revision"],
                        )
                finally:
                    resume.set()
                    with pytest.raises(SessionUpdateConflict):
                        await stale
                    monkeypatch.setattr(
                        session_update_service, "get_review_draft", original_get
                    )

            # A competing SQLite reservation produces a safe conflict, not a 500.
            busy_engine = create_async_engine(
                "sqlite+aiosqlite:///" + (tmp_path / "fictional.db").as_posix(),
                connect_args={"timeout": 0.05},
            )
            try:
                busy_sessions = async_sessionmaker(busy_engine, expire_on_commit=False)
                async with sessions() as reserved:
                    await reserved.execute(
                        update(SessionUpdateDraft)
                        .where(SessionUpdateDraft.id == race["id"])
                        .values(revision=SessionUpdateDraft.revision)
                    )
                    async with busy_sessions() as competing:
                        with pytest.raises(
                            SessionUpdateConflict, match="competing write"
                        ):
                            await session_update_service.decide_candidate(
                                competing,
                                draft_id=race["id"],
                                candidate_id="entity-0",
                                decision="accepted",
                            )
                    await reserved.rollback()
            finally:
                await busy_engine.dispose()
            async with sessions() as db:
                current = await session_update_service.get_review_draft(db, race["id"])
                assert current.decisions["entity-0"]["decision"] == "rejected"
                assert current.revision == race["revision"] + 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
