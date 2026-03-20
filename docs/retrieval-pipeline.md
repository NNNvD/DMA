# Retrieval Pipeline

This repository uses a lightweight hybrid retrieval approach suitable for DMA:

- Query expansion: heuristic synonyms for common campaign terms (e.g., npc→character, lore→world).
- Candidate pool: recent documents from `documents` table (limit 500).
- Dual scoring:
  - Embedding similarity (cosine) when vectors exist.
  - Keyword score over title/summary/content for expanded terms.
- Reranking: weighted blend (default 0.7 embedding, 0.3 keyword) with top-k returned.

Endpoints and services:
- Service: `backend/services/retrieval_service.py` (`search_documents`)
- Rules Q&A: `backend/services/rules_service.py`
- Embeddings: `backend/services/embedding_service.py` (OpenAI or local)
- Data model: `backend/models/document.py`
- API:
  - `POST /api/documents` ingests documents and stores chunks
  - `GET /api/documents/search` returns ranked retrieval results
  - `POST /api/documents/rules/query` returns a retrieval-backed answer with citations

Next steps:
- Replace heuristic expansion with LLM-backed query rewriting when keys are available.
- Add reranking cross-encoder model (e.g., BGE reranker) for improved ordering.
- Introduce metadata filters (kind/source) and time decay for session queries.
