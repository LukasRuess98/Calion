"""
Utility functions for the CALION Dashboard.

Contains color definitions, formatting helpers, and reusable utility functions.
"""

from __future__ import annotations

from typing import Dict, Optional

try:
    import panel as pn
    HAVE_PANEL = True
except ImportError:
    HAVE_PANEL = False
    pn = None


# =============================================================================
# Color Palettes
# =============================================================================

# Professional technical color palette (DIN-inspired, subdued, scientific)
KPI_COLORS: Dict[str, str] = {
    'primary': '#004191',    # Universitätsblau (Hauptfarbe)
    'secondary': '#6c757d',  # Neutralgrau (Sekundärinformation)
    'success': '#2E7D32',    # Dunkelgrün (Erfolg, positiv)
    'danger': '#C62828',     # Dunkelrot (Warnung, kritisch)
    'warning': '#F57C00',    # Orange (Aufmerksamkeit)
    'info': '#0277BD',       # Dunkelblau (Information)
    'light': '#E0E0E0'       # Hellgrau (neutral)
}

# Component-specific colors for plots
COMPONENT_COLORS: Dict[str, str] = {
    'HP1': '#1976D2',        # Technisches Blau (Wärmepumpe 1)
    'HP2': '#0288D1',        # Technisches Hellblau (Wärmepumpe 2)
    'HP3': '#0277BD',        # Technisches Mittelblau (Wärmepumpe 3)
    'HP4': '#01579B',        # Technisches Dunkelblau (Wärmepumpe 4)
    'HKW': '#D32F2F',        # Technisches Rot (Heizkraftwerk)
    'GTOST': '#C62828',      # Technisches Dunkelrot (GuD-Kraftwerk)
    'BMHKW': '#388E3C',      # Technisches Grün (Biomasse-Heizkraftwerk)
    'TES_discharge': '#757575',  # Technisches Grau (Speicherentladung)
}

# CO2 category colors
CO2_COLORS: Dict[str, str] = {
    'heat': '#dc3545',       # Danger (rot) - Wärmeerzeugung
    'elec_self': '#198754',  # Success (grün) - Strom-Eigenverbrauch
    'elec_grid': '#0dcaf0',  # Info (blau) - Strombezug
}

# Default color for unknown components
DEFAULT_COLOR = '#616161'  # Neutrales Technisches Grau


# =============================================================================
# Color Functions
# =============================================================================

def get_component_color(component: str) -> str:
    """
    Get color for component based on type using professional technical palette.

    Parameters
    ----------
    component : str
        Component name (e.g., 'HP1_Q_th_MW', 'HKW', etc.)

    Returns
    -------
    str
        Hex color code
    """
    for key, color in COMPONENT_COLORS.items():
        if key in component:
            return color
    return DEFAULT_COLOR


def get_kpi_color(card_type: str) -> str:
    """
    Get color for KPI card based on type.

    Parameters
    ----------
    card_type : str
        One of: primary, secondary, success, danger, warning, info, light

    Returns
    -------
    str
        Hex color code
    """
    return KPI_COLORS.get(card_type, KPI_COLORS['secondary'])


# =============================================================================
# KPI Card Creation
# =============================================================================

def create_kpi_card(title: str, value: str, card_type: str = 'primary') -> 'pn.pane.HTML':
    """
    Create a single KPI card with professional technical color scheme.

    Parameters
    ----------
    title : str
        Card title
    value : str
        Display value
    card_type : str
        Color type: primary, secondary, success, danger, warning, info, light

    Returns
    -------
    pn.pane.HTML
        Panel HTML pane with styled card
    """
    if not HAVE_PANEL:
        raise ImportError("Panel is required for KPI cards")

    color = get_kpi_color(card_type)

    card_content = pn.pane.HTML(
        f"""
        <div style="padding: 20px; background: linear-gradient(135deg, {color}20 0%, {color}10 100%);
                    border-left: 4px solid {color}; border-radius: 8px;">
            <div style="font-size: 14px; color: #666; margin-bottom: 8px;">{title}</div>
            <div style="font-size: 28px; font-weight: bold; color: {color};">{value}</div>
        </div>
        """,
        sizing_mode='stretch_width'
    )

    return card_content


# =============================================================================
# Formatting Helpers
# =============================================================================

def format_currency(value: float, currency: str = '€') -> str:
    """Format value as currency string."""
    return f"{value:,.0f} {currency}"


def format_energy(value: float, unit: str = 'MWh') -> str:
    """Format value as energy string."""
    return f"{value:,.0f} {unit}"


def format_power(value: float, unit: str = 'MW') -> str:
    """Format value as power string."""
    return f"{value:.1f} {unit}"


def format_percentage(value: float) -> str:
    """Format value as percentage string."""
    return f"{value:.1f} %"


def format_emissions(value: float, unit: str = 't') -> str:
    """Format value as emissions string."""
    return f"{value:,.1f} {unit}"


# =============================================================================
# Component Type Maps
# =============================================================================

COMPONENT_TYPE_MAP = {
    'chp': 'CHP',
    'thermal_generator': 'Kessel',
    'heat_pump': 'Wärmepumpe',
    'p2h': 'Power-to-Heat'
}

FUEL_TYPE_MAP = {
    'gas': 'Gas',
    'biomass': 'Biomasse',
    'waste': 'Abfall'
}


def translate_component_type(comp_type: str) -> str:
    """Translate component type to German display name."""
    return COMPONENT_TYPE_MAP.get(comp_type, comp_type)


def translate_fuel_type(fuel_type: str) -> str:
    """Translate fuel type to German display name."""
    return FUEL_TYPE_MAP.get(fuel_type, fuel_type)
