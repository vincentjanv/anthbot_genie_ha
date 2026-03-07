"""Config flow for Anthbot Genie."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AnthbotCloudApiClient, AnthbotGenieApiError
from .const import (
    CONF_API_HOST,
    CONF_AREA_CODE,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    COUNTRY_AREA_CODES,
    DEFAULT_API_HOST,
    DEFAULT_AREA_CODE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class AnthbotGenieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Anthbot Genie."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="already_configured")

            session = async_get_clientsession(self.hass)
            cloud_client = AnthbotCloudApiClient(
                session=session,
                host=user_input[CONF_API_HOST],
            )
            try:
                await cloud_client.async_login(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    area_code=user_input[CONF_AREA_CODE],
                )
                devices = await cloud_client.async_get_bound_devices()
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input,
                    )
            except AnthbotGenieApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        country_options = [
            selector.SelectOptionDict(value=code, label=label)
            for label, code in COUNTRY_AREA_CODES
        ]
        non_empty_string = vol.All(str, vol.Strip, vol.Length(min=1))

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): non_empty_string,
                vol.Required(CONF_USERNAME): non_empty_string,
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_API_HOST, default=DEFAULT_API_HOST): non_empty_string,
                vol.Required(CONF_AREA_CODE, default=DEFAULT_AREA_CODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=country_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
