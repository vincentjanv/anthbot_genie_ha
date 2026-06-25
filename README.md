# Anthbot HA Home Assistant Integration

![Anthbot Genie logo](logo.png)

## Disclaimer

This is an unofficial, community project and is not affiliated with, endorsed by, sponsored by, or approved by Anthbot.

All product names, logos, and trademarks are property of their respective owners. See [NOTICE.md](NOTICE.md).

This repository contains a custom integration for Anthbot robotic mowers:

- `custom_components/anthbot_genie`

## What it does now

This integration supports the Anthbot Genie 600, Genie 1000, M5, and M9 models. It auto-discovers all account-bound mowers via:

- `GET https://api.anthbot.com/api/v1/device/bind/list`

For each mower, it auto-fetches its cloud region/IoT endpoint via:

- `GET https://api.anthbot.com/api/v1/device/v2/region?sn=<sn>`

Then it polls the AWS IoT device shadow endpoint per discovered `sn` using automatic SigV4 signing:

- `GET https://<iot_endpoint>/things/<sn>/shadow?name=property`

It also fetches the mower area definition file from Anthbot cloud to discover:

- manual zones
- auto-zones

From `state.reported` it exposes:

- `lawn_mower.<device>` mapping `robot_sta.value` or `mode.value` to the standard Home Assistant `mowing` / `paused` / `docked` / `returning` activities, with `start_mowing`, `pause`, and `dock` actions
- `sensor.<device>_battery_level` from `elec.value` (M5/M9) or `elec` (Genie 600)
- `sensor.<device>_mower_status` from `robot_sta.value` or `mode.value`
- `sensor.<device>_cutting_height` from `param_set.cutter_height` / `mow_remote.cutter_height`
- `sensor.<device>_voice_volume` from `volume`
- `sensor.<device>_mowing_time` from `mowing_time_new.value` (session elapsed time)
- `sensor.<device>_mowing_area` from `mowing_area_new.value` (session mowed area)
- `sensor.<device>_mowing_time_total` from `mowing_time.value` (M5/M9 total time)
- `sensor.<device>_mowing_area_total` from `mowing_area.value` (M5/M9 total area)
- `sensor.<device>_custom_mowing_direction` from `param_set.mow_head`
- `sensor.<device>_custom_mowing_direction_enabled` from `param_set.enable_adaptive_head` (mapped to enabled/disabled)
- `sensor.<device>_mode` from `mode.value` (M5/M9)
- `sensor.<device>_error_code` from `err_code`
- `sensor.<device>_ip_address` from `sta_ip_addr`
- `sensor.<device>_wifi_ssid` from `sta_ssid`
- `sensor.<device>_rtk_state` from `rtk_state`
- `sensor.<device>_map_area` from `map_area`
- `sensor.<device>_mapping_task_state` from `map_sta.value`
- `sensor.<device>_zones` for discovered manual zones
- `sensor.<device>_auto_zones` for discovered auto-zones
- `sensor.<device>_position` from `pose` (live position; `x`/`y` attributes are in millimetres, in the same coordinate frame as zone `vertexs`, plus a `heading` attribute in degrees)
- `binary_sensor.<device>_connection` from `online`
- `binary_sensor.<device>_charging` from `robot_sta.value` or `mode.value`
- `switch.<device>_custom_mowing_direction_enabled` to toggle `param_set.enable_adaptive_head`
- `switch.<device>_rain_perception_enabled` to toggle `rain_switch`
- `switch.<device>_base_station_mowing_enabled` to toggle Anthbot's nest/base-station mowing mode
- `switch.<device>_base_station_visual_inspection_enabled` to toggle visual inspection for that mode
- `number.<device>_base_station_mow_count_setting` for 1x/2x nest mowing passes
- `number.<device>_base_station_mow_height_setting` for nest mowing height
- `select.<device>_base_station_visual_inspection_level` for nest visual inspection level (`Low`, `Medium`, `High`)

Entity attributes also include:

- `serial_number`
- `mower_status`
- `robot_status_raw`
- `mode` (M5/M9)
- `error_code` (M5/M9)
- `cutting_height`
- `mowing_time`
- `mowing_area`
- `mowing_time_total` (M5/M9)
- `mowing_area_total` (M5/M9)
- `voice_volume`
- `custom_mowing_direction`
- `custom_mowing_direction_enabled`
- `base_station_mowing_enabled`
- `base_station_mow_count`
- `base_station_mow_height`
- `base_station_visual_inspection_enabled`
- `base_station_visual_inspection_level`
- `base_station_mowing_active`
- `rain_continue_time`
- `voice_status`
- `ip_address` (M5/M9)
- `wifi_ssid` (M5/M9)
- `rtk_state` (M5/M9)
- `map_area` (M5/M9)
- `mapping_task_state` (M5/M9)`

The dedicated zone sensors also expose:

- manual zone ids, names, and active zone ids
- auto-zone ids and names

For easier control, the integration also creates per-zone buttons on the mower device:

- `Zone <name>` for each manual zone
- `Auto zone <name>` for each auto-zone

Each of those button entities exposes the zone-specific metadata as attributes and can be pressed directly from the device page.

## Setup

### HACS

1. Open HACS -> Integrations -> top-right menu -> `Custom repositories`.
2. Add repository URL: `https://github.com/vincentjanv/anthbot_genie_ha`
3. Category: `Integration`
4. Install `Anthbot HA` from HACS and restart Home Assistant.
5. Add integration: `Settings -> Devices & Services -> Add Integration -> Anthbot HA`.

### Manual

1. Copy `custom_components/anthbot_genie` into your Home Assistant config directory.
2. Restart Home Assistant.
3. Add integration: `Settings -> Devices & Services -> Add Integration -> Anthbot HA`.
4. In config, enter Anthbot `username`/`password`, select your country (area code dropdown).
5. The rest (device discovery, region, IoT endpoint, shadow auth signing) is automatic.

## Home Assistant Brands

Starting with Home Assistant 2026.3, custom integrations can ship their own brand images directly. This integration includes local brand assets at:

- `custom_components/anthbot_genie/brand/icon.png`
- `custom_components/anthbot_genie/brand/logo.png`

Home Assistant serves these through its local brands API, so the Anthbot icon will be displayed in your Home Assistant integration list and device pages. No separate `home-assistant/brands` PR is required for HACS/custom installs.

## Home Assistant Brands

Starting with Home Assistant 2026.3, custom integrations can ship their own brand images directly. This integration includes local brand assets at:

- `custom_components/anthbot_genie/brand/icon.png`
- `custom_components/anthbot_genie/brand/logo.png`

Home Assistant serves these through its local brands API, so no separate `home-assistant/brands` PR is required for HACS/custom installs.

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

- Lawn mower: `lawn_mower.<device>` with the standard `start_mowing`, `pause`, and `dock` actions
- Buttons: `Start full mow`, `Stop mow`, `Return to dock`
- Buttons: one `Zone <name>` per manual zone
- Buttons: one `Auto zone <name>` per auto-zone
- Number controls (sliders): `Mow height`, `Voice volume`
- Number control (slider): `Custom mowing direction` (0..180)
- Number control (slider): `Rain continue time` (0..8 hours)
- Number controls (sliders): `Base station mow count` (1..2), `Base station mow height` (30..70 mm)
- Select: `Base station visual inspection level` (`Low`, `Medium`, `High`)
- Switch: `Custom mowing direction enabled`
- Switch: `Rain perception`
- Switches: `Base station mowing`, `Base station visual inspection`
- Sensors: `Zones`, `Auto zones` with zone ids/names summaries

You can trigger/test commands directly from those entities in the device page.

## Community contributions

Recent community contributions include:

- Anthbot M5/M9 model support by `@riza-aslan`.
- Standard Home Assistant `lawn_mower` entity support by Denis Kot / `DenisBY` in PR #12.
- Polish translations by Tomasz Terlecki / `tazmanska` in PR #9.

## Buy me some new blades!

Feel free to make a contribution at https://buymeacoffee.com/vincentjanv if this integration helped you in any way...

## Issues, discussions, ideas..?

If you have any issues with this integration, feel free to open an issue in this repository. For discussions on improving this repository, please join the global Anthbot community on Facebook at https://www.facebook.com/groups/anthbotglobalcommunity of if you're living in the Nordics, at https://www.facebook.com/groups/anthbotnordicscommunity .
