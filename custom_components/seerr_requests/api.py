"""Small async client for the Seerr (Jellyseerr / Overseerr) v1 API."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

REQUEST_TIMEOUT = 15


class SeerrError(Exception):
    """Base error talking to Seerr."""


class SeerrAuthError(SeerrError):
    """The API key was rejected."""


class SeerrConnectionError(SeerrError):
    """Seerr could not be reached."""


class SeerrClient:
    """Talks to one Seerr server."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        verify_ssl: bool = True,
    ) -> None:
        self._session = session
        self._base = url.rstrip("/")
        self._api_key = api_key
        self._ssl = bool(verify_ssl)

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        url = f"{self._base}/api/v1{path}"
        headers = {"X-Api-Key": self._api_key, "Accept": "application/json"}
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.request(
                    method, url, params=params, headers=headers, ssl=self._ssl
                ) as resp:
                    if resp.status in (401, 403):
                        raise SeerrAuthError("Seerr rejected the API key")
                    if resp.status >= 400:
                        text = await resp.text()
                        raise SeerrError(f"Seerr returned HTTP {resp.status}: {text[:200]}")
                    text = await resp.text()
                    if not text.strip():
                        return None
                    try:
                        return json.loads(text)
                    except ValueError as err:
                        raise SeerrError(
                            f"Seerr sent a non-JSON reply (is the URL right?): {text[:120]}"
                        ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SeerrConnectionError(f"Cannot reach Seerr at {self._base}: {err}") from err

    async def status(self) -> dict[str, Any]:
        """Server status (includes the version)."""
        return await self._request("GET", "/status") or {}

    async def request_count(self) -> dict[str, Any]:
        """Request totals by status. Needs a valid API key."""
        return await self._request("GET", "/request/count") or {}

    async def requests(self, status_filter: str, take: int = 100) -> list[dict[str, Any]]:
        """Requests matching a Seerr filter ("pending", "processing", ...), newest first."""
        data = await self._request(
            "GET",
            "/request",
            params={"take": take, "skip": 0, "filter": status_filter, "sort": "added"},
        )
        return (data or {}).get("results", [])

    async def pending_requests(self, take: int = 100) -> list[dict[str, Any]]:
        """Requests waiting for approval."""
        return await self.requests("pending", take)

    async def processing_requests(self, take: int = 100) -> list[dict[str, Any]]:
        """Approved requests that aren't fully available yet."""
        return await self.requests("processing", take)

    async def media_details(self, media_type: str, tmdb_id: int) -> dict[str, Any]:
        """Movie or TV details (title, overview, artwork, external ids)."""
        kind = "tv" if media_type == "tv" else "movie"
        return await self._request("GET", f"/{kind}/{tmdb_id}") or {}

    async def approve(self, request_id: int) -> None:
        """Approve a request."""
        await self._request("POST", f"/request/{int(request_id)}/approve")

    async def decline(self, request_id: int) -> None:
        """Decline a request."""
        await self._request("POST", f"/request/{int(request_id)}/decline")
