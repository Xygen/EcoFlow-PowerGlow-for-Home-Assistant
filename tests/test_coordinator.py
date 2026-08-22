"""Coordinator scheduling regression tests without a Home Assistant install."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from typing import Any


class _FakeDataUpdateCoordinator:
    @classmethod
    def __class_getitem__(cls, _item: Any) -> type[_FakeDataUpdateCoordinator]:
        return cls

    def __init__(
        self,
        hass: Any,
        _logger: Any,
        *,
        config_entry: Any,
        name: str,
        update_interval: Any,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.name = name
        self.update_interval = update_interval
        self.data: dict[str, Any] = {}
        self.refreshes = 0

    async def async_refresh(self) -> None:
        self.refreshes += 1

    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        self.data = data


class _UpdateFailed(Exception):
    pass


class _FakeApiClient:
    def __init__(self, _session: Any, _email: str, _password: str) -> None:
        pass


homeassistant = ModuleType("homeassistant")
config_entries = ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = object
core = ModuleType("homeassistant.core")
core.HomeAssistant = object
helpers = ModuleType("homeassistant.helpers")
aiohttp_client = ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = lambda _hass: object()
update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
update_coordinator.DataUpdateCoordinator = _FakeDataUpdateCoordinator
update_coordinator.UpdateFailed = _UpdateFailed

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.config_entries"] = config_entries
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

api = ModuleType("custom_components.ecoflow_powerglow.api")
api.PowerGlowApiClient = _FakeApiClient
cloud_mqtt = ModuleType("custom_components.ecoflow_powerglow.ecoflow.cloud_mqtt")
cloud_mqtt.EcoFlowMQTTClient = object
const = ModuleType("custom_components.ecoflow_powerglow.const")
const.CONF_EMAIL = "email"
const.CONF_PASSWORD = "password"
const.CONFIRMED_WRITE_GRACE_SECONDS = 45
const.DOMAIN = "ecoflow_powerglow"
const.ENERGY_STREAM_KEEPALIVE_SECONDS = 20
const.LATEST_QUOTAS_INTERVAL_SECONDS = 30
const.UPDATE_INTERVAL_SECONDS = 30
sys.modules["custom_components.ecoflow_powerglow.api"] = api
sys.modules["custom_components.ecoflow_powerglow.ecoflow.cloud_mqtt"] = cloud_mqtt
sys.modules["custom_components.ecoflow_powerglow.const"] = const

from custom_components.ecoflow_powerglow.coordinator import (  # noqa: E402
    PowerGlowCoordinator,
)

CONF_EMAIL = const.CONF_EMAIL
CONF_PASSWORD = const.CONF_PASSWORD
UPDATE_INTERVAL_SECONDS = const.UPDATE_INTERVAL_SECONDS


class _FakeHandle:
    def __init__(self, delay: float, callback: Any) -> None:
        self.delay = delay
        self.callback = callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class _FakeLoop:
    def __init__(self) -> None:
        self.handles: list[_FakeHandle] = []

    def call_later(self, delay: float, callback: Any) -> _FakeHandle:
        handle = _FakeHandle(delay, callback)
        self.handles.append(handle)
        return handle


class _FakeHass:
    def __init__(self) -> None:
        self.loop = _FakeLoop()
        self.is_stopping = False
        self.tasks: list[Any] = []

    def async_create_task(self, coroutine: Any) -> None:
        self.tasks.append(coroutine)


def test_mqtt_pushes_cannot_postpone_authoritative_http_poll() -> None:
    hass = _FakeHass()
    entry = SimpleNamespace(
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "secret"},
        pref_disable_polling=False,
    )
    coordinator = PowerGlowCoordinator(hass, entry)

    assert coordinator.update_interval is None
    coordinator.start_polling()
    first_handle = coordinator._http_poll_handle
    assert first_handle is not None
    assert first_handle.delay == UPDATE_INTERVAL_SECONDS

    for value in range(20):
        coordinator.async_set_updated_data({"HF33": {"heating_power_w": value}})
    assert coordinator._http_poll_handle is first_handle

    first_handle.callback()
    assert coordinator._http_poll_handle is None
    asyncio.run(hass.tasks.pop())

    assert coordinator.refreshes == 1
    assert coordinator._http_poll_handle is not None
    assert coordinator._http_poll_handle is not first_handle
