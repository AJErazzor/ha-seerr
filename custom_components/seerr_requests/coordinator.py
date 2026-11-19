"""Keeps the list of pending Seerr requests up to date."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SeerrAlreadyHandledError, SeerrClient, SeerrError
from .const import (
    CONF_EXTERNAL_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_REQUEST_ACTIONED,
)
from .models import REQUEST_APPROVED, REQUEST_PENDING, build_request

_LOGGER = logging.getLogger(__name__)


class AlreadyHandled(HomeAssistantError):
    """Seerr says the request was already approved or declined."""


@dataclass
class SeerrData:
    """What one refresh returns."""

    pending: list[dict[str, Any]] = field(default_factory=list)
    processing: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)
    version: str | None = None


class SeerrCoordinator(DataUpdateCoordinator[SeerrData]):
    """Polls Seerr (and refreshes early when the webhook fires)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SeerrClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.external_url: str = (
            entry.data.get(CONF_EXTERNAL_URL) or entry.data[CONF_URL]
        ).rstrip("/")
        self._details_cache: dict[tuple[str, int], dict[str, Any]] = {}
        self._version: str | None = None

    async def _async_update_data(self) -> SeerrData:
        try:
            if self._version is None:
                self._version = (await self.client.status()).get("version")
            counts = await self.client.request_count()
            raw_pending = await self.client.pending_requests()
            raw_processing = await self.client.processing_requests()
        except SeerrError as err:
            raise UpdateFailed(str(err)) from err

        seen: set[tuple[str, int]] = set()
        pending = await self._build_all(raw_pending, REQUEST_PENDING, seen)
        processing = await self._build_all(raw_processing, REQUEST_APPROVED, seen)

        # Forget artwork/details for requests that are no longer listed.
        for key in list(self._details_cache):
            if key not in seen:
                del self._details_cache[key]

        return SeerrData(
            pending=pending, processing=processing, counts=counts, version=self._version
        )

    async def _build_all(
        self, raws: list[dict[str, Any]], status: int, seen: set[tuple[str, int]]
    ) -> list[dict[str, Any]]:
        built: list[dict[str, Any]] = []
        for raw in raws:
            if raw.get("status") != status:
                continue
            media = raw.get("media") or {}
            media_type = "tv" if (raw.get("type") or media.get("mediaType")) == "tv" else "movie"
            tmdb_id = media.get("tmdbId")
            details: dict[str, Any] = {}
            if tmdb_id:
                key = (media_type, int(tmdb_id))
                seen.add(key)
                if key not in self._details_cache:
                    try:
                        self._details_cache[key] = await self.client.media_details(
                            media_type, int(tmdb_id)
                        )
                    except SeerrError as err:
                        _LOGGER.debug("Could not load details for %s: %s", key, err)
                        self._details_cache[key] = {}
                details = self._details_cache[key]
            built.append(build_request(raw, details, self.external_url))
        return built

    def find(self, request_id: int) -> dict[str, Any] | None:
        """A pending or approved request by id, if we have it."""
        if not self.data:
            return None
        return next(
            (r for r in [*self.data.pending, *self.data.processing] if r["id"] == request_id),
            None,
        )

    async def async_act(self, request_id: int, action: str, source: str = "service") -> str:
        """Approve or decline a request. Returns the title for messages."""
        request = self.find(request_id)
        title = request["title"] if request else f"request #{request_id}"
        try:
            if action == "approve":
                await self.client.approve(request_id)
            elif action == "decline":
                await self.client.decline(request_id)
            else:
                raise HomeAssistantError(f"Unknown action {action}")
        except SeerrAlreadyHandledError as err:
            # Someone already dealt with it (in Seerr, or auto-approve). Refresh so it drops off.
            await self.async_request_refresh()
            raise AlreadyHandled(f"{title} was already approved or declined in Seerr") from err
        except SeerrError as err:
            raise HomeAssistantError(f"Couldn't {action} {title}: {err}") from err

        # Drop it from the list straight away so the card updates instantly.
        if self.data:
            self.async_set_updated_data(
                replace(
                    self.data,
                    pending=[r for r in self.data.pending if r["id"] != request_id],
                )
            )
        self.hass.bus.async_fire(
            EVENT_REQUEST_ACTIONED,
            {"request_id": request_id, "action": action, "title": title, "source": source},
        )
        await self.async_request_refresh()
        return title
