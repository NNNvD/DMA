from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MapToolToken(BaseModel):
    id: str
    name: str
    x: float
    y: float
    notes: Optional[str] = None
    gm_notes: Optional[str] = None
    layer: Optional[str] = None
    light_radius: Optional[float] = None
    vision_enabled: bool = True


class MapToolLightUpdate(BaseModel):
    mode: str = Field(default="dim")
    intensity: Optional[float] = Field(default=None, description="Light intensity or radius")


class MapToolFogUpdate(BaseModel):
    shape: str = Field(default="reveal")
    coordinates: List[List[float]] = Field(default_factory=list)


class MapToolMap(BaseModel):
    id: str
    name: str
    tokens: List[MapToolToken] = Field(default_factory=list)
    fog_state: Optional[str] = None
    light_state: Optional[str] = None

    def to_campaign_map(self) -> CampaignMapState:
        return maptool_map_to_campaign(self)


class MapToolTokenUpdate(BaseModel):
    token_id: str
    x: Optional[float] = None
    y: Optional[float] = None
    note: Optional[str] = None
    gm_note: Optional[str] = None

    def to_payload(self) -> dict:
        payload = {}
        if self.x is not None:
            payload["x"] = self.x
        if self.y is not None:
            payload["y"] = self.y
        if self.note is not None:
            payload["notes"] = self.note
        if self.gm_note is not None:
            payload["gm_notes"] = self.gm_note
        return payload


class CampaignToken(BaseModel):
    token_id: str
    label: str
    x: float
    y: float
    note: Optional[str] = None
    gm_note: Optional[str] = None
    layer: Optional[str] = None


class CampaignMapState(BaseModel):
    map_id: str
    name: str
    tokens: List[CampaignToken] = Field(default_factory=list)
    fog_state: Optional[str] = None
    light_state: Optional[str] = None


def maptool_token_to_campaign(token: MapToolToken) -> CampaignToken:
    return CampaignToken(
        token_id=token.id,
        label=token.name,
        x=token.x,
        y=token.y,
        note=token.notes,
        gm_note=token.gm_notes,
        layer=token.layer,
    )


def maptool_map_to_campaign(map_payload: MapToolMap) -> CampaignMapState:
    return CampaignMapState(
        map_id=map_payload.id,
        name=map_payload.name,
        tokens=[maptool_token_to_campaign(token) for token in map_payload.tokens],
        fog_state=map_payload.fog_state,
        light_state=map_payload.light_state,
    )
