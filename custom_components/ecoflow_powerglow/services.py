"""Opt-in device-level PowerGlow shutdown request.

Transport outcomes are not guarantees about physical heating power.
This module never runs on its own; the integration registers its action.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN

SERVICE_REQUEST_SHUTDOWN = "request_shutdown"
SHUTDOWN_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})


async def _request_shutdown(hass: HomeAssistant, call: ServiceCall) -> dict[str, str | bool]:
    """Send OFF unconditionally to one loaded, registered PowerGlow device."""
    device = dr.async_get(hass).async_get(call.data["device_id"])
    if device is None:
        raise ServiceValidationError("PowerGlow device not found")

    serials = {value for domain, value in device.identifiers if domain == DOMAIN}
    matches = []
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            continue
        coordinator = entry.runtime_data
        matches.extend(
            (coordinator, serial)
            for serial in serials
            if serial in coordinator.devices
        )
    if len(matches) != 1:
        raise ServiceValidationError(
            "Expected exactly one loaded PowerGlow for the requested device"
        )

    coordinator, serial = matches[0]
    try:
        evidence = await coordinator.async_request_shutdown(serial)
    except (ConnectionError, TimeoutError) as exc:
        raise HomeAssistantError(
            "PowerGlow OFF request could not be confirmed over MQTT"
        ) from exc

    return {
        "transport_evidence": evidence,
        "physical_shutdown_verified": False,
    }


def async_register_services(hass: HomeAssistant) -> None:
    """Register before config entries load so HA can validate automations."""
    async def handle(call: ServiceCall) -> dict[str, str | bool]:
        return await _request_shutdown(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REQUEST_SHUTDOWN,
        handle,
        schema=SHUTDOWN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
