"""
Network Loader for Thermal Networks from Excel

Loads thermal network topology from Excel sheets:
- Sheet "Network_Nodes": Node definitions (plants, consumers, junctions)
- Sheet "Network_Pipes": Pipe connections and parameters
- Sheet "Network_Parameters": Global network parameters

Author: CALION Development Team
Date: 2025-12-11
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from calion.io._utils import _is_empty
from calion.logging_config import get_logger
from calion.utils.xlsx import list_sheet_names, read_xlsx

logger = get_logger(__name__)


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float with default."""
    if _is_empty(value):
        return default
    try:
        if isinstance(value, str):
            return float(value.replace(",", "."))
        return float(value)
    except (ValueError, TypeError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    """Convert value to boolean."""
    if _is_empty(value):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).lower().strip()
    return text in ("true", "1", "yes", "ja", "x")


def _normalize_column(name: str) -> str:
    """Normalize column name for matching."""
    return name.lower().strip().replace(" ", "_").replace("-", "_")


def _find_column(header: list[str], candidates: list[str]) -> int | None:
    """Find column index matching any candidate."""
    norm_header = {_normalize_column(h): i for i, h in enumerate(header)}
    for cand in candidates:
        norm_cand = _normalize_column(cand)
        if norm_cand in norm_header:
            return norm_header[norm_cand]
        # Partial match
        for norm_h, idx in norm_header.items():
            if norm_cand in norm_h or norm_h in norm_cand:
                return idx
    return None


def load_network_from_excel(
    path: str,
    nodes_sheet: str = "Network_Nodes",
    pipes_sheet: str = "Network_Pipes",
    params_sheet: str = "Network_Parameters"
) -> dict[str, Any] | None:
    """
    Load thermal network configuration from Excel file.

    Args:
        path: Path to Excel file
        nodes_sheet: Sheet name for node definitions
        pipes_sheet: Sheet name for pipe definitions
        params_sheet: Sheet name for global parameters

    Returns:
        Network configuration dict compatible with NetworkManager,
        or None if no network sheets found
    """
    excel_path = Path(path)
    if not excel_path.exists():
        logger.warning(f"Excel file not found: {path}")
        return None

    # Check available sheets
    try:
        available_sheets = list_sheet_names(str(excel_path))
    except Exception as e:
        logger.error(f"Error reading Excel sheets: {e}")
        return None

    logger.info(f"Available sheets in {excel_path.name}: {available_sheets}")

    # Check if network sheets exist
    has_nodes = nodes_sheet in available_sheets
    has_pipes = pipes_sheet in available_sheets
    has_params = params_sheet in available_sheets

    if not (has_nodes or has_pipes):
        logger.info("No network sheets found in Excel, skipping network loading")
        return None

    network_config = {
        "enabled": True,
        "parameters": {},
        "production_plants": [],
        "pump_stations": [],
        "consumer_zones": [],
        "pipes": [],
    }

    # Load parameters
    if has_params:
        network_config["parameters"] = _load_parameters(str(excel_path), params_sheet)
    else:
        # Default parameters
        network_config["parameters"] = {
            "supply_temp_nominal_c": 90.0,
            "return_temp_nominal_c": 50.0,
            "ground_temp_default_c": 10.0,
            "design_pressure_bar": 16.0,
            "max_pressure_bar": 25.0,
            "max_velocity_m_s": 2.5,
        }

    # Load nodes
    if has_nodes:
        plants, pumps, consumers = _load_nodes(str(excel_path), nodes_sheet)
        network_config["production_plants"] = plants
        network_config["pump_stations"] = pumps
        network_config["consumer_zones"] = consumers

    # Load pipes
    if has_pipes:
        network_config["pipes"] = _load_pipes(str(excel_path), pipes_sheet)

    logger.info(
        f"Loaded network from Excel: "
        f"{len(network_config['production_plants'])} plants, "
        f"{len(network_config['pump_stations'])} pumps, "
        f"{len(network_config['consumer_zones'])} consumers, "
        f"{len(network_config['pipes'])} pipes"
    )

    return network_config


def _load_parameters(path: str, sheet_name: str) -> dict[str, Any]:
    """Load network parameters from Excel sheet."""
    header, rows = read_xlsx(path, sheet_name)
    if not header or not rows:
        return {}

    params = {}

    # Find columns
    param_col = _find_column(header, ["parameter", "param", "name", "bezeichnung"])
    value_col = _find_column(header, ["value", "wert", "val"])

    if param_col is None or value_col is None:
        logger.warning(f"Could not find parameter/value columns in {sheet_name}")
        return params

    for row in rows:
        if len(row) <= max(param_col, value_col):
            continue
        param_name = str(row[param_col]).strip()
        if _is_empty(param_name):
            continue

        value = row[value_col]
        # Try to convert to appropriate type
        if isinstance(value, (int, float)):
            params[param_name] = value
        elif isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ("true", "false"):
                params[param_name] = value_lower == "true"
            else:
                try:
                    params[param_name] = float(value.replace(",", "."))
                except ValueError:
                    params[param_name] = value
        else:
            params[param_name] = value

    return params


def _load_nodes(path: str, sheet_name: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Load node definitions from Excel sheet."""
    header, rows = read_xlsx(path, sheet_name)
    if not header or not rows:
        return [], [], []

    plants = []
    pumps = []
    consumers = []

    # Find required columns
    id_col = _find_column(header, ["node_id", "id", "knoten_id"])
    name_col = _find_column(header, ["name", "bezeichnung"])
    type_col = _find_column(header, ["type", "typ", "node_type", "knotentyp"])
    elev_col = _find_column(header, ["elevation_m", "elevation_nn_m", "hoehe_m", "nn_m"])
    x_col = _find_column(header, ["x", "coord_x", "x_coord"])
    y_col = _find_column(header, ["y", "coord_y", "y_coord"])
    supply_t_col = _find_column(header, ["supply_temp_c", "vorlauf_c", "t_supply"])
    supply_p_col = _find_column(header, ["supply_pressure_bar", "druck_bar", "p_supply"])
    demand_frac_col = _find_column(header, ["demand_fraction", "anteil_bedarf", "demand_share"])
    max_power_col = _find_column(header, ["max_power_mw", "max_leistung_mw", "p_max_mw"])

    if id_col is None:
        logger.warning(f"Could not find node_id column in {sheet_name}")
        return [], [], []

    for row in rows:
        if len(row) <= id_col:
            continue

        node_id = str(row[id_col]).strip()
        if _is_empty(node_id):
            continue

        node_type = str(row[type_col]).lower().strip() if type_col is not None and len(row) > type_col else "junction"

        node_config = {
            "node_id": node_id,
            "name": str(row[name_col]).strip() if name_col is not None and len(row) > name_col else node_id,
            "type": node_type,
        }

        # Optional fields
        if elev_col is not None and len(row) > elev_col:
            node_config["elevation_nn_m"] = _to_float(row[elev_col], 0.0)

        if x_col is not None and y_col is not None and len(row) > max(x_col, y_col):
            node_config["coordinates"] = {
                "x": _to_float(row[x_col], 0.0),
                "y": _to_float(row[y_col], 0.0),
            }

        if supply_t_col is not None and len(row) > supply_t_col:
            node_config["supply_temp_c"] = _to_float(row[supply_t_col], 90.0)

        if supply_p_col is not None and len(row) > supply_p_col:
            node_config["supply_pressure_bar"] = _to_float(row[supply_p_col], 6.0)

        if demand_frac_col is not None and len(row) > demand_frac_col:
            node_config["demand_fraction"] = _to_float(row[demand_frac_col], 0.0)

        if max_power_col is not None and len(row) > max_power_col:
            node_config["max_power_mw"] = _to_float(row[max_power_col], 0.0)

        # Categorize by type
        if node_type in ("plant", "erzeugung", "producer"):
            plants.append(node_config)
        elif node_type in ("pump", "pump_station", "pumpe", "pumpstation"):
            pumps.append(node_config)
        elif node_type in ("consumer", "verbraucher", "demand", "bedarf"):
            consumers.append(node_config)
        else:
            # Default to junction/pump station
            pumps.append(node_config)

    return plants, pumps, consumers


def _load_pipes(path: str, sheet_name: str) -> list[dict]:
    """Load pipe definitions from Excel sheet."""
    header, rows = read_xlsx(path, sheet_name)
    if not header or not rows:
        return []

    pipes = []

    # Find required columns
    id_col = _find_column(header, ["pipe_id", "id", "rohr_id"])
    from_col = _find_column(header, ["from_node", "von", "from", "start_node"])
    to_col = _find_column(header, ["to_node", "nach", "to", "end_node"])
    length_col = _find_column(header, ["length_m", "laenge_m", "length"])
    diam_col = _find_column(header, ["diameter_mm", "durchmesser_mm", "dn", "diameter"])
    u_supply_col = _find_column(header, ["u_value_supply", "u_vorlauf", "u_supply"])
    u_return_col = _find_column(header, ["u_value_return", "u_ruecklauf", "u_return"])
    existing_col = _find_column(header, ["existing", "bestehend", "vorhanden"])
    upgrade_col = _find_column(header, ["upgrade_enabled", "erweiterbar", "upgradeable"])
    max_flow_col = _find_column(header, ["max_flow_kg_s", "max_flow", "max_massenstrom"])
    max_pressure_col = _find_column(header, ["max_pressure_bar", "max_druck", "pn"])

    if id_col is None or from_col is None or to_col is None:
        logger.warning(f"Could not find required pipe columns (id, from, to) in {sheet_name}")
        return []

    for row in rows:
        if len(row) <= max(id_col, from_col, to_col):
            continue

        pipe_id = str(row[id_col]).strip()
        if _is_empty(pipe_id):
            continue

        pipe_config = {
            "id": pipe_id,
            "from_node": str(row[from_col]).strip(),
            "to_node": str(row[to_col]).strip(),
            "length_m": _to_float(row[length_col], 100.0) if length_col is not None and len(row) > length_col else 100.0,
        }

        # Diameter
        if diam_col is not None and len(row) > diam_col:
            diam = _to_float(row[diam_col], 200.0)
            pipe_config["current_diameter_supply_mm"] = diam
            pipe_config["current_diameter_return_mm"] = diam

        # U-values (insulation)
        if u_supply_col is not None and len(row) > u_supply_col:
            pipe_config["u_value_supply_w_per_m_k"] = _to_float(row[u_supply_col], 0.28)
        if u_return_col is not None and len(row) > u_return_col:
            pipe_config["u_value_return_w_per_m_k"] = _to_float(row[u_return_col], 0.30)

        # Existing/upgrade flags
        if existing_col is not None and len(row) > existing_col:
            pipe_config["existing"] = _to_bool(row[existing_col], True)
        else:
            pipe_config["existing"] = True  # Default: existing brownfield pipe

        if upgrade_col is not None and len(row) > upgrade_col:
            upgrade_enabled = _to_bool(row[upgrade_col], False)
            pipe_config["upgrade_options"] = {"enabled": upgrade_enabled}
        else:
            pipe_config["upgrade_options"] = {"enabled": False}  # Default: no upgrade

        # Flow and pressure limits
        if max_flow_col is not None and len(row) > max_flow_col:
            max_flow = _to_float(row[max_flow_col], 0.0)
            if max_flow > 0:
                pipe_config["max_flow_kg_s"] = max_flow

        if max_pressure_col is not None and len(row) > max_pressure_col:
            max_pressure = _to_float(row[max_pressure_col], 0.0)
            if max_pressure > 0:
                pipe_config["max_pressure_bar"] = max_pressure

        pipes.append(pipe_config)

    return pipes


def create_network_excel_template(output_path: str) -> None:
    """
    Create an Excel template for network definition.

    This creates a template with example data showing
    the expected format for network definition sheets.
    """

    # This is a simplified version - for a real template,
    # you'd want to create a proper multi-sheet Excel file
    logger.info(f"Creating network Excel template at: {output_path}")

    # For now, just log the expected format
    logger.info(
        "Network Excel Format:\n\n"
        "Sheet: Network_Parameters\n"
        "| Parameter                | Value |\n"
        "|--------------------------|-------|\n"
        "| supply_temp_nominal_c    | 90    |\n"
        "| return_temp_nominal_c    | 50    |\n"
        "| ground_temp_default_c    | 10    |\n"
        "| design_pressure_bar      | 16    |\n"
        "| max_pressure_bar         | 25    |\n"
        "| max_velocity_m_s         | 2.5   |\n\n"
        "Sheet: Network_Nodes\n"
        "| node_id     | name        | type     | elevation_m | supply_temp_c | demand_fraction |\n"
        "|-------------|-------------|----------|-------------|---------------|-----------------|\n"
        "| plant_main  | Main Plant  | plant    | 470         | 100           |                 |\n"
        "| zone_nord   | Zone North  | consumer | 465         |               | 0.4             |\n"
        "| zone_sued   | Zone South  | consumer | 480         |               | 0.6             |\n\n"
        "Sheet: Network_Pipes\n"
        "| pipe_id    | from_node   | to_node   | length_m | diameter_mm | existing |"
        " max_flow_kg_s | max_pressure_bar |\n"
        "|------------|-------------|-----------|----------|-------------|----------|"
        "---------------|------------------|\n"
        "| main_nord  | plant_main  | zone_nord | 1500     | 300         | TRUE     | 200           | 16               |\n"
        "| main_sued  | plant_main  | zone_sued | 2000     | 350         | TRUE     | 250           | 25               |"
    )
