"""Diagnostics support for EVCC loadpoints."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SENSITIVE_DIAGNOSTIC_KEYS
from .coordinator import EvccCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator: EvccCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(
        {
            "entry": dict(entry.data),
            "available": coordinator.client.available,
            "normalized": {
                "loadpoints": len(coordinator.data.loadpoints),
                "totals_kwh": dict(coordinator.energy_store.totals.totals_kwh),
            },
            "raw_state": coordinator.client.raw_state,
        },
        SENSITIVE_DIAGNOSTIC_KEYS,
    )
