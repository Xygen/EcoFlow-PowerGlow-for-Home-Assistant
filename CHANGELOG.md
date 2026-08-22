# Changelog

## 0.1.13

- Adds a localized `running` binary sensor for the verified PowerGlow run-state
  values: 0 is not running and 1 is running. Missing or unknown values make the
  entity unavailable instead of guessing a state.
- Keeps the numeric run-state sensor as a raw diagnostic entity, disabled by
  default for new entity-registry entries.

## 0.1.12

- Decodes the EcoFlow-provided PV, battery, and grid shares from fields 4, 5,
  and 6 of the same serial-scoped `212/33` report as measured heating power.
- Treats omitted protobuf source fields as 0 W and rejects an implausible
  source sum above heating power plus a 2 W rounding tolerance.

## 0.1.11

- Keeps the authoritative 30-second HTTP poll independent from frequent MQTT
  push updates. This restores PV, grid, and battery source-power updates while
  retaining the roughly five-second measured heating-power updates from MQTT.

## 0.1.10

- Corrects the fast heating-power decoder from the parent flow report `241/33`
  to the serial-scoped PowerGlow report `212/33` based on live 100 W and 0 W
  captures from version 0.1.9.
- Treats a matching `212/33` report without its default-valued power fields as
  an explicit 0 W update.

## 0.1.9

- Decodes the fast binary PowerGlow accessory-flow report (`241/33`) and
  updates measured heating power directly from MQTT, including explicit 0 W
  when protobuf omits its default-valued power fields.
- Decodes verified operating mode, run state, water temperature, tank volume,
  self-check, run flag, and error code fields from report `212/8`.
- Removes the stale two-second HTTP refresh and the continuous ten-second
  binary-frame fallback polling introduced in 0.1.8.
- Keeps a confirmed Home Assistant target value for up to 45 seconds so an
  older cloud snapshot cannot make the control jump back while EcoFlow catches
  up. The protection clears as soon as an authoritative report matches.

## 0.1.8

- Keeps Enhanced-mode PowerOcean energy-stream reports active with the
  hardware-proven 20-second `EnergyStreamSwitch` cadence.
- Requests `latestQuotas` every 30 seconds and applies matching PowerGlow JSON
  MQTT reports immediately instead of waiting for the HTTP poll.
- Uses PowerGlow-specific binary MQTT frames as rate-limited change hints,
  reducing the fallback wait to at most 10 seconds without globally increasing
  HTTP traffic.
- Starts a debounced authoritative HTTP refresh two seconds after a Home
  Assistant command.

## 0.1.7

- Prevents false command errors when EcoFlow applies a SET but its MQTT
  `set_reply` is lost.
- Uses the matching broker echo as a provisional fallback confirmation; a real
  `set_reply` remains preferred and HTTP polling remains authoritative.
- Still raises an error when neither a matching reply nor broker echo arrives.

## 0.1.6

- Changes target-power control from 100 W to 1 W increments.
- Uses a numeric input box for precise 0–9000 W entry, including low average
  targets that the PowerGlow realizes through time-proportional operation.

## 0.1.5

- Updates target values immediately after a matching EcoFlow MQTT SET reply,
  instead of waiting up to 30 seconds for the next HTTP poll.
- Adds a translated operating-mode select for Off, Solar mode, and Manual mode.
- Combines `runStat` and `mode` reports for the displayed operating status.
- Ignores late Paho callbacks during Home Assistant event-loop shutdown.

## 0.1.4

- Corrects the PowerGlow parameter-command destination from 212 to 96 based on
  a captured official iOS-app target-temperature SET frame and its SET reply.

## 0.1.3

- Passively captures redacted official-app SET frames and SET replies in
  integration diagnostics so the real PowerGlow write protocol can be verified.
- Records redacted Home Assistant command frames for direct comparison.

## 0.1.2

- Initializes the Paho client before connecting the MQTT write channel.
- Keeps HTTP telemetry available when the optional MQTT control channel fails,
  and retries that channel during later coordinator updates.

## 0.1.1

- Fixes accounts where the provider device-list endpoint is empty by using the
  normal EcoFlow app device list as a PowerOcean discovery fallback.
- Rejects incomplete discovery instead of creating permanently unavailable
  entities without a PowerOcean parent.

## 0.1.0

- Initial standalone Home Assistant integration.
- Discovers direct `HF33` PowerGlow devices and maps them to their PowerOcean parent.
- Provides PowerGlow telemetry through the EcoFlow consumer detail API.
- Adds target temperature and target power controls using narrowly scoped optional fields in the reconstructed `HeatingRodParamSet` protobuf command.
