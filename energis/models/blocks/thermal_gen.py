from __future__ import annotations

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ..component import BaseComponent, Flow
from ..registry import register_component


@register_component("thermal_generator", category="converter", description="Thermal generator with optional CHP")
class ThermalGeneratorBlock(BaseComponent):
    """
    Thermal generator with optional CHP and investment mode.

    Supports both:
    - Brownfield mode (investable=False): Fixed capacity, always built
    - Investment mode (investable=True): Variable capacity, build decision
    """

    def __init__(
        self,
        name: str,
        th_eff: float,
        el_eff: float | None,
        cap_th_mw: float,
        label: str = None,
        investable: bool = False,
        capacity_min_mw: float = 0.0,
        capacity_max_mw: float = None,
        capacity_init_mw: float = None,
        capex_eur_per_mw: float = 200000.0,
        activation_cost_eur: float = 50000.0,
    ):
        super().__init__(name, label)
        self.th_eff = float(th_eff)
        self.el_eff = None if el_eff is None else float(el_eff)
        self.cap_th = float(cap_th_mw)

        # Investment parameters
        self.investable = bool(investable)
        self.capacity_min_mw = float(capacity_min_mw)
        self.capacity_max_mw = float(capacity_max_mw) if capacity_max_mw is not None else self.cap_th
        self.capacity_init_mw = float(capacity_init_mw) if capacity_init_mw is not None else self.cap_th
        self.capex_eur_per_mw = float(capex_eur_per_mw)
        self.activation_cost_eur = float(activation_cost_eur)

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")
        comp = self.name
        setattr(m, f"{comp}_Qth", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_fuel", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        Qth = getattr(m, f"{comp}_Qth")
        fuel = getattr(m, f"{comp}_fuel")

        # Build decision variable (binary)
        setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
        build = getattr(m, f"{comp}_build")

        # Capacity variable (continuous, bounds depend on investable)
        setattr(m, f"{comp}_cap_mw", pyo.Var(
            domain=pyo.NonNegativeReals,
            bounds=(0, self.capacity_max_mw)
        ))
        cap = getattr(m, f"{comp}_cap_mw")

        # Efficiency parameter
        setattr(m, f"{comp}_th_eff", pyo.Param(initialize=self.th_eff))

        # Fix variables in brownfield mode
        if not self.investable:
            build.fix(1 if self.capacity_init_mw > 0 else 0)
            cap.fix(self.capacity_init_mw)
        else:
            # Investment mode: set initial values
            cap.set_value(self.capacity_init_mw)

        # Capacity constraint: Q_th <= cap_mw
        def cap_rule(mm, t):
            return Qth[t] <= cap

        # Efficiency link: Q_th = th_eff * fuel
        def th_link(mm, t):
            return Qth[t] == mm.__getattribute__(f"{comp}_th_eff") * fuel[t]

        setattr(m, f"{comp}_cap_constraint", pyo.Constraint(Tset, rule=cap_rule))
        setattr(m, f"{comp}_thlink", pyo.Constraint(Tset, rule=th_link))

        # Investment mode constraints
        if self.investable:
            # Capacity only if built: cap_min * build <= cap <= cap_max * build
            def cap_min_rule(mm):
                return cap >= self.capacity_min_mw * build

            def cap_max_rule(mm):
                return cap <= self.capacity_max_mw * build

            setattr(m, f"{comp}_cap_min", pyo.Constraint(rule=cap_min_rule))
            setattr(m, f"{comp}_cap_max", pyo.Constraint(rule=cap_max_rule))

        # Store CAPEX expression for objective
        capex_expr = self.activation_cost_eur * build + self.capex_eur_per_mw * cap
        if not hasattr(m, 'generator_capex_costs'):
            m.generator_capex_costs = {}
        m.generator_capex_costs[comp] = capex_expr

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

        # Fuel input (will be registered with fuel buses in system_builder)
        # Note: fuel bus type determined by config

        # Register with buses if available
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

        # Return standardized format
        flows_dict = {"heat": {"output": Qth}}
        if Pel is not None:
            flows_dict["electricity"] = {"output": Pel}

        return {
            "flows": flows_dict,
            "metadata": {
                "th_eff": self.th_eff,
                "el_eff": self.el_eff,
                "capacity_th": self.cap_th,
                "investable": self.investable,
            },
            # Investment variables
            "build": build,
            "cap_mw": cap,
            "capex": capex_expr,
            # Legacy compatibility
            "Q_th_out": Qth,
            "fuel_in": fuel,
            "P_el_out": Pel
        }
