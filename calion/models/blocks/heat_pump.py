from __future__ import annotations

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ...constants import COP_DEFAULT, COP_MAX_HEATPUMP, COP_MIN
from ..component import BaseComponent, Flow, InvestmentResult
from ..registry import register_component


@register_component("heat_pump", category="converter", description="Heat pump with COP series and waste heat recovery")
class HeatPumpBlock(BaseComponent):
    def __init__(
        self,
        name: str,
        min_load: float,
        cop_series: list[float],
        *,
        capacity_min_mw: float,
        capacity_max_mw: float,
        capacity_init_mw: float,
        investable: bool,
        wrg_cap_series: dict[int, float] | None = None,
        cop_default: float = COP_DEFAULT,
        label: str | None = None
    ):
        super().__init__(name, label)
        self.min_load = float(min_load)

        # Validate and clamp COP values to safe ranges
        cop_list = []
        for c in cop_series:
            cop_val = float(c)
            if cop_val < COP_MIN:
                raise ValueError(f"Heat pump COP must be >= {COP_MIN} to avoid division by zero, got {cop_val}")
            if cop_val > COP_MAX_HEATPUMP:
                raise ValueError(f"Heat pump COP suspiciously high (> {COP_MAX_HEATPUMP}), got {cop_val}")
            cop_list.append(cop_val)
        self.COP_series = cop_list

        self.capacity_min_mw = float(capacity_min_mw)
        self.capacity_max_mw = float(capacity_max_mw)
        self.capacity_init_mw = float(capacity_init_mw)
        self.investable = bool(investable)
        self.wrg_cap_series = wrg_cap_series or {}

        # Validate default COP
        cop_default_val = float(cop_default) if cop_default else COP_DEFAULT
        if cop_default_val < COP_MIN:
            raise ValueError(f"Heat pump default COP must be >= {COP_MIN}, got {cop_default_val}")
        self.cop_default = cop_default_val

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")
        # Create variables
        comp = self.name
        setattr(m, f"{comp}_Q", pyo.Var(Tset, domain=pyo.NonNegativeReals))  # heat out
        setattr(m, f"{comp}_Q_wrg", pyo.Var(Tset, domain=pyo.NonNegativeReals))  # heat from WRG
        setattr(m, f"{comp}_Q_def", pyo.Var(Tset, domain=pyo.NonNegativeReals))  # fallback heat
        setattr(m, f"{comp}_on", pyo.Var(Tset, domain=pyo.Binary))
        setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
        # When investment is disabled, capacity is fixed - ensure bounds accommodate the fixed value
        effective_cap_max = max(self.capacity_max_mw, self.capacity_init_mw) if not self.investable else self.capacity_max_mw
        setattr(
            m,
            f"{comp}_cap_mw",
            pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, effective_cap_max)),
        )

        Q = getattr(m, f"{comp}_Q")
        Q_wrg = getattr(m, f"{comp}_Q_wrg")
        Q_def = getattr(m, f"{comp}_Q_def")
        onv = getattr(m, f"{comp}_on")
        build = getattr(m, f"{comp}_build")
        cap = getattr(m, f"{comp}_cap_mw")

        # Params
        setattr(m, f"{comp}_minload", pyo.Param(initialize=self.min_load))
        COPp = pyo.Param(Tset, initialize={t: self.COP_series[t-1] for t in Tset}, mutable=False)
        setattr(m, f"{comp}_COP", COPp)
        setattr(m, f"{comp}_COP_default", pyo.Param(initialize=self.cop_default, mutable=False))
        COP_def = getattr(m, f"{comp}_COP_default")

        if not self.investable:
            build.fix(1 if self.capacity_init_mw > 0 else 0)
            cap.fix(self.capacity_init_mw)
        else:
            cap.set_value(self.capacity_init_mw)

        setattr(m, f"{comp}_cap_min", pyo.Param(initialize=self.capacity_min_mw))
        setattr(m, f"{comp}_cap_max", pyo.Param(initialize=self.capacity_max_mw))

        # Constraints
        def cap_rule(mm, t):
            return Q[t] <= cap * onv[t]
        setattr(m, f"{comp}_cap", pyo.Constraint(Tset, rule=cap_rule))

        def min_rule(mm, t):
            return Q[t] >= mm.__getattribute__(f"{comp}_minload") * cap * onv[t]
        setattr(m, f"{comp}_min", pyo.Constraint(Tset, rule=min_rule))

        def split_balance(mm, t):
            return Q[t] == Q_wrg[t] + Q_def[t]
        setattr(m, f"{comp}_split_balance", pyo.Constraint(Tset, rule=split_balance))

        def pel_expr_rule(mm, t):
            return Q_wrg[t] / mm.__getattribute__(f"{comp}_COP")[t] + Q_def[t] / COP_def

        Pel_expr = pyo.Expression(Tset, rule=pel_expr_rule)
        setattr(m, f"{comp}_Pel", Pel_expr)

        def cap_hi(mm):
            return cap <= mm.__getattribute__(f"{comp}_cap_max") * build
        setattr(m, f"{comp}_cap_hi", pyo.Constraint(rule=cap_hi))

        def cap_lo(mm):
            return cap >= mm.__getattribute__(f"{comp}_cap_min") * build
        setattr(m, f"{comp}_cap_lo", pyo.Constraint(rule=cap_lo))

        def mode_link(mm, t):
            return onv[t] <= build
        setattr(m, f"{comp}_mode_link", pyo.Constraint(Tset, rule=mode_link))

        if self.wrg_cap_series:
            wrg_param = pyo.Param(Tset, initialize=self.wrg_cap_series, mutable=False)
            setattr(m, f"{comp}_WRG_cap", wrg_param)

            def wrg_rule(mm, t):
                return Q_wrg[t] <= wrg_param[t]

            setattr(m, f"{comp}_wrg_limit", pyo.Constraint(Tset, rule=wrg_rule))

        # Register flows with framework
        self.add_flow(Flow(
            bus="heat",
            direction="output",
            variable=Q,
            nominal_value=self.capacity_max_mw,
            investment=self.investable
        ))

        self.add_flow(Flow(
            bus="electricity",
            direction="input",
            variable=Pel_expr,
            flow_type="electric_power"
        ))

        # Register with buses if available
        if buses:
            if "heat" in buses:
                buses["heat"].add_output(Q)
            if "electricity" in buses:
                buses["electricity"].add_input(Pel_expr)

        # Return standardized format
        return {
            "flows": {
                "heat": {"output": Q},
                "electricity": {"input": Pel_expr}
            },
            "investment": InvestmentResult(
                capacity=cap,
                build=build
            ) if self.investable else None,
            "metadata": {
                "Q_wrg": Q_wrg,
                "Q_def": Q_def,
                "min_load": self.min_load,
                "cop_default": self.cop_default
            },
            # Legacy compatibility - keep old keys for now
            "Q_th_out": Q,
            "P_el_in": Pel_expr,
            "build": build,
            "capacity": cap,
            "Q_wrg": Q_wrg,
            "Q_def": Q_def,
        }

