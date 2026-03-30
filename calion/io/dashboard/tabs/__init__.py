"""
Dashboard Tab Components.

Each module in this package provides a function to create a specific tab
for the CALION Dashboard.
"""

from .overview import create_overview_tab
from .timeseries import create_timeseries_tab
from .duration_curve import create_duration_curve_tab
from .efficiency import create_efficiency_tab
from .energy_flows import create_sankey_tab
from .emissions import create_emissions_tab
from .costs import create_costs_tab
from .design import create_design_tab
from .comparison import create_comparison_tab
from .multi_network import create_multi_network_tab, has_multi_network_data
from .thermal_network import create_thermal_network_tab, has_thermal_network_data

__all__ = [
    'create_overview_tab',
    'create_timeseries_tab',
    'create_duration_curve_tab',
    'create_efficiency_tab',
    'create_sankey_tab',
    'create_emissions_tab',
    'create_costs_tab',
    'create_design_tab',
    'create_comparison_tab',
    'create_multi_network_tab',
    'has_multi_network_data',
    'create_thermal_network_tab',
    'has_thermal_network_data',
]
