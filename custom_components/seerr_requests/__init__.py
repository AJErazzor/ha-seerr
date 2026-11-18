"""Seerr Requests: see, approve and decline Seerr / Jellyseerr requests in Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from aiohttp import web
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import SeerrClient
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_REQUEST_ID,
    CARD_FILENAME,
    CARD_URL,
    CONF_WEBHOOK_ID,
    DOMAIN,
    SERVICE_APPROVE,
    SERVICE_DECLINE,
)
from .coordinator import SeerrCoordinator
from .notifications import SeerrNotifier

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REQUEST_ID): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


@dataclass
class SeerrRuntime:
    """Objects that live for as long as the config entry is loaded."""

    client: SeerrClient
    coordinator: SeerrCoordinator
    notifier: SeerrNotifier


type SeerrConfigEntry = ConfigEntry[SeerrRuntime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and register the approve/decline actions."""
    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=False)]
    )
    # The version (written by the release workflow) makes browsers fetch the new card after an update.
    version = (await async_get_integration(hass, DOMAIN)).version
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")

    async def handle_action(call: ServiceCall) -> None:
        entry = _resolve_entry(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await entry.runtime_data.coordinator.async_act(call.data[ATTR_REQUEST_ID], call.service)

    for service in (SERVICE_APPROVE, SERVICE_DECLINE):
        hass.services.async_register(DOMAIN, service, handle_action, schema=SERVICE_SCHEMA)
    return True


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> SeerrConfigEntry:
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED and (entry_id is None or e.entry_id == entry_id)
    ]
    if not entries:
        raise ServiceValidationError("No loaded Seerr Requests integration found")
    return entries[0]


async def async_setup_entry(hass: HomeAssistant, entry: SeerrConfigEntry) -> bool:
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)
    client = SeerrClient(
        async_get_clientsession(hass, verify_ssl),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        verify_ssl,
    )
    coordinator = SeerrCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    notifier = SeerrNotifier(hass, entry, coordinator)
    await notifier.async_start()
    entry.async_on_unload(notifier.async_stop)

    entry.runtime_data = SeerrRuntime(client=client, coordinator=coordinator, notifier=notifier)

    # Seerr's webhook just tells us "something changed" so we refresh immediately.
    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> None:
        _LOGGER.debug("Seerr webhook received, refreshing")
        await coordinator.async_request_refresh()

    webhook_id = entry.data[CONF_WEBHOOK_ID]
    webhook.async_register(
        hass,
        DOMAIN,
        "Seerr Requests",
        webhook_id,
        handle_webhook,
        local_only=True,
        allowed_methods=["POST"],
    )
    entry.async_on_unload(lambda: webhook.async_unregister(hass, webhook_id))
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_on_options(hass: HomeAssistant, entry: SeerrConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SeerrConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
