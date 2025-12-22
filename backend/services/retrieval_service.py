from typing import List, Dict, Any, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc

from backend.models.document import Document
from backend.models.chunk import DocumentChunk
from backend.services.embedding_service import embedding_service


class RetrievalService:
    def __init__(self) -> None:
        # Tunable weights
        self.weight_embedding = 0.7
        self.weight_keyword = 0.3

    def _expand_query(self, query: str) -> List[str]:
        q = query.lower()
        expansions = [q]
        synonyms = {
            "npc": ["character", "villager", "ally"],
            "rule": ["mechanic", "guideline"],
            "lore": ["world", "story", "setting"],
            "combat": ["battle", "fight"],
        }
        for k, vals in synonyms.items():
            if k in q:
                expansions.extend(vals)
        return list(dict.fromkeys(expansions))

    def _keyword_score(self, text: str, terms: List[str]) -> float:
        if not text:
            return 0.0
        text_l = text.lower()
        hits = sum(1 for t in terms if t in text_l)
        return hits / max(1, len(terms))

    async def search_documents(
        self, query: str, db: AsyncSession, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        terms = self._expand_query(query)

        # Prefer docs with embeddings; fetch a candidate pool
        result = await db.execute(
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(desc(Document.updated_at))
            .limit(500)
        )
        docs = result.scalars().all()

        # Compute query embedding when available
        q_emb: Optional[List[float]] = await embedding_service.generate_embedding(query)

        scored: List[Tuple[float, Document]] = []
        for d in docs:
            kscore = self._keyword_score(
                (d.title or "") + "\n" + (d.summary or "") + "\n" + (d.content or ""),
                terms,
            )
            escore = self._embedding_score(q_emb, d.embedding)
            cscore = self._best_chunk_score(q_emb, terms, d.chunks or [])
            score = self.weight_embedding * max(escore, cscore) + self.weight_keyword * kscore
            if score > 0:
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        return [
            {"score": s, "document": {"id": d.id, "title": d.title, "kind": d.kind, "summary": d.summary}}
            for s, d in top
        ]

    def _embedding_score(self, query_emb: Optional[List[float]], candidate_emb: Optional[List[float]]) -> float:
        if not query_emb or not candidate_emb or not isinstance(candidate_emb, list):
            return 0.0
        try:
            return embedding_service.compute_similarity(query_emb, candidate_emb)
        except Exception:
            return 0.0

    def _best_chunk_score(
        self, query_emb: Optional[List[float]], terms: List[str], chunks: List[DocumentChunk]
    ) -> float:
        if not chunks:
            return 0.0
        best = 0.0
        for chunk in chunks:
            kscore = self._keyword_score(chunk.content, terms)
            escore = self._embedding_score(query_emb, chunk.embedding)
            best = max(best, 0.6 * escore + 0.4 * kscore)
        return best


retrieval_service = RetrievalService()
