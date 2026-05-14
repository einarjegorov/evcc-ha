"""Coordinator behavior coverage for EVCC loadpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.evcc.coordinator import EvccCoordinator


def test_heartbeat_observes_energy_and_republishes_current_data(hass) -> None:
    """The minute heartbeat integrates charge power before publishing state."""
    coordinator = object.__new__(EvccCoordinator)
    coordinator.hass = hass
    coordinator.client = type(
        "Client",
        (),
        {
            "raw_state": {
                "loadpoints": [
                    {
                        "title": "Garage",
                        "chargePower": 1000,
                        "chargedEnergy": 2000,
                    }
                ]
            },
            "available": True,
            "host": "evcc.local",
            "port": 7070,
            "use_ssl": False,
        },
    )()
    coordinator.energy_store = type(
        "EnergyStore",
        (),
        {
            "totals": type(
                "Totals",
                (),
                {
                    "totals_kwh": {"1": 5.0},
                    "observe": MagicMock(return_value=True),
                },
            )()
        },
    )()
    coordinator.async_set_updated_data = MagicMock()

    EvccCoordinator._handle_heartbeat(coordinator, None)

    coordinator.energy_store.totals.observe.assert_called_once()
    coordinator.async_set_updated_data.assert_called_once()
    data = coordinator.async_set_updated_data.call_args.args[0]
    assert data.loadpoint(1).charge_power_w == 1000
    assert data.loadpoint(1).cumulative_energy_kwh == 5.0


def test_client_update_observes_energy_and_republishes(hass) -> None:
    """Client updates observe live charge power before publishing."""
    coordinator = object.__new__(EvccCoordinator)
    coordinator.hass = hass
    coordinator.client = type(
        "Client",
        (),
        {
            "raw_state": {"loadpoints": [{"chargePower": 2500}]},
            "available": True,
            "host": "evcc.local",
            "port": 7070,
            "use_ssl": False,
        },
    )()
    coordinator.energy_store = type(
        "EnergyStore",
        (),
        {
            "totals": type(
                "Totals",
                (),
                {
                    "totals_kwh": {"1": 5.0},
                    "observe": MagicMock(return_value=False),
                },
            )(),
            "async_save": MagicMock(),
        },
    )()
    coordinator.async_set_updated_data = MagicMock()

    EvccCoordinator._handle_client_update(coordinator)

    coordinator.energy_store.totals.observe.assert_called_once()
    observed = coordinator.energy_store.totals.observe.call_args.args[0]
    assert observed.loadpoint(1).charge_power_w == 2500
    coordinator.async_set_updated_data.assert_called_once()


def test_poll_schedules_rest_state_refresh(hass) -> None:
    """The REST polling timer schedules a canonical state refresh."""
    coordinator = object.__new__(EvccCoordinator)
    coordinator.hass = type(
        "Hass",
        (),
        {"async_create_task": MagicMock()},
    )()
    coordinator._async_poll_state = MagicMock(return_value="poll-coro")

    EvccCoordinator._handle_poll(coordinator, None)

    coordinator.hass.async_create_task.assert_called_once_with("poll-coro")


async def test_poll_refreshes_state(hass) -> None:
    """Polling uses /api/state through the client."""
    coordinator = object.__new__(EvccCoordinator)
    coordinator.client = type(
        "Client",
        (),
        {
            "async_refresh_state": AsyncMock(return_value={"loadpoints": []}),
            "set_available": MagicMock(),
        },
    )()

    await EvccCoordinator._async_poll_state(coordinator)

    coordinator.client.async_refresh_state.assert_awaited_once()
    coordinator.client.set_available.assert_not_called()
