# Anthbot Genie Home Assistant Integration (Phase 1)

![Anthbot Genie logo](logo.png)

## Disclaimer

This is an unofficial, community project and is not affiliated with, endorsed by, sponsored by, or approved by Anthbot.

All product names, logos, and trademarks are property of their respective owners. See [NOTICE.md](NOTICE.md).

This repository now contains a first custom integration at:

- `custom_components/anthbot_genie`

## What it does now

It auto-discovers all account-bound mowers via:

- `GET https://api.anthbot.com/api/v1/device/bind/list`

For each mower, it auto-fetches its cloud region/IoT endpoint via:

- `GET https://api.anthbot.com/api/v1/device/v2/region?sn=<sn>`

Then it polls the AWS IoT device shadow endpoint per discovered `sn` using automatic SigV4 signing:

- `GET https://<iot_endpoint>/things/<sn>/shadow?name=property`

From `state.reported` it exposes:

- `sensor.<device>_battery_level` from `elec`
- `sensor.<device>_cutting_height` from `mow_remote.cutter_height`
- `sensor.<device>_voice_volume` from `volume`
- `sensor.<device>_mowing_time` from `mowing_time_new.value` (session elapsed time)
- `sensor.<device>_mow_count` from `param_set.mow_count`
- `sensor.<device>_custom_mowing_direction` from `param_set.mow_head`
- `sensor.<device>_custom_mowing_direction_enabled` from `param_set.enable_adaptive_head` (mapped to enabled/disabled)
- `binary_sensor.<device>_connection` from `online`
- `binary_sensor.<device>_charging` from `robot_sta.value`
- `switch.<device>_custom_mowing_direction_enabled` to toggle `param_set.enable_adaptive_head`

Entity attributes also include:

- `serial_number`
- `cutting_height`
- `mowing_time`
- `mow_count`
- `voice_volume`
- `custom_mowing_direction`
- `custom_mowing_direction_enabled`
- `voice_status`

## Setup

### HACS

1. Open HACS -> Integrations -> top-right menu -> `Custom repositories`.
2. Add repository URL: `https://github.com/vincentverbist/anthbot_ha`
3. Category: `Integration`
4. Install `Anthbot Genie` from HACS and restart Home Assistant.
5. Add integration: `Settings -> Devices & Services -> Add Integration -> Anthbot Genie`.

### Manual

1. Copy `custom_components/anthbot_genie` into your Home Assistant config directory.
2. Restart Home Assistant.
3. Add integration: `Settings -> Devices & Services -> Add Integration -> Anthbot Genie`.
4. In config, enter Anthbot `username`/`password`, select your country (area code dropdown).
5. The rest (device discovery, region, IoT endpoint, shadow auth signing) is automatic.

## Home Assistant Brands (integration tile icon)

To show the icon/logo in Home Assistant's integration tile, a PR must be submitted to `home-assistant/brands`.

Prepared assets are included in this repository at:

- `brands/custom_integrations/anthbot_genie/icon.png`
- `brands/custom_integrations/anthbot_genie/logo.png`

## Actions (services)

The integration provides these Home Assistant services:

- `anthbot_genie.start_full_mow`
- `anthbot_genie.stop_mow`
- `anthbot_genie.return_to_dock`
- `anthbot_genie.set_mow_height` (`mow_height`: 30..70 in 5 mm steps)
- `anthbot_genie.set_voice_volume` (`voice_volume`: 0..100)
- `anthbot_genie.set_custom_mowing_direction` (`mow_direction`: 0..180, `enable_custom_direction`: true/false)

You can target by Anthbot entities (`target.entity_id`) and/or by `serial_number`.

## Device page controls

The integration also creates control entities on each mower device page:

- Buttons: `Start full mow`, `Stop mow`, `Return to dock`
- Number controls (sliders): `Mow height`, `Voice volume`
- Number control (slider): `Custom mowing direction` (0..180)
- Switch: `Custom mowing direction enabled`

You can trigger/test commands directly from those entities in the device page.
