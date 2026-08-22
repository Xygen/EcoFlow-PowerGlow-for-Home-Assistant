"""Constants for EcoFlow PowerGlow."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfVolume

DOMAIN = "ecoflow_powerglow"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

IOT_API_BASE = "https://api-e.ecoflow.com"
MQTT_HOST = "mqtt-e.ecoflow.com"
MQTT_PORT_TCP = 8883
MQTT_PORT_WSS = 8084
MQTT_WSS_PATH = "/mqtt"
DEFAULT_MQTT_KEEPALIVE = 60
DEFAULT_WSS_KEEPALIVE = 60
DEFAULT_RECONNECT_DELAY = 2
DEFAULT_MAX_RECONNECT_DELAY = 300
DEFAULT_MAX_RECONNECT_ATTEMPTS = 10
DEFAULT_COUNTER_RESET_INTERVAL = 300
UPDATE_INTERVAL_SECONDS = 30
ENERGY_STREAM_KEEPALIVE_SECONDS = 20
LATEST_QUOTAS_INTERVAL_SECONDS = 30
CONFIRMED_WRITE_GRACE_SECONDS = 45

POWERGLOW_PREFIX = "HF33"
@dataclass(frozen=True, kw_only=True)
class PowerGlowSensorDescription(SensorEntityDescription):
    diagnostic: bool = False


SENSORS = (
    PowerGlowSensorDescription(
        key="heating_power_w",
        translation_key="heating_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PowerGlowSensorDescription(
        key="water_temperature_c",
        translation_key="water_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    PowerGlowSensorDescription(
        key="power_from_pv_w",
        translation_key="power_from_pv",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PowerGlowSensorDescription(
        key="power_from_grid_w",
        translation_key="power_from_grid",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PowerGlowSensorDescription(
        key="power_from_battery_w",
        translation_key="power_from_battery",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PowerGlowSensorDescription(
        key="water_tank_volume_l",
        translation_key="water_tank_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PowerGlowSensorDescription(
        key="self_check_pct",
        translation_key="self_check",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        diagnostic=True,
    ),
    PowerGlowSensorDescription(
        key="run_flag_raw", translation_key="run_flag", diagnostic=True
    ),
    PowerGlowSensorDescription(
        key="run_state_raw",
        translation_key="run_state",
        diagnostic=True,
        entity_registry_enabled_default=False,
    ),
    PowerGlowSensorDescription(
        key="error_code_raw", translation_key="error_code", diagnostic=True
    ),
)
