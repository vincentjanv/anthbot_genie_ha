"""Lawn mower platform for Anthbot Genie."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator


_MOWING_RAW_STATUSES: frozenset[str] = frozenset(
    {
        "globalmowing",
        "zonemowing",
        "pointmowing",
        "bordermowing",
        "regionmowing",
        "nestmowing",
        "position",
        "resume_point",
        "gototarget",
        "mapping",
    }
)
_DOCKED_RAW_STATUSES: frozenset[str] = frozenset(
    {"charge", "charging", "charge_start", "idle", "sleep", "shutdown"}
)
_RETURNING_RAW_STATUSES: frozenset[str] = frozenset({"backtodock"})
_PAUSED_RAW_STATUSES: frozenset[str] = frozenset({"pause"})

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


def _activity_from_state(data: dict[str, Any]) -> LawnMowerActivity | None:
    """Map raw shadow state to a Home Assistant LawnMowerActivity."""
    raw = _raw_robot_status(data)
    if raw is None:
        return None
    if raw in _MOWING_RAW_STATUSES:
        return LawnMowerActivity.MOWING
    if raw in _RETURNING_RAW_STATUSES:
        return LawnMowerActivity.RETURNING
    if raw in _PAUSED_RAW_STATUSES:
        return LawnMowerActivity.PAUSED
    if raw in _DOCKED_RAW_STATUSES:
        return LawnMowerActivity.DOCKED
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot lawn mower entities from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotLawnMowerEntity(coordinator) for coordinator in coordinators
    )


class AnthbotLawnMowerEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], LawnMowerEntity
):
    """Anthbot lawn mower entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_lawn_mower"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return current mower activity."""
        return _activity_from_state(self.coordinator.reported_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self.coordinator.reported_state
        return {
            "serial_number": self.coordinator.client.serial_number,
            "robot_status_raw": _raw_robot_status(state),
        }

    async def _async_sync_after_command(self) -> None:
        """Refresh shadow state after issuing a command."""
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_start_mowing(self) -> None:
        """Start mowing."""
        await self.coordinator.client.async_publish_service_command(
            cmd="app_state", data=1
        )
        await self.coordinator.client.async_publish_service_command(
            cmd="mow_start", data=1
        )
        await self._async_sync_after_command()

    async def async_pause(self) -> None:
        """Pause the mower.

        Anthbot Genie does not expose a true pause command; this stops the
        current task, mirroring the behavior of the ``Stop mow`` button.
        """
        await self.coordinator.client.async_publish_service_command(
            cmd="stop_all_tasks", data=1
        )
        await self._async_sync_after_command()

    async def async_dock(self) -> None:
        """Send the mower back to its dock."""
        await self.coordinator.client.async_publish_service_command(
            cmd="charge_start", data=1
        )
        await self._async_sync_after_command()
