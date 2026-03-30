"""
Dashboard Tab Components.

Each module in this package provides a function to create a specific tab
for the CALION Dashboard.
"""

from .comparison import create_comparison_tab
from .costs import create_costs_tab
from .design import create_design_tab
from .duration_curve import create_duration_curve_tab
from .efficiency import create_efficiency_tab
from .emissions import create_emissions_tab
from .energy_flows import create_sankey_tab
from .multi_network import create_multi_network_tab, has_multi_network_data
from .overview import create_overview_tab
from .thermal_network import create_thermal_network_tab, has_thermal_network_data
from .timeseries import create_timeseries_tab

__all__ = [
    'create_comparison_tab',
    'create_costs_tab',
    'create_design_tab',
    'create_duration_curve_tab',
    'create_efficiency_tab',
    'create_emissions_tab',
    'create_multi_network_tab',
    'create_overview_tab',
    'create_sankey_tab',
    'create_thermal_network_tab',
    'create_timeseries_tab',
    'has_multi_network_data',
    'has_thermal_network_data',
]
