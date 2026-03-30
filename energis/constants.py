"""
Constants for the EnerGIS Framework.

This module centralizes all hard-coded values used throughout the framework
to improve maintainability and configurability.
"""

# ==========================================
# Heat Pump Constants
# ==========================================

# Minimum COP to avoid numerical issues (division by zero, etc.)
COP_MIN = 1.01

# Maximum reasonable COP for heat pumps (sanity check)
COP_MAX_HEATPUMP = 10.0

# Maximum COP for system builder interpolation
COP_MAX_SYSTEM_BUILDER = 12.0

# Default/fallback COP when calculation fails or data is missing
# Must be >= COP_MIN (1.01) to pass HeatPumpBlock validation
COP_DEFAULT = 2.0

# Default temperature difference for COP calculation (Kelvin)
COP_DELTA_T_K = 20.0


# ==========================================
# Storage Constants
# ==========================================

# Minimum efficiency floor to prevent division by zero and numerical instability
EFFICIENCY_FLOOR = 0.01

# Minimum and maximum valid efficiency range
EFFICIENCY_MIN = 0.01
EFFICIENCY_MAX = 1.0


# ==========================================
# Time Constants
# ==========================================

# Hours per year (standard)
HOURS_PER_YEAR = 8760

# Hours per leap year
HOURS_PER_LEAP_YEAR = 8784


# ==========================================
# Capacity Planning Constants
# ==========================================

# Safety factor for capacity vs demand validation
CAPACITY_SAFETY_FACTOR = 1.05

# Default lifetime for investments (years)
DEFAULT_LIFETIME_YEARS = 20.0


# ==========================================
# Numerical Stability Constants
# ==========================================

# Epsilon for floating point comparisons
FLOAT_EPSILON = 1e-9

# Tolerance for optimization solver
SOLVER_TOLERANCE = 1e-6


# ==========================================
# Grid / Economic Defaults
# ==========================================

# Big-M for grid import/export linearization (MW)
# Must be large enough to never bind, but not so large as to cause numerical issues
BIG_M_GRID_MW = 1e4

# Default CO₂ price when not specified in config (EUR/tCO₂)
DEFAULT_CO2_PRICE_EUR_PER_T = 100.0

# Default dump (curtailment) cost (EUR/MWh_th)
DEFAULT_DUMP_COST_EUR_PER_MWH_TH = 1.0


# ==========================================
# Component Sizing Defaults
# ==========================================

# Default heat pump thermal capacity when not optimizing (MW)
DEFAULT_HP_CAPACITY_MW = 50.0

# Default storage energy capacity when not optimizing (MWh)
DEFAULT_STORAGE_ENERGY_MWH = 500.0

# Default storage power capacity when not optimizing (MW)
DEFAULT_STORAGE_POWER_MW = 50.0

# Minimum fallback storage power as fraction of energy capacity (MW = MWh / ratio)
STORAGE_POWER_ENERGY_RATIO = 50.0

# Minimum fallback storage power floor (MW)
STORAGE_POWER_MIN_MW = 10.0


# ==========================================
# Rolling Horizon / MPC Defaults
# ==========================================

# Default rolling-horizon window length (hours)
DEFAULT_HORIZON_HOURS = 168.0
