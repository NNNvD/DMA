from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from fastapi.testclient import TestClient

from backend.services.metrics_service import metrics_service
from tests.support.app_factory import create_documents_test_app

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "phase2"
NOTES_PATH = FIXTURE_ROOT / "sample_campaign_notes.md"
PC_SHEET_PATH = FIXTURE_ROOT / "sample_pc_sheet.json"


def summarize_latencies(latencies_ms: list[float]) -> dict[str, float]:
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


def percentile(values: list[float], percentile_value: int) -> float:
    index = max(
        0, min(len(values) - 1, ((percentile_value * len(values) + 99) // 100) - 1)
    )
    return round(values[index], 3)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def run_benchmark(json_output: bool) -> int:
    notes = NOTES_PATH.read_text()
    pc_sheet = load_json(PC_SHEET_PATH)
    metrics_service.reset()
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    import_latencies: list[float] = []
    query_latencies: list[float] = []
    failures: list[dict[str, Any]] = []

    try:
        start = perf_counter()
        notes_response = client.post(
            "/api/campaign/import/notes",
            json={"source_id": "benchmark-notes-v1", "markdown": notes},
        )
        import_latencies.append((perf_counter() - start) * 1000)
        if notes_response.status_code != 200:
            failures.append(
                {
                    "stage": "import_notes",
                    "status_code": notes_response.status_code,
                }
            )

        start = perf_counter()
        pc_response = client.post("/api/campaign/import/pc-sheet", json=pc_sheet)
        import_latencies.append((perf_counter() - start) * 1000)
        if pc_response.status_code != 200:
            failures.append(
                {
                    "stage": "import_pc_sheet",
                    "status_code": pc_response.status_code,
                }
            )

        for path, params, expected_key in (
            ("/api/campaign/npcs", {"location": "otari"}, "captain-mira"),
            (
                "/api/campaign/entities/search",
                {"type": "npc", "location": "otari"},
                "captain-mira",
            ),
        ):
            start = perf_counter()
            response = client.get(path, params=params)
            query_latencies.append((perf_counter() - start) * 1000)
            if response.status_code != 200:
                failures.append(
                    {
                        "stage": path,
                        "status_code": response.status_code,
                    }
                )
                continue
            payload = response.json()
            results = payload["results"]
            if not results or results[0]["entity_key"] != expected_key:
                failures.append(
                    {
                        "stage": path,
                        "reason": "unexpected query result",
                    }
                )

        factions_response = client.get("/api/campaign/pcs/talia-storm/factions")
        if factions_response.status_code != 200:
            failures.append(
                {
                    "stage": "pc_factions",
                    "status_code": factions_response.status_code,
                }
            )
        else:
            factions = factions_response.json()["factions"]
            if not factions or factions[0]["entity"]["entity_key"] != "dawnwatch":
                failures.append(
                    {
                        "stage": "pc_factions",
                        "reason": "missing faction tie",
                    }
                )

        consistency_response = client.get("/api/campaign/consistency")
        if (
            consistency_response.status_code != 200
            or not consistency_response.json()["ok"]
        ):
            failures.append(
                {
                    "stage": "consistency",
                    "reason": "consistency endpoint failed or returned problems",
                }
            )

        metrics = client.get("/api/admin/metrics").json()
    finally:
        asyncio.run(engine.dispose())

    report = {
        "fixture": str(FIXTURE_ROOT),
        "validation": {
            "passed": not failures,
            "failure_count": len(failures),
            "failures": failures,
        },
        "latency_ms": {
            "campaign_import": summarize_latencies(import_latencies),
            "campaign_query": summarize_latencies(query_latencies),
        },
        "metrics": metrics,
    }

    if json_output:
        print(json.dumps(report, indent=2))
    else:
        print("Phase 2 benchmark")
        print(f"Fixture: {FIXTURE_ROOT}")
        print(
            "Validation: "
            f"{'passed' if report['validation']['passed'] else 'failed'} "
            f"({report['validation']['failure_count']} failures)"
        )
        print(
            "Campaign import latency: "
            f"avg={report['latency_ms']['campaign_import']['avg_latency_ms']} ms, "
            f"p95={report['latency_ms']['campaign_import']['p95_latency_ms']} ms"
        )
        print(
            "Campaign query latency: "
            f"avg={report['latency_ms']['campaign_query']['avg_latency_ms']} ms, "
            f"p95={report['latency_ms']['campaign_query']['p95_latency_ms']} ms"
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
        description="Run a lightweight Phase 2 benchmark against the sample campaign fixtures."
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    args = parser.parse_args()
    return run_benchmark(json_output=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
