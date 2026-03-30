"""High-level programmatic API for building energy system models.

Inspired by PyPSA's ``Network`` class, this module provides a fluent
interface for constructing, solving, and inspecting district heating
optimisation models without touching YAML files.

Typical usage::

    from energis import Network

    net = Network(dt_h=1.0, solver="glpk")
    net.add_bus("electricity")
    net.add_bus("heat")

    net.add_heat_pump("HP1", capacity_mw=10.0, cop=3.5)
    net.add_storage("TES", energy_mwh=200.0, power_mw=40.0)
    net.add_generator("Boiler", cap_th_mw=5.0, efficiency=0.90)

    net.set_demand("heat", demand_mw=[...])
    net.set_electricity_price(prices_eur_mwh=[...])

    result = net.optimize()
    print(result.costs)
"""

from __future__ import annotations

import copy
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from energis.models.results import InvestmentDecisions
from energis.utils.timeseries import TimeSeriesTable


class Network:
    """Programmatic model builder for district heating systems.

    This class constructs a config dict and time-series table internally,
    then delegates to the existing ``build_model`` / ``_solve_scenario``
    pipeline.  It is a *convenience wrapper*, not a replacement — all
    existing YAML-based workflows remain supported.

    Parameters
    ----------
    dt_h : float
        Time step in hours (default 1.0).
    solver : str
        Solver name passed to Pyomo's ``SolverFactory`` (default ``"glpk"``).
    name : str
        Optional scenario name.
    """

    def __init__(
        self,
        dt_h: float = 1.0,
        solver: str = "glpk",
        name: str = "programmatic",
    ) -> None:
        self.dt_h = dt_h
        self.solver = solver
        self.name = name

        # Internal config that will be passed to build_model
        self._heat_pumps: List[Dict[str, Any]] = []
        self._generators: Dict[str, Dict[str, Any]] = {}
        self._storage: Optional[Dict[str, Any]] = None
        self._grid: Dict[str, Any] = {}
        self._costs: Dict[str, Any] = {}
        self._fuels: Dict[str, Dict[str, Any]] = {}

        # Network topology
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._pipes: Dict[str, Dict[str, Any]] = {}
        self._network_physics: Dict[str, Any] = {}
        self._network_temps: Dict[str, float] = {}

        # Time series (column name → values)
        self._series: Dict[str, List[float]] = {}
        self._n_steps: Optional[int] = None

    # ------------------------------------------------------------------
    # Component registration
    # ------------------------------------------------------------------

    def add_heat_pump(
        self,
        id: str,
        capacity_mw: float,
        cop: float = 3.0,
        *,
        enabled: bool = True,
        investment: bool = False,
        capacity_min_mw: float = 0.0,
        capacity_max_mw: Optional[float] = None,
    ) -> "Network":
        """Add a heat pump to the system.

        Parameters
        ----------
        id : str
            Unique heat pump identifier (e.g. ``"HP1"``).
        capacity_mw : float
            Thermal capacity in MW.
        cop : float
            Coefficient of performance (constant).
        enabled : bool
            Whether the heat pump is initially enabled.
        investment : bool
            Whether investment optimisation is enabled for this unit.
        capacity_min_mw : float
            Minimum capacity bound for investment mode.
        capacity_max_mw : float, optional
            Maximum capacity bound (defaults to ``capacity_mw``).
        """
        hp: Dict[str, Any] = {
            "id": id,
            "enabled": enabled,
            "max_th_mw": capacity_mw,
            "min_th_mw": 0.0,
            "cop_default": cop,
            "type": "standard",
        }
        if investment:
            hp["investment"] = {
                "enabled": True,
                "capacity_min_mw": capacity_min_mw,
                "capacity_max_mw": capacity_max_mw or capacity_mw,
            }
        self._heat_pumps.append(hp)
        return self

    def add_storage(
        self,
        id: str = "TES",
        energy_mwh: float = 100.0,
        power_mw: float = 20.0,
        *,
        eta_charge: float = 0.95,
        eta_discharge: float = 0.95,
        soc_init_mwh: float = 0.0,
        self_discharge_rate: float = 0.0,
        investment: bool = False,
    ) -> "Network":
        """Add thermal energy storage.

        Parameters
        ----------
        id : str
            Storage identifier.
        energy_mwh : float
            Energy capacity in MWh.
        power_mw : float
            Charge/discharge power limit in MW.
        eta_charge, eta_discharge : float
            Round-trip efficiencies (0–1).
        soc_init_mwh : float
            Initial state of charge.
        self_discharge_rate : float
            Hourly self-discharge fraction (0–1).
        investment : bool
            Enable investment optimisation for storage sizing.
        """
        self._storage = {
            "enabled": True,
            "id": id,
            "energy_mwh": energy_mwh,
            "power_mw": power_mw,
            "eta_charge": eta_charge,
            "eta_discharge": eta_discharge,
            "soc_init_mwh": soc_init_mwh,
            "self_discharge_rate": self_discharge_rate,
        }
        if investment:
            self._storage["investment"] = {
                "enabled": True,
                "energy_capacity_max_mwh": energy_mwh,
                "power_capacity_max_mw": power_mw,
            }
        return self

    def add_generator(
        self,
        id: str,
        cap_th_mw: float,
        *,
        fuel_bus: str = "electricity",
        efficiency: float = 0.99,
        enabled: bool = True,
    ) -> "Network":
        """Add a thermal generator (P2H / boiler / CHP).

        Parameters
        ----------
        id : str
            Generator identifier.
        cap_th_mw : float
            Thermal output capacity in MW.
        fuel_bus : str
            Fuel bus name (``"electricity"``, ``"gas"``, etc.).
        efficiency : float
            Thermal efficiency (fuel → heat).
        enabled : bool
            Whether the generator is initially enabled.
        """
        self._generators[id] = {
            "enabled": enabled,
            "cap_th_mw": cap_th_mw,
            "fuel_bus": fuel_bus,
            "th_eff": efficiency,
        }
        return self

    # ------------------------------------------------------------------
    # Network topology
    # ------------------------------------------------------------------

    def set_network_temps(
        self,
        supply_temp_c: float = 90.0,
        return_temp_c: float = 55.0,
        ground_temp_c: float = 10.0,
    ) -> "Network":
        """Set network temperature parameters."""
        self._network_temps = {
            "supply_temp_c": supply_temp_c,
            "return_temp_c": return_temp_c,
            "ground_temp_c": ground_temp_c,
        }
        return self

    def set_network_physics(
        self,
        heat_loss: bool = True,
        pressure_drop: bool = False,
        transport_delay: bool = False,
    ) -> "Network":
        """Enable/disable network physics features."""
        self._network_physics = {
            "heat_loss": heat_loss,
            "pressure_drop": pressure_drop,
            "transport_delay": transport_delay,
        }
        return self

    def add_node(
        self,
        id: str,
        type: str = "junction",
        *,
        assets: Optional[List[str]] = None,
        demand_fraction: Optional[float] = None,
        demand_column: Optional[str] = None,
        peak_demand_mw: Optional[float] = None,
    ) -> "Network":
        """Add a network node (producer, consumer, or junction).

        Parameters
        ----------
        id : str
            Unique node identifier.
        type : str
            One of ``"producer"``, ``"consumer"``, ``"junction"``.
        assets : list of str, optional
            Component IDs attached to this node.
        demand_fraction : float, optional
            Fraction of global heat demand served by this consumer (0–1).
            Required for consumer nodes when using network topology.
        demand_column : str, optional
            Time-series column name for consumer demand.
        peak_demand_mw : float, optional
            Peak demand for consumer nodes.
        """
        node: Dict[str, Any] = {"type": type}
        if assets:
            node["assets"] = assets
        if demand_fraction is not None:
            node["demand_fraction"] = demand_fraction
        if demand_column or peak_demand_mw:
            demand: Dict[str, Any] = {}
            if demand_column:
                demand["column"] = demand_column
            if peak_demand_mw is not None:
                demand["peak_demand_mw"] = peak_demand_mw
            node["demand"] = demand
        self._nodes[id] = node
        return self

    def add_pipe(
        self,
        id: str,
        from_node: str,
        to_node: str,
        length_m: float,
        diameter_mm: float = 300,
        *,
        u_value_w_per_m_k: Optional[float] = None,
        burial_depth_m: Optional[float] = None,
    ) -> "Network":
        """Add a pipe connecting two nodes.

        Parameters
        ----------
        id : str
            Unique pipe identifier.
        from_node, to_node : str
            Node IDs at pipe endpoints.
        length_m : float
            Pipe length in metres.
        diameter_mm : float
            Inner pipe diameter in mm.
        u_value_w_per_m_k : float, optional
            Overall heat transfer coefficient [W/(m·K)].
        burial_depth_m : float, optional
            Pipe burial depth in metres.
        """
        pipe: Dict[str, Any] = {
            "from": from_node,
            "to": to_node,
            "length_m": length_m,
            "diameter_mm": diameter_mm,
        }
        if u_value_w_per_m_k is not None:
            pipe["u_value_w_per_m_k"] = u_value_w_per_m_k
        if burial_depth_m is not None:
            pipe["burial_depth_m"] = burial_depth_m
        self._pipes[id] = pipe
        return self

    def set_fuel(
        self,
        name: str,
        price_eur_mwh: float,
        ef_kg_per_mwh_fuel: float = 0.0,
    ) -> "Network":
        """Define a fuel type and its cost/emissions."""
        self._fuels[name] = {
            "price_eur_mwh": price_eur_mwh,
            "ef_kg_per_mwh_fuel": ef_kg_per_mwh_fuel,
        }
        return self

    # ------------------------------------------------------------------
    # Grid / cost parameters
    # ------------------------------------------------------------------

    def set_grid(
        self,
        max_import_mw: float = 1e4,
        max_export_mw: float = 1e4,
        demand_charge_eur_per_mw_y: float = 0.0,
    ) -> "Network":
        """Configure grid connection parameters."""
        self._grid.update({
            "max_import_mw": max_import_mw,
            "max_export_mw": max_export_mw,
            "demand_charge_eur_per_mw_y": demand_charge_eur_per_mw_y,
        })
        return self

    def set_costs(
        self,
        co2_price_eur_per_t: float = 100.0,
        dump_cost_eur_per_mwh_th: float = 1.0,
    ) -> "Network":
        """Configure cost parameters."""
        self._costs.update({
            "co2_price_eur_per_t": co2_price_eur_per_t,
            "dump_cost_eur_per_mwh_th": dump_cost_eur_per_mwh_th,
        })
        return self

    # ------------------------------------------------------------------
    # Time series
    # ------------------------------------------------------------------

    def set_demand(self, values: Sequence[float]) -> "Network":
        """Set heat demand time series (MW)."""
        self._set_series("waermebedarf_MWth", values)
        return self

    def set_electricity_price(self, values: Sequence[float]) -> "Network":
        """Set electricity price time series (EUR/MWh)."""
        self._set_series("strompreis_EUR_MWh", values)
        return self

    def set_grid_co2(self, values: Sequence[float]) -> "Network":
        """Set grid CO₂ intensity time series (kg/MWh)."""
        self._set_series("grid_co2_kg_MWh", values)
        return self

    def set_cop_series(self, hp_id: str, values: Sequence[float]) -> "Network":
        """Set a time-varying COP series for a specific heat pump."""
        self._set_series(f"cop_{hp_id}", values)
        return self

    def _set_series(self, name: str, values: Sequence[float]) -> None:
        vals = list(values)
        if self._n_steps is None:
            self._n_steps = len(vals)
        elif len(vals) != self._n_steps:
            raise ValueError(
                f"Series '{name}' has {len(vals)} steps, expected {self._n_steps}"
            )
        self._series[name] = vals

    # ------------------------------------------------------------------
    # Build config + table
    # ------------------------------------------------------------------

    def _build_config(self) -> Dict[str, Any]:
        """Assemble the internal config dict."""
        cfg: Dict[str, Any] = {
            "scenario": {"name": self.name, "workflow": ["PF"], "run_mode": "PF_ONLY"},
            "run": {"dt_h": self.dt_h, "solver": self.solver},
            "grid": self._grid or {},
            "costs": self._costs or {},
            "system": {},
        }

        if self._heat_pumps:
            cfg["system"]["heat_pumps"] = self._heat_pumps

        if self._storage:
            cfg["system"]["storage"] = self._storage

        if self._generators:
            cfg["system"]["generators"] = self._generators

        if self._fuels:
            cfg["fuels"] = copy.deepcopy(self._fuels)

        # Network topology → thermal_network block for NetworkManager
        if self._nodes and self._pipes:
            # Auto-distribute demand fractions among consumers if not set
            consumers = [
                nid for nid, nd in self._nodes.items()
                if nd.get("type") == "consumer"
            ]
            consumers_without_fraction = [
                nid for nid in consumers
                if self._nodes[nid].get("demand_fraction") is None
            ]
            if consumers_without_fraction:
                # Compute remaining fraction after explicit fractions
                used = sum(
                    self._nodes[nid].get("demand_fraction", 0.0)
                    for nid in consumers
                    if self._nodes[nid].get("demand_fraction") is not None
                )
                remaining = max(0.0, 1.0 - used)
                auto_frac = remaining / len(consumers_without_fraction) if consumers_without_fraction else 0.0
                for nid in consumers_without_fraction:
                    self._nodes[nid]["demand_fraction"] = round(auto_frac, 6)

            nodes_list = []
            for nid, ndata in self._nodes.items():
                node_entry: Dict[str, Any] = {
                    "id": nid,
                    "type": ndata.get("type", "junction"),
                }
                # Attach component references for producer nodes
                assets = ndata.get("assets", [])
                if assets:
                    node_entry["components"] = assets
                # Consumer demand fraction (required by ThermalNodeBlock)
                if ndata.get("demand_fraction") is not None:
                    node_entry["demand_fraction"] = ndata["demand_fraction"]
                nodes_list.append(node_entry)

            pipes_list = []
            for pid, pdata in self._pipes.items():
                pipe_entry: Dict[str, Any] = {
                    "id": pid,
                    "from_node": pdata["from"],
                    "to_node": pdata["to"],
                    "length_m": pdata["length_m"],
                    "current_diameter_supply_mm": pdata.get("diameter_mm", 300),
                    "diameter_mm": pdata.get("diameter_mm", 300),
                }
                if "u_value_w_per_m_k" in pdata:
                    pipe_entry["u_value_supply_w_per_m_k"] = pdata["u_value_w_per_m_k"]
                    pipe_entry["u_value_return_w_per_m_k"] = pdata["u_value_w_per_m_k"]
                if "burial_depth_m" in pdata:
                    pipe_entry["burial_depth_m"] = pdata["burial_depth_m"]
                pipes_list.append(pipe_entry)

            temps = self._network_temps or {}
            physics = self._network_physics or {}
            cfg["thermal_network"] = {
                "enabled": True,
                "milp_linearize": True,
                "nodes": nodes_list,
                "pipes": pipes_list,
                "parameters": {
                    "supply_temp_nominal_c": temps.get("supply_temp_c", 90.0),
                    "return_temp_nominal_c": temps.get("return_temp_c", 55.0),
                    "ground_temp_default_c": temps.get("ground_temp_c", 10.0),
                },
                "heat_loss_enabled": physics.get("heat_loss", True),
                "pressure_drop_enabled": physics.get("pressure_drop", False),
                "transport_delay_enabled": physics.get("transport_delay", False),
            }

        return cfg

    def _build_table(self) -> TimeSeriesTable:
        """Assemble the internal TimeSeriesTable."""
        n = self._n_steps
        if n is None or n == 0:
            raise ValueError("No time series data set. Call set_demand() first.")

        # Ensure required columns exist with defaults
        if "waermebedarf_MWth" not in self._series:
            raise ValueError("Heat demand is required. Call set_demand().")
        if "strompreis_EUR_MWh" not in self._series:
            self._series["strompreis_EUR_MWh"] = [50.0] * n  # default 50 EUR/MWh
        if "grid_co2_kg_MWh" not in self._series:
            self._series["grid_co2_kg_MWh"] = [400.0] * n  # default 400 kg/MWh

        start = datetime(2023, 1, 1)
        index = [start + timedelta(hours=i * self.dt_h) for i in range(n)]
        columns = list(self._series.keys())
        data = {k: v[:] for k, v in self._series.items()}

        return TimeSeriesTable(index=index, columns=columns, data=data)

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------

    def optimize(self) -> "NetworkResult":
        """Build the Pyomo model, solve, and return structured results.

        Returns
        -------
        NetworkResult
            Wrapper around :class:`~energis.run.types.ScenarioResult` with
            convenience accessors.

        Raises
        ------
        RuntimeError
            If the solver is not available or the model is infeasible.
        """
        from energis.run.solver import _solve_scenario

        cfg = self._build_config()
        table = self._build_table()

        result = _solve_scenario(table, cfg, self.dt_h, self.solver)
        return NetworkResult(result)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        parts = [f"Network(dt_h={self.dt_h}, solver={self.solver!r})"]
        if self._heat_pumps:
            parts.append(f"  heat_pumps: {len(self._heat_pumps)}")
        if self._generators:
            parts.append(f"  generators: {len(self._generators)}")
        if self._storage:
            parts.append(f"  storage: {self._storage.get('id', 'TES')}")
        if self._nodes:
            parts.append(f"  nodes: {len(self._nodes)}")
        if self._pipes:
            parts.append(f"  pipes: {len(self._pipes)}")
        if self._n_steps:
            parts.append(f"  time_steps: {self._n_steps}")
        return "\n".join(parts)


class NetworkResult:
    """Convenience wrapper around a :class:`ScenarioResult`.

    Attributes
    ----------
    scenario : ScenarioResult
        The underlying raw result object.
    costs : dict
        Cost breakdown dictionary.
    series : OrderedDict
        Time series results (column → values).
    investments : InvestmentDecisions or None
        Structured investment decisions (if applicable).
    """

    def __init__(self, scenario_result: Any) -> None:
        self.scenario = scenario_result
        self.costs = scenario_result.costs
        self.series = scenario_result.series
        self.summary = scenario_result.summary
        self.investments = scenario_result.investments
        self.solver = scenario_result.solver

    @property
    def is_optimal(self) -> bool:
        """Return True if the solver found an optimal solution."""
        tc = str(self.solver.get("termination_condition", "")).lower()
        return "optimal" in tc

    def get_series(self, name: str) -> List[float]:
        """Get a named time series from the results."""
        if name not in self.series:
            available = list(self.series.keys())
            raise KeyError(f"Series '{name}' not found. Available: {available}")
        return self.series[name]

    def total_cost(self) -> float:
        """Return total system cost (objective value in EUR)."""
        # Try standard key first, then the objective-prefixed key
        c = self.costs
        return float(
            c.get("total_cost_eur",
                   c.get("objective.OBJ_value_EUR", 0.0))
        )

    def co2_total_t(self) -> float:
        """Return total CO2 emissions in tonnes."""
        return float(self.costs.get("grid.Total_CO2_emissions_t", 0.0))

    def fuel_cost(self) -> float:
        """Return total fuel cost."""
        return float(self.costs.get("objective.Fuel_cost_EUR", 0.0))

    def grid_cost(self) -> float:
        """Return grid energy cost."""
        return float(self.costs.get("objective.Grid_energy_cost_EUR", 0.0))

    def co2_cost(self) -> float:
        """Return CO2 cost."""
        return float(self.costs.get("objective.CO2_cost_EUR", 0.0))

    def __repr__(self) -> str:
        status = "optimal" if self.is_optimal else self.solver.get("termination_condition", "?")
        return f"NetworkResult(status={status}, cost={self.total_cost():,.0f} EUR)"
