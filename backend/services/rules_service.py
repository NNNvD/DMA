from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.retrieval_service import retrieval_service


class RulesService:
    """Retrieval-backed rules answers with citations and strict mode handling."""

    def __init__(self, confidence_threshold: float = 0.08) -> None:
        self.confidence_threshold = confidence_threshold

    async def answer_question(
        self,
        query: str,
        db: AsyncSession,
        *,
        top_k: int = 3,
        strict: bool = False,
    ) -> Dict[str, Any]:
        matches = await retrieval_service.search_documents_detailed(
            query,
            db,
            top_k=top_k,
            kind="rule",
            include_chunks=2,
        )

        citations = self._build_citations(matches)
        confident = (
            bool(matches)
            and matches[0]["score"] >= self.confidence_threshold
            and bool(citations)
        )

        if strict and not confident:
            return {
                "answer": (
                    "I couldn't find a confident answer in the ingested rules. "
                    "Try a narrower query or verify the rule manually."
                ),
                "strict_mode": True,
                "confidence": matches[0]["score"] if matches else 0.0,
                "citations": citations,
            }

        if not citations:
            return {
                "answer": "I couldn't find supporting rule text for that query yet.",
                "strict_mode": strict,
                "confidence": matches[0]["score"] if matches else 0.0,
                "citations": [],
            }

        answer = self._compose_answer(
            query, citations, strict=strict, confident=confident
        )
        return {
            "answer": answer,
            "strict_mode": strict,
            "confidence": matches[0]["score"] if matches else 0.0,
            "citations": citations,
        }

    def _build_citations(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        citations: List[Dict[str, Any]] = []
        for match in matches:
            document = match["document"]
            for chunk in match.get("chunks", []):
                citations.append(
                    {
                        "document_id": document["id"],
                        "title": document["title"],
                        "source_name": document.get("source_name"),
                        "url": document.get("url"),
                        "chunk_index": chunk["chunk_index"],
                        "score": chunk["score"],
                        "excerpt": self._excerpt(chunk["content"]),
                    }
                )
        citations.sort(key=lambda item: item["score"], reverse=True)
        return citations[:5]

    def _compose_answer(
        self,
        query: str,
        citations: List[Dict[str, Any]],
        *,
        strict: bool,
        confident: bool,
    ) -> str:
        excerpts = [
            citation["excerpt"] for citation in citations[:2] if citation["excerpt"]
        ]
        combined = " ".join(excerpts).strip()

        if strict and confident:
            return f"Based on the retrieved rules text for '{query}', the strongest support says: {combined}"

        if confident:
            return f"The best matching rules text suggests: {combined}"

        return (
            "I found partially relevant rules text, but the match is weak. "
            f"The closest support says: {combined}"
        )

    def _excerpt(self, text: str, max_chars: int = 500) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 3].rstrip() + "..."


rules_service = RulesService()
