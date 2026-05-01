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
        self.stopwords = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "bonus",
            "by",
            "do",
            "does",
            "for",
            "from",
            "get",
            "give",
            "gives",
            "grant",
            "grants",
            "how",
            "i",
            "if",
            "in",
            "is",
            "it",
            "me",
            "my",
            "of",
            "on",
            "or",
            "our",
            "tell",
            "the",
            "to",
            "we",
            "what",
            "when",
            "who",
            "why",
            "with",
            "you",
            "your",
        }

    def _expand_query(self, query: str) -> List[str]:
        q = query.lower()
        tokens = ["".join(ch for ch in token if ch.isalnum()) for token in q.split()]
        meaningful_tokens = [
            token for token in tokens if len(token) >= 3 and token not in self.stopwords
        ]
        expansions = [q]
        expansions.extend(meaningful_tokens)
        expansions.extend(self._morphological_variants(meaningful_tokens))
        synonyms = {
            "npc": ["character", "villager", "ally"],
            "rule": ["mechanic", "guideline"],
            "lore": ["world", "story", "setting"],
            "combat": ["battle", "fight"],
            "invisibility": ["invisible", "unseen"],
        }
        for k, vals in synonyms.items():
            if k in q:
                expansions.extend(vals)
        return list(dict.fromkeys(expansions))

    def _morphological_variants(self, tokens: List[str]) -> List[str]:
        variants: List[str] = []
        for token in tokens:
            if len(token) <= 4:
                continue
            if token.endswith("s"):
                variants.append(token[:-1])
            if token.endswith("ing"):
                variants.append(token[:-3])
            if token.endswith("ed"):
                variants.append(token[:-2])
            if token.endswith("ility"):
                variants.append(token[:-5] + "le")
        return [variant for variant in variants if len(variant) >= 3]

    def _keyword_score(self, text: str, terms: List[str]) -> float:
        if not text:
            return 0.0
        text_l = text.lower()
        hits = sum(1 for t in terms if t in text_l)
        return hits / max(1, len(terms))

    async def search_documents(
        self,
        query: str,
        db: AsyncSession,
        top_k: int = 5,
        kind: Optional[str] = None,
        source_class: Optional[str] = None,
        privacy_scope: Optional[str] = None,
        review_status: Optional[str] = None,
        visibility_scope: Optional[str] = None,
        rag_eligible: Optional[bool] = None,
        train_eligible: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        ranked = await self._rank_documents(
            query,
            db,
            top_k=top_k,
            kind=kind,
            include_chunks=0,
            source_class=source_class,
            privacy_scope=privacy_scope,
            review_status=review_status,
            visibility_scope=visibility_scope,
            rag_eligible=rag_eligible,
            train_eligible=train_eligible,
        )
        return [
            {
                "score": item["score"],
                "document": item["document"],
            }
            for item in ranked
        ]

    async def search_documents_detailed(
        self,
        query: str,
        db: AsyncSession,
        *,
        top_k: int = 5,
        kind: Optional[str] = None,
        include_chunks: int = 2,
        source_class: Optional[str] = None,
        privacy_scope: Optional[str] = None,
        review_status: Optional[str] = None,
        visibility_scope: Optional[str] = None,
        rag_eligible: Optional[bool] = None,
        train_eligible: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        return await self._rank_documents(
            query,
            db,
            top_k=top_k,
            kind=kind,
            include_chunks=include_chunks,
            source_class=source_class,
            privacy_scope=privacy_scope,
            review_status=review_status,
            visibility_scope=visibility_scope,
            rag_eligible=rag_eligible,
            train_eligible=train_eligible,
        )

    async def _rank_documents(
        self,
        query: str,
        db: AsyncSession,
        *,
        top_k: int,
        kind: Optional[str],
        include_chunks: int,
        source_class: Optional[str],
        privacy_scope: Optional[str],
        review_status: Optional[str],
        visibility_scope: Optional[str],
        rag_eligible: Optional[bool],
        train_eligible: Optional[bool],
    ) -> List[Dict[str, Any]]:
        terms = self._expand_query(query)

        # Prefer docs with embeddings; fetch a candidate pool
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(desc(Document.updated_at))
            .limit(500)
        )
        if kind:
            stmt = stmt.where(Document.kind == kind)
        if source_class:
            stmt = stmt.where(Document.source_class == source_class)
        if privacy_scope:
            stmt = stmt.where(Document.privacy_scope == privacy_scope)
        if review_status:
            stmt = stmt.where(Document.review_status == review_status)
        if visibility_scope:
            stmt = stmt.where(Document.visibility_scope == visibility_scope)
        if rag_eligible is not None:
            stmt = stmt.where(Document.rag_eligible == rag_eligible)
        if train_eligible is not None:
            stmt = stmt.where(Document.train_eligible == train_eligible)

        result = await db.execute(stmt)
        docs = result.scalars().all()

        # Compute query embedding when available
        q_emb: Optional[List[float]] = await embedding_service.generate_embedding(query)

        scored: List[Tuple[float, Document, List[Dict[str, Any]]]] = []
        for d in docs:
            kscore = self._keyword_score(
                (d.title or "") + "\n" + (d.summary or "") + "\n" + (d.content or ""),
                terms,
            )
            escore = self._embedding_score(q_emb, d.embedding)
            cscore, top_chunks = self._score_chunks(
                q_emb, terms, d.chunks or [], include_chunks
            )
            score = (
                self.weight_embedding * max(escore, cscore)
                + self.weight_keyword * kscore
            )
            if score > 0:
                scored.append((score, d, top_chunks))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]
        return [
            {
                "score": s,
                "document": {
                    "id": d.id,
                    "title": d.title,
                    "kind": d.kind,
                    "summary": d.summary,
                    "source_name": d.source_name,
                    "url": d.url,
                    "source_class": d.source_class,
                    "privacy_scope": d.privacy_scope,
                    "review_status": d.review_status,
                    "visibility_scope": d.visibility_scope,
                    "rag_eligible": d.rag_eligible,
                    "train_eligible": d.train_eligible,
                },
                "chunks": chunks,
            }
            for s, d, chunks in top
        ]

    def _embedding_score(
        self, query_emb: Optional[List[float]], candidate_emb: Optional[List[float]]
    ) -> float:
        if not query_emb or not candidate_emb or not isinstance(candidate_emb, list):
            return 0.0
        try:
            return embedding_service.compute_similarity(query_emb, candidate_emb)
        except Exception:
            return 0.0

    def _score_chunks(
        self,
        query_emb: Optional[List[float]],
        terms: List[str],
        chunks: List[DocumentChunk],
        include_chunks: int,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        if not chunks:
            return 0.0, []
        scored_chunks: List[Tuple[float, DocumentChunk]] = []
        for chunk in chunks:
            kscore = self._keyword_score(chunk.content, terms)
            escore = self._embedding_score(query_emb, chunk.embedding)
            score = 0.6 * escore + 0.4 * kscore
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        best = scored_chunks[0][0]
        top_chunks = [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "score": score,
            }
            for score, chunk in scored_chunks[:include_chunks]
        ]
        return best, top_chunks


retrieval_service = RetrievalService()
