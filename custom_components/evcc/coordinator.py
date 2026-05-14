"""Coordinator for the EVCC loadpoint integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import EvccClient, entry_client_options
from .const import DOMAIN, HEARTBEAT_INTERVAL, STATE_POLL_INTERVAL
from .energy import EvccEnergyStore
from .models import NormalizedEvccData, normalize_evcc_data

_LOGGER = logging.getLogger(__name__)


class EvccCoordinator(DataUpdateCoordinator[NormalizedEvccData]):
    """Push coordinator backed by EVCC state and websocket updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
        )
        self.entry = entry
        host, port, use_ssl = entry_client_options(entry.data)
        self.client = EvccClient(
            session=session,
            host=host,
            port=port,
            use_ssl=use_ssl,
        )
        self.energy_store = EvccEnergyStore(hass)
        self._remove_listener = self.client.add_listener(self._handle_client_update)
        self._remove_heartbeat: Callable[[], None] | None = None
        self._remove_poll: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start EVCC communication and wait for the first snapshot."""
        await self.energy_store.async_load()
        await self.client.async_start()
        self._publish_client_data(update_energy=True)
        self._remove_heartbeat = async_track_time_interval(
            self.hass,
            self._handle_heartbeat,
            HEARTBEAT_INTERVAL,
        )
        self._remove_poll = async_track_time_interval(
            self.hass,
            self._handle_poll,
            STATE_POLL_INTERVAL,
        )

    async def async_shutdown(self) -> None:
        """Stop EVCC communication."""
        if self._remove_heartbeat is not None:
            self._remove_heartbeat()
            self._remove_heartbeat = None
        if self._remove_poll is not None:
            self._remove_poll()
            self._remove_poll = None
        self._remove_listener()
        await self.client.async_stop()

    async def _async_update_data(self) -> NormalizedEvccData:
        """Return the latest normalized client data for manual refreshes."""
        return self._normalized_data()

    @callback
    def _handle_client_update(self) -> None:
        self._publish_client_data(update_energy=True)

    @callback
    def _handle_heartbeat(self, _now: Any) -> None:
        self._publish_client_data(update_energy=True)

    @callback
    def _handle_poll(self, _now: Any) -> None:
        self.hass.async_create_task(self._async_poll_state())

    async def _async_poll_state(self) -> None:
        """Refresh canonical state when websocket updates are absent."""
        try:
            await self.client.async_refresh_state()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error while polling EVCC state")
            self.client.set_available(False)

    @callback
    def _publish_client_data(self, *, update_energy: bool) -> None:
        data = self._normalized_data()
        if update_energy and self.energy_store.totals.observe(data):
            self.hass.async_create_task(self.energy_store.async_save())
            data = self._normalized_data()
        self.async_set_updated_data(data)

    def _normalized_data(self) -> NormalizedEvccData:
        """Return current normalized data with cumulative totals applied."""
        return normalize_evcc_data(
            self.client.raw_state,
            available=self.client.available,
            host=self.client.host,
            port=self.client.port,
            use_ssl=self.client.use_ssl,
            totals_kwh=self.energy_store.totals.totals_kwh,
        )
