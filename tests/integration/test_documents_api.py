import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.document import Document
from tests.support.app_factory import create_documents_test_app


def test_create_document_uses_ingestion_pipeline():
    app, engine, session_local = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/documents",
            json={
                "title": "Basic Rules",
                "kind": "rule",
                "summary": "Spellcasting guidance",
                "content": (
                    ("A short paragraph about spell preparation. " * 30)
                    + "\n\n"
                    + ("A second paragraph with more rules text and examples. " * 30)
                ),
            },
        )

        assert response.status_code == 200

        async def _load_document():
            async with session_local() as session:
                result = await session.execute(
                    select(Document).options(selectinload(Document.chunks))
                )
                return result.scalar_one()

        stored = asyncio.run(_load_document())
        assert stored.title == "Basic Rules"
        assert len(stored.chunks) >= 2
        assert stored.chunks[0].content
        assert stored.source_class == "private_local"
        assert stored.visibility_scope == "gm_only"
        assert stored.rag_eligible is True
    finally:
        asyncio.run(engine.dispose())


def test_rules_query_returns_citations_and_strict_mode_fallback():
    app, engine, session_local = create_documents_test_app()
    client = TestClient(app)

    try:
        client.post(
            "/api/documents",
            json={
                "title": "Spell Rules",
                "kind": "rule",
                "content": (
                    "Fireball explodes in a 20-foot-radius sphere. "
                    "Creatures in the area take fire damage on a failed save."
                ),
            },
        )

        positive = client.post(
            "/api/documents/rules/query",
            json={"query": "What does fireball do?", "strict": True},
        )
        assert positive.status_code == 200
        payload = positive.json()
        assert payload["citations"]
        assert "fireball" in payload["answer"].lower()

        strict_miss = client.post(
            "/api/documents/rules/query",
            json={"query": "How does underwater basket weaving work?", "strict": True},
        )
        assert strict_miss.status_code == 200
        miss_payload = strict_miss.json()
        assert "couldn't find a confident answer" in miss_payload["answer"].lower()
    finally:
        asyncio.run(engine.dispose())


def test_document_filters_support_governance_metadata():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        guide = client.post(
            "/api/documents",
            json={
                "title": "Public Spell Guide",
                "kind": "guide",
                "content": "Fireball is excellent area damage against clustered foes.",
                "source_class": "trainable_with_review",
                "privacy_scope": "public",
                "review_status": "pending",
                "visibility_scope": "player_safe",
                "rag_eligible": True,
                "train_eligible": False,
            },
        )
        assert guide.status_code == 200
        guide_payload = guide.json()
        assert guide_payload["source_class"] == "trainable_with_review"
        assert guide_payload["visibility_scope"] == "player_safe"

        gm_note = client.post(
            "/api/documents",
            json={
                "title": "Secret Encounter Plan",
                "kind": "campaign_note",
                "content": "Hidden cultists ambush the party after the bridge scene.",
                "source_class": "trainable_open",
                "privacy_scope": "private_local",
                "review_status": "approved",
                "visibility_scope": "gm_only",
                "rag_eligible": True,
                "train_eligible": False,
            },
        )
        assert gm_note.status_code == 200

        list_response = client.get(
            "/api/documents",
            params={
                "visibility_scope": "player_safe",
                "source_class": "trainable_with_review",
            },
        )
        assert list_response.status_code == 200
        list_payload = list_response.json()
        assert list_payload["total"] == 1
        assert list_payload["items"][0]["title"] == "Public Spell Guide"

        search_response = client.get(
            "/api/documents/search",
            params={
                "q": "fireball",
                "kind": "guide",
                "visibility_scope": "player_safe",
                "review_status": "pending",
                "source_class": "trainable_with_review",
                "rag_eligible": True,
            },
        )
        assert search_response.status_code == 200
        search_payload = search_response.json()
        assert len(search_payload["results"]) == 1
        assert search_payload["results"][0]["document"]["title"] == "Public Spell Guide"
        assert (
            search_payload["results"][0]["document"]["visibility_scope"]
            == "player_safe"
        )
    finally:
        asyncio.run(engine.dispose())
