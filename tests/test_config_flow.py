"""Config flow coverage for EVCC loadpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant")

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from custom_components.evcc.const import CONF_USE_SSL, DEFAULT_PORT, DOMAIN


async def test_user_flow_success(hass) -> None:
    """A successful user flow creates an entry."""
    with patch(
        "custom_components.evcc.config_flow.async_probe_client",
        AsyncMock(return_value={"siteTitle": "Home EVCC", "loadpoints": [{}]}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "evcc.local",
                CONF_PORT: DEFAULT_PORT,
                CONF_USE_SSL: False,
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Home EVCC"
    assert result2["data"] == {
        CONF_HOST: "evcc.local",
        CONF_PORT: DEFAULT_PORT,
        CONF_USE_SSL: False,
    }


async def test_user_flow_cannot_connect(hass) -> None:
    """Connection failures are surfaced as form errors."""
    from custom_components.evcc.client import CannotConnectError

    with patch(
        "custom_components.evcc.config_flow.async_probe_client",
        AsyncMock(side_effect=CannotConnectError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "evcc.local",
                CONF_PORT: DEFAULT_PORT,
                CONF_USE_SSL: False,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"]["base"] == "cannot_connect"


async def test_duplicate_entry_aborts(hass) -> None:
    """An already configured EVCC instance is not added twice."""
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Existing",
        data={
            CONF_HOST: "evcc.local",
            CONF_PORT: DEFAULT_PORT,
            CONF_USE_SSL: False,
        },
        source=config_entries.SOURCE_USER,
        entry_id="test",
        unique_id="http://evcc.local:7070",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.evcc.config_flow.async_probe_client",
        AsyncMock(return_value={"siteTitle": "Existing", "loadpoints": [{}]}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "evcc.local",
                CONF_PORT: DEFAULT_PORT,
                CONF_USE_SSL: False,
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_reconfigure_updates_entry(hass) -> None:
    """Reconfigure updates connection settings in place."""
    entry = config_entries.ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Existing",
        data={
            CONF_HOST: "evcc.local",
            CONF_PORT: DEFAULT_PORT,
            CONF_USE_SSL: False,
        },
        source=config_entries.SOURCE_USER,
        entry_id="test",
        unique_id="http://evcc.local:7070",
        discovery_keys={},
        options={},
        subentries_data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.evcc.config_flow.async_probe_client",
        AsyncMock(return_value={"siteTitle": "Existing", "loadpoints": [{}]}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_RECONFIGURE},
            data={"entry_id": entry.entry_id},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "new.local",
                CONF_PORT: 7443,
                CONF_USE_SSL: True,
            },
        )

    assert result2["type"] == "abort"
    assert entry.data == {
        CONF_HOST: "new.local",
        CONF_PORT: 7443,
        CONF_USE_SSL: True,
    }
