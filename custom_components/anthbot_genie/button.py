"""Button platform for Anthbot Genie actions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class AnthbotButtonDescription(ButtonEntityDescription):
    """Describes an Anthbot action button."""


BUTTONS: tuple[AnthbotButtonDescription, ...] = (
    AnthbotButtonDescription(
        key="start_full_mow",
        translation_key="start_full_mow",
        name="Start full mow",
    ),
    AnthbotButtonDescription(
        key="stop_mow",
        translation_key="stop_mow",
        name="Stop mow",
    ),
    AnthbotButtonDescription(
        key="return_to_dock",
        translation_key="return_to_dock",
        name="Return to dock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot buttons from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotButtonEntity(coordinator, description)
        for coordinator in coordinators
        for description in BUTTONS
    )


class AnthbotButtonEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], ButtonEntity
):
    """Anthbot action button entity."""

    entity_description: AnthbotButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotButtonDescription,
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

    async def async_press(self) -> None:
        """Run the button action."""
        key = self.entity_description.key
        if key == "start_full_mow":
            await self.coordinator.client.async_publish_service_command(
                cmd="app_state", data=1
            )
            await self.coordinator.client.async_publish_service_command(
                cmd="mow_start", data=1
            )
        elif key == "stop_mow":
            await self.coordinator.client.async_publish_service_command(
                cmd="stop_all_tasks", data=1
            )
        elif key == "return_to_dock":
            await self.coordinator.client.async_publish_service_command(
                cmd="charge_start", data=1
            )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
