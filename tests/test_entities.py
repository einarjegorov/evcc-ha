"""Entity behavior coverage for EVCC loadpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

from custom_components.evcc.models import normalize_evcc_data


class _StubClient:
    """Minimal coordinator client stub for button tests."""

    def __init__(self) -> None:
        self.mode_calls: list[tuple[int, str]] = []

    async def async_set_loadpoint_mode(self, loadpoint_id: int, mode: str) -> None:
        self.mode_calls.append((loadpoint_id, mode))


def _coordinator():
    coordinator = type("Coordinator", (), {})()
    coordinator.data = normalize_evcc_data(
        {
            "siteTitle": "Home",
            "loadpoints": [
                {
                    "title": "Garage",
                    "connected": True,
                    "charging": True,
                    "chargePower": 4200,
                    "chargedEnergy": 1500,
                    "mode": "minpv",
                    "vehicleTitle": "Car",
                    "vehicleName": "car",
                }
            ],
        },
        available=True,
        host="evcc.local",
        port=7070,
        use_ssl=False,
        totals_kwh={"1": 12.25},
    )
    coordinator.client = _StubClient()
    return coordinator


def test_sensor_entities_reflect_loadpoint_state(hass) -> None:
    """Stable entities expose normalized loadpoint values."""
    from custom_components.evcc.sensor import (
        EvccChargePowerSensor,
        EvccCumulativeEnergySensor,
        EvccModeSensor,
        EvccSessionEnergySensor,
        EvccVehicleNameSensor,
        EvccVehicleTitleSensor,
    )

    coordinator = _coordinator()
    entry = type("Entry", (), {"entry_id": "entry"})()

    assert EvccChargePowerSensor(coordinator, entry, 1).native_value == 4200
    assert EvccSessionEnergySensor(coordinator, entry, 1).native_value == 1.5
    assert EvccCumulativeEnergySensor(coordinator, entry, 1).native_value == 12.25
    assert EvccModeSensor(coordinator, entry, 1).native_value == "Min+PV"
    assert EvccVehicleTitleSensor(coordinator, entry, 1).native_value == "Car"
    assert EvccVehicleNameSensor(coordinator, entry, 1).native_value == "car"


def test_all_sensors_force_update(hass) -> None:
    """All sensors must emit repeated same-value states for automation reliability."""
    from custom_components.evcc.sensor import (
        EvccChargePowerSensor,
        EvccCumulativeEnergySensor,
        EvccModeSensor,
        EvccSessionEnergySensor,
        EvccVehicleNameSensor,
        EvccVehicleTitleSensor,
    )

    coordinator = _coordinator()
    entry = type("Entry", (), {"entry_id": "entry"})()

    sensors = [
        EvccChargePowerSensor(coordinator, entry, 1),
        EvccSessionEnergySensor(coordinator, entry, 1),
        EvccCumulativeEnergySensor(coordinator, entry, 1),
        EvccModeSensor(coordinator, entry, 1),
        EvccVehicleTitleSensor(coordinator, entry, 1),
        EvccVehicleNameSensor(coordinator, entry, 1),
    ]

    assert all(sensor.force_update is True for sensor in sensors)
    assert sensors[2].name == "Total Charged Energy"


async def test_history_sensitive_sensors_register_entity_heartbeat(hass) -> None:
    """Recorder-sensitive sensors register their own minute write timer."""
    from custom_components.evcc.const import HEARTBEAT_INTERVAL
    from custom_components.evcc.sensor import EvccChargePowerSensor

    coordinator = _coordinator()
    entry = type("Entry", (), {"entry_id": "entry"})()
    sensor = EvccChargePowerSensor(coordinator, entry, 1)
    sensor.hass = hass
    sensor.async_on_remove = MagicMock()
    remove = MagicMock()

    with patch(
        "custom_components.evcc.sensor.async_track_time_interval",
        return_value=remove,
    ) as track:
        await sensor.async_added_to_hass()

    track.assert_called_once_with(
        hass,
        sensor._handle_history_heartbeat,
        HEARTBEAT_INTERVAL,
    )
    sensor.async_on_remove.assert_called_once_with(remove)


def test_binary_sensor_entities_reflect_loadpoint_state(hass) -> None:
    """Binary sensors expose loadpoint connection and charging state."""
    from custom_components.evcc.binary_sensor import (
        EvccChargingBinarySensor,
        EvccConnectedBinarySensor,
    )

    coordinator = _coordinator()
    entry = type("Entry", (), {"entry_id": "entry"})()

    assert EvccConnectedBinarySensor(coordinator, entry, 1).is_on is True
    assert EvccChargingBinarySensor(coordinator, entry, 1).is_on is True


async def test_button_entities_send_expected_mode_commands(hass) -> None:
    """Button presses use EVCC mode names."""
    from custom_components.evcc.button import EvccModeButton

    coordinator = _coordinator()
    entry = type("Entry", (), {"entry_id": "entry"})()

    await EvccModeButton(coordinator, entry, 1, "off").async_press()
    await EvccModeButton(coordinator, entry, 1, "now").async_press()
    await EvccModeButton(coordinator, entry, 1, "minpv").async_press()
    await EvccModeButton(coordinator, entry, 1, "pv").async_press()

    assert coordinator.client.mode_calls == [
        (1, "off"),
        (1, "now"),
        (1, "minpv"),
        (1, "pv"),
    ]


def test_history_sensitive_sensors_write_on_coordinator_update(hass) -> None:
    """Coordinator updates make history-sensitive sensors write HA state."""
    from custom_components.evcc.sensor import (
        EvccChargePowerSensor,
        EvccCumulativeEnergySensor,
    )

    coordinator = _coordinator()
    entry = type("Entry", (), {"entry_id": "entry"})()
    charge_power = EvccChargePowerSensor(coordinator, entry, 1)
    cumulative = EvccCumulativeEnergySensor(coordinator, entry, 1)
    calls: list[str] = []

    charge_power.async_write_ha_state = lambda: calls.append("power")
    cumulative.async_write_ha_state = lambda: calls.append("energy")

    charge_power._handle_coordinator_update()
    cumulative._handle_coordinator_update()

    assert calls == ["power", "energy"]
