from __future__ import annotations

from time import perf_counter
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.services.campaign_service import (
    CampaignValidationError,
    campaign_service,
)
from backend.services.metrics_service import metrics_service

router = APIRouter()


class RelationshipPayload(BaseModel):
    target_key: str | None = None
    target_type: str | None = None
    target_name: str | None = None
    relationship_type: str
    note: str | None = None


class EntityPayloadBase(BaseModel):
    entity_key: str | None = None
    name: str
    summary: str | None = None
    status: str = "active"
    tags: list[str] = Field(default_factory=list)
    relationships: list[RelationshipPayload] = Field(default_factory=list)


class PCEntityPayload(EntityPayloadBase):
    entity_type: Literal["pc"]
    ancestry: str | None = None
    character_class: str | None = None
    level: int | None = None
    background: str | None = None
    backstory: str | None = None
    homeland: str | None = None
    languages: list[str] = Field(default_factory=list)
    notable_items: list[str] = Field(default_factory=list)


class NPCEntityPayload(EntityPayloadBase):
    entity_type: Literal["npc"]
    role: str | None = None
    appearance: str | None = None
    goal: str | None = None
    disposition: str | None = None


class FactionEntityPayload(EntityPayloadBase):
    entity_type: Literal["faction"]
    category: str | None = None
    goals: str | None = None
    influence: str | None = None
    alignment: str | None = None


class LocationEntityPayload(EntityPayloadBase):
    entity_type: Literal["location"]
    location_type: str | None = None
    region: str | None = None
    environment: str | None = None


class EventEntityPayload(EntityPayloadBase):
    entity_type: Literal["event"]
    event_date: str | None = None
    phase: str | None = None
    details: str | None = None


EntityPayload = Annotated[
    PCEntityPayload
    | NPCEntityPayload
    | FactionEntityPayload
    | LocationEntityPayload
    | EventEntityPayload,
    Field(discriminator="entity_type"),
]


class NoteImportRequest(BaseModel):
    source_id: str
    markdown: str


class PCSheetImportRequest(BaseModel):
    source_id: str
    entity_key: str | None = None
    name: str
    summary: str | None = None
    status: str = "active"
    tags: list[str] = Field(default_factory=list)
    ancestry: str | None = None
    character_class: str | None = None
    level: int | None = None
    background: str | None = None
    backstory: str | None = None
    homeland: str | None = None
    languages: list[str] = Field(default_factory=list)
    notable_items: list[str] = Field(default_factory=list)
    current_location: str | None = None
    factions: list[str] = Field(default_factory=list)
    relationships: list[RelationshipPayload] = Field(default_factory=list)


def _raise_validation_error(error: CampaignValidationError) -> None:
    message = str(error)
    if message.startswith("Unknown entity:"):
        raise HTTPException(status_code=404, detail=message) from error
    raise HTTPException(status_code=400, detail=message) from error


@router.post("/entities")
async def upsert_campaign_entity(
    payload: EntityPayload,
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = campaign_service.serialize_entity(
            await campaign_service.upsert_entity(
                payload.model_dump(exclude_none=True),
                db,
            )
        )
        success = True
        return response_payload
    except CampaignValidationError as error:
        _raise_validation_error(error)
    finally:
        metrics_service.record(
            "campaign.entities.upsert",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(
                payload.model_dump(exclude_none=True)
            ),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/entities/search")
async def search_campaign_entities(
    q: str | None = Query(default=None),
    entity_type: str | None = Query(default=None, alias="type"),
    location: str | None = Query(default=None),
    related_to: str | None = Query(default=None),
    relationship_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = {
            "results": await campaign_service.search_entities(
                db,
                q=q,
                entity_type=entity_type,
                location=location,
                related_to=related_to,
                relationship_type=relationship_type,
            )
        }
        success = True
        return response_payload
    except CampaignValidationError as error:
        _raise_validation_error(error)
    finally:
        metrics_service.record(
            "campaign.entities.search",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(
                {
                    "q": q,
                    "type": entity_type,
                    "location": location,
                    "related_to": related_to,
                    "relationship_type": relationship_type,
                }
            ),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/entities/{entity_key}")
async def get_campaign_entity(
    entity_key: str,
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        entity = await campaign_service.get_entity(entity_key, db)
        if entity is None:
            raise HTTPException(status_code=404, detail="Campaign entity not found")
        response_payload = campaign_service.serialize_entity(entity)
        success = True
        return response_payload
    finally:
        metrics_service.record(
            "campaign.entities.get",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens({"entity_key": entity_key}),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/npcs")
async def get_npcs_by_location(
    location: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = {
            "location": location,
            "results": await campaign_service.list_npcs_by_location(location, db),
        }
        success = True
        return response_payload
    except CampaignValidationError as error:
        _raise_validation_error(error)
    finally:
        metrics_service.record(
            "campaign.npcs.by_location",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens({"location": location}),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/pcs/{entity_key}/factions")
async def get_pc_factions(
    entity_key: str,
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = await campaign_service.list_pc_factions(entity_key, db)
        success = True
        return response_payload
    except CampaignValidationError as error:
        _raise_validation_error(error)
    finally:
        metrics_service.record(
            "campaign.pcs.factions",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens({"entity_key": entity_key}),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.post("/import/notes")
async def import_campaign_notes(
    payload: NoteImportRequest,
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = await campaign_service.import_notes(
            source_id=payload.source_id,
            markdown=payload.markdown,
            db=db,
        )
        success = True
        return response_payload
    except CampaignValidationError as error:
        _raise_validation_error(error)
    finally:
        metrics_service.record(
            "campaign.import.notes",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(
                payload.model_dump(exclude_none=True)
            ),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.post("/import/pc-sheet")
async def import_pc_sheet(
    payload: PCSheetImportRequest,
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = await campaign_service.import_pc_sheet(
            source_id=payload.source_id,
            payload=payload.model_dump(exclude={"source_id"}, exclude_none=True),
            db=db,
        )
        success = True
        return response_payload
    except CampaignValidationError as error:
        _raise_validation_error(error)
    finally:
        metrics_service.record(
            "campaign.import.pc_sheet",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=metrics_service.estimate_tokens(
                payload.model_dump(exclude_none=True)
            ),
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )


@router.get("/consistency")
async def get_campaign_consistency(
    db: AsyncSession = Depends(get_db),
):
    start = perf_counter()
    response_payload = None
    success = False
    try:
        response_payload = await campaign_service.get_consistency_report(db)
        success = True
        return response_payload
    finally:
        metrics_service.record(
            "campaign.consistency",
            latency_ms=(perf_counter() - start) * 1000,
            input_tokens=0,
            output_tokens=metrics_service.estimate_tokens(response_payload),
            success=success,
            token_source="estimated",
        )
