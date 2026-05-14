"""HTTP and websocket client for EVCC."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Mapping
from typing import Any

import aiohttp
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CLIENT_READY_TIMEOUT,
    CONF_USE_SSL,
    RECONNECT_INITIAL_DELAY,
    RECONNECT_MAX_DELAY,
    STATE_PATH,
    WS_PATH,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnectError(Exception):
    """Raised when EVCC cannot be reached."""


class InvalidStateError(Exception):
    """Raised when EVCC does not return a usable state payload."""


def build_base_url(host: str, port: int, use_ssl: bool) -> str:
    """Build the EVCC HTTP base URL."""
    scheme = "https" if use_ssl else "http"
    return f"{scheme}://{host}:{port}"


def build_ws_url(host: str, port: int, use_ssl: bool) -> str:
    """Build the EVCC websocket URL."""
    scheme = "wss" if use_ssl else "ws"
    return f"{scheme}://{host}:{port}{WS_PATH}"


class EvccClient:
    """Long-lived EVCC client using REST snapshots and websocket updates."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        use_ssl: bool,
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self._listeners: set[Callable[[], None]] = set()
        self._ready = asyncio.Event()
        self._raw_state: dict[str, Any] | None = None
        self._available = False
        self._task: asyncio.Task[None] | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

    @property
    def raw_state(self) -> dict[str, Any] | None:
        """Return the latest raw EVCC state."""
        return self._raw_state

    @property
    def available(self) -> bool:
        """Return whether the websocket is currently connected."""
        return self._available

    def set_available(self, available: bool) -> None:
        """Set connectivity availability from coordinator-side refresh failures."""
        self._set_available(available)

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener for state updates."""
        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    async def async_start(self) -> None:
        """Start the websocket background task and wait for initial state."""
        if self._task is not None:
            return

        await self.async_refresh_state()
        self._ready.set()
        self._task = asyncio.create_task(self._run(), name="evcc_ws")
        await self.async_wait_until_ready()

    async def async_wait_until_ready(self) -> None:
        """Wait until the first valid snapshot has been received."""
        async with asyncio.timeout(CLIENT_READY_TIMEOUT):
            await self._ready.wait()

    async def async_stop(self) -> None:
        """Stop the websocket background task."""
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        if self._ws is not None:
            await self._ws.close()
            self._ws = None

        self._set_available(False)

    async def async_refresh_state(self) -> dict[str, Any]:
        """Fetch and store the canonical EVCC state snapshot."""
        state = await async_get_state(
            self._session,
            self.host,
            self.port,
            self.use_ssl,
        )
        self._raw_state = state
        self._available = True
        self._ready.set()
        self._notify_listeners()
        return state

    async def async_set_loadpoint_mode(self, loadpoint_id: int, mode: str) -> None:
        """Set one loadpoint's charging mode."""
        url = (
            f"{build_base_url(self.host, self.port, self.use_ssl)}"
            f"/api/loadpoints/{loadpoint_id}/mode/{mode}"
        )
        try:
            async with self._session.post(url) as response:
                if response.status >= 400:
                    raise CannotConnectError(
                        f"EVCC returned HTTP {response.status} for {url}"
                    )
        except aiohttp.ClientError as err:
            raise CannotConnectError from err

        await self.async_refresh_state()

    async def _run(self) -> None:
        delay = RECONNECT_INITIAL_DELAY

        while True:
            try:
                await self._listen_once()
                delay = RECONNECT_INITIAL_DELAY
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error while communicating with EVCC websocket")

            self._set_available(False)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _listen_once(self) -> None:
        await self.async_refresh_state()
        url = build_ws_url(self.host, self.port, self.use_ssl)
        _LOGGER.debug("Connecting to EVCC websocket at %s", url)

        async with self._session.ws_connect(url) as ws:
            self._ws = ws
            self._set_available(True)
            async for message in ws:
                payload = _decode_ws_message(message)
                if payload is None:
                    continue
                if not await self._handle_payload(payload):
                    await self.async_refresh_state()

    async def _handle_payload(self, payload: Any) -> bool:
        if self._raw_state is None:
            return False

        if isinstance(payload, Mapping):
            if "loadpoints" in payload:
                self._raw_state = dict(payload)
                self._notify_listeners()
                return True

            if _apply_key_value_update(self._raw_state, payload):
                self._notify_listeners()
                return True

            self._raw_state.update(payload)
            self._notify_listeners()
            return True

        if isinstance(payload, list):
            changed = False
            for item in payload:
                if isinstance(item, Mapping):
                    changed = _apply_key_value_update(self._raw_state, item) or changed
            if changed:
                self._notify_listeners()
            return changed

        _LOGGER.debug("Ignoring EVCC non-state payload: %r", payload)
        return False

    def _set_available(self, available: bool) -> None:
        if self._available == available:
            return
        self._available = available
        self._notify_listeners()

    def _notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()


async def async_probe_client(
    host: str,
    port: int,
    use_ssl: bool,
    *,
    timeout: int = CLIENT_READY_TIMEOUT,
) -> dict[str, Any]:
    """Fetch one EVCC state snapshot for config-flow validation."""
    try:
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(timeout):
                return await async_get_state(session, host, port, use_ssl)
    except InvalidStateError:
        raise
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise CannotConnectError from err


async def async_get_state(
    session: aiohttp.ClientSession,
    host: str,
    port: int,
    use_ssl: bool,
) -> dict[str, Any]:
    """Fetch the canonical EVCC state snapshot."""
    url = f"{build_base_url(host, port, use_ssl)}{STATE_PATH}"
    try:
        async with session.get(url) as response:
            if response.status >= 400:
                raise CannotConnectError(f"EVCC returned HTTP {response.status}")
            payload = await response.json()
    except aiohttp.ClientError as err:
        raise CannotConnectError from err

    if not isinstance(payload, dict) or not isinstance(payload.get("loadpoints"), list):
        raise InvalidStateError("EVCC state does not contain loadpoints")

    return payload


def _decode_ws_message(message: aiohttp.WSMessage) -> Any | None:
    if message.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED}:
        return None

    if message.type == aiohttp.WSMsgType.ERROR:
        if message.data is not None:
            raise CannotConnectError(message.data)
        return None

    if message.type != aiohttp.WSMsgType.TEXT:
        return None

    try:
        return json.loads(message.data)
    except json.JSONDecodeError:
        _LOGGER.debug("Ignoring invalid JSON websocket payload: %s", message.data)
        return None


def _apply_key_value_update(raw_state: dict[str, Any], payload: Mapping[str, Any]) -> bool:
    key = payload.get("key")
    if not isinstance(key, str):
        key = payload.get("name")
    if not isinstance(key, str):
        return False

    value = payload.get("value")
    if "value" not in payload:
        value = payload.get("val")

    _set_path(raw_state, key.replace("/", ".").split("."), value)
    return True


def _set_path(target: dict[str, Any], path: list[str], value: Any) -> None:
    current: Any = target
    for part in path[:-1]:
        if isinstance(current, list):
            index = _list_index(part)
            if index is None or index >= len(current):
                return
            current = current[index]
            continue

        if not isinstance(current, dict):
            return

        if part not in current:
            current[part] = {}
        current = current[part]

    if not path:
        return

    last = path[-1]
    if isinstance(current, list):
        index = _list_index(last)
        if index is not None and index < len(current):
            current[index] = value
        return

    if isinstance(current, dict):
        current[last] = value


def _list_index(value: str) -> int | None:
    try:
        index = int(value)
    except ValueError:
        return None
    if index <= 0:
        return None
    return index - 1


def entry_client_options(entry_data: Mapping[str, Any]) -> tuple[str, int, bool]:
    """Return normalized host, port, and SSL options from config entry data."""
    return (
        str(entry_data[CONF_HOST]),
        int(entry_data[CONF_PORT]),
        bool(entry_data.get(CONF_USE_SSL, False)),
    )
