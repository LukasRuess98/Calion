# energis/models/network_physics.py

import math
from typing import Dict

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