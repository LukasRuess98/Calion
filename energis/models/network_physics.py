# energis/models/network_physics.py
"""
Network Physics Module
======================

Physical calculations for district heating networks:
- Mass flow from heat demand
- Flow velocity calculations
- Pipe heat losses
- Supply temperature heating curve (Heizkurve)
"""

import math
from typing import Dict, List, Union, Sequence

def heat_kw_to_mdot_kg_s(
    Q_kw: float,
    cp_kj_per_kg_k: float,
    delta_T_K: float,
) -> float:
    """
    Berechne Massenstrom aus Leistung.

    Formel:
        m_dot [kg/s] = Q [kW] / (cp [kJ/(kg·K)] * ΔT [K])
    """
    if delta_T_K <= 0 or cp_kj_per_kg_k <= 0:
        return 0.0
    return Q_kw / (cp_kj_per_kg_k * delta_T_K)


def mdot_to_velocity_m_s(
    mdot_kg_s: float,
    diameter_mm: float,
    rho_kg_per_m3: float,
) -> float:
    """
    Berechne Strömungsgeschwindigkeit aus Massenstrom.

    Formel:
        v = m_dot / (rho * A)
    """
    d_m = diameter_mm / 1000.0
    if d_m <= 0 or rho_kg_per_m3 <= 0:
        return 0.0

    area_m2 = math.pi * (d_m / 2) ** 2
    if area_m2 <= 0:
        return 0.0

    return mdot_kg_s / (rho_kg_per_m3 * area_m2)


def pipe_heat_loss_mw(
    U_w_per_m_k: float,
    length_m: float,
    T_fluid_c: float,
    T_ground_c: float,
) -> float:
    """
    Wärmeverlust einer Leitung (Vorlauf oder Rücklauf) in MW.

    Formel:
        Q_loss [MW] = U [W/(m·K)] * L [m] * (T_fluid - T_ground) [K] / 1e6
    """
    delta_T = T_fluid_c - T_ground_c
    return U_w_per_m_k * length_m * delta_T / 1e6


def pipe_total_heat_loss_mw(
    length_m: float,
    u_supply_w_per_m_k: float,
    u_return_w_per_m_k: float,
    T_supply_c: float,
    T_return_c: float,
    T_ground_c: float,
) -> Dict[str, float]:
    """
    Liefert separate und gesamte Verluste für Vor- und Rücklauf einer Leitung.
    """
    q_loss_supply_mw = pipe_heat_loss_mw(
        u_supply_w_per_m_k, length_m, T_supply_c, T_ground_c
    )
    q_loss_return_mw = pipe_heat_loss_mw(
        u_return_w_per_m_k, length_m, T_return_c, T_ground_c
    )
    return {
        "supply_mw": q_loss_supply_mw,
        "return_mw": q_loss_return_mw,
        "total_mw": q_loss_supply_mw + q_loss_return_mw,
    }


# =============================================================================
# HEATING CURVE (Heizkurve)
# =============================================================================

def calculate_supply_temperature(
    T_outdoor_c: float,
    T_supply_min_c: float = 80.0,
    T_supply_max_c: float = 120.0,
    T_outdoor_high_c: float = 20.0,
    T_outdoor_low_c: float = -10.0,
) -> float:
    """
    Calculate supply temperature based on outdoor temperature using a heating curve.

    Linear interpolation between two points:
    - At T_outdoor >= T_outdoor_high: T_supply = T_supply_min (summer mode)
    - At T_outdoor <= T_outdoor_low: T_supply = T_supply_max (winter mode)

    Default values create the curve:
    - 20°C outdoor → 80°C supply
    - -10°C outdoor → 120°C supply

    Formula:
        T_supply = T_supply_min + (T_supply_max - T_supply_min) *
                   (T_outdoor_high - T_outdoor) / (T_outdoor_high - T_outdoor_low)

    Args:
        T_outdoor_c: Current outdoor temperature [°C]
        T_supply_min_c: Minimum supply temperature (at high outdoor temp) [°C]
        T_supply_max_c: Maximum supply temperature (at low outdoor temp) [°C]
        T_outdoor_high_c: Outdoor temperature threshold for minimum supply [°C]
        T_outdoor_low_c: Outdoor temperature threshold for maximum supply [°C]

    Returns:
        Supply temperature [°C], clamped between T_supply_min and T_supply_max

    Example:
        >>> calculate_supply_temperature(10.0)  # 10°C outdoor
        93.33  # Interpolated supply temperature
        >>> calculate_supply_temperature(-10.0)  # -10°C outdoor
        120.0  # Maximum supply temperature
        >>> calculate_supply_temperature(25.0)  # 25°C outdoor (summer)
        80.0   # Minimum supply temperature
    """
    # Handle edge cases
    if T_outdoor_high_c <= T_outdoor_low_c:
        raise ValueError(
            f"T_outdoor_high ({T_outdoor_high_c}) must be > T_outdoor_low ({T_outdoor_low_c})"
        )

    # Clamp outdoor temperature to valid range
    T_outdoor_clamped = max(T_outdoor_low_c, min(T_outdoor_high_c, T_outdoor_c))

    # Linear interpolation
    # slope = (T_supply_max - T_supply_min) / (T_outdoor_low - T_outdoor_high)
    # T_supply = T_supply_min + slope * (T_outdoor - T_outdoor_high)

    delta_T_supply = T_supply_max_c - T_supply_min_c
    delta_T_outdoor = T_outdoor_high_c - T_outdoor_low_c

    T_supply = T_supply_min_c + delta_T_supply * (T_outdoor_high_c - T_outdoor_clamped) / delta_T_outdoor

    # Clamp result (should already be in range, but safety check)
    return max(T_supply_min_c, min(T_supply_max_c, T_supply))


def calculate_supply_temperature_series(
    T_outdoor_series: Sequence[float],
    T_supply_min_c: float = 80.0,
    T_supply_max_c: float = 120.0,
    T_outdoor_high_c: float = 20.0,
    T_outdoor_low_c: float = -10.0,
) -> List[float]:
    """
    Calculate supply temperature series for a sequence of outdoor temperatures.

    Args:
        T_outdoor_series: Sequence of outdoor temperatures [°C]
        T_supply_min_c: Minimum supply temperature [°C]
        T_supply_max_c: Maximum supply temperature [°C]
        T_outdoor_high_c: Outdoor temp threshold for min supply [°C]
        T_outdoor_low_c: Outdoor temp threshold for max supply [°C]

    Returns:
        List of supply temperatures [°C]

    Example:
        >>> outdoor = [15.0, 5.0, -5.0, 10.0]
        >>> calculate_supply_temperature_series(outdoor)
        [86.67, 100.0, 113.33, 93.33]
    """
    return [
        calculate_supply_temperature(
            T_outdoor_c=T_out,
            T_supply_min_c=T_supply_min_c,
            T_supply_max_c=T_supply_max_c,
            T_outdoor_high_c=T_outdoor_high_c,
            T_outdoor_low_c=T_outdoor_low_c,
        )
        for T_out in T_outdoor_series
    ]


def get_heating_curve_parameters(
    T_supply_min_c: float = 80.0,
    T_supply_max_c: float = 120.0,
    T_outdoor_high_c: float = 20.0,
    T_outdoor_low_c: float = -10.0,
) -> Dict[str, float]:
    """
    Calculate and return the heating curve parameters in slope-intercept form.

    The heating curve can be expressed as:
        T_supply = slope * T_outdoor + intercept

    Returns:
        Dictionary with:
        - slope: Temperature change per degree outdoor temp [°C/°C]
        - intercept: Y-intercept [°C]
        - T_supply_min: Minimum supply temperature [°C]
        - T_supply_max: Maximum supply temperature [°C]
        - T_outdoor_high: Upper outdoor temp threshold [°C]
        - T_outdoor_low: Lower outdoor temp threshold [°C]

    Example:
        >>> params = get_heating_curve_parameters()
        >>> params['slope']
        -1.333  # Supply temp decreases 1.33°C per 1°C outdoor increase
        >>> params['intercept']
        106.67  # At T_outdoor = 0°C, T_supply ≈ 106.67°C
    """
    delta_T_supply = T_supply_max_c - T_supply_min_c
    delta_T_outdoor = T_outdoor_high_c - T_outdoor_low_c

    # T_supply = T_supply_min + delta_T_supply * (T_outdoor_high - T_outdoor) / delta_T_outdoor
    # T_supply = T_supply_min + delta_T_supply * T_outdoor_high / delta_T_outdoor
    #            - delta_T_supply * T_outdoor / delta_T_outdoor
    # T_supply = intercept + slope * T_outdoor

    slope = -delta_T_supply / delta_T_outdoor
    intercept = T_supply_min_c + delta_T_supply * T_outdoor_high_c / delta_T_outdoor

    return {
        "slope": round(slope, 4),
        "intercept": round(intercept, 2),
        "T_supply_min_c": T_supply_min_c,
        "T_supply_max_c": T_supply_max_c,
        "T_outdoor_high_c": T_outdoor_high_c,
        "T_outdoor_low_c": T_outdoor_low_c,
        "formula": f"T_supply = {intercept:.2f} + ({slope:.4f}) * T_outdoor",
    }