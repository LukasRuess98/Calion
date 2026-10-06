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

import logging
import math
from collections.abc import Sequence

logger = logging.getLogger(__name__)

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


def surface_factor(aspect_ratio: float) -> float:
    """k(AR) for a closed cylinder: outer surface A = k(AR) * V^(2/3), AR = h/d.

    A = π(AR+0.5)·(4/(π·AR))^(2/3)·V^(2/3). Minimal at AR=1 (h=d); k(2)/k(1)≈1.05
    — the surface (loss) penalty of a tall, well-stratified tank is small (~5%).
    """
    return math.pi * (aspect_ratio + 0.5) * (4.0 / (math.pi * aspect_ratio)) ** (2.0 / 3.0)


def standing_loss_fraction_per_h(volume_m3: float, aspect_ratio: float,
                                 u_value_w_m2k: float, t_tes_c: float, t_amb_c: float,
                                 energy_coeff_mwh_per_m3: float) -> float:
    """Fractional standing loss per hour for a stratified tank, surface-scaled.

    Q̇_loss,full [MW] = U·k(AR)·V^(2/3)·(T_tes−T_amb) / 1e6.  The fractional rate
    (loss ÷ full-charge energy E_max = coeff·V) is
        λ = U·k(AR)·(T_tes−T_amb)/(1e6·coeff) · V^(−1/3)   [1/h]
    i.e. it DECREASES with size as V^(−1/3): big stores lose relatively less
    (the surface-area benefit). For a stratified tank the absolute loss scales
    with the hot fraction (SoC), so applying λ to E[t] (SoC-proportional) is exact
    in shape and avoids driving E below 0. Returns λ for a KNOWN (fixed) V.
    """
    if volume_m3 <= 0 or energy_coeff_mwh_per_m3 <= 0:
        return 0.0
    k = surface_factor(aspect_ratio)
    return (u_value_w_m2k * k * max(t_tes_c - t_amb_c, 0.0)
            / (1.0e6 * energy_coeff_mwh_per_m3) * volume_m3 ** (-1.0 / 3.0))


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
        n_discrete_sizes: int = 4,
        discrete_energies_mwh: list | None = None,
        unit_tank_m3: float | None = None,
        v_min_realistic_m3: float = 0.0,
        # ── v3 atmospheric geometry (all default to LEGACY = pre-v3 behaviour) ──
        loss_model: str = "proportional",   # "surface" | "proportional"(legacy)
        cost_model: str = "linear",         # "degressive" | "linear"(legacy)
        eta_strat: float = 1.0,             # stratification efficiency on E_max (1.0 = legacy)
        u_value_w_m2k: float = 0.0,         # surface standing-loss coefficient (surface model)
        t_amb_c: float = 10.0,
        t_return_c: float | None = None,    # for T_hot = t_return + ΔT in the loss ΔT
        t_store_max_c: float | None = None, # atmospheric store ceiling (clips ΔT)
        c0_eur: float | None = None,        # degressive C0·(V/V0)^b
        v0_m3: float | None = None,
        exponent_b: float | None = None,
        discharge_mask: list | None = None, # per-hour 0/1: block discharge where T_VL(t)>T_store_max
        pressure_limits_size: bool = True,  # V2f: atmospheric flat-bottomed tanks (EN14015/API650) are
                                             # NOT pressure vessels -- size must NOT derive from p_max_bar.
                                             # True (default) preserves legacy/pressurized-vessel behaviour
                                             # (Study G); component_assembler passes False for the
                                             # atmospheric technology.
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
        # Number of discrete tank sizes {0, ..., V_max} for the investment choice.
        # >=2 replaces the continuous V + big-M build coupling (a weak LP relaxation
        # that made TES-at-consumer-node scenarios intractable) with a tight exact
        # selection. 0/1 keeps the legacy continuous formulation.
        self.n_discrete_sizes = int(n_discrete_sizes)
        # Explicit discrete storage sizes as ENERGY [MWh] (incl. 0 = no storage),
        # anchored to hours of mean heat demand. When given, overrides the even
        # V-spacing above. Each size's volume V_k = E_k/energy_coeff; sizes larger
        # than one realistic tank (unit_tank_m3) are realised as N_k = ceil(V_k/unit)
        # identical tanks at the same site, so beta_tes (fixed cost) applies PER TANK.
        self.discrete_energies_mwh = list(discrete_energies_mwh) if discrete_energies_mwh else None
        self.unit_tank_m3 = float(unit_tank_m3) if unit_tank_m3 else None
        # Realistic minimum vessel (m³): with beta_tes=0 (turnkey €/m³) the optimizer
        # could otherwise select an unphysical micro-store. Positive ladder rungs whose
        # derived volume falls below this floor are dropped (the 0 rung is kept).
        self.v_min_realistic_m3 = float(v_min_realistic_m3) if v_min_realistic_m3 else 0.0

        # ── v3 atmospheric geometry params ──────────────────────────────────
        self.loss_model = str(loss_model)
        self.cost_model = str(cost_model)
        self.eta_strat = float(eta_strat)
        self.u_value_w_m2k = float(u_value_w_m2k)
        self.t_amb_c = float(t_amb_c)
        self.t_return_c = float(t_return_c) if t_return_c is not None else None
        self.t_store_max_c = float(t_store_max_c) if t_store_max_c is not None else None
        self.c0_eur = float(c0_eur) if c0_eur is not None else None
        self.v0_m3 = float(v0_m3) if v0_m3 is not None else None
        self.exponent_b = float(exponent_b) if exponent_b is not None else None
        self.discharge_mask = list(discharge_mask) if discharge_mask else None

        # Atmospheric store ceiling: clip the usable ΔT if the (charge) supply
        # temperature would exceed the tank's boiling-limited ceiling. Uses
        # t_return to reconstruct the hot temperature T_hot = t_return + ΔT.
        if self.t_store_max_c is not None and self.t_return_c is not None:
            t_hot = self.t_return_c + self.delta_T_k
            if t_hot > self.t_store_max_c:
                self.delta_T_k = max(self.t_store_max_c - self.t_return_c, 0.0)

        # Pre-compute energy coefficient [MWh/m³]: ρ·c_p·ΔT scaled by stratification
        # efficiency η_strat (usable fraction). η_strat=1.0 reproduces legacy.
        self.energy_coeff = self.eta_strat * _energy_coeff_mwh_per_m3(self.delta_T_k)

        # Derive V_max from pressure constraint -- ONLY for a real pressure vessel
        # (Study-G pressurized variant). An atmospheric, flat-bottomed EN 14015 /
        # API 650 tank has no design-pressure ceiling on height/volume at all (its
        # wall is sized via hoop stress for whatever hydrostatic load the height
        # produces); V2f makes this structural, not just numerically non-binding --
        # p_max_bar is then a real, physically-meaningful design value (reporting/
        # option_b geometry only) that can never feed into the size cap.
        self.pressure_limits_size = bool(pressure_limits_size)
        if self.pressure_limits_size:
            h_max_from_p = _h_max_from_pressure(self.p_max_bar)
            # h/d = r_hd  →  d = h/r_hd  →  V = π/4*(h/r_hd)²*h = π*h³/(4*r_hd²)
            V_max_from_p = math.pi * h_max_from_p**3 / (4.0 * self.r_hd**2)
            self.V_max_effective = min(self.V_max_m3, V_max_from_p)
        else:
            self.V_max_effective = self.V_max_m3

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
            logger.info("[GEOMETRIC_STORAGE] %s: fixed %.1f MWh @ dT=%.1f K -> V=%.0f m3 "
                        "(OK; limit %.0f m3, p_max_bar=%.1f, r_hd=%.1f)",
                        name, self.energy_mwh_fixed, self.delta_T_k, self.V_fixed_m3,
                        self.V_max_effective, self.p_max_bar, self.r_hd)
            self.V_max_effective = self.V_fixed_m3
            self.V_min_m3 = self.V_fixed_m3

    def attach(self, m, Tset, cfg, buses):
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach geometric_storage blocks")

        comp = self.name
        times = list(Tset)

        # ── Investment variables ──────────────────────────────────────────────
        # Resolve the discrete size ladder (volumes + tank counts) first, so V_m3's
        # upper bound covers multi-tank totals.
        v_list = n_tanks_list = None
        use_discrete = self.investable and (bool(self.discrete_energies_mwh)
                                            or self.n_discrete_sizes >= 2)
        if self.investable and self.discrete_energies_mwh:
            # Explicit ENERGY ladder [MWh] -> volumes at this scenario's ΔT. Sizes
            # larger than one realistic tank are realised as N = ceil(V/unit) tanks.
            e_list = sorted(set([0.0] + [float(e) for e in self.discrete_energies_mwh]))
            v_list = [e / self.energy_coeff for e in e_list]
            # Realistic-minimum-vessel floor: drop positive rungs whose volume (at this
            # scenario's ΔT) is below v_min_realistic_m3, so beta=0 cannot admit a
            # micro-store. Keep the 0 rung. Applied BEFORE tank-count / cost build.
            if self.v_min_realistic_m3 > 0:
                _kept = [(e, v) for e, v in zip(e_list, v_list)
                         if e <= 0.0 or v >= self.v_min_realistic_m3]
                if len(_kept) < len(e_list):
                    logger.info("[GEOMETRIC_STORAGE] %s: dropped %d rung(s) below "
                                "v_min_realistic=%.0f m³ (beta=0 micro-store guard)",
                                comp, len(e_list) - len(_kept), self.v_min_realistic_m3)
                e_list = [e for e, _ in _kept]
                v_list = [v for _, v in _kept]
            unit = self.unit_tank_m3 or self.V_max_effective
            n_tanks_list = [0 if e <= 0 else max(1, math.ceil(v / unit))
                            for e, v in zip(e_list, v_list)]
            v_ub = max(v_list)
            # Defensive check (2026-09-02): flag the TRUNCATION signature -- the
            # volume cap set right at one unit AND the ladder topping out there, so
            # the multi-tank mechanism is silently disabled and the store is hard-
            # capped at a single vessel. This is exactly the Stadtbach artefact
            # (V_max = unit_tank = 5000 m³, ladder ending at ~one tank) that made
            # "TES = boundary solution" look physical when it was a config cap.
            # Condition is narrow (cap ≈ unit AND ladder near the cap) so it does
            # NOT fire on a legitimately single large unit (e.g. one big pit, where
            # V_max ≠ unit_tank). If larger stores are intended, raise
            # discrete_energies_mwh AND V_max_m3 above unit_tank_m3.
            _cap_at_one_unit = abs(self.V_max_m3 - self.unit_tank_m3) < 0.05 * self.unit_tank_m3
            if self.unit_tank_m3 and max(n_tanks_list) <= 1 and _cap_at_one_unit \
                    and v_ub >= 0.8 * self.unit_tank_m3:
                logger.warning(
                    "[GEOMETRIC_STORAGE] %s: multi-tank never engages -- V_max_m3=%.0f ≈ "
                    "unit_tank_m3=%.0f and the ladder tops out at V=%.0f m³ (one vessel). "
                    "The store is HARD-CAPPED at a single tank; if larger stores are "
                    "intended, raise discrete_energies_mwh AND V_max_m3 above unit_tank_m3.",
                    comp, self.V_max_m3, self.unit_tank_m3, v_ub)
        elif use_discrete:
            K = self.n_discrete_sizes
            v_list = [self.V_max_effective * k / (K - 1) for k in range(K)]
            n_tanks_list = [0 if k == 0 else 1 for k in range(K)]
            v_ub = self.V_max_effective
        else:
            v_ub = self.V_max_effective

        setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
        setattr(m, f"{comp}_V_m3", pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, v_ub)))
        build = getattr(m, f"{comp}_build")
        V = getattr(m, f"{comp}_V_m3")
        n_tanks_expr = build  # default: one tank when built (continuous / even-spacing)

        if not self.investable:
            # Fixed/existing tank: geometry is known, not optimized.
            build.fix(1)
            V.fix(self.V_fixed_m3)
        elif use_discrete:
            # ── Discrete tank-size selection (exact, no big-M) ─────────────────
            # V and build become linear functions of the size binaries -> tight LP
            # relaxation (the continuous V + big-M coupling stalled TES-at-consumer
            # -node scenarios at 43-88 % gap). Large sizes = N identical tanks at the
            # site, so beta_tes (fixed cost) applies per tank (n_tanks below).
            K = len(v_list)
            setattr(m, f"{comp}_size_sel", pyo.Var(range(K), domain=pyo.Binary))
            ysel = getattr(m, f"{comp}_size_sel")
            _vl, _nl = list(v_list), list(n_tanks_list)  # freeze for the closures
            setattr(m, f"{comp}_size_one",
                    pyo.Constraint(rule=lambda mm: sum(ysel[k] for k in range(K)) == 1))
            setattr(m, f"{comp}_size_V",
                    pyo.Constraint(rule=lambda mm: V == sum(_vl[k] * ysel[k] for k in range(K))))
            setattr(m, f"{comp}_size_build",
                    pyo.Constraint(rule=lambda mm: build == sum(ysel[k] for k in range(K) if _vl[k] > 0)))
            setattr(m, f"{comp}_n_tanks",
                    pyo.Expression(rule=lambda mm: sum(_nl[k] * ysel[k] for k in range(K))))
            n_tanks_expr = getattr(m, f"{comp}_n_tanks")
        self._n_tanks_expr = n_tanks_expr

        # ── CAPEX expression (un-annualized; the assembler applies ANF) ──────
        # PER-TANK degressive cost (2026-09-04 storage-tech decision): C = N·C_unit(V/N)
        # with N = _nl[k] tanks and C_unit(v) = c0·(v/v0)^b. The curve is therefore
        # evaluated at the PER-TANK volume v/N — never above one unit (unit ≈ v0), so
        # a multi-tank farm never receives the unphysical whole-volume large-scale
        # discount; each tank pays its own single-vessel price. Attached per rung as a
        # constant selected by the size binary -> stays LINEAR (no PWL, no SOS2). c0
        # is turnkey/installed (incl. BoP), so there is NO separate β. Only valid with
        # the discrete ladder; otherwise fall back to legacy linear α·V + β·N.
        if self.cost_model == "degressive" and self.c0_eur and use_discrete:
            _c0, _v0, _b = self.c0_eur, self.v0_m3, self.exponent_b
            _cost_k = []
            for k in range(len(_vl)):
                if _vl[k] <= 0:
                    _cost_k.append(0.0)
                    continue
                _N = max(1, int(_nl[k]))
                _v_per = _vl[k] / _N                       # per-tank volume ≤ unit
                _cost_k.append(_N * _c0 * (_v_per / _v0) ** _b)
            setattr(m, f"{comp}_capex_raw",
                    pyo.Expression(rule=lambda mm: sum(_cost_k[k] * ysel[k] for k in range(len(_vl)))))
            self._capex_raw_expr = getattr(m, f"{comp}_capex_raw")
        else:
            self._capex_raw_expr = self.alpha_tes * V + self.beta_tes * n_tanks_expr

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

        # V bounds linked to build decision (Big-M). Skipped in discrete mode,
        # where the size selection already ties V and build exactly (no big-M).
        if not use_discrete:
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
        # Charge/discharge MODE BINARIES ELIMINATED (2026-07-13, "Edit A"): they only
        # forbade simultaneous charge+discharge, which strictly positive round-trip
        # losses (eff_c, eff_d < 1) already make sub-optimal — so they are provably
        # redundant (a standard exact simplification). Dropping them removes ~3
        # binaries/timestep (~26k full-year) and the big-M power linearisation, so
        # storage becomes a pure LP inside the dispatch and the LP relaxation is
        # tighter; the investment size-selection carries the remaining integrality.
        setattr(m, f"{comp}_E", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Qc", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Qd", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        E = getattr(m, f"{comp}_E")
        Qc = getattr(m, f"{comp}_Qc")
        Qd = getattr(m, f"{comp}_Qd")
        cm = dm = active = None  # eliminated (complementarity implied by losses)

        # ── Standing loss ────────────────────────────────────────────────────
        # Legacy ("proportional"): multiplicative fractional decay E[t]=prev·f,
        # size-independent (f = hourly_loss^dt).
        # v3 ("surface"): a CONSTANT standing loss Q̇_loss = U·k(AR)·V^(2/3)·ΔT [MW]
        # applied ADDITIVELY, and — crucially — computed the SAME way in BOTH the
        # fixed-V dispatch class and the endogenous investment class, so the
        # sweep<->MILP cross-validation (T5/F3) compares like with like. In the
        # investment class the per-rung constants Q̇_loss,k are selected by the size
        # binary (linear, no McCormick). The loss per m³ falls as V^(-1/3) (the
        # surface-area benefit). A tiny forced trickle keeps E ≥ Q̇_loss·dt when
        # near-empty (~0.002 % of capacity) — negligible and identical in both classes.
        q_loss_mw = None                 # None -> use multiplicative loss_factor (legacy)
        loss_factor = float(self.hourly_loss) ** self.dt_h
        _surface = (self.loss_model == "surface" and self.u_value_w_m2k > 0
                    and self.t_return_c is not None)
        if _surface:
            _k_ar = surface_factor(self.r_hd)
            _dT_loss = max((self.t_return_c + self.delta_T_k) - self.t_amb_c, 0.0)
            _coef = self.u_value_w_m2k * _k_ar * _dT_loss / 1.0e6   # MW per (m³)^(2/3)
            if self.V_fixed_m3 is not None:
                q_loss_mw = _coef * self.V_fixed_m3 ** (2.0 / 3.0)          # scalar
            elif use_discrete and v_list:
                _ql_k = [_coef * (v ** (2.0 / 3.0)) for v in v_list]         # per rung
                setattr(m, f"{comp}_qloss",
                        pyo.Expression(rule=lambda mm: sum(_ql_k[k] * ysel[k]
                                                           for k in range(len(v_list)))))
                q_loss_mw = getattr(m, f"{comp}_qloss")
            else:
                logger.info("[GEOMETRIC_STORAGE] %s: surface loss needs fixed V or a "
                            "discrete ladder; continuous V -> proportional loss.", comp)
        eff_c = max(self.eff_c, 1e-4)
        eff_d = max(self.eff_d, 1e-4)
        # ── Initial SOC (2026-09-22 FIX, defect 7 / B1c) ────────────────────────────────
        # OLD rule (found while auditing, asymmetric, not cyclic): E[0] was PINNED to a fixed
        # fraction (soc0_fraction × E_max, both networks 0.5) via a plain Expression -- not a
        # decision variable, no freedom at all -- while the terminal constraint was only a
        # ONE-SIDED inequality E[last] >= terminal_soc_fraction × E_max (also 0.5). So a tank
        # could end the year fuller than it started at no cost; the two fractions happening to
        # share the same 0.5 value made this easy to miss.
        # NEW rule: E[0] is a genuine free Var (not fixed), bounded like every other E[t] (0 <=
        # E0 <= E_max_expr via soc_hi_0 below, mirroring soc_hi), and closed cyclically with a
        # HARD equality E[last] == E[0] (see terminal_soc_fraction handling further below, which
        # now enforces this instead of the old one-sided >= 0.5 bound). Start is free, but bound.
        # Unbounded-above Var (like E[t] itself); soc_hi_0 below does the real bounding via a
        # Constraint, which works whether E_max_expr is a Var-linked Expression (investable) or
        # a plain float (fixed tank) -- Pyomo builds `E0 <= <literal>` fine in the latter case.
        E0 = pyo.Var(domain=pyo.NonNegativeReals)
        setattr(m, f"{comp}_E0", E0)
        setattr(m, f"{comp}_soc_hi_0", pyo.Constraint(expr=E0 <= E_max_expr))
        if self.e_min_fraction > 0.0:
            setattr(m, f"{comp}_soc_lo_0", pyo.Constraint(expr=E0 >= self.e_min_fraction * E_max_expr))
        soc0_expr = E0

        # SOC dynamics: first timestep uses soc0_expr (linear in V, not a fixed scalar).
        t_first = Tset.first()
        def soc_dyn(mm, t):
            prev = E[t - 1] if t != t_first else soc0_expr
            gain = eff_c * Qc[t] * self.dt_h - (Qd[t] * self.dt_h) / eff_d
            if q_loss_mw is not None:      # surface: additive constant standing loss
                return E[t] == prev + gain - q_loss_mw * self.dt_h
            return E[t] == prev * loss_factor + gain          # legacy: multiplicative decay
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

        # ── Power limits (Edit A: charge/discharge ≤ built power, no mode binary) ─
        # cap_p is already gated to 0 when the tank is not built (cap_p ≤ ratio·E_max,
        # E_max = energy_coeff·V, and V = 0 when build = 0), so these two linear limits
        # also enforce "no operation unless built" — with NO binaries and NO big-M.
        setattr(m, f"{comp}_qc_lim", pyo.Constraint(Tset, rule=lambda mm, t: Qc[t] <= cap_p))
        setattr(m, f"{comp}_qd_lim", pyo.Constraint(Tset, rule=lambda mm, t: Qd[t] <= cap_p))

        # ── OPTIONAL discharge-temperature mask (A, 2026-09-02) ──────────────
        # Conservative SENSITIVITY (not the energy-only base): forbid discharge in
        # hours where the network supply exceeds the store's temperature ceiling
        # (T_VL(t) > T_store_max), i.e. an atmospheric store cannot inject into a
        # hotter supply. This is a LOWER bound (ignores return-preheating, which the
        # energy-only base captures); if the atmospheric-vs-pressurised conclusion
        # survives this mask, it is robust. mask[t]∈{0,1}, precomputed from T_VL(t)
        # and t_store_max in scenario_runner. Pressurised (no ceiling) -> all 1s.
        if self.discharge_mask is not None:
            _mask = self.discharge_mask
            _n = len(_mask)
            def qd_mask(mm, t):
                mi = _mask[(t - 1) % _n] if _n else 1
                return Qd[t] <= cap_p * float(mi)
            setattr(m, f"{comp}_qd_mask", pyo.Constraint(Tset, rule=qd_mask))

        # Shared-port valid inequality (2026-07-13). A single-loop stratified tank
        # shares ONE heat-exchanger/pump train between charge and discharge, so
        # COMBINED throughput — not each direction independently — is capacity-
        # limited. DIAGNOSTIC FINDING (root-LP relaxation of SB-S2-HK0, TES at a
        # consumer node): without this, the two independent qc_lim/qd_lim constraints
        # let the LP relaxation charge AND discharge simultaneously at (near) full
        # cap_p in 97% of hours — a "wash" cycle that nets out almost exactly on the
        # local heat bus (Qc, Qd enter it unscaled by efficiency; only the SOC
        # recursion pays the round-trip loss + cycling_cost_eur_per_mwh), which the LP
        # exploits because marginal heat is cheap/free at many hours once generator
        # commitment is relaxed. This was the dominant driver of that scenario's 74%
        # MIP gap — NOT demand-charge peak-shaving, the original hypothesis (that term
        # was only 1.5% of the incumbent objective). The comment previously here
        # ("simultaneous charge+discharge is never optimal, so it needs no explicit
        # constraint") is true for a well-posed problem's TRUE optimum, given strictly
        # positive round-trip losses — but the diagnostic shows the LP relaxation used
        # for the B&B bound does not reach that optimum without this cut.
        setattr(m, f"{comp}_shared_port",
                pyo.Constraint(Tset, rule=lambda mm, t: Qc[t] + Qd[t] <= cap_p))

        # Terminal SOC constraint (2026-09-22 FIX, defect 7 / B1c): genuinely cyclic now --
        # E[last] == E0, where E0 is the free initial-SOC Var declared above (soc0_expr).
        # terminal_soc_fraction is no longer used here (kept as a constructor arg for back-
        # compat / non-cyclic callers) -- the cyclic equality replaces the old one-sided
        # E[last] >= terminal_soc_fraction * E_max inequality unconditionally for every
        # geometric_storage asset, since a hard cyclic SOC condition is a technology-neutral
        # correctness fix, not a scenario choice.
        t_last = Tset.last()
        setattr(m, f"{comp}_terminal", pyo.Constraint(expr=E[t_last] == E0))

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
            "n_tanks": self._n_tanks_expr,
            "capex_raw_expr": self._capex_raw_expr,  # un-annualized CAPEX (degressive or legacy)
            "V_m3": V,
            "cap_power": cap_p,
            "h_m": h_m3,   # None unless option_b=True
            "d_m": d_m3,   # None unless option_b=True
        }
