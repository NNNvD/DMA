#!/usr/bin/env python3
"""
Generate embeddings for DMA documents missing vectors.
Adapted from ainewslive pattern; targets backend.models.document.Document.
"""

import asyncio
import os
import sys
import json
import logging
from typing import List

# Ensure project root on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import select, and_, text
from backend.models.base import async_session_maker
from backend.models.document import Document
from backend.services.embedding_service import embedding_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_embeddings")


async def generate_missing_embeddings(batch_size: int = 20, max_docs: int = 500):
    async with async_session_maker() as db:
        # Count
        result = await db.execute(text("SELECT COUNT(*) FROM documents WHERE embedding IS NULL"))
        total_missing = result.scalar() or 0
        logger.info("Documents missing embeddings: %s", total_missing)
        if total_missing == 0:
            return

        limit = min(max_docs, total_missing)
        processed = 0
        batch = 1
        while processed < limit:
            current = min(batch_size, limit - processed)
            result = await db.execute(
                select(Document)
                .where(Document.embedding.is_(None))
                .order_by(Document.updated_at.desc())
                .limit(current)
            )
            docs: List[Document] = result.scalars().all()
            if not docs:
                break

            texts = []
            for d in docs:
                parts: List[str] = []
                if d.title:
                    parts.append(f"Title: {d.title}")
                if d.summary:
                    parts.append(f"Summary: {d.summary}")
                if d.content:
                    parts.append(f"Content: {d.content[:1000]}")
                if d.kind:
                    parts.append(f"Kind: {d.kind}")
                if d.source_name:
                    parts.append(f"Source: {d.source_name}")
                texts.append("\n".join(parts))

            try:
                embeddings = await embedding_service.generate_embeddings_batch(texts)
                updated = 0
                for doc, emb in zip(docs, embeddings):
                    if emb:
                        doc.embedding = emb if isinstance(emb, list) else json.loads(json.dumps(emb))
                        updated += 1
                await db.commit()
                processed += len(docs)
                logger.info(
                    "Batch %s: updated %s/%s docs (progress %s/%s)",
                    batch,
                    updated,
                    len(docs),
                    processed,
                    limit,
                )
            except Exception as e:
                logger.error("Batch %s failed: %s", batch, e)
                await db.rollback()
                break
            batch += 1
            await asyncio.sleep(0.5)


async def main():
    if embedding_service.provider == "disabled":
        logger.warning("Embeddings provider is disabled. Configure .env to enable.")
    await generate_missing_embeddings()


if __name__ == "__main__":
    asyncio.run(main())

