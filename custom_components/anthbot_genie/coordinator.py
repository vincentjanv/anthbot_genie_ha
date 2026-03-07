"""Data coordinator for Anthbot Genie."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AnthbotBoundDevice, AnthbotGenieApiError, AnthbotShadowApiClient
from .const import DOMAIN


class AnthbotGenieDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch and cache Anthbot shadow state."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
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
        self.client = client
        self.device = device

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

            merged_state = dict(property_state)
            merged_state["_service_reported"] = service_state
            return merged_state
        except AnthbotGenieApiError as err:
            raise UpdateFailed(str(err)) from err
