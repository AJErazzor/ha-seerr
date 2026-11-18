"""Phone notifications with Approve / Decline buttons, and the new-request event."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import CONF_NOTIFY_SERVICES, DOMAIN, EVENT_NEW_REQUEST
from .coordinator import SeerrCoordinator
from .models import season_text

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
MOBILE_ACTION_EVENT = "mobile_app_notification_action"


def _tag(request_id: int) -> str:
    return f"seerr_request_{request_id}"


class SeerrNotifier:
    """Watches for new requests, sends notifications and handles button taps."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator: SeerrCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._services: list[str] = [
            s.removeprefix("notify.") for s in entry.options.get(CONF_NOTIFY_SERVICES, [])
        ]
        self._prefix = f"SEERR_{entry.entry_id[:8].upper()}_"
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._known: set[int] | None = None  # None = first run ever
        self._notified: set[int] = set()
        self._keep: set[int] = set()  # confirmations we must not clear
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []

    async def async_start(self) -> None:
        stored = await self._store.async_load()
        if stored is not None:
            self._known = set(stored.get("known", []))
            self._notified = set(stored.get("notified", []))
        self._unsubs.append(self.coordinator.async_add_listener(self._on_update))
        self._unsubs.append(self.hass.bus.async_listen(MOBILE_ACTION_EVENT, self._on_action))
        await self._process()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _on_update(self) -> None:
        self.hass.async_create_task(self._process())

    async def _process(self) -> None:
        async with self._lock:
            data = self.coordinator.data
            if data is None:
                return
            current = {r["id"]: r for r in data.pending}

            if self._known is None:
                # First time ever: don't spam notifications for an existing backlog.
                self._known = set(current)
                await self._save()
                return

            for request_id, request in current.items():
                if request_id in self._known:
                    continue
                self.hass.bus.async_fire(EVENT_NEW_REQUEST, dict(request))
                if self._services:
                    await self._send_request(request)
                    self._notified.add(request_id)

            # Requests handled elsewhere (Seerr UI, the card): clear their notification.
            gone = self._notified - set(current)
            for request_id in gone:
                if request_id in self._keep:
                    self._keep.discard(request_id)
                else:
                    await self._send_all(
                        {"message": "clear_notification", "data": {"tag": _tag(request_id)}}
                    )
            self._notified -= gone
            self._known = set(current)
            await self._save()

    async def _save(self) -> None:
        await self._store.async_save(
            {"known": sorted(self._known or []), "notified": sorted(self._notified)}
        )

    async def _send_all(self, payload: dict[str, Any]) -> None:
        for service in self._services:
            if not self.hass.services.has_service("notify", service):
                _LOGGER.warning("Notify service notify.%s not found", service)
                continue
            try:
                await self.hass.services.async_call("notify", service, payload, blocking=True)
            except HomeAssistantError as err:
                _LOGGER.warning("Sending to notify.%s failed: %s", service, err)

    async def _send_request(self, request: dict[str, Any]) -> None:
        request_id = request["id"]
        name = request["title"] + (f" ({request['year']})" if request.get("year") else "")
        extras = []
        if request["type"] == "tv" and request.get("seasons"):
            extras.append(season_text(request["seasons"]))
        if request.get("is4k"):
            extras.append("4K")
        message = f"{request['requested_by']} requested {name}"
        if extras:
            message += " · " + ", ".join(extras)

        data: dict[str, Any] = {
            "tag": _tag(request_id),
            "group": "seerr-requests",
            "actions": [
                {"action": f"{self._prefix}APPROVE_{request_id}", "title": "Approve"},
                {
                    "action": f"{self._prefix}DECLINE_{request_id}",
                    "title": "Decline",
                    "destructive": True,
                },
            ],
        }
        if request.get("poster"):
            data["image"] = request["poster"]
        if request.get("seerr_url"):
            data["url"] = request["seerr_url"]  # iOS
            data["clickAction"] = request["seerr_url"]  # Android

        kind = "TV" if request["type"] == "tv" else "movie"
        await self._send_all({"title": f"New {kind} request", "message": message, "data": data})

    async def _on_action(self, event: Event) -> None:
        action = str(event.data.get("action", ""))
        if not action.startswith(self._prefix):
            return
        verb, _, raw_id = action[len(self._prefix):].partition("_")
        try:
            request_id = int(raw_id)
        except ValueError:
            return
        if verb not in ("APPROVE", "DECLINE"):
            return

        self._keep.add(request_id)
        try:
            title = await self.coordinator.async_act(
                request_id, verb.lower(), source="notification"
            )
            message = f"✅ Approved: {title}" if verb == "APPROVE" else f"❌ Declined: {title}"
        except HomeAssistantError as err:
            self._keep.discard(request_id)
            message = str(err)
        await self._send_all(
            {"title": "Seerr", "message": message, "data": {"tag": _tag(request_id)}}
        )
