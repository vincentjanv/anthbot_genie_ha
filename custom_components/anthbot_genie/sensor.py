"""Sensor platform for Anthbot Genie."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfArea, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .mow_params import (
    custom_direction_enabled_from_state,
    nest_mowing_enabled_from_state,
    nest_visual_inspection_enabled_from_state,
    nest_visual_inspection_option_from_state,
    raw_int_value,
)
from .zones import active_manual_zone_ids, auto_zones, manual_zones


def _path_exists(data: dict[str, Any], *keys: str) -> bool:
    """Check if a nested path exists in the data dictionary."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return False
        if key not in current:
            return False
        current = current[key]
    return True


def _is_custom_mowing_direction_enabled(data: dict[str, Any]) -> bool:
    """Map raw enable_adaptive_head value to custom-direction state."""
    return custom_direction_enabled_from_state(data)


_ROBOT_STATUS_BY_CODE: tuple[str, ...] = (
    "idle",
    "pause",
    "charge",
    "sleep",
    "ota",
    "position",
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "mapping",
    "backtodock",
    "resume_point",
    "shutdown",
    "remotectrl",
    "factory",
    "sleep",
    "camera_cleaning",
    "gototarget",
    "bordermowing",
    "regionmowing",
    "nestmowing",
)

MOWER_STATUS_OPTIONS: list[str] = [
    "standby",
    "paused",
    "charging",
    "mowing",
    "returning_to_dock",
    "mapping",
    "positioning",
    "resuming",
    "sleeping",
    "ota_updating",
    "remote_control",
    "factory_mode",
    "camera_cleaning",
    "going_to_target",
    "shutdown",
    "unknown",
]


def _raw_robot_status(data: dict[str, Any]) -> str | None:
    """Return raw robot status from shadow payload.
    
    Supports both Genie 600 (robot_sta.value) and M5/M9 (mode.value) formats.
    """
    # Try Genie 600 format first: robot_sta.value
    robot_sta = data.get("robot_sta")
    if isinstance(robot_sta, dict):
        value = robot_sta.get("value")
        if isinstance(value, str):
            return value.lower()
        if isinstance(value, int):
            if 0 <= value < len(_ROBOT_STATUS_BY_CODE):
                return _ROBOT_STATUS_BY_CODE[value]
            return str(value)
    
    # Try M5/M9 format: mode.value (fallback for newer models)
    mode = data.get("mode")
    if isinstance(mode, dict):
        value = mode.get("value")
        if isinstance(value, str):
            return value.lower()
        if isinstance(value, int):
            if 0 <= value < len(_ROBOT_STATUS_BY_CODE):
                return _ROBOT_STATUS_BY_CODE[value]
            return str(value)
    
    return None


def _general_mower_status(data: dict[str, Any]) -> str:
    """Map raw robot status to a human-readable general status."""
    raw = _raw_robot_status(data)
    if raw is None:
        return "unknown"

    if raw in {
        "globalmowing",
        "zonemowing",
        "pointmowing",
        "bordermowing",
        "regionmowing",
        "nestmowing",
    }:
        return "mowing"
    if raw in {"charge", "charging", "charge_start"}:
        return "charging"
    if raw == "backtodock":
        return "returning_to_dock"
    if raw == "idle":
        return "standby"
    if raw == "pause":
        return "paused"
    if raw == "mapping":
        return "mapping"
    if raw == "position":
        return "positioning"
    if raw == "resume_point":
        return "resuming"
    if raw == "sleep":
        return "sleeping"
    if raw == "ota":
        return "ota_updating"
    if raw == "remotectrl":
        return "remote_control"
    if raw == "factory":
        return "factory_mode"
    if raw == "camera_cleaning":
        return "camera_cleaning"
    if raw == "gototarget":
        return "going_to_target"
    if raw == "shutdown":
        return "shutdown"
    return "unknown"


def _pose(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the live pose dict (x/y in millimetres, same frame as zone vertexs)."""
    pose = data.get("pose")
    return pose if isinstance(pose, dict) else None


def _position_summary(data: dict[str, Any]) -> str | None:
    """Return the live position as an 'x, y' string in millimetres."""
    pose = _pose(data)
    if pose is None:
        return None
    x = pose.get("x")
    y = pose.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return f"{x}, {y}"


def _heading_degrees(data: dict[str, Any]) -> float | None:
    """Return mower heading in degrees [0, 360) derived from pose.yaw."""
    pose = _pose(data)
    if pose is None:
        return None
    yaw = pose.get("yaw")
    if not isinstance(yaw, (int, float)):
        return None
    return round(yaw % 360, 1)


@dataclass(frozen=True, kw_only=True)
class AnthbotSensorDescription(SensorEntityDescription):
    """Describes an Anthbot sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[AnthbotSensorDescription, ...] = (
    AnthbotSensorDescription(
        key="mower_status",
        translation_key="mower_status",
        name="Mower status",
        device_class=SensorDeviceClass.ENUM,
        options=MOWER_STATUS_OPTIONS,
        value_fn=_general_mower_status,
    ),
    AnthbotSensorDescription(
        key="voice_volume",
        translation_key="voice_volume",
        name="Voice volume",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("volume"),
    ),
    AnthbotSensorDescription(
        key="cutting_height",
        translation_key="cutting_height",
        name="Cutting height",
        native_unit_of_measurement="mm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("param_set", {}).get("cutter_height")
            if isinstance(data.get("param_set"), dict)
            else (
                data.get("mow_remote", {}).get("cutter_height")
                if isinstance(data.get("mow_remote"), dict)
                else None
            )
        ),
    ),
    AnthbotSensorDescription(
        key="mowing_time",
        translation_key="mowing_time",
        name="Mowing time (session)",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("mowing_time_new", {}).get("value")
            if isinstance(data.get("mowing_time_new"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="mowing_area",
        translation_key="mowing_area",
        name="Mowing area (session)",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("mowing_area_new", {}).get("value")
            if isinstance(data.get("mowing_area_new"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="custom_mowing_direction",
        translation_key="custom_mowing_direction",
        name="Custom mowing direction",
        native_unit_of_measurement="deg",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("param_set", {}).get("mow_head")
            if isinstance(data.get("param_set"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="custom_mowing_direction_enabled",
        translation_key="custom_mowing_direction_enabled",
        name="Custom mowing direction enabled",
        device_class=SensorDeviceClass.ENUM,
        options=["enabled", "disabled"],
        value_fn=lambda data: (
            "enabled" if _is_custom_mowing_direction_enabled(data) else "disabled"
        ),
    ),
    AnthbotSensorDescription(
        key="zones",
        translation_key="zones",
        name="Zones",
        value_fn=lambda data: len(manual_zones(data)),
    ),
    AnthbotSensorDescription(
        key="auto_zones",
        translation_key="auto_zones",
        name="Auto zones",
        value_fn=lambda data: len(auto_zones(data)),
    ),
    AnthbotSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("elec", {}).get("value")
            if isinstance(data.get("elec"), dict)
            else data.get("elec")
        ),
    ),
    # M5-specific sensors with safe fallback for Genie 600 compatibility
    AnthbotSensorDescription(
        key="mode",
        translation_key="mode",
        name="Mode",
        value_fn=lambda data: (
            data.get("mode", {}).get("value")
            if isinstance(data.get("mode"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="error_code",
        translation_key="error_code",
        name="Error code",
        value_fn=lambda data: data.get("err_code"),
    ),
    AnthbotSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        name="IP address",
        value_fn=lambda data: data.get("sta_ip_addr"),
    ),
    AnthbotSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        name="WiFi SSID",
        value_fn=lambda data: data.get("sta_ssid"),
    ),
    AnthbotSensorDescription(
        key="mowing_area_total",
        translation_key="mowing_area_total",
        name="Mowing area (total)",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("mowing_area", {}).get("value")
            if isinstance(data.get("mowing_area"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="mowing_time_total",
        translation_key="mowing_time_total",
        name="Mowing time (total)",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            int(data.get("mowing_time", {}).get("value") / 60)
            if isinstance(data.get("mowing_time"), dict) and data.get("mowing_time", {}).get("value") is not None
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="rtk_state",
        translation_key="rtk_state",
        name="RTK state",
        value_fn=lambda data: (
            str(data.get("rtk_state")) if data.get("rtk_state") is not None else None
        ),
    ),
    AnthbotSensorDescription(
        key="map_area",
        translation_key="map_area",
        name="Map area",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("map_area"),
    ),
    AnthbotSensorDescription(
        key="mapping_task_state",
        translation_key="mapping_task_state",
        name="Mapping task state",
        value_fn=lambda data: (
            data.get("map_sta", {}).get("value")
            if isinstance(data.get("map_sta"), dict)
            else None
        ),
    ),
    # Additional M5/M9 sensors
    AnthbotSensorDescription(
        key="volume",
        translation_key="volume",
        name="Volume",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("device_config", {}).get("volume")
            if isinstance(data.get("device_config"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="sim_id",
        translation_key="sim_id",
        name="SIM ID",
        value_fn=lambda data: data.get("4g_ccid"),
    ),
    AnthbotSensorDescription(
        key="ota_status",
        translation_key="ota_status",
        name="OTA status",
        value_fn=lambda data: (
            data.get("ota_status", {}).get("ota_state")
            if isinstance(data.get("ota_status"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="ota_progress",
        translation_key="ota_progress",
        name="OTA progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("ota_status", {}).get("ota_progress")
            if isinstance(data.get("ota_status"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        name="Firmware version",
        value_fn=lambda data: (
            data.get("fw_version", {}).get("system_version")
            if isinstance(data.get("fw_version"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="mow_count",
        translation_key="mow_count",
        name="Mow count",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.get("param_set", {}).get("mow_count")
            if isinstance(data.get("param_set"), dict)
            else None
        ),
    ),
    AnthbotSensorDescription(
        key="position",
        translation_key="position",
        name="Position",
        icon="mdi:crosshairs-gps",
        value_fn=_position_summary,
    ),
    AnthbotSensorDescription(
        key="coverage_trail",
        translation_key="coverage_trail",
        name="Coverage trail",
        icon="mdi:map-marker-path",
        value_fn=lambda data: len(data.get("_coverage_trail") or []) or None,
    ),
)


def _sensor_path_for_description(description: AnthbotSensorDescription) -> list[str] | None:
    """Return the data path for a sensor description, if it has one."""
    # Map sensor keys to their data paths for conditional creation
    path_map: dict[str, list[str]] = {
        "volume": ["device_config", "volume"],
        "sim_id": ["4g_ccid"],
        "ota_status": ["ota_status", "ota_state"],
        "ota_progress": ["ota_status", "ota_progress"],
        "firmware_version": ["fw_version", "system_version"],
        "mow_count": ["param_set", "mow_count"],
        "position": ["pose", "x"],
        "coverage_trail": ["curpath"],
        "mode": ["mode", "value"],
        "error_code": ["err_code"],
        "ip_address": ["sta_ip_addr"],
        "wifi_ssid": ["sta_ssid"],
        "mowing_area_total": ["mowing_area", "value"],
        "mowing_time_total": ["mowing_time", "value"],
        "rtk_state": ["rtk_state"],
        "map_area": ["map_area"],
        "mapping_task_state": ["map_sta", "value"],
    }
    return path_map.get(description.key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot sensors from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    
    entities_to_add: list[AnthbotSensorEntity] = []
    for coordinator in coordinators:
        state = coordinator.reported_state
        for description in SENSORS:
            # Check if the data path exists for conditional sensor creation
            path = _sensor_path_for_description(description)
            if path is not None:
                if not _path_exists(state, *path):
                    continue
            entities_to_add.append(AnthbotSensorEntity(coordinator, description))
    
    async_add_entities(entities_to_add)


class AnthbotSensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SensorEntity
):
    """Anthbot sensor entity."""

    entity_description: AnthbotSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def native_value(self) -> Any:
        """Return current sensor value."""
        return self.entity_description.value_fn(self.coordinator.reported_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self.coordinator.reported_state
        cutting_height = (
            state.get("param_set", {}).get("cutter_height")
            if isinstance(state.get("param_set"), dict)
            else (
                state.get("mow_remote", {}).get("cutter_height")
                if isinstance(state.get("mow_remote"), dict)
                else None
            )
        )
        service_reported = (
            state.get("_service_reported")
            if isinstance(state.get("_service_reported"), dict)
            else None
        )
        mowing_time = (
            state.get("mowing_time_new", {}).get("value")
            if isinstance(state.get("mowing_time_new"), dict)
            else None
        )
        mowing_area = (
            state.get("mowing_area_new", {}).get("value")
            if isinstance(state.get("mowing_area_new"), dict)
            else None
        )
        custom_mowing_direction = (
            state.get("param_set", {}).get("mow_head")
            if isinstance(state.get("param_set"), dict)
            else None
        )
        custom_mowing_direction_enabled = (
            _is_custom_mowing_direction_enabled(state)
            if isinstance(state.get("param_set"), dict)
            else False
        )
        base_station_mowing_enabled = nest_mowing_enabled_from_state(state)
        base_station_mow_count = raw_int_value(state.get("nest_mow_count"))
        base_station_mow_height = raw_int_value(state.get("nest_cutter_height"))
        base_station_visual_inspection_enabled = (
            nest_visual_inspection_enabled_from_state(state)
        )
        base_station_visual_inspection_level = (
            nest_visual_inspection_option_from_state(state)
        )
        voice_volume = state.get("volume")
        voice_status = (
            state.get("voice_status")
            if isinstance(state.get("voice_status"), dict)
            else None
        )
        rain_continue_time = state.get("rain_continue_time")
        mower_status = _general_mower_status(state)
        robot_status_raw = _raw_robot_status(state)
        base_station_mowing_active = robot_status_raw == "nestmowing"
        attributes = {
            "serial_number": self.coordinator.client.serial_number,
            "mower_status": mower_status,
            "robot_status_raw": robot_status_raw,
            "cutting_height": cutting_height,
            "mowing_time": mowing_time,
            "mowing_area": mowing_area,
            "custom_mowing_direction": custom_mowing_direction,
            "custom_mowing_direction_enabled": custom_mowing_direction_enabled,
            "base_station_mowing_enabled": base_station_mowing_enabled,
            "base_station_mow_count": base_station_mow_count,
            "base_station_mow_height": base_station_mow_height,
            "base_station_visual_inspection_enabled": (
                base_station_visual_inspection_enabled
            ),
            "base_station_visual_inspection_level": base_station_visual_inspection_level,
            "base_station_mowing_active": base_station_mowing_active,
            "voice_volume": voice_volume,
            "voice_status": voice_status,
            "rain_continue_time": rain_continue_time,
            "last_service_command": (
                service_reported.get("cmd") if service_reported else None
            ),
            "last_service_command_generation": (
                service_reported.get("generation") if service_reported else None
            ),
            # M5-specific attributes
            "mode": (
                state.get("mode", {}).get("value")
                if isinstance(state.get("mode"), dict)
                else None
            ),
            "error_code": state.get("err_code"),
            "ip_address": state.get("sta_ip_addr"),
            "wifi_ssid": state.get("sta_ssid"),
            "rtk_state": state.get("rtk_state"),
            "map_area": state.get("map_area"),
            "mapping_task_state": (
                state.get("map_sta", {}).get("value")
                if isinstance(state.get("map_sta"), dict)
                else None
            ),
        }
        if self.entity_description.key == "zones":
            manual_zone_list = manual_zones(state)
            attributes["zone_ids"] = [
                zone_id
                for zone in manual_zone_list
                if isinstance((zone_id := zone.get("id")), int)
            ]
            attributes["zone_names"] = [
                zone_name
                for zone in manual_zone_list
                if isinstance((zone_name := zone.get("name")), str) and zone_name
            ]
            attributes["active_zone_ids"] = active_manual_zone_ids(state)
        if self.entity_description.key == "auto_zones":
            auto_zone_list = auto_zones(state)
            attributes["auto_zone_ids"] = [
                zone_id
                for zone in auto_zone_list
                if isinstance((zone_id := zone.get("id")), int)
            ]
            attributes["auto_zone_names"] = [
                zone_name
                for zone in auto_zone_list
                if isinstance((zone_name := zone.get("name")), str) and zone_name
            ]
        if self.entity_description.key == "position":
            pose = _pose(state) or {}
            attributes["x"] = pose.get("x")
            attributes["y"] = pose.get("y")
            attributes["heading"] = _heading_degrees(state)
            attributes["yaw_raw"] = pose.get("yaw")
        if self.entity_description.key == "coverage_trail":
            points = state.get("_coverage_trail") or []
            attributes["points"] = points
            attributes["point_count"] = len(points)
        return attributes
