from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.services.prep_service import prep_service


router = APIRouter()


class SessionBriefRequest(BaseModel):
    title: Optional[str] = None
    focus: Optional[str] = None
    current_location_id: Optional[int] = None
    session_count: int = Field(default=3, ge=1, le=10)
    include_inactive: bool = False
    store_document: bool = True
    source_name: Optional[str] = None


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


@router.post("/session-brief")
async def create_session_brief(
    payload: SessionBriefRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await prep_service.generate_session_brief(
            db,
            title=payload.title,
            focus=payload.focus,
            current_location_id=payload.current_location_id,
            session_count=payload.session_count,
            include_inactive=payload.include_inactive,
            store_document=payload.store_document,
            source_name=payload.source_name,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
