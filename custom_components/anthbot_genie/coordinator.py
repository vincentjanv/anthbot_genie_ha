"""Data coordinator for Anthbot Genie."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AnthbotBoundDevice,
    AnthbotCloudApiClient,
    AnthbotGenieApiError,
    AnthbotShadowApiClient,
)
from .const import DOMAIN
from .maps import parse_history_path_bytes


def _raw_robot_status(data: dict[str, Any]) -> str | None:
    robot_sta = data.get("robot_sta")
    if not isinstance(robot_sta, dict):
        return None
    value = robot_sta.get("value")
    if isinstance(value, str):
        return value.lower()
    return None


def _should_refresh_path(
    state: dict[str, Any],
    cached_path_points: list[dict[str, int]],
    last_path_time: str | None,
    last_path_fetch_at: datetime | None,
) -> bool:
    path_time = state.get("path_time")
    has_curpath = isinstance(state.get("curpath"), str) and bool(state.get("curpath"))
    status = _raw_robot_status(state)
    session_active = status in {
        "globalmowing",
        "zonemowing",
        "pointmowing",
        "bordermowing",
        "regionmowing",
        "nestmowing",
        "pause",
        "backtodock",
        "mapping",
    }

    if isinstance(path_time, str) and path_time and path_time != last_path_time:
        return True
    if not cached_path_points and has_curpath:
        return True
    if not session_active:
        return False
    if last_path_fetch_at is None:
        return True
    return (datetime.now(timezone.utc) - last_path_fetch_at) >= timedelta(minutes=2)


class AnthbotGenieDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch and cache Anthbot shadow state."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        account_client: AnthbotCloudApiClient,
        client: AnthbotShadowApiClient,
        device: AnthbotBoundDevice,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.account_client = account_client
        self.client = client
        self.device = device
        self._area_definition: dict[str, Any] = {}
        self._last_area_time: str | None = None
        self._session_path_points: list[dict[str, int]] = []
        self._last_path_time: str | None = None
        self._last_path_fetch_at: datetime | None = None

    @property
    def reported_state(self) -> dict[str, Any]:
        """Return the latest reported state."""
        return self.data if isinstance(self.data, dict) else {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest state from the cloud endpoint."""
        try:
            property_state = await self.client.async_get_shadow_reported_state()
            try:
                service_state = await self.client.async_get_service_reported_state()
            except AnthbotGenieApiError:
                service_state = {}

            area_time = property_state.get("area_time")
            if not isinstance(area_time, str):
                area_time = None
            should_refresh_area = not self._area_definition or (
                area_time is not None and area_time != self._last_area_time
            )
            if should_refresh_area:
                try:
                    self._area_definition = (
                        await self.account_client.async_get_device_area_definition(
                            self.client.serial_number
                        )
                    )
                    self._last_area_time = area_time
                except AnthbotGenieApiError:
                    if not self._area_definition:
                        self._area_definition = {}

            if _should_refresh_path(
                property_state,
                self._session_path_points,
                self._last_path_time,
                self._last_path_fetch_at,
            ):
                try:
                    path_bytes = await self.account_client.async_get_device_path_data(
                        self.client.serial_number
                    )
                    self._session_path_points = parse_history_path_bytes(path_bytes)
                    path_time = property_state.get("path_time")
                    self._last_path_time = path_time if isinstance(path_time, str) else None
                    self._last_path_fetch_at = datetime.now(timezone.utc)
                except AnthbotGenieApiError:
                    if not self._session_path_points:
                        self._session_path_points = []

            merged_state = dict(property_state)
            merged_state["_service_reported"] = service_state
            merged_state["_area_definition"] = self._area_definition
            merged_state["_session_path_points"] = self._session_path_points
            merged_state["_session_path_source"] = (
                "history_file" if self._session_path_points else "curpath"
            )
            return merged_state
        except AnthbotGenieApiError as err:
            raise UpdateFailed(str(err)) from err
