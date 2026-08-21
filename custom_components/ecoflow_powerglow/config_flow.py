"""Config flow for EcoFlow PowerGlow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PowerGlowApiClient
from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN


class PowerGlowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PowerGlow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect EcoFlow app credentials and validate discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = PowerGlowApiClient(
                async_get_clientsession(self.hass),
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.async_login()
                devices = await client.async_discover_powerglows()
            except Exception:  # Home Assistant shows a stable localized error.
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(user_input[CONF_EMAIL].strip().lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="EcoFlow PowerGlow",
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL].strip(),
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

