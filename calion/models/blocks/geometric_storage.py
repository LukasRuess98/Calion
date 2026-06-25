"""Geometric TES block for Paper 2 investment optimization.

Extends the standard StorageBlock by replacing fixed energy capacity
with a geometric sizing model: V_TES [m³] and h_TES [m] are Pyomo
decision variables, and E_TES_max is derived from geometry.

Design:
  Option A (default): Fixed aspect ratio h/d = r_hd → V = π/4 * (h/r_hd)² * h
    → Only h_TES is a free variable; V_TES is derived.
  Option B: Both V_TES and h_TES are free (V = π/4 * d² * h, d separate).
    → d_TES is also a Pyomo variable.

Linearization:
  E_TES_max = rho * cp * delta_T * V_TES
  where delta_T is treated as a scenario parameter (from heating curve),
  so E_TES_max = const_per_scenario * V_TES   →  linear in V_TES.

Pressure constraint:
  p_betr = p_atm + rho * g * h_TES / 1e5  ≤  p_max [bar]
  → upper bound on h_TES: h_TES ≤ (p_max - p_atm) * 1e5 / (rho * g)
"""

from __future__ import annotations

import math
from collections.abc import Sequence

try:
    import pyomo.environ as pyo
except Exception:
    pyo = None

from ..component import BaseComponent, Flow, InvestmentResult
from ..registry import register_component

# Water properties at 75°C
_RHO = 971.8        # kg/m³
_CP = 4.189         # kJ/(kg·K)  →  kJ = kWh * 3600 * 1000
_G = 9.81           # m/s²
_P_ATM_BAR = 1.013  # bar


def _h_max_from_pressure(p_max_bar: float) -> float:
    """Max TES height from pressure constraint [m]."""
    return (p_max_bar - _P_ATM_BAR) * 1e5 / (_RHO * _G)


def _energy_coeff_mwh_per_m3(delta_T_k: float) -> float:
    """MWh per m³ for given temperature spread."""
    # E [kJ] = rho [kg/m³] * cp [kJ/(kg·K)] * dT [K] * V [m³]
    # E [MWh] = E_kJ / 3600 / 1000
    return _RHO * _CP * delta_T_k / 3600.0 / 1000.0


@register_component(
    "geometric_storage",
    category="storage",
    description="TES with geometric sizing variables V_TES, h_TES for Paper 2 investment",
)
class GeometricStorageBlock(BaseComponent):
    """TES block with V_TES and h_TES as investment decision variables.

    The E_TES capacity (MWh) is computed as:
        E_TES_max = coeff_mwh_per_m3 * V_TES
    where coeff is pre-computed from (delta_T, rho, cp) as a scenario parameter.

    For the h/d option A (fixed aspect ratio):
        h_TES = r_hd * d_TES
        V_TES = π/4 * d_TES² * h_TES  →  nonlinear if both are variables
        Simplification: given h_TES as the single free variable and r_hd fixed:
            d = h / r_hd
            V = π/4 * (h/r_hd)² * h = π/(4*r_hd²) * h³   →  nonlinear
        Therefore we keep V_TES as the primary optimization variable,
        and derive h_TES from V via: h = (r_hd² * 4/π * V)^(1/3)  post-solve.
        During optimization we use p_max as a bound on V instead:
            h_max = (p_max - p_atm)*1e5/(rho*g)
            V_max = π/(4*r_hd²) * h_max³

    For Option B (d free):
        Add d_TES as an extra continuous variable and a nonlinear volume constraint.
        This makes the model MIQCP — only viable if solver supports nonconvex.
        Default is Option A (V only, MILP-safe).
    """

    def __init__(
        self,
        name: str,
        # Economic
        alpha_tes_eur_per_m3: float,
        beta_tes_eur: float,
        lifetime_years: float,
        # Geometry
        delta_T_scenario_k: float,
        r_hd: float,
        p_max_bar: float,
        V_min_m3: float,
        V_max_m3: float,
        # Operating dynamics (same as StorageBlock)
        eff_c: float,
        eff_d: float,
        hourly_loss: float,
        dt_h: float,
        soc0_fraction: float,
        power_to_energy_ratio: float | None = None,
        terminal_soc_fraction: float | None = None,
        *,
        label: str | None = None,
    ):
        super().__init__(name, label)
        self.alpha_tes = float(alpha_tes_eur_per_m3)
        self.beta_tes = float(beta_tes_eur)
        self.lifetime_years = float(lifetime_years)
        self.delta_T_k = float(delta_T_scenario_k)
        self.r_hd = float(r_hd)
        self.p_max_bar = float(p_max_bar)
        self.V_min_m3 = float(V_min_m3)
        self.V_max_m3 = float(V_max_m3)
        self.eff_c = float(eff_c)
        self.eff_d = float(eff_d)
        self.hourly_loss = float(hourly_loss)
        self.dt_h = float(dt_h)
        self.soc0_fraction = float(soc0_fraction)
        self.power_to_energy_ratio = power_to_energy_ratio
        self.terminal_soc_fraction = terminal_soc_fraction

        # Pre-compute energy coefficient [MWh/m³] for this scenario's ΔT
        self.energy_coeff = _energy_coeff_mwh_per_m3(self.delta_T_k)

        # Derive V_max from pressure constraint
        h_max_from_p = _h_max_from_pressure(self.p_max_bar)
        # h/d = r_hd  →  d = h/r_hd  →  V = π/4*(h/r_hd)²*h = π*h³/(4*r_hd²)
        V_max_from_p = math.pi * h_max_from_p**3 / (4.0 * self.r_hd**2)
        self.V_max_effective = min(self.V_max_m3, V_max_from_p)

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach geometric_storage blocks")

        comp = self.name
        times = list(Tset)

        # ── Investment variables ──────────────────────────────────────────────
        setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
        setattr(
            m,
            f"{comp}_V_m3",
            pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, self.V_max_effective)),
        )
        build = getattr(m, f"{comp}_build")
        V = getattr(m, f"{comp}_V_m3")

        # Energy capacity derived from volume (linear thanks to scenario ΔT param)
        # E_max [MWh] = energy_coeff [MWh/m³] * V [m³]
        E_max_expr = self.energy_coeff * V
        setattr(m, f"{comp}_E_max_expr", pyo.Expression(rule=lambda mm: E_max_expr))

        # Power capacity (option: fixed ratio to energy capacity)
        if self.power_to_energy_ratio is not None:
            ratio = float(self.power_to_energy_ratio)
            setattr(m, f"{comp}_cap_power", pyo.Var(
                domain=pyo.NonNegativeReals,
                bounds=(0.0, self.V_max_effective * self.energy_coeff * ratio),
            ))
            cap_p = getattr(m, f"{comp}_cap_power")
            def p_energy_coupling(mm):
                return cap_p <= ratio * E_max_expr
            setattr(m, f"{comp}_p_coupling", pyo.Constraint(rule=p_energy_coupling))
        else:
            # Default: power capacity = 1/4 C-rate (discharge in ~4h)
            default_ratio = 0.25
            setattr(m, f"{comp}_cap_power", pyo.Var(
                domain=pyo.NonNegativeReals,
                bounds=(0.0, self.V_max_effective * self.energy_coeff * default_ratio * 2),
            ))
            cap_p = getattr(m, f"{comp}_cap_power")
            def p_energy_coupling(mm):
                return cap_p <= default_ratio * E_max_expr
            setattr(m, f"{comp}_p_coupling", pyo.Constraint(rule=p_energy_coupling))

        # V bounds linked to build decision (Big-M)
        def V_lo(mm):
            return V >= self.V_min_m3 * build
        def V_hi(mm):
            return V <= self.V_max_effective * build
        setattr(m, f"{comp}_V_lo", pyo.Constraint(rule=V_lo))
        setattr(m, f"{comp}_V_hi", pyo.Constraint(rule=V_hi))

        # ── State-of-charge variables ─────────────────────────────────────────
        setattr(m, f"{comp}_E", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Qc", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Qd", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_charge_mode", pyo.Var(Tset, domain=pyo.Binary))
        setattr(m, f"{comp}_discharge_mode", pyo.Var(Tset, domain=pyo.Binary))
        setattr(m, f"{comp}_active", pyo.Var(Tset, domain=pyo.Binary))

        E = getattr(m, f"{comp}_E")
        Qc = getattr(m, f"{comp}_Qc")
        Qd = getattr(m, f"{comp}_Qd")
        cm = getattr(m, f"{comp}_charge_mode")
        dm = getattr(m, f"{comp}_discharge_mode")
        active = getattr(m, f"{comp}_active")

        loss_factor = float(self.hourly_loss) ** self.dt_h
        eff_c = max(self.eff_c, 1e-4)
        eff_d = max(self.eff_d, 1e-4)
        soc0 = self.soc0_fraction * self.energy_coeff * self.V_max_effective

        # SOC dynamics
        def soc_dyn(mm, t):
            prev = E[t - 1] if t > Tset.first() else soc0
            return E[t] == prev * loss_factor + eff_c * Qc[t] * self.dt_h - (Qd[t] * self.dt_h) / eff_d
        setattr(m, f"{comp}_soc", pyo.Constraint(Tset, rule=soc_dyn))

        # SOC ≤ E_max (from geometry)
        def soc_hi(mm, t):
            return E[t] <= E_max_expr * active[t]
        setattr(m, f"{comp}_soc_hi", pyo.Constraint(Tset, rule=soc_hi))

        # Power limits
        def qc_limit(mm, t):
            return Qc[t] <= cap_p * cm[t]
        def qd_limit(mm, t):
            return Qd[t] <= cap_p * dm[t]
        setattr(m, f"{comp}_qc_lim", pyo.Constraint(Tset, rule=qc_limit))
        setattr(m, f"{comp}_qd_lim", pyo.Constraint(Tset, rule=qd_limit))

        # Mode exclusivity
        def mode_excl(mm, t):
            return cm[t] + dm[t] <= active[t]
        setattr(m, f"{comp}_mode_excl", pyo.Constraint(Tset, rule=mode_excl))

        def active_build(mm, t):
            return active[t] <= build
        setattr(m, f"{comp}_active_build", pyo.Constraint(Tset, rule=active_build))

        # Terminal SOC constraint (cyclic: first ≈ last)
        if self.terminal_soc_fraction is not None:
            t_last = Tset.last()
            target = self.terminal_soc_fraction * self.energy_coeff * self.V_max_effective
            setattr(m, f"{comp}_terminal", pyo.Constraint(expr=E[t_last] >= target))

        # ── Register flows ────────────────────────────────────────────────────
        self.add_flow(Flow(bus="heat", direction="output", variable=Qd, investment=True))
        self.add_flow(Flow(bus="heat", direction="input", variable=Qc, investment=True))

        if buses and "heat" in buses:
            buses["heat"].add_output(Qd)
            buses["heat"].add_input(Qc)

        return {
            "flows": {"heat": {"output": Qd, "input": Qc}},
            "investment": InvestmentResult(
                capacity_energy=V,    # using V_m3 as the "energy cap" placeholder
                capacity_power=cap_p,
                build=build,
            ),
            "state": E,
            "metadata": {
                "V_m3": V,
                "E_max_expr": E_max_expr,
                "energy_coeff_mwh_per_m3": self.energy_coeff,
                "delta_T_k": self.delta_T_k,
                "alpha_tes": self.alpha_tes,
                "beta_tes": self.beta_tes,
                "lifetime_years": self.lifetime_years,
                "charge_mode": cm,
                "discharge_mode": dm,
                "active": active,
            },
            "Q_th_out": Qd,
            "Q_th_in": Qc,
            "SOC": E,
            "build": build,
            "V_m3": V,
            "cap_power": cap_p,
        }
