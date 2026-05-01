from __future__ import annotations

import logging
from enum import Enum
from typing import Any, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.document import Document
from backend.models.chunk import DocumentChunk
from backend.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class ChunkStrategy:
    """Utilities for chunking free-form text while keeping paragraph boundaries."""

    def __init__(self, max_chars: int = 1200, overlap: int = 200) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if overlap < 0:
            raise ValueError("overlap cannot be negative")
        self.max_chars = max_chars
        self.overlap = min(overlap, max_chars // 2)

    def _split_paragraphs(self, text: str) -> List[str]:
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paras if paras else [text.strip()]

    def chunk(self, text: Optional[str]) -> List[str]:
        if not text or not text.strip():
            return []
        chunks: List[str] = []
        paragraphs = self._split_paragraphs(text)
        current: List[str] = []
        current_len = 0
        for para in paragraphs:
            para_len = len(para)
            if para_len >= self.max_chars:
                # Hard split long paragraphs
                if current:
                    self._flush_chunk(" ".join(current), chunks)
                    current, current_len = [], 0
                for part in self._slice_long_paragraph(para):
                    self._flush_chunk(part, chunks)
                continue

            if current_len + para_len + 1 > self.max_chars and current:
                self._flush_chunk(" ".join(current), chunks)
                current, current_len = [], 0

            current.append(para)
            current_len += para_len + 1

        self._flush_chunk(" ".join(current), chunks)
        return chunks

    def _slice_long_paragraph(self, para: str) -> List[str]:
        slices: List[str] = []
        step = self.max_chars - self.overlap
        for start in range(0, len(para), step):
            end = min(len(para), start + self.max_chars)
            slices.append(para[start:end])
            if end == len(para):
                break
        return slices

    def _flush_chunk(self, text: str, chunks: List[str]) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        if chunks:
            # Add overlap from previous chunk
            overlap_text = chunks[-1][-self.overlap :]
            cleaned = f"{overlap_text} {cleaned}".strip()
        chunks.append(cleaned)


class IngestionService:
    """Ingests documents, chunks them, and persists both text and embeddings."""

    def __init__(self, chunk_strategy: Optional[ChunkStrategy] = None) -> None:
        self.chunk_strategy = chunk_strategy or ChunkStrategy()

    async def ingest_document(
        self,
        db: AsyncSession,
        *,
        title: str,
        kind: str,
        content: Optional[str],
        summary: Optional[str] = None,
        source_name: Optional[str] = None,
        url: Optional[str] = None,
        dedupe_on_url: bool = False,
        source_class: str = "private_local",
        privacy_scope: str = "private_local",
        review_status: str = "approved",
        visibility_scope: str = "gm_only",
        rag_eligible: bool = True,
        train_eligible: bool = False,
    ) -> Document:
        governance_fields = {
            "source_class": source_class,
            "privacy_scope": privacy_scope,
            "review_status": review_status,
            "visibility_scope": visibility_scope,
            "rag_eligible": rag_eligible,
            "train_eligible": train_eligible,
        }
        if dedupe_on_url and url:
            existing = await self._get_document_by_url(db, kind=kind, url=url)
            if existing is not None:
                content_changed = existing.content != content
                existing.title = title
                existing.kind = kind
                existing.content = content
                existing.summary = summary
                existing.source_name = source_name
                existing.url = url
                self._apply_governance_fields(existing, governance_fields)
                return await self.refresh_document(
                    db, existing, rechunk=content_changed
                )

        document = Document(
            title=title,
            kind=kind,
            content=content,
            summary=summary,
            source_name=source_name,
            url=url,
            **governance_fields,
        )
        db.add(document)
        await db.flush()

        chunks = self.chunk_strategy.chunk(content or "")
        await self._attach_chunks(document, chunks, db)
        await self._maybe_embed_document(document)
        await db.commit()
        await db.refresh(document)
        return document

    def _apply_governance_fields(
        self, document: Document, governance_fields: dict[str, Any]
    ) -> None:
        for field, value in governance_fields.items():
            if isinstance(value, Enum):
                value = value.value
            setattr(document, field, value)

    async def _get_document_by_url(
        self, db: AsyncSession, *, kind: str, url: str
    ) -> Optional[Document]:
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.kind == kind)
            .where(Document.url == url)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _attach_chunks(
        self, document: Document, chunks: Sequence[str], db: AsyncSession
    ) -> None:
        if not chunks:
            return
        embeddings = await self._maybe_embed_chunks(chunks)
        for idx, (text, embedding) in enumerate(zip(chunks, embeddings)):
            doc_chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                content=text,
                embedding=embedding,
            )
            doc_chunk.document = document
            db.add(doc_chunk)
        await db.flush()

    async def refresh_document(
        self, db: AsyncSession, document: Document, *, rechunk: bool = False
    ) -> Document:
        if rechunk:
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )
            await db.flush()
            chunks = self.chunk_strategy.chunk(document.content or "")
            await self._attach_chunks(document, chunks, db)

        await self._maybe_embed_document(document)
        await db.commit()
        await db.refresh(document)
        return document

    async def _maybe_embed_document(self, document: Document) -> None:
        text = embedding_service.create_document_text(document.__dict__)
        document.embedding = await embedding_service.generate_embedding(text)

    async def _maybe_embed_chunks(
        self, chunks: Sequence[str]
    ) -> List[Optional[List[float]]]:
        if not chunks:
            return []
        # Batch for efficiency
        batch_size = max(1, min(len(chunks), 50))
        embeddings: List[Optional[List[float]]] = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            embeddings.extend(await embedding_service.generate_embeddings_batch(batch))
        return embeddings


ingestion_service = IngestionService()
