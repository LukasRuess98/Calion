from __future__ import annotations

import logging

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ..component import BaseComponent, Flow
from ..registry import register_component

logger = logging.getLogger(__name__)


@register_component("thermal_generator", category="converter", description="Thermal generator with optional CHP")
class ThermalGeneratorBlock(BaseComponent):
    def __init__(
        self,
        name: str,
        th_eff: float,
        el_eff: float | None,
        cap_th_mw: float,
        min_load_fraction: float = 0.0,
        min_uptime_h: float = 0.0,
        min_downtime_h: float = 0.0,
        max_ramp_up_mw_per_h: float | None = None,
        max_ramp_down_mw_per_h: float | None = None,
        startup_cost_eur: float = 0.0,
        label: str | None = None,
    ):
        super().__init__(name, label)
        self.th_eff = float(th_eff)
        self.el_eff = None if el_eff is None else float(el_eff)
        self.cap_th = float(cap_th_mw)
        self.min_load_fraction = max(0.0, float(min_load_fraction))
        self.min_uptime_h = max(0.0, float(min_uptime_h))
        self.min_downtime_h = max(0.0, float(min_downtime_h))
        self.max_ramp_up_mw_per_h = None if max_ramp_up_mw_per_h is None else float(max_ramp_up_mw_per_h)
        self.max_ramp_down_mw_per_h = None if max_ramp_down_mw_per_h is None else float(max_ramp_down_mw_per_h)
        self.startup_cost_eur = max(0.0, float(startup_cost_eur))

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")
        comp = self.name
        setattr(m, f"{comp}_Qth", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_fuel", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        Qth = getattr(m, f"{comp}_Qth")
        fuel = getattr(m, f"{comp}_fuel")

        setattr(m, f"{comp}_Qmax", pyo.Param(initialize=self.cap_th))
        setattr(m, f"{comp}_th_eff", pyo.Param(initialize=self.th_eff))

        # ── On/Off Binary (unit commitment) ───────────────────────────────────
        # Created only when needed — existing configs with all defaults=0/None
        # follow the original code path (no binary, no ramp, pure continuous).
        needs_binary = (
            self.min_load_fraction > 0
            or self.min_uptime_h > 0
            or self.min_downtime_h > 0
            or self.max_ramp_up_mw_per_h is not None
            or self.max_ramp_down_mw_per_h is not None
        )

        on = None
        if needs_binary:
            on = pyo.Var(Tset, domain=pyo.Binary)
            setattr(m, f"{comp}_on", on)

            cap_th_val = self.cap_th

            def cap_hi_rule(mm, t):
                return Qth[t] <= cap_th_val * on[t]

            setattr(m, f"{comp}_cap", pyo.Constraint(Tset, rule=cap_hi_rule))

            if self.min_load_fraction > 0:
                min_load_mw = self.min_load_fraction * cap_th_val

                def cap_lo_rule(mm, t):
                    return Qth[t] >= min_load_mw * on[t]

                setattr(m, f"{comp}_cap_lo", pyo.Constraint(Tset, rule=cap_lo_rule))
        else:
            # Original unidirektionale Kapazitätsschranke — identisch zum alten Verhalten
            def cap_rule(mm, t):
                return Qth[t] <= mm.__getattribute__(f"{comp}_Qmax")

            setattr(m, f"{comp}_cap", pyo.Constraint(Tset, rule=cap_rule))

        def th_link(mm, t):
            return Qth[t] == mm.__getattribute__(f"{comp}_th_eff") * fuel[t]

        setattr(m, f"{comp}_thlink", pyo.Constraint(Tset, rule=th_link))

        # ── Ramp Rate Constraints ──────────────────────────────────────────────
        dt_h_model = float(getattr(m, 'dt_h', 1.0))
        time_list = sorted(list(Tset))

        if self.max_ramp_up_mw_per_h is not None:
            ramp_up_mw = self.max_ramp_up_mw_per_h * dt_h_model

            def ramp_up_rule(mm, t):
                idx = time_list.index(t)
                if idx == 0:
                    return pyo.Constraint.Skip
                return Qth[t] - Qth[time_list[idx - 1]] <= ramp_up_mw

            setattr(m, f"{comp}_ramp_up", pyo.Constraint(Tset, rule=ramp_up_rule))

        if self.max_ramp_down_mw_per_h is not None:
            ramp_down_mw = self.max_ramp_down_mw_per_h * dt_h_model

            def ramp_down_rule(mm, t):
                idx = time_list.index(t)
                if idx == 0:
                    return pyo.Constraint.Skip
                return Qth[time_list[idx - 1]] - Qth[t] <= ramp_down_mw

            setattr(m, f"{comp}_ramp_down", pyo.Constraint(Tset, rule=ramp_down_rule))

        # ── Min Uptime / Downtime (unit commitment) ────────────────────────────
        # Pattern copied from heat_pump.py:141–187.
        L = max(0, round(self.min_uptime_h / dt_h_model))
        D = max(0, round(self.min_downtime_h / dt_h_model))

        u = None
        v = None
        if (L > 0 or D > 0) and on is not None:
            u = pyo.Var(Tset, domain=pyo.Binary)
            v = pyo.Var(Tset, domain=pyo.Binary)
            setattr(m, f"{comp}_u", u)
            setattr(m, f"{comp}_v", v)

            def state_transition_rule(mm, t):
                idx = time_list.index(t)
                if idx == 0:
                    return pyo.Constraint.Skip
                t_prev = time_list[idx - 1]
                return on[t] - on[t_prev] == u[t] - v[t]

            setattr(m, f"{comp}_state_transition",
                    pyo.Constraint(Tset, rule=state_transition_rule))

            def no_simultaneous_rule(mm, t):
                return u[t] + v[t] <= 1

            setattr(m, f"{comp}_no_simultaneous",
                    pyo.Constraint(Tset, rule=no_simultaneous_rule))

            if L > 0:
                def min_uptime_rule(mm, t):
                    idx = time_list.index(t)
                    start = max(0, idx - L + 1)
                    return sum(u[time_list[k]] for k in range(start, idx + 1)) <= on[t]

                setattr(m, f"{comp}_min_uptime",
                        pyo.Constraint(Tset, rule=min_uptime_rule))

            if D > 0:
                def min_downtime_rule(mm, t):
                    idx = time_list.index(t)
                    start = max(0, idx - D + 1)
                    return sum(v[time_list[k]] for k in range(start, idx + 1)) <= 1 - on[t]

                setattr(m, f"{comp}_min_downtime",
                        pyo.Constraint(Tset, rule=min_downtime_rule))

            logger.info(
                "[THERMAL_GEN] %s: unit commitment enabled "
                "(min_uptime=%dh, min_downtime=%dh, startup_cost=%.0f EUR)",
                comp, self.min_uptime_h, self.min_downtime_h, self.startup_cost_eur,
            )

        if needs_binary:
            logger.info(
                "[THERMAL_GEN] %s: binary on/off active "
                "(min_load=%.0f%%, ramp_up=%s MW/h, ramp_down=%s MW/h)",
                comp,
                self.min_load_fraction * 100,
                self.max_ramp_up_mw_per_h,
                self.max_ramp_down_mw_per_h,
            )

        # ── CHP Electric Output ────────────────────────────────────────────────
        Pel = None
        if self.el_eff is not None:
            setattr(m, f"{comp}_el_eff", pyo.Param(initialize=self.el_eff))
            setattr(m, f"{comp}_Pel", pyo.Var(Tset, domain=pyo.NonNegativeReals))
            Pelv = getattr(m, f"{comp}_Pel")

            def el_link(mm, t):
                return Pelv[t] == mm.__getattribute__(f"{comp}_el_eff") * fuel[t]

            setattr(m, f"{comp}_ellink", pyo.Constraint(Tset, rule=el_link))
            Pel = Pelv

        # Register flows with framework
        self.add_flow(Flow(
            bus="heat",
            direction="output",
            variable=Qth,
            nominal_value=self.cap_th
        ))

        if buses:
            if "heat" in buses:
                buses["heat"].add_output(Qth)
            if Pel is not None and "electricity" in buses:
                self.add_flow(Flow(
                    bus="electricity",
                    direction="output",
                    variable=Pel,
                    flow_type="electric_power"
                ))
                buses["electricity"].add_output(Pel)

        flows_dict = {"heat": {"output": Qth}}
        if Pel is not None:
            flows_dict["electricity"] = {"output": Pel}

        return {
            "flows": flows_dict,
            "metadata": {
                "th_eff": self.th_eff,
                "el_eff": self.el_eff,
                "capacity_th": self.cap_th,
            },
            # Legacy compatibility
            "Q_th_out": Qth,
            "fuel_in": fuel,
            "P_el_out": Pel,
            # Unit commitment
            "on_var": on,
            "startup_var": u,
            "shutdown_var": v,
            "startup_cost_eur": self.startup_cost_eur,
        }
