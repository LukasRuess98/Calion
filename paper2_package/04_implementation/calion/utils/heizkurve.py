"""Heating curve (Heizkurve) utilities for Paper 2 investment optimization.

Computes supply temperature time series T_VL(t) from the parametric heating curve:

  T_VL(t) = clip(T_VL_min + k * (T_VL_max - T_VL_min) * (T_heiz - T_aus(t))
                                                         / (T_heiz - T_aus_design),
                 T_VL_min, T_VL_max)

Where:
  - k: slope multiplier (0..1]; HK0=1.0 (real curve), HK1=0.8, HK2=0.6
  - T_heiz: heating start temperature (default +15°C)
  - T_aus_design: design outdoor temperature (default -12°C, DIN EN 12831)

Physical behaviour: T_VL decreases as T_aus increases (warmer outside → cooler supply),
clamped to [T_VL_min, T_VL_max]. Lower k flattens the curve (reduced network temperatures).

The outer scenario loop in scenario_runner.py iterates over discrete (k, T_VL_min) pairs
rather than including k as an SOS1 variable, keeping the MILP linear.
"""

from __future__ import annotations

import numpy as np


# Water properties at ~75°C (used for TES capacity)
RHO_WATER_KG_M3 = 971.8
CP_WATER_KJ_KG_K = 4.189

# Default heating curve reference points (DIN EN 12831)
T_HEIZ_DEFAULT_C = 15.0      # outdoor temperature at which heating is no longer needed
T_AUS_DESIGN_C = -12.0       # design outdoor temperature (coldest day)


def compute_heizkurve(
    k: float,
    T_VL_min_c: float,
    T_VL_max_c: float,
    T_aus_ts: list[float] | np.ndarray,
    T_heiz_c: float = T_HEIZ_DEFAULT_C,
    T_aus_design_c: float = T_AUS_DESIGN_C,
) -> np.ndarray:
    """Compute supply temperature time series from heating curve parameters.

    Args:
        k: Slope multiplier (0 < k ≤ 1). k=1.0 → full heating curve (HK0).
            Lower k flattens the curve (lower network temperatures).
        T_VL_min_c: Minimum supply temperature [°C]. Floor of the curve.
        T_VL_max_c: Maximum supply temperature [°C]. Ceiling at design conditions.
        T_aus_ts: Outdoor temperature time series [°C], length T.
        T_heiz_c: Outdoor temperature above which no heating is needed [°C].
        T_aus_design_c: Design outdoor temperature [°C] (coldest day, DIN EN 12831).

    Returns:
        np.ndarray of shape (T,) with supply temperatures [°C] per timestep.
    """
    T_aus = np.asarray(T_aus_ts, dtype=float)
    span = T_VL_max_c - T_VL_min_c
    norm = T_heiz_c - T_aus_design_c  # positive denominator
    T_VL = T_VL_min_c + k * span * (T_heiz_c - T_aus) / norm
    return np.clip(T_VL, T_VL_min_c, T_VL_max_c)


def generate_hk_scenarios(
    k_values: list[float],
    T_VL_min_values: list[float],
    T_VL_max_c: float,
    T_aus_ts: list[float] | np.ndarray,
) -> list[dict]:
    """Generate a list of heat curve scenario dicts for the outer scenario loop.

    Each dict contains the precomputed T_VL array and the (k, T_VL_min) label.

    Args:
        k_values: List of heating curve slopes to enumerate.
        T_VL_min_values: List of minimum supply temperatures [°C] to enumerate.
        T_VL_max_c: Maximum supply temperature [°C], shared across scenarios.
        T_aus_ts: Outdoor temperature time series [°C].

    Returns:
        List of dicts with keys: 'k', 'T_VL_min_c', 'T_VL_max_c', 'T_VL_ts'
    """
    scenarios = []
    for k in k_values:
        for T_min in T_VL_min_values:
            T_VL = compute_heizkurve(k, T_min, T_VL_max_c, T_aus_ts)
            scenarios.append({
                "k": k,
                "T_VL_min_c": T_min,
                "T_VL_max_c": T_VL_max_c,
                "T_VL_ts": T_VL,
            })
    return scenarios


def check_consumer_min_temps(
    T_VL_ts: np.ndarray,
    consumer_min_temps_c: dict[str, float],
) -> dict[str, dict]:
    """Verify that the supply temperature satisfies all consumer minimum temperatures.

    Args:
        T_VL_ts: Supply temperature time series [°C].
        consumer_min_temps_c: Mapping of consumer_id → minimum required temperature [°C].

    Returns:
        Dict with per-consumer violations: {consumer_id: {'violations': int, 'max_deficit_c': float}}
        Empty dict if all constraints satisfied.
    """
    violations = {}
    for consumer_id, T_min in consumer_min_temps_c.items():
        deficit = T_min - T_VL_ts
        violated = deficit > 0
        n_viol = int(np.sum(violated))
        if n_viol > 0:
            violations[consumer_id] = {
                "violations": n_viol,
                "max_deficit_c": float(np.max(deficit)),
                "hours_below_pct": round(n_viol / len(T_VL_ts) * 100, 2),
            }
    return violations


def tes_thermal_capacity_mwh(
    V_TES_m3: float,
    delta_T_k: float,
    rho_kg_m3: float = RHO_WATER_KG_M3,
    cp_kj_kg_k: float = CP_WATER_KJ_KG_K,
) -> float:
    """Compute TES thermal capacity [MWh] from geometry and temperature spread.

    E_TES = rho * cp * delta_T * V / 3600  (kJ → kWh → MWh)

    Args:
        V_TES_m3: Storage volume [m³].
        delta_T_k: Temperature spread T_hot - T_cold [K].
        rho_kg_m3: Water density [kg/m³].
        cp_kj_kg_k: Specific heat capacity [kJ/(kg·K)].

    Returns:
        Thermal capacity [MWh].
    """
    energy_kj = rho_kg_m3 * cp_kj_kg_k * delta_T_k * V_TES_m3
    return energy_kj / 3600.0 / 1000.0  # kJ → MWh


def tes_operating_pressure_bar(h_TES_m: float, p_atm_bar: float = 1.01325) -> float:
    """Compute hydrostatic operating pressure at bottom of TES [bar].

    p_betr = p_atm + rho * g * h / 1e5

    Args:
        h_TES_m: TES height [m].
        p_atm_bar: Atmospheric pressure [bar], default 1.01325.

    Returns:
        Operating pressure [bar].
    """
    rho_kg_m3 = RHO_WATER_KG_M3
    g_m_s2 = 9.81
    hydrostatic_pa = rho_kg_m3 * g_m_s2 * h_TES_m
    return p_atm_bar + hydrostatic_pa / 1e5
