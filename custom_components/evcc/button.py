"""Button platform for EVCC loadpoints."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CHARGE_MODE_LABELS, CHARGE_MODES, DOMAIN
from .coordinator import EvccCoordinator
from .entity import EvccLoadpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EVCC loadpoint buttons."""
    coordinator: EvccCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []
    for loadpoint in coordinator.data.loadpoints:
        entities.extend(
            EvccModeButton(coordinator, entry, loadpoint.id, mode)
            for mode in CHARGE_MODES
        )
    async_add_entities(entities)


class EvccModeButton(EvccLoadpointEntity, ButtonEntity):
    """Button that forwards a mode command to EVCC."""

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
        mode: str,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._mode = mode
        self._attr_name = CHARGE_MODE_LABELS[mode]
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_mode_{mode}"
        )

    async def async_press(self) -> None:
        """Send the requested mode command."""
        await self.coordinator.client.async_set_loadpoint_mode(
            self.loadpoint_id,
            self._mode,
        )
