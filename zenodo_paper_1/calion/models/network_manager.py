"""
Network Manager for Thermal District Heating Networks
======================================================
... (Docstring bleibt wie gehabt) ...
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False
    pyo = None

from ..utils.config_utils import resolve_heating_curve_profile
from .blocks.pipe_pair import PipePairBlock
from .blocks.thermal_node import ThermalNodeBlock
from .network_physics import (
    calculate_supply_temperature_series,
    get_heating_curve_parameters,
)
from .state_constraints import add_network_state_validation_config

logger = logging.getLogger(__name__)


class NetworkManager:
    """Manages thermal network components and topology."""

    def __init__(self, config: dict[str, Any], config_dir: Path | None = None):
        """
        Args:
            config: Full configuration dict containing 'thermal_network' or 'network' section
            config_dir: Base directory for resolving relative topology file paths
        """
        self.config = config
        # Ensure state-validation defaults exist once so all downstream
        # components read a consistent configuration.
        if isinstance(self.config, dict):
            add_network_state_validation_config(self.config)
        self.config_dir = config_dir or Path.cwd()
        self._last_pipe_components: dict[str, dict[str, Any]] = {}
        self._last_node_components: dict[str, dict[str, Any]] = {}

        self.nodes = {}        # Dict[str, dict] â€” node configurations
        self.pipes = {}        # Dict[str, dict] â€” pipe configurations
        self.pipe_catalog = {} # Dict[str, dict] â€” available pipe types
        self.topology = {}     # Dict â€” raw topology data from file
        self.parameters = {}   # Dict â€” network parameters (temps, pressures)

        # â”€â”€â”€ FIX: Check BOTH 'thermal_network' AND 'network' config keys â”€â”€â”€
        tn_cfg = config.get('thermal_network', {})
        net_cfg = config.get('network', {})
        self.network_enabled = (
            tn_cfg.get('enabled', False)
            or net_cfg.get('enabled', False)
            # Auto-enable: if pipes are defined inline, the network is active
            or bool(net_cfg.get('pipes'))
            or bool(tn_cfg.get('pipes'))
            or bool(tn_cfg.get('topology_file'))
            or bool(tn_cfg.get('topology_excel'))
        )

        if self.network_enabled:
            self._load_network_topology()

    # â”€â”€ Unified config properties (DRY) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @property
    def _net_cfg(self) -> dict:
        """Unified network config â€” resolves 'thermal_network' vs 'network' key.

        Priority: 'thermal_network' (more specific) > 'network' (YAML shorthand).
        """
        tn = self.config.get('thermal_network', {})
        if tn:
            return tn
        return self.config.get('network', {})

    @property
    def _physics_cfg(self) -> dict:
        """Physics sub-config from unified network config."""
        return self._net_cfg.get('physics', {})

    @property
    def _milp_linearize(self) -> bool:
        """Whether MILP linearization is enabled."""
        return self._net_cfg.get('milp_linearize', False)

    @property
    def _pressure_drop_enabled(self) -> bool:
        """Whether pressure drop calculation is enabled."""
        return self._physics_cfg.get('pressure_drop', True)

    # â”€â”€ Path helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _find_repo_root(self, start_path: Path | None = None) -> Path:
        """Find repository root by searching for .git directory."""
        if start_path is None:
            start_path = Path.cwd()
        current = start_path.resolve()
        for _ in range(10):
            if (current / '.git').exists():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent
        return start_path

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path relative to repo root or config_dir."""
        path = Path(path_str)
        if path.is_absolute():
            return path

        repo_relative = self._find_repo_root() / path
        if repo_relative.exists():
            return repo_relative

        config_relative = self.config_dir / path
        if config_relative.exists():
            return config_relative

        logger.warning(f"Path not found. Tried:\n  - {repo_relative}\n  - {config_relative}")
        return repo_relative

    # â”€â”€ Topology loading â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _load_network_topology(self):
        """Load network topology from YAML file, Excel file, or inline config."""
        # â”€â”€â”€ FIX: Read from BOTH config keys â”€â”€â”€
        network_config = self.config.get('thermal_network', {})
        if not network_config:
            network_config = self.config.get('network', {})

        topology_file = network_config.get('topology_file')
        topology_excel = network_config.get('topology_excel')

        if topology_excel:
            excel_path = self._resolve_path(topology_excel)
            logger.info(f"Loading network topology from Excel: {excel_path}")
            try:
                from calion.io.network_loader import load_network_from_excel
                topology_data = load_network_from_excel(
                    str(excel_path),
                    nodes_sheet=network_config.get('nodes_sheet', 'Network_Nodes'),
                    pipes_sheet=network_config.get('pipes_sheet', 'Network_Pipes'),
                    params_sheet=network_config.get('params_sheet', 'Network_Parameters'),
                )
            except FileNotFoundError:
                logger.error(f"Network Excel file not found: {excel_path}")
                self.network_enabled = False
                return
            except Exception as e:
                logger.error(f"Error loading network from Excel: {e}")
                self.network_enabled = False
                return

            if topology_data is None:
                logger.warning("No network data found in Excel, disabling network")
                self.network_enabled = False
                return

        elif topology_file:
            topology_path = self._resolve_path(topology_file)
            logger.info(f"Loading network topology from YAML: {topology_path}")
            try:
                with open(topology_path, encoding="utf-8") as f:
                    topology_data = yaml.safe_load(f)
            except FileNotFoundError:
                logger.error("=" * 70)
                logger.error("THERMAL NETWORK ERROR: Topology file not found!")
                logger.error(f"  Expected: {topology_path}")
                logger.error(f"  Config value: {topology_file}")
                logger.error(f"  Config dir: {self.config_dir}")
                logger.error(f"  Repo root: {self._find_repo_root()}")
                logger.error("=" * 70)
                self.network_enabled = False
                return
            except yaml.YAMLError as e:
                logger.error(f"Error parsing network YAML file: {e}")
                self.network_enabled = False
                return
        else:
            # Inline config: topology is embedded directly in the network section
            topology_data = network_config

        self.topology = topology_data
        self.parameters = topology_data.get('parameters', {})
        self.pipe_catalog = topology_data.get('pipe_catalog', {})

        self._parse_nodes(topology_data)
        self._overlay_runtime_node_overrides(network_config)
        self._parse_pipes(topology_data)

        logger.info(f"Loaded network: {len(self.nodes)} nodes, {len(self.pipes)} pipes")

    def _parse_nodes(self, topology_data: dict):
        """Parse node definitions from topology (all supported formats).

        Supported formats:
        1. Unified list:  nodes: [{id: ..., type: ...}, ...]
        2. Nested dict:   networks.{net_id}.nodes.{node_id}: {type: ...}
        (stadtbach network_topology.yaml uses this format)
        3. Legacy lists:  production_plants / pump_stations / consumer_zones
        """
        # Format 1: flat nodes list with explicit 'id' field
        nodes_list = topology_data.get('nodes', [])
        if isinstance(nodes_list, list):
            for node_cfg in nodes_list:
                node_id = node_cfg.get('id') or node_cfg.get('node_id')
                if node_id:
                    self.nodes[node_id] = {**node_cfg, 'id': node_id}
        elif isinstance(nodes_list, dict):
            # Format 2a: nodes is itself a dict-of-dicts (key = node_id)
            for node_id, node_cfg in nodes_list.items():
                if node_cfg and isinstance(node_cfg, dict):
                    self.nodes[node_id] = {**node_cfg, 'id': node_id}

        # Format 2b: networks.{network_id}.nodes dict-of-dicts (stadtbach style)
        for net_data in topology_data.get('networks', {}).values():
            if not isinstance(net_data, dict):
                continue
            nodes_in_net = net_data.get('nodes', {})
            if isinstance(nodes_in_net, dict):
                for node_id, node_cfg in nodes_in_net.items():
                    if node_cfg and isinstance(node_cfg, dict):
                        self.nodes[node_id] = {**node_cfg, 'id': node_id}
            elif isinstance(nodes_in_net, list):
                for node_cfg in nodes_in_net:
                    node_id = node_cfg.get('id') or node_cfg.get('node_id')
                    if node_id:
                        self.nodes[node_id] = {**node_cfg, 'id': node_id}

        # Format 3: legacy separate lists per type
        for plant_cfg in topology_data.get('production_plants', []):
            node_id = plant_cfg['node_id']
            self.nodes[node_id] = {**plant_cfg, 'id': node_id, 'type': 'producer'}

        for pump_cfg in topology_data.get('pump_stations', []):
            node_id = pump_cfg['node_id']
            self.nodes[node_id] = {**pump_cfg, 'id': node_id, 'type': 'junction'}

        for consumer_cfg in topology_data.get('consumer_zones', []):
            node_id = consumer_cfg['node_id']
            self.nodes[node_id] = {**consumer_cfg, 'id': node_id, 'type': 'consumer'}

    def _overlay_runtime_node_overrides(self, network_config: dict) -> None:
        """Overlay runtime `network.nodes` entries onto parsed topology nodes."""
        node_overrides = network_config.get('nodes')
        if not node_overrides:
            return

        items: list[tuple[str, dict[str, Any]]] = []
        if isinstance(node_overrides, dict):
            for node_id, node_cfg in node_overrides.items():
                if isinstance(node_cfg, dict):
                    items.append((str(node_id), node_cfg))
        elif isinstance(node_overrides, list):
            for node_cfg in node_overrides:
                if not isinstance(node_cfg, dict):
                    continue
                node_id = node_cfg.get('id') or node_cfg.get('node_id')
                if node_id:
                    items.append((str(node_id), node_cfg))

        applied = 0
        for node_id, node_cfg in items:
            base_cfg = self.nodes.get(node_id, {'id': node_id})
            self.nodes[node_id] = {**base_cfg, **node_cfg, 'id': node_id}
            applied += 1

        if applied > 0:
            sample = self.nodes.get('j_1', {})
            sample_lf = sample.get('return_temp_load_factor') if isinstance(sample, dict) else None
            sample_mode = None
            sample_ref_prof = None
            j14 = self.nodes.get('j_14', {})
            if isinstance(j14, dict):
                sample_mode = j14.get('return_temp_load_mode')
                sample_ref_prof = 'set' if j14.get('return_temp_ref_profile') is not None else 'none'
            logger.info(
                "Applied %d runtime node override(s) from network.nodes. "
                "Sample j_1.return_temp_load_factor=%s, j_14.return_temp_load_mode=%s, "
                "j_14.return_temp_ref_profile=%s",
                applied,
                sample_lf,
                sample_mode,
                sample_ref_prof,
            )

    def _parse_pipes(self, topology_data: dict):
        """Parse pipe definitions from topology.

        Supported formats:
        1. Flat list:   pipes: [{id: ..., from_node: ..., to_node: ...}, ...]
        2. Nested dict: networks.{net_id}.pipes.{pipe_id}: {from_node: ..., to_node: ...}
        3. Dict-of-dicts at top level: pipes.{pipe_id}: {from_node: ..., to_node: ...}
        """
        pipes_val = topology_data.get('pipes', [])
        if isinstance(pipes_val, list):
            for pipe_cfg in pipes_val:
                pipe_id = pipe_cfg.get('id')
                if pipe_id:
                    self.pipes[pipe_id] = pipe_cfg
        elif isinstance(pipes_val, dict):
            for pipe_id, pipe_cfg in pipes_val.items():
                if pipe_cfg and isinstance(pipe_cfg, dict):
                    self.pipes[pipe_id] = {**pipe_cfg, 'id': pipe_id}

        # Nested under 'networks' (stadtbach style)
        for net_data in topology_data.get('networks', {}).values():
            if not isinstance(net_data, dict):
                continue
            pipes_in_net = net_data.get('pipes', {})
            if isinstance(pipes_in_net, dict):
                for pipe_id, pipe_cfg in pipes_in_net.items():
                    if pipe_cfg and isinstance(pipe_cfg, dict):
                        self.pipes[pipe_id] = {**pipe_cfg, 'id': pipe_id}
            elif isinstance(pipes_in_net, list):
                for pipe_cfg in pipes_in_net:
                    pipe_id = pipe_cfg.get('id')
                    if pipe_id:
                        self.pipes[pipe_id] = pipe_cfg

    # â”€â”€ Single-node fallback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _ensure_single_node_fallback(self) -> None:
        """Auto-create a virtual hub node when no pipes are configured.

        When topology has no `pipes:` key (or empty list), a single node
        `_network_root` is created and all existing node components are merged
        into it.  Calling code then proceeds through the unified network path
        without any special-case branches.
        """
        if self.pipes:
            return  # Normal multi-node topology

        virtual_node_id = '_network_root'
        if virtual_node_id not in self.nodes:
            all_components: dict = {}
            for ncfg in self.nodes.values():
                all_components.update(ncfg.get('components', {}))

            self.nodes = {
                virtual_node_id: {
                    'id': virtual_node_id,
                    'type': 'producer',
                    'components': all_components,
                    'name': 'Virtual network root (single-node fallback)',
                }
            }
            logger.info(
                "No pipes configured â€” created virtual single-node hub: _network_root"
            )

    # â”€â”€ Outdoor temperature loader â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _load_outdoor_temp_from_data(self, time_set) -> list[float] | None:
        """Try to load outdoor temperature series from the site input data.

        Searches for common outdoor temperature column names in the input
        Excel/CSV file referenced by the site config section.
        """
        import pandas as pd

        site_cfg = self.config.get('site', {})
        input_file = site_cfg.get('input_xlsx') or site_cfg.get('input_csv')
        if not input_file:
            return None

        input_path = self._resolve_path(input_file)
        if not input_path.exists():
            logger.warning(f"  Input file not found: {input_path}")
            return None

        try:
            if input_path.suffix in ('.xlsx', '.xls'):
                df = pd.read_excel(input_path, sheet_name=0)
            else:
                df = pd.read_csv(input_path)
        except Exception as e:
            logger.warning(f"  Could not read input file for outdoor temp: {e}")
            return None

        # Search for outdoor temperature column (exact matches first)
        outdoor_candidates = [
            "outdoor_temp_C", "T_outdoor_C", "Aussentemperatur_C",
            "Aussentemperatur", "outdoor_temp", "T_aussen_C",
            "T_ambient_C", "ambient_temp_C",
        ]

        # Also check if heating_curve config specifies the column name
        hc_cfg = self._net_cfg.get('heating_curve', {})
        explicit_col = hc_cfg.get('outdoor_temp_column')
        if explicit_col:
            outdoor_candidates.insert(0, explicit_col)

        outdoor_col = None
        for candidate in outdoor_candidates:
            if candidate in df.columns:
                outdoor_col = candidate
                break

        # Fuzzy match: any column containing 'aussen' or 'outdoor' or 'ambient'
        if outdoor_col is None:
            for col in df.columns:
                if any(kw in col.lower() for kw in ['aussen', 'outdoor', 'ambient']):
                    outdoor_col = col
                    break

        if outdoor_col is None:
            logger.warning(
                f"  No outdoor temperature column found in {input_path.name}. "
                f"Tried: {outdoor_candidates[:5]}..."
            )
            return None

        series = pd.to_numeric(df[outdoor_col], errors='coerce').dropna()
        n_timesteps = len(list(time_set))

        if len(series) < n_timesteps:
            logger.warning(
                f"  Outdoor temp series too short ({len(series)} < {n_timesteps} timesteps)"
            )
            return None

        # Trim to match time_set length
        outdoor_values = series.iloc[:n_timesteps].tolist()
        logger.info(f"  Found outdoor temp column: '{outdoor_col}' ({len(outdoor_values)} values)")
        return outdoor_values

    # â”€â”€ Main entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def attach_to_model(self, model, time_set, buses: dict) -> dict[str, Any]:
        """
        Attach network components to Pyomo model.

        Args:
            model: Pyomo ConcreteModel
            time_set: Set of timesteps
            buses: Dict of bus components

        Returns:
            Dict with network results and references
        """
        if not self.network_enabled:
            logger.info("Thermal network disabled, skipping")
            return {}

        logger.info("=" * 60)
        logger.info("ATTACHING THERMAL NETWORK")
        logger.info("=" * 60)

        self._ensure_single_node_fallback()

        temp_setup = self._setup_temperatures(model, time_set)
        pipe_components = self._attach_all_pipes(model, time_set, buses, temp_setup)
        node_components = self._attach_all_nodes(model, time_set, buses, temp_setup, pipe_components)

        milp_linearize = self._milp_linearize
        pressure_drop_enabled = self._pressure_drop_enabled

        self._link_pipe_temperatures(
            model, time_set, pipe_components, node_components, temp_setup=temp_setup
        )
        self._link_consumer_demands(model, time_set, pipe_components, node_components)
        if pressure_drop_enabled:
            self._link_pressure_propagation(model, time_set, pipe_components, node_components)
            pump_el_flows = self._link_pump_head(model, time_set, pipe_components, node_components)
        else:
            logger.info("Pressure drop disabled: skipping pressure propagation and pump head constraints")
            pump_el_flows = []

        if not milp_linearize:
            # Full physics: junction temp mixing + plant return temp (bilinear)
            self._link_junction_flows(model, time_set, pipe_components, node_components)
            self._link_plant_return_temps(model, time_set, temp_setup, pipe_components, node_components)
        else:
            # MILP mode: junction mass balance only (no temp mixing â€” temps are fixed Params)
            self._link_junction_flows_simple(model, time_set, pipe_components, node_components)
            logger.info("MILP mode: skipped temperature mixing + plant return temps (temps are fixed Params)")

        self._setup_network_losses(model, time_set, pipe_components)
        # Keep references for post-solve residual diagnostics.
        self._last_pipe_components = pipe_components
        self._last_node_components = node_components

        logger.info("\n" + "=" * 60)
        logger.info("THERMAL NETWORK ATTACHED SUCCESSFULLY")
        logger.info(f"  Pipes: {len(pipe_components)}")
        logger.info(f"  Nodes: {len(node_components)}")
        logger.info(f"  Pump flows: {len(pump_el_flows)}")
        logger.info("=" * 60)

        return {
            'pipes': pipe_components,
            'nodes': node_components,
            'parameters': self.parameters,
            'supply_temp': temp_setup['supply_temp'],
            'return_temp': temp_setup['return_temp'],
            'ground_temp': temp_setup['ground_temp'],
            'pump_el_flows': pump_el_flows,
        }

    # â”€â”€ Private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _coerce_profile_dict(
        self,
        profile: dict[Any, Any] | None,
        time_set,
        default_value: float,
    ) -> dict[Any, float]:
        """Coerce sparse/mixed-key profile dicts to exact time_set keys."""
        if not isinstance(profile, dict):
            return {t: float(default_value) for t in time_set}

        out: dict[Any, float] = {}
        for idx, t in enumerate(time_set):
            value = None
            for cand in (t, str(t), idx, str(idx), idx + 1, str(idx + 1)):
                if cand in profile:
                    value = profile[cand]
                    break
            if value is None:
                value = default_value
            out[t] = float(value)
        return out

    def _build_temperature_frame_profiles(self, time_set) -> dict[str, dict[Any, float]] | None:
        """Build hourly Tsup/Tret profiles from network.temperature_frame."""
        net_cfg = self._net_cfg
        frame_cfg = net_cfg.get('temperature_frame', {})
        if not isinstance(frame_cfg, dict):
            return None

        seasons_cfg = frame_cfg.get('seasons', {})
        if not isinstance(seasons_cfg, dict) or not seasons_cfg:
            return None

        month_to_values: dict[int, tuple[float, float, float]] = {}
        default_band = float(frame_cfg.get('default_return_band_c', 5.0))
        for _season_name, season_cfg in seasons_cfg.items():
            if not isinstance(season_cfg, dict):
                continue
            months = season_cfg.get('months', [])
            supply_c = season_cfg.get('supply_c')
            return_c = season_cfg.get('return_c')
            band_c = float(season_cfg.get('return_band_c', default_band))
            if supply_c is None or return_c is None:
                continue
            try:
                supply_v = float(supply_c)
                return_v = float(return_c)
            except (TypeError, ValueError):
                continue
            for month in months:
                try:
                    month_i = int(month)
                except (TypeError, ValueError):
                    continue
                if 1 <= month_i <= 12:
                    month_to_values[month_i] = (supply_v, return_v, max(0.0, band_c))

        if not month_to_values:
            return None

        scenario_cfg = self.config.get('scenario', {})
        horizon_cfg = scenario_cfg.get('horizon', {}) if isinstance(scenario_cfg, dict) else {}
        start_raw = horizon_cfg.get('start')
        if not start_raw:
            logger.warning(
                "temperature_frame configured but scenario.horizon.start missing; "
                "falling back to nominal fixed temperatures."
            )
            return None

        start_dt = None
        try:
            start_dt = datetime.fromisoformat(str(start_raw))
        except ValueError:
            for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
                try:
                    start_dt = datetime.strptime(str(start_raw), fmt)
                    break
                except ValueError:
                    continue
        if start_dt is None:
            logger.warning(
                "temperature_frame configured but horizon.start=%r is not parseable; "
                "falling back to nominal fixed temperatures.",
                start_raw,
            )
            return None

        fallback_supply = float(net_cfg.get('supply_temp_c', 90.0))
        fallback_return = float(net_cfg.get('return_temp_c', 55.0))
        supply_profile: dict[Any, float] = {}
        return_profile: dict[Any, float] = {}
        band_profile: dict[Any, float] = {}

        for i, t in enumerate(time_set):
            ts = start_dt + timedelta(hours=i)
            values = month_to_values.get(ts.month)
            if values is None:
                sup_v, ret_v, band_v = fallback_supply, fallback_return, default_band
            else:
                sup_v, ret_v, band_v = values
            supply_profile[t] = float(sup_v)
            return_profile[t] = float(ret_v)
            band_profile[t] = float(band_v)

        logger.info(
            'Using temperature_frame profiles: supply %.1f-%.1f degC, return %.1f-%.1f degC',
            min(supply_profile.values()),
            max(supply_profile.values()),
            min(return_profile.values()),
            max(return_profile.values()),
        )
        return {
            'supply_temp_dict': supply_profile,
            'return_temp_dict': return_profile,
            'return_temp_band_dict': band_profile,
        }

    def _setup_temperatures(self, model, time_set) -> dict[str, Any]:
        """Setup supply/return temperature profiles with config precedence."""
        net_cfg = self._net_cfg

        supply_temp_nominal = self.parameters.get(
            'supply_temp_nominal_c',
            net_cfg.get('supply_temp_c', 90.0)
        )
        return_temp_nominal = self.parameters.get(
            'return_temp_nominal_c',
            net_cfg.get('return_temp_c', 50.0)
        )
        ground_temp = self.parameters.get(
            'ground_temp_default_c',
            net_cfg.get('ground_temp_c', 10.0)
        )

        # 1) Explicit profiles passed via parameters (runner-injected)
        explicit_supply = self.parameters.get('supply_temp_dict')
        explicit_return = self.parameters.get('return_temp_dict')
        explicit_band = self.parameters.get('return_temp_band_dict')
        if isinstance(explicit_supply, dict):
            supply_profile = self._coerce_profile_dict(
                explicit_supply, time_set, float(supply_temp_nominal)
            )
            if isinstance(explicit_return, dict):
                return_profile = self._coerce_profile_dict(
                    explicit_return, time_set, float(return_temp_nominal)
                )
                band_profile = self._coerce_profile_dict(explicit_band, time_set, 0.0)
            else:
                # Supply-only dict: fall back to temperature_frame for return
                frame_profiles = self._build_temperature_frame_profiles(time_set)
                if frame_profiles is not None:
                    return_profile = frame_profiles['return_temp_dict']
                    band_profile = frame_profiles['return_temp_band_dict']
                else:
                    return_profile = {t: float(return_temp_nominal) for t in time_set}
                    band_profile = {t: 0.0 for t in time_set}
            model.supply_temp_series = supply_profile
            model.return_temp_series = return_profile
            supply_temp = sum(supply_profile.values()) / len(supply_profile)
            return_temp = sum(return_profile.values()) / len(return_profile)
            logger.info(
                'Using explicit Tsup profile from config parameters (mean %.1f degC), '
                'return profile from %s (mean %.1f degC).',
                supply_temp,
                'explicit dict' if isinstance(explicit_return, dict) else 'temperature_frame/nominal',
                return_temp,
            )
            return {
                'supply_temp': supply_temp,
                'return_temp': return_temp,
                'ground_temp': ground_temp,
                'use_heating_curve': False,
                'use_outdoor_temp': False,
                'supply_temp_dict': supply_profile,
                'return_temp_dict': return_profile,
                'return_temp_band_dict': band_profile,
            }

        # 2) Seasonal frame profiles from network.temperature_frame
        frame_profiles = self._build_temperature_frame_profiles(time_set)
        if frame_profiles is not None:
            supply_profile = frame_profiles['supply_temp_dict']
            return_profile = frame_profiles['return_temp_dict']
            band_profile = frame_profiles['return_temp_band_dict']
            model.supply_temp_series = supply_profile
            model.return_temp_series = return_profile
            supply_temp = sum(supply_profile.values()) / len(supply_profile)
            return_temp = sum(return_profile.values()) / len(return_profile)
            return {
                'supply_temp': supply_temp,
                'return_temp': return_temp,
                'ground_temp': ground_temp,
                'use_heating_curve': False,
                'use_outdoor_temp': False,
                'supply_temp_dict': supply_profile,
                'return_temp_dict': return_profile,
                'return_temp_band_dict': band_profile,
            }

        # 3) Legacy behavior: heating curve/fixed supply + fixed return
        use_outdoor_temp = (
            net_cfg.get('use_outdoor_temperature', False)
            or net_cfg.get('heating_curve', {}).get('enabled', False)
            or self.parameters.get('heating_curve', {}).get('enabled', False)
        )

        if use_outdoor_temp and hasattr(model, 'outdoor_temp'):
            logger.info('Using time-varying outdoor temperature from model')
            outdoor_temp_series = [model.outdoor_temp[t] for t in time_set]
        elif use_outdoor_temp and not hasattr(model, 'outdoor_temp'):
            logger.warning(
                'Heating curve needs outdoor temperature but model.outdoor_temp not set! '
                'Attempting to load from site data...'
            )
            outdoor_temp_series = self._load_outdoor_temp_from_data(time_set)
            if outdoor_temp_series is not None:
                model.outdoor_temp = {t: outdoor_temp_series[i] for i, t in enumerate(time_set)}
                logger.info(
                    f"  Loaded outdoor temp: {min(outdoor_temp_series):.1f}Â°C "
                    f"to {max(outdoor_temp_series):.1f}Â°C"
                )
            else:
                logger.warning(
                    "  Could not load outdoor temperature - falling back to fixed supply temp!"
                )
                use_outdoor_temp = False
                model.outdoor_temp = {t: ground_temp for t in time_set}
                outdoor_temp_series = [ground_temp for _ in time_set]
        else:
            model.outdoor_temp = {t: ground_temp for t in time_set}
            outdoor_temp_series = [ground_temp for _ in time_set]
            logger.info(f"Using fixed ground temperature: {ground_temp}Â°C")

        heating_curve_config_raw = self.parameters.get('heating_curve', {})
        if not heating_curve_config_raw:
            heating_curve_config_raw = net_cfg.get('heating_curve', {})

        heating_curve_config = resolve_heating_curve_profile(
            heating_curve_config_raw,
            config_dir=self.config_dir,
        )
        use_heating_curve = heating_curve_config.get('enabled', False)

        if use_heating_curve and use_outdoor_temp:
            T_supply_min = heating_curve_config.get('T_supply_min_c', 80.0)
            T_supply_max = heating_curve_config.get('T_supply_max_c', 120.0)
            T_outdoor_high = heating_curve_config.get('T_outdoor_high_c', 20.0)
            T_outdoor_low = heating_curve_config.get('T_outdoor_low_c', -10.0)

            supply_temp_series = calculate_supply_temperature_series(
                T_outdoor_series=outdoor_temp_series,
                T_supply_min_c=T_supply_min,
                T_supply_max_c=T_supply_max,
                T_outdoor_high_c=T_outdoor_high,
                T_outdoor_low_c=T_outdoor_low,
            )
            model.supply_temp_series = {t: supply_temp_series[i] for i, t in enumerate(time_set)}

            curve_params = get_heating_curve_parameters(
                T_supply_min_c=T_supply_min,
                T_supply_max_c=T_supply_max,
                T_outdoor_high_c=T_outdoor_high,
                T_outdoor_low_c=T_outdoor_low,
            )
            logger.info("\n  HEATING CURVE (Heizkurve) ACTIVE:")
            logger.info(f"    Formula: {curve_params['formula']}")
            logger.info(
                f"    Range: {T_supply_min}Â°C (at {T_outdoor_high}Â°C outdoor) "
                f"to {T_supply_max}Â°C (at {T_outdoor_low}Â°C outdoor)"
            )
            logger.info(
                f"    Supply temp range in data: "
                f"{min(supply_temp_series):.1f}Â°C - {max(supply_temp_series):.1f}Â°C"
            )
            supply_temp = sum(supply_temp_series) / len(supply_temp_series)
            logger.info(f"    Average supply temp: {supply_temp:.1f}Â°C")
        else:
            supply_temp = float(supply_temp_nominal)
            model.supply_temp_series = {t: supply_temp for t in time_set}
            if use_heating_curve and not use_outdoor_temp:
                logger.warning('  Heating curve enabled but outdoor temperature not available!')
                logger.warning(f"  -> Supply temp FIXED at {supply_temp:.1f}Â°C for all timesteps!")
                logger.warning(
                    '  Fix: ensure outdoor_temp_C column exists in input data, '
                    "or set 'outdoor_temp_column' in heating_curve config."
                )
            else:
                logger.info(f"  Using fixed supply temperature: {supply_temp:.1f}Â°C")

        return_temp = float(return_temp_nominal)
        model.return_temp_series = {t: return_temp for t in time_set}
        return {
            'supply_temp': supply_temp,
            'return_temp': return_temp,
            'ground_temp': ground_temp,
            'use_heating_curve': use_heating_curve,
            'use_outdoor_temp': use_outdoor_temp,
            'supply_temp_dict': {t: model.supply_temp_series[t] for t in time_set},
            'return_temp_dict': {t: model.return_temp_series[t] for t in time_set},
            'return_temp_band_dict': {t: 0.0 for t in time_set},
        }

    def _attach_all_pipes(self, model, time_set, buses, temp_setup) -> dict:
        """Phase 1: Validate and attach all pipe pair blocks."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        use_outdoor_temp = temp_setup['use_outdoor_temp']

        pipe_components: dict = {}
        logger.info(f"\nAttaching {len(self.pipes)} pipe pairs...")

        # Read flags from unified config
        milp_linearize = self._milp_linearize
        temperature_linearize_pipe = self._net_cfg.get('temperature_linearize', None)
        pressure_drop_enabled = self._pressure_drop_enabled
        physics_cfg = self._physics_cfg
        params_cfg = self._net_cfg.get('parameters', {}) if isinstance(self._net_cfg.get('parameters', {}), dict) else {}
        delay_warmup_mode = params_cfg.get('delay_warmup_mode', physics_cfg.get('delay_warmup_mode', 'cold_zero'))
        root_state_validation = self.config.get('state_validation', {})
        if not isinstance(root_state_validation, dict):
            root_state_validation = {}
        net_state_validation = self._net_cfg.get('state_validation', {})
        if not isinstance(net_state_validation, dict):
            net_state_validation = {}
        merged_state_validation_global = {**root_state_validation, **net_state_validation}

        for pipe_id, pipe_config in self.pipes.items():
            pipe_dict = pipe_config if isinstance(pipe_config, dict) else pipe_config.__dict__
            # Prevent runner/raw config profile dicts (often 0-based) from overriding
            # the already coerced time_set-aligned profiles from temp_setup.
            safe_parameters = dict(self.parameters)
            safe_parameters.pop('supply_temp_dict', None)
            safe_parameters.pop('return_temp_dict', None)
            safe_parameters.pop('return_temp_band_dict', None)
            enriched_config = {
                **pipe_dict,
                **safe_parameters,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                # Per-timestep supply temperature (from heating curve or fixed nominal).
                # PipePairBlock uses this to initialize T_supply_in Params in MILP mode,
                # enabling variable delivery temperatures that track the Heizkurve.
                'supply_temp_dict': temp_setup['supply_temp_dict'],
                # Optional per-timestep return temperatures (seasonal frame / runner injection).
                'return_temp_dict': temp_setup.get('return_temp_dict'),
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
                'milp_linearize': milp_linearize,
                'temperature_linearize': temperature_linearize_pipe,
                'pressure_drop_enabled': pressure_drop_enabled,
                'pump_enabled': pressure_drop_enabled and pipe_dict.get('pump_enabled', True),
                'physics': physics_cfg,
                'delay_warmup_mode': delay_warmup_mode,
                'state_validation': merged_state_validation_global,
            }
            PipePairBlock.validate_config(enriched_config)
            pipe_result = PipePairBlock.attach(model, time_set, enriched_config, buses)
            pipe_components[pipe_id] = pipe_result
            logger.info(
                f"  âœ“ {pipe_id}: {pipe_config.get('from_node', pipe_config.get('from'))} â†’ "
                f"{pipe_config.get('to_node', pipe_config.get('to'))} "
                f"({pipe_config['length_m']}m)"
            )

        return pipe_components

    def _attach_all_nodes(self, model, time_set, buses, temp_setup, pipe_components) -> dict:
        """Phase 2: Validate and attach all thermal node blocks."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']

        # Read flags from unified config
        milp_linearize = self._milp_linearize
        temperature_linearize = self._net_cfg.get('temperature_linearize', None)
        pressure_drop_enabled = self._pressure_drop_enabled
        net_cfg = self._net_cfg
        delta_p_min_consumer = net_cfg.get('delta_p_min_consumer_bar', 0.7)
        lin_cfg = net_cfg.get('linearization', {})
        disable_node_return_tuning = bool(net_cfg.get('disable_node_return_tuning', False))
        params_cfg = net_cfg.get('parameters', {}) if isinstance(net_cfg.get('parameters', {}), dict) else {}
        allow_heat_demand_slack_global = bool(params_cfg.get('allow_heat_demand_slack', False))
        demand_slack_penalty_global = float(params_cfg.get('demand_slack_penalty_eur_per_mwh', 1e6))
        max_heat_demand_slack_frac_global = float(params_cfg.get('max_heat_demand_slack_frac', 0.0))
        root_state_validation = self.config.get('state_validation', {})
        if not isinstance(root_state_validation, dict):
            root_state_validation = {}
        net_state_validation = net_cfg.get('state_validation', {})
        if not isinstance(net_state_validation, dict):
            net_state_validation = {}
        global_state_validation_base = {**root_state_validation, **net_state_validation}
        if disable_node_return_tuning:
            logger.info("Node return tuning is disabled by network config flag.")

        node_components: dict = {}
        logger.info(f"\nAttaching {len(self.nodes)} thermal nodes...")

        for node_id, node_config in self.nodes.items():
            node_dict = node_config if isinstance(node_config, dict) else node_config.__dict__
            node_type = node_dict.get('type', 'unknown')
            if node_type == 'plant':
                node_type = 'producer'

            if disable_node_return_tuning and node_type in ('consumer', 'mixed'):
                node_dict = dict(node_dict)
                node_dict['return_temp_load_factor'] = 0.0
                node_dict['return_temp_ref_profile'] = None
                node_dict['return_temp_band_profile'] = None
            if allow_heat_demand_slack_global and node_type in ('consumer', 'mixed'):
                node_dict = dict(node_dict)
                node_dict.setdefault('allow_heat_demand_slack', True)
                node_dict.setdefault('demand_slack_penalty_eur_per_mwh', demand_slack_penalty_global)
                node_dict.setdefault('max_heat_demand_slack_frac', max_heat_demand_slack_frac_global)

            # MILP path: keep T_return as fixed profile (linear + realistic).
            if (
                milp_linearize
                and node_type in ('consumer', 'mixed')
                and 'return_temp_profile' not in node_dict
                and temp_setup.get('return_temp_dict')
            ):
                node_dict = dict(node_dict)
                node_dict['return_temp_profile'] = temp_setup.get('return_temp_dict')

            # NLP path: variable T_return within time-varying frame.
            if (
                not milp_linearize
                and node_type in ('consumer', 'mixed')
                and temp_setup.get('return_temp_dict')
            ):
                node_dict = dict(node_dict)
                ref_profile = temp_setup.get('return_temp_dict')
                band_profile = temp_setup.get('return_temp_band_dict') or {}
                node_dict.setdefault('return_temp_ref_profile', ref_profile)
                node_dict.setdefault('return_temp_band_profile', band_profile)
                if 'return_temp_range' not in node_dict and isinstance(ref_profile, dict):
                    ref_vals = list(ref_profile.values())
                    if ref_vals:
                        band_default = float(node_dict.get('return_temp_band_c', 0.0))
                        lows: list[float] = []
                        highs: list[float] = []
                        for key, ref_val in ref_profile.items():
                            if isinstance(band_profile, dict):
                                band_val = band_profile.get(
                                    key,
                                    band_profile.get(str(key), band_default),
                                )
                            else:
                                band_val = band_default
                            band_v = max(0.0, float(band_val))
                            ref_v = float(ref_val)
                            lows.append(ref_v - band_v)
                            highs.append(ref_v + band_v)
                        node_dict['return_temp_range'] = [float(min(lows)), float(max(highs))]
            global_state_validation = global_state_validation_base
            node_state_validation = node_dict.get('state_validation', {})
            if not isinstance(node_state_validation, dict):
                node_state_validation = {}
            merged_state_validation = dict(global_state_validation)
            if node_state_validation:
                for _k, _v in node_state_validation.items():
                    if (
                        isinstance(_v, dict)
                        and isinstance(merged_state_validation.get(_k), dict)
                    ):
                        merged_state_validation[_k] = {
                            **merged_state_validation[_k],
                            **_v,
                        }
                    else:
                        merged_state_validation[_k] = _v

            enriched_config = {
                **node_dict,
                'id': node_id,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_c': return_temp,
                'milp_linearize': milp_linearize,
                'temperature_linearize': temperature_linearize,
                'linearization': lin_cfg,
                'pressure_drop_enabled': pressure_drop_enabled,
                'delta_p_min_consumer_bar': delta_p_min_consumer,
                'state_validation': merged_state_validation,
            }
            ThermalNodeBlock.validate_config(enriched_config)
            node_result = ThermalNodeBlock.attach(
                model, time_set, enriched_config, buses, pipe_components
            )
            node_components[node_id] = node_result
            logger.info(f"  âœ“ {node_id} ({node_type})")

        return node_components

    def _link_pipe_temperatures(
        self, model, time_set, pipe_components, node_components, temp_setup: dict | None = None
    ) -> None:
        """Phase 3: manager-owned pipe<->node temperature coupling with interface checks."""
        milp_linearize = self._milp_linearize
        logger.info("\nConnecting pipe temperatures to nodes...")
        supply_profile = None
        if isinstance(temp_setup, dict):
            prof = temp_setup.get('supply_temp_dict')
            if isinstance(prof, dict) and prof:
                supply_profile = prof

        # Producer/mixed source nodes need an explicit supply-temperature anchor so
        # T_supply is never left as a free variable.
        anchor_mode = str(
            self._net_cfg.get('producer_supply_anchor_mode', 'profile_or_nominal')
        ).strip().lower()
        if anchor_mode not in ('profile_or_nominal', 'profile_only', 'none'):
            anchor_mode = 'profile_or_nominal'
        anchored_source_nodes: set[str] = set()
        if not milp_linearize:
            for node_id, node_comp in node_components.items():
                node_type = node_comp.get('type')
                source_like = node_type in ('producer', 'mixed') and not node_comp.get('incoming_pipes', [])
                if not source_like:
                    continue
                node_T_supply = node_comp.get('T_supply')
                if not isinstance(node_T_supply, pyo.Var):
                    node_comp['supply_temp_source'] = 'fixed_param'
                    continue

                if supply_profile is not None:
                    cname = f"source_{node_id}_T_supply_profile_anchor"
                    if not hasattr(model, cname):
                        def source_profile_rule(m, t, _T=node_T_supply, _prof=supply_profile):
                            value = _prof.get(t, _prof.get(str(t), None))
                            if value is None:
                                return pyo.Constraint.Skip
                            return _T[t] == float(value)
                        setattr(model, cname, pyo.Constraint(time_set, rule=source_profile_rule))
                    node_comp['supply_temp_source'] = 'profile'
                    anchored_source_nodes.add(node_id)
                    continue

                if anchor_mode == 'profile_or_nominal':
                    node_cfg = self.nodes.get(node_id, {}) if isinstance(self.nodes.get(node_id, {}), dict) else {}
                    anchor_temp = float(
                        node_cfg.get(
                            'supply_temp_nominal_c',
                            self.parameters.get('supply_temp_nominal_c', self._net_cfg.get('supply_temp_c', 90.0)),
                        )
                    )
                    cname = f"source_{node_id}_T_supply_nominal_anchor"
                    if not hasattr(model, cname):
                        setattr(
                            model,
                            cname,
                            pyo.Constraint(time_set, rule=lambda m, t, _T=node_T_supply, _v=anchor_temp: _T[t] == _v),
                        )
                    node_comp['supply_temp_source'] = 'nominal_anchor'
                    anchored_source_nodes.add(node_id)
                elif anchor_mode == 'profile_only':
                    node_comp['supply_temp_source'] = 'unanchored_profile_missing'
                    logger.warning(
                        "  âš  Source node %s has no supply profile; T_supply remains externally coupled only.",
                        node_id,
                    )
                else:
                    node_comp['supply_temp_source'] = 'unanchored_by_config'

        for pipe_id, pipe_comp in pipe_components.items():
            required_pipe_keys = ('from_node', 'to_node', 'T_supply_in', 'T_return_in')
            missing_pipe_keys = [k for k in required_pipe_keys if k not in pipe_comp]
            if missing_pipe_keys:
                raise ValueError(f"Pipe {pipe_id} missing interface keys: {missing_pipe_keys}")

            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']
            pipe_T_supply_in = pipe_comp['T_supply_in']
            pipe_T_return_in = pipe_comp['T_return_in']

            if from_node in node_components and not milp_linearize:
                from_node_comp = node_components[from_node]
                if 'T_supply' not in from_node_comp:
                    raise ValueError(f"Node {from_node} missing T_supply interface for pipe {pipe_id}")
                node_T_supply = from_node_comp['T_supply']
                constraint_name = f"link_pipe_{pipe_id}_supply_in_to_node_{from_node}"

                def supply_link_rule(m, t, _pipe=pipe_T_supply_in, _node=node_T_supply):
                    if isinstance(_node, pyo.Param):
                        return _pipe[t] == pyo.value(_node[t])
                    return _pipe[t] == _node[t]

                setattr(model, constraint_name, pyo.Constraint(time_set, rule=supply_link_rule))
                from_node_comp.setdefault('supply_outgoing_pipe_links', []).append(pipe_id)
                logger.info(f"    {pipe_id}.T_supply_in â† {from_node}.T_supply")

            if to_node in node_components and not milp_linearize:
                to_node_comp = node_components[to_node]
                if 'T_return' not in to_node_comp:
                    raise ValueError(f"Node {to_node} missing T_return interface for pipe {pipe_id}")
                node_T_return = to_node_comp['T_return']
                constraint_name = f"link_pipe_{pipe_id}_return_in_to_node_{to_node}"

                def return_link_rule(m, t, _pipe=pipe_T_return_in, _node=node_T_return):
                    if isinstance(_node, pyo.Param):
                        return _pipe[t] == pyo.value(_node[t])
                    return _pipe[t] == _node[t]

                setattr(model, constraint_name, pyo.Constraint(time_set, rule=return_link_rule))
                to_node_comp.setdefault('return_outgoing_pipe_links', []).append(pipe_id)
                logger.info(f"    {pipe_id}.T_return_in â† {to_node}.T_return")

            # Track return-side incoming pipes for producer/mixed nodes.
            if from_node in node_components:
                from_node_comp = node_components[from_node]
                if from_node_comp['type'] in ('producer', 'mixed'):
                    rp = from_node_comp.setdefault('return_pipes', [])
                    if pipe_id not in rp:
                        rp.append(pipe_id)
                    ri = from_node_comp.setdefault('return_incoming_pipes', [])
                    if pipe_id not in ri:
                        ri.append(pipe_id)

        # Final diagnostics for link coverage per node.
        for node_id, node_comp in node_components.items():
            node_comp.setdefault('supply_outgoing_pipe_links', [])
            node_comp.setdefault('return_outgoing_pipe_links', [])
            node_comp['interface_validated'] = True
            if node_id in anchored_source_nodes:
                node_comp['interface_supply_anchor'] = node_comp.get('supply_temp_source', 'profile')


    def _link_consumer_demands(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 4: Connect consumer heat demands to incoming pipe Q_consumer variables.

        Uses Q_consumer (the delay-aware delivery variable) rather than Q_delivered.
        """
        logger.info("\nConnecting consumer demands to pipes...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] not in ('consumer', 'mixed'):
                continue

            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])
            has_outgoing = len(outgoing_pipes) > 0
            node_Q_demand = node_comp.get('Q_demand')
            node_Q_slack = node_comp.get('Q_demand_slack')

            if len(incoming_pipes) == 1 and not has_outgoing:
                # Mixed terminal nodes: constraint_builder adds a combined balance
                if node_comp['type'] == 'mixed':
                    logger.info(
                        f"  âœ“ {node_id} (mixed terminal â€” combined balance in constraint_builder)"
                    )
                    continue

                # Simple terminal consumer: one pipe in, no downstream
                pipe_id = incoming_pipes[0]
                pipe_comp = pipe_components[pipe_id]
                pipe_Q_consumer = pipe_comp.get('Q_consumer', pipe_comp['Q_delivered'])

                def demand_heat_rule(
                    m, t, _Q_pipe=pipe_Q_consumer, _Q_dem=node_Q_demand, _Q_slack=node_Q_slack
                ):
                    if isinstance(_Q_dem, pyo.Param):
                        q_dem_t = pyo.value(_Q_dem[t])
                    else:
                        q_dem_t = _Q_dem[t]
                    if _Q_slack is not None:
                        return _Q_pipe[t] + _Q_slack[t] == q_dem_t
                    return _Q_pipe[t] == q_dem_t

                setattr(model, f"link_heat_demand_{node_id}_to_pipe_{pipe_id}",
                        pyo.Constraint(time_set, rule=demand_heat_rule))
                if node_Q_slack is not None:
                    logger.info(f"  âœ“ {node_id} demand â† pipe {pipe_id} (Q_consumer + slack)")
                else:
                    logger.info(f"  âœ“ {node_id} demand â† pipe {pipe_id} (Q_consumer)")

            elif len(incoming_pipes) == 1 and has_outgoing:
                # Passthrough consumer: takes demand fraction, passes rest downstream
                pipe_id = incoming_pipes[0]
                pipe_comp = pipe_components[pipe_id]
                pipe_m_dot = pipe_comp['m_dot']
                node_m_dot = node_comp['m_dot_demand']

                def passthrough_flow_rule(m, t, _pipe=pipe_m_dot, _node=node_m_dot, _out=outgoing_pipes):
                    outgoing_flow = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                    return _pipe[t] == _node[t] + outgoing_flow

                setattr(model, f"link_demand_{node_id}_passthrough_flow",
                        pyo.Constraint(time_set, rule=passthrough_flow_rule))
                logger.info(
                    f"  âœ“ {node_id} passthrough: incoming={pipe_id}, "
                    f"outgoing={len(outgoing_pipes)} pipes"
                )

            elif len(incoming_pipes) > 1:
                node_m_dot = node_comp['m_dot_demand']

                if has_outgoing:
                    def multi_passthrough_flow_rule(
                        m, t, _in=incoming_pipes, _out=outgoing_pipes, _node=node_m_dot
                    ):
                        total_in = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                        total_out = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                        return total_in == _node[t] + total_out

                    setattr(model, f"link_demand_{node_id}_multi_passthrough_flow",
                            pyo.Constraint(time_set, rule=multi_passthrough_flow_rule))
                    logger.info(
                        f"  âœ“ {node_id} has {len(incoming_pipes)} incoming, "
                        f"{len(outgoing_pipes)} outgoing pipes"
                    )
                else:
                    # Multiple incoming pipes, no outgoing.
                    # Prefer node-level slack from thermal_node config; fallback to
                    # a permissive unbounded slack for legacy configs.
                    _slack_var = node_Q_slack
                    _penalty = self.parameters.get('demand_slack_penalty_eur_per_mwh', 1e6)
                    if _slack_var is None:
                        _slack_var = pyo.Var(time_set, domain=pyo.NonNegativeReals)
                        setattr(model, f"demand_slack_{node_id}", _slack_var)
                        if not hasattr(model, 'demand_slack_penalty_terms'):
                            model.demand_slack_penalty_terms = []
                        model.demand_slack_penalty_terms.append((_slack_var, _penalty))

                    def multi_pipe_heat_rule(
                        m, t, _incoming=incoming_pipes, _Q=node_Q_demand, _slack=_slack_var
                    ):
                        total_Q_consumer = sum(
                            pipe_components[pid].get('Q_consumer', pipe_components[pid]['Q_delivered'])[t]
                            for pid in _incoming
                        )
                        if isinstance(_Q, pyo.Param):
                            return total_Q_consumer + _slack[t] == pyo.value(_Q[t])
                        return total_Q_consumer + _slack[t] == _Q[t]

                    setattr(model, f"link_demand_{node_id}_multi_pipe_heat",
                            pyo.Constraint(time_set, rule=multi_pipe_heat_rule))
                    if node_Q_slack is not None:
                        logger.info(
                            f"  âœ“ {node_id}: {len(incoming_pipes)} pipes â†’ "
                            "Q_consumer sum + node slack = Q_demand"
                        )
                    else:
                        logger.info(
                            f"  âœ“ {node_id}: {len(incoming_pipes)} pipes â†’ "
                            f"Q_consumer sum + slack = Q_demand (penalty={_penalty:.0e} â‚¬/MWh)"
                        )
            else:
                logger.warning(f"  âš  {node_id} has no incoming pipes!")

    def _link_junction_flows(self, model, time_set, pipe_components, node_components) -> None:
        """Phase 4b: Mass flow balance constraints for junction nodes."""
        logger.info("\nSetting up junction flow balance constraints...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'junction':
                continue

            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])

            if not incoming_pipes or not outgoing_pipes:
                logger.warning(
                    f"  âš  Junction {node_id} incomplete: "
                    f"{len(incoming_pipes)} in, {len(outgoing_pipes)} out"
                )
                continue

            def junction_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                total_in = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                total_out = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                return total_in == total_out

            setattr(model, f"junction_{node_id}_flow_balance",
                    pyo.Constraint(time_set, rule=junction_flow_rule))

            logger.info(
                f"  âœ“ {node_id}: flow balance {len(incoming_pipes)} in = {len(outgoing_pipes)} out"
            )

            # Supply-side temperature mixing is handled inside ThermalNodeBlock.

    def _link_junction_flows_simple(self, model, time_set, pipe_components, node_components) -> None:
        """MILP-mode simplified junction flow balance: supply-side mass balance only."""
        logger.info("\nSetting up simplified junction flow balance (MILP mode)...")

        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'junction':
                continue

            incoming_pipes = node_comp.get('incoming_pipes', [])
            outgoing_pipes = node_comp.get('outgoing_pipes', [])

            if not incoming_pipes or not outgoing_pipes:
                continue

            def junction_flow_rule(m, t, _in=incoming_pipes, _out=outgoing_pipes):
                total_in = sum(pipe_components[pid]['m_dot'][t] for pid in _in)
                total_out = sum(pipe_components[pid]['m_dot'][t] for pid in _out)
                return total_in == total_out

            setattr(model, f"junction_{node_id}_flow_balance",
                    pyo.Constraint(time_set, rule=junction_flow_rule))
            logger.info(f"  âœ“ {node_id}: {len(incoming_pipes)} in = {len(outgoing_pipes)} out")

    def _link_plant_return_temps(
        self, model, time_set, temp_setup, pipe_components, node_components
    ) -> None:
        """Phase 5: Link node return temperatures to incoming return-side pipe outlets."""
        logger.info("\nSetting up return temperature mixing constraints...")

        for node_id, node_comp in node_components.items():
            return_incoming = node_comp.get('return_incoming_pipes')
            if not isinstance(return_incoming, list):
                return_incoming = node_comp.get('outgoing_pipes', [])
            if not return_incoming:
                if node_comp.get('type') == 'producer':
                    logger.warning(f"  âš  Producer {node_id} has no return incoming pipes")
                continue

            self._add_junction_temperature_mixing(
                model,
                time_set,
                node_id,
                return_incoming,
                node_components,
                pipe_components,
                temperature_attr='T_return_out',
                node_temp_attr='T_return',
                constraint_prefix=f"return_mix_{node_id}",
            )
            node_comp['return_mixing_pipes'] = list(return_incoming)

        logger.info("\nChecking plant-to-network heat linkage...")
        for node_id, node_comp in node_components.items():
            if node_comp['type'] == 'producer':
                outgoing = node_comp.get('outgoing_pipes', [])
                logger.info(f"  Producer {node_id}: {len(outgoing)} outgoing pipes")

    def _add_junction_temperature_mixing(
        self,
        model,
        time_set,
        node_id: str,
        pipe_ids: list[str],
        node_components: dict,
        pipe_components: dict,
        temperature_attr: str = 'T_supply_out',
        node_temp_attr: str = 'T_supply',
        constraint_prefix: str | None = None,
    ) -> None:
        """Add physical enthalpy mixing for node temperatures.

        For a single incoming pipe:
            T_node == T_pipe_out
        For multiple incoming pipes:
            T_node * Î£ m_in == Î£ (m_in * T_pipe_out)
        where m_in is pipe mass-flow magnitude (`m_dot_abs` when available).
        """
        if not pipe_ids:
            return

        pfx = constraint_prefix or f"junc_mix_{node_id}"
        node_T = node_components[node_id][node_temp_attr]
        if isinstance(node_T, pyo.Param):
            logger.info(
                "  âŠ˜ %s: skipped %s mixing because node temperature is fixed Param",
                node_id,
                node_temp_attr,
            )
            return

        if len(pipe_ids) == 1:
            pid = pipe_ids[0]
            pipe_T = pipe_components[pid][temperature_attr]
            setattr(
                model,
                f"{pfx}_single_pipe",
                pyo.Constraint(time_set, rule=lambda m, t, _n=node_T, _p=pipe_T: _n[t] == _p[t]),
            )
            logger.info("  âœ“ %s: single-pipe %s link from %s", node_id, node_temp_attr, pid)
            return

        def mixing_rule(m, t, _pipes=pipe_ids, _node_T=node_T, _attr=temperature_attr):
            total_m = 0
            weighted_t = 0
            for pid in _pipes:
                pipe_comp = pipe_components[pid]
                flow_var = pipe_comp.get('m_dot_abs')
                if flow_var is None:
                    flow_var = pipe_comp.get('m_dot')
                if flow_var is None:
                    raise ValueError(f"Pipe {pid} has no flow variable for mixing")
                temp_var = pipe_comp[_attr]
                total_m += flow_var[t]
                weighted_t += flow_var[t] * temp_var[t]
            return _node_T[t] * total_m == weighted_t

        setattr(model, f"{pfx}_enthalpy", pyo.Constraint(time_set, rule=mixing_rule))
        logger.info("  âœ“ %s: enthalpy mixing (%d pipes, attr=%s)", node_id, len(pipe_ids), temperature_attr)

    def _link_pressure_propagation(
        self, model, time_set, pipe_components: dict, node_components: dict
    ) -> None:
        """A1 â€” Pressure propagation through the pipe network.

        For each pipe (from_node â†’ to_node):
        Supply side:  P_supply[to_node, t]   == P_supply[from_node, t] - delta_p_supply[pipe, t]
        Return side:  P_return[from_node, t] == P_return[to_node, t]   - delta_p_return[pipe, t]

        Producer nodes have their supply pressure fixed to the configured setpoint.
        Consumer nodes get a minimum pressure constraint (min_required_bar).
        """
        logger.info("\nSetting up pressure propagation constraints...")

        # Fix producer supply pressure setpoints
        for node_id, node_comp in node_components.items():
            if node_comp['type'] not in ('producer', 'mixed'):
                continue
            node_cfg = self.nodes.get(node_id, {})
            setpoint = node_cfg.get('pressure', {}).get('setpoint_bar', 10.0)
            node_P_supply = node_comp['pressure_supply']

            setattr(
                model,
                f"producer_{node_id}_P_supply_setpoint",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _P=node_P_supply, _sp=setpoint: _P[t] == _sp,
                ),
            )
            logger.info(
                f"  âœ“ Producer {node_id}: P_supply fixed = {setpoint} bar, "
                f"P_return determined by pump head"
            )

        # Collect producer/mixed node IDs
        producer_nodes = {
            nid for nid, nc in node_components.items() if nc['type'] in ('producer', 'mixed')
        }

        # Propagate pressure through pipes
        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']

            if from_node not in node_components or to_node not in node_components:
                continue

            # Skip loop-closing pipes
            if to_node in producer_nodes:
                logger.info(
                    f"  âŠ˜ {pipe_id}: loop-closing pipe ({from_node} â†’ producer {to_node}) "
                    f"â€” pressure propagation skipped"
                )
                continue

            pipe_prefix = pipe_comp.get('prefix', pipe_id.upper().replace('-', '_'))
            delta_p_supply = getattr(model, f"{pipe_prefix}_delta_p_supply", None)
            delta_p_return = getattr(model, f"{pipe_prefix}_delta_p_return", None)

            if delta_p_supply is None or delta_p_return is None:
                logger.warning(f"  âš  {pipe_id}: pressure drop variables not found, skipping propagation")
                continue

            from_P_supply = node_components[from_node]['pressure_supply']
            to_P_supply = node_components[to_node]['pressure_supply']
            from_P_return = node_components[from_node]['pressure_return']
            to_P_return = node_components[to_node]['pressure_return']
            flow_dir = pipe_comp.get('flow_dir')
            bidirectional_pipe = bool(pipe_comp.get('bidirectional', False)) and flow_dir is not None

            if not bidirectional_pipe:
                # Supply: pressure drops from from_node to to_node
                setattr(
                    model,
                    f"pressure_supply_prop_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_supply, _t=to_P_supply, _dp=delta_p_supply: (
                            _t[t] == _f[t] - _dp[t]
                        ),
                    ),
                )
                # Return: pressure drops from to_node back to from_node
                setattr(
                    model,
                    f"pressure_return_prop_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_return, _t=to_P_return, _dp=delta_p_return: (
                            _f[t] == _t[t] - _dp[t]
                        ),
                    ),
                )
                logger.info(
                    f"  âœ“ {pipe_id}: P_supply[{to_node}] = P_supply[{from_node}] - Î”P_supply; "
                    f"P_return[{from_node}] = P_return[{to_node}] - Î”P_return"
                )
            else:
                p_big_m = float(self._net_cfg.get('pressure_big_m_bar', 30.0))
                # Supply side:
                #   flow_dir=1 -> to = from - dp
                #   flow_dir=0 -> to = from + dp
                setattr(
                    model,
                    f"pressure_supply_fwd_ub_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_supply, _t=to_P_supply, _dp=delta_p_supply, _d=flow_dir, _M=p_big_m: (
                            _t[t] - (_f[t] - _dp[t]) <= _M * (1 - _d[t])
                        ),
                    ),
                )
                setattr(
                    model,
                    f"pressure_supply_fwd_lb_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_supply, _t=to_P_supply, _dp=delta_p_supply, _d=flow_dir, _M=p_big_m: (
                            (_f[t] - _dp[t]) - _t[t] <= _M * (1 - _d[t])
                        ),
                    ),
                )
                setattr(
                    model,
                    f"pressure_supply_rev_ub_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_supply, _t=to_P_supply, _dp=delta_p_supply, _d=flow_dir, _M=p_big_m: (
                            _t[t] - (_f[t] + _dp[t]) <= _M * _d[t]
                        ),
                    ),
                )
                setattr(
                    model,
                    f"pressure_supply_rev_lb_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_supply, _t=to_P_supply, _dp=delta_p_supply, _d=flow_dir, _M=p_big_m: (
                            (_f[t] + _dp[t]) - _t[t] <= _M * _d[t]
                        ),
                    ),
                )
                # Return side:
                #   flow_dir=1 -> from = to - dp
                #   flow_dir=0 -> to = from - dp
                setattr(
                    model,
                    f"pressure_return_fwd_ub_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_return, _t=to_P_return, _dp=delta_p_return, _d=flow_dir, _M=p_big_m: (
                            _f[t] - (_t[t] - _dp[t]) <= _M * (1 - _d[t])
                        ),
                    ),
                )
                setattr(
                    model,
                    f"pressure_return_fwd_lb_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_return, _t=to_P_return, _dp=delta_p_return, _d=flow_dir, _M=p_big_m: (
                            (_t[t] - _dp[t]) - _f[t] <= _M * (1 - _d[t])
                        ),
                    ),
                )
                setattr(
                    model,
                    f"pressure_return_rev_ub_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_return, _t=to_P_return, _dp=delta_p_return, _d=flow_dir, _M=p_big_m: (
                            _t[t] - (_f[t] - _dp[t]) <= _M * _d[t]
                        ),
                    ),
                )
                setattr(
                    model,
                    f"pressure_return_rev_lb_{pipe_id}",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _f=from_P_return, _t=to_P_return, _dp=delta_p_return, _d=flow_dir, _M=p_big_m: (
                            (_f[t] - _dp[t]) - _t[t] <= _M * _d[t]
                        ),
                    ),
                )
                logger.info(
                    f"  âœ“ {pipe_id}: bidirectional pressure propagation with flow_dir selector"
                )

        # Minimum pressure at consumer nodes
        for node_id, node_comp in node_components.items():
            if node_comp['type'] != 'consumer':
                continue
            node_cfg = self.nodes.get(node_id, {})
            min_p = node_cfg.get('pressure', {}).get('min_required_bar')
            if min_p is None:
                continue
            node_P_supply = node_comp['pressure_supply']
            setattr(
                model,
                f"consumer_{node_id}_P_min",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _P=node_P_supply, _mp=min_p: _P[t] >= _mp,
                ),
            )
            logger.info(f"  âœ“ Consumer {node_id}: P_supply >= {min_p} bar")

    def _link_pump_head(
        self, model, time_set, pipe_components: dict, node_components: dict
    ) -> list:
        """Link producer supply/return pressure by a nodal pump head.

        Models one pump head per producer node and aggregates the outgoing pipe
        pump powers into one electricity load per producer.

        Returns a list of aggregated producer pump-power variables for the
        electricity bus.
        """
        logger.info("\nSetting up producer pump head constraints...")
        pump_el_flows = []

        # 2026-07-26 surgical pump-attribution fix (faithful Paper-1 correction).
        # PREVIOUS behaviour attributed ONLY a producer's own immediately-outgoing
        # pipe(s) to its pump, silently dropping every pipe further downstream --
        # which still has a real, nonzero P_pump, friction does not stop after one
        # hop -- from ANY producer's electricity load. For the radial primary
        # network (plant j_1 has a single outgoing pipe j1_to_j2) this discarded
        # 13 of 14 pipes' pumping work from the objective. Each producer now claims
        # every pipe on its nearest (fewest-hop) path from itself, stopping
        # expansion at any OTHER producer node (that station's own pump takes over
        # beyond there). Objective-only change; the per-pipe P_pump aggregation and
        # nodal pump-head handling below are untouched.
        from collections import deque
        adjacency: dict[str, list[tuple[str, dict, str]]] = {}
        for pipe_id, pipe_comp in pipe_components.items():
            from_node = pipe_comp['from_node']
            to_node = pipe_comp['to_node']
            if from_node not in node_components or to_node not in node_components:
                continue
            adjacency.setdefault(from_node, []).append((pipe_id, pipe_comp, to_node))

        producer_node_ids = {
            nid for nid, nc in node_components.items()
            if nc['type'] in ('producer', 'mixed')
        }

        pipe_owner: dict[str, str] = {}
        hop_of: dict[str, int] = {}
        queue: deque[tuple[str, str, int]] = deque()
        for pid in sorted(producer_node_ids):
            hop_of[pid] = 0
            queue.append((pid, pid, 0))
        while queue:
            node_id, owner, hops = queue.popleft()
            for pipe_id, pipe_comp, to_node in adjacency.get(node_id, []):
                pipe_owner.setdefault(pipe_id, owner)
                if to_node in producer_node_ids and to_node != owner:
                    continue  # that station's own pump takes over beyond here
                if to_node not in hop_of or hop_of[to_node] > hops + 1:
                    hop_of[to_node] = hops + 1
                    queue.append((to_node, owner, hops + 1))

        producer_pipes: dict[str, list[tuple[str, dict]]] = {}
        for pipe_id, owner in pipe_owner.items():
            if not pipe_components[pipe_id].get('pump_enabled', False):
                continue
            producer_pipes.setdefault(owner, []).append((pipe_id, pipe_components[pipe_id]))

        for node_id, pipes in producer_pipes.items():
            node_P_supply = node_components[node_id]['pressure_supply']
            node_P_return = node_components[node_id]['pressure_return']
            head_max = self.nodes.get(node_id, {}).get('pressure', {}).get('setpoint_bar', 10.0) * 2.0

            pump_head = pyo.Var(
                time_set,
                domain=pyo.NonNegativeReals,
                bounds=(0.0, max(float(head_max), 1.0)),
            )
            setattr(model, f"producer_{node_id}_pump_head", pump_head)

            setattr(
                model,
                f"producer_{node_id}_pump_head_balance",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _ps=node_P_supply, _pr=node_P_return, _h=pump_head: (
                        _h[t] == _ps[t] - _pr[t]
                    ),
                ),
            )

            agg_pump_power = pyo.Var(time_set, domain=pyo.NonNegativeReals)
            setattr(model, f"producer_{node_id}_P_pump", agg_pump_power)
            setattr(
                model,
                f"producer_{node_id}_pump_power_agg",
                pyo.Constraint(
                    time_set,
                    rule=lambda m, t, _agg=agg_pump_power, _pipes=pipes: (
                        _agg[t] == sum(
                            pipe_comp.get('P_pump')[t]
                            for _, pipe_comp in _pipes
                            if pipe_comp.get('P_pump') is not None
                        )
                    ),
                ),
            )
            pump_el_flows.append(agg_pump_power)

            logger.info(
                f"  âœ“ producer {node_id}: nodal pump head + aggregated pump power "
                f"for {len(pipes)} outgoing pipe(s)"
            )

        # Transfer-station (Uebergabestation) differential-pressure pump work
        # (2026-07-27): the circulation pump must ALSO overcome the differential
        # pressure maintained at each consumer transfer station (control-valve
        # authority, delta_p_min_consumer_bar) -- dissipated at the station valve.
        # This is real, dominant DH pump energy that the friction-only formulation
        # omitted, under-stating pumping ~1-2 orders of magnitude vs real DH. It is
        # LINEAR in the consumer mass flow m_dot_demand, hence exact in the MILP
        # (no PWL -> also immune to the PWL low-flow looseness). Same unit
        # convention as pipe P_pump: MW = dp_bar * 1e5 * m_dot / (rho * eta * 1e6).
        rho_w = 1000.0
        eta_pump = float(self._net_cfg.get('pump_efficiency', 0.75))
        dp_station_bar = float(self._net_cfg.get('delta_p_min_consumer_bar', 0.6))
        n_station = 0
        if dp_station_bar > 0:
            for c_id, c_comp in node_components.items():
                if c_comp.get('type') not in ('consumer', 'mixed'):
                    continue
                mdot = c_comp.get('m_dot_demand')
                if mdot is None:
                    continue
                st_pump = pyo.Var(time_set, domain=pyo.NonNegativeReals)
                setattr(model, f"station_{c_id}_P_pump", st_pump)
                setattr(
                    model,
                    f"station_{c_id}_pump_balance",
                    pyo.Constraint(
                        time_set,
                        rule=lambda m, t, _v=st_pump, _md=mdot, _dp=dp_station_bar,
                        _rho=rho_w, _eta=eta_pump: (
                            _v[t] == _dp * 1e5 * _md[t] / (_rho * _eta * 1e6)
                        ),
                    ),
                )
                pump_el_flows.append(st_pump)
                n_station += 1
            logger.info(
                "  âœ“ transfer-station Î”p pump (%.2f bar) added for %d consumer node(s)",
                dp_station_bar, n_station,
            )

        logger.info(f"  Total aggregated producer pump loads registered: {len(pump_el_flows)}")
        return pump_el_flows

    def _setup_network_losses(self, model, time_set, pipe_components) -> None:
        """Phase 6: Create per-timestep network heat loss variable binding all pipe losses."""
        logger.info("\nCreating per-timestep network heat losses...")

        loss_bounds = self.parameters.get('network_Q_loss_bounds_mw', (0, 50))
        try:
            loss_min, loss_max = loss_bounds
        except Exception:
            loss_min, loss_max = 0, 50

        model.network_Q_loss_per_timestep = pyo.Var(
            time_set,
            domain=pyo.NonNegativeReals,
            bounds=(loss_min, loss_max),
        )

        if pipe_components:
            def network_loss_rule(m, t):
                return m.network_Q_loss_per_timestep[t] == sum(
                    pipe_comp['Q_loss_supply'][t] + pipe_comp['Q_loss_return'][t]
                    for pipe_comp in pipe_components.values()
                )

            model.network_loss_per_timestep_calc = pyo.Constraint(
                time_set, rule=network_loss_rule
            )
            logger.info(f"  âœ“ network_Q_loss_per_timestep = Î£ pipe losses ({len(pipe_components)} pipes)")
        else:
            # Single-node fallback: no pipe losses
            def zero_loss_rule(m, t):
                return m.network_Q_loss_per_timestep[t] == 0

            model.network_loss_per_timestep_calc = pyo.Constraint(
                time_set, rule=zero_loss_rule
            )
            logger.info("  âœ“ network_Q_loss_per_timestep = 0 (single-node topology)")

        if hasattr(model, 'pipe_capex_costs'):
            total_pipe_capex = sum(model.pipe_capex_costs.values())
            logger.info(f"  Total pipe CAPEX (annualized): {total_pipe_capex}")

    @staticmethod
    def _safe_numeric_value(expr, default: float = 0.0) -> float:
        """Safely evaluate a Pyomo expression/variable and return float fallback."""
        try:
            val = pyo.value(expr)
            if val is None:
                return float(default)
            return float(val)
        except Exception:
            return float(default)

    @staticmethod
    def _abs_stats(values: list[float]) -> dict[str, float]:
        """Return max/mean absolute stats for a residual series."""
        if not values:
            return {'max_abs': 0.0, 'mean_abs': 0.0}
        abs_vals = [abs(float(v)) for v in values]
        return {
            'max_abs': max(abs_vals),
            'mean_abs': sum(abs_vals) / len(abs_vals),
        }

    def _compute_physics_diagnostics(self, model, time_set) -> dict[str, Any]:
        """Compute mass/enthalpy/delay residual diagnostics from last attached components."""
        if not self._last_pipe_components or not self._last_node_components:
            return {}

        time_list = list(time_set)
        if not time_list:
            return {}
        time_idx = {t: i for i, t in enumerate(time_list)}

        pipe_components = self._last_pipe_components
        node_components = self._last_node_components

        mass_by_node: dict[str, dict[str, float]] = {}
        supply_mix_by_node: dict[str, dict[str, float]] = {}
        return_mix_by_node: dict[str, dict[str, float]] = {}
        delay_by_pipe: dict[str, dict[str, float | int | str]] = {}

        def _flow_for_mixing(pipe_comp: dict, t) -> float:
            flow_abs = pipe_comp.get('m_dot_abs')
            if flow_abs is not None:
                return self._safe_numeric_value(flow_abs[t], 0.0)
            flow_signed = pipe_comp.get('m_dot')
            if flow_signed is None:
                return 0.0
            return abs(self._safe_numeric_value(flow_signed[t], 0.0))

        def _mix_temp_error(
            node_comp: dict,
            pipe_ids: list[str],
            node_temp_attr: str,
            pipe_temp_attr: str,
        ) -> list[float]:
            node_temp = node_comp.get(node_temp_attr)
            if node_temp is None:
                return []

            errors: list[float] = []
            for t in time_list:
                node_t = self._safe_numeric_value(node_temp[t], 0.0)
                total_m = 0.0
                weighted_temp = 0.0
                for pid in pipe_ids:
                    pipe_comp = pipe_components.get(pid)
                    if not pipe_comp:
                        continue
                    pipe_temp = pipe_comp.get(pipe_temp_attr)
                    if pipe_temp is None:
                        continue
                    m_val = _flow_for_mixing(pipe_comp, t)
                    total_m += m_val
                    weighted_temp += m_val * self._safe_numeric_value(pipe_temp[t], 0.0)

                if total_m > 1e-9:
                    mixed_temp = weighted_temp / total_m
                else:
                    mixed_temp = node_t
                errors.append(node_t - mixed_temp)
            return errors

        for node_id, node_comp in node_components.items():
            incoming = list(node_comp.get('incoming_pipes', []))
            outgoing = list(node_comp.get('outgoing_pipes', []))
            node_type = str(node_comp.get('type', '')).lower()
            demand_var = node_comp.get('m_dot_demand')

            mass_residuals: list[float] = []
            for t in time_list:
                total_in = 0.0
                total_out = 0.0
                for pid in incoming:
                    pcomp = pipe_components.get(pid)
                    if not pcomp or pcomp.get('m_dot') is None:
                        continue
                    total_in += self._safe_numeric_value(pcomp['m_dot'][t], 0.0)
                for pid in outgoing:
                    pcomp = pipe_components.get(pid)
                    if not pcomp or pcomp.get('m_dot') is None:
                        continue
                    total_out += self._safe_numeric_value(pcomp['m_dot'][t], 0.0)

                demand = (
                    self._safe_numeric_value(demand_var[t], 0.0)
                    if demand_var is not None else 0.0
                )
                if node_type in ('consumer', 'mixed'):
                    mass_residuals.append(total_in - total_out - demand)
                else:
                    mass_residuals.append(total_in - total_out)

            mass_stats = self._abs_stats(mass_residuals)
            mass_by_node[node_id] = {
                'max_abs_kg_s': mass_stats['max_abs'],
                'mean_abs_kg_s': mass_stats['mean_abs'],
                'samples': len(mass_residuals),
            }

            supply_pipes = list(node_comp.get('supply_incoming_pipes', incoming))
            return_pipes = list(node_comp.get('return_incoming_pipes', outgoing))

            supply_errors = _mix_temp_error(
                node_comp=node_comp,
                pipe_ids=supply_pipes,
                node_temp_attr='T_supply',
                pipe_temp_attr='T_supply_out',
            )
            return_errors = _mix_temp_error(
                node_comp=node_comp,
                pipe_ids=return_pipes,
                node_temp_attr='T_return',
                pipe_temp_attr='T_return_out',
            )

            supply_stats = self._abs_stats(supply_errors)
            return_stats = self._abs_stats(return_errors)
            supply_mix_by_node[node_id] = {
                'max_abs_c': supply_stats['max_abs'],
                'mean_abs_c': supply_stats['mean_abs'],
                'samples': len(supply_errors),
            }
            return_mix_by_node[node_id] = {
                'max_abs_c': return_stats['max_abs'],
                'mean_abs_c': return_stats['mean_abs'],
                'samples': len(return_errors),
            }

        for pipe_id, pipe_comp in pipe_components.items():
            q_consumer = pipe_comp.get('Q_consumer')
            q_delivered = pipe_comp.get('Q_delivered')
            if q_consumer is None or q_delivered is None:
                continue

            tau_steps = [int(tau) for tau in (pipe_comp.get('tau_steps') or [])]
            warmup_mode = str(pipe_comp.get('delay_warmup_mode', 'cold_zero')).lower()
            prefix = pipe_comp.get('prefix', pipe_id.upper().replace('-', '_'))
            z_delay = getattr(model, f'{prefix}_z_delay', None)
            q_init = float(self.pipes.get(pipe_id, {}).get('Q_pipe_initial_mw', 0.0) or 0.0)

            residuals: list[float] = []
            skipped_warmup = 0

            for t in time_list:
                i = time_idx[t]
                q_c = self._safe_numeric_value(q_consumer[t], 0.0)

                if not tau_steps or z_delay is None:
                    q_src = self._safe_numeric_value(q_delivered[t], 0.0)
                    residuals.append(q_c - q_src)
                    continue

                z_values = [self._safe_numeric_value(z_delay[n, t], 0.0) for n in range(len(tau_steps))]
                active_bucket = max(range(len(z_values)), key=lambda n: z_values[n]) if z_values else 0
                if warmup_mode == 'skip' and i < tau_steps[active_bucket]:
                    skipped_warmup += 1
                    continue

                predicted = 0.0
                for n, tau in enumerate(tau_steps):
                    z_val = z_values[n]
                    if i < tau:
                        if warmup_mode == 'hold_first':
                            source_q = self._safe_numeric_value(q_delivered[time_list[0]], 0.0)
                        elif warmup_mode == 'cold_zero':
                            source_q = q_init
                        else:
                            source_q = 0.0
                    else:
                        source_q = self._safe_numeric_value(q_delivered[time_list[i - tau]], 0.0)
                    predicted += z_val * source_q
                residuals.append(q_c - predicted)

            delay_stats = self._abs_stats(residuals)
            delay_by_pipe[pipe_id] = {
                'mode': 'delayed' if tau_steps and z_delay is not None else 'direct',
                'warmup_mode': warmup_mode,
                'max_abs_mw': delay_stats['max_abs'],
                'mean_abs_mw': delay_stats['mean_abs'],
                'samples': len(residuals),
                'skipped_warmup_samples': skipped_warmup,
            }

        mass_global = max(
            (item['max_abs_kg_s'] for item in mass_by_node.values()),
            default=0.0,
        )
        supply_global = max(
            (item['max_abs_c'] for item in supply_mix_by_node.values()),
            default=0.0,
        )
        return_global = max(
            (item['max_abs_c'] for item in return_mix_by_node.values()),
            default=0.0,
        )
        delay_global = max(
            (item['max_abs_mw'] for item in delay_by_pipe.values()),
            default=0.0,
        )

        return {
            'mass_balance': {
                'global_max_abs_kg_s': mass_global,
                'by_node': mass_by_node,
            },
            'enthalpy_mixing': {
                'supply_global_max_abs_c': supply_global,
                'return_global_max_abs_c': return_global,
                'supply_by_node': supply_mix_by_node,
                'return_by_node': return_mix_by_node,
            },
            'delay_consistency': {
                'global_max_abs_mw': delay_global,
                'by_pipe': delay_by_pipe,
            },
        }

    # â”€â”€ Results extraction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def get_results(self, model, time_set) -> dict[str, Any]:
        """Extract network results from solved model."""
        if not self.network_enabled:
            return {}

        logger.info("Extracting network results...")

        results = {
            'metadata': {
                'network_name': self.topology.get('metadata', {}).get('name', 'Unknown'),
                'total_nodes': len(self.nodes),
                'total_pipes': len(self.pipes),
            },
            'pipes': {},
            'nodes': {},
            'diagnostics': {},
            'summary': {},
        }

        for pipe_id, pipe_config in self.pipes.items():
            results['pipes'][pipe_id] = PipePairBlock.get_results(model, time_set, pipe_config)

        for node_id, node_config in self.nodes.items():
            results['nodes'][node_id] = ThermalNodeBlock.get_results(model, time_set, node_config)

        dt_h = getattr(model, 'dt_h', 1.0)

        total_heat_delivered = sum(
            r['total_heat_delivered_mwh'] for r in results['pipes'].values()
        )
        total_heat_loss = sum(
            r['total_heat_loss_mwh'] for r in results['pipes'].values()
        )

        if total_heat_delivered <= 0 and hasattr(model, 'network_Q_loss_per_timestep'):
            total_heat_loss = sum(
                pyo.value(model.network_Q_loss_per_timestep[t]) * dt_h / 1000
                for t in time_set
            )
            if hasattr(model, 'heatd'):
                total_heat_delivered = sum(
                    pyo.value(model.heatd[t]) * dt_h / 1000 for t in time_set
                )

        loss_percentage = (
            (total_heat_loss / total_heat_delivered * 100)
            if total_heat_delivered > 0 else 0
        )

        max_velocity = max(
            (r.get('max_velocity_m_s', 0) for r in results['pipes'].values()),
            default=0,
        )
        total_pressure_drop = sum(
            r.get('max_delta_p_total_bar', 0) for r in results['pipes'].values()
        )
        avg_total_flow = (
            sum(r.get('avg_flow_kg_s', 0) for r in results['pipes'].values())
            / max(len(results['pipes']), 1)
        )

        pump_efficiency = 0.75
        density_water = 1000  # kg/mÂ³
        pump_power_kw = (
            avg_total_flow * total_pressure_drop * 100000
        ) / (density_water * pump_efficiency * 1000) if total_pressure_drop > 0 else 0

        n_timesteps = len(list(time_set))
        operating_hours = n_timesteps * dt_h
        pump_energy_mwh = pump_power_kw * operating_hours / 1000

        diagnostics = self._compute_physics_diagnostics(model, time_set)
        if diagnostics:
            results['diagnostics'] = diagnostics

        results['summary'] = {
            'total_heat_delivered_mwh': total_heat_delivered,
            'total_heat_loss_mwh': total_heat_loss,
            'loss_percentage': loss_percentage,
            'total_pipe_length_m': sum(p['length_m'] for p in self.pipes.values()),
            'max_velocity_m_s': max_velocity,
            'total_pressure_drop_bar': total_pressure_drop,
            'pump_power_kw': pump_power_kw,
            'pump_energy_mwh': pump_energy_mwh,
            'pump_efficiency': pump_efficiency,
            'mass_balance_max_abs_kg_s': diagnostics.get('mass_balance', {}).get('global_max_abs_kg_s', 0.0) if diagnostics else 0.0,
            'supply_mixing_max_abs_c': diagnostics.get('enthalpy_mixing', {}).get('supply_global_max_abs_c', 0.0) if diagnostics else 0.0,
            'return_mixing_max_abs_c': diagnostics.get('enthalpy_mixing', {}).get('return_global_max_abs_c', 0.0) if diagnostics else 0.0,
            'delay_consistency_max_abs_mw': diagnostics.get('delay_consistency', {}).get('global_max_abs_mw', 0.0) if diagnostics else 0.0,
        }

        logger.info(f"  Total heat delivered: {total_heat_delivered:.1f} MWh")
        logger.info(f"  Total heat losses: {total_heat_loss:.1f} MWh ({loss_percentage:.2f}%)")
        logger.info(f"  Max velocity: {max_velocity:.2f} m/s")
        logger.info(f"  Total pressure drop: {total_pressure_drop:.2f} bar")
        logger.info(f"  Pump power: {pump_power_kw:.1f} kW ({pump_energy_mwh:.1f} MWh/period)")

        return results

    def export_for_dashboard(self, results: dict[str, Any]) -> dict[str, Any]:
        """Format network results for dashboard visualization."""
        dashboard_data = {
            'metadata': results.get('metadata', {}),
            'network_topology': {'nodes': [], 'pipes': []},
            'time_series': {'pipe_flows': {}, 'temperatures': {}, 'heat_losses': {}},
            'investment_results': {
                'pipe_upgrades': [],
                'total_investment_eur': 0,
                'annual_savings_eur': 0,
            },
            'summary': results.get('summary', {}),
        }

        for node_id, node_config in self.nodes.items():
            node_result = results['nodes'].get(node_id, {})
            dashboard_data['network_topology']['nodes'].append({
                'id': node_id,
                'name': node_config.get('name', node_id),
                'type': node_config.get('type'),
                'coordinates': node_config.get('coordinates', {}),
                'elevation_m': node_config.get('elevation_nn_m'),
                'avg_supply_temp_c': node_result.get('avg_supply_temp_c'),
                'avg_return_temp_c': node_result.get('avg_return_temp_c'),
                'total_demand_mwh': node_result.get('total_demand_mwh', 0),
                'network': node_config.get('network'),
            })

        for pipe_id, pipe_result in results['pipes'].items():
            pipe_config = self.pipes[pipe_id]
            dashboard_data['network_topology']['pipes'].append({
                'id': pipe_id,
                'from': pipe_result['from_node'],
                'to': pipe_result['to_node'],
                'length_m': pipe_result['length_m'],
                'diameter_current_mm': pipe_result['current_diameter_mm'],
                'diameter_optimized_mm': pipe_result['selected_diameter_mm'],
                'upgrade_recommended': pipe_result['upgrade_recommended'],
                'total_heat_loss_mwh': pipe_result['total_heat_loss_mwh'],
                'loss_percentage': pipe_result['loss_percentage'],
                'avg_flow_kg_s': pipe_result['avg_flow_kg_s'],
            })
            dashboard_data['time_series']['pipe_flows'][pipe_id] = pipe_result['flow_kg_s']
            dashboard_data['time_series']['heat_losses'][pipe_id] = pipe_result['Q_loss_supply_kw']

        for node_id, node_result in results['nodes'].items():
            dashboard_data['time_series']['temperatures'][f'{node_id}_supply'] = node_result['T_supply_c']
            dashboard_data['time_series']['temperatures'][f'{node_id}_return'] = node_result['T_return_c']

        for pipe_id, pipe_result in results['pipes'].items():
            if pipe_result.get('upgrade_recommended'):
                dashboard_data['investment_results']['pipe_upgrades'].append({
                    'pipe_id': pipe_id,
                    'current_diameter': pipe_result['current_diameter_mm'],
                    'recommended_diameter': pipe_result['selected_diameter_mm'],
                    'action': 'upgrade_diameter',
                    'cost_eur': 0,
                })

        return dashboard_data

    def validate_hydraulics_post_optimization(
        self, heat_series: list[float], dt_h: float = 1.0
    ) -> dict[str, Any]:
        """Post-optimization validation of hydraulic constraints."""
        if not self.network_enabled:
            return {'is_valid': True, 'violations': [], 'max_utilization': {}, 'recommendations': []}

        logger.info("=" * 60)
        logger.info("POST-OPTIMIZATION HYDRAULIC VALIDATION")
        logger.info("=" * 60)

        network_config = self.topology.get('network_parameters', {})
        parameters = self.parameters or {}

        supply_temp = network_config.get(
            'supply_temp_nominal_c', parameters.get('supply_temp_nominal_c', 120.0)
        )
        return_temp = network_config.get(
            'return_temp_nominal_c', parameters.get('return_temp_nominal_c', 55.0)
        )
        delta_t = supply_temp - return_temp

        cp_water = network_config.get(
            'cp_water_kj_per_kg_k', parameters.get('cp_water_kj_per_kg_k', 4.186)
        )
        rho_water = network_config.get(
            'rho_water_kg_per_m3', parameters.get('rho_water_kg_per_m3', 983.0)
        )
        max_velocity_m_s = network_config.get(
            'max_velocity_m_s', parameters.get('max_velocity_m_s', 2.5)
        )
        default_pipe_fraction = parameters.get('default_pipe_demand_fraction', 0.2)

        violations = []
        max_utilization = {}
        recommendations = []

        for pipe_id, pipe_config in self.pipes.items():
            diameter_m = pipe_config.get('diameter_mm', 200) / 1000.0
            max_flow_m3_s = (3.14159 * (diameter_m / 2) ** 2) * max_velocity_m_s
            max_flow_kg_s = max_flow_m3_s * rho_water

            demand_fraction = pipe_config.get('demand_fraction', default_pipe_fraction)
            pipe_violations = []
            pipe_max_util = 0.0

            for t, heat_mw in enumerate(heat_series):
                total_flow_kg_s = (
                    heat_mw * 1000 / (cp_water * delta_t)
                    if cp_water > 0 and delta_t > 0 else 0.0
                )
                pipe_flow_kg_s = total_flow_kg_s * demand_fraction
                utilization = pipe_flow_kg_s / max_flow_kg_s if max_flow_kg_s > 0 else 0
                pipe_max_util = max(pipe_max_util, utilization)

                if utilization > 1.0:
                    pipe_violations.append({
                        'timestep': t,
                        'heat_mw': heat_mw,
                        'required_flow_kg_s': pipe_flow_kg_s,
                        'max_flow_kg_s': max_flow_kg_s,
                        'utilization': utilization,
                        'excess_percent': (utilization - 1.0) * 100,
                    })

            max_utilization[pipe_id] = {
                'max_utilization': pipe_max_util,
                'diameter_mm': pipe_config.get('diameter_mm', 200),
                'max_flow_kg_s': max_flow_kg_s,
                'is_overloaded': pipe_max_util > 1.0,
            }

            if pipe_violations:
                violations.extend([{'pipe_id': pipe_id, **v} for v in pipe_violations])
                recommended_diameter = self._calculate_required_diameter(
                    max(v['required_flow_kg_s'] for v in pipe_violations),
                    max_velocity_m_s,
                    rho_water,
                )
                recommendations.append({
                    'pipe_id': pipe_id,
                    'current_diameter_mm': pipe_config.get('diameter_mm', 200),
                    'recommended_diameter_mm': recommended_diameter,
                    'max_overload_percent': (pipe_max_util - 1.0) * 100,
                    'violation_hours': len(pipe_violations),
                })

        overloaded_pipes = sum(1 for m in max_utilization.values() if m['is_overloaded'])
        logger.info(f"  Analyzed {len(self.pipes)} pipes")
        logger.info(f"  Overloaded pipes: {overloaded_pipes}")

        if overloaded_pipes > 0:
            logger.warning(f"  âš  {overloaded_pipes} pipes exceed hydraulic limits!")
            for rec in recommendations:
                logger.warning(
                    f"    - {rec['pipe_id']}: {rec['current_diameter_mm']}mm â†’ "
                    f"{rec['recommended_diameter_mm']}mm "
                    f"(overload: {rec['max_overload_percent']:.1f}%)"
                )
        else:
            logger.info("  âœ“ All pipes within hydraulic limits")

        return {
            'is_valid': len(violations) == 0,
            'violations': violations,
            'max_utilization': max_utilization,
            'recommendations': recommendations,
            'summary': {
                'total_pipes': len(self.pipes),
                'overloaded_pipes': overloaded_pipes,
                'total_violation_hours': len(violations),
                'network_delta_t_k': delta_t,
                'max_velocity_m_s': max_velocity_m_s,
            },
        }

    def _calculate_required_diameter(
        self, required_flow_kg_s: float, max_velocity_m_s: float, rho_water: float
    ) -> int:
        """Calculate minimum diameter (mm) for given flow and max velocity."""
        import math
        area_m2 = required_flow_kg_s / (rho_water * max_velocity_m_s)
        diameter_m = 2 * math.sqrt(area_m2 / 3.14159)
        diameter_mm = diameter_m * 1000

        standard_sizes = [50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800]
        for size in standard_sizes:
            if size >= diameter_mm:
                return size
        return int(math.ceil(diameter_mm / 50) * 50)
