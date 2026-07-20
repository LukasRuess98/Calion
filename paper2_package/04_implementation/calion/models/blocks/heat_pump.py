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
        min_uptime_h: float = 0.0,
        min_downtime_h: float = 0.0,
        cop_charge_series: list[float] | None = None,
        label: str | None = None
    ):
        super().__init__(name, label)
        self.min_load = float(min_load)
        self.min_uptime_h = float(min_uptime_h)
        self.min_downtime_h = float(min_downtime_h)

        # Hot-charging channel (Paper 2 F2): optional second COP series for heat
        # delivered at T_charge > T_VL(t) (TES charging). When set, a Q_hot(t)
        # output channel is created that shares the installed capacity but pays
        # electricity at the (lower) charging COP.
        self.cop_charge_series: list[float] | None = None
        if cop_charge_series is not None:
            charge_list = []
            for c in cop_charge_series:
                cv = float(c)
                if cv < COP_MIN:
                    raise ValueError(f"Hot-charging COP must be >= {COP_MIN}, got {cv}")
                if cv > COP_MAX_HEATPUMP:
                    raise ValueError(f"Hot-charging COP suspiciously high (> {COP_MAX_HEATPUMP}), got {cv}")
                charge_list.append(cv)
            self.cop_charge_series = charge_list

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
        times = list(Tset)
        if len(self.COP_series) == 1:
            cop_map = {t: self.COP_series[0] for t in times}
        elif len(self.COP_series) != len(times):
            raise ValueError(
                f"Heat pump '{comp}' COP series length ({len(self.COP_series)}) "
                f"does not match time index length ({len(times)})"
            )
        else:
            cop_map = {t: self.COP_series[i] for i, t in enumerate(times)}
        COPp = pyo.Param(Tset, initialize=cop_map, mutable=False)
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

        # ── Exact linearization of cap * onv[t] (binary × bounded continuous) ──
        # PERF FIX (2026-07-04): this product was previously written directly as
        # `cap * onv[t]` in cap_rule/min_rule, which Pyomo builds as a genuine
        # quadratic expression. Verified via direct Gurobi inspection that this
        # makes the model IsQCP=1 (72 quadratic constraints in a 1-day Stadtbach
        # test) rather than a pure MILP — nonconvex spatial branching is far more
        # expensive than LP-based branch-and-bound and is the likely root cause
        # of multi-hour solves on HP-investment scenarios (e.g. MM-S2, ~24h).
        # Standard exact (not relaxed) reformulation for y∈{0,1}, x∈[0,x_max]:
        #   z <= x_max * y ;  z <= x ;  z >= x - x_max*(1-y) ;  z >= 0
        cap_max_bound = max(self.capacity_max_mw, self.capacity_init_mw, 1e-9)
        setattr(m, f"{comp}_cap_x_on", pyo.Var(
            Tset, domain=pyo.NonNegativeReals, bounds=(0.0, cap_max_bound)))
        cap_x_on = getattr(m, f"{comp}_cap_x_on")

        def _linfix_hi(mm, t):
            return cap_x_on[t] <= cap_max_bound * onv[t]
        setattr(m, f"{comp}_linfix_hi", pyo.Constraint(Tset, rule=_linfix_hi))

        def _linfix_le_cap(mm, t):
            return cap_x_on[t] <= cap
        setattr(m, f"{comp}_linfix_le_cap", pyo.Constraint(Tset, rule=_linfix_le_cap))

        def _linfix_lo(mm, t):
            return cap_x_on[t] >= cap - cap_max_bound * (1 - onv[t])
        setattr(m, f"{comp}_linfix_lo", pyo.Constraint(Tset, rule=_linfix_lo))

        # ── Hot-charging channel (optional) ───────────────────────────────────
        # Q_hot(t): heat delivered at T_charge (for TES charging), sharing the
        # installed capacity with the network channel Q(t) but priced at the
        # charging COP. Modeling note: the WRG quantity limit is applied to the
        # network channel only; the charging COP series already reflects the
        # hourly source (waste heat or ambient fallback) via its precompute.
        Q_hot = None
        COP_hot = None
        if self.cop_charge_series is not None:
            setattr(m, f"{comp}_Q_hot", pyo.Var(Tset, domain=pyo.NonNegativeReals))
            Q_hot = getattr(m, f"{comp}_Q_hot")
            times_hot = list(Tset)
            if len(self.cop_charge_series) == 1:
                cop_hot_map = {t: self.cop_charge_series[0] for t in times_hot}
            elif len(self.cop_charge_series) != len(times_hot):
                raise ValueError(
                    f"Heat pump '{comp}' charge-COP series length "
                    f"({len(self.cop_charge_series)}) does not match time index "
                    f"length ({len(times_hot)})"
                )
            else:
                cop_hot_map = {t: self.cop_charge_series[i] for i, t in enumerate(times_hot)}
            COP_hot = pyo.Param(Tset, initialize=cop_hot_map, mutable=False)
            setattr(m, f"{comp}_COP_hot", COP_hot)

        # Constraints
        def cap_rule(mm, t):
            if Q_hot is not None:
                return Q[t] + Q_hot[t] <= cap_x_on[t]
            return Q[t] <= cap_x_on[t]
        setattr(m, f"{comp}_cap", pyo.Constraint(Tset, rule=cap_rule))

        def min_rule(mm, t):
            if Q_hot is not None:
                return Q[t] + Q_hot[t] >= mm.__getattribute__(f"{comp}_minload") * cap_x_on[t]
            return Q[t] >= mm.__getattribute__(f"{comp}_minload") * cap_x_on[t]
        setattr(m, f"{comp}_min", pyo.Constraint(Tset, rule=min_rule))

        def split_balance(mm, t):
            return Q[t] == Q_wrg[t] + Q_def[t]
        setattr(m, f"{comp}_split_balance", pyo.Constraint(Tset, rule=split_balance))

        def pel_expr_rule(mm, t):
            base = Q_wrg[t] / mm.__getattribute__(f"{comp}_COP")[t] + Q_def[t] / COP_def
            if Q_hot is not None:
                return base + Q_hot[t] / COP_hot[t]
            return base

        Pel_expr = pyo.Expression(Tset, rule=pel_expr_rule)
        setattr(m, f"{comp}_Pel", Pel_expr)

        if self.investable:
            # When fixed (non-investable), cap is already fixed to cap_init_mw
            # and build is fixed to 0 or 1 — no constraint needed, and
            # capacity_max_mw: 0 from scenario overrides would make it infeasible.
            def cap_hi(mm):
                return cap <= mm.__getattribute__(f"{comp}_cap_max") * build
            setattr(m, f"{comp}_cap_hi", pyo.Constraint(rule=cap_hi))

        def cap_lo(mm):
            return cap >= mm.__getattribute__(f"{comp}_cap_min") * build
        setattr(m, f"{comp}_cap_lo", pyo.Constraint(rule=cap_lo))

        def mode_link(mm, t):
            return onv[t] <= build
        setattr(m, f"{comp}_mode_link", pyo.Constraint(Tset, rule=mode_link))

        # ── Min Uptime / Downtime (unit commitment) ────────────────────────────
        dt_h_model = float(getattr(m, 'dt_h', 1.0))
        L = max(0, round(self.min_uptime_h / dt_h_model))   # uptime in timesteps
        D = max(0, round(self.min_downtime_h / dt_h_model))  # downtime in timesteps

        if L > 0 or D > 0:
            time_list = sorted(list(Tset))
            t_idx = {t: i for i, t in enumerate(time_list)}  # O(1) lookup — avoids O(N²) list.index()

            # Startup (u) and shutdown (v) binary variables
            u = pyo.Var(Tset, domain=pyo.Binary)
            v = pyo.Var(Tset, domain=pyo.Binary)
            setattr(m, f"{comp}_u", u)
            setattr(m, f"{comp}_v", v)

            # (1) State transition: y[t] - y[t-1] = u[t] - v[t]
            def state_transition_rule(mm, t, _tl=time_list, _ti=t_idx):
                idx = _ti[t]
                if idx == 0:
                    return pyo.Constraint.Skip
                t_prev = _tl[idx - 1]
                return onv[t] - onv[t_prev] == u[t] - v[t]
            setattr(m, f"{comp}_state_transition",
                    pyo.Constraint(Tset, rule=state_transition_rule))

            # (2) Cannot start up and shut down simultaneously
            def no_simultaneous_rule(mm, t):
                return u[t] + v[t] <= 1
            setattr(m, f"{comp}_no_simultaneous",
                    pyo.Constraint(Tset, rule=no_simultaneous_rule))

            # (3) Min uptime: sum of startups in [t-L+1..t] <= y[t]
            if L > 0:
                def min_uptime_rule(mm, t, _tl=time_list, _ti=t_idx):
                    idx = _ti[t]
                    start = max(0, idx - L + 1)
                    return sum(u[_tl[k]] for k in range(start, idx + 1)) <= onv[t]
                setattr(m, f"{comp}_min_uptime",
                        pyo.Constraint(Tset, rule=min_uptime_rule))

            # (4) Min downtime: sum of shutdowns in [t-D+1..t] <= 1 - y[t]
            if D > 0:
                def min_downtime_rule(mm, t, _tl=time_list, _ti=t_idx):
                    idx = _ti[t]
                    start = max(0, idx - D + 1)
                    return sum(v[_tl[k]] for k in range(start, idx + 1)) <= 1 - onv[t]
                setattr(m, f"{comp}_min_downtime",
                        pyo.Constraint(Tset, rule=min_downtime_rule))

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
            "Q_hot": Q_hot,   # None unless cop_charge_series was provided
        }

