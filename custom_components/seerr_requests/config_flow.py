"""Set-up and options screens."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError

from .api import SeerrAuthError, SeerrClient, SeerrConnectionError, SeerrError
from .const import (
    CONF_EXTERNAL_URL,
    CONF_NOTIFY_SERVICES,
    CONF_SCAN_INTERVAL,
    CONF_WEBHOOK_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Optional(CONF_EXTERNAL_URL, default=""): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


def _clean_url(url: str) -> str:
    return url.strip().rstrip("/")


class SeerrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a Seerr server."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _clean_url(user_input[CONF_URL])
            external = _clean_url(user_input.get(CONF_EXTERNAL_URL) or "")
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)

            if not url.startswith(("http://", "https://")):
                errors[CONF_URL] = "invalid_url"
            elif external and not external.startswith(("http://", "https://")):
                errors[CONF_EXTERNAL_URL] = "invalid_url"
            else:
                self._async_abort_entries_match({CONF_URL: url})
                client = SeerrClient(
                    async_get_clientsession(self.hass, verify_ssl),
                    url,
                    user_input[CONF_API_KEY],
                    verify_ssl,
                )
                try:
                    await client.status()
                    await client.request_count()  # proves the API key works
                except SeerrAuthError:
                    errors["base"] = "invalid_auth"
                except SeerrConnectionError:
                    errors["base"] = "cannot_connect"
                except SeerrError:
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title="Seerr",
                        data={
                            CONF_URL: url,
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_EXTERNAL_URL: external,
                            CONF_VERIFY_SSL: verify_ssl,
                            CONF_WEBHOOK_ID: webhook.async_generate_id(),
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SeerrOptionsFlow()


class SeerrOptionsFlow(OptionsFlow):
    """Refresh interval and which phones get notifications."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)

        phones = sorted(
            f"notify.{name}"
            for name in self.hass.services.async_services_for_domain("notify")
            if name.startswith("mobile_app_")
        )
        current = self.config_entry.options

        try:
            webhook_url = webhook.async_generate_url(
                self.hass, self.config_entry.data[CONF_WEBHOOK_ID], prefer_external=False
            )
        except NoURLAvailableError:
            webhook_url = "(set your Home Assistant URL under Settings → System → Network first)"

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_SERVICES, default=current.get(CONF_NOTIFY_SERVICES, [])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=phones,
                        multiple=True,
                        custom_value=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=3600,
                        step=5,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"webhook_url": webhook_url},
        )
