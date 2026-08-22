"""Binary sensor platform for EcoFlow PowerGlow."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowerGlowCoordinator
from .entity import PowerGlowEntity
from .parser import powerglow_is_running


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PowerGlow binary sensors."""
    coordinator: PowerGlowCoordinator = entry.runtime_data
    async_add_entities(
        PowerGlowRunningBinarySensor(coordinator, serial)
        for serial in coordinator.devices
    )


class PowerGlowRunningBinarySensor(PowerGlowEntity, BinarySensorEntity):
    """Expose the reported PowerGlow run state as a binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "run_state"

    def __init__(self, coordinator: PowerGlowCoordinator, serial: str) -> None:
        """Initialize the run-state binary sensor."""
        super().__init__(coordinator, serial, "running")

    @property
    def available(self) -> bool:
        """Return whether EcoFlow reported a known run state."""
        return (
            self.coordinator.last_update_success
            and powerglow_is_running(
                self.coordinator.data.get(self.serial, {})
            )
            is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true while EcoFlow reports the PowerGlow as enabled."""
        return powerglow_is_running(
            self.coordinator.data.get(self.serial, {})
        )
