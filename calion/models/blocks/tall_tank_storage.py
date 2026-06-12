"""
Tall-Tank Thermal Storage with Static Pressure Head Coupling
=============================================================

Models a tall cylindrical hot-water tank (e.g., 20–70 m height) with:
- Two-zone stratification (hot/cold) based on volume fill
- Investable tank volume (optimizer chooses size up to geometry limit)
- Static pressure head coupled to network node: ΔP_head[t] = ρ·g·H·(V_hot[t]/V_cap)/1e5 [bar]
- MILP-compatible (no bilinear terms when milp_linearize=True; V_cap fixed to max in that mode)

Physical constants:
  ρ_water = 997 kg/m³ (at ~25 °C)
  cp_water = 4186 J/(kg·K)
  g = 9.81 m/s²
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ..component import BaseComponent, Flow, InvestmentResult
from ..registry import register_component

RHO_WATER = 997.0    # kg/m³
CP_WATER = 4186.0    # J/(kg·K)
G_ACCEL = 9.81       # m/s²
J_TO_MWH = 1.0 / 3.6e9


@register_component(
    "tall_tank_storage",
    category="storage",
    description="Tall cylindrical tank with static pressure head coupling",
)
class TallTankStorageBlock(BaseComponent):
    """
    Tall-tank stratified storage block.

    Parameters
    ----------
    name : str
    T_hot_C : float   Hot-zone temperature [°C]
    T_cold_C : float  Cold-zone temperature [°C]
    height_m : float  Tank height [m] — determines max static head
    diameter_m : float  Tank inner diameter [m] — used for V_max geometry
    dt_h : float      Time-step size [h]
    soc0_fraction : float  Initial hot-zone fraction [0–1], default 0.5
    cap_volume_min_m3 : float  Minimum investable volume [m³], default 0
    cap_volume_max_m3 : float | None  Maximum volume [m³]; None → π*(d/2)²*H
    milp_linearize : bool  If True, fix cap_volume to max → linear pressure head
    """

    def __init__(
        self,
        name: str,
        T_hot_C: float,
        T_cold_C: float,
        height_m: float,
        diameter_m: float,
        dt_h: float,
        *,
        soc0_fraction: float = 0.5,
        cap_volume_min_m3: float = 0.0,
        cap_volume_max_m3: float | None = None,
        milp_linearize: bool = False,
        label: str | None = None,
    ):
        super().__init__(name, label)
        self.T_hot_C = float(T_hot_C)
        self.T_cold_C = float(T_cold_C)
        if self.T_hot_C <= self.T_cold_C:
            raise ValueError(
                f"TallTankStorage '{name}': T_hot_C ({T_hot_C}) must be > T_cold_C ({T_cold_C})"
            )
        self.height_m = float(height_m)
        self.diameter_m = float(diameter_m)
        self.dt_h = float(dt_h)
        self.soc0_fraction = float(soc0_fraction)
        self.cap_volume_min_m3 = float(cap_volume_min_m3)
        # Geometry-derived maximum volume
        _v_geo = math.pi * (self.diameter_m / 2.0) ** 2 * self.height_m
        self.cap_volume_max_m3 = float(cap_volume_max_m3) if cap_volume_max_m3 is not None else _v_geo
        self.milp_linearize = bool(milp_linearize)

        # Pre-compute energy conversion factor: 1 m³ of hot water above T_cold → MWh
        dT_K = self.T_hot_C - self.T_cold_C
        self._e_per_m3_mwh = RHO_WATER * CP_WATER * dT_K * J_TO_MWH   # MWh/m³

        # Static head coefficient: ΔP [bar] = _head_coeff * V_hot[m³] / V_cap[m³]
        # = ρ·g·H / 1e5  [bar per unit fill-ratio]
        self._head_coeff_bar = RHO_WATER * G_ACCEL * self.height_m / 1e5

        logger.debug(
            "[TALL_TANK] '%s': H=%.1f m, D=%.1f m, V_max=%.1f m³, "
            "e_per_m3=%.4f MWh/m³, head_coeff=%.3f bar (full tank)",
            name, height_m, diameter_m, self.cap_volume_max_m3,
            self._e_per_m3_mwh, self._head_coeff_bar,
        )

    # ------------------------------------------------------------------
    # attach()
    # ------------------------------------------------------------------
    def attach(self, m: Any, Tset: Any, cfg: Any, buses: Any) -> dict:
        if pyo is None:  # pragma: no cover
            raise RuntimeError("Pyomo is required to attach TallTankStorageBlock")

        comp = self.name
        times = sorted(list(Tset))
        t0 = times[0]
        t_last = times[-1]

        V_max = self.cap_volume_max_m3
        V_min = self.cap_volume_min_m3
        V0 = V_max * self.soc0_fraction   # initial hot volume [m³]

        # ── Pyomo variables ────────────────────────────────────────────
        # Hot-zone volume [m³]
        setattr(m, f"{comp}_V_hot", pyo.Var(Tset, domain=pyo.NonNegativeReals, bounds=(0.0, V_max)))
        # Charge/discharge thermal power [MW]
        setattr(m, f"{comp}_Qc", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Qd", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        # Binary build decision
        setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
        # Tank volume investment variable [m³]
        # In MILP mode: fixed to V_max after building (keeps pressure head linear)
        setattr(m, f"{comp}_cap_volume", pyo.Var(domain=pyo.NonNegativeReals, bounds=(0.0, V_max)))
        # Static pressure head contribution [bar]
        setattr(m, f"{comp}_P_head", pyo.Var(Tset, domain=pyo.NonNegativeReals, bounds=(0.0, self._head_coeff_bar)))

        V_hot = getattr(m, f"{comp}_V_hot")
        Qc = getattr(m, f"{comp}_Qc")
        Qd = getattr(m, f"{comp}_Qd")
        build = getattr(m, f"{comp}_build")
        cap_vol = getattr(m, f"{comp}_cap_volume")
        P_head = getattr(m, f"{comp}_P_head")

        # MILP linearization: fix cap_volume = V_max (build decides yes/no only)
        if self.milp_linearize:
            cap_vol.fix(V_max)

        # ── Investment bounds (only when not MILP-fixed) ───────────────
        if not self.milp_linearize:
            def cap_vol_hi(mm):
                return cap_vol <= V_max * build
            def cap_vol_lo(mm):
                return cap_vol >= V_min * build
            setattr(m, f"{comp}_cap_vol_hi", pyo.Constraint(rule=cap_vol_hi))
            setattr(m, f"{comp}_cap_vol_lo", pyo.Constraint(rule=cap_vol_lo))
        else:
            # In MILP mode cap_volume is fixed; only build controls activation
            pass

        # ── Hot-volume bounds ──────────────────────────────────────────
        # Use V_max (scalar) * build in MILP to avoid Var*Var when cap_vol is fixed
        if self.milp_linearize:
            def v_hot_hi(mm, t):
                return V_hot[t] <= V_max * build
        else:
            def v_hot_hi(mm, t):
                return V_hot[t] <= cap_vol * build
        setattr(m, f"{comp}_v_hot_hi", pyo.Constraint(Tset, rule=v_hot_hi))

        # ── Volume dynamics ────────────────────────────────────────────
        # V_hot[t] = V_hot[t-1] + (Qc[t] - Qd[t]) * dt_h / e_per_m3  [m³]
        dt_h = self.dt_h
        e_m3 = self._e_per_m3_mwh  # MWh/m³ → MW·h/m³

        def vol_dyn(mm, t):
            if t == t0:
                # Initial SOC scales with build binary so V_hot[t0]=0 when tank not built
                v_prev = V0 * build
            else:
                idx = times.index(t)
                v_prev = V_hot[times[idx - 1]]
            return V_hot[t] == v_prev + (Qc[t] - Qd[t]) * dt_h / e_m3

        setattr(m, f"{comp}_vol_dyn", pyo.Constraint(Tset, rule=vol_dyn))

        # Terminal: hot volume at end >= initial (no free draining over horizon)
        setattr(m, f"{comp}_terminal", pyo.Constraint(expr=V_hot[t_last] >= V0 * build))

        # ── Power bounds ───────────────────────────────────────────────
        # Q_max_mw = V_max * e_per_m3 / dt_h  (full tank charge in one step)
        Q_max_mw = V_max * e_m3 / dt_h

        def qc_hi(mm, t):
            return Qc[t] <= Q_max_mw * build
        def qd_hi(mm, t):
            return Qd[t] <= Q_max_mw * build
        setattr(m, f"{comp}_qc_hi", pyo.Constraint(Tset, rule=qc_hi))
        setattr(m, f"{comp}_qd_hi", pyo.Constraint(Tset, rule=qd_hi))

        # ── Static pressure head ───────────────────────────────────────
        # P_head[t] = ρ·g·H·(V_hot[t] / V_cap) / 1e5
        # When MILP: V_cap = V_max (fixed Param) → linear in V_hot[t]
        # When NLP:  V_cap = cap_vol (Var) → bilinear, handled with direct expr
        head_coeff = self._head_coeff_bar  # bar at 100% fill

        if self.milp_linearize:
            # Linear: P_head[t] = head_coeff * V_hot[t] / V_max
            def p_head_rule(mm, t):
                return P_head[t] == head_coeff * V_hot[t] / V_max
            setattr(m, f"{comp}_p_head_con", pyo.Constraint(Tset, rule=p_head_rule))
        else:
            # NLP: bilinear P_head[t] * cap_vol == head_coeff * V_hot[t]
            # When build=0, cap_vol→0 makes P_head unconstrained; add explicit upper bound.
            def p_head_rule(mm, t):
                return P_head[t] * cap_vol == head_coeff * V_hot[t]
            def p_head_ub(mm, t):
                return P_head[t] <= head_coeff * build
            setattr(m, f"{comp}_p_head_con", pyo.Constraint(Tset, rule=p_head_rule))
            setattr(m, f"{comp}_p_head_ub", pyo.Constraint(Tset, rule=p_head_ub))

        # ── Register flows ─────────────────────────────────────────────
        self.add_flow(Flow(bus="heat", direction="output", variable=Qd, nominal_value=Q_max_mw, investment=True))
        self.add_flow(Flow(bus="heat", direction="input", variable=Qc, nominal_value=Q_max_mw, investment=True))

        logger.info(
            "[TALL_TANK] '%s' attached: V_max=%.1f m³, E_max=%.2f MWh, "
            "Q_max=%.2f MW, P_head_max=%.3f bar, MILP=%s",
            comp, V_max, V_max * e_m3, Q_max_mw, head_coeff, self.milp_linearize,
        )

        return {
            "flows": {"heat": {"output": Qd, "input": Qc}},
            "investment": InvestmentResult(
                capacity=cap_vol,
                build=build,
            ),
            "pressure_head": P_head,
            "V_hot": V_hot,
            "cap_volume": cap_vol,
            # Legacy keys used by component_assembler
            "Q_th_out": Qd,
            "Q_th_in": Qc,
            "build": build,
            "cap_energy": None,   # not used; volume is the investment var
            "cap_power": None,
        }
