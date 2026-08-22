# EcoFlow PowerGlow for Home Assistant

Monitor and control an EcoFlow PowerGlow immersion heater from Home Assistant.
The integration connects to the EcoFlow cloud with the same account as the
official app and discovers the PowerGlow automatically. You do not need to
enter its serial number.

## User guide

### What this integration provides

- Current heating power and water temperature
- EcoFlow-provided solar, battery, and grid shares of the heating power
- Water-tank volume and operating status
- A choice of **Off**, **Solar mode**, and **Manual mode**
- Target temperature control from 10 to 80 °C
- Target power control from 0 to 9000 W in 1 W steps

Changes made in Home Assistant are normally visible in the EcoFlow app within
a few seconds. The integration also keeps a slower cloud poll as a fallback.

### Before you install

This is an unofficial cloud integration. It requires an internet connection
and an EcoFlow app account that owns the PowerGlow.

The integration has so far been tested only with the **9 kW PowerGlow** whose
serial number starts with `HF33`. Smaller PowerGlow variants may use different
serial-number prefixes and have not yet been verified.

When first testing controls, use conservative values and watch both the
EcoFlow app and the physical heater.

### Installation with HACS

1. Open **HACS → Integrations** in Home Assistant.
2. Open the HACS menu and choose **Custom repositories**.
3. Add
   `https://github.com/Xygen/EcoFlow-PowerGlow-for-Home-Assistant` as an
   **Integration** repository.
4. Find **EcoFlow PowerGlow** in HACS and download it.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration** and choose
   **EcoFlow PowerGlow**.
7. Enter the email address and password used by the EcoFlow app.

The PowerGlow and its associated PowerOcean are discovered automatically. The
setup therefore does not ask for a serial number.

### Manual installation

1. Open the
   [latest release](https://github.com/Xygen/EcoFlow-PowerGlow-for-Home-Assistant/releases/latest).
2. Download the attached `ecoflow_powerglow-<version>.zip` file. Do not use
   GitHub's automatically generated source-code archive.
3. Extract the archive into the Home Assistant `/config` directory. The final
   file path must be
   `/config/custom_components/ecoflow_powerglow/manifest.json`.
4. Restart Home Assistant and add the integration as described above.

### Everyday use

| Control or reading | Purpose |
| --- | --- |
| Operating mode | Turns the heater off or selects Solar or Manual mode. |
| Target temperature | Sets the desired water temperature, primarily for Solar mode. |
| Target power | Sets the requested heating power for Manual mode in 1 W steps. |
| Heating power | Shows the power currently used by the heater. |
| Power from solar, battery, and grid | Shows the EcoFlow-provided contribution of each source to the current heating power. |
| Water temperature | Shows the reported tank temperature. |
| Operating status | Shows whether the PowerGlow is running or not running. |
| Water-tank volume | Shows the configured tank volume reported by EcoFlow. |

The **Operating mode** control is the normal place to turn the PowerGlow on or
off. The read-only **Operating status** confirms whether EcoFlow currently
reports it as running.

Very low target-power values are valid, but the heater appears to have a
minimum continuous output of roughly 92–100 W. It may achieve a lower average
by alternating between this output and 0 W. Automations should therefore use
an averaged measured power instead of reacting to every brief transition.

### If something does not work

- Make sure the PowerGlow is online and visible in the EcoFlow app.
- Confirm that the account entered in Home Assistant owns both the PowerGlow
  and its associated PowerOcean.
- After installing or updating the integration, restart Home Assistant.
- If all entities are unavailable, check the Home Assistant log for entries
  containing `ecoflow_powerglow`.
- When reporting a problem, include the integration version, the PowerGlow
  power variant, and only the first four characters of its serial number.

## Technical reference

The following sections retain the implementation and protocol details that
may be useful to contributors, reviewers, and developers of other EcoFlow
projects.

### Hardware discovery and compatibility

The integration discovers a direct `HF33` PowerGlow device in an EcoFlow
account and associates it with the PowerOcean that carries its consumer
reports. Automatic discovery currently recognizes `HF33` devices. Because
smaller PowerGlow variants may use other serial-number prefixes, compatibility
with those variants cannot yet be guaranteed.

### Entity model

- Sensors: heating power, water temperature, PV/grid/battery power,
  tank volume, and self-check.
- Binary sensor: operating status using Home Assistant's `running` device
  class.
- Diagnostic sensors: raw run state, run flag, and error code. The raw
  run-state sensor is disabled by default because the binary sensor is the
  preferred representation.
- Numbers: target temperature (10–80 °C) and target power (0–9000 W in 1 W
  increments).
- Select: operating mode with Off, Solar mode, and Manual mode.

The binary operating status maps verified run-state value 0 to `off` and 1 to
`on`. Missing or unknown values make the entity unavailable instead of
guessing a state.

Each control writes only the optional protobuf field needed for that change.
The operating-mode select combines the reported run state with the mode enum:
run state 0 is Off, while an enabled heater uses mode 0 for Solar and mode 1
for Manual. When an off heater is enabled, the requested mode is configured
before the run-state command is sent.

### Protocol status and safety

Reads combine EcoFlow Enhanced-mode MQTT updates with the consumer detail
endpoint as a 30-second authoritative fallback. The PowerOcean energy stream
is kept active every 20 seconds and `latestQuotas` is requested every 30
seconds. The fast binary heating-rod report (`212/33`) updates measured heating
power and its EcoFlow-provided PV, battery, and grid shares directly from MQTT,
normally within a few seconds. Its push updates cannot postpone the independent
30-second HTTP fallback.

The verified parts of parameter report `212/8` update operating mode, run
state, water temperature, tank volume, self-check, run flag, and error code.
Writes use the app MQTT topic of the associated PowerOcean and the reconstructed
protobuf message `HeatingRodParamSet` (`cmd_func=212`, `cmd_id=99`, system
destination `96`). The temperature, run-state, and Solar-mode message shapes
and replies were captured from the official iOS app. Home Assistant target-
temperature and target-power writes have been confirmed end-to-end against
PowerGlow hardware.

Home Assistant normally changes immediately after a matching EcoFlow MQTT SET
reply. If that reply is lost but the broker echoes the exact command and
sequence, the value is accepted provisionally instead of showing a false
error. A confirmed target remains visible while EcoFlow's slower cloud
snapshot catches up, instead of being overwritten temporarily by an older
value. The protection expires after 45 seconds and clears earlier as soon as
an authoritative report matches. Temperature is constrained to the published
10–80 °C range and power to 0–9000 W.

Cloud credentials are stored by Home Assistant in the config entry. This
project is not affiliated with EcoFlow. Cloud endpoints and protocol details
may change.

## Attribution

The authentication, MQTT transport, and existing read-path research are
derived from `shuette42/ecoflow-energy-ha` and
`Xygen/ecoflow-energy-ha-test` under the MIT license. PowerGlow protobuf field
definitions were cross-checked against `foxthefox/ioBroker.ecoflow-mqtt`.
