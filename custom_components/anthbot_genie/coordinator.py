"""Data coordinator for Anthbot Genie."""

from __future__ import annotations

import base64
from datetime import timedelta
import logging
import struct
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

_CURPATH_MAGIC = b"\x16\x01\x03\x05"
_CURPATH_HEADER_LEN = 22
_CURPATH_RECORD_LEN = 5
_CURPATH_SCALE = 10  # curpath is in centimetres; pose/zone vertexs are in millimetres
_COVERAGE_MAX_POINTS = 5000
_MOWING_STATES = {
    "globalmowing", "zonemowing", "pointmowing",
    "bordermowing", "regionmowing", "nestmowing",
}
_DOCK_RESET_STATES = {
    "charge", "charging", "charge_start", "backtodock",
    "idle", "sleep", "shutdown",
}


def _decode_curpath_mm(blob: Any) -> list[list[int]]:
    """Decode the base64 ``curpath`` window into ``[x, y]`` points in millimetres.

    22-byte header (magic ``16 01 03 05``, uint32 LE point count at offset 4),
    then that many 5-byte records of ``int16 x, int16 y`` (little-endian) plus a
    1-byte flag. The raw values are in CENTIMETRES, so they are scaled to
    millimetres (the same frame as the zone ``vertexs`` and ``pose``).
    """
    if not isinstance(blob, str) or not blob:
        return []
    try:
        raw = base64.b64decode(blob)
    except (ValueError, TypeError):
        return []
    if len(raw) < _CURPATH_HEADER_LEN + _CURPATH_RECORD_LEN or raw[:4] != _CURPATH_MAGIC:
        return []
    count = struct.unpack_from("<I", raw, 4)[0]
    body = raw[_CURPATH_HEADER_LEN:]
    usable = min(count, len(body) // _CURPATH_RECORD_LEN)
    points: list[list[int]] = []
    for i in range(usable):
        x, y = struct.unpack_from("<hh", body, i * _CURPATH_RECORD_LEN)
        points.append([x * _CURPATH_SCALE, y * _CURPATH_SCALE])
    return points


def _raw_robot_status(data: dict[str, Any]) -> str | None:
    """Return the raw robot status string (Genie 600 ``robot_sta`` / M5-M9 ``mode``)."""
    for key in ("robot_sta", "mode"):
        value = data.get(key)
        if isinstance(value, dict):
            raw = value.get("value")
            if isinstance(raw, str):
                return raw.lower()
    return None


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
        self._coverage_points: list[list[int]] = []
        self._coverage_mowing = False

    @property
    def reported_state(self) -> dict[str, Any]:
        """Return the latest reported state."""
        return self.data if isinstance(self.data, dict) else {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest state from the cloud endpoint."""
        try:
            await self.client.async_ensure_temporary_credentials(self.account_client)
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

            self._accumulate_coverage(property_state)

            merged_state = dict(property_state)
            merged_state["_service_reported"] = service_state
            merged_state["_area_definition"] = self._area_definition
            merged_state["_coverage_trail"] = list(self._coverage_points)
            return merged_state
        except AnthbotGenieApiError as err:
            raise UpdateFailed(str(err)) from err

    def _accumulate_coverage(self, property_state: dict[str, Any]) -> None:
        """Accumulate the rolling ``curpath`` window into a growing coverage trail.

        ``curpath`` only carries a sliding ~1 m window of the most recent path,
        so the cumulative trail is built up across polls here: new points are
        appended (consecutive duplicates skipped), the list is reset when a new
        mowing session starts or the mower docks, and it is capped in length.
        """
        status = _raw_robot_status(property_state)
        if status in _MOWING_STATES:
            if not self._coverage_mowing:
                # New mowing session started -> begin a fresh trail.
                self._coverage_points = []
            self._coverage_mowing = True
            for point in _decode_curpath_mm(property_state.get("curpath")):
                if not self._coverage_points or self._coverage_points[-1] != point:
                    self._coverage_points.append(point)
            if len(self._coverage_points) > _COVERAGE_MAX_POINTS:
                self._coverage_points = self._coverage_points[-_COVERAGE_MAX_POINTS:]
        elif status in _DOCK_RESET_STATES:
            self._coverage_points = []
            self._coverage_mowing = False
        # Other states (e.g. paused, unknown): keep the trail unchanged.
