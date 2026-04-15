"""Camera platform for generated Anthbot Genie maps."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .maps import (
    active_zone_ids,
    auto_zone_points,
    manual_zone_polygons,
    merged_session_path_points,
    mower_pose,
    render_map_png,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AnthbotMapCameraDescription(CameraEntityDescription):
    """Describes an Anthbot generated map camera."""

    title: str
    show_manual_zones: bool
    show_auto_zones: bool
    show_path: bool
    show_pose: bool


CAMERAS: tuple[AnthbotMapCameraDescription, ...] = (
    AnthbotMapCameraDescription(
        key="session_map",
        name="Session map",
        title="Session Map",
        show_manual_zones=True,
        show_auto_zones=True,
        show_path=True,
        show_pose=True,
    ),
    AnthbotMapCameraDescription(
        key="zones_map",
        name="Zones map",
        title="Zones Map",
        show_manual_zones=True,
        show_auto_zones=False,
        show_path=False,
        show_pose=False,
    ),
    AnthbotMapCameraDescription(
        key="auto_zones_map",
        name="Auto-zones map",
        title="Auto-zones Map",
        show_manual_zones=True,
        show_auto_zones=True,
        show_path=False,
        show_pose=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot map cameras from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotMapCameraEntity(coordinator, description)
        for coordinator in coordinators
        for description in CAMERAS
    )


class AnthbotMapCameraEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], Camera
):
    """Generated mower map camera."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_content_type = "image/png"

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotMapCameraDescription,
    ) -> None:
        Camera.__init__(self)
        CoordinatorEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.client.serial_number}_{description.key}"
        self._last_render_key: tuple[Any, ...] | None = None
        self._last_image: bytes | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    def _render_key(self) -> tuple[Any, ...]:
        state = self.coordinator.reported_state
        return (
            self.entity_description.key,
            state.get("generation"),
            state.get("area_time"),
            state.get("path_time"),
            state.get("timestamp"),
            state.get("curpath"),
        )

    def _render(self) -> bytes:
        state = self.coordinator.reported_state
        return render_map_png(
            title=self.entity_description.title,
            serial_number=self.coordinator.client.serial_number,
            manual_zones_data=manual_zone_polygons(state),
            auto_zones_data=auto_zone_points(state),
            active_zone_id_list=active_zone_ids(state),
            path_points=merged_session_path_points(state),
            pose=mower_pose(state),
            path_source=state.get("_session_path_source"),
            show_manual_zones=self.entity_description.show_manual_zones,
            show_auto_zones=self.entity_description.show_auto_zones,
            show_path=self.entity_description.show_path,
            show_pose=self.entity_description.show_pose,
        )

    def _render_cached(self) -> bytes:
        render_key = self._render_key()
        if self._last_image is not None and render_key == self._last_render_key:
            return self._last_image

        image = self._render()
        self._last_render_key = render_key
        self._last_image = image
        return image

    def camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes:
        """Return the generated PNG image."""
        try:
            return self._render_cached()
        except Exception:
            _LOGGER.exception(
                "Failed to render Anthbot map camera %s",
                self.entity_id or self._attr_unique_id,
            )
            return self._last_image or b""

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes:
        """Return the generated PNG image."""
        try:
            return await self.hass.async_add_executor_job(self._render_cached)
        except Exception:
            _LOGGER.exception(
                "Failed to render Anthbot map camera %s",
                self.entity_id or self._attr_unique_id,
            )
            return self._last_image or b""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return camera metadata."""
        state = self.coordinator.reported_state
        path_points = merged_session_path_points(state)
        pose = mower_pose(state)
        return {
            "serial_number": self.coordinator.client.serial_number,
            "manual_zone_count": len(manual_zone_polygons(state)),
            "auto_zone_count": len(auto_zone_points(state)),
            "active_zone_ids": active_zone_ids(state),
            "path_point_count": len(path_points),
            "path_source": state.get("_session_path_source"),
            "pose": {"x": pose[0], "y": pose[1]} if pose is not None else None,
        }
