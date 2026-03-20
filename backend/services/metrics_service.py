from __future__ import annotations

import json
import math
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional

from backend.config.settings import settings

DEFAULT_OPENAI_EMBEDDING_COSTS_PER_1M = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}


class OperationStats:
    def __init__(self, max_latency_samples: int) -> None:
        self.count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self.max_latency_ms = 0.0
        self.recent_latency_ms: deque[float] = deque(maxlen=max_latency_samples)
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self.actual_token_events = 0
        self.estimated_token_events = 0
        self.providers: Dict[str, int] = {}
        self.models: Dict[str, int] = {}
        self.last_seen_at: Optional[str] = None

    def record(
        self,
        *,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        success: bool,
        token_source: str,
        provider: Optional[str],
        model: Optional[str],
    ) -> None:
        self.count += 1
        if not success:
            self.error_count += 1
        self.total_latency_ms += latency_ms
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.recent_latency_ms.append(latency_ms)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.total_cost_usd += cost_usd
        if token_source == "actual":
            self.actual_token_events += 1
        else:
            self.estimated_token_events += 1
        if provider:
            self.providers[provider] = self.providers.get(provider, 0) + 1
        if model:
            self.models[model] = self.models.get(model, 0) + 1
        self.last_seen_at = _utcnow()

    def snapshot(self) -> Dict[str, Any]:
        latencies = sorted(self.recent_latency_ms)
        return {
            "count": self.count,
            "error_count": self.error_count,
            "avg_latency_ms": (
                _round(self.total_latency_ms / self.count) if self.count else 0.0
            ),
            "p50_latency_ms": _percentile(latencies, 50),
            "p95_latency_ms": _percentile(latencies, 95),
            "max_latency_ms": _round(self.max_latency_ms),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": _round(self.total_cost_usd, 8),
            "actual_token_events": self.actual_token_events,
            "estimated_token_events": self.estimated_token_events,
            "providers": dict(sorted(self.providers.items())),
            "models": dict(sorted(self.models.items())),
            "last_seen_at": self.last_seen_at,
        }


class MetricsService:
    def __init__(self, max_latency_samples: int = 500) -> None:
        self.max_latency_samples = max_latency_samples
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.started_at = _utcnow()
            self.updated_at = self.started_at
            self._operations: Dict[str, OperationStats] = {}

    def estimate_tokens(self, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, default=str, sort_keys=True)
        if not text.strip():
            return 0
        return max(1, math.ceil(len(text) / 4))

    def estimate_embedding_cost_usd(self, model: str, input_tokens: int) -> float:
        if input_tokens <= 0:
            return 0.0
        per_million = settings.openai_embedding_cost_per_1m_tokens
        if per_million is None:
            per_million = DEFAULT_OPENAI_EMBEDDING_COSTS_PER_1M.get(model, 0.0)
        return (input_tokens / 1_000_000) * per_million

    def record(
        self,
        operation: str,
        *,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        success: bool = True,
        token_source: str = "estimated",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        with self._lock:
            stats = self._operations.setdefault(
                operation, OperationStats(self.max_latency_samples)
            )
            stats.record(
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                success=success,
                token_source=token_source,
                provider=provider,
                model=model,
            )
            self.updated_at = _utcnow()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            operations = {
                name: stats.snapshot()
                for name, stats in sorted(self._operations.items())
            }
            total_requests = sum(item["count"] for item in operations.values())
            total_errors = sum(item["error_count"] for item in operations.values())
            total_input_tokens = sum(
                item["input_tokens"] for item in operations.values()
            )
            total_output_tokens = sum(
                item["output_tokens"] for item in operations.values()
            )
            total_cost_usd = sum(item["total_cost_usd"] for item in operations.values())
            avg_latency_numerator = sum(
                item["avg_latency_ms"] * item["count"] for item in operations.values()
            )
            avg_latency_ms = (
                avg_latency_numerator / total_requests if total_requests else 0.0
            )
            return {
                "started_at": self.started_at,
                "updated_at": self.updated_at,
                "max_latency_samples": self.max_latency_samples,
                "totals": {
                    "request_count": total_requests,
                    "error_count": total_errors,
                    "avg_latency_ms": _round(avg_latency_ms),
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "total_cost_usd": _round(total_cost_usd, 8),
                },
                "operations": operations,
            }


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    index = math.ceil((percentile / 100) * len(values)) - 1
    index = min(max(index, 0), len(values) - 1)
    return _round(values[index])


def _round(value: float, digits: int = 3) -> float:
    return round(value, digits)


metrics_service = MetricsService(max_latency_samples=settings.metrics_latency_samples)
