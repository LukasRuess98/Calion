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
COP_DEFAULT = 1.0

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
