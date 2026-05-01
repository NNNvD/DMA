import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.base import Base
from backend.models.document import Document
from backend.models.chunk import DocumentChunk
from backend.services.retrieval_service import retrieval_service


def _create_in_memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    SessionLocal = asyncio.run(_init())
    return engine, SessionLocal


def test_retrieval_prefers_chunk_hits_when_embeddings_disabled():
    engine, SessionLocal = _create_in_memory_db()
    doc_id = None

    async def _seed():
        nonlocal doc_id
        async with SessionLocal() as session:
            doc = Document(
                title="Rules Compendium", kind="rule", content="General rules overview"
            )
            session.add(doc)
            await session.flush()
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=0,
                content="Fireball spell explodes in a 20-foot radius and deals fire damage.",
            )
            chunk.document = doc
            session.add(chunk)
            await session.commit()
            doc_id = doc.id

    async def _run_search():
        async with SessionLocal() as session:
            results = await retrieval_service.search_documents(
                "fireball", session, top_k=1
            )
            return results

    try:
        asyncio.run(_seed())
        results = asyncio.run(_run_search())
        assert results, "Expected at least one retrieval result"
        assert results[0]["document"]["id"] == doc_id
    finally:
        asyncio.run(engine.dispose())
