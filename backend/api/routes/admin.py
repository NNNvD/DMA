from fastapi import APIRouter
from backend.services.scheduler import scheduler

router = APIRouter()


@router.post("/reindex")
async def trigger_reindex():
    await scheduler.reindex_embeddings()
    return {"status": "ok", "triggered": "reindex_embeddings"}

