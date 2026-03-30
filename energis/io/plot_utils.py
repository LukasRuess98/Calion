"""Shared plotting utilities for EnerGIS.

This module provides common functions used across different plotting modules
to avoid code duplication.
"""

from typing import Sequence
from datetime import datetime

from energis.logging_config import get_logger

logger = get_logger(__name__)

try:
    import matplotlib.pyplot as plt
    from matplotlib.axes import Axes
    HAVE_MATPLOTLIB = True
except ImportError:  # pragma: no cover
    HAVE_MATPLOTLIB = False
    Axes = object  # type: ignore


__all__ = [
    "has_content",
    "prettify_label_de",
    "prettify_label_en",
    "configure_time_axis",
    "save_figure",
]


def has_content(
    values: Sequence[float],
    threshold: float = 1e-9
) -> bool:
    """Check if series has meaningful non-zero content.

    Parameters
    ----------
    values : sequence of float
        Numeric values to check
    threshold : float, default 1e-9
        Minimum absolute value to consider non-zero

    Returns
    -------
    bool
        True if at least one value exceeds threshold

    Examples
    --------
    >>> has_content([0.0, 0.0, 1.5])
    True
    >>> has_content([1e-10, 0.0, 1e-11])
    False
    """
    return any(abs(float(v)) > threshold for v in values)


def prettify_label_de(name: str) -> str:
    """Format technical variable name for German display.

    Parameters
    ----------
    name : str
        Technical variable name (e.g., 'P_buy_MW')

    Returns
    -------
    str
        German-readable label with units

    Examples
    --------
    >>> prettify_label_de('P_buy_MW')
    'Netzbezug [MW]'
    >>> prettify_label_de('TES_SOC_MWh')
    'TES Füllstand [MWh]'
    """
    suffix_map = {
        "_Q_th_MW": ("Thermische Leistung", " [MW]"),
        "_Pel_MW": ("Elektrische Leistung", " [MW]"),
        "_fuel_MW": ("Brennstoffleistung", " [MW]"),
        "_MW": ("", " [MW]"),
        "_MWh": ("", " [MWh]"),
        "_EUR": ("", " [EUR]"),
    }

    pretty = name
    unit = ""
    for suffix, (alias, unit_label) in suffix_map.items():
        if pretty.endswith(suffix):
            pretty = pretty[: -len(suffix)]
            unit = unit_label
            if alias:
                pretty = f"{pretty}_{alias}" if pretty else alias
            break

    pretty = pretty.replace("_", " ").strip()

    lower = pretty.lower()
    special_map = {
        "p buy": "Netzbezug",
        "p sell": "Netzeinspeisung",
        "tes": "TES",
    }
    if lower in special_map:
        pretty = special_map[lower]

    replacements = {
        "charge": "Beladung",
        "discharge": "Entladung",
        "storage": "Speicher",
        "thermische": "Thermische",
        "elektrische": "Elektrische",
        "brennstoffleistung": "Brennstoffleistung",
        "soc": "Füllstand",
    }
    words = pretty.split()
    normalized_words: list[str] = []
    for word in words:
        repl = replacements.get(word.lower())
        if repl:
            normalized_words.append(repl)
        elif word.isupper() or any(char.isdigit() for char in word):
            normalized_words.append(word)
        else:
            normalized_words.append(word.capitalize())
    pretty = " ".join(normalized_words)

    return f"{pretty}{unit}".strip()


def prettify_label_en(name: str) -> str:
    """Format technical variable name for English display.

    Parameters
    ----------
    name : str
        Technical variable name (e.g., 'P_buy_MW')

    Returns
    -------
    str
        English-readable label

    Examples
    --------
    >>> prettify_label_en('P_buy_MW')
    'Grid Import'
    >>> prettify_label_en('HP1_Q_th_MW')
    'Heat Pump 1 Heat'
    """
    label = name

    suffix_map = {
        "_Q_th_MW": " Heat",
        "_Pel_MW": " Power",
        "_fuel_MW": " Fuel",
        "_MW": "",
        "_MWh": "",
        "_EUR": "",
        "_t": "",
        "_SOC_MWh": " SOC",
        "_charge_MW": " Charge",
        "_discharge_MW": " Discharge",
    }

    for suffix, replacement in suffix_map.items():
        if label.endswith(suffix):
            label = label[:-len(suffix)] + replacement
            break

    # Replace component names
    replacements = {
        "HP1": "Heat Pump 1",
        "HP2": "Heat Pump 2",
        "HP3": "Heat Pump 3",
        "HP4": "Heat Pump 4",
        "HKW": "Gas Boiler",
        "GTOST": "Peak Boiler",
        "P2H": "Power-to-Heat",
        "BMHKW": "Biomass CHP",
        "HWS": "Summer Waste Heat",
        "HWW": "Winter Waste Heat",
        "AVA": "Waste Incineration",
        "TES": "Thermal Storage",
        "P_buy": "Grid Import",
        "P_sell": "Grid Export",
        "waermebedarf": "Heat Demand",
    }

    for old, new in replacements.items():
        label = label.replace(old, new)

    return label.strip()


def configure_time_axis(
    ax: "Axes",
    timestamps: Sequence[datetime] | Sequence[int]
) -> None:
    """Configure time axis formatting for plots.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axes to configure
    timestamps : sequence of datetime or int
        Time series data (datetime objects or integer indices)

    Notes
    -----
    - For datetime: formats as dates with rotation
    - For integers: uses linear scale
    """
    if not HAVE_MATPLOTLIB:
        return

    if timestamps and isinstance(timestamps[0], datetime):
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')
            label.set_rotation_mode('anchor')


def save_figure(
    fig: "plt.Figure",
    outdir: str,
    basename: str,
    dpi: int = 300,
    formats: Sequence[str] = ("png", "pdf")
) -> list[str]:
    """Save matplotlib figure in multiple formats.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        Figure to save
    outdir : str
        Output directory
    basename : str
        Base filename (without extension)
    dpi : int, default 300
        Resolution for raster formats
    formats : sequence of str, default ("png", "pdf")
        File formats to save

    Returns
    -------
    list of str
        Paths to saved files

    Examples
    --------
    >>> fig, ax = plt.subplots()
    >>> paths = save_figure(fig, "outputs", "plot", dpi=150, formats=["png"])
    >>> print(paths)
    ['outputs/plot.png']
    """
    if not HAVE_MATPLOTLIB:
        return []

    import os

    paths = []
    for fmt in formats:
        path = os.path.join(outdir, f"{basename}.{fmt}")
        fig.savefig(path, dpi=dpi, bbox_inches='tight', format=fmt)
        paths.append(path)

    return paths
