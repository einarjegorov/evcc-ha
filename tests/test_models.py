"""Tests for EVCC state normalization."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _load_module(name: str, relative_path: str):
    path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


models = _load_module("evcc_models", "custom_components/evcc/models.py")


def test_normalize_evcc_data_loadpoints_only() -> None:
    """State normalization ignores site sensors and keeps loadpoint fields."""
    data = models.normalize_evcc_data(
        {
            "siteTitle": "Home EVCC",
            "gridPower": 1234,
            "pvPower": 5678,
            "loadpoints": [
                {
                    "title": "Garage",
                    "charger": "wallbox",
                    "meter": "garage-meter",
                    "circuit": "garage-circuit",
                    "connected": True,
                    "charging": False,
                    "chargePower": 3210,
                    "chargedEnergy": 12500,
                    "mode": "pv",
                    "vehicleTitle": "Car",
                    "vehicleName": "car",
                }
            ],
        },
        available=True,
        host="evcc.local",
        port=7070,
        use_ssl=False,
        totals_kwh={"1": 42.1234567},
    )

    assert data.title == "Home EVCC"
    assert data.client_key == "evcc.local:7070"
    assert len(data.loadpoints) == 1
    loadpoint = data.loadpoints[0]
    assert loadpoint.id == 1
    assert loadpoint.display_title == "Garage"
    assert loadpoint.charger_ref == "wallbox"
    assert loadpoint.meter_ref == "garage-meter"
    assert loadpoint.circuit_ref == "garage-circuit"
    assert loadpoint.stable_ref == "charger:wallbox"
    assert data.energy_key(loadpoint) == "evcc.local:7070:charger:wallbox"
    assert loadpoint.connected is True
    assert loadpoint.charging is False
    assert loadpoint.charge_power_w == 3210
    assert loadpoint.charged_energy_wh == 12500
    assert loadpoint.session_energy_kwh == 12.5
    assert loadpoint.cumulative_energy_kwh == 42.123457
    assert loadpoint.mode == "pv"
    assert loadpoint.vehicle_title == "Car"
    assert loadpoint.vehicle_name == "car"


def test_normalize_evcc_data_handles_missing_state() -> None:
    """Missing raw state returns an empty unavailable data object."""
    data = models.normalize_evcc_data(
        None,
        available=False,
        host="evcc.local",
        port=7070,
        use_ssl=False,
    )

    assert data.available is False
    assert data.title == "evcc.local"
    assert data.loadpoints == ()


def test_loadpoint_lookup() -> None:
    """Loadpoints can be addressed by EVCC's 1-based id."""
    data = models.normalize_evcc_data(
        {"loadpoints": [{"title": "A"}, {"title": "B"}]},
        available=True,
        host="evcc.local",
        port=7070,
        use_ssl=False,
    )

    assert data.loadpoint(1).title == "A"
    assert data.loadpoint(2).title == "B"
    assert data.loadpoint(3) is None


def test_loadpoint_stable_ref_falls_back_to_meter_circuit_and_id() -> None:
    """Loadpoint energy keys prefer EVCC static refs before array id."""
    data = models.normalize_evcc_data(
        {
            "loadpoints": [
                {"title": "A", "meter": "meter-a"},
                {"title": "B", "circuit": "circuit-b"},
                {"title": "C"},
            ]
        },
        available=True,
        host="evcc.local",
        port=7070,
        use_ssl=False,
    )

    assert data.loadpoint(1).stable_ref == "meter:meter-a"
    assert data.loadpoint(2).stable_ref == "circuit:circuit-b"
    assert data.loadpoint(3).stable_ref == "loadpoint:3"
