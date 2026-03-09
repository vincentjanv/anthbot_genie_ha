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
    robot_sta = data.get("robot_sta")
    if not isinstance(robot_sta, dict):
        return False
    value = robot_sta.get("value")
    if not isinstance(value, str):
        return False
    return value.lower() in {"charge", "charging", "charge_start"}


def _is_custom_mowing_direction_enabled(data: dict[str, Any]) -> bool:
    param_set = data.get("param_set")
    if not isinstance(param_set, dict):
        return False
    value = param_set.get("enable_adaptive_head")
    adaptive_enabled = False
    if isinstance(value, bool):
        adaptive_enabled = value
    elif isinstance(value, int):
        adaptive_enabled = value == 1
    elif isinstance(value, str):
        adaptive_enabled = value == "1"
    return not adaptive_enabled


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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot binary sensors from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotBinarySensorEntity(coordinator, description)
        for coordinator in coordinators
        for description in BINARY_SENSORS
    )


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
            "voice_volume": voice_volume,
            "voice_status": voice_status,
            "last_service_command": (
                service_reported.get("cmd") if service_reported else None
            ),
            "last_service_command_generation": (
                service_reported.get("generation") if service_reported else None
            ),
        }
