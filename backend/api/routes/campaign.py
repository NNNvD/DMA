from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import get_db
from backend.services.campaign_asset_import_service import campaign_asset_import_service
from backend.services.campaign_note_import_service import campaign_note_import_service
from backend.services.campaign_service import campaign_service
from backend.services.obsidian_vault_service import obsidian_vault_service
from backend.services.obsidian_vault_sync_service import obsidian_vault_sync_service
from backend.services.pc_sheet_import_service import pc_sheet_import_service
from backend.services.session_update_service import session_update_service


router = APIRouter()


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


class LocationDetails(BaseModel):
    category: Optional[str] = None
    region: Optional[str] = None
    environment: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)


class FactionDetails(BaseModel):
    agenda: Optional[str] = None
    headquarters: Optional[str] = None
    reputation: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    fronts: list[str] = Field(default_factory=list)


class CharacterDetails(BaseModel):
    role: Optional[str] = None
    pronouns: Optional[str] = None
    status: Optional[str] = None
    status_detail: Optional[str] = None
    portrait: Optional[str] = None
    image_link: Optional[str] = None
    public_summary: Optional[str] = None
    appearance_description: Optional[str] = None
    gm_summary: Optional[str] = None
    pc_encountered: Optional[bool] = None
    pc_relationship_status: Optional[str] = None
    vault_dm_notes: Optional[str] = None
    vault_player_summary: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    clues: list[str] = Field(default_factory=list)
    campaign_encounters: list[str] = Field(default_factory=list)
    vault_session_changes: list[str] = Field(default_factory=list)
    combat: dict[str, Any] = Field(default_factory=dict)
    statblock: dict[str, Any] = Field(default_factory=dict)


class ArtifactDetails(BaseModel):
    artifact_type: Optional[str] = None
    rarity: Optional[str] = None
    properties: list[str] = Field(default_factory=list)
    attuned_to: list[str] = Field(default_factory=list)


class EventDetails(BaseModel):
    timeline_position: Optional[str] = None
    scheduled_for: Optional[str] = None
    status: Optional[str] = None
    consequences: list[str] = Field(default_factory=list)


class CalendarDetails(BaseModel):
    months: list[str] = Field(default_factory=list)
    weekdays: list[str] = Field(default_factory=list)
    seasons: list[str] = Field(default_factory=list)
    current_date: dict[str, Any] = Field(default_factory=dict)


class HolidayDetails(BaseModel):
    date_label: Optional[str] = None
    recurrence: Optional[str] = None
    traditions: list[str] = Field(default_factory=list)


class ShopDetails(BaseModel):
    category: Optional[str] = None
    owner_name: Optional[str] = None
    stock_summary: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)


DETAIL_MODEL_BY_ENTITY_TYPE = {
    "artifact": ArtifactDetails,
    "calendar": CalendarDetails,
    "event": EventDetails,
    "faction": FactionDetails,
    "holiday": HolidayDetails,
    "location": LocationDetails,
    "npc": CharacterDetails,
    "pc": CharacterDetails,
    "shop": ShopDetails,
}


class CampaignEntityCreate(BaseModel):
    entity_type: str
    name: str = Field(min_length=1)
    stable_key: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    parent_entity_id: Optional[int] = None
    current_location_id: Optional[int] = None
    owner_entity_id: Optional[int] = None


class CampaignEntityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    stable_key: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None
    parent_entity_id: Optional[int] = None
    current_location_id: Optional[int] = None
    owner_entity_id: Optional[int] = None
    clear_parent_entity: bool = False
    clear_current_location: bool = False
    clear_owner_entity: bool = False


class CampaignRelationshipCreate(BaseModel):
    source_entity_id: int
    target_entity_id: int
    relationship_type: str = Field(min_length=1)
    strength: Optional[int] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None


class CharacterSheetData(BaseModel):
    ancestry: Optional[str] = None
    background: Optional[str] = None
    class_name: Optional[str] = None
    subclass: Optional[str] = None
    level: int = Field(default=1, ge=1)
    languages: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    attributes: dict[str, int] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)
    items: list[str | dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None


class CharacterSheetVersionCreate(BaseModel):
    source_name: Optional[str] = None
    sheet: CharacterSheetData


class CampaignNoteImportRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_name: Optional[str] = None
    default_tags: list[str] = Field(default_factory=list)
    store_document: bool = True


class PCSheetImportRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str | dict[str, Any]
    source_name: Optional[str] = None
    default_tags: list[str] = Field(default_factory=list)
    store_document: bool = True


class SessionUpdateImportRequest(BaseModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_name: Optional[str] = None
    default_tags: list[str] = Field(default_factory=list)
    store_document: bool = True


class BatchImportRequest(BaseModel):
    root_path: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    dry_run: bool = False
    store_documents: bool = True
    stop_on_error: bool = False


class ObsidianVaultExportRequest(BaseModel):
    vault_path: str = Field(min_length=1)
    include_inactive: bool = True
    include_campaign_notes: bool = True
    include_pc_sheets: bool = True
    include_session_logs: bool = True
    include_session_prep: bool = True
    include_indexes: bool = True
    include_command_center: bool = True
    campaign_note_limit: int = Field(default=100, ge=1, le=500)
    pc_sheet_limit: int = Field(default=50, ge=1, le=500)
    session_limit: int = Field(default=50, ge=1, le=500)
    prep_limit: int = Field(default=50, ge=1, le=500)


class ObsidianVaultImportRequest(BaseModel):
    vault_path: str = Field(min_length=1)
    include_campaign_entities: bool = True
    include_campaign_notes: bool = True
    include_pc_sheets: bool = True
    include_session_logs: bool = True


def _validate_details(entity_type: str, details: dict[str, Any]) -> dict[str, Any]:
    detail_model = DETAIL_MODEL_BY_ENTITY_TYPE.get(entity_type.strip().lower())
    if detail_model is None:
        return details
    return detail_model(**details).model_dump(exclude_none=True)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _normalize_import_content(value: str | dict[str, Any]) -> str:
    if isinstance(value, dict):
        return json.dumps(value)
    return value


@router.get("/overview")
async def get_campaign_overview(db: AsyncSession = Depends(get_db)):
    return await campaign_service.get_overview(db)


@router.post("/import/notes")
async def import_campaign_notes(
    payload: CampaignNoteImportRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await campaign_note_import_service.import_note(
            db,
            title=payload.title,
            content=payload.content,
            source_name=payload.source_name,
            default_tags=payload.default_tags,
            store_document=payload.store_document,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc


@router.post("/import/pc-sheet")
async def import_pc_sheet(
    payload: PCSheetImportRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await pc_sheet_import_service.import_sheet(
            db,
            title=payload.title,
            content=_normalize_import_content(payload.content),
            source_name=payload.source_name,
            default_tags=payload.default_tags,
            store_document=payload.store_document,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc


@router.post("/import/session-update")
async def import_session_update(
    payload: SessionUpdateImportRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await session_update_service.import_session_update(
            db,
            title=payload.title,
            content=payload.content,
            source_name=payload.source_name,
            default_tags=payload.default_tags,
            store_document=payload.store_document,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc


@router.get("/import/dropzone")
async def preview_dropzone_imports(
    root_path: Optional[str] = Query(default=None),
    category: Optional[list[str]] = Query(default=None),
    store_documents: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await campaign_asset_import_service.preview_batch(
            db,
            root_path=root_path,
            categories=category,
            store_documents=store_documents,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except OSError as exc:
        raise _bad_request(str(exc)) from exc


@router.post("/import/batch")
async def import_dropzone_assets(
    payload: BatchImportRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await campaign_asset_import_service.import_batch(
            db,
            root_path=payload.root_path,
            categories=payload.categories,
            dry_run=payload.dry_run,
            store_documents=payload.store_documents,
            stop_on_error=payload.stop_on_error,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except OSError as exc:
        raise _bad_request(str(exc)) from exc


@router.post("/export/obsidian-vault")
async def export_obsidian_vault(
    payload: ObsidianVaultExportRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await obsidian_vault_service.export_vault(
            db,
            vault_path=payload.vault_path,
            include_inactive=payload.include_inactive,
            include_campaign_notes=payload.include_campaign_notes,
            include_pc_sheets=payload.include_pc_sheets,
            include_session_logs=payload.include_session_logs,
            include_session_prep=payload.include_session_prep,
            include_indexes=payload.include_indexes,
            include_command_center=payload.include_command_center,
            campaign_note_limit=payload.campaign_note_limit,
            pc_sheet_limit=payload.pc_sheet_limit,
            session_limit=payload.session_limit,
            prep_limit=payload.prep_limit,
        )
    except OSError as exc:
        raise _bad_request(str(exc)) from exc


@router.get("/entities", response_model=PaginatedResponse)
async def list_campaign_entities(
    entity_type: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    language: Optional[str] = Query(default=None),
    current_location_id: Optional[int] = Query(default=None),
    owner_entity_id: Optional[int] = Query(default=None),
    relationship_type: Optional[str] = Query(default=None),
    related_entity_id: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await campaign_service.list_entities(
            db,
            entity_type=entity_type,
            q=q,
            language=language,
            current_location_id=current_location_id,
            owner_entity_id=owner_entity_id,
            relationship_type=relationship_type,
            related_entity_id=related_entity_id,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc


@router.post("/import/obsidian-vault")
async def import_obsidian_vault(
    payload: ObsidianVaultImportRequest, db: AsyncSession = Depends(get_db)
):
    try:
        return await obsidian_vault_sync_service.import_vault(
            db,
            vault_path=payload.vault_path,
            include_campaign_entities=payload.include_campaign_entities,
            include_campaign_notes=payload.include_campaign_notes,
            include_pc_sheets=payload.include_pc_sheets,
            include_session_logs=payload.include_session_logs,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc


@router.post("/entities")
async def create_campaign_entity(
    payload: CampaignEntityCreate, db: AsyncSession = Depends(get_db)
):
    try:
        entity = await campaign_service.create_entity(
            db,
            entity_type=payload.entity_type,
            name=payload.name,
            stable_key=payload.stable_key,
            summary=payload.summary,
            description=payload.description,
            details=_validate_details(payload.entity_type, payload.details),
            tags=payload.tags,
            is_active=payload.is_active,
            parent_entity_id=payload.parent_entity_id,
            current_location_id=payload.current_location_id,
            owner_entity_id=payload.owner_entity_id,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    return campaign_service.entity_to_dict(entity, include_relationships=True)


@router.get("/entities/{entity_id}")
async def get_campaign_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    entity = await campaign_service.get_entity(entity_id, db)
    if entity is None:
        raise _not_found("Campaign entity not found")
    return campaign_service.entity_to_dict(
        entity, include_relationships=True, include_sheet_versions=True
    )


@router.patch("/entities/{entity_id}")
async def update_campaign_entity(
    entity_id: int,
    payload: CampaignEntityUpdate,
    db: AsyncSession = Depends(get_db),
):
    update_values = payload.model_dump(exclude_unset=True)
    if "details" in update_values and payload.details is not None:
        entity = await campaign_service.get_entity(entity_id, db)
        if entity is None:
            raise _not_found("Campaign entity not found")
        update_values["details"] = _validate_details(
            entity.entity_type, payload.details
        )
    try:
        entity = await campaign_service.update_entity(
            entity_id,
            db,
            **update_values,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    return campaign_service.entity_to_dict(
        entity, include_relationships=True, include_sheet_versions=True
    )


@router.delete("/entities/{entity_id}")
async def delete_campaign_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await campaign_service.delete_entity(entity_id, db)
    if not deleted:
        raise _not_found("Campaign entity not found")
    return {"deleted": True, "id": entity_id}


@router.post("/relationships")
async def create_campaign_relationship(
    payload: CampaignRelationshipCreate, db: AsyncSession = Depends(get_db)
):
    try:
        relationship = await campaign_service.create_relationship(
            db,
            source_entity_id=payload.source_entity_id,
            target_entity_id=payload.target_entity_id,
            relationship_type=payload.relationship_type,
            strength=payload.strength,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    return campaign_service.relationship_to_dict(relationship)


@router.get("/entities/{entity_id}/relationships")
async def list_entity_relationships(entity_id: int, db: AsyncSession = Depends(get_db)):
    try:
        relationships = await campaign_service.list_relationships(entity_id, db)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    return {"entity_id": entity_id, "relationships": relationships}


@router.get("/pcs/{entity_id}/dossier")
async def get_pc_dossier(entity_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await campaign_service.get_pc_dossier(entity_id, db)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc


@router.post("/entities/{entity_id}/sheet-versions")
async def create_character_sheet_version(
    entity_id: int,
    payload: CharacterSheetVersionCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        version = await campaign_service.add_sheet_version(
            entity_id,
            db,
            payload=payload.sheet.model_dump(exclude_none=True),
            source_name=payload.source_name,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    return campaign_service.sheet_version_to_dict(version)


@router.get("/entities/{entity_id}/sheet-versions")
async def list_character_sheet_versions(
    entity_id: int, db: AsyncSession = Depends(get_db)
):
    try:
        versions = await campaign_service.list_sheet_versions(entity_id, db)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except LookupError as exc:
        raise _not_found(str(exc)) from exc
    return {"entity_id": entity_id, "versions": versions}


@router.get("/session-history", response_model=PaginatedResponse)
async def get_session_history(
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.get_session_history(
        db,
        q=q,
        page=page,
        page_size=page_size,
    )
