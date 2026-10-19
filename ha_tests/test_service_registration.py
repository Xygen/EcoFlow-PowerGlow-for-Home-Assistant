"""RF-002: run service registration against a real, isolated HA Core instance.

No config entry, EcoFlow cloud or device is connected. A fake handler tests
Home Assistant's service schema and response handling; the real handler is
used only for the unknown-device error case.
"""
from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.ecoflow_powerglow import async_setup
from custom_components.ecoflow_powerglow.const import DOMAIN
from custom_components.ecoflow_powerglow import services as shutdown_services

pytestmark = pytest.mark.asyncio


async def test_shutdown_action_registered_before_any_device_load(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
):
    observed = []

    async def fake_device_handler(_hass, call):
        observed.append(call.data["device_id"])
        return {
            "transport_evidence": "broker_echo_only",
            "physical_shutdown_verified": False,
        }

    monkeypatch.setattr(shutdown_services, "_request_shutdown", fake_device_handler)
    assert await async_setup(hass, {})
    assert hass.services.has_service(DOMAIN, "request_shutdown")

    result = await hass.services.async_call(
        DOMAIN, "request_shutdown",
        {"device_id": "test-device-id"},
        blocking=True, return_response=True,
    )
    assert observed == ["test-device-id"]
    assert result == {
        "transport_evidence": "broker_echo_only",
        "physical_shutdown_verified": False,
    }


async def test_unknown_powerglow_device_fails_closed_in_real_ha(
    hass: HomeAssistant
):
    assert await async_setup(hass, {})
    with pytest.raises(ServiceValidationError, match="not found"):
        await hass.services.async_call(
            DOMAIN, "request_shutdown",
            {"device_id": "nonexistent-device"},
            blocking=True, return_response=True,
        )
