"""Writable PowerGlow target values."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowerGlowCoordinator
from .entity import PowerGlowEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PowerGlowCoordinator = entry.runtime_data
    async_add_entities(
        entity
        for serial in coordinator.devices
        for entity in (
            PowerGlowTargetNumber(coordinator, serial, "target_temperature_c"),
            PowerGlowTargetNumber(coordinator, serial, "target_power_w"),
        )
    )


class PowerGlowTargetNumber(PowerGlowEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: PowerGlowCoordinator, serial: str, key: str) -> None:
        super().__init__(coordinator, serial, key)
        if key == "target_temperature_c":
            self._attr_translation_key = "target_temperature"
            self._attr_native_min_value = 10
            self._attr_native_max_value = 80
            self._attr_native_step = 1
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        else:
            self._attr_translation_key = "target_power"
            self._attr_native_min_value = 0
            self._attr_native_max_value = 9000
            self._attr_native_step = 1
            self._attr_mode = NumberMode.BOX
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_device_class = NumberDeviceClass.POWER

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(self.serial, {}).get(self.key)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_parameter(self.serial, self.key, round(value))
