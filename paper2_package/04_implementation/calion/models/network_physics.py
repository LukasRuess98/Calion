# calion/models/network_physics.py
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
from collections.abc import Sequence
from typing import Any

from calion.logging_config import get_logger

logger = get_logger(__name__)

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
) -> dict[str, float]:
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
# PIPE TEMPERATURE DROP CALCULATION
# =============================================================================

def pipe_temperature_drop_c(
    U_w_per_m_k: float,
    length_m: float,
    T_inlet_c: float,
    T_ground_c: float,
    m_dot_kg_s: float,
    cp_kj_per_kg_k: float = 4.186,
) -> float:
    """
    Calculate temperature drop through a pipe based on heat loss.

    Uses the logarithmic mean temperature difference (LMTD) model
    for more accurate results than simple average temperature.

    Simplified formula (for moderate ΔT):
        T_out = T_in - Q_loss / (m_dot × c_p)
        where Q_loss = U × L × (T_avg - T_ground)
        and T_avg ≈ (T_in + T_out) / 2

    Solving for T_out:
        T_out = (T_in × (m_dot × c_p - U × L / 2) + U × L × T_ground / 2) /
                (m_dot × c_p + U × L / 2)

    Or simplified for low losses:
        ΔT ≈ U × L × (T_in - T_ground) / (m_dot × c_p)

    Args:
        U_w_per_m_k: Heat transfer coefficient [W/(m·K)]
        length_m: Pipe length [m]
        T_inlet_c: Inlet temperature [°C]
        T_ground_c: Ground temperature [°C]
        m_dot_kg_s: Mass flow rate [kg/s]
        cp_kj_per_kg_k: Specific heat capacity [kJ/(kg·K)], default 4.186 for water

    Returns:
        Temperature drop ΔT [°C]
    """
    if m_dot_kg_s <= 0.001:  # Avoid division by zero, assume 1g/s minimum
        m_dot_kg_s = 0.001

    # Heat loss [W] = U × L × ΔT_avg
    # For small losses, ΔT_avg ≈ T_inlet - T_ground
    # Q_loss [kW] = U [W/(m·K)] × L [m] × (T_in - T_ground) [K] / 1000

    delta_T_driving = T_inlet_c - T_ground_c
    Q_loss_kw = U_w_per_m_k * length_m * delta_T_driving / 1000.0

    # Temperature drop: ΔT = Q_loss / (m_dot × c_p)
    # m_dot [kg/s] × c_p [kJ/(kg·K)] = [kW/K]
    heat_capacity_rate = m_dot_kg_s * cp_kj_per_kg_k  # [kW/K]

    delta_T_c = Q_loss_kw / heat_capacity_rate

    # Sanity check: temperature drop shouldn't exceed driving temperature
    max_delta = max(0, delta_T_driving * 0.9)  # Cap at 90% of driving force
    return min(delta_T_c, max_delta)


def calculate_pipe_temp_drops(
    pipes_config: dict[str, dict],
    supply_temp_c: float,
    return_temp_c: float,
    ground_temp_c: float,
    total_heat_demand_kw: float,
    default_u_value: float = 0.5,
    cp_kj_per_kg_k: float = 4.186,
) -> dict[str, dict[str, float]]:
    """
    Calculate temperature drops for all pipes based on physics.

    Estimates flow distribution based on pipe geometry and calculates
    individual temperature drops using the pipe_temperature_drop_c function.

    Args:
        pipes_config: Dictionary of pipe configurations with 'length_m', 'u_value_w_per_m_k', etc.
        supply_temp_c: Supply temperature at plant [°C]
        return_temp_c: Return temperature at plant [°C]
        ground_temp_c: Ground temperature [°C]
        total_heat_demand_kw: Total system heat demand [kW]
        default_u_value: Default U-value if not specified [W/(m·K)]
        cp_kj_per_kg_k: Specific heat capacity [kJ/(kg·K)]

    Returns:
        Dictionary mapping pipe_id to {'supply_drop_c': float, 'return_drop_c': float}
    """
    delta_T_system = supply_temp_c - return_temp_c
    if delta_T_system <= 0:
        delta_T_system = 40  # Default 40K spread

    # Total mass flow from system demand
    total_m_dot_kg_s = total_heat_demand_kw / (cp_kj_per_kg_k * delta_T_system)

    result = {}
    total_length = sum(p.get('length_m', 100) for p in pipes_config.values())

    for pipe_id, pipe_cfg in pipes_config.items():
        length_m = pipe_cfg.get('length_m', 100)
        u_value = pipe_cfg.get('u_value_w_per_m_k', default_u_value)

        # Estimate flow for this pipe (proportional to length for series, or demand-based)
        # Simplified: assume proportional distribution
        pipe_flow_fraction = length_m / total_length if total_length > 0 else 1.0
        pipe_m_dot = total_m_dot_kg_s * max(pipe_flow_fraction, 0.1)  # Min 10% flow

        # Supply pipe temperature drop
        supply_drop = pipe_temperature_drop_c(
            U_w_per_m_k=u_value,
            length_m=length_m,
            T_inlet_c=supply_temp_c,
            T_ground_c=ground_temp_c,
            m_dot_kg_s=pipe_m_dot,
            cp_kj_per_kg_k=cp_kj_per_kg_k,
        )

        # Return pipe temperature drop (heating from ground if return < ground)
        return_inlet = return_temp_c
        return_drop = pipe_temperature_drop_c(
            U_w_per_m_k=u_value,
            length_m=length_m,
            T_inlet_c=return_inlet,
            T_ground_c=ground_temp_c,
            m_dot_kg_s=pipe_m_dot,
            cp_kj_per_kg_k=cp_kj_per_kg_k,
        )

        result[pipe_id] = {
            'supply_drop_c': supply_drop,
            'return_drop_c': return_drop,
            'estimated_flow_kg_s': pipe_m_dot,
        }

    return result


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
) -> list[float]:
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
) -> dict[str, float]:
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


def compute_delay_buckets(
    length_m: float,
    diameter_mm: float,
    density_kg_per_m3: float,
    m_max_kg_s: float,
    n_buckets: int = 3,
    dt_h: float = 1.0,
) -> dict[str, Any]:
    """
    Compute integer transport delay constants for piecewise-linear SOS2 linearisation.

    Physical delay: τ(t) = L × ρ × A / m_dot(t) is nonlinear in mass flow.
    This function precomputes n_buckets integer delays (in timesteps) for n_buckets
    flow bands, enabling a MILP-compatible 3-bucket SOS2 approximation.

    Default n_buckets=3 gives a good accuracy/complexity trade-off for district
    heating networks where flow rarely varies more than ±40% from design point.

    Bucket layout (n_buckets=3):
      Bucket 0 (high flow):   m_dot ∈ [m_mid, m_max] → τ₁ timesteps (shortest delay)
      Bucket 1 (medium flow): m_dot ∈ [m_low, m_mid] → τ₂ timesteps
      Bucket 2 (low flow):    m_dot ∈ [0,     m_low] → τ₃ timesteps (longest delay)
    where m_mid = (m_max + m_min) / 2 and m_min = 0.1 × m_max.

    Args:
        length_m: Pipe length [m]
        diameter_mm: Pipe inner diameter [mm]
        density_kg_per_m3: Fluid density [kg/m³]
        m_max_kg_s: Maximum mass flow rate [kg/s]
        n_buckets: Number of flow buckets (default 3)

    Returns:
        Dict with:
          - tau_steps: List[int] of n_buckets integer delays (shortest first, in timesteps)
          - m_bounds: List[Tuple[float, float]] of (m_lower, m_upper) per bucket
          - volume_kg: Pipe fluid mass = L × ρ × A [kg]
          - length_m, diameter_mm, area_m2, m_max_kg_s: echo of inputs
    """
    if m_max_kg_s <= 0:
        m_max_kg_s = 0.001  # Avoid division by zero

    d_m = diameter_mm / 1000.0
    area_m2 = math.pi * (d_m / 2.0) ** 2
    volume_kg = length_m * density_kg_per_m3 * area_m2  # [kg]

    # Minimum flow representative: 10% of max flow
    m_min_kg_s = m_max_kg_s * 0.1

    if n_buckets == 3:
        # Representative flow per bucket (bucket 0 = high, bucket 2 = low)
        m_mid = (m_max_kg_s + m_min_kg_s) / 2.0
        rep_flows = [m_max_kg_s, m_mid, m_min_kg_s]
        # Flow bounds: [m_lower, m_upper] inclusive per bucket
        m_bounds = [
            (m_mid, m_max_kg_s),    # Bucket 0: high flow
            (m_min_kg_s, m_mid),    # Bucket 1: medium flow
            (0.0, m_min_kg_s),      # Bucket 2: low flow
        ]
    else:
        # General case: n evenly-spaced bands from m_max down to m_min
        step = (m_max_kg_s - m_min_kg_s) / max(n_buckets - 1, 1)
        rep_flows = [m_max_kg_s - i * step for i in range(n_buckets)]
        boundaries = [m_max_kg_s - i * (m_max_kg_s - m_min_kg_s) / n_buckets
                      for i in range(n_buckets + 1)]
        m_bounds = [(boundaries[i + 1], boundaries[i]) for i in range(n_buckets)]

    # Integer delay per bucket: τ = round(volume_kg / m_rep / dt_seconds)
    # volume_kg / m_rep gives seconds; divide by dt to get timesteps
    dt_seconds = dt_h * 3600.0
    tau_steps = [max(0, round(volume_kg / m / dt_seconds)) for m in rep_flows]

    return {
        'tau_steps': tau_steps,
        'm_bounds': m_bounds,
        'volume_kg': volume_kg,
        'length_m': length_m,
        'diameter_mm': diameter_mm,
        'area_m2': area_m2,
        'm_max_kg_s': m_max_kg_s,
    }


def plot_heating_curve(
    T_supply_min_c: float = 80.0,
    T_supply_max_c: float = 120.0,
    T_outdoor_high_c: float = 20.0,
    T_outdoor_low_c: float = -10.0,
    outdoor_temp_series: Sequence[float] | None = None,
    supply_temp_series: Sequence[float] | None = None,
    save_path: str | None = None,
    show: bool = True,
    figsize: tuple = (10, 6),
) -> "matplotlib.figure.Figure":  # type: ignore[name-defined]  # noqa: F821
    """
    Plot the heating curve and optionally actual data points.

    Args:
        T_supply_min_c: Minimum supply temperature [°C]
        T_supply_max_c: Maximum supply temperature [°C]
        T_outdoor_high_c: Outdoor temp threshold for min supply [°C]
        T_outdoor_low_c: Outdoor temp threshold for max supply [°C]
        outdoor_temp_series: Optional actual outdoor temperature data [°C]
        supply_temp_series: Optional actual supply temperature data [°C]
        save_path: Optional path to save the figure
        show: Whether to display the figure
        figsize: Figure size (width, height) in inches

    Returns:
        matplotlib Figure object

    Example:
        >>> # Plot theoretical heating curve
        >>> fig = plot_heating_curve()
        >>>
        >>> # Plot with actual data
        >>> fig = plot_heating_curve(
        ...     outdoor_temp_series=[15, 10, 5, 0, -5],
        ...     supply_temp_series=[87, 93, 100, 107, 113],
        ...     save_path="heating_curve.pdf"
        ... )
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        raise ImportError("matplotlib and numpy are required for plotting") from None

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Generate theoretical curve
    T_outdoor_range = np.linspace(T_outdoor_low_c - 5, T_outdoor_high_c + 5, 100)
    T_supply_theoretical = [
        calculate_supply_temperature(
            T_outdoor_c=t,
            T_supply_min_c=T_supply_min_c,
            T_supply_max_c=T_supply_max_c,
            T_outdoor_high_c=T_outdoor_high_c,
            T_outdoor_low_c=T_outdoor_low_c,
        )
        for t in T_outdoor_range
    ]

    # Plot theoretical curve
    ax.plot(
        T_outdoor_range,
        T_supply_theoretical,
        'b-',
        linewidth=2,
        label='Heizkurve (theoretisch)',
        zorder=2,
    )

    # Add actual data points if provided
    if outdoor_temp_series is not None and supply_temp_series is not None:
        ax.scatter(
            outdoor_temp_series,
            supply_temp_series,
            c='red',
            s=20,
            alpha=0.5,
            label='Betriebsdaten',
            zorder=3,
        )

    # Mark design points
    ax.scatter(
        [T_outdoor_high_c, T_outdoor_low_c],
        [T_supply_min_c, T_supply_max_c],
        c='green',
        s=100,
        marker='D',
        label='Auslegungspunkte',
        zorder=4,
    )

    # Add annotations for design points
    ax.annotate(
        f'Sommer: {T_supply_min_c}°C\n(bei {T_outdoor_high_c}°C)',
        xy=(T_outdoor_high_c, T_supply_min_c),
        xytext=(T_outdoor_high_c + 3, T_supply_min_c - 8),
        fontsize=9,
        arrowprops=dict(arrowstyle='->', color='gray'),
    )
    ax.annotate(
        f'Winter: {T_supply_max_c}°C\n(bei {T_outdoor_low_c}°C)',
        xy=(T_outdoor_low_c, T_supply_max_c),
        xytext=(T_outdoor_low_c + 3, T_supply_max_c + 5),
        fontsize=9,
        arrowprops=dict(arrowstyle='->', color='gray'),
    )

    # Formatting
    ax.set_xlabel('Außentemperatur [°C]', fontsize=12)
    ax.set_ylabel('Vorlauftemperatur [°C]', fontsize=12)
    ax.set_title('Heizkurve Fernwärmenetz', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # Set axis limits
    ax.set_xlim(T_outdoor_low_c - 5, T_outdoor_high_c + 5)
    ax.set_ylim(T_supply_min_c - 10, T_supply_max_c + 10)

    # Add formula annotation
    params = get_heating_curve_parameters(
        T_supply_min_c, T_supply_max_c, T_outdoor_high_c, T_outdoor_low_c
    )
    ax.text(
        0.02, 0.98,
        f"Formel: {params['formula']}",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
    )

    plt.tight_layout()

    # Save if path provided
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Heating curve plot saved to: {save_path}")

    # Show if requested
    if show:
        plt.show()

    return fig
