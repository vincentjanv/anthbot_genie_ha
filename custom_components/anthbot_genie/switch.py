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

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator


def _is_custom_direction_enabled(value: object) -> bool:
    """Map raw enable_adaptive_head value to custom-direction toggle state."""
    adaptive_enabled = False
    if isinstance(value, bool):
        adaptive_enabled = value
    elif isinstance(value, int):
        adaptive_enabled = value == 1
    elif isinstance(value, str):
        adaptive_enabled = value == "1"
    return not adaptive_enabled


@dataclass(frozen=True, kw_only=True)
class AnthbotSwitchDescription(SwitchEntityDescription):
    """Describes an Anthbot switch setting."""


SWITCHES: tuple[AnthbotSwitchDescription, ...] = (
    AnthbotSwitchDescription(
        key="custom_mowing_direction_enabled",
        translation_key="custom_mowing_direction_enabled",
        name="Custom mowing direction enabled",
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
        param_set = self.coordinator.reported_state.get("param_set")
        if not isinstance(param_set, dict):
            return False
        return _is_custom_direction_enabled(param_set.get("enable_adaptive_head"))

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

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        await self._async_set_custom_direction_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        await self._async_set_custom_direction_enabled(False)
