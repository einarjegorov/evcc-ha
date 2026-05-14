"""Sensor platform for EVCC loadpoints."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CHARGE_MODE_LABELS, CHARGE_MODE_OPTIONS, DOMAIN, HEARTBEAT_INTERVAL
from .coordinator import EvccCoordinator
from .entity import EvccLoadpointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EVCC loadpoint sensors."""
    coordinator: EvccCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for loadpoint in coordinator.data.loadpoints:
        entities.extend(
            [
                EvccChargePowerSensor(coordinator, entry, loadpoint.id),
                EvccSessionEnergySensor(coordinator, entry, loadpoint.id),
                EvccCumulativeEnergySensor(coordinator, entry, loadpoint.id),
                EvccModeSensor(coordinator, entry, loadpoint.id),
                EvccVehicleTitleSensor(coordinator, entry, loadpoint.id),
                EvccVehicleNameSensor(coordinator, entry, loadpoint.id),
            ]
        )
    async_add_entities(entities)


class EvccSensor(EvccLoadpointEntity, SensorEntity):
    """Base EVCC loadpoint sensor."""

    _attr_force_update = True


class EvccHistoryHeartbeatSensor(EvccSensor):
    """Sensor that writes its HA state every minute for recorder history."""

    async def async_added_to_hass(self) -> None:
        """Register an entity-local heartbeat after HA adds the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._handle_history_heartbeat,
                HEARTBEAT_INTERVAL,
            )
        )

    @callback
    def _handle_history_heartbeat(self, _now) -> None:
        """Write state even when EVCC and the coordinator are unchanged."""
        self.async_write_ha_state()


class EvccChargePowerSensor(EvccHistoryHeartbeatSensor):
    """Sensor for current loadpoint charge power."""

    _attr_name = "Charge Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_charge_power"
        )

    @property
    def native_value(self) -> float | None:
        """Return current charge power in watts."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.charge_power_w


class EvccSessionEnergySensor(EvccSensor):
    """Sensor for EVCC's current session energy."""

    _attr_name = "Session Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_session_energy"
        )

    @property
    def native_value(self) -> float | None:
        """Return current EVCC session energy in kWh."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.session_energy_kwh


class EvccCumulativeEnergySensor(EvccHistoryHeartbeatSensor):
    """Sensor for HA-persisted cumulative loadpoint energy."""

    _attr_name = "Total Charged Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_cumulative_energy"
        )

    @property
    def available(self) -> bool:
        """Keep cumulative energy available once a persisted total exists."""
        loadpoint = self.loadpoint
        return loadpoint is not None and loadpoint.cumulative_energy_kwh is not None

    @property
    def native_value(self) -> float | None:
        """Return cumulative energy in kWh."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.cumulative_energy_kwh


class EvccModeSensor(EvccSensor):
    """Sensor for the current EVCC loadpoint mode."""

    _attr_name = "Mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CHARGE_MODE_OPTIONS

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_mode"

    @property
    def native_value(self) -> str | None:
        """Return the current loadpoint mode."""
        loadpoint = self.loadpoint
        if loadpoint is None or loadpoint.mode is None:
            return None
        return CHARGE_MODE_LABELS.get(loadpoint.mode, loadpoint.mode)


class EvccVehicleTitleSensor(EvccSensor):
    """Sensor for the current vehicle title."""

    _attr_name = "Vehicle"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_vehicle_title"
        )

    @property
    def native_value(self) -> str | None:
        """Return the current vehicle title."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.vehicle_title


class EvccVehicleNameSensor(EvccSensor):
    """Sensor for the current vehicle technical name."""

    _attr_name = "Vehicle Name"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: EvccCoordinator,
        config_entry: ConfigEntry,
        loadpoint_id: int,
    ) -> None:
        super().__init__(coordinator, config_entry, loadpoint_id)
        self._attr_unique_id = (
            f"{config_entry.entry_id}_loadpoint_{loadpoint_id}_vehicle_name"
        )

    @property
    def native_value(self) -> str | None:
        """Return the current vehicle technical name."""
        loadpoint = self.loadpoint
        return None if loadpoint is None else loadpoint.vehicle_name
