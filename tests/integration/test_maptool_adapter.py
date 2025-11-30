from typing import Dict

import asyncio
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.maptool import router as maptool_router
from backend.models.maptool import MapToolMap, MapToolToken, MapToolTokenUpdate
from backend.services.maptool_adapter import MapToolAdapter


def test_pull_map_state_uses_authorization_header():
    calls: Dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["authorization"] = request.headers.get("Authorization")
        if request.url.path == "/maps/cavern":
            payload = {
                "id": "cavern",
                "name": "Crystal Cavern",
                "tokens": [
                    {"id": "rogue", "name": "Rogue", "x": 2, "y": 4, "notes": "Ready", "layer": "objects"}
                ],
                "fog_state": "clear",
                "light_state": "dim",
            }
            return httpx.Response(200, json=payload)
        raise AssertionError(f"Unexpected path {request.url.path}")

    adapter = MapToolAdapter(base_url="http://maptool.example", transport=httpx.MockTransport(handler))
    result = asyncio.run(adapter.pull_map_state("cavern", auth_header="Bearer session-token"))

    assert calls["authorization"] == "Bearer session-token"
    assert result.map_id == "cavern"
    assert result.tokens[0].label == "Rogue"
    assert result.fog_state == "clear"


def test_push_token_updates_retries_on_failure():
    attempts: Dict[str, int] = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"token": "session"})
        if request.url.path.startswith("/maps/dungeon/tokens/"):
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(500, json={"error": "server flake"})
            payload = {
                "id": "fighter",
                "name": "Fighter",
                "x": 9,
                "y": 12,
                "notes": "Moved",
                "gm_notes": None,
                "layer": "objects",
            }
            return httpx.Response(200, json=payload)
        raise AssertionError(f"Unexpected path {request.url.path}")

    adapter = MapToolAdapter(
        base_url="http://maptool.example",
        username="dm",
        password="secret",
        transport=httpx.MockTransport(handler),
        backoff_factor=0,
    )

    updates = [MapToolTokenUpdate(token_id="fighter", x=9, y=12, note="Moved")]
    results = asyncio.run(adapter.push_token_updates("dungeon", updates))

    assert attempts["count"] == 2
    assert results[0].x == 9
    assert results[0].notes == "Moved"


def test_maptool_routes_wire_adapter(monkeypatch):
    calls: Dict[str, int] = {"pull": 0, "push": 0}

    async def fake_pull(map_id: str, auth_header=None, retries=None):
        calls["pull"] += 1
        return MapToolMap(
            id=map_id,
            name="Demo",
            tokens=[MapToolToken(id="alpha", name="Alpha", x=1, y=2)],
        ).to_campaign_map()

    async def fake_push(map_id: str, updates, auth_header=None, retries=None):
        calls["push"] += 1
        return [MapToolToken(id="alpha", name="Alpha", x=updates[0].x or 0, y=updates[0].y or 0)]

    monkeypatch.setattr("backend.api.routes.maptool.maptool_adapter.pull_map_state", fake_pull)
    monkeypatch.setattr("backend.api.routes.maptool.maptool_adapter.push_token_updates", fake_push)

    app = FastAPI()
    app.include_router(maptool_router, prefix="/api/maptool")
    client = TestClient(app)

    pull_response = client.post("/api/maptool/pull", json={"map_id": "demo"}, headers={"Authorization": "token"})
    push_response = client.post(
        "/api/maptool/push",
        json={"map_id": "demo", "updates": [{"token_id": "alpha", "x": 3, "y": 5}]},
        headers={"Authorization": "token"},
    )

    assert pull_response.status_code == 200
    assert push_response.status_code == 200
    assert calls["pull"] == 1
    assert calls["push"] == 1
    assert pull_response.json()["map_id"] == "demo"
    assert push_response.json()["updated"][0]["x"] == 3
