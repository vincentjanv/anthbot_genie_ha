"""Number platform for Anthbot Genie settings."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AnthbotNumberDescription(NumberEntityDescription):
    """Describes an Anthbot number setting."""

    getter: Callable


NUMBERS: tuple[AnthbotNumberDescription, ...] = (
    AnthbotNumberDescription(
        key="mow_height_setting",
        translation_key="mow_height_setting",
        name="Mow height",
        native_min_value=30,
        native_max_value=70,
        native_step=5,
        native_unit_of_measurement="mm",
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("param_set", {}).get("cutter_height")
            if isinstance(data.get("param_set"), dict)
            else (
                data.get("mow_remote", {}).get("cutter_height")
                if isinstance(data.get("mow_remote"), dict)
                else None
            )
        ),
    ),
    AnthbotNumberDescription(
        key="voice_volume_setting",
        translation_key="voice_volume_setting",
        name="Voice volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        getter=lambda data: data.get("volume"),
    ),
    AnthbotNumberDescription(
        key="custom_mowing_direction_setting",
        translation_key="custom_mowing_direction_setting",
        name="Custom mowing direction",
        native_min_value=0,
        native_max_value=180,
        native_step=1,
        native_unit_of_measurement="deg",
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("param_set", {}).get("mow_head")
            if isinstance(data.get("param_set"), dict)
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot number entities from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotNumberEntity(coordinator, description)
        for coordinator in coordinators
        for description in NUMBERS
    )


class AnthbotNumberEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], NumberEntity
):
    """Anthbot number entity."""

    entity_description: AnthbotNumberDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotNumberDescription,
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
    def native_value(self) -> float | None:
        """Return current value."""
        value = self.entity_description.getter(self.coordinator.reported_state)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set value on mower."""
        int_value = int(round(value))
        key = self.entity_description.key
        if key == "mow_height_setting":
            if int_value < 30 or int_value > 70 or int_value % 5 != 0:
                raise ValueError("Mow height must be 30..70 in 5 mm steps")
            await self.coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={"cutter_height": int_value, "rid_switch": 0},
            )
        elif key == "voice_volume_setting":
            if int_value < 0 or int_value > 100:
                raise ValueError("Voice volume must be 0..100")
            await self.coordinator.client.async_publish_service_command(
                cmd="volume_ctl",
                data={"volume": int_value},
            )
        elif key == "custom_mowing_direction_setting":
            if int_value < 0 or int_value > 180:
                raise ValueError("Custom mowing direction must be 0..180")
            await self.coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={
                    "mow_head": int_value,
                    "enable_adaptive_head": 0,
                },
            )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
