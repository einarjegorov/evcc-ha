"""Typed normalized models for EVCC loadpoint state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class LoadpointData:
    """Normalized state for one EVCC loadpoint."""

    id: int
    title: str
    charger_ref: str | None
    meter_ref: str | None
    circuit_ref: str | None
    connected: bool | None
    charging: bool | None
    charge_power_w: float | None
    charged_energy_wh: float | None
    cumulative_energy_kwh: float | None
    mode: str | None
    vehicle_title: str | None
    vehicle_name: str | None
    raw: Mapping[str, Any]

    @property
    def key(self) -> str:
        """Return a stable storage key for this loadpoint."""
        return str(self.id)

    @property
    def stable_ref(self) -> str:
        """Return the most stable EVCC-provided reference for this loadpoint."""
        if self.charger_ref:
            return f"charger:{self.charger_ref}"
        if self.meter_ref:
            return f"meter:{self.meter_ref}"
        if self.circuit_ref:
            return f"circuit:{self.circuit_ref}"
        return f"loadpoint:{self.id}"

    @property
    def display_title(self) -> str:
        """Return a user-facing loadpoint title."""
        return self.title or f"Loadpoint {self.id}"

    @property
    def session_energy_kwh(self) -> float | None:
        """Return current EVCC session energy in kWh."""
        if self.charged_energy_wh is None:
            return None
        return round(self.charged_energy_wh / 1000, 3)


@dataclass(frozen=True, slots=True)
class NormalizedEvccData:
    """Normalized EVCC state used by Home Assistant entities."""

    available: bool
    host: str
    port: int
    use_ssl: bool
    title: str
    loadpoints: tuple[LoadpointData, ...]
    raw_state: Mapping[str, Any]

    @property
    def client_key(self) -> str:
        """Return a stable key for diagnostics and fallback identifiers."""
        return f"{self.host}:{self.port}"

    def loadpoint(self, loadpoint_id: int) -> LoadpointData | None:
        """Return one loadpoint by 1-based EVCC id."""
        for loadpoint in self.loadpoints:
            if loadpoint.id == loadpoint_id:
                return loadpoint
        return None

    def energy_key(self, loadpoint: LoadpointData) -> str:
        """Return the persisted energy key for one loadpoint."""
        return f"{self.client_key}:{loadpoint.stable_ref}"


def normalize_evcc_data(
    raw_state: Mapping[str, Any] | None,
    *,
    available: bool,
    host: str,
    port: int,
    use_ssl: bool,
    totals_kwh: Mapping[str, float] | None = None,
) -> NormalizedEvccData:
    """Normalize a raw EVCC state snapshot for Home Assistant entities."""
    totals_kwh = totals_kwh or {}
    if raw_state is None:
        return NormalizedEvccData(
            available=available,
            host=host,
            port=port,
            use_ssl=use_ssl,
            title=host,
            loadpoints=(),
            raw_state={},
        )

    loadpoints = tuple(
        _normalize_loadpoint(index, item, totals_kwh)
        for index, item in enumerate(_as_list(raw_state.get("loadpoints")), start=1)
        if isinstance(item, Mapping)
    )

    data = NormalizedEvccData(
        available=available,
        host=host,
        port=port,
        use_ssl=use_ssl,
        title=_as_str(raw_state.get("siteTitle")) or "EVCC",
        loadpoints=loadpoints,
        raw_state=raw_state,
    )
    return with_cumulative_totals(data, totals_kwh)


def with_cumulative_totals(
    data: NormalizedEvccData, totals_kwh: Mapping[str, float]
) -> NormalizedEvccData:
    """Return normalized data with updated cumulative loadpoint totals."""
    loadpoints = tuple(
        replace(
            loadpoint,
            cumulative_energy_kwh=_round_kwh(
                totals_kwh.get(
                    data.energy_key(loadpoint),
                    totals_kwh.get(loadpoint.key),
                )
            ),
        )
        for loadpoint in data.loadpoints
    )
    return replace(data, loadpoints=loadpoints)


def _normalize_loadpoint(
    index: int,
    loadpoint: Mapping[str, Any],
    totals_kwh: Mapping[str, float],
) -> LoadpointData:
    title = _as_str(loadpoint.get("title")) or f"Loadpoint {index}"
    key = str(index)
    return LoadpointData(
        id=index,
        title=title,
        charger_ref=_as_str(loadpoint.get("charger"))
        or _as_str(loadpoint.get("chargerRef")),
        meter_ref=_as_str(loadpoint.get("meter")) or _as_str(loadpoint.get("meterRef")),
        circuit_ref=_as_str(loadpoint.get("circuit"))
        or _as_str(loadpoint.get("circuitRef")),
        connected=_as_bool(loadpoint.get("connected")),
        charging=_as_bool(loadpoint.get("charging")),
        charge_power_w=_as_float(loadpoint.get("chargePower")),
        charged_energy_wh=_as_float(loadpoint.get("chargedEnergy")),
        cumulative_energy_kwh=_round_kwh(totals_kwh.get(key)),
        mode=_as_str(loadpoint.get("mode")),
        vehicle_title=_as_str(loadpoint.get("vehicleTitle")),
        vehicle_name=_as_str(loadpoint.get("vehicleName")),
        raw=loadpoint,
    )


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes", "on"}:
            return True
        if value.lower() in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, int | float):
        return bool(value)
    return None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_kwh(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)
