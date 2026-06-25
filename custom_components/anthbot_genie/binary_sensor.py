"""Binary sensor platform for Anthbot Genie."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
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


def _is_connected(data: dict[str, Any]) -> bool:
    online = data.get("online")
    if isinstance(online, bool):
        return online
    if isinstance(online, str):
        return online == "1"
    if isinstance(online, int):
        return online == 1
    return False


def _is_charging(data: dict[str, Any]) -> bool:
    """Check if mower is charging.
    
    Supports both Genie 600 (robot_sta.value) and M5/M9 (mode.value) formats.
    """
    # Try Genie 600 format first: robot_sta.value
    robot_sta = data.get("robot_sta")
    if isinstance(robot_sta, dict):
        value = robot_sta.get("value")
        if isinstance(value, str):
            return value.lower() in {"charge", "charging", "charge_start"}
    
    # Try M5/M9 format: mode.value (fallback for newer models)
    mode = data.get("mode")
    if isinstance(mode, dict):
        value = mode.get("value")
        if isinstance(value, str):
            return value.lower() in {"charge", "charging", "charge_start"}
    
    return False


def _is_custom_mowing_direction_enabled(data: dict[str, Any]) -> bool:
    return custom_direction_enabled_from_state(data)


def _is_rain_sensor_active(data: dict[str, Any]) -> bool:
    """Check if rain perception is active."""
    return data.get("rain_switch") in (1, "1", True, "true")


def _is_camera_active(data: dict[str, Any]) -> bool:
    """Check if camera is active."""
    return data.get("camera_switch") in (1, "1", True, "true")


def _is_anti_theft_active(data: dict[str, Any]) -> bool:
    """Check if anti-theft (anti-loss) protection is active."""
    return data.get("anti_loss_switch") in (1, "1", True, "true")


def _is_wifi_connected(data: dict[str, Any]) -> bool:
    """Check if WiFi is connected."""
    return data.get("wifi_state") in (1, "1", True, "true")


def _is_4g_connected(data: dict[str, Any]) -> bool:
    """Check if 4G is connected."""
    return data.get("4g_state") in (1, "1", True, "true")


def _is_adaptive_head_enabled(data: dict[str, Any]) -> bool:
    """Check if adaptive mowing head is enabled."""
    param_set = data.get("param_set")
    if isinstance(param_set, dict):
        value = param_set.get("enable_adaptive_head")
        return value in (1, "1", True, "true")
    return False


@dataclass(frozen=True, kw_only=True)
class AnthbotBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an Anthbot binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[AnthbotBinarySensorDescription, ...] = (
    AnthbotBinarySensorDescription(
        key="connection",
        translation_key="connection",
        name="Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_is_connected,
    ),
    AnthbotBinarySensorDescription(
        key="charging",
        translation_key="charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_is_charging,
    ),
    # M5/M9 specific binary sensors
    AnthbotBinarySensorDescription(
        key="rain_sensor",
        translation_key="rain_sensor",
        name="Rain sensor",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=_is_rain_sensor_active,
    ),
    AnthbotBinarySensorDescription(
        key="camera",
        translation_key="camera",
        name="Camera",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_is_camera_active,
    ),
    AnthbotBinarySensorDescription(
        key="anti_theft",
        translation_key="anti_theft",
        name="Anti-theft",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=_is_anti_theft_active,
    ),
    AnthbotBinarySensorDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        name="WiFi connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_is_wifi_connected,
    ),
    AnthbotBinarySensorDescription(
        key="mobile_connected",
        translation_key="mobile_connected",
        name="Mobile connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_is_4g_connected,
    ),
    AnthbotBinarySensorDescription(
        key="adaptive_head_enabled",
        translation_key="adaptive_head_enabled",
        name="Adaptive head enabled",
        value_fn=_is_adaptive_head_enabled,
    ),
)


def _binary_sensor_path_for_description(description: AnthbotBinarySensorDescription) -> list[str] | None:
    """Return the data path for a binary sensor description, if it has one."""
    # Map binary sensor keys to their data paths for conditional creation
    path_map: dict[str, list[str]] = {
        "rain_sensor": ["rain_switch"],
        "camera": ["camera_switch"],
        "anti_theft": ["anti_loss_switch"],
        "wifi_connected": ["wifi_state"],
        "mobile_connected": ["4g_state"],
        "adaptive_head_enabled": ["param_set", "enable_adaptive_head"],
    }
    return path_map.get(description.key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot binary sensors from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    
    entities_to_add: list[AnthbotBinarySensorEntity] = []
    for coordinator in coordinators:
        state = coordinator.reported_state
        for description in BINARY_SENSORS:
            # Check if the data path exists for conditional sensor creation
            path = _binary_sensor_path_for_description(description)
            if path is not None:
                if not _path_exists(state, *path):
                    continue
            entities_to_add.append(AnthbotBinarySensorEntity(coordinator, description))
    
    async_add_entities(entities_to_add)


class AnthbotBinarySensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], BinarySensorEntity
):
    """Anthbot binary sensor entity."""

    entity_description: AnthbotBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotBinarySensorDescription,
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
    def is_on(self) -> bool:
        """Return current binary sensor value."""
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
        return {
            "serial_number": self.coordinator.client.serial_number,
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
            "voice_volume": voice_volume,
            "voice_status": voice_status,
            "last_service_command": (
                service_reported.get("cmd") if service_reported else None
            ),
            "last_service_command_generation": (
                service_reported.get("generation") if service_reported else None
            ),
        }
