"""Curated reference for model-facing configuration keys.

The mappings below collect the YAML keys consumed by the MILP model and
its rolling-horizon driver, together with a short description of each
parameter.  They are intended as a lightweight anchor for documentation
that links formulas to the values read from `configs/*.yaml`.
"""

from __future__ import annotations

# Rolling-horizon parameters -------------------------------------------------
ROLLING_HORIZON: dict[str, str] = {
    "heat_horizon_hours": (
        "Optimisation window length in hours. Each RH solve spans this"
        " period before the workflow rolls forward."
    ),
    "step_hours": (
        "Number of hours that are committed from each window before the next"
        " iteration begins. A value smaller than `heat_horizon_hours`"
        " produces overlapping solves."
    ),
    "overlap_hours": (
        "Explicit overlap between consecutive windows. This is applied on top"
        " of the commit length to retain more look-ahead information."
    ),
    "terminal_policy": (
        "Storage terminal condition applied at the end of each window."
        " Common values are `free` (no constraint), `hold` (fix SOC to the"
        " initial value) or a numeric target such as `0.5` for a 50%"
        " end-of-window state of charge."
    ),
}

# Grid limits and pricing ----------------------------------------------------
GRID_LIMITS: dict[str, str] = {
    "max_import_mw": "Upper bound on power imported from the grid (MW).",
    "max_export_mw": "Upper bound on power exported to the grid (MW).",
    "big_m_grid_mw": (
        "Big-M constant used in the buy/sell mode constraints. Should be"
        " larger than any expected import/export flow to avoid infeasibility"
        " while keeping relaxations tight."
    ),
    "energy_fee_eur_mwh": "Per-MWh network fee applied to imported energy.",
    "gridcost_eur_mwh": (
        "Base electricity price for purchases before demand-charge or"
        " haircut adjustments."
    ),
    "sell_floor_eur_mwh": "Minimum selling price allowed after haircuts.",
    "sell_haircut_fraction": (
        "Fractional discount applied to the raw buy price when calculating"
        " the export tariff."
    ),
    "sell_spread_eur_mwh": (
        "Absolute price spread added between buying and selling to model"
        " transaction costs."
    ),
    "sell_fee_eur_mwh": "Per-MWh transaction fee for exported energy.",
    "sell_premium_eur_mwh": (
        "Optional premium granted on exports, e.g. for feed-in tariffs."
    ),
    "demand_charge_eur_per_mw_y": (
        "Annualised demand charge applied to the maximum import level."
    ),
    "year_fraction": (
        "Share of the year represented by the simulated horizon. Used to"
        " scale annual demand charges down to the model period."
    ),
}

# Storage policies and terminal settings ------------------------------------
STORAGE_POLICIES: dict[str, str] = {
    "terminal.policy": (
        "Dictates how the state of charge is treated at the end of the"
        " optimisation horizon. `free` leaves the terminal SOC unconstrained,"
        " `hold` fixes it to the initial SOC, and numeric values set an"
        " absolute MWh target."
    ),
    "terminal.target_mwh": (
        "Explicit MWh target for the terminal SOC; overrides symbolic"
        " policies when provided."
    ),
    "max_energy_mwh": "Nameplate energy capacity of the storage asset.",
    "max_power_mw": "Charge/discharge power limit for the storage asset.",
    "soc0_mwh": (
        "Initial state of charge at the start of the simulation. Also used"
        " as the reference for `terminal.policy=hold`."
    ),
}
