"""Tests for EVCC client helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest.importorskip("homeassistant")

from custom_components.evcc.client import (
    EvccClient,
    build_base_url,
    build_ws_url,
)


class _Response:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _Session:
    def __init__(self) -> None:
        self.posts: list[str] = []

    def post(self, url: str):
        self.posts.append(url)
        return _Response()


def test_url_builders() -> None:
    """HTTP and websocket URLs use matching schemes."""
    assert build_base_url("evcc.local", 7070, False) == "http://evcc.local:7070"
    assert build_base_url("evcc.local", 443, True) == "https://evcc.local:443"
    assert build_ws_url("evcc.local", 7070, False) == "ws://evcc.local:7070/ws"
    assert build_ws_url("evcc.local", 443, True) == "wss://evcc.local:443/ws"


async def test_mode_command_uses_1_based_loadpoint_endpoint() -> None:
    """Mode commands target EVCC's 1-based loadpoint REST endpoint."""
    session = _Session()
    client = EvccClient(session, "evcc.local", 7070, False)
    client.async_refresh_state = AsyncMock(return_value={"loadpoints": []})

    await client.async_set_loadpoint_mode(2, "minpv")

    assert session.posts == [
        "http://evcc.local:7070/api/loadpoints/2/mode/minpv"
    ]
    client.async_refresh_state.assert_awaited_once()
