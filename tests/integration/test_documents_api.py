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
