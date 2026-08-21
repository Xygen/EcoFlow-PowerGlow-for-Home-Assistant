"""PowerGlow operating-mode status and control."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PowerGlowCoordinator
from .entity import PowerGlowEntity
from .parser import powerglow_operating_mode

OPTION_OFF = "off"
OPTION_SOLAR = "solar"
OPTION_MANUAL = "manual"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PowerGlowCoordinator = entry.runtime_data
    async_add_entities(
        PowerGlowOperatingModeSelect(coordinator, serial)
        for serial in coordinator.devices
    )


class PowerGlowOperatingModeSelect(PowerGlowEntity, SelectEntity):
    """Expose Off, Solar mode, and Manual mode as one select entity."""

    _attr_translation_key = "operating_mode"
    _attr_options = [OPTION_OFF, OPTION_SOLAR, OPTION_MANUAL]

    def __init__(self, coordinator: PowerGlowCoordinator, serial: str) -> None:
        super().__init__(coordinator, serial, "operating_mode")

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and powerglow_operating_mode(
                self.coordinator.data.get(self.serial, {})
            )
            is not None
        )

    @property
    def current_option(self) -> str | None:
        return powerglow_operating_mode(
            self.coordinator.data.get(self.serial, {})
        )

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data.get(self.serial, {})
        if option == OPTION_OFF:
            if int(data.get("run_state_raw", -1)) != 0:
                await self.coordinator.async_set_parameter(
                    self.serial, "run_state_raw", 0
                )
            return

        requested_mode = {OPTION_SOLAR: 0, OPTION_MANUAL: 1}.get(option)
        if requested_mode is None:
            raise ValueError(f"Unsupported PowerGlow operating mode: {option}")

        # Configure the requested mode before enabling the heater. This avoids
        # briefly starting an off device in its previously selected mode.
        if int(data.get("mode_raw", -1)) != requested_mode:
            await self.coordinator.async_set_parameter(
                self.serial, "mode_raw", requested_mode
            )
        if int(data.get("run_state_raw", -1)) != 1:
            await self.coordinator.async_set_parameter(
                self.serial, "run_state_raw", 1
            )
