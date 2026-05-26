"""
Stratified Thermal Energy Storage Component
============================================

Two-zone thermal storage model for large-scale heat storage systems
(e.g., district heating, industrial applications).

Features:
- Two-zone stratification (hot/cold layers)
- Fixed design temperatures for linear formulation
- Geometry-based heat loss calculation
- Cylindrical tank geometry
- Piecewise-linear loss approximation
- Compatible with MIP solvers

Physical Model:
- Hot zone (top): T_hot (e.g., 90°C)
- Cold zone (bottom): T_cold (e.g., 40°C)
- Volume dynamics: charging increases hot volume, discharging decreases it
- Energy calculation: E = ρ × V × cp × (T - T_ref)
- Heat losses based on surface area and U-values

Author: CALION Framework
Version: 1.0.0
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    import pyomo.environ as pyo
except Exception:  # pragma: no cover
    pyo = None

from ...constants import EFFICIENCY_MAX, EFFICIENCY_MIN
from ..component import BaseComponent, Flow, InvestmentResult
from ..registry import register_component

# Physical constants
RHO_WATER = 1000.0  # kg/m³ - water density
CP_WATER = 4.186    # kJ/(kg·K) - specific heat capacity
T_REF = 0.0         # °C - reference temperature


def _prepare_series(
    indices: Iterable[int],
    series: Sequence[float] | Mapping[int, float] | None,
    default: float,
) -> dict[int, float]:
    """Return mapping for Pyomo params while supporting broadcasting."""
    idx_list = list(indices)
    if series is None:
        return {i: float(default) for i in idx_list}
    if isinstance(series, Mapping):
        return {i: float(series.get(i, default)) for i in idx_list}
    values = [float(v) for v in series]
    if len(values) == 1:
        return {i: float(values[0]) for i in idx_list}
    if len(values) != len(idx_list):
        raise ValueError("Series length does not match time index length")
    return {i: float(values[pos]) for pos, i in enumerate(idx_list)}


def calculate_cylindrical_geometry(
    volume_m3: float,
    aspect_ratio: float = 1.5,
    geometry_type: str = "tank"
) -> dict[str, float]:
    """
    Calculate geometry parameters for cylindrical storage tank.

    Args:
        volume_m3: Total storage volume in m³
        aspect_ratio: Height/Diameter ratio
            - 1.5-2.0 for above-ground tanks
            - 0.3-0.5 for pit thermal energy storage (PTES)
        geometry_type: "tank" or "pit"

    Returns:
        Dictionary with diameter, height, and surface areas
    """
    if geometry_type == "pit":
        aspect_ratio = min(aspect_ratio, 0.5)  # PTES are shallow

    # V = π × (D/2)² × H
    # H = aspect_ratio × D
    # V = π × (D/2)² × (aspect_ratio × D)
    # V = π × aspect_ratio × D³ / 4
    # D³ = 4V / (π × aspect_ratio)

    diameter = (4.0 * volume_m3 / (math.pi * aspect_ratio)) ** (1.0/3.0)
    height = aspect_ratio * diameter

    # Surface areas
    A_top = math.pi * (diameter / 2.0) ** 2
    A_side = math.pi * diameter * height
    A_bottom = A_top
    A_total = 2 * A_top + A_side

    return {
        "diameter_m": diameter,
        "height_m": height,
        "A_top_m2": A_top,
        "A_side_m2": A_side,
        "A_bottom_m2": A_bottom,
        "A_total_m2": A_total,
        "aspect_ratio": aspect_ratio,
        "volume_m3": volume_m3
    }


@register_component(
    "stratified_storage",
    category="storage",
    description="Two-zone stratified thermal energy storage with geometry-based losses",
    version="1.0.0"
)
class StratifiedStorageBlock(BaseComponent):
    """
    Two-zone stratified thermal energy storage.

    Models large-scale thermal storage with:
    - Hot zone (top) and cold zone (bottom)
    - Fixed design temperatures for linear formulation
    - Volume-based energy calculation
    - Geometry-based heat losses
    - Investment optimization capability

    Linear formulation suitable for MIP solvers.
    """

    def __init__(
        self,
        name: str,
        # Thermal parameters
        T_hot_C: float = 90.0,
        T_cold_C: float = 40.0,
        T_ambient_C: float = 10.0,
        T_ground_C: float = 10.0,
        # Geometry
        volume_total_m3: float | None = None,  # Auto-calculated if None
        aspect_ratio: float = 1.5,
        geometry_type: str = "tank",  # "tank" or "pit"
        # Heat transfer coefficients (U-values) [W/(m²·K)]
        U_top: float = 0.5,
        U_side: float = 0.3,
        U_bottom: float = 0.2,
        # Efficiency
        eff_c: float = 0.95,
        eff_d: float = 0.95,
        # Time step
        dt_h: float = 1.0,
        # Initial state
        soc0: float = 0.0,
        V_hot_init_fraction: float = 0.5,  # Initial fraction of hot volume
        # Investment parameters
        *,
        investable: bool,
        e_cap_min: float,
        e_cap_max: float,
        p_cap_min: float,
        p_cap_max: float,
        e_cap_init: float = 0.0,
        p_cap_init: float = 0.0,
        terminal_target: float | None = None,
        # Optional parameters
        eff_charge_series: Sequence[float] | Mapping[int, float] | None = None,
        eff_discharge_series: Sequence[float] | Mapping[int, float] | None = None,
        capacity_active_series: Sequence[float] | Mapping[int, float] | None = None,
        power_energy_coupling: float | None = None,
        # Piecewise linearization settings
        piecewise_n_points: int = 5,  # Number of breakpoints for piecewise linearization
        label: str | None = None
    ):
        """
        Initialize stratified storage component.

        Args:
            name: Component identifier
            T_hot_C: Hot zone temperature in °C
            T_cold_C: Cold zone temperature in °C
            T_ambient_C: Ambient temperature (for top/side losses) in °C
            T_ground_C: Ground temperature (for bottom losses) in °C
            volume_total_m3: Total storage volume (auto-calculated from e_cap_max if None)
            aspect_ratio: Height/Diameter ratio
            geometry_type: "tank" (H/D=1.5-2.0) or "pit" (H/D=0.3-0.5)
            U_top, U_side, U_bottom: Heat transfer coefficients [W/(m²·K)]
            eff_c, eff_d: Charging/discharging efficiency
            dt_h: Time step in hours
            soc0: Initial state of charge [MWh]
            V_hot_init_fraction: Initial fraction of hot volume (0-1)
            investable: Whether storage capacity is optimized
            e_cap_min, e_cap_max: Energy capacity bounds [MWh]
            p_cap_min, p_cap_max: Power capacity bounds [MW]
            e_cap_init, p_cap_init: Initial capacities
            terminal_target: Target SOC at end of horizon
            eff_charge_series, eff_discharge_series: Time-varying efficiencies
            capacity_active_series: Availability factor per timestep
            power_energy_coupling: Optional P/E ratio constraint
            piecewise_n_points: Breakpoints for piecewise loss linearization
            label: Human-readable label
        """
        super().__init__(name, label)

        # Validate temperatures
        self._validate_range(T_hot_C, "T_hot_C", 40.0, 120.0)
        self._validate_range(T_cold_C, "T_cold_C", 20.0, 80.0)
        if T_hot_C <= T_cold_C:
            raise ValueError(f"T_hot_C ({T_hot_C}) must be > T_cold_C ({T_cold_C})")

        self.T_hot = float(T_hot_C)
        self.T_cold = float(T_cold_C)
        self.T_ambient = float(T_ambient_C)
        self.T_ground = float(T_ground_C)
        self.delta_T = self.T_hot - self.T_cold

        # Validate efficiencies
        eff_c_val = float(eff_c)
        eff_d_val = float(eff_d)
        if not (EFFICIENCY_MIN <= eff_c_val <= EFFICIENCY_MAX):
            raise ValueError(f"Charge efficiency must be in [{EFFICIENCY_MIN}, {EFFICIENCY_MAX}]")
        if not (EFFICIENCY_MIN <= eff_d_val <= EFFICIENCY_MAX):
            raise ValueError(f"Discharge efficiency must be in [{EFFICIENCY_MIN}, {EFFICIENCY_MAX}]")

        self.eff_c = eff_c_val
        self.eff_d = eff_d_val
        self.dt_h = float(dt_h)
        self.soc0 = float(soc0)
        self.V_hot_init_fraction = float(V_hot_init_fraction)

        # Investment parameters
        self.investable = bool(investable)
        self.e_cap_min = float(e_cap_min)
        self.e_cap_max = float(e_cap_max)
        self.p_cap_min = float(p_cap_min)
        self.p_cap_max = float(p_cap_max)
        self.e_cap_init = float(e_cap_init)
        self.p_cap_init = float(p_cap_init)
        self.terminal_target = terminal_target
        self.power_energy_coupling = power_energy_coupling

        # Optional series
        self.eff_charge_series = eff_charge_series
        self.eff_discharge_series = eff_discharge_series
        self.capacity_active_series = capacity_active_series

        # Piecewise linearization
        self.piecewise_n_points = max(2, int(piecewise_n_points))

        # Calculate or use provided geometry
        if volume_total_m3 is None:
            # Auto-calculate from energy capacity
            # Usable energy swing: E_usable [MWh] = ρ × V × cp × (T_hot - T_cold) / 3600000
            # V [m³] = E_cap_max [MWh] × 3600000 / (ρ [kg/m³] × cp [kJ/(kg·K)] × delta_T [K])
            volume_total_m3 = (
                e_cap_max * 3600000.0 / (RHO_WATER * CP_WATER * self.delta_T)
            )

        self.volume_total = float(volume_total_m3)
        self.aspect_ratio = float(aspect_ratio)
        self.geometry_type = geometry_type

        # Calculate cylindrical geometry
        self.geometry = calculate_cylindrical_geometry(
            self.volume_total,
            self.aspect_ratio,
            self.geometry_type
        )

        # Store U-values [W/(m²·K)]
        self.U_top = float(U_top)
        self.U_side = float(U_side)
        self.U_bottom = float(U_bottom)

        # Calculate energy-specific constant [MWh / (m³ · K)]
        # E [MWh] = ρ [kg/m³] × V [m³] × cp [kJ/(kg·K)] × ΔT [K] / 3600000 [kJ/MWh]
        # e_specific = ρ × cp / 3600000
        self.e_specific = RHO_WATER * CP_WATER / 3600000.0  # [MWh/(m³·K)]

        # Calculate initial hot volume from soc0
        # Assuming uniform initial temperature distribution
        self.V_hot_init = self.volume_total * self.V_hot_init_fraction

    def attach(self, m, Tset, cfg, buses):
        """
        Attach stratified storage to Pyomo model.

        Creates:
        - V_hot[t], V_cold[t]: Zone volumes
        - E_total[t]: Total energy content
        - Qc[t], Qd[t]: Charging/discharging power
        - Constraints for volume balance, energy calculation, dynamics, losses

        Returns:
            Dictionary with flows, investment, state, and metadata
        """
        if pyo is None:
            raise RuntimeError("Pyomo is required to attach blocks")

        comp = self.name
        times = list(Tset)

        # ========================================
        # VARIABLES
        # ========================================

        # Zone volumes [m³]
        setattr(m, f"{comp}_V_hot", pyo.Var(Tset, bounds=(0, self.volume_total)))
        setattr(m, f"{comp}_V_cold", pyo.Var(Tset, bounds=(0, self.volume_total)))

        # Total energy [MWh]
        setattr(m, f"{comp}_E_total", pyo.Var(Tset, domain=pyo.NonNegativeReals))

        # Charging/discharging power [MW]
        setattr(m, f"{comp}_Qc", pyo.Var(Tset, domain=pyo.NonNegativeReals))
        setattr(m, f"{comp}_Qd", pyo.Var(Tset, domain=pyo.NonNegativeReals))

        # Mode binaries
        setattr(m, f"{comp}_build", pyo.Var(domain=pyo.Binary))
        setattr(m, f"{comp}_charge_mode", pyo.Var(Tset, domain=pyo.Binary))
        setattr(m, f"{comp}_discharge_mode", pyo.Var(Tset, domain=pyo.Binary))
        setattr(m, f"{comp}_active", pyo.Var(Tset, domain=pyo.Binary))

        # Capacities
        setattr(m, f"{comp}_cap_energy", pyo.Var(
            domain=pyo.NonNegativeReals, bounds=(0.0, self.e_cap_max)
        ))
        setattr(m, f"{comp}_cap_power", pyo.Var(
            domain=pyo.NonNegativeReals, bounds=(0.0, self.p_cap_max)
        ))

        # Get variable references
        V_hot = getattr(m, f"{comp}_V_hot")
        V_cold = getattr(m, f"{comp}_V_cold")
        E_total = getattr(m, f"{comp}_E_total")
        Qc = getattr(m, f"{comp}_Qc")
        Qd = getattr(m, f"{comp}_Qd")
        build = getattr(m, f"{comp}_build")
        charge_mode = getattr(m, f"{comp}_charge_mode")
        discharge_mode = getattr(m, f"{comp}_discharge_mode")
        active = getattr(m, f"{comp}_active")
        cap_e = getattr(m, f"{comp}_cap_energy")
        cap_p = getattr(m, f"{comp}_cap_power")

        # ========================================
        # PARAMETERS
        # ========================================

        # Efficiency series
        effc_map = _prepare_series(times, self.eff_charge_series, self.eff_c)
        effd_map = _prepare_series(times, self.eff_discharge_series, self.eff_d)
        active_limit_map = _prepare_series(times, self.capacity_active_series, 1.0)

        setattr(m, f"{comp}_effc", pyo.Param(Tset, initialize=effc_map, mutable=True))
        setattr(m, f"{comp}_effd", pyo.Param(Tset, initialize=effd_map, mutable=True))
        setattr(m, f"{comp}_capacity_active_limit",
                pyo.Param(Tset, initialize=active_limit_map, mutable=True))

        # Geometry parameters
        setattr(m, f"{comp}_volume_total", pyo.Param(initialize=self.volume_total))
        setattr(m, f"{comp}_T_hot", pyo.Param(initialize=self.T_hot))
        setattr(m, f"{comp}_T_cold", pyo.Param(initialize=self.T_cold))
        setattr(m, f"{comp}_delta_T", pyo.Param(initialize=self.delta_T))

        # Investment bounds
        setattr(m, f"{comp}_capE_min", pyo.Param(initialize=self.e_cap_min))
        setattr(m, f"{comp}_capE_max", pyo.Param(initialize=self.e_cap_max))
        setattr(m, f"{comp}_capP_min", pyo.Param(initialize=self.p_cap_min))
        setattr(m, f"{comp}_capP_max", pyo.Param(initialize=self.p_cap_max))

        # Fix or initialize capacities
        if not self.investable:
            build.fix(1 if self.e_cap_max > 0 else 0)
            cap_e.fix(self.e_cap_init if self.e_cap_init > 0 else self.e_cap_max)
            cap_p.fix(self.p_cap_init if self.p_cap_init > 0 else self.p_cap_max)
        else:
            cap_e.set_value(self.e_cap_init if self.e_cap_init > 0 else self.e_cap_min)
            cap_p.set_value(self.p_cap_init if self.p_cap_init > 0 else self.p_cap_min)

        # ========================================
        # CONSTRAINTS
        # ========================================

        # (1) Volume balance: V_hot + V_cold = V_total
        def volume_balance_rule(mm, t):
            return V_hot[t] + V_cold[t] == self.volume_total
        setattr(m, f"{comp}_volume_balance", pyo.Constraint(Tset, rule=volume_balance_rule))

        # (2) Energy from volumes (LINEAR!)
        # E_hot = e_specific * T_hot * V_hot
        # E_cold = e_specific * T_cold * V_cold
        # E_total = E_hot + E_cold
        def energy_from_volume_rule(mm, t):
            e_hot = self.e_specific * self.T_hot * V_hot[t]
            e_cold = self.e_specific * self.T_cold * V_cold[t]
            return E_total[t] == e_hot + e_cold
        setattr(m, f"{comp}_energy_calc", pyo.Constraint(Tset, rule=energy_from_volume_rule))

        # ========================================
        # PIECEWISE-LINEAR LOSS MODEL (MILP-Compatible)
        # ========================================
        # Instead of constant 50% assumption, use PWL approximation
        # based on actual V_hot/V_total ratio.
        #
        # Creates V_loss[t] as a variable linked to V_hot[t-1] via PWL constraint
        # ========================================
        use_pwl_loss = cfg.get('use_pwl_loss', True)

        if use_pwl_loss and self.piecewise_n_points >= 3:
            # Generate PWL data
            pwl_data = self.calculate_loss_piecewise_data()
            bp_ratios = pwl_data["breakpoints"]  # [0, 0.25, 0.5, 0.75, 1.0]
            bp_v_losses = pwl_data["volume_losses"]  # V_loss at each breakpoint

            n_segments = len(bp_ratios) - 1
            bp_V_hot = [r * self.volume_total for r in bp_ratios]

            # V_loss variable [m³]
            max_v_loss = max(bp_v_losses) * self.dt_h * 1.2 if bp_v_losses else 1.0
            setattr(m, f"{comp}_V_loss", pyo.Var(Tset, domain=pyo.NonNegativeReals, bounds=(0, max_v_loss)))
            V_loss_var = getattr(m, f"{comp}_V_loss")

            # Lambda variables for PWL interpolation (SOS2-style)
            # λ_i ≥ 0, Σλ_i = 1, at most 2 adjacent λ_i non-zero
            setattr(m, f"{comp}_pwl_lambda", pyo.Var(Tset, range(len(bp_ratios)),
                                                      domain=pyo.NonNegativeReals, bounds=(0, 1)))
            pwl_lambda = getattr(m, f"{comp}_pwl_lambda")

            # Constraint: Σλ = 1
            def lambda_sum_rule(mm, t):
                return sum(pwl_lambda[t, i] for i in range(len(bp_ratios))) == 1
            setattr(m, f"{comp}_pwl_lambda_sum", pyo.Constraint(Tset, rule=lambda_sum_rule))

            # Constraint: V_hot[t-1] = Σ λ_i * V_bp_i (links V_hot to breakpoints)
            def v_hot_pwl_rule(mm, t):
                if t == Tset.first():
                    V_prev = self.V_hot_init
                else:
                    V_prev = V_hot[t-1]
                return V_prev == sum(pwl_lambda[t, i] * bp_V_hot[i] for i in range(len(bp_ratios)))
            setattr(m, f"{comp}_v_hot_pwl", pyo.Constraint(Tset, rule=v_hot_pwl_rule))

            # Constraint: V_loss = Σ λ_i * V_loss_bp_i (interpolated loss)
            # Note: V_loss from calculate_loss_piecewise_data is per hour, multiply by dt_h
            def v_loss_pwl_rule(mm, t):
                return V_loss_var[t] == sum(
                    pwl_lambda[t, i] * bp_v_losses[i] * self.dt_h
                    for i in range(len(bp_ratios))
                )
            setattr(m, f"{comp}_v_loss_pwl", pyo.Constraint(Tset, rule=v_loss_pwl_rule))

            # SOS2 constraint: enforce adjacency (binary variables for segment selection)
            setattr(m, f"{comp}_pwl_seg", pyo.Var(Tset, range(n_segments), domain=pyo.Binary))
            pwl_seg = getattr(m, f"{comp}_pwl_seg")

            # Only one segment active
            def one_seg_rule(mm, t):
                return sum(pwl_seg[t, s] for s in range(n_segments)) == 1
            setattr(m, f"{comp}_pwl_one_seg", pyo.Constraint(Tset, rule=one_seg_rule))

            # Lambda constraints: λ_i can only be non-zero if adjacent segment is active
            def lambda_seg_rule(mm, t, i):
                if i == 0:
                    return pwl_lambda[t, i] <= pwl_seg[t, 0]
                elif i == len(bp_ratios) - 1:
                    return pwl_lambda[t, i] <= pwl_seg[t, n_segments - 1]
                else:
                    return pwl_lambda[t, i] <= pwl_seg[t, i-1] + pwl_seg[t, i]
            setattr(m, f"{comp}_lambda_seg", pyo.Constraint(Tset, range(len(bp_ratios)), rule=lambda_seg_rule))

            logger.info(f"Storage {comp}: PWL loss model with {len(bp_ratios)} breakpoints")
            logger.debug(f"  Breakpoint ratios: {bp_ratios}")
            logger.debug(f"  V_loss at breakpoints (m³/h): {[f'{v:.4f}' for v in bp_v_losses]}")

        else:
            # Simple constant loss model (original)
            V_loss_var = None

        # (3) Volume dynamics with losses
        def volume_dynamics_rule(mm, t):
            effc = mm.__getattribute__(f"{comp}_effc")[t]
            effd = mm.__getattribute__(f"{comp}_effd")[t]

            # Previous hot volume
            if t == Tset.first():
                V_prev = self.V_hot_init
            else:
                V_prev = V_hot[t-1]

            # Volume change from charging/discharging
            # ΔE_charge = eff_c * Qc * dt_h [MWh]
            # ΔV_charge [m³] = ΔE_charge [MWh] / (e_specific [MWh/(m³·K)] * delta_T [K])
            conversion_factor = 1.0 / (self.e_specific * self.delta_T)

            delta_V_charge = effc * Qc[t] * self.dt_h * conversion_factor
            delta_V_discharge = (Qd[t] / effd) * self.dt_h * conversion_factor

            # Heat losses
            if V_loss_var is not None:
                # PWL model: V_loss determined by separate constraint
                V_loss = V_loss_var[t]
            else:
                # Simplified: constant rate based on 50% fill assumption
                V_loss = self._calculate_volume_loss_simple(V_prev, t)

            return V_hot[t] == V_prev + delta_V_charge - delta_V_discharge - V_loss

        setattr(m, f"{comp}_volume_dynamics", pyo.Constraint(Tset, rule=volume_dynamics_rule))

        # (4) Capacity constraints
        def energy_cap_hi_rule(mm, t):
            return E_total[t] <= cap_e * active[t]
        setattr(m, f"{comp}_energy_cap_hi", pyo.Constraint(Tset, rule=energy_cap_hi_rule))

        def power_cap_charge_rule(mm, t):
            return Qc[t] <= cap_p * charge_mode[t]
        setattr(m, f"{comp}_power_cap_charge", pyo.Constraint(Tset, rule=power_cap_charge_rule))

        def power_cap_discharge_rule(mm, t):
            return Qd[t] <= cap_p * discharge_mode[t]
        setattr(m, f"{comp}_power_cap_discharge", pyo.Constraint(Tset, rule=power_cap_discharge_rule))

        # (5) Mode constraints
        def mode_constraint_rule(mm, t):
            return charge_mode[t] + discharge_mode[t] <= active[t]
        setattr(m, f"{comp}_mode_constraint", pyo.Constraint(Tset, rule=mode_constraint_rule))

        def active_build_rule(mm, t):
            return active[t] <= build
        setattr(m, f"{comp}_active_build", pyo.Constraint(Tset, rule=active_build_rule))

        def active_limit_rule(mm, t):
            limit = mm.__getattribute__(f"{comp}_capacity_active_limit")[t]
            return active[t] <= limit
        setattr(m, f"{comp}_active_limit", pyo.Constraint(Tset, rule=active_limit_rule))

        # (6) Investment constraints
        def cap_e_hi_rule(mm):
            return cap_e <= mm.__getattribute__(f"{comp}_capE_max") * build
        setattr(m, f"{comp}_capE_hi", pyo.Constraint(rule=cap_e_hi_rule))

        def cap_e_lo_rule(mm):
            return cap_e >= mm.__getattribute__(f"{comp}_capE_min") * build
        setattr(m, f"{comp}_capE_lo", pyo.Constraint(rule=cap_e_lo_rule))

        def cap_p_hi_rule(mm):
            return cap_p <= mm.__getattribute__(f"{comp}_capP_max") * build
        setattr(m, f"{comp}_capP_hi", pyo.Constraint(rule=cap_p_hi_rule))

        def cap_p_lo_rule(mm):
            return cap_p >= mm.__getattribute__(f"{comp}_capP_min") * build
        setattr(m, f"{comp}_capP_lo", pyo.Constraint(rule=cap_p_lo_rule))

        # (7) Optional power-energy coupling
        if self.power_energy_coupling is not None:
            coupling = float(self.power_energy_coupling)

            def power_energy_ratio_rule(mm):
                return cap_p <= coupling * cap_e
            setattr(m, f"{comp}_capP_coupling", pyo.Constraint(rule=power_energy_ratio_rule))

        # (8) Initial SOC constraint
        if self.soc0 > 0:
            setattr(m, f"{comp}_soc0_cap", pyo.Constraint(expr=self.soc0 <= cap_e))

        # (9) NOTE: Terminal constraint is created at the system_builder level (system_builder.py:685-699)
        # to allow for policy-based constraints (==, >=) based on terminal_policy.
        # Do NOT create a duplicate constraint here.

        # ========================================
        # REGISTER FLOWS
        # ========================================

        self.add_flow(Flow(
            bus="heat",
            direction="output",
            variable=Qd,
            nominal_value=self.p_cap_max,
            investment=self.investable
        ))

        self.add_flow(Flow(
            bus="heat",
            direction="input",
            variable=Qc,
            nominal_value=self.p_cap_max,
            investment=self.investable
        ))

        # Register with buses
        if buses and "heat" in buses:
            buses["heat"].add_output(Qd)
            buses["heat"].add_input(Qc)

        # ========================================
        # RETURN RESULTS
        # ========================================

        return {
            "flows": {
                "heat": {"output": Qd, "input": Qc}
            },
            "investment": InvestmentResult(
                capacity_energy=cap_e,
                capacity_power=cap_p,
                build=build
            ) if self.investable else None,
            "state": E_total,
            "zones": {
                "V_hot": V_hot,
                "V_cold": V_cold
            },
            "metadata": {
                "T_hot_C": self.T_hot,
                "T_cold_C": self.T_cold,
                "delta_T_K": self.delta_T,
                "volume_total_m3": self.volume_total,
                "geometry": self.geometry,
                "U_top_W_m2K": self.U_top,
                "U_side_W_m2K": self.U_side,
                "U_bottom_W_m2K": self.U_bottom,
                "charge_mode": charge_mode,
                "discharge_mode": discharge_mode,
                "active": active,
                "efficiency_charge": self.eff_c,
                "efficiency_discharge": self.eff_d
            },
            # Legacy compatibility
            "Q_th_out": Qd,
            "Q_th_in": Qc,
            "SOC": E_total,
            "build": build,
            "cap_energy": cap_e,
            "cap_power": cap_p,
            "charge_mode": charge_mode,
            "discharge_mode": discharge_mode,
            "active": active,
        }

    def _calculate_volume_loss_simple(self, V_hot_prev, t):
        """
        Calculate volume loss using simplified constant-rate model.

        This is a placeholder for the piecewise-linear loss model.
        Uses geometry-based calibration to determine equivalent hourly loss rate.

        Args:
            V_hot_prev: Previous hot volume (for time-lagged linearization)
            t: Timestep index

        Returns:
            Volume loss in m³
        """
        # Simplified: assume average hot volume fraction of 50%
        avg_ratio_hot = 0.5

        # Calculate average heat loss power [MW]
        # Q_loss = U × A × ΔT / 1e6  (W → MW)
        Q_loss_top = (self.U_top * self.geometry["A_top_m2"] *
                      (self.T_hot - self.T_ambient) / 1e6)

        Q_loss_side = (self.U_side * self.geometry["A_side_m2"] * avg_ratio_hot *
                       (self.T_hot - self.T_ambient) / 1e6)

        Q_loss_bottom = (self.U_bottom * self.geometry["A_bottom_m2"] * avg_ratio_hot *
                         (self.T_hot - self.T_ground) / 1e6)

        Q_loss_total = Q_loss_top + Q_loss_side + Q_loss_bottom  # [MW]

        # Energy loss over timestep
        E_loss = Q_loss_total * self.dt_h  # [MWh]

        # Convert to volume loss
        # ΔV [m³] = ΔE [MWh] / (e_specific [MWh/(m³·K)] × delta_T [K])
        V_loss = E_loss / (self.e_specific * self.delta_T)  # [m³]

        return V_loss

    def calculate_loss_piecewise_data(self) -> dict[str, Any]:
        """
        Generate piecewise-linear approximation data for heat losses.

        Creates breakpoints for ratio_hot ∈ [0, 1] and corresponding volume losses.
        Can be used to create piecewise-linear constraints in Pyomo.

        Returns:
            Dictionary with:
            - breakpoints: List of ratio_hot values (0 to 1)
            - volume_losses: Corresponding volume loss values [m³/h]
            - energy_losses: Corresponding energy loss values [MWh/h]
        """
        breakpoints = [i / (self.piecewise_n_points - 1) for i in range(self.piecewise_n_points)]
        volume_losses = []
        energy_losses = []

        for ratio_hot in breakpoints:
            # Calculate heat loss for this ratio
            # Top: always hot zone
            Q_loss_top = (self.U_top * self.geometry["A_top_m2"] *
                          (self.T_hot - self.T_ambient) / 1e6)

            # Side: proportional to hot zone height
            Q_loss_side_hot = (self.U_side * self.geometry["A_side_m2"] * ratio_hot *
                               (self.T_hot - self.T_ambient) / 1e6)

            Q_loss_side_cold = (self.U_side * self.geometry["A_side_m2"] * (1 - ratio_hot) *
                                (self.T_cold - self.T_ambient) / 1e6)

            # Bottom: depends on whether it's in hot or cold zone
            # For simplicity: if ratio_hot > 0, bottom is cold; otherwise no loss
            if ratio_hot < 1.0:
                Q_loss_bottom = (self.U_bottom * self.geometry["A_bottom_m2"] *
                                (self.T_cold - self.T_ground) / 1e6)
            else:
                Q_loss_bottom = (self.U_bottom * self.geometry["A_bottom_m2"] *
                                (self.T_hot - self.T_ground) / 1e6)

            Q_loss_total = Q_loss_top + Q_loss_side_hot + Q_loss_side_cold + Q_loss_bottom

            # Energy loss per hour [MWh/h]
            E_loss_per_hour = Q_loss_total

            # Volume loss per hour [m³/h]
            # This is approximate since losses affect both zones differently
            # Simplified: allocate all losses to hot zone volume
            V_loss_per_hour = E_loss_per_hour / (self.e_specific * self.delta_T)

            volume_losses.append(V_loss_per_hour)
            energy_losses.append(E_loss_per_hour)

        return {
            "breakpoints": breakpoints,
            "volume_losses": volume_losses,
            "energy_losses": energy_losses
        }

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary of stratified storage configuration.

        Returns:
            Dictionary with configuration and calculated parameters
        """
        # Calculate some derived metrics
        # Maximum usable energy (from full hot to full cold)
        E_max_theoretical = (
            self.e_specific * self.delta_T * self.volume_total
        )

        # Loss rate at 50% fill
        loss_data = self.calculate_loss_piecewise_data()
        avg_loss_idx = len(loss_data["breakpoints"]) // 2
        avg_loss_MWh_per_h = loss_data["energy_losses"][avg_loss_idx]

        # Annual losses at average fill (exponential decay model)
        # hourly_retention = 1 - (loss_MW / E_max_MWh)
        # annual_retention = hourly_retention ^ 8760
        # annual_loss_rate = 1 - annual_retention
        if E_max_theoretical > 0:
            hourly_loss_fraction = avg_loss_MWh_per_h / E_max_theoretical
            hourly_retention = max(0.0, 1.0 - hourly_loss_fraction)
            annual_retention = hourly_retention ** 8760
            annual_loss_rate = (1.0 - annual_retention)
        else:
            annual_loss_rate = 0.0

        return {
            "component": "StratifiedStorage",
            "name": self.name,
            "thermal": {
                "T_hot_C": self.T_hot,
                "T_cold_C": self.T_cold,
                "delta_T_K": self.delta_T,
                "T_ambient_C": self.T_ambient,
                "T_ground_C": self.T_ground
            },
            "geometry": {
                **self.geometry,
                "type": self.geometry_type
            },
            "heat_transfer": {
                "U_top_W_m2K": self.U_top,
                "U_side_W_m2K": self.U_side,
                "U_bottom_W_m2K": self.U_bottom
            },
            "capacity": {
                "E_max_theoretical_MWh": E_max_theoretical,
                "volume_total_m3": self.volume_total,
                "investable": self.investable,
                "E_cap_range_MWh": [self.e_cap_min, self.e_cap_max],
                "P_cap_range_MW": [self.p_cap_min, self.p_cap_max]
            },
            "losses": {
                "avg_loss_MW_at_50pct": avg_loss_MWh_per_h,
                "annual_loss_rate_pct": annual_loss_rate * 100,
                "piecewise_n_points": self.piecewise_n_points
            },
            "efficiency": {
                "charge": self.eff_c,
                "discharge": self.eff_d,
                "roundtrip": self.eff_c * self.eff_d
            }
        }
