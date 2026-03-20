from fastapi import APIRouter
from backend.services.scheduler import scheduler
from backend.services.metrics_service import metrics_service

router = APIRouter()


@router.post("/reindex")
async def trigger_reindex():
    await scheduler.reindex_embeddings()
    return {"status": "ok", "triggered": "reindex_embeddings"}


@router.get("/metrics")
async def get_metrics():
    snapshot = metrics_service.snapshot()
    metrics_service.record(
        "admin.metrics",
        latency_ms=0.0,
        input_tokens=0,
        output_tokens=metrics_service.estimate_tokens(snapshot),
        success=True,
        token_source="estimated",
    )
    return metrics_service.snapshot()


@router.post("/metrics/reset")
async def reset_metrics():
    metrics_service.reset()
    return {"status": "ok", "reset": True}
