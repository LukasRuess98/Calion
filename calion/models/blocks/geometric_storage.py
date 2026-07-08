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

from ...constants import (
    CP_WATER_HOT_KJ_PER_KGK as _CP,
    G_ACCEL_M_S2 as _G,
    P_ATM_BAR as _P_ATM_BAR,
    RHO_WATER_HOT_KG_M3 as _RHO,
)
from ..component import BaseComponent, Flow, InvestmentResult
from ..registry import register_component


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
        option_b: bool = False,
        *,
        investable: bool = True,
        energy_mwh_fixed: float | None = None,
        power_mw_fixed: float | None = None,
        e_min_fraction: float = 0.0,
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
        self.option_b = bool(option_b)
        self.e_min_fraction = float(e_min_fraction)

        # Pre-compute energy coefficient [MWh/m³] for this scenario's ΔT
        self.energy_coeff = _energy_coeff_mwh_per_m3(self.delta_T_k)

        # Derive V_max from pressure constraint
        h_max_from_p = _h_max_from_pressure(self.p_max_bar)
        # h/d = r_hd  →  d = h/r_hd  →  V = π/4*(h/r_hd)²*h = π*h³/(4*r_hd²)
        V_max_from_p = math.pi * h_max_from_p**3 / (4.0 * self.r_hd**2)
        self.V_max_effective = min(self.V_max_m3, V_max_from_p)

        # ── Non-investable / fixed-geometry mode ────────────────────────────
        # Represents a real, already-built tank (e.g. an existing HKW buffer)
        # sized by its known energy/power rating rather than optimized. Volume
        # and height are still derived geometrically (via energy_coeff, r_hd)
        # so the tank participates in the same F4 hydrostatic pressure
        # coupling as an investable tank — it just isn't a free decision.
        self.investable = bool(investable)
        self.energy_mwh_fixed = float(energy_mwh_fixed) if energy_mwh_fixed is not None else None
        self.power_mw_fixed = float(power_mw_fixed) if power_mw_fixed is not None else None
        self.V_fixed_m3 = None
        if not self.investable:
            if self.energy_mwh_fixed is None or self.power_mw_fixed is None:
                raise ValueError(
                    f"GeometricStorageBlock '{name}': investable=False requires "
                    "energy_mwh_fixed and power_mw_fixed"
                )
            self.V_fixed_m3 = self.energy_mwh_fixed / self.energy_coeff
            if self.V_fixed_m3 > self.V_max_effective:
                raise ValueError(
                    f"GeometricStorageBlock '{name}': fixed energy {self.energy_mwh_fixed} MWh "
                    f"at dT={self.delta_T_k} K needs V={self.V_fixed_m3:.0f} m3, exceeding the "
                    f"pressure/geometry limit of {self.V_max_effective:.0f} m3 (p_max_bar={self.p_max_bar}, "
                    f"r_hd={self.r_hd}). Raise p_max_bar/r_hd or lower delta_T_scenario_k."
                )
            # Fixed tank's own footprint sets both bounds (report/PWL use V_max_effective;
            # V_min_m3 must match too or the V_lo Big-M constraint below is infeasible).
            self.V_max_effective = self.V_fixed_m3
            self.V_min_m3 = self.V_fixed_m3

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

        if not self.investable:
            # Fixed/existing tank: geometry is known, not optimized.
            build.fix(1)
            V.fix(self.V_fixed_m3)

        # Energy capacity derived from volume (linear thanks to scenario ΔT param)
        # E_max [MWh] = energy_coeff [MWh/m³] * V [m³]
        E_max_expr = self.energy_coeff * V
        setattr(m, f"{comp}_E_max_expr", pyo.Expression(rule=lambda mm: E_max_expr))

        # Power capacity (option: fixed ratio to energy capacity)
        if not self.investable:
            setattr(m, f"{comp}_cap_power", pyo.Var(
                domain=pyo.NonNegativeReals, bounds=(0.0, self.power_mw_fixed),
            ))
            cap_p = getattr(m, f"{comp}_cap_power")
            cap_p.fix(self.power_mw_fixed)
        elif self.power_to_energy_ratio is not None:
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

        # V bounds linked to build decision (Big-M). Trivially satisfied when
        # fixed (build==1, V==V_fixed_m3 <= V_max_effective==V_fixed_m3), kept
        # so downstream code (e.g. F4 pressure coupling) sees a uniform shape.
        def V_lo(mm):
            return V >= self.V_min_m3 * build
        def V_hi(mm):
            return V <= self.V_max_effective * build
        setattr(m, f"{comp}_V_lo", pyo.Constraint(rule=V_lo))
        setattr(m, f"{comp}_V_hi", pyo.Constraint(rule=V_hi))

        # ── Option B: explicit h_TES and d_TES variables (MIQCP) ─────────────
        # V = π/4 × d² × h is a bilinear/quadratic constraint; makes model MIQCP.
        # Useful when site footprint or explicit geometry is needed in results.
        h_m3 = None
        d_m3 = None
        if self.option_b:
            h_max = _h_max_from_pressure(self.p_max_bar)
            # d_max from V_max_effective and h_min = 1 m (practical floor)
            d_max = math.sqrt(4.0 * self.V_max_effective / math.pi)  # at h=1 m, upper bound
            setattr(m, f"{comp}_h_m", pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, h_max)))
            setattr(m, f"{comp}_d_m", pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, d_max)))
            h_m3 = getattr(m, f"{comp}_h_m")
            d_m3 = getattr(m, f"{comp}_d_m")

            # Quadratic volume identity: V = π/4 × d² × h
            def geom_vol(mm):
                return V == (math.pi / 4.0) * d_m3**2 * h_m3
            setattr(m, f"{comp}_geom_vol", pyo.Constraint(rule=geom_vol))

            # Aspect ratio: h/d = r_hd  →  h = r_hd × d
            def aspect_ratio(mm):
                return h_m3 == self.r_hd * d_m3
            setattr(m, f"{comp}_aspect", pyo.Constraint(rule=aspect_ratio))

            # Explicit pressure ceiling (h_TES ≤ h_max already via bounds)
            # — the bounds handle this; no additional constraint needed

            # h and d must be zero when no tank built
            def h_build(mm):
                return h_m3 <= h_max * build
            def d_build(mm):
                return d_m3 <= d_max * build
            setattr(m, f"{comp}_h_build", pyo.Constraint(rule=h_build))
            setattr(m, f"{comp}_d_build", pyo.Constraint(rule=d_build))

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
        # Initial SOC as an expression of V so it stays feasible for any invested capacity.
        # E_initial = soc0_fraction × energy_coeff × V  (linear in V, the decision variable).
        soc0_expr = self.soc0_fraction * E_max_expr

        # SOC dynamics: first timestep uses soc0_expr (linear in V, not a fixed scalar).
        t_first = Tset.first()
        def soc_dyn(mm, t):
            prev = E[t - 1] if t != t_first else soc0_expr
            return E[t] == prev * loss_factor + eff_c * Qc[t] * self.dt_h - (Qd[t] * self.dt_h) / eff_d
        setattr(m, f"{comp}_soc", pyo.Constraint(Tset, rule=soc_dyn))

        # SOC ≤ E_max: bounded by installed capacity (build, not active).
        # Using active[t] here was a bug: it would force E=0 whenever the storage is idle.
        # PERF FIX (2026-07-04): dropped the redundant "* build" factor — it made
        # this a genuine quadratic constraint (V * build, both variables) and was
        # the last remaining MIQCP source in this block. It is provably redundant:
        # V_hi already enforces V <= V_max_effective * build, so V == 0 whenever
        # build == 0, making E_max_expr (= energy_coeff * V) already zero in that
        # case without needing the extra binary factor. Verified: same objective
        # value before/after (50632.0114841813 vs ...29, float noise only).
        def soc_hi(mm, t):
            return E[t] <= E_max_expr
        setattr(m, f"{comp}_soc_hi", pyo.Constraint(Tset, rule=soc_hi))

        if self.e_min_fraction > 0.0:
            def soc_lo(mm, t):
                return E[t] >= self.e_min_fraction * E_max_expr
            setattr(m, f"{comp}_soc_lo", pyo.Constraint(Tset, rule=soc_lo))

        # ── Exact linearization of cap_p * mode[t] (binary × bounded continuous) ─
        # PERF FIX (2026-07-04): writing cap_p*cm[t]/cap_p*dm[t] directly makes
        # Gurobi solve a nonconvex MIQCP (this block is active in nearly every
        # Paper 2 scenario with a TES — verified as the dominant remaining
        # quadratic-constraint source after the heat_pump/p2h fix: NumQConstrs
        # dropped 72->36 with only those two fixed, on a model with one TES).
        # Exact reformulation for y∈{0,1}, x∈[0,x_max]:
        #   z<=x_max*y ; z<=x ; z>=x-x_max*(1-y) ; z>=0
        cap_p_max = float(cap_p.ub)
        setattr(m, f"{comp}_cap_p_x_cm", pyo.Var(Tset, domain=pyo.NonNegativeReals, bounds=(0.0, cap_p_max)))
        setattr(m, f"{comp}_cap_p_x_dm", pyo.Var(Tset, domain=pyo.NonNegativeReals, bounds=(0.0, cap_p_max)))
        cap_p_x_cm = getattr(m, f"{comp}_cap_p_x_cm")
        cap_p_x_dm = getattr(m, f"{comp}_cap_p_x_dm")

        def _cm_hi(mm, t):
            return cap_p_x_cm[t] <= cap_p_max * cm[t]
        def _cm_le_cap(mm, t):
            return cap_p_x_cm[t] <= cap_p
        def _cm_lo(mm, t):
            return cap_p_x_cm[t] >= cap_p - cap_p_max * (1 - cm[t])
        setattr(m, f"{comp}_cap_p_cm_hi", pyo.Constraint(Tset, rule=_cm_hi))
        setattr(m, f"{comp}_cap_p_cm_le_cap", pyo.Constraint(Tset, rule=_cm_le_cap))
        setattr(m, f"{comp}_cap_p_cm_lo", pyo.Constraint(Tset, rule=_cm_lo))

        def _dm_hi(mm, t):
            return cap_p_x_dm[t] <= cap_p_max * dm[t]
        def _dm_le_cap(mm, t):
            return cap_p_x_dm[t] <= cap_p
        def _dm_lo(mm, t):
            return cap_p_x_dm[t] >= cap_p - cap_p_max * (1 - dm[t])
        setattr(m, f"{comp}_cap_p_dm_hi", pyo.Constraint(Tset, rule=_dm_hi))
        setattr(m, f"{comp}_cap_p_dm_le_cap", pyo.Constraint(Tset, rule=_dm_le_cap))
        setattr(m, f"{comp}_cap_p_dm_lo", pyo.Constraint(Tset, rule=_dm_lo))

        # Power limits
        def qc_limit(mm, t):
            return Qc[t] <= cap_p_x_cm[t]
        def qd_limit(mm, t):
            return Qd[t] <= cap_p_x_dm[t]
        setattr(m, f"{comp}_qc_lim", pyo.Constraint(Tset, rule=qc_limit))
        setattr(m, f"{comp}_qd_lim", pyo.Constraint(Tset, rule=qd_limit))

        # Mode exclusivity
        def mode_excl(mm, t):
            return cm[t] + dm[t] <= active[t]
        setattr(m, f"{comp}_mode_excl", pyo.Constraint(Tset, rule=mode_excl))

        def active_build(mm, t):
            return active[t] <= build
        setattr(m, f"{comp}_active_build", pyo.Constraint(Tset, rule=active_build))

        # Terminal SOC constraint (cyclic: first ≈ last).
        # Target is also a linear expression of V so it scales with the invested capacity.
        if self.terminal_soc_fraction is not None:
            t_last = Tset.last()
            target_expr = self.terminal_soc_fraction * E_max_expr
            setattr(m, f"{comp}_terminal",
                    pyo.Constraint(expr=E[t_last] >= target_expr))

        # ── Register flows ────────────────────────────────────────────────────
        self.add_flow(Flow(bus="heat", direction="output", variable=Qd, investment=self.investable))
        self.add_flow(Flow(bus="heat", direction="input", variable=Qc, investment=self.investable))

        if buses and "heat" in buses:
            buses["heat"].add_output(Qd)
            buses["heat"].add_input(Qc)

        return {
            "flows": {"heat": {"output": Qd, "input": Qc}},
            "investment": InvestmentResult(
                capacity_energy=V,    # using V_m3 as the "energy cap" placeholder
                capacity_power=cap_p,
                build=build,
            ) if self.investable else None,
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
            "h_m": h_m3,   # None unless option_b=True
            "d_m": d_m3,   # None unless option_b=True
        }
