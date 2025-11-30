from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import httpx

from backend.config.settings import settings
from backend.models.maptool import (
    CampaignMapState,
    MapToolFogUpdate,
    MapToolLightUpdate,
    MapToolMap,
    MapToolToken,
    MapToolTokenUpdate,
    maptool_map_to_campaign,
)

logger = logging.getLogger(__name__)


class MapToolAdapter:
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        backoff_factor: float = 0.2,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.base_url = (base_url or settings.maptool_base_url).rstrip("/")
        self.username = username or settings.maptool_username
        self.password = password or settings.maptool_password
        self.timeout = timeout or settings.maptool_timeout_seconds
        self.max_retries = max_retries or settings.maptool_max_retries
        self.backoff_factor = backoff_factor
        self._transport = transport
        self.session_token: Optional[str] = None

    def _auth_headers(self, auth_header: Optional[str] = None) -> dict:
        headers = {"Accept": "application/json"}
        token = auth_header or self.session_token
        if token:
            headers["Authorization"] = token
        return headers

    async def authenticate(self, auth_header: Optional[str] = None) -> str:
        if auth_header:
            self.session_token = auth_header
            return auth_header
        if not self.username or not self.password:
            raise ValueError("MapTool credentials are required for authentication")

        payload = {"username": self.username, "password": self.password}
        response = await self._request_with_retries(
            "POST", "/auth/login", json=payload, headers={"Accept": "application/json"}
        )
        data = response.json()
        token = data.get("token") or data.get("session")
        if not token:
            raise RuntimeError("MapTool authentication response missing token")
        self.session_token = token if str(token).startswith("Bearer") else f"Bearer {token}"
        logger.debug("Authenticated to MapTool, token cached")
        return self.session_token

    async def fetch_map(
        self, map_id: str, auth_header: Optional[str] = None, attempts: Optional[int] = None
    ) -> MapToolMap:
        response = await self._request_with_retries(
            "GET", f"/maps/{map_id}", headers=self._auth_headers(auth_header), attempts=attempts
        )
        return MapToolMap.model_validate(response.json())

    async def create_token(
        self, map_id: str, token: MapToolToken, auth_header: Optional[str] = None
    ) -> MapToolToken:
        response = await self._request_with_retries(
            "POST",
            f"/maps/{map_id}/tokens",
            json=token.model_dump(exclude_none=True),
            headers=self._auth_headers(auth_header),
        )
        return MapToolToken.model_validate(response.json())

    async def update_token(
        self, map_id: str, token_update: MapToolTokenUpdate, auth_header: Optional[str] = None
    ) -> MapToolToken:
        response = await self._request_with_retries(
            "PATCH",
            f"/maps/{map_id}/tokens/{token_update.token_id}",
            json=token_update.to_payload(),
            headers=self._auth_headers(auth_header),
        )
        return MapToolToken.model_validate(response.json())

    async def delete_token(self, map_id: str, token_id: str, auth_header: Optional[str] = None) -> bool:
        response = await self._request_with_retries(
            "DELETE", f"/maps/{map_id}/tokens/{token_id}", headers=self._auth_headers(auth_header)
        )
        return response.status_code == 204

    async def update_fog(self, map_id: str, fog: MapToolFogUpdate, auth_header: Optional[str] = None) -> dict:
        response = await self._request_with_retries(
            "PATCH",
            f"/maps/{map_id}/fog",
            json=fog.model_dump(exclude_none=True),
            headers=self._auth_headers(auth_header),
        )
        return response.json()

    async def update_light(
        self, map_id: str, light: MapToolLightUpdate, auth_header: Optional[str] = None
    ) -> dict:
        response = await self._request_with_retries(
            "PATCH",
            f"/maps/{map_id}/light",
            json=light.model_dump(exclude_none=True),
            headers=self._auth_headers(auth_header),
        )
        return response.json()

    async def pull_map_state(
        self, map_id: str, auth_header: Optional[str] = None, retries: Optional[int] = None
    ) -> CampaignMapState:
        await self.ensure_auth(auth_header)
        map_payload = await self.fetch_map(
            map_id, auth_header=self.session_token, attempts=retries
        )
        return maptool_map_to_campaign(map_payload)

    async def push_token_updates(
        self,
        map_id: str,
        updates: List[MapToolTokenUpdate],
        auth_header: Optional[str] = None,
        retries: Optional[int] = None,
    ) -> List[MapToolToken]:
        await self.ensure_auth(auth_header)
        results: List[MapToolToken] = []
        for update in updates:
            response = await self._request_with_retries(
                "PATCH",
                f"/maps/{map_id}/tokens/{update.token_id}",
                json=update.to_payload(),
                headers=self._auth_headers(self.session_token),
                attempts=retries,
            )
            results.append(MapToolToken.model_validate(response.json()))
        return results

    async def ensure_auth(self, auth_header: Optional[str]) -> str:
        if auth_header:
            self.session_token = auth_header
            return auth_header
        if self.session_token:
            return self.session_token
        return await self.authenticate()

    async def _request_with_retries(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict] = None,
        headers: Optional[dict] = None,
        attempts: Optional[int] = None,
    ) -> httpx.Response:
        total_attempts = attempts or self.max_retries
        last_error: Optional[Exception] = None
        for attempt in range(1, total_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.request(method, path, json=json, headers=headers)
                if response.status_code >= 500:
                    response.raise_for_status()
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:  # pragma: no cover - exercised in tests
                last_error = exc
                logger.warning(
                    "MapTool request %s %s failed on attempt %s/%s: %s",
                    method,
                    path,
                    attempt,
                    total_attempts,
                    exc,
                )
                if attempt == total_attempts:
                    break
                await asyncio.sleep(self.backoff_factor * attempt)
        assert last_error is not None
        raise last_error


maptool_adapter = MapToolAdapter()
