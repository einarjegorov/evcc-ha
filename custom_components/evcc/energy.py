"""Persistent cumulative energy tracking for EVCC loadpoints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import LoadpointData, NormalizedEvccData


@dataclass(slots=True)
class EvccEnergyTotals:
    """Track monotonic cumulative energy totals by integrating charge power."""

    totals_kwh: dict[str, float] = field(default_factory=dict)
    _last_observed: dict[str, datetime] = field(default_factory=dict)

    @classmethod
    def from_stored(cls, stored: Mapping[str, object] | None) -> EvccEnergyTotals:
        """Create totals from persisted storage data."""
        totals: dict[str, float] = {}
        if isinstance(stored, Mapping):
            raw_totals = stored.get("totals_kwh")
            if isinstance(raw_totals, Mapping):
                for key, value in raw_totals.items():
                    number = _as_float(value)
                    if number is not None:
                        totals[str(key)] = number
        return cls(totals_kwh=totals)

    def as_stored(self) -> dict[str, object]:
        """Return the storage representation."""
        return {"totals_kwh": dict(self.totals_kwh)}

    def observe(
        self,
        data: NormalizedEvccData,
        now: datetime | None = None,
    ) -> bool:
        """Integrate current charge power into cumulative totals.

        Returns true when persisted totals changed.
        """
        now = now or datetime.now(UTC)
        changed = False
        for loadpoint in data.loadpoints:
            key, migrated = self._resolve_key(data, loadpoint)
            changed = changed or migrated
            previous = self._last_observed.get(key)
            self._last_observed[key] = now

            if not data.available:
                continue

            power_w = loadpoint.charge_power_w
            if power_w is None or power_w <= 0:
                if key not in self.totals_kwh:
                    self.totals_kwh[key] = 0.0
                    changed = True
                continue

            if key not in self.totals_kwh:
                self.totals_kwh[key] = 0.0
                changed = True

            if previous is None:
                continue

            elapsed_seconds = (now - previous).total_seconds()
            if elapsed_seconds <= 0:
                continue

            self.totals_kwh[key] += (power_w * elapsed_seconds) / 3_600_000
            changed = True

        return changed

    def _resolve_key(
        self,
        data: NormalizedEvccData,
        loadpoint: LoadpointData,
    ) -> tuple[str, bool]:
        key = data.energy_key(loadpoint)
        legacy_key = loadpoint.key
        changed = False

        if key not in self.totals_kwh and legacy_key in self.totals_kwh:
            self.totals_kwh[key] = self.totals_kwh.pop(legacy_key)
            changed = True

        if key not in self._last_observed and legacy_key in self._last_observed:
            self._last_observed[key] = self._last_observed.pop(legacy_key)

        return key, changed


class EvccEnergyStore:
    """Home Assistant storage wrapper for cumulative energy totals."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, object]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self.totals = EvccEnergyTotals()

    async def async_load(self) -> None:
        """Load totals from storage."""
        self.totals = EvccEnergyTotals.from_stored(await self._store.async_load())

    async def async_save(self) -> None:
        """Persist totals to storage."""
        await self._store.async_save(self.totals.as_stored())


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
