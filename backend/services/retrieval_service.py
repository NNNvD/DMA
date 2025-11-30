from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.models.document import Document
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

    async def search_documents(self, query: str, db: AsyncSession, top_k: int = 5) -> List[Dict[str, Any]]:
        terms = self._expand_query(query)

        # Prefer docs with embeddings; fetch a candidate pool
        result = await db.execute(
            select(Document).order_by(desc(Document.updated_at)).limit(500)
        )
        docs = result.scalars().all()

        # Compute query embedding when available
        q_emb: Optional[List[float]] = await embedding_service.generate_embedding(query)

        scored: List[Tuple[float, Document]] = []
        for d in docs:
            kscore = self._keyword_score((d.title or "") + "\n" + (d.summary or "") + "\n" + (d.content or ""), terms)
            escore = 0.0
            if q_emb and isinstance(d.embedding, list) and d.embedding:
                try:
                    escore = embedding_service.compute_similarity(q_emb, d.embedding)
                except Exception:
                    escore = 0.0
            score = self.weight_embedding * escore + self.weight_keyword * kscore
            if score > 0:
                scored.append((score, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        return [
            {"score": s, "document": {"id": d.id, "title": d.title, "kind": d.kind, "summary": d.summary}}
            for s, d in top
        ]


retrieval_service = RetrievalService()

