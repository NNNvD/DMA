from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.routes.admin import router as admin_router
from backend.api.routes.documents import router as documents_router
from backend.models.base import Base, get_db
from backend.services.metrics_service import metrics_service

ROOT = Path(__file__).resolve().parent.parent

FIXTURE_ROOT = ROOT / "tests" / "acceptance" / "pf2e_phase1_acceptance_corpus"
CORPUS_PATH = FIXTURE_ROOT / "assets" / "fixtures" / "phase1" / "phase1_corpus.json"
QUESTIONS_PATH = FIXTURE_ROOT / "tests" / "acceptance" / "phase1_questions.json"
SUPPORTED_DOCUMENT_FIELDS = {
    "title",
    "kind",
    "content",
    "summary",
    "source_name",
    "url",
}


def create_benchmark_app():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session_local = asyncio.run(_init())
    app = FastAPI()
    app.include_router(documents_router, prefix="/api/documents")
    app.include_router(admin_router, prefix="/api/admin")

    async def override_get_db():
        async with session_local() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, engine


def summarize_latencies(latencies_ms: List[float]) -> Dict[str, float]:
    if not latencies_ms:
        return {
            "count": 0,
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "max_latency_ms": 0.0,
        }
    ordered = sorted(latencies_ms)
    return {
        "count": len(ordered),
        "avg_latency_ms": round(mean(ordered), 3),
        "p50_latency_ms": percentile(ordered, 50),
        "p95_latency_ms": percentile(ordered, 95),
        "max_latency_ms": round(max(ordered), 3),
    }


def percentile(values: List[float], p: int) -> float:
    index = max(0, min(len(values) - 1, ((p * len(values) + 99) // 100) - 1))
    return round(values[index], 3)


def load_fixture(path: Path) -> Any:
    return json.loads(path.read_text())


def validate_case(
    case: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any] | None:
    if case.get("expected_strict_abstain"):
        if "couldn't find a confident answer" in payload["answer"].lower():
            return None
        return {
            "query": case["query"],
            "category": case["category"],
            "reason": "expected strict abstention",
        }

    combined_text = " ".join(
        [payload["answer"], *[citation["excerpt"] for citation in payload["citations"]]]
    ).lower()
    if case["expected_snippet"].lower() not in combined_text:
        return {
            "query": case["query"],
            "category": case["category"],
            "reason": "expected snippet not found",
            "expected_snippet": case["expected_snippet"],
        }
    return None


def run_benchmark(json_output: bool) -> int:
    corpus = load_fixture(CORPUS_PATH)
    questions = load_fixture(QUESTIONS_PATH)
    metrics_service.reset()
    app, engine = create_benchmark_app()
    client = TestClient(app)
    ingest_latencies: List[float] = []
    search_latencies: List[float] = []
    rules_latencies: List[float] = []
    failures: List[Dict[str, Any]] = []

    try:
        for document in corpus:
            payload = {
                key: value
                for key, value in document.items()
                if key in SUPPORTED_DOCUMENT_FIELDS
            }
            start = perf_counter()
            response = client.post("/api/documents", json=payload)
            ingest_latencies.append((perf_counter() - start) * 1000)
            if response.status_code != 200:
                failures.append(
                    {
                        "stage": "ingest",
                        "document": document["title"],
                        "status_code": response.status_code,
                    }
                )

        start = perf_counter()
        search_response = client.get(
            "/api/documents/search",
            params={"q": "fireball", "kind": "rule", "top_k": 3},
        )
        search_latencies.append((perf_counter() - start) * 1000)
        if search_response.status_code != 200:
            failures.append(
                {
                    "stage": "search",
                    "query": "fireball",
                    "status_code": search_response.status_code,
                }
            )

        category_latencies: Dict[str, List[float]] = {}
        for case in questions:
            start = perf_counter()
            response = client.post(
                "/api/documents/rules/query",
                json={"query": case["query"], "strict": True, "top_k": 3},
            )
            latency_ms = (perf_counter() - start) * 1000
            rules_latencies.append(latency_ms)
            category_latencies.setdefault(case["category"], []).append(latency_ms)
            if response.status_code != 200:
                failures.append(
                    {
                        "stage": "rules_query",
                        "query": case["query"],
                        "status_code": response.status_code,
                    }
                )
                continue
            failure = validate_case(case, response.json())
            if failure:
                failures.append(failure)

        metrics = client.get("/api/admin/metrics").json()
    finally:
        asyncio.run(engine.dispose())

    report = {
        "fixture": str(FIXTURE_ROOT),
        "documents": len(corpus),
        "questions": len(questions),
        "validation": {
            "passed": not failures,
            "failure_count": len(failures),
            "failures": failures,
        },
        "latency_ms": {
            "documents_create": summarize_latencies(ingest_latencies),
            "documents_search": summarize_latencies(search_latencies),
            "rules_query": summarize_latencies(rules_latencies),
            "rules_query_by_category": {
                category: summarize_latencies(values)
                for category, values in sorted(category_latencies.items())
            },
        },
        "metrics": metrics,
    }

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print("Phase 1 benchmark")
        print(f"Fixture: {FIXTURE_ROOT}")
        print(
            "Validation: "
            f"{'passed' if report['validation']['passed'] else 'failed'} "
            f"({report['validation']['failure_count']} failures)"
        )
        print(
            "Rules query latency: "
            f"avg={report['latency_ms']['rules_query']['avg_latency_ms']} ms, "
            f"p95={report['latency_ms']['rules_query']['p95_latency_ms']} ms"
        )
        print(
            "Tracked tokens/cost: "
            f"{metrics['totals']['total_tokens']} tokens, "
            f"${metrics['totals']['total_cost_usd']:.8f}"
        )
        if failures:
            print("Failures:")
            for failure in failures:
                print(json.dumps(failure, sort_keys=True))

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a lightweight Phase 1 benchmark against the active acceptance corpus."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full benchmark report as JSON.",
    )
    args = parser.parse_args()
    return run_benchmark(json_output=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
