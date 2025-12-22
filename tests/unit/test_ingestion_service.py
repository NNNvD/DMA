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
    assert chunks[1].startswith(chunks[0][-strategy.overlap:].strip())


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
            result = await session.execute(select(Document).options(selectinload(Document.chunks)))
            return result.scalars().first()

    try:
        stored = asyncio.run(_run())
        assert stored is not None
        assert len(stored.chunks) >= 2
        assert stored.chunks[0].content
        assert stored.chunks[0].document_id == stored.id
    finally:
        asyncio.run(engine.dispose())

