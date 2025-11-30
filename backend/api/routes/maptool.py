from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.models.maptool import CampaignMapState, MapToolTokenUpdate
from backend.services.maptool_adapter import maptool_adapter

router = APIRouter()


class MapPullRequest(BaseModel):
    map_id: str = Field(description="MapTool map identifier")
    retries: Optional[int] = Field(default=None, ge=1, description="Override retry attempts")


class MapPushRequest(BaseModel):
    map_id: str = Field(description="MapTool map identifier")
    retries: Optional[int] = Field(default=None, ge=1, description="Override retry attempts")
    updates: List[MapToolTokenUpdate]


@router.post("/pull", response_model=CampaignMapState)
async def pull_map_state(payload: MapPullRequest, authorization: Optional[str] = Header(default=None)):
    try:
        return await maptool_adapter.pull_map_state(
            payload.map_id, auth_header=authorization, retries=payload.retries
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/push")
async def push_token_updates(payload: MapPushRequest, authorization: Optional[str] = Header(default=None)):
    try:
        tokens = await maptool_adapter.push_token_updates(
            map_id=payload.map_id,
            updates=payload.updates,
            auth_header=authorization,
            retries=payload.retries,
        )
        return {"updated": [token.model_dump() for token in tokens]}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
