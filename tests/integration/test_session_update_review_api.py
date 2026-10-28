import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.support.app_factory import create_documents_test_app
from backend.models.campaign import CampaignEntityProvenance
from backend.services.session_update_service import session_update_service


def _create_entity(client: TestClient, **payload):
    response = client.post("/api/campaign/entities", json=payload)
    assert response.status_code == 200
    return response.json()


def test_preview_stages_candidates_without_changing_campaign_or_prep():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)
    content = """Summary: The guild arrived

## Location: Greyhaven
Summary: A quiet harbor town

## Changelog
- The guild opened a new office.
"""

    try:
        response = client.post(
            "/api/campaign/session-update-drafts",
            json={"title": "Session 1", "content": content},
        )
        assert response.status_code == 201
        draft = response.json()
        assert draft["campaign_id"] == "abomination-vaults"
        assert draft["status"] == "pending"
        assert (
            client.get(f"/api/campaign/session-update-drafts/{draft['id']}").json()[
                "content"
            ]
            == content
        )
        assert {item["candidate_type"] for item in draft["candidates"]} == {
            "entity",
            "session_event",
        }
        assert (
            client.get(
                "/api/campaign/entities", params={"entity_type": "location"}
            ).json()["total"]
            == 0
        )
        assert client.get("/api/campaign/session-history").json()["total"] == 0
        pending = client.get(
            "/api/campaign/session-update-drafts", params={"status": "pending"}
        )
        assert pending.status_code == 200
        assert [item["id"] for item in pending.json()] == [draft["id"]]
        prep = client.post(
            "/api/prep/session-brief",
            json={"title": "Preview check", "store_document": False},
        )
        assert prep.status_code == 200
        assert prep.json()["recent_sessions"] == []
    finally:
        asyncio.run(engine.dispose())


def test_rejected_candidate_and_log_do_not_promote_or_enter_prep_history():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        draft_response = client.post(
            "/api/campaign/session-update-drafts",
            json={
                "title": "Rejected session",
                "content": (
                    "## Location: Greyhaven\nSummary: Unverified place\n\n"
                    "## Location: Blackstone\nSummary: Unreviewed place\n"
                ),
            },
        )
        assert draft_response.status_code == 201
        draft = draft_response.json()
        candidates = [
            item for item in draft["candidates"] if item["candidate_type"] == "entity"
        ]

        decision = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/candidates/{candidates[0]['id']}/decision",
            json={"decision": "rejected", "reason": "Not established in play"},
        )
        assert decision.status_code == 200
        deferred = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/candidates/{candidates[1]['id']}/decision",
            json={"decision": "deferred"},
        )
        assert deferred.status_code == 200
        finalized = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/finalize",
            json={"decision": "rejected", "reason": "Unverified source"},
        )
        assert finalized.status_code == 200
        assert (
            client.get(
                "/api/campaign/entities", params={"entity_type": "location"}
            ).json()["total"]
            == 0
        )
        assert client.get("/api/campaign/session-history").json()["total"] == 0
    finally:
        asyncio.run(engine.dispose())


def test_acceptance_is_intent_until_atomic_promote_and_approved_log_enters_history():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        draft_response = client.post(
            "/api/campaign/session-update-drafts",
            json={
                "title": "Reviewed session",
                "content": "## Location: Greyhaven\nSummary: Confirmed harbor town\n",
            },
        )
        assert draft_response.status_code == 201
        draft = draft_response.json()
        candidate = next(
            item for item in draft["candidates"] if item["candidate_type"] == "entity"
        )

        accepted = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/candidates/{candidate['id']}/decision",
            json={"decision": "accepted"},
        )
        assert accepted.status_code == 200
        assert accepted.json()["decision"]["decision"] == "accepted"
        assert accepted.json()["decision"]["reviewed_at"]
        assert accepted.json()["promotion"] is None
        assert client.get("/api/campaign/session-history").json()["total"] == 0
        assert (
            client.get(
                "/api/campaign/entities", params={"entity_type": "location"}
            ).json()["total"]
            == 0
        )

        promoted = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/promote"
        )
        assert promoted.status_code == 200
        assert (
            "promotion" in promoted.json()["decisions"][candidate["id"]]
        ), promoted.json()
        provenance_id = promoted.json()["decisions"][candidate["id"]]["provenance_id"]
        entity = client.get(
            "/api/campaign/entities", params={"entity_type": "location"}
        ).json()["items"][0]
        provenance = client.get(f"/api/campaign/entities/{entity['id']}/provenance")
        assert provenance.status_code == 200
        assert provenance.json()[0]["id"] == provenance_id
        assert provenance.json()[0]["draft_id"] == draft["id"]
        assert provenance.json()[0]["source_hash"] == draft["source_hash"]
        retried = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/promote"
        )
        assert retried.status_code == 200
        assert (
            len(client.get(f"/api/campaign/entities/{entity['id']}/provenance").json())
            == 1
        )

        finalized = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/finalize",
            json={"decision": "approved"},
        )
        assert finalized.status_code == 200
        assert finalized.json()["session_log_decision"] == "approved"
        assert finalized.json()["session_log_document_id"] is not None
        retry_after_finalize = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/promote"
        )
        assert retry_after_finalize.status_code == 200
        assert (
            retry_after_finalize.json()["decisions"][candidate["id"]]["promotion"]
            == promoted.json()["decisions"][candidate["id"]]["promotion"]
        )
        history = client.get("/api/campaign/session-history").json()
        assert history["total"] == 1
        assert history["items"][0]["title"] == "Reviewed session"
        prep = client.post(
            "/api/prep/session-brief",
            json={"title": "Accepted session prep", "store_document": False},
        )
        assert prep.status_code == 200
        assert prep.json()["recent_sessions"][0]["title"] == "Reviewed session"
    finally:
        asyncio.run(engine.dispose())


def test_pending_and_rejected_session_logs_are_excluded_from_history():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        for title, decision in [("Pending log", None), ("Rejected log", "rejected")]:
            draft = client.post(
                "/api/campaign/session-update-drafts",
                json={"title": title, "content": "No extracted facts."},
            ).json()
            if decision:
                result = client.post(
                    f"/api/campaign/session-update-drafts/{draft['id']}/finalize",
                    json={"decision": decision, "reason": "Not for prep"},
                )
                assert result.status_code == 200

        assert client.get("/api/campaign/session-history").json()["total"] == 0
    finally:
        asyncio.run(engine.dispose())


def test_candidate_promotion_conflicts_if_target_changed_since_preview():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        location = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven",
            summary="The DM's current description",
        )
        draft = client.post(
            "/api/campaign/session-update-drafts",
            json={
                "title": "Session update",
                "content": "## Location: Greyhaven\nSummary: Stale description\n",
            },
        ).json()
        candidate = draft["candidates"][0]
        changed = client.patch(
            f"/api/campaign/entities/{location['id']}",
            json={"summary": "The DM changed this after preview"},
        )
        assert changed.status_code == 200

        accepted = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/candidates/{candidate['id']}/decision",
            json={"decision": "accepted"},
        )
        assert accepted.status_code == 200
        promotion = client.post(
            f"/api/campaign/session-update-drafts/{draft['id']}/promote"
        )
        assert promotion.status_code == 409
        current = client.get(f"/api/campaign/entities/{location['id']}").json()
        assert current["summary"] == "The DM changed this after preview"
        refreshed_draft = client.get(
            f"/api/campaign/session-update-drafts/{draft['id']}"
        ).json()
        assert refreshed_draft["decisions"][candidate["id"]]["decision"] == "accepted"
    finally:
        asyncio.run(engine.dispose())


def test_atomic_promotion_rolls_back_prior_candidates_after_failure(monkeypatch):
    app, engine, session_local = create_documents_test_app()
    client = TestClient(app)
    original = session_update_service._promote_candidate

    async def fail_on_second(db, draft, candidate, *, commit=True):
        if candidate["id"] == "entity-1":
            raise RuntimeError("fixture failure after first promotion")
        return await original(db, draft, candidate, commit=commit)

    monkeypatch.setattr(session_update_service, "_promote_candidate", fail_on_second)
    try:
        draft = client.post(
            "/api/campaign/session-update-drafts",
            json={
                "title": "Atomic batch",
                "content": (
                    "## Location: Greyhaven\nSummary: Harbor town\n\n"
                    "## Location: Blackstone\nSummary: Mountain town\n"
                ),
            },
        ).json()
        for candidate in draft["candidates"]:
            response = client.post(
                f"/api/campaign/session-update-drafts/{draft['id']}/candidates/{candidate['id']}/decision",
                json={"decision": "accepted"},
            )
            assert response.status_code == 200
        with pytest.raises(RuntimeError, match="fixture failure"):
            client.post(f"/api/campaign/session-update-drafts/{draft['id']}/promote")
        assert (
            client.get(
                "/api/campaign/entities", params={"entity_type": "location"}
            ).json()["total"]
            == 0
        )
        assert (
            client.get(f"/api/campaign/session-update-drafts/{draft['id']}")
            .json()["decisions"]["entity-0"]
            .get("provenance_id")
            is None
        )

        async def provenance_count():
            async with session_local() as session:
                result = await session.execute(select(CampaignEntityProvenance.id))
                return len(result.scalars().all())

        assert asyncio.run(provenance_count()) == 0
    finally:
        asyncio.run(engine.dispose())
