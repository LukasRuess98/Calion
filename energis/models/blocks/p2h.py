from __future__ import annotations

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ..component import BaseComponent, Flow
from ..registry import register_component


@register_component("p2h", category="converter", description="Power-to-Heat converter (electric boiler/resistance heater)")
class P2HBlock(BaseComponent):
    def __init__(self, name: str, eff: float, cap_th_mw: float, label: str = None):
        super().__init__(name, label)
        self.eff = float(eff)
        self.cap = float(cap_th_mw)

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")
        comp = self.name
        setattr(m, f"{comp}_Qth", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Pel", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        Q = getattr(m, f"{comp}_Qth")
        P = getattr(m, f"{comp}_Pel")
        setattr(m, f"{comp}_eff", pyo.Param(initialize=self.eff))
        setattr(m, f"{comp}_cap", pyo.Param(initialize=self.cap))

        def cap_rule(mm, t):
            return Q[t] <= mm.__getattribute__(f"{comp}_cap")

        def link(mm, t):
            return Q[t] == mm.__getattribute__(f"{comp}_eff") * P[t]

        setattr(m, f"{comp}_capcons", pyo.Constraint(Tset, rule=cap_rule))
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
        return {
            "flows": {
                "heat": {"output": Q},
                "electricity": {"input": P}
            },
            "metadata": {
                "efficiency": self.eff,
                "capacity_th": self.cap
            },
            # Legacy compatibility
            "Q_th_out": Q,
            "P_el_in": P
        }
