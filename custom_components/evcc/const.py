"""Constants for the EVCC loadpoint integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_PORT, Platform

DOMAIN = "evcc"
NAME = "EVCC Loadpoints"
MANUFACTURER = "EVCC"

CONF_USE_SSL = "use_ssl"

DEFAULT_PORT = 7070
WS_PATH = "/ws"
STATE_PATH = "/api/state"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

CLIENT_READY_TIMEOUT = 10
RECONNECT_INITIAL_DELAY = 1
RECONNECT_MAX_DELAY = 60
HEARTBEAT_INTERVAL = timedelta(seconds=60)
STATE_POLL_INTERVAL = timedelta(seconds=10)

MODE_OFF = "off"
MODE_NOW = "now"
MODE_MINPV = "minpv"
MODE_PV = "pv"
CHARGE_MODES = [MODE_OFF, MODE_NOW, MODE_MINPV, MODE_PV]
CHARGE_MODE_OPTIONS = ["Off", "Fast", "Min+PV", "PV"]
CHARGE_MODE_LABELS = {
    MODE_OFF: "Off",
    MODE_NOW: "Fast",
    MODE_MINPV: "Min+PV",
    MODE_PV: "PV",
}

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.energy"

SENSITIVE_DIAGNOSTIC_KEYS = {
    CONF_HOST,
    "host",
    "password",
    "token",
    "auth",
    "authorization",
    "cookie",
}
