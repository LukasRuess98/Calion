"""Enhanced cost calculation with zonal support.

This module extends cost_calculator.py with zonal versions of cost functions.
It maintains backward compatibility (falls back to global if zones not present).
"""

from __future__ import annotations

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except Exception:  # pragma: no cover
    HAVE_PYOMO = False
    pyo = None


def calculate_demand_charge_zonal(
    model,
    include_demand: bool = True,
) -> any:
    """Calculate peak demand charge with ZONAL support.
    
    Improved version that uses zone-specific costs if available.
    Falls back to global if zones not present.
    
    Args:
        model: Pyomo model with zone_demand_charge or demand_charge_y
        include_demand: Whether to include demand charges
    
    Returns:
        Pyomo expression for total demand charge (over all zones)
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for cost calculation")
    
    if not include_demand:
        return 0
    
    # CHECK 1: Zonal costs defined?
    if hasattr(model, 'zone_demand_charge') and model.zone_demand_charge:
        # ✓ ZONAL MODE: Sum over all zones, all sharing the single grid peak
        demand_cost = sum(
            model.zone_demand_charge[zone_id] * model.year_frac * model.P_buy_peak
            for zone_id in model.zone_demand_charge.keys()
        )
        return demand_cost
    
    # CHECK 2: Global demand charge (fallback)
    if hasattr(model, 'P_buy_peak') and hasattr(model, 'demand_charge_y'):
        # ✓ GLOBAL MODE: Old behavior
        return model.demand_charge_y * model.year_frac * model.P_buy_peak
    
    # No demand charges defined
    return 0


def calculate_demand_charge_zonal_dynamic(
    model,
    include_demand: bool = True,
) -> any:
    """Calculate demand charge with DYNAMIC zonal costs (CSV-based).
    
    Uses hourly tariffs from zone_demand_charge_ts if available.
    Falls back to static zone costs, then global.
    
    Args:
        model: Pyomo model with zone_demand_charge_ts[zone][t] or fallbacks
        include_demand: Whether to include demand charges
    
    Returns:
        Pyomo expression for total demand charge (sum over zones and time)
    """
    if not HAVE_PYOMO:
        raise ImportError("Pyomo is required for cost calculation")
    
    if not include_demand:
        return 0
    
    # CHECK 1: Dynamic zonal costs (hourly)?
    if hasattr(model, 'zone_demand_charge_ts') and model.zone_demand_charge_ts:
        # ✓ DYNAMIC ZONAL MODE: Sum over zones × timesteps
        demand_cost = sum(
            model.zone_demand_charge_ts[zone_id][t] * 
            model.P_buy_by_zone.get(zone_id, model.P_buy)[t] *
            model.dt_h  # dt_h should be set on model
            for zone_id in model.zone_demand_charge_ts.keys()
            for t in model.t
        )
        return demand_cost
    
    # CHECK 2: Static zonal costs (fallback)?
    if hasattr(model, 'zone_demand_charge') and model.zone_demand_charge:
        # ✓ STATIC ZONAL MODE: Per-zone, annual, all sharing the single grid peak
        demand_cost = sum(
            model.zone_demand_charge[zone_id] * model.year_frac * model.P_buy_peak
            for zone_id in model.zone_demand_charge.keys()
        )
        return demand_cost
    
    # CHECK 3: Global (fallback)
    if hasattr(model, 'P_buy_peak') and hasattr(model, 'demand_charge_y'):
        return model.demand_charge_y * model.year_frac * model.P_buy_peak
    
    return 0


# ============================================================================
# EXAMPLE: Before/After Comparison
# ============================================================================

"""
BEFORE (global only):
─────────────────────

    demand_cost = model.demand_charge_y * model.year_frac * model.P_buy_peak
    
    Example: 
    - All zones: 50,000 EUR/MW/Year
    - Peak power: 75 MW total (from 1 global P_buy_peak)
    - Cost: 50,000 * 1.0 * 75 = 3,750,000 EUR
    
    PROBLEM: Ignores zone-specific costs!


AFTER (with zonal support):
────────────────────────────

    demand_cost = sum(
        zone_demand_charge[zone] * year_frac * P_buy_peak_by_zone[zone]
        for zone in zones
    )
    
    Example:
    - plant_main:  0 EUR/MW/Y × 0 MW    = 0
    - j_central:  30,000 EUR/MW/Y × 65 MW = 1,950,000 EUR
    - j_south:    70,000 EUR/MW/Y × 70 MW = 4,900,000 EUR
    ─────────────────────────────────────────────────
    Total:                                 6,850,000 EUR
    
    ADVANTAGE: Individual zone costs respected!
"""
