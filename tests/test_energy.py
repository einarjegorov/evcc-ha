"""Tests for EVCC cumulative energy tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("homeassistant")

from custom_components.evcc.energy import EvccEnergyTotals
from custom_components.evcc.models import normalize_evcc_data


def _data(charge_power_w: float, *, available: bool = True):
    return normalize_evcc_data(
        {"loadpoints": [{"title": "Garage", "chargePower": charge_power_w}]},
        available=available,
        host="evcc.local",
        port=7070,
        use_ssl=False,
    )


def _data_with_charger(charge_power_w: float, charger: str):
    return normalize_evcc_data(
        {
            "loadpoints": [
                {
                    "title": "Garage",
                    "charger": charger,
                    "chargePower": charge_power_w,
                }
            ]
        },
        available=True,
        host="evcc.local",
        port=7070,
        use_ssl=False,
    )


def test_energy_totals_integrate_charge_power_over_time() -> None:
    """Charge power is integrated into the persisted total."""
    totals = EvccEnergyTotals()
    now = datetime(2026, 1, 1, tzinfo=UTC)

    assert totals.observe(_data(3600), now) is True
    assert totals.totals_kwh["evcc.local:7070:loadpoint:1"] == 0.0
    assert totals.observe(_data(3600), now + timedelta(minutes=1)) is True
    assert totals.totals_kwh["evcc.local:7070:loadpoint:1"] == 0.06


def test_energy_totals_do_not_integrate_when_power_is_zero() -> None:
    """Zero charge power does not increase cumulative totals."""
    totals = EvccEnergyTotals(totals_kwh={"evcc.local:7070:loadpoint:1": 10.0})
    now = datetime(2026, 1, 1, tzinfo=UTC)

    totals.observe(_data(0), now)
    assert totals.observe(_data(0), now + timedelta(minutes=1)) is False
    assert totals.totals_kwh["evcc.local:7070:loadpoint:1"] == 10.0


def test_energy_totals_do_not_backfill_disconnect_gaps() -> None:
    """Disconnected periods are not added after EVCC reconnects."""
    totals = EvccEnergyTotals()
    now = datetime(2026, 1, 1, tzinfo=UTC)

    totals.observe(_data(3600), now)
    totals.observe(_data(3600, available=False), now + timedelta(hours=1))
    assert totals.observe(_data(3600), now + timedelta(hours=1, minutes=1)) is True
    assert totals.totals_kwh["evcc.local:7070:loadpoint:1"] == 0.06


def test_energy_totals_use_charger_reference_and_migrate_legacy_key() -> None:
    """Legacy numeric totals move to the EVCC charger-scoped key."""
    totals = EvccEnergyTotals(totals_kwh={"1": 12.0})
    now = datetime(2026, 1, 1, tzinfo=UTC)

    assert totals.observe(_data_with_charger(3600, "wallbox"), now) is True

    assert "1" not in totals.totals_kwh
    assert totals.totals_kwh["evcc.local:7070:charger:wallbox"] == 12.0


def test_energy_totals_load_stored_values() -> None:
    """Stored totals are restored and normalized."""
    totals = EvccEnergyTotals.from_stored(
        {"totals_kwh": {"1": "12.5", "bad": object(), "none": None}}
    )

    assert totals.totals_kwh == {"1": 12.5}
