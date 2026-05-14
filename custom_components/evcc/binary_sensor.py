"""Binary sensor platform for EVCC loadpoints."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EvccCoordinator
from .entity import EvccLoadpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EVCC loadpoint binary sensors."""
    coordinator: EvccCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []
    for loadpoint in coordinator.data.loadpoints:
        entities.extend(
            [
                EvccConnectedBinarySensor(coordinator, entry, loadpoint.id),
                EvccChargingBinarySensor(coordinator, entry, loadpoint.id),
            ]
        )
    async_add_entities(entities)


class EvccConnectedBinarySensor(EvccLoadpointEntity, BinarySensorEntity):
    """Binary sensor showing whether a vehicle is connected."""

    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.PLUG

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_connected"
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether a vehicle is connected."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.connected


class EvccChargingBinarySensor(EvccLoadpointEntity, BinarySensorEntity):
    """Binary sensor showing whether charging is active."""

    _attr_name = "Charging"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_charging"
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether charging is active."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.charging
