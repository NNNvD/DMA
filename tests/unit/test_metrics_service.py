from backend.services.metrics_service import MetricsService


def test_metrics_service_tracks_latency_tokens_and_costs():
    service = MetricsService(max_latency_samples=5)

    service.record(
        "rules.query",
        latency_ms=12.5,
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.001,
        success=True,
        token_source="estimated",
        provider="internal",
        model="deterministic",
    )
    service.record(
        "rules.query",
        latency_ms=20.0,
        input_tokens=4,
        output_tokens=6,
        cost_usd=0.0,
        success=False,
        token_source="actual",
        provider="internal",
        model="deterministic",
    )

    snapshot = service.snapshot()
    rules_stats = snapshot["operations"]["rules.query"]

    assert snapshot["totals"]["request_count"] == 2
    assert rules_stats["count"] == 2
    assert rules_stats["error_count"] == 1
    assert rules_stats["input_tokens"] == 14
    assert rules_stats["output_tokens"] == 26
    assert rules_stats["total_tokens"] == 40
    assert rules_stats["total_cost_usd"] == 0.001
    assert rules_stats["estimated_token_events"] == 1
    assert rules_stats["actual_token_events"] == 1
    assert rules_stats["p95_latency_ms"] == 20.0


def test_metrics_service_estimates_tokens_and_embedding_cost():
    service = MetricsService(max_latency_samples=2)

    assert service.estimate_tokens("fireball rules") > 0
    assert service.estimate_tokens({"query": "fireball"}) > 0
    assert service.estimate_embedding_cost_usd("text-embedding-3-small", 1000) > 0
