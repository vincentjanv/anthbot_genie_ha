# Anthbot Genie Home Assistant Integration

![Anthbot Genie logo](logo.png)

## Disclaimer

This is an unofficial, community project and is not affiliated with, endorsed by, sponsored by, or approved by Anthbot.

All product names, logos, and trademarks are property of their respective owners. See [NOTICE.md](NOTICE.md).

This repository now contains a first custom integration at:

- `custom_components/anthbot_genie`

## What it does now

This integration has been tested with a Anthbot Genie 600, but most sensors/properties should work on other robots as well. It auto-discovers all account-bound mowers via:

- `GET https://api.anthbot.com/api/v1/device/bind/list`

For each mower, it auto-fetches its cloud region/IoT endpoint via:

- `GET https://api.anthbot.com/api/v1/device/v2/region?sn=<sn>`

Then it polls the AWS IoT device shadow endpoint per discovered `sn` using automatic SigV4 signing:

- `GET https://<iot_endpoint>/things/<sn>/shadow?name=property`

It also fetches the mower area definition file from Anthbot cloud to discover:

- manual zones
- auto-zones

It also generates per-device map camera entities in Home Assistant using:

- manual zone geometry from the area file
- auto-zone points from the area file
- live/session path overlays from `curpath` and the cloud path export

From `state.reported` it exposes:

- `sensor.<device>_battery_level` from `elec`
- `sensor.<device>_mower_status` from `robot_sta.value`
- `sensor.<device>_cutting_height` from `param_set.cutter_height` / `mow_remote.cutter_height`
- `sensor.<device>_voice_volume` from `volume`
- `sensor.<device>_mowing_time` from `mowing_time_new.value` (session elapsed time)
- `sensor.<device>_mowing_area` from `mowing_area_new.value` (session mowed area)
- `sensor.<device>_custom_mowing_direction` from `param_set.mow_head`
- `sensor.<device>_custom_mowing_direction_enabled` from `param_set.enable_adaptive_head` (mapped to enabled/disabled)
- `sensor.<device>_zones` for discovered manual zones
- `sensor.<device>_auto_zones` for discovered auto-zones
- `binary_sensor.<device>_connection` from `online`
- `binary_sensor.<device>_charging` from `robot_sta.value`
- `switch.<device>_custom_mowing_direction_enabled` to toggle `param_set.enable_adaptive_head`
- `switch.<device>_rain_perception_enabled` to toggle `rain_switch`

Entity attributes also include:

- `serial_number`
- `mower_status`
- `robot_status_raw`
- `cutting_height`
- `mowing_time`
- `mowing_area`
- `voice_volume`
- `custom_mowing_direction`
- `custom_mowing_direction_enabled`
- `rain_continue_time`
- `voice_status`

The dedicated zone sensors also expose:

- manual zone ids, names, and active zone ids
- auto-zone ids and names

For easier control, the integration also creates per-zone buttons on the mower device:

- `Zone <name>` for each manual zone
- `Auto zone <name>` for each auto-zone

Each of those button entities exposes the zone-specific metadata as attributes and can be pressed directly from the device page.

The integration also creates three generated map camera entities per mower:

- `camera.<device>_session_map`
- `camera.<device>_zones_map`
- `camera.<device>_auto_zones_map`

These are currently coordinate-based rendered maps. They do not yet use the app's binary base-map layer.

## Setup

### HACS

1. Open HACS -> Integrations -> top-right menu -> `Custom repositories`.
2. Add repository URL: `https://github.com/vincentjanv/anthbot_genie_ha`
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
- `anthbot_genie.start_zone_mow` (`zones`: id, name, comma-separated string, or YAML list)
- `anthbot_genie.start_auto_zone_mow` (`auto_zones`: id, name, comma-separated string, or YAML list)

You can target by Anthbot entities (`target.entity_id`) and/or by `serial_number`.

Examples:

```yaml
service: anthbot_genie.start_zone_mow
target:
  entity_id: sensor.cleaver_zones
data:
  zones: [100]
```

```yaml
service: anthbot_genie.start_auto_zone_mow
target:
  entity_id: sensor.cleaver_auto_zones
data:
  auto_zones: "1, Front area"
```

## Device page controls

The integration also creates control entities on each mower device page:

- Buttons: `Start full mow`, `Stop mow`, `Return to dock`
- Buttons: one `Zone <name>` per manual zone
- Buttons: one `Auto zone <name>` per auto-zone
- Cameras: `Session map`, `Zones map`, `Auto-zones map`
- Number controls (sliders): `Mow height`, `Voice volume`
- Number control (slider): `Custom mowing direction` (0..180)
- Number control (slider): `Rain continue time` (0..8 hours)
- Switch: `Custom mowing direction enabled`
- Switch: `Rain perception`
- Sensors: `Zones`, `Auto zones` with zone ids/names summaries

You can trigger/test commands directly from those entities in the device page.

## Buy me some new blades!
Feel free to make a contribution at https://buymeacoffee.com/vincentjanv if this integration helped you in any way...

## Issues, discussions, ideas..?

If you have any issues with this integration, feel free to open an issue in this repository. For discussions on improving this repository, please join the global Anthbot community on Facebook at https://www.facebook.com/groups/anthbotglobalcommunity of if you're living in the Nordics, at https://www.facebook.com/groups/anthbotnordicscommunity .
