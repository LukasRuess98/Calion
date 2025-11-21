"""Excel-to-YAML converter for thermal network scenarios.

This module provides functionality to convert a structured Excel file with
multiple sheets into YAML configuration files for thermal network simulation.

The Excel file should contain the following sheets:
- Netzwerk: Network-level parameters
- Erzeuger: Heat producers (boilers, heat pumps, CHP, etc.)
- Speicher: Thermal storage units
- Rohre: Pipe definitions (only supply pipes, return pipes auto-generated)
- Verbraucher: Heat consumers
- Zeitreihen: All timeseries data (8760 rows)

Usage in Jupyter notebook:
    from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

    parser = ThermalNetworkExcelParser("data/my_network.xlsx")
    errors = parser.validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
    else:
        parser.save_yaml("configs/scenarios/my_network.scenario.yaml")
        print("Successfully created YAML configuration")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml
from datetime import datetime

from energis.utils.xlsx import read_xlsx


@dataclass
class NetworkConfig:
    """Network-level configuration."""
    name: str
    T_supply_nom: float  # Nominal supply temperature [°C]
    T_return_nom: float  # Nominal return temperature [°C]
    p_nominal: float  # Nominal pressure [bar]
    network_type: str = "district_heating"  # district_heating | building_network
    optimization_mode: str = "cost"  # cost | emissions | exergy

    # Optional parameters
    ground_temperature: float = 10.0  # [°C]
    soil_thermal_conductivity: float = 1.5  # [W/m/K]
    ambient_temperature_profile: Optional[str] = None


@dataclass
class ProducerConfig:
    """Heat producer configuration."""
    id: str
    type: str  # boiler | heat_pump | chp | solar_thermal | geothermal

    # Brownfield/Greenfield flags
    existing: bool = False
    invest: bool = False

    # Capacity
    Q_nom: Optional[float] = None  # Nominal heat output [MW]
    Q_options: Optional[List[float]] = None  # Investment options [MW]

    # Economic parameters
    capex_specific: Optional[float] = None  # [€/kW]
    opex_fix: Optional[float] = None  # [€/kW/a]
    opex_var: Optional[float] = None  # [€/MWh]
    lifetime: int = 20  # [years]

    # Technical parameters (type-specific)
    efficiency: Optional[float] = None  # [0-1]
    COP_nominal: Optional[float] = None  # For heat pumps
    electrical_efficiency: Optional[float] = None  # For CHP
    fuel_type: Optional[str] = None  # gas | oil | biomass | electricity

    # Connection
    supply_node: Optional[str] = None
    return_node: Optional[str] = None


@dataclass
class StorageConfig:
    """Thermal storage configuration."""
    id: str
    type: str = "hot_water_tank"  # hot_water_tank | ptes | ates

    # Brownfield/Greenfield flags
    existing: bool = False
    invest: bool = False

    # Capacity
    capacity_MWh: Optional[float] = None  # [MWh]
    capacity_options: Optional[List[float]] = None  # [MWh]

    # Technical parameters
    T_max: float = 95.0  # [°C]
    T_min: float = 40.0  # [°C]
    loss_rate: float = 0.001  # [1/h]
    charge_rate_MW: Optional[float] = None  # [MW]
    discharge_rate_MW: Optional[float] = None  # [MW]

    # Economic parameters
    capex_specific: Optional[float] = None  # [€/kWh]
    opex_fix: Optional[float] = None  # [€/kWh/a]
    lifetime: int = 30

    # Connection
    supply_node: Optional[str] = None
    return_node: Optional[str] = None


@dataclass
class PipeConfig:
    """Pipe configuration (supply pipe, return pipe auto-generated)."""
    id: str
    from_node: str
    to_node: str
    length_m: float

    # Brownfield/Greenfield flags
    existing: bool = False
    invest: bool = False

    # For existing pipes (Brownfield)
    DN_fixed: Optional[str] = None  # e.g., "DN150"
    insulation_fixed: Optional[str] = None  # e.g., "standard" | "enhanced"
    installation_year: Optional[int] = None
    condition: str = "good"  # good | fair | poor

    # For investment pipes (Greenfield)
    DN_options: Optional[List[str]] = None  # e.g., ["DN100", "DN150", "DN200"]
    insulation_options: Optional[List[str]] = None

    # Economic parameters
    capex_per_m: Optional[float] = None  # [€/m]
    lifetime: int = 40


@dataclass
class ConsumerConfig:
    """Heat consumer configuration."""
    id: str
    demand_profile: str  # Reference to timeseries

    # Location
    node: str

    # Optional parameters
    peak_demand_MW: Optional[float] = None
    annual_demand_MWh: Optional[float] = None

    # Substation parameters
    T_supply_required: Optional[float] = None  # [°C]
    T_return_design: Optional[float] = None  # [°C]
    pressure_loss_bar: float = 0.5  # [bar]


class ThermalNetworkExcelParser:
    """Parse Excel file with thermal network data into YAML configuration."""

    def __init__(self, excel_path: str | Path):
        """Initialize parser with Excel file path.

        Args:
            excel_path: Path to Excel file with thermal network data
        """
        self.excel_path = Path(excel_path)
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        self.sheets: Dict[str, Tuple[List[str], List[List[Any]]]] = {}
        self.config: Dict[str, Any] = {}
        self.nodes: Set[str] = set()
        self.timeseries_data: Dict[str, List[float]] = {}

        self._load_excel()
        self._parse_to_config()

    def _load_excel(self) -> None:
        """Load all sheets from Excel file."""
        sheet_names = ["Netzwerk", "Erzeuger", "Speicher", "Rohre", "Verbraucher", "Zeitreihen"]

        for sheet_name in sheet_names:
            try:
                # Note: read_xlsx with sheet_name expects "sheet1", "sheet2", etc.
                # We need to read by sheet index or modify approach
                # For now, we'll try to read and catch errors
                header, rows = read_xlsx(str(self.excel_path), sheet_name=sheet_name.lower())
                self.sheets[sheet_name] = (header, rows)
            except Exception as e:
                # Sheet might not exist or have different name
                self.sheets[sheet_name] = ([], [])
                print(f"Warning: Could not read sheet '{sheet_name}': {e}")

    def _parse_to_config(self) -> None:
        """Parse Excel sheets into configuration dictionary."""
        self.config = {
            "thermal_network": {},
            "nodes": {},
            "pipes": [],
            "producers": [],
            "storage": [],
            "consumers": [],
            "timeseries": {},
            "simulation": {}
        }

        self._parse_network()
        self._parse_producers()
        self._parse_storage()
        self._parse_pipes()
        self._parse_consumers()
        self._parse_timeseries()
        self._extract_nodes()
        self._generate_return_pipes()
        self._add_simulation_defaults()

    def _parse_network(self) -> None:
        """Parse Netzwerk sheet."""
        header, rows = self.sheets.get("Netzwerk", ([], []))
        if not rows:
            # Use defaults
            self.config["thermal_network"] = {
                "name": self.excel_path.stem,
                "T_supply_nom": 90.0,
                "T_return_nom": 50.0,
                "p_nominal": 6.0,
                "network_type": "district_heating",
                "optimization_mode": "cost"
            }
            return

        # Convert to dict (assuming key-value pairs in columns)
        params = {}
        for row in rows:
            if len(row) >= 2 and row[0] and row[1]:
                params[str(row[0]).strip()] = row[1]

        self.config["thermal_network"] = {
            "name": params.get("Name", self.excel_path.stem),
            "T_supply_nom": float(params.get("T_Vorlauf_nom", 90.0)),
            "T_return_nom": float(params.get("T_Ruecklauf_nom", 50.0)),
            "p_nominal": float(params.get("p_nominal", 6.0)),
            "network_type": params.get("Netztyp", "district_heating"),
            "optimization_mode": params.get("Optimierungsmodus", "cost")
        }

    def _parse_producers(self) -> None:
        """Parse Erzeuger sheet."""
        header, rows = self.sheets.get("Erzeuger", ([], []))
        if not rows:
            return

        # Create column mapping
        col_map = {h: i for i, h in enumerate(header)}

        for row in rows:
            if not row or not row[0]:  # Skip empty rows
                continue

            producer = {
                "id": str(row[col_map.get("ID", 0)]),
                "type": str(row[col_map.get("Typ", 1)]).lower(),
                "existing": self._parse_bool(row[col_map.get("Bestand?", 2)]),
                "invest": self._parse_bool(row[col_map.get("Investition?", 3)]),
            }

            # Capacity
            if "Q_nom_MW" in col_map and row[col_map["Q_nom_MW"]]:
                producer["Q_nom"] = float(row[col_map["Q_nom_MW"]])
            if "Q_options_MW" in col_map and row[col_map["Q_options_MW"]]:
                producer["Q_options"] = self._parse_list(row[col_map["Q_options_MW"]])

            # Economic parameters
            if "CAPEX_€_kW" in col_map and row[col_map["CAPEX_€_kW"]]:
                producer["capex_specific"] = float(row[col_map["CAPEX_€_kW"]])
            if "OPEX_fix_€_kW_a" in col_map and row[col_map["OPEX_fix_€_kW_a"]]:
                producer["opex_fix"] = float(row[col_map["OPEX_fix_€_kW_a"]])
            if "OPEX_var_€_MWh" in col_map and row[col_map["OPEX_var_€_MWh"]]:
                producer["opex_var"] = float(row[col_map["OPEX_var_€_MWh"]])

            # Technical parameters
            if "Wirkungsgrad" in col_map and row[col_map["Wirkungsgrad"]]:
                producer["efficiency"] = float(row[col_map["Wirkungsgrad"]])
            if "COP" in col_map and row[col_map["COP"]]:
                producer["COP_nominal"] = float(row[col_map["COP"]])
            if "Brennstoff" in col_map and row[col_map["Brennstoff"]]:
                producer["fuel_type"] = str(row[col_map["Brennstoff"]])

            # Connection
            if "Vorlauf_Knoten" in col_map and row[col_map["Vorlauf_Knoten"]]:
                producer["supply_node"] = str(row[col_map["Vorlauf_Knoten"]])
            if "Ruecklauf_Knoten" in col_map and row[col_map["Ruecklauf_Knoten"]]:
                producer["return_node"] = str(row[col_map["Ruecklauf_Knoten"]])

            self.config["producers"].append(producer)

    def _parse_storage(self) -> None:
        """Parse Speicher sheet."""
        header, rows = self.sheets.get("Speicher", ([], []))
        if not rows:
            return

        col_map = {h: i for i, h in enumerate(header)}

        for row in rows:
            if not row or not row[0]:
                continue

            storage = {
                "id": str(row[col_map.get("ID", 0)]),
                "type": str(row[col_map.get("Typ", 1)]).lower() if col_map.get("Typ") else "hot_water_tank",
                "existing": self._parse_bool(row[col_map.get("Bestand?", 2)]),
                "invest": self._parse_bool(row[col_map.get("Investition?", 3)]),
            }

            # Capacity
            if "Kapazitaet_MWh" in col_map and row[col_map["Kapazitaet_MWh"]]:
                storage["capacity_MWh"] = float(row[col_map["Kapazitaet_MWh"]])
            if "Kapazitaet_options_MWh" in col_map and row[col_map["Kapazitaet_options_MWh"]]:
                storage["capacity_options"] = self._parse_list(row[col_map["Kapazitaet_options_MWh"]])

            # Technical parameters
            if "T_max_C" in col_map and row[col_map["T_max_C"]]:
                storage["T_max"] = float(row[col_map["T_max_C"]])
            if "T_min_C" in col_map and row[col_map["T_min_C"]]:
                storage["T_min"] = float(row[col_map["T_min_C"]])
            if "Verlustrate_1_h" in col_map and row[col_map["Verlustrate_1_h"]]:
                storage["loss_rate"] = float(row[col_map["Verlustrate_1_h"]])

            # Economic parameters
            if "CAPEX_€_kWh" in col_map and row[col_map["CAPEX_€_kWh"]]:
                storage["capex_specific"] = float(row[col_map["CAPEX_€_kWh"]])

            # Connection
            if "Vorlauf_Knoten" in col_map and row[col_map["Vorlauf_Knoten"]]:
                storage["supply_node"] = str(row[col_map["Vorlauf_Knoten"]])
            if "Ruecklauf_Knoten" in col_map and row[col_map["Ruecklauf_Knoten"]]:
                storage["return_node"] = str(row[col_map["Ruecklauf_Knoten"]])

            self.config["storage"].append(storage)

    def _parse_pipes(self) -> None:
        """Parse Rohre sheet (only supply pipes, return pipes generated automatically)."""
        header, rows = self.sheets.get("Rohre", ([], []))
        if not rows:
            return

        col_map = {h: i for i, h in enumerate(header)}

        for row in rows:
            if not row or not row[0]:
                continue

            pipe = {
                "id": str(row[col_map.get("ID", 0)]),
                "from_node": str(row[col_map.get("Von_Knoten", 1)]),
                "to_node": str(row[col_map.get("Zu_Knoten", 2)]),
                "length_m": float(row[col_map.get("Laenge_m", 3)]),
                "existing": self._parse_bool(row[col_map.get("Bestand?", 4)]),
                "invest": self._parse_bool(row[col_map.get("Investition?", 5)]),
            }

            # Existing pipe parameters
            if "DN_fix" in col_map and row[col_map["DN_fix"]]:
                pipe["DN_fixed"] = str(row[col_map["DN_fix"]])
            if "Daemmung_fix" in col_map and row[col_map["Daemmung_fix"]]:
                pipe["insulation_fixed"] = str(row[col_map["Daemmung_fix"]])
            if "Baujahr" in col_map and row[col_map["Baujahr"]]:
                pipe["installation_year"] = int(row[col_map["Baujahr"]])
            if "Zustand" in col_map and row[col_map["Zustand"]]:
                pipe["condition"] = str(row[col_map["Zustand"]])

            # Investment options
            if "DN_options" in col_map and row[col_map["DN_options"]]:
                pipe["DN_options"] = self._parse_list(row[col_map["DN_options"]])
            if "Daemmung_options" in col_map and row[col_map["Daemmung_options"]]:
                pipe["insulation_options"] = self._parse_list(row[col_map["Daemmung_options"]])

            # Economic parameters
            if "CAPEX_€_m" in col_map and row[col_map["CAPEX_€_m"]]:
                pipe["capex_per_m"] = float(row[col_map["CAPEX_€_m"]])

            self.config["pipes"].append(pipe)

    def _parse_consumers(self) -> None:
        """Parse Verbraucher sheet."""
        header, rows = self.sheets.get("Verbraucher", ([], []))
        if not rows:
            return

        col_map = {h: i for i, h in enumerate(header)}

        for row in rows:
            if not row or not row[0]:
                continue

            consumer = {
                "id": str(row[col_map.get("ID", 0)]),
                "node": str(row[col_map.get("Knoten", 1)]),
                "demand_profile": str(row[col_map.get("Lastgang", 2)]),
            }

            # Optional parameters
            if "Spitzenlast_MW" in col_map and row[col_map["Spitzenlast_MW"]]:
                consumer["peak_demand_MW"] = float(row[col_map["Spitzenlast_MW"]])
            if "Jahresbedarf_MWh" in col_map and row[col_map["Jahresbedarf_MWh"]]:
                consumer["annual_demand_MWh"] = float(row[col_map["Jahresbedarf_MWh"]])
            if "T_Vorlauf_min_C" in col_map and row[col_map["T_Vorlauf_min_C"]]:
                consumer["T_supply_required"] = float(row[col_map["T_Vorlauf_min_C"]])
            if "T_Ruecklauf_C" in col_map and row[col_map["T_Ruecklauf_C"]]:
                consumer["T_return_design"] = float(row[col_map["T_Ruecklauf_C"]])

            self.config["consumers"].append(consumer)

    def _parse_timeseries(self) -> None:
        """Parse Zeitreihen sheet."""
        header, rows = self.sheets.get("Zeitreihen", ([], []))
        if not rows:
            return

        # Each column (except first which might be timestamp) is a timeseries
        for col_idx, col_name in enumerate(header):
            if col_idx == 0 and "time" in str(col_name).lower():
                continue  # Skip timestamp column

            values = []
            for row in rows:
                if col_idx < len(row):
                    try:
                        values.append(float(row[col_idx]))
                    except (ValueError, TypeError):
                        values.append(0.0)
                else:
                    values.append(0.0)

            self.timeseries_data[str(col_name)] = values
            self.config["timeseries"][str(col_name)] = {
                "source": "excel",
                "length": len(values)
            }

    def _extract_nodes(self) -> None:
        """Extract unique nodes from pipes and components."""
        # From pipes
        for pipe in self.config["pipes"]:
            self.nodes.add(pipe["from_node"])
            self.nodes.add(pipe["to_node"])

        # From producers
        for producer in self.config["producers"]:
            if producer.get("supply_node"):
                self.nodes.add(producer["supply_node"])
            if producer.get("return_node"):
                self.nodes.add(producer["return_node"])

        # From storage
        for storage in self.config["storage"]:
            if storage.get("supply_node"):
                self.nodes.add(storage["supply_node"])
            if storage.get("return_node"):
                self.nodes.add(storage["return_node"])

        # From consumers
        for consumer in self.config["consumers"]:
            self.nodes.add(consumer["node"])

        # Add to config
        for node in sorted(self.nodes):
            self.config["nodes"][node] = {
                "id": node,
                "type": "junction"  # Can be refined later
            }

    def _generate_return_pipes(self) -> None:
        """Auto-generate return pipes from supply pipes."""
        return_pipes = []

        for pipe in self.config["pipes"]:
            return_pipe = pipe.copy()
            return_pipe["id"] = pipe["id"] + "_return"
            return_pipe["from_node"] = pipe["to_node"]  # Swapped
            return_pipe["to_node"] = pipe["from_node"]  # Swapped
            return_pipes.append(return_pipe)

        # Add return pipes to config
        self.config["pipes"].extend(return_pipes)

    def _add_simulation_defaults(self) -> None:
        """Add default simulation parameters."""
        self.config["simulation"] = {
            "timesteps": len(next(iter(self.timeseries_data.values()))) if self.timeseries_data else 8760,
            "dt_hours": 1.0,
            "solver": "gurobi",
            "solver_options": {
                "MIPGap": 0.01,
                "TimeLimit": 3600
            }
        }

    def _parse_bool(self, value: Any) -> bool:
        """Parse boolean value from Excel."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("ja", "yes", "true", "1", "x")
        if isinstance(value, (int, float)):
            return value > 0
        return False

    def _parse_list(self, value: Any) -> List[Any]:
        """Parse list from Excel (comma or semicolon separated)."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            # Split by comma or semicolon
            items = value.replace(";", ",").split(",")
            result = []
            for item in items:
                item = item.strip()
                try:
                    # Try to convert to number
                    if "." in item:
                        result.append(float(item))
                    else:
                        result.append(int(item))
                except ValueError:
                    result.append(item)
            return result
        return []

    def validate(self) -> List[str]:
        """Validate the configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check that each pipe has a return pipe
        supply_pipes = [p["id"] for p in self.config["pipes"] if not p["id"].endswith("_return")]
        return_pipes = [p["id"] for p in self.config["pipes"] if p["id"].endswith("_return")]

        for supply_id in supply_pipes:
            if f"{supply_id}_return" not in return_pipes:
                errors.append(f"Supply pipe '{supply_id}' missing return pipe")

        # Check existing XOR invest for all components
        for comp_type in ["producers", "storage", "pipes"]:
            for comp in self.config[comp_type]:
                existing = comp.get("existing", False)
                invest = comp.get("invest", False)

                if existing and invest:
                    errors.append(
                        f"{comp_type[:-1]} '{comp['id']}': Cannot have both existing=True and invest=True"
                    )

                if not existing and not invest:
                    errors.append(
                        f"{comp_type[:-1]} '{comp['id']}': Must have either existing=True or invest=True"
                    )

                # If invest, check that options are provided
                if invest:
                    if comp_type == "producers" and not comp.get("Q_options"):
                        errors.append(
                            f"Producer '{comp['id']}': invest=True requires Q_options"
                        )
                    elif comp_type == "storage" and not comp.get("capacity_options"):
                        errors.append(
                            f"Storage '{comp['id']}': invest=True requires capacity_options"
                        )
                    elif comp_type == "pipes" and not comp.get("DN_options"):
                        errors.append(
                            f"Pipe '{comp['id']}': invest=True requires DN_options"
                        )

                # If existing, check that fixed parameters are provided
                if existing:
                    if comp_type == "producers" and not comp.get("Q_nom"):
                        errors.append(
                            f"Producer '{comp['id']}': existing=True requires Q_nom"
                        )
                    elif comp_type == "storage" and not comp.get("capacity_MWh"):
                        errors.append(
                            f"Storage '{comp['id']}': existing=True requires capacity_MWh"
                        )
                    elif comp_type == "pipes" and not comp.get("DN_fixed"):
                        errors.append(
                            f"Pipe '{comp['id']}': existing=True requires DN_fixed"
                        )

        # Check that all referenced nodes exist
        all_nodes = set(self.config["nodes"].keys())

        for pipe in self.config["pipes"]:
            if pipe["from_node"] not in all_nodes:
                errors.append(f"Pipe '{pipe['id']}': from_node '{pipe['from_node']}' not found")
            if pipe["to_node"] not in all_nodes:
                errors.append(f"Pipe '{pipe['id']}': to_node '{pipe['to_node']}' not found")

        for consumer in self.config["consumers"]:
            if consumer["node"] not in all_nodes:
                errors.append(f"Consumer '{consumer['id']}': node '{consumer['node']}' not found")

        # Check that demand profiles exist
        available_profiles = set(self.config["timeseries"].keys())
        for consumer in self.config["consumers"]:
            if consumer["demand_profile"] not in available_profiles:
                errors.append(
                    f"Consumer '{consumer['id']}': demand_profile '{consumer['demand_profile']}' not found in timeseries"
                )

        return errors

    def save_yaml(self, output_path: str | Path) -> None:
        """Save configuration as YAML file.

        Args:
            output_path: Path for output YAML file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False, indent=2)

        print(f"Saved configuration to: {output_path}")

        # Also save timeseries data as CSV if available
        if self.timeseries_data:
            csv_path = output_path.parent / f"{output_path.stem}_timeseries.csv"
            self._save_timeseries_csv(csv_path)

    def _save_timeseries_csv(self, csv_path: Path) -> None:
        """Save timeseries data as CSV file."""
        import csv

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            headers = list(self.timeseries_data.keys())
            writer.writerow(headers)

            # Data rows
            num_rows = len(next(iter(self.timeseries_data.values())))
            for i in range(num_rows):
                row = [self.timeseries_data[col][i] for col in headers]
                writer.writerow(row)

        print(f"Saved timeseries to: {csv_path}")

    def get_summary(self) -> str:
        """Get a summary of the parsed configuration.

        Returns:
            Human-readable summary string
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"Thermal Network: {self.config['thermal_network']['name']}")
        lines.append("=" * 60)
        lines.append(f"Network type: {self.config['thermal_network']['network_type']}")
        lines.append(f"Supply temperature: {self.config['thermal_network']['T_supply_nom']}°C")
        lines.append(f"Return temperature: {self.config['thermal_network']['T_return_nom']}°C")
        lines.append(f"Nominal pressure: {self.config['thermal_network']['p_nominal']} bar")
        lines.append("")

        lines.append("Components:")
        lines.append(f"  Nodes: {len(self.config['nodes'])}")
        lines.append(f"  Pipes (supply + return): {len(self.config['pipes'])}")
        lines.append(f"  Producers: {len(self.config['producers'])}")
        lines.append(f"  Storage units: {len(self.config['storage'])}")
        lines.append(f"  Consumers: {len(self.config['consumers'])}")
        lines.append(f"  Timeseries: {len(self.config['timeseries'])}")
        lines.append("")

        # Brownfield vs Greenfield
        existing_pipes = sum(1 for p in self.config['pipes'] if p.get('existing'))
        invest_pipes = sum(1 for p in self.config['pipes'] if p.get('invest'))
        lines.append("Brownfield/Greenfield Mix:")
        lines.append(f"  Existing pipes: {existing_pipes}")
        lines.append(f"  Investment pipes: {invest_pipes}")

        existing_producers = sum(1 for p in self.config['producers'] if p.get('existing'))
        invest_producers = sum(1 for p in self.config['producers'] if p.get('invest'))
        lines.append(f"  Existing producers: {existing_producers}")
        lines.append(f"  Investment producers: {invest_producers}")

        lines.append("=" * 60)

        return "\n".join(lines)


def create_example_excel_template(output_path: str | Path) -> None:
    """Create an example Excel template for thermal network input.

    Args:
        output_path: Path for the output Excel file
    """
    from energis.utils.xlsx import write_simple_xlsx

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # This is a simplified version - full implementation would need multi-sheet support
    # For now, create a single sheet with instructions

    headers = ["Sheet", "Column", "Description", "Example"]
    rows = [
        ["Netzwerk", "Name", "Network name", "Musterhausen"],
        ["Netzwerk", "T_Vorlauf_nom", "Nominal supply temperature [°C]", "90"],
        ["Netzwerk", "T_Ruecklauf_nom", "Nominal return temperature [°C]", "50"],
        ["", "", "", ""],
        ["Erzeuger", "ID", "Unique identifier", "Kessel_1"],
        ["Erzeuger", "Typ", "Type (boiler, heat_pump, chp)", "boiler"],
        ["Erzeuger", "Bestand?", "Existing? (ja/nein)", "ja"],
        ["Erzeuger", "Q_nom_MW", "Nominal capacity [MW]", "5.0"],
        ["", "", "", ""],
        ["Rohre", "ID", "Pipe identifier", "P1"],
        ["Rohre", "Von_Knoten", "From node", "N1"],
        ["Rohre", "Zu_Knoten", "To node", "N2"],
        ["Rohre", "Laenge_m", "Length [m]", "500"],
    ]

    write_simple_xlsx(str(output_path), headers, rows)
    print(f"Created example template: {output_path}")
