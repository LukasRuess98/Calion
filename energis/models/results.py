"""Structured result containers for optimization outputs.

These dataclasses replace the loose dicts that were previously returned by
the result collector and parsed via string-pattern matching in design.py.
They provide type-safe access to optimization results, investment decisions,
and component summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Investment results (extracted from solved model)
# ---------------------------------------------------------------------------

@dataclass
class HeatPumpInvestment:
    """Investment result for a single heat pump."""

    id: str
    capacity_mw: float
    build: bool
    build_binary: float  # raw solver value (0.0–1.0)

    @property
    def enabled(self) -> bool:
        return self.build


@dataclass
class StorageInvestment:
    """Investment result for thermal storage."""

    name: str
    energy_mwh: float
    power_mw: float
    build: bool
    build_binary: float  # raw solver value

    @property
    def enabled(self) -> bool:
        return self.build


@dataclass
class InvestmentDecisions:
    """All investment decisions extracted from an optimization run.

    Replaces the string-based extraction in ``design.py`` and
    ``design_helpers._extract_design_data()``.
    """

    heat_pumps: Dict[str, HeatPumpInvestment] = field(default_factory=dict)
    storage: Optional[StorageInvestment] = None

    def to_fixed_values(self) -> Dict[str, Any]:
        """Convert to the dict format expected by ``apply_optimization_config``.

        Returns a dict with 'heat_pumps' and 'storage' keys matching
        the ``extracted_values`` parameter of
        ``design.apply_optimization_config()``.
        """
        result: Dict[str, Any] = {"heat_pumps": {}, "storage": {}}

        for hp_id, hp in self.heat_pumps.items():
            result["heat_pumps"][hp_id] = {
                "capacity_mw": hp.capacity_mw,
                "build": hp.build,
            }

        if self.storage is not None:
            result["storage"] = {
                "energy_mwh": self.storage.energy_mwh,
                "power_mw": self.storage.power_mw,
                "build": self.storage.build,
            }

        return result

    @classmethod
    def from_summary(
        cls, summary: Dict[str, Dict[str, Any]]
    ) -> InvestmentDecisions:
        """Extract investment decisions from a result summary dict.

        Replaces ``design.extract_optimization_results()`` and
        ``design_helpers._extract_design_data()`` with a single,
        type-safe extraction method.

        Parameters
        ----------
        summary
            The ``summary_sections`` dict returned by
            ``_collect_timeseries_and_summary()``, keyed by component
            section name (e.g. ``"heat_pump_HP1"``, ``"storage_TES"``).
        """
        heat_pumps: Dict[str, HeatPumpInvestment] = {}
        storage: Optional[StorageInvestment] = None

        for key, metrics in summary.items():
            if not isinstance(metrics, dict):
                continue

            if key.startswith("heat_pump_"):
                hp_id = key.split("heat_pump_", 1)[1]
                capacity = _safe_float(metrics.get("Thermal_capacity_MW"))
                build_val = _safe_float(
                    metrics.get("Build_binary", metrics.get("Build"))
                )
                heat_pumps[hp_id] = HeatPumpInvestment(
                    id=hp_id,
                    capacity_mw=capacity,
                    build=build_val >= 0.5,
                    build_binary=build_val,
                )

            elif key.startswith("storage_"):
                name = key.split("storage_", 1)[1]
                energy = _safe_float(metrics.get("Capacity_MWh"))
                power = _safe_float(metrics.get("Power_limit_MW"))
                build_val = _safe_float(
                    metrics.get("Build_binary", metrics.get("Build"))
                )
                storage = StorageInvestment(
                    name=name,
                    energy_mwh=energy,
                    power_mw=power,
                    build=build_val >= 0.5,
                    build_binary=build_val,
                )

        return cls(heat_pumps=heat_pumps, storage=storage)

    def has_decisions(self) -> bool:
        """Return True if any investment decisions were extracted."""
        return bool(self.heat_pumps) or self.storage is not None

    def to_design_spec(self) -> Any:
        """Convert to legacy ``DesignSpec`` for backward compatibility.

        Import is deferred to avoid circular dependency.
        This method exists solely to ease migration; new code should use
        :meth:`to_fixed_values` + ``apply_optimization_config`` instead.
        """
        from energis.design import DesignSpec, HeatPumpDesign, StorageDesign

        hp_specs = {
            hp_id: HeatPumpDesign(
                id=hp_id,
                capacity_mw=hp.capacity_mw,
                enabled=hp.build,
                build_binary=hp.build_binary,
            )
            for hp_id, hp in self.heat_pumps.items()
        }

        sto_spec = None
        if self.storage is not None:
            sto_spec = StorageDesign(
                capacity_mwh=self.storage.energy_mwh,
                power_mw=self.storage.power_mw,
                enabled=self.storage.build,
                build_binary=self.storage.build_binary,
            )

        return DesignSpec(heat_pumps=hp_specs, storage=sto_spec)


# ---------------------------------------------------------------------------
# Component summary
# ---------------------------------------------------------------------------

@dataclass
class ComponentSummary:
    """Summary metrics for a single component.

    A thin typed wrapper around the per-component OrderedDict that
    ``_collect_timeseries_and_summary()`` already produces.
    """

    name: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.metrics.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.metrics[key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert to float, returning *default* on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
