import math
import logging
from time import perf_counter
from typing import Any, Dict, List, Optional, Sequence

from backend.config.settings import settings
from backend.services.metrics_service import metrics_service

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.provider = settings.embedding_provider
        self.openai_client: Any = None
        self.sentence_transformer: Any = None
        self.model = settings.embedding_model

        if self.provider == "openai":
            if not settings.openai_api_key:
                logger.warning("OPENAI_API_KEY not set; disabling embeddings")
                self.provider = "disabled"
            else:
                from openai import OpenAI

                self.openai_client = OpenAI(api_key=settings.openai_api_key)

        if self.provider == "local":
            self.model = settings.local_embedding_model
            try:
                from sentence_transformers import SentenceTransformer

                self.sentence_transformer = SentenceTransformer(
                    settings.local_embedding_model
                )
                logger.info(
                    f"Loaded local embedding model: {settings.local_embedding_model}"
                )
            except ImportError:
                logger.error(
                    "sentence-transformers not installed. Install optional deps with "
                    "`pip install -r backend/requirements-local.txt`."
                )
                raise

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None
        start = perf_counter()
        input_tokens = metrics_service.estimate_tokens(text)
        token_source = "estimated"
        cost_usd = 0.0
        success = False
        try:
            if self.provider == "openai":
                if self.openai_client is None:
                    success = True
                    return None
                resp = self.openai_client.embeddings.create(
                    input=text, model=self.model
                )
                input_tokens, token_source = self._token_usage(resp, input_tokens)
                cost_usd = metrics_service.estimate_embedding_cost_usd(
                    self.model, input_tokens
                )
                success = True
                return self._coerce_embedding(resp.data[0].embedding)
            if self.provider == "local":
                if self.sentence_transformer is None:
                    success = True
                    return None
                emb = self.sentence_transformer.encode(text, convert_to_numpy=True)
                success = True
                return self._coerce_embedding(emb)
            success = True
            return None
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
        finally:
            metrics_service.record(
                "embeddings.generate",
                latency_ms=(perf_counter() - start) * 1000,
                input_tokens=input_tokens,
                output_tokens=0,
                cost_usd=cost_usd,
                success=success,
                token_source=token_source,
                provider=self.provider,
                model=self.model,
            )

    async def generate_embeddings_batch(
        self, texts: Sequence[str]
    ) -> List[Optional[List[float]]]:
        items = list(texts)
        if not items:
            return []
        valid_texts = [t for t in items if t and t.strip()]
        if not valid_texts:
            return [None] * len(items)
        start = perf_counter()
        input_tokens = sum(
            metrics_service.estimate_tokens(text) for text in valid_texts
        )
        token_source = "estimated"
        cost_usd = 0.0
        success = False
        try:
            if self.provider == "openai":
                if self.openai_client is None:
                    success = True
                    return [None] * len(items)
                resp = self.openai_client.embeddings.create(
                    input=valid_texts, model=self.model
                )
                input_tokens, token_source = self._token_usage(resp, input_tokens)
                cost_usd = metrics_service.estimate_embedding_cost_usd(
                    self.model, input_tokens
                )
                embs = [self._coerce_embedding(d.embedding) for d in resp.data]
                out: List[Optional[List[float]]] = []
                idx = 0
                for t in items:
                    if t and t.strip():
                        out.append(embs[idx])
                        idx += 1
                    else:
                        out.append(None)
                success = True
                return out
            if self.provider == "local":
                if self.sentence_transformer is None:
                    success = True
                    return [None] * len(items)
                embs = self.sentence_transformer.encode(
                    valid_texts, convert_to_numpy=True
                )
                local_out: List[Optional[List[float]]] = []
                idx = 0
                for t in items:
                    if t and t.strip():
                        local_out.append(self._coerce_embedding(embs[idx]))
                        idx += 1
                    else:
                        local_out.append(None)
                success = True
                return local_out
            success = True
            return [None] * len(items)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return [None] * len(items)
        finally:
            metrics_service.record(
                "embeddings.batch",
                latency_ms=(perf_counter() - start) * 1000,
                input_tokens=input_tokens,
                output_tokens=0,
                cost_usd=cost_usd,
                success=success,
                token_source=token_source,
                provider=self.provider,
                model=self.model,
            )

    def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        if not embedding1 or not embedding2:
            return 0.0
        if len(embedding1) != len(embedding2):
            return 0.0
        dot = sum(a * b for a, b in zip(embedding1, embedding2))
        n1 = math.sqrt(sum(a * a for a in embedding1))
        n2 = math.sqrt(sum(b * b for b in embedding2))
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

    def _coerce_embedding(self, embedding: Any) -> List[float]:
        if hasattr(embedding, "tolist"):
            coerced = embedding.tolist()
        else:
            coerced = list(embedding)
        return [float(value) for value in coerced]

    def _token_usage(self, response: Any, fallback_tokens: int) -> tuple[int, str]:
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        if prompt_tokens is None:
            return fallback_tokens, "estimated"
        return int(prompt_tokens), "actual"


# Singleton
embedding_service = EmbeddingService()
