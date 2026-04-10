import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.base import Base
from backend.models.document import Document
from backend.services.ingestion_service import ChunkStrategy, IngestionService


def _create_in_memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    SessionLocal = asyncio.run(_init())
    return engine, SessionLocal


def test_chunk_strategy_respects_paragraphs_and_overlap():
    strategy = ChunkStrategy(max_chars=30, overlap=5)
    text = "Intro paragraph.\n\nSecond paragraph is a bit longer than the first."
    chunks = strategy.chunk(text)

    assert len(chunks) >= 2
    assert "Intro paragraph." in chunks[0]
    assert chunks[1].startswith(chunks[0][-strategy.overlap :].strip())


def test_ingest_document_creates_chunks_and_persists():
    engine, SessionLocal = _create_in_memory_db()
    service = IngestionService(chunk_strategy=ChunkStrategy(max_chars=40, overlap=8))

    async def _run():
        async with SessionLocal() as session:
            await service.ingest_document(
                session,
                title="Test Rules",
                kind="rule",
                content="Paragraph one explains rules.\n\nParagraph two continues with more details.",
                summary="Two paragraphs",
                source_name="Core",
            )
            result = await session.execute(
                select(Document).options(selectinload(Document.chunks))
            )
            return result.scalars().first()

    try:
        stored = asyncio.run(_run())
        assert stored is not None
        assert len(stored.chunks) >= 2
        assert stored.chunks[0].content
        assert stored.chunks[0].document_id == stored.id
    finally:
        asyncio.run(engine.dispose())


def test_ingest_document_can_refresh_existing_document_by_url():
    engine, SessionLocal = _create_in_memory_db()
    service = IngestionService(chunk_strategy=ChunkStrategy(max_chars=40, overlap=8))

    async def _run():
        async with SessionLocal() as session:
            first = await service.ingest_document(
                session,
                title="Session 12",
                kind="session_log",
                content="Old content",
                summary="First pass",
                source_name="session-logs/session-12.md",
                url="/tmp/session-12.md",
                dedupe_on_url=True,
            )
            second = await service.ingest_document(
                session,
                title="Session 12 Harbor Fire",
                kind="session_log",
                content="Updated content\n\nWith another paragraph.",
                summary="Refreshed",
                source_name="session-logs/session-12.md",
                url="/tmp/session-12.md",
                dedupe_on_url=True,
            )
            result = await session.execute(
                select(Document).options(selectinload(Document.chunks))
            )
            documents = list(result.scalars().all())
            return first, second, documents

    try:
        first, second, documents = asyncio.run(_run())
        assert first.id == second.id
        assert len(documents) == 1
        assert documents[0].title == "Session 12 Harbor Fire"
        assert documents[0].summary == "Refreshed"
        assert len(documents[0].chunks) >= 1
    finally:
        asyncio.run(engine.dispose())
