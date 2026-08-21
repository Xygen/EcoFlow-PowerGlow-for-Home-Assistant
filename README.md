# EcoFlow PowerGlow for Home Assistant

Standalone custom integration for an EcoFlow PowerGlow smart immersion heater.
It discovers a direct `HF33` PowerGlow device in an EcoFlow account, associates
it with the PowerOcean that carries its consumer reports, and exposes both
telemetry and controls.

## Entities

- Sensors: heating power, water temperature, PV/grid/battery power,
  tank volume, self-check, run state, run flag, and error code.
- Numbers: target temperature (10–80 °C) and target power (0–9000 W in 1 W
  increments).
- Select: operating mode with Off, Solar mode, and Manual mode.

Each control writes only the optional protobuf field needed for that change.
The operating-mode select combines the reported run state with the mode enum:
run state 0 is Off, while an enabled heater uses mode 0 for Solar and mode 1 for
Manual. When an off heater is enabled, the requested mode is configured before
the run-state command is sent.

## Installation

1. Copy `custom_components/ecoflow_powerglow` to the same path in the Home
   Assistant configuration directory, or add the repository as a HACS custom
   repository of type Integration.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and choose
   **EcoFlow PowerGlow**.
4. Sign in with the EcoFlow app account that owns the PowerGlow.

## Protocol status and safety

This is an unofficial cloud integration. Reads use EcoFlow's consumer detail
endpoint. Writes use the app MQTT topic of the associated PowerOcean and the
reconstructed protobuf message `HeatingRodParamSet` (`cmd_func=212`,
`cmd_id=99`, system destination `96`). The temperature, run-state, and
Solar-mode message shapes and replies were captured from the official iOS app.
Home Assistant target-temperature writes have also been confirmed end-to-end
against PowerGlow hardware.

Test with conservative values while watching the EcoFlow app and the physical
heater. Home Assistant normally changes immediately after a matching EcoFlow
MQTT SET reply. If that reply is lost but the broker echoes the exact command
and sequence, the value is accepted provisionally instead of showing a false
error; the 30-second HTTP poll remains the authoritative synchronization path.
Temperature is constrained to the published 10–80 °C range and power to
0–9000 W.

Power targets below the heater's apparent minimum continuous output are kept as
valid average targets. The PowerGlow may realize them by alternating roughly
92–100 W operation with 0 W periods, so automations should evaluate averaged
measured power instead of reacting to every instantaneous transition.

Cloud credentials are stored by Home Assistant in the config entry. This project
is not affiliated with EcoFlow. Cloud endpoints and protocol details may change.

## Attribution

The authentication, MQTT transport, and existing read-path research are derived
from `shuette42/ecoflow-energy-ha` and `Xygen/ecoflow-energy-ha-test` under the
MIT license. PowerGlow protobuf field definitions were cross-checked against
`foxthefox/ioBroker.ecoflow-mqtt`.
