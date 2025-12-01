from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.base import get_db
from backend.services.context_service import context_service


router = APIRouter()


class ContextPayload(BaseModel):
    key: str
    data: Dict[str, Any]


@router.post("/save")
async def save_context(payload: ContextPayload, db: AsyncSession = Depends(get_db)):
    entry = await context_service.save(payload.key, payload.data, db)
    return {"key": entry.key, "updated_at": entry.updated_at.isoformat()}


@router.get("/restore/{key}")
async def restore_context(key: str, db: AsyncSession = Depends(get_db)):
    entry = await context_service.load(key, db)
    if not entry:
        raise HTTPException(status_code=404, detail="Context not found")
    return {"key": entry.key, "data": entry.data, "updated_at": entry.updated_at.isoformat()}


@router.delete("/{key}")
async def delete_context(key: str, db: AsyncSession = Depends(get_db)):
    ok = await context_service.delete(key, db)
    if not ok:
        raise HTTPException(status_code=404, detail="Context not found")
    return {"deleted": True, "key": key}

