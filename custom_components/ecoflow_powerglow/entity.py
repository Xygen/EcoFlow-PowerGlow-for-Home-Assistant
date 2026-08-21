"""Base entity for EcoFlow PowerGlow."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PowerGlowCoordinator


class PowerGlowEntity(CoordinatorEntity[PowerGlowCoordinator]):
    """Base class bound to one discovered heating rod."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PowerGlowCoordinator, serial: str, key: str) -> None:
        super().__init__(coordinator)
        self.serial = serial
        self.key = key
        self._attr_unique_id = f"{serial}_{key}"
        item = coordinator.devices[serial]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="EcoFlow",
            model="PowerGlow",
            name=item.get("name") or "EcoFlow PowerGlow",
        )

    @property
    def available(self) -> bool:
        return super().available and self.key in self.coordinator.data.get(self.serial, {})

