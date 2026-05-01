#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import secrets
import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.models.maptool import MapToolMap  # noqa: E402


class BridgeLoginRequest(BaseModel):
    username: str
    password: str


class BridgeStatusResponse(BaseModel):
    ok: bool = True
    protected: bool
    map_count: int


class MapToolBridgeStore:
    def __init__(self) -> None:
        self._maps: dict[str, MapToolMap] = {}

    def save(self, payload: MapToolMap) -> MapToolMap:
        self._maps[payload.id] = payload
        return payload

    def get(self, map_id: str) -> MapToolMap | None:
        return self._maps.get(map_id)

    def count(self) -> int:
        return len(self._maps)


def create_bridge_app(
    *,
    username: str | None = None,
    password: str | None = None,
    bearer_token: str | None = None,
) -> FastAPI:
    app = FastAPI(title="DMA MapTool Bridge", version="0.1.0")
    store = MapToolBridgeStore()

    configured_username = _normalize_optional_text(username)
    configured_password = _normalize_optional_text(password)
    configured_token = _normalize_token(bearer_token)
    auth_enabled = configured_token is not None

    def require_auth(authorization: str | None) -> None:
        if not auth_enabled:
            return
        if authorization != configured_token:
            raise HTTPException(status_code=401, detail="Invalid bridge authorization")

    @app.get("/health", response_model=BridgeStatusResponse)
    async def health():
        return BridgeStatusResponse(protected=auth_enabled, map_count=store.count())

    @app.post("/auth/login")
    async def login(payload: BridgeLoginRequest):
        if (
            configured_username is None
            or configured_password is None
            or configured_token is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Bridge login is not configured; use an Authorization header instead",
            )
        if (
            payload.username != configured_username
            or payload.password != configured_password
        ):
            raise HTTPException(status_code=401, detail="Invalid bridge credentials")
        return {"token": configured_token.removeprefix("Bearer ").strip()}

    @app.post("/bridge/map-state", response_model=MapToolMap)
    async def push_map_state(
        payload: MapToolMap,
        authorization: Optional[str] = Header(default=None),
    ):
        require_auth(authorization)
        return store.save(payload)

    @app.get("/maps/{map_id}", response_model=MapToolMap)
    async def fetch_map_state(
        map_id: str,
        authorization: Optional[str] = Header(default=None),
    ):
        require_auth(authorization)
        payload = store.get(map_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Unknown map id: {map_id}")
        return payload

    return app


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_token(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized.startswith("Bearer "):
        return normalized
    return f"Bearer {normalized}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local HTTP bridge that exposes cached MapTool state to DMA."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument(
        "--port", type=int, default=5005, help="Port for the local bridge."
    )
    parser.add_argument(
        "--username",
        default=os.getenv("MAPTOOL_BRIDGE_USERNAME"),
        help="Optional bridge username for /auth/login.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("MAPTOOL_BRIDGE_PASSWORD"),
        help="Optional bridge password for /auth/login.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("MAPTOOL_BRIDGE_TOKEN"),
        help=(
            "Optional bearer token for protected routes. If omitted but username/password "
            "are provided, a random token is generated for the process."
        ),
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    token = args.token
    if token is None and args.username and args.password:
        token = secrets.token_urlsafe(24)

    app = create_bridge_app(
        username=args.username,
        password=args.password,
        bearer_token=token,
    )

    if token is not None:
        print(f"MapTool bridge token: {_normalize_token(token)}")
    else:
        print("MapTool bridge token: disabled")

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
