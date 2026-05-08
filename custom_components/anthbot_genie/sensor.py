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
    """Return raw robot status from shadow payload."""
    robot_sta = data.get("robot_sta")
    if not isinstance(robot_sta, dict):
        robot_sta = data.get("mode")
        if not isinstance(robot_sta, dict):
            return None
    value = robot_sta.get("value")
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
        value_fn=lambda data: (
            data.get("volume")
            if isinstance(data.get("volume"), int)
            else (
                data.get("device_config").get("volume")
                if isinstance(data.get("device_config"), dict)
                else None
            )
        ),
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
            else (
                data.get("mowing_time", {}).get('value')
                if isinstance(data.get("mowing_time"), dict)
                else None
            )
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
            else (
                data.get("mowing_area", {}).get('value')
                if isinstance(data.get("mowing_area"), dict)
                else None
            )
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot sensors from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotSensorEntity(coordinator, description)
        for coordinator in coordinators
        for description in SENSORS
    )


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
        return attributes
