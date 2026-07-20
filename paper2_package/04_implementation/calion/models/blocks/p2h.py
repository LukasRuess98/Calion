from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ..component import BaseComponent, Flow
from ..registry import register_component


def _prepare_eff_series(
    indices: Iterable[int],
    series: Sequence[float] | Mapping[int, float] | None,
    default: float,
) -> dict[int, float]:
    """Prepare efficiency series for Pyomo parameters with broadcasting support."""
    idx_list = list(indices)
    if series is None:
        return {i: float(default) for i in idx_list}
    if isinstance(series, Mapping):
        return {i: float(series.get(i, default)) for i in idx_list}
    values = [float(v) for v in series]
    if len(values) == 1:
        return {i: float(values[0]) for i in idx_list}
    if len(values) != len(idx_list):
        raise ValueError("Efficiency series length does not match time index length")
    return {i: float(values[pos]) for pos, i in enumerate(idx_list)}


@register_component("p2h", category="converter", description="Power-to-Heat converter (electric boiler/resistance heater)")
class P2HBlock(BaseComponent):
    def __init__(
        self,
        name: str,
        eff: float,
        cap_th_mw: float,
        label: str | None = None,
        *,
        min_load: float = 0.0,
        eff_series: Sequence[float] | Mapping[int, float] | None = None,
        part_load_penalty: float = 0.0,
        investable: bool = False,
        capacity_min_mw: float = 0.0,
        capacity_max_mw: float | None = None,
    ):
        """Initialize P2H block with optional load-dependent efficiency.

        Args:
            name: Component name
            eff: Nominal efficiency at full load (0-1)
            cap_th_mw: Thermal capacity in MW (fixed capacity, or initial value when investable)
            label: Optional label
            min_load: Minimum load fraction (0-1), default 0.0
            eff_series: Optional time-series of efficiency values for load-dependent modeling
            part_load_penalty: Efficiency penalty at minimum load (e.g., 0.02 = 2% loss), default 0.0
            investable: If True, capacity becomes a decision variable {name}_cap_mw
                with a build binary {name}_build (Paper 2 EK investment).
            capacity_min_mw: Minimum invested capacity if built [MW].
            capacity_max_mw: Maximum invested capacity [MW]; required when investable.
        """
        super().__init__(name, label)
        self.eff = float(eff)
        self.cap = float(cap_th_mw)
        self.min_load = float(min_load)
        self.eff_series = eff_series
        self.part_load_penalty = float(part_load_penalty)
        self.investable = bool(investable)
        self.capacity_min_mw = float(capacity_min_mw)
        self.capacity_max_mw = float(capacity_max_mw) if capacity_max_mw is not None else self.cap

        if not 0.0 <= self.min_load <= 1.0:
            raise ValueError(f"min_load must be in [0, 1], got {self.min_load}")
        if not 0.0 <= self.part_load_penalty <= 0.5:
            raise ValueError(f"part_load_penalty must be in [0, 0.5], got {self.part_load_penalty}")
        if self.investable and self.capacity_max_mw <= 0:
            raise ValueError(f"Investable P2H '{name}' needs capacity_max_mw > 0")

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")
        comp = self.name

        # Variables
        setattr(m, f"{comp}_Qth", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Pel", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        Q = getattr(m, f"{comp}_Qth")
        P = getattr(m, f"{comp}_Pel")

        # Add binary on/off variable if min_load > 0
        if self.min_load > 0:
            setattr(m, f"{comp}_on", pyo.Var(Tset, domain=pyo.Binary))
            on = getattr(m, f"{comp}_on")
        else:
            on = None

        # Prepare efficiency series (time-varying or constant)
        times = list(Tset)
        eff_map = _prepare_eff_series(times, self.eff_series, self.eff)

        # Parameters
        setattr(m, f"{comp}_eff", pyo.Param(Tset, initialize=eff_map, mutable=True))
        setattr(m, f"{comp}_cap", pyo.Param(initialize=self.cap))
        setattr(m, f"{comp}_min_load", pyo.Param(initialize=self.min_load))

        # ── Investment (Paper 2 EK): capacity var + build binary ─────────────
        cap_var = None
        build = None
        if self.investable:
            setattr(m, f"{comp}_cap_mw", pyo.Var(
                domain=pyo.NonNegativeReals, bounds=(0.0, self.capacity_max_mw)))
            setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
            cap_var = getattr(m, f"{comp}_cap_mw")
            build = getattr(m, f"{comp}_build")
            cap_var.set_value(self.cap)

            def inv_cap_hi(mm):
                return cap_var <= self.capacity_max_mw * build
            setattr(m, f"{comp}_cap_hi", pyo.Constraint(rule=inv_cap_hi))

            def inv_cap_lo(mm):
                return cap_var >= self.capacity_min_mw * build
            setattr(m, f"{comp}_cap_lo", pyo.Constraint(rule=inv_cap_lo))

            if on is not None:
                def on_link(mm, t):
                    return on[t] <= build
                setattr(m, f"{comp}_on_link", pyo.Constraint(Tset, rule=on_link))

        # ── Exact linearization of cap_var * on[t] (binary × bounded continuous) ─
        # PERF FIX (2026-07-04): mirrors the heat_pump.py fix — writing this
        # product directly makes Gurobi solve a nonconvex MIQCP (verified via
        # gm.IsQCP==1) instead of a pure MILP. Exact reformulation for y∈{0,1},
        # x∈[0,x_max]: z<=x_max*y ; z<=x ; z>=x-x_max*(1-y) ; z>=0.
        cap_x_on = None
        if cap_var is not None and on is not None:
            setattr(m, f"{comp}_cap_x_on", pyo.Var(
                Tset, domain=pyo.NonNegativeReals, bounds=(0.0, self.capacity_max_mw)))
            cap_x_on = getattr(m, f"{comp}_cap_x_on")

            def _linfix_hi(mm, t):
                return cap_x_on[t] <= self.capacity_max_mw * on[t]
            setattr(m, f"{comp}_linfix_hi", pyo.Constraint(Tset, rule=_linfix_hi))

            def _linfix_le_cap(mm, t):
                return cap_x_on[t] <= cap_var
            setattr(m, f"{comp}_linfix_le_cap", pyo.Constraint(Tset, rule=_linfix_le_cap))

            def _linfix_lo(mm, t):
                return cap_x_on[t] >= cap_var - self.capacity_max_mw * (1 - on[t])
            setattr(m, f"{comp}_linfix_lo", pyo.Constraint(Tset, rule=_linfix_lo))

        # Capacity constraint
        def cap_rule(mm, t):
            if cap_var is not None:
                # invested capacity limits output; on-gating via big-M cap_max
                if on is not None:
                    return Q[t] <= self.capacity_max_mw * on[t]
                return Q[t] <= cap_var
            if on is not None:
                return Q[t] <= mm.__getattribute__(f"{comp}_cap") * on[t]
            return Q[t] <= mm.__getattribute__(f"{comp}_cap")

        if cap_var is not None:
            def cap_inv_rule(mm, t):
                return Q[t] <= cap_var
            setattr(m, f"{comp}_capinv", pyo.Constraint(Tset, rule=cap_inv_rule))

        # Minimum load constraint
        def min_load_rule(mm, t):
            if cap_x_on is not None:
                return Q[t] >= mm.__getattribute__(f"{comp}_min_load") * cap_x_on[t]
            if on is not None:
                return Q[t] >= mm.__getattribute__(f"{comp}_min_load") * mm.__getattribute__(f"{comp}_cap") * on[t]
            return pyo.Constraint.Skip

        # Efficiency link (with optional part-load penalty)
        def link(mm, t):
            eff_t = mm.__getattribute__(f"{comp}_eff")[t]
            # Simple linear approximation: Q = eff * P (maintains MILP)
            # Part-load penalty is represented through time-varying efficiency series
            return Q[t] == eff_t * P[t]

        setattr(m, f"{comp}_capcons", pyo.Constraint(Tset, rule=cap_rule))
        setattr(m, f"{comp}_minload", pyo.Constraint(Tset, rule=min_load_rule))
        setattr(m, f"{comp}_link", pyo.Constraint(Tset, rule=link))

        # Register flows with framework
        self.add_flow(Flow(
            bus="heat",
            direction="output",
            variable=Q,
            nominal_value=self.cap
        ))

        self.add_flow(Flow(
            bus="electricity",
            direction="input",
            variable=P,
            flow_type="electric_power"
        ))

        # Register with buses if available
        if buses:
            if "heat" in buses:
                buses["heat"].add_output(Q)
            if "electricity" in buses:
                buses["electricity"].add_input(P)

        # Return standardized format
        result = {
            "flows": {
                "heat": {"output": Q},
                "electricity": {"input": P}
            },
            "metadata": {
                "efficiency": self.eff,
                "capacity_th": self.cap,
                "min_load": self.min_load,
                "has_load_dependent_eff": self.eff_series is not None,
            },
            # Legacy compatibility
            "Q_th_out": Q,
            "P_el_in": P
        }

        if on is not None:
            result["on"] = on
            result["metadata"]["on_variable"] = on

        if cap_var is not None:
            result["capacity"] = cap_var
            result["build"] = build

        return result
