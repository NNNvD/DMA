from typing import List, Optional, Dict, Any
import logging
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.provider = settings.embedding_provider
        self.openai_client = None
        self.sentence_transformer = None
        self.model = settings.embedding_model

        if self.provider == "openai":
            if not settings.openai_api_key:
                logger.warning("OPENAI_API_KEY not set; disabling embeddings")
                self.provider = "disabled"
            else:
                from openai import OpenAI

                self.openai_client = OpenAI(api_key=settings.openai_api_key)

        if self.provider == "local":
            try:
                from sentence_transformers import SentenceTransformer

                self.sentence_transformer = SentenceTransformer(settings.local_embedding_model)
                logger.info(f"Loaded local embedding model: {settings.local_embedding_model}")
            except ImportError:
                logger.error("sentence-transformers not installed. pip install sentence-transformers")
                raise

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        try:
            if self.provider == "openai":
                resp = self.openai_client.embeddings.create(input=text, model=self.model)
                return resp.data[0].embedding
            if self.provider == "local":
                emb = self.sentence_transformer.encode(text, convert_to_numpy=True)
                return emb.tolist()
            return None
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        if not texts:
            return []
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return [None] * len(texts)
        try:
            if self.provider == "openai":
                resp = self.openai_client.embeddings.create(input=valid_texts, model=self.model)
                embs = [d.embedding for d in resp.data]
                out, idx = [], 0
                for t in texts:
                    if t and t.strip():
                        out.append(embs[idx]); idx += 1
                    else:
                        out.append(None)
                return out
            if self.provider == "local":
                embs = self.sentence_transformer.encode(valid_texts, convert_to_numpy=True)
                out, idx = [], 0
                for t in texts:
                    if t and t.strip():
                        out.append(embs[idx].tolist()); idx += 1
                    else:
                        out.append(None)
                return out
            return [None] * len(texts)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return [None] * len(texts)

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        if not embedding1 or not embedding2:
            return 0.0
        import numpy as np
        v1, v2 = np.array(embedding1), np.array(embedding2)
        dot = float(np.dot(v1, v2))
        n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def create_document_text(self, doc: Dict[str, Any]) -> str:
        parts: List[str] = []
        if doc.get("title"):
            parts.append(f"Title: {doc['title']}")
        if doc.get("summary"):
            parts.append(f"Summary: {doc['summary']}")
        if doc.get("content"):
            parts.append(f"Content: {doc['content'][:1000]}")
        if doc.get("kind"):
            parts.append(f"Kind: {doc['kind']}")
        if doc.get("source_name"):
            parts.append(f"Source: {doc['source_name']}")
        return "\n".join(parts)


# Singleton
embedding_service = EmbeddingService()

