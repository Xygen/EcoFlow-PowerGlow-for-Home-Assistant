# Changelog

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

