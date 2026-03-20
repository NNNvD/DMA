import asyncio

from fastapi.testclient import TestClient

from backend.services.metrics_service import metrics_service
from tests.support.app_factory import create_documents_test_app


def test_admin_metrics_reports_phase1_activity_and_can_reset():
    metrics_service.reset()
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        create_response = client.post(
            "/api/documents",
            json={
                "title": "Spell Rules",
                "kind": "rule",
                "content": (
                    "Fireball explodes in a 20-foot-radius sphere. "
                    "Creatures in the area take fire damage on a failed save."
                ),
            },
        )
        assert create_response.status_code == 200

        query_response = client.post(
            "/api/documents/rules/query",
            json={"query": "What does fireball do?", "strict": True},
        )
        assert query_response.status_code == 200

        metrics_response = client.get("/api/admin/metrics")
        assert metrics_response.status_code == 200
        payload = metrics_response.json()

        assert payload["totals"]["request_count"] >= 4
        assert payload["operations"]["documents.create"]["count"] == 1
        assert payload["operations"]["rules.query"]["count"] == 1
        assert payload["operations"]["embeddings.batch"]["count"] >= 1
        assert payload["operations"]["embeddings.generate"]["count"] >= 1
        assert payload["operations"]["rules.query"]["avg_latency_ms"] >= 0.0
        assert payload["operations"]["rules.query"]["input_tokens"] > 0

        reset_response = client.post("/api/admin/metrics/reset")
        assert reset_response.status_code == 200

        reset_payload = client.get("/api/admin/metrics").json()
        assert reset_payload["totals"]["request_count"] == 1
        assert reset_payload["operations"]["admin.metrics"]["count"] == 1
    finally:
        metrics_service.reset()
        asyncio.run(engine.dispose())
