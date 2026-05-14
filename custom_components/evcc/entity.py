"""Shared entity code for the EVCC loadpoint integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import EvccCoordinator
from .models import LoadpointData


class EvccEntity(CoordinatorEntity[EvccCoordinator]):
    """Base entity for the EVCC integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry


class EvccLoadpointEntity(EvccEntity):
    """Base entity for a single EVCC loadpoint."""

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry)
        self.loadpoint_id = loadpoint_id

    @property
    def loadpoint(self) -> LoadpointData | None:
        """Return the current normalized loadpoint data."""
        return self.coordinator.data.loadpoint(self.loadpoint_id)

    @property
    def available(self) -> bool:
        """Loadpoint entities are unavailable when EVCC is disconnected."""
        return self.coordinator.data.available and self.loadpoint is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the EVCC loadpoint as a Home Assistant device."""
        loadpoint = self.loadpoint
        title = (
            loadpoint.display_title
            if loadpoint is not None
            else f"Loadpoint {self.loadpoint_id}"
        )
        return DeviceInfo(
            identifiers={
                (DOMAIN, self.coordinator.data.client_key, str(self.loadpoint_id))
            },
            manufacturer=MANUFACTURER,
            model="EVCC Loadpoint",
            name=title,
        )
