"""Switch platform for Anthbot Genie settings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .mow_params import (
    build_nest_mow_params_payload,
    coerce_enabled_value,
    custom_direction_enabled_from_state,
    nest_mowing_enabled_from_state,
    nest_visual_inspection_enabled_from_state,
)


@dataclass(frozen=True, kw_only=True)
class AnthbotSwitchDescription(SwitchEntityDescription):
    """Describes an Anthbot switch setting."""


SWITCHES: tuple[AnthbotSwitchDescription, ...] = (
    AnthbotSwitchDescription(
        key="custom_mowing_direction_enabled",
        translation_key="custom_mowing_direction_enabled",
        name="Custom mowing direction enabled",
    ),
    AnthbotSwitchDescription(
        key="rain_perception_enabled",
        translation_key="rain_perception_enabled",
        name="Rain perception",
    ),
    AnthbotSwitchDescription(
        key="base_station_mowing_enabled",
        translation_key="base_station_mowing_enabled",
        name="Base station mowing",
    ),
    AnthbotSwitchDescription(
        key="base_station_visual_inspection_enabled",
        translation_key="base_station_visual_inspection_enabled",
        name="Base station visual inspection",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot switch entities from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotSwitchEntity(coordinator, description)
        for coordinator in coordinators
        for description in SWITCHES
    )


class AnthbotSwitchEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SwitchEntity
):
    """Anthbot switch entity."""

    entity_description: AnthbotSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotSwitchDescription,
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
        """Return current switch value."""
        state = self.coordinator.reported_state
        if self.entity_description.key == "rain_perception_enabled":
            if state.get("rain_switch") is None:
                return coerce_enabled_value(state.get("device_config").get("rain_switch"))
            else:
                return coerce_enabled_value(state.get("rain_switch"))
        if self.entity_description.key == "base_station_mowing_enabled":
            return nest_mowing_enabled_from_state(state)
        if self.entity_description.key == "base_station_visual_inspection_enabled":
            return nest_visual_inspection_enabled_from_state(state)
        return custom_direction_enabled_from_state(state)

    async def _async_set_custom_direction_enabled(self, enabled: bool) -> None:
        """Set custom mowing direction toggle."""
        param_set = self.coordinator.reported_state.get("param_set")
        mow_head = 0
        if isinstance(param_set, dict):
            value = param_set.get("mow_head")
            if isinstance(value, int):
                mow_head = value

        await self.coordinator.client.async_publish_service_command(
            cmd="param_set",
            data={
                "mow_head": mow_head,
                "enable_adaptive_head": 0 if enabled else 1,
            },
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def _async_set_rain_perception_enabled(self, enabled: bool) -> None:
        """Set rain perception toggle."""
        target_value = 1 if enabled else 0
        reported_continue_time = self.coordinator.reported_state.get("rain_continue_time")
        continue_time = (
            reported_continue_time
            if isinstance(reported_continue_time, int) and reported_continue_time > 0
            else 10800
        )

        await self.coordinator.client.async_publish_service_command(
            cmd="ctl_rainer",
            data={
                "switch": target_value,
                "continue_time": continue_time,
            },
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

        if self.is_on != enabled:
            raise AnthbotGenieApiError(
                "Rain perception command was accepted but the reported state did not change"
            )

    async def _async_set_base_station_mowing_enabled(self, enabled: bool) -> None:
        """Set base-station mowing mode."""
        await self.coordinator.client.async_publish_service_command(
            cmd="set_mow_params",
            data=build_nest_mow_params_payload(
                self.coordinator.reported_state,
                nest_switch=1 if enabled else 0,
            ),
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def _async_set_base_station_visual_inspection_enabled(
        self, enabled: bool
    ) -> None:
        """Set base-station visual inspection toggle."""
        await self.coordinator.client.async_publish_service_command(
            cmd="set_mow_params",
            data=build_nest_mow_params_payload(
                self.coordinator.reported_state,
                nest_pobctl_switch=1 if enabled else 0,
            ),
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        if self.entity_description.key == "rain_perception_enabled":
            await self._async_set_rain_perception_enabled(True)
            return
        if self.entity_description.key == "base_station_mowing_enabled":
            await self._async_set_base_station_mowing_enabled(True)
            return
        if self.entity_description.key == "base_station_visual_inspection_enabled":
            await self._async_set_base_station_visual_inspection_enabled(True)
            return
        await self._async_set_custom_direction_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        if self.entity_description.key == "rain_perception_enabled":
            await self._async_set_rain_perception_enabled(False)
            return
        if self.entity_description.key == "base_station_mowing_enabled":
            await self._async_set_base_station_mowing_enabled(False)
            return
        if self.entity_description.key == "base_station_visual_inspection_enabled":
            await self._async_set_base_station_visual_inspection_enabled(False)
            return
        await self._async_set_custom_direction_enabled(False)
