"""Sensor platform for EcoFlow PowerGlow."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SENSORS, PowerGlowSensorDescription
from .coordinator import PowerGlowCoordinator
from .entity import PowerGlowEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PowerGlowCoordinator = entry.runtime_data
    async_add_entities(
        PowerGlowSensor(coordinator, serial, description)
        for serial in coordinator.devices
        for description in SENSORS
    )


class PowerGlowSensor(PowerGlowEntity, SensorEntity):
    def __init__(self, coordinator: PowerGlowCoordinator, serial: str, description: PowerGlowSensorDescription) -> None:
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description
        if description.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        return self.coordinator.data.get(self.serial, {}).get(self.key)
