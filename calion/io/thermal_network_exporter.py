"""
Thermal Network Results Exporter
================================

Comprehensive export of thermal network simulation results including:
- Node-level results (temperatures, pressures, demands)
- Pipe-level results (flows, pressure drops, heat losses)
- Network-wide summaries
- Gurobi/solver solution files
- Physics-based calculations (PWL pressure, temperature drops)

Author: CALION Development Team
"""

import json
import logging
import os
from datetime import datetime
from typing import Any

import pandas as pd

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

logger = logging.getLogger(__name__)


def _val(obj):
    """Read a Pyomo Var/Param value without logging errors for uninitialized vars."""
    return pyo.value(obj, exception=False) if HAVE_PYOMO else None


def export_solver_solution(
    model,
    output_dir: str,
    filename: str = "gurobi_solution",
) -> dict[str, str]:
    """
    Export solver solution files (LP, SOL, MPS).

    Parameters
    ----------
    model : pyomo.ConcreteModel
        Solved Pyomo model
    output_dir : str
        Output directory
    filename : str
        Base filename without extension

    Returns
    -------
    Dict[str, str]
        Dictionary of exported file paths
    """
    files = {}
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Export LP file (problem formulation)
        lp_path = os.path.join(output_dir, f"{filename}.lp")
        model.write(lp_path, io_options={'symbolic_solver_labels': True})
        files['lp_file'] = lp_path
        logger.info(f"  Exported LP file: {lp_path}")
    except Exception as e:
        logger.warning(f"Could not export LP file: {e}")

    try:
        # Export SOL file (solution values)
        sol_path = os.path.join(output_dir, f"{filename}.sol")

        # Get objective value (could be obj, OBJ, or other names)
        obj_val = "N/A"
        for obj_name in ['obj', 'OBJ', 'objective']:
            if hasattr(model, obj_name):
                obj_val = pyo.value(getattr(model, obj_name))
                break

        # Write solution manually since Pyomo doesn't have direct .sol export
        with open(sol_path, 'w', encoding="utf-8") as f:
            f.write("# Gurobi Solution Export\n")
            f.write(f"# Generated: {datetime.now().isoformat()}\n")
            f.write(f"# Objective Value: {obj_val}\n\n")

            # Write all variable values
            for var in model.component_objects(pyo.Var, active=True):
                var_name = var.name
                for idx in var:
                    val = _val(var[idx])
                    if val is not None and abs(val) > 1e-9:
                        f.write(f"{var_name}[{idx}] {val}\n")

        files['sol_file'] = sol_path
        logger.info(f"  Exported SOL file: {sol_path}")
    except Exception as e:
        logger.warning(f"Could not export SOL file: {e}")
        import traceback
        logger.debug(f"SOL export traceback: {traceback.format_exc()}")

    try:
        # Export MPS file (standard format)
        mps_path = os.path.join(output_dir, f"{filename}.mps")
        model.write(mps_path)
        files['mps_file'] = mps_path
        logger.info(f"  Exported MPS file: {mps_path}")
    except Exception as e:
        logger.warning(f"Could not export MPS file: {e}")
        import traceback
        logger.debug(f"MPS export traceback: {traceback.format_exc()}")

    return files


def export_thermal_network_results(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float = 1.0,
) -> dict[str, str]:
    """
    Export comprehensive thermal network results.

    Parameters
    ----------
    model : pyomo.ConcreteModel
        Solved Pyomo model
    network_manager : NetworkManager
        Network manager instance
    time_set : Set
        Pyomo time set
    output_dir : str
        Output directory
    dt_h : float
        Timestep duration in hours

    Returns
    -------
    Dict[str, str]
        Dictionary of exported file paths
    """
    files = {}

    network_dir = os.path.join(output_dir, "thermal_network")
    os.makedirs(network_dir, exist_ok=True)

    logger.info("=" * 60)
    logger.info("EXPORTING THERMAL NETWORK RESULTS")
    logger.info("=" * 60)

    # ========================================
    # 1. NODE RESULTS
    # ========================================
    node_files = _export_node_results(model, network_manager, time_set, network_dir, dt_h)
    files.update(node_files)

    # ========================================
    # 2. PIPE RESULTS
    # ========================================
    pipe_files = _export_pipe_results(model, network_manager, time_set, network_dir, dt_h)
    files.update(pipe_files)

    # ========================================
    # 3. NETWORK SUMMARY
    # ========================================
    summary_files = _export_network_summary(model, network_manager, time_set, network_dir, dt_h)
    files.update(summary_files)

    # ========================================
    # 4. PHYSICS CALCULATIONS
    # ========================================
    physics_files = _export_physics_results(model, network_manager, time_set, network_dir, dt_h)
    files.update(physics_files)

    # ========================================
    # 5. STORAGE RESULTS (if available)
    # ========================================
    storage_files = _export_storage_results(model, time_set, network_dir, dt_h)
    files.update(storage_files)

    logger.info(f"\nExported {len(files)} thermal network files to {network_dir}")

    return files


def _export_node_results(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float,
) -> dict[str, str]:
    """Export node-level results."""
    files = {}

    nodes_dir = os.path.join(output_dir, "nodes")
    os.makedirs(nodes_dir, exist_ok=True)

    logger.info("\n[NODES] Exporting node results...")

    # Collect all node data
    all_nodes_data = []
    node_timeseries = {}

    for node_id, node_config in network_manager.nodes.items():
        node_prefix = node_id.upper().replace('-', '_')
        node_type = node_config.get('type', 'unknown')

        node_summary = {
            'node_id': node_id,
            'type': node_type,
            'name': node_config.get('name', node_id),
            'elevation_m': node_config.get('elevation_m', 0),
        }

        # Extract temperature variables
        T_supply_var = getattr(model, f'{node_prefix}_T_supply', None)
        T_return_var = getattr(model, f'{node_prefix}_T_return', None)

        if T_supply_var is not None:
            T_supply_vals = [_val(T_supply_var[t]) for t in time_set]
            finite = [v for v in T_supply_vals if v is not None]
            if finite:
                node_summary['T_supply_avg_c'] = sum(finite) / len(finite)
                node_summary['T_supply_min_c'] = min(finite)
                node_summary['T_supply_max_c'] = max(finite)
                node_timeseries[f'{node_id}_T_supply'] = T_supply_vals

        if T_return_var is not None:
            T_return_vals = [_val(T_return_var[t]) for t in time_set]
            finite = [v for v in T_return_vals if v is not None]
            if finite:
                node_summary['T_return_avg_c'] = sum(finite) / len(finite)
                node_summary['T_return_min_c'] = min(finite)
                node_summary['T_return_max_c'] = max(finite)
                node_timeseries[f'{node_id}_T_return'] = T_return_vals

        # Extract demand for consumer nodes
        if node_type == 'consumer':
            Q_demand_var = getattr(model, f'{node_prefix}_Q_demand', None)
            if Q_demand_var is not None:
                try:
                    Q_vals = [pyo.value(Q_demand_var[t]) for t in time_set]
                    node_summary['Q_demand_total_mwh'] = sum(Q_vals) * dt_h
                    node_summary['Q_demand_peak_mw'] = max(Q_vals)
                    node_timeseries[f'{node_id}_Q_demand'] = Q_vals
                except Exception as e:
                    logger.debug(f"Could not export Q_demand for {node_id}: {e}")

        # Extract pressure if available.
        # BUGFIX (2026-07-19): this looked for "{node_prefix}_P", but the
        # actual Pyomo attribute (calion/models/blocks/thermal_node.py:279)
        # is named "{prefix}_pressure_supply" -- the lookup never matched
        # anything, on either network, for the whole campaign, so P_avg_bar
        # and every "{node}_P" timeseries column were always empty despite
        # pressure being modeled and solved. Also export pressure_return for
        # completeness (previously not attempted at all).
        P_var = getattr(model, f'{node_prefix}_pressure_supply', None)
        if P_var is not None:
            try:
                P_vals = [pyo.value(P_var[t]) for t in time_set]
                node_summary['P_avg_bar'] = sum(P_vals) / len(P_vals)
                node_timeseries[f'{node_id}_P'] = P_vals
            except Exception as e:
                logger.debug(f"Could not export pressure for {node_id}: {e}")

        P_ret_var = getattr(model, f'{node_prefix}_pressure_return', None)
        if P_ret_var is not None:
            try:
                P_ret_vals = [pyo.value(P_ret_var[t]) for t in time_set]
                node_summary['P_return_avg_bar'] = sum(P_ret_vals) / len(P_ret_vals)
                node_timeseries[f'{node_id}_P_return'] = P_ret_vals
            except Exception as e:
                logger.debug(f"Could not export return pressure for {node_id}: {e}")

        all_nodes_data.append(node_summary)
        logger.info(f"  ✓ {node_id} ({node_type})")

    # Save node summary JSON
    summary_path = os.path.join(nodes_dir, "nodes_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(all_nodes_data, f, indent=2, default=str)
    files['nodes_summary'] = summary_path

    # Save node timeseries CSV
    if node_timeseries:
        ts_df = pd.DataFrame(node_timeseries, index=list(time_set))
        ts_path = os.path.join(nodes_dir, "nodes_timeseries.csv")
        ts_df.to_csv(ts_path, sep=';')
        files['nodes_timeseries'] = ts_path

    return files


def _export_pipe_results(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float,
) -> dict[str, str]:
    """Export pipe-level results with pressure drops and heat losses."""
    files = {}

    pipes_dir = os.path.join(output_dir, "pipes")
    os.makedirs(pipes_dir, exist_ok=True)

    logger.info("\n[PIPES] Exporting pipe results...")

    all_pipes_data = []
    pipe_timeseries = {}

    for pipe_id, pipe_config in network_manager.pipes.items():
        pipe_prefix = pipe_id.upper().replace('-', '_')

        pipe_summary = {
            'pipe_id': pipe_id,
            'from_node': pipe_config.get('from_node'),
            'to_node': pipe_config.get('to_node'),
            'length_m': pipe_config.get('length_m', 0),
            'diameter_mm': pipe_config.get('diameter_mm', 0),
            'u_value_w_per_m_k': pipe_config.get('u_value_w_per_m_k', 0),
        }

        # Mass flow rate
        m_dot_var = getattr(model, f'{pipe_prefix}_m_dot', None)
        if m_dot_var is not None:
            try:
                m_dot_vals = [pyo.value(m_dot_var[t]) for t in time_set]
                pipe_summary['m_dot_avg_kg_s'] = sum(m_dot_vals) / len(m_dot_vals)
                pipe_summary['m_dot_max_kg_s'] = max(m_dot_vals)
                pipe_timeseries[f'{pipe_id}_m_dot'] = m_dot_vals
            except Exception as e:
                logger.debug(f"Could not export m_dot for {pipe_id}: {e}")

        # Velocity
        velocity_var = getattr(model, f'{pipe_prefix}_velocity', None)
        if velocity_var is not None:
            try:
                v_vals = [pyo.value(velocity_var[t]) for t in time_set]
                pipe_summary['velocity_avg_m_s'] = sum(v_vals) / len(v_vals)
                pipe_summary['velocity_max_m_s'] = max(v_vals)
                pipe_timeseries[f'{pipe_id}_velocity'] = v_vals
            except Exception as e:
                logger.debug(f"Could not export velocity for {pipe_id}: {e}")

        # Pressure drops
        delta_p_supply = getattr(model, f'{pipe_prefix}_delta_p_supply', None)
        delta_p_return = getattr(model, f'{pipe_prefix}_delta_p_return', None)
        delta_p_total = getattr(model, f'{pipe_prefix}_delta_p_total', None)

        if delta_p_supply is not None:
            try:
                dp_s_vals = [pyo.value(delta_p_supply[t]) for t in time_set]
                pipe_summary['delta_p_supply_avg_bar'] = sum(dp_s_vals) / len(dp_s_vals)
                pipe_summary['delta_p_supply_max_bar'] = max(dp_s_vals)
                pipe_timeseries[f'{pipe_id}_delta_p_supply'] = dp_s_vals
            except Exception as e:
                logger.debug(f"Could not export delta_p_supply for {pipe_id}: {e}")

        if delta_p_return is not None:
            try:
                dp_r_vals = [pyo.value(delta_p_return[t]) for t in time_set]
                pipe_summary['delta_p_return_avg_bar'] = sum(dp_r_vals) / len(dp_r_vals)
                pipe_summary['delta_p_return_max_bar'] = max(dp_r_vals)
                pipe_timeseries[f'{pipe_id}_delta_p_return'] = dp_r_vals
            except Exception as e:
                logger.debug(f"Could not export delta_p_return for {pipe_id}: {e}")

        if delta_p_total is not None:
            try:
                dp_t_vals = [pyo.value(delta_p_total[t]) for t in time_set]
                pipe_summary['delta_p_total_avg_bar'] = sum(dp_t_vals) / len(dp_t_vals)
                pipe_summary['delta_p_total_max_bar'] = max(dp_t_vals)
                pipe_timeseries[f'{pipe_id}_delta_p_total'] = dp_t_vals
            except Exception as e:
                logger.debug(f"Could not export delta_p_total for {pipe_id}: {e}")

        # Temperature variables
        for temp_var in ['T_supply_in', 'T_supply_out', 'T_return_in', 'T_return_out']:
            var = getattr(model, f'{pipe_prefix}_{temp_var}', None)
            if var is not None:
                try:
                    vals = [pyo.value(var[t]) for t in time_set]
                    pipe_summary[f'{temp_var}_avg_c'] = sum(vals) / len(vals)
                    pipe_timeseries[f'{pipe_id}_{temp_var}'] = vals
                except Exception as e:
                    logger.debug(f"Could not export {temp_var} for {pipe_id}: {e}")

        # Heat losses and delay-aware consumer delivery
        for heat_var, summary_key in [
            ('Q_loss_supply', 'Q_loss_supply_total_mwh'),
            ('Q_loss_return', 'Q_loss_return_total_mwh'),
            ('Q_consumer',    'Q_consumer_total_mwh'),
        ]:
            var = getattr(model, f'{pipe_prefix}_{heat_var}', None)
            if var is not None:
                try:
                    vals = [pyo.value(var[t]) for t in time_set]
                    pipe_summary[summary_key] = sum(vals) * dt_h
                    pipe_timeseries[f'{pipe_id}_{heat_var}'] = vals
                except Exception as e:
                    logger.debug(f"Could not export {heat_var} for {pipe_id}: {e}")

        # PWL segment info (if available)
        pwl_segment = getattr(model, f'{pipe_prefix}_pwl_segment', None)
        if pwl_segment is not None:
            pipe_summary['uses_pwl_pressure_drop'] = True
            segment_usage = {0: 0, 1: 0, 2: 0}
            for t in time_set:
                for s in range(3):
                    try:
                        if pyo.value(pwl_segment[t, s]) > 0.5:
                            segment_usage[s] += 1
                    except Exception:
                        pass
            pipe_summary['pwl_segment_usage'] = segment_usage
        else:
            pipe_summary['uses_pwl_pressure_drop'] = False

        # Pressure parameters (stored during model build)
        pressure_params = getattr(model, f'{pipe_prefix}_pressure_params', None)
        if pressure_params:
            pipe_summary['pressure_params'] = pressure_params

        all_pipes_data.append(pipe_summary)
        logger.info(f"  ✓ {pipe_id}: {pipe_config.get('from_node')} → {pipe_config.get('to_node')}")

    # Save pipe summary JSON
    summary_path = os.path.join(pipes_dir, "pipes_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(all_pipes_data, f, indent=2, default=str)
    files['pipes_summary'] = summary_path

    # Save pipe timeseries CSV
    if pipe_timeseries:
        ts_df = pd.DataFrame(pipe_timeseries, index=list(time_set))
        ts_path = os.path.join(pipes_dir, "pipes_timeseries.csv")
        ts_df.to_csv(ts_path, sep=';')
        files['pipes_timeseries'] = ts_path

    return files


def _export_network_summary(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float,
) -> dict[str, str]:
    """Export network-wide summary statistics."""
    files = {}

    logger.info("\n[SUMMARY] Exporting network summary...")

    summary = {
        'metadata': {
            'export_timestamp': datetime.now().isoformat(),
            'total_timesteps': len(list(time_set)),
            'dt_hours': dt_h,
            'total_hours': len(list(time_set)) * dt_h,
        },
        'topology': {
            'total_nodes': len(network_manager.nodes),
            'total_pipes': len(network_manager.pipes),
            'node_types': {},
        },
        'parameters': network_manager.parameters,
        'energy': {},
        'hydraulics': {},
    }

    # Count node types
    for _node_id, node_cfg in network_manager.nodes.items():
        node_type = node_cfg.get('type', 'unknown')
        summary['topology']['node_types'][node_type] = \
            summary['topology']['node_types'].get(node_type, 0) + 1

    # Network heat loss
    if hasattr(model, 'network_Q_loss_per_timestep'):
        try:
            loss_vals = [pyo.value(model.network_Q_loss_per_timestep[t]) for t in time_set]
            summary['energy']['total_network_loss_mwh'] = sum(loss_vals) * dt_h
            summary['energy']['avg_network_loss_mw'] = sum(loss_vals) / len(loss_vals)
            summary['energy']['max_network_loss_mw'] = max(loss_vals)
        except Exception as e:
            logger.debug(f"Could not export network_Q_loss_per_timestep: {e}")

    # Brownfield specific data
    if hasattr(model, '_brownfield_total_loss_mw'):
        summary['energy']['brownfield_reference_loss_mw'] = model._brownfield_total_loss_mw

    if hasattr(model, '_brownfield_pipe_losses'):
        summary['energy']['brownfield_pipe_losses'] = model._brownfield_pipe_losses

    if hasattr(model, '_brownfield_delta_T'):
        summary['parameters']['brownfield_delta_T_k'] = model._brownfield_delta_T

    # Total pipe length
    total_length = sum(p.get('length_m', 0) for p in network_manager.pipes.values())
    summary['topology']['total_pipe_length_m'] = total_length
    summary['topology']['total_pipe_length_km'] = total_length / 1000

    # Save summary
    summary_path = os.path.join(output_dir, "network_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, default=str)
    files['network_summary'] = summary_path

    logger.info("  ✓ Network summary saved")

    return files


def _export_physics_results(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float,
) -> dict[str, str]:
    """Export physics calculation results (PWL, temperature drops, etc.)."""
    files = {}

    physics_dir = os.path.join(output_dir, "physics")
    os.makedirs(physics_dir, exist_ok=True)

    logger.info("\n[PHYSICS] Exporting physics calculations...")

    physics_data = {
        'pressure_drop_model': {},
        'temperature_drop_model': {},
        'heat_loss_model': {},
    }

    # Check what physics models are used
    has_pwl = False
    has_physics_temp = False

    for pipe_id in network_manager.pipes:
        pipe_prefix = pipe_id.upper().replace('-', '_')

        if hasattr(model, f'{pipe_prefix}_pwl_segment'):
            has_pwl = True
            physics_data['pressure_drop_model']['type'] = 'piecewise_linear_3_segment'
            physics_data['pressure_drop_model']['description'] = \
                'Darcy-Weisbach approximated with 3-segment PWL function'
            break

    # Get brownfield parameters if available
    if hasattr(model, '_brownfield_ground_temp'):
        physics_data['temperature_drop_model']['ground_temp_c'] = model._brownfield_ground_temp

    if network_manager.parameters.get('use_physics_temp_drop', False):
        has_physics_temp = True
        physics_data['temperature_drop_model']['type'] = 'physics_based'
        physics_data['temperature_drop_model']['description'] = \
            'ΔT = U × L × ΔT_log / (ṁ × cp) based on heat loss equation'
    else:
        physics_data['temperature_drop_model']['type'] = 'constant'
        physics_data['temperature_drop_model']['default_drop_c'] = \
            network_manager.parameters.get('brownfield_temp_drop_per_pipe_c', 1.0)

    # Heat loss model info
    if network_manager.parameters.get('brownfield_loss_model') == 'demand_proportional':
        physics_data['heat_loss_model']['type'] = 'demand_proportional'
    else:
        physics_data['heat_loss_model']['type'] = 'constant'

    physics_data['pressure_drop_model']['uses_pwl'] = has_pwl
    physics_data['temperature_drop_model']['uses_physics'] = has_physics_temp

    # Save physics info
    physics_path = os.path.join(physics_dir, "physics_models.json")
    with open(physics_path, 'w', encoding='utf-8') as f:
        json.dump(physics_data, f, indent=2, default=str)
    files['physics_models'] = physics_path

    logger.info("  ✓ Physics models info saved")
    logger.info(f"    - PWL pressure drop: {has_pwl}")
    logger.info(f"    - Physics temp drop: {has_physics_temp}")

    return files


def _find_storage_attrs(model, suffix: str) -> list[str]:
    """Return all model attribute names matching *_{suffix} that are Pyomo components.

    Handles both the legacy single-storage name ('TES_SOC') and multi-node names
    ('tes_sb_SOC', 'tes_existing_SOC', etc.) produced by component_assembler when
    unified-config storage blocks are registered with their asset name as prefix.
    """
    import pyomo.core as pyo_core
    matches = []
    for attr in dir(model):
        if not attr.endswith(f'_{suffix}'):
            continue
        obj = getattr(model, attr, None)
        if obj is None:
            continue
        # Accept Pyomo Var, Reference, or any IndexedComponent
        if isinstance(obj, (pyo_core.base.var.IndexedVar,
                            pyo_core.base.var.ScalarVar,
                            pyo_core.base.reference.Reference,
                            pyo_core.base.block.BlockData)):
            matches.append(attr)
        elif hasattr(obj, '__getitem__') and hasattr(obj, '_index'):
            matches.append(attr)
    return matches


def _sum_storage_timeseries(model, time_set, suffix: str) -> list[float] | None:
    """Sum timeseries values across all storage units for the given variable suffix."""
    attrs = _find_storage_attrs(model, suffix)
    if not attrs:
        return None
    combined = [0.0] * len(time_set)
    for attr in attrs:
        obj = getattr(model, attr)
        try:
            for i, t in enumerate(time_set):
                v = pyo.value(obj[t])
                if v is not None:
                    combined[i] += v
        except Exception:
            pass
    return combined


def _export_storage_results(
    model,
    time_set,
    output_dir: str,
    dt_h: float,
) -> dict[str, str]:
    """Export thermal storage results including PWL losses."""
    files = {}

    # Check if any storage SOC variable exists (multi-node: tes_sb_SOC etc.; legacy: TES_SOC)
    if not _find_storage_attrs(model, 'SOC'):
        return files

    storage_dir = os.path.join(output_dir, "storage")
    os.makedirs(storage_dir, exist_ok=True)

    logger.info("\n[STORAGE] Exporting storage results...")

    storage_data = {
        'timeseries': {},
        'summary': {},
    }

    # SOC timeseries — summed across all storage units
    soc_vals = _sum_storage_timeseries(model, time_set, 'SOC')
    if soc_vals is not None:
        storage_data['timeseries']['SOC_MWh'] = soc_vals
        storage_data['summary']['SOC_avg_MWh'] = sum(soc_vals) / len(soc_vals)
        storage_data['summary']['SOC_min_MWh'] = min(soc_vals)
        storage_data['summary']['SOC_max_MWh'] = max(soc_vals)

    # Charge/discharge — summed across all storage units
    charge_vals = _sum_storage_timeseries(model, time_set, 'Q_charge')
    if charge_vals is not None:
        storage_data['timeseries']['Q_charge_MW'] = charge_vals
        storage_data['summary']['total_charge_MWh'] = sum(charge_vals) * dt_h

    discharge_vals = _sum_storage_timeseries(model, time_set, 'Q_discharge')
    if discharge_vals is not None:
        storage_data['timeseries']['Q_discharge_MW'] = discharge_vals
        storage_data['summary']['total_discharge_MWh'] = sum(discharge_vals) * dt_h

    # Losses
    loss_vals = _sum_storage_timeseries(model, time_set, 'Q_loss')
    if loss_vals is not None:
        storage_data['timeseries']['Q_loss_MW'] = loss_vals
        storage_data['summary']['total_loss_MWh'] = sum(loss_vals) * dt_h
        storage_data['summary']['avg_loss_MW'] = sum(loss_vals) / len(loss_vals)

    # PWL loss info
    if _find_storage_attrs(model, 'pwl_lambda'):
        storage_data['summary']['uses_pwl_losses'] = True
        logger.info("    - PWL storage losses: Yes")
    else:
        storage_data['summary']['uses_pwl_losses'] = False

    # Save timeseries CSV
    if storage_data['timeseries']:
        ts_df = pd.DataFrame(storage_data['timeseries'], index=list(time_set))
        ts_path = os.path.join(storage_dir, "storage_timeseries.csv")
        ts_df.to_csv(ts_path, sep=';')
        files['storage_timeseries'] = ts_path

    # Save summary JSON
    summary_path = os.path.join(storage_dir, "storage_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(storage_data['summary'], f, indent=2, default=str)
    files['storage_summary'] = summary_path

    logger.info("  ✓ Storage results saved")

    return files


def export_all_results(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float = 1.0,
    export_solver_files: bool = True,
    scenario_name: str | None = None,
) -> dict[str, Any]:
    """
    Export all results including solver files and thermal network.

    Parameters
    ----------
    model : pyomo.ConcreteModel
        Solved Pyomo model
    network_manager : NetworkManager
        Network manager instance (can be None)
    time_set : Set
        Pyomo time set
    output_dir : str
        Output directory
    dt_h : float
        Timestep duration in hours
    export_solver_files : bool
        Whether to export LP/SOL/MPS files
    scenario_name : str
        Optional scenario name for the export

    Returns
    -------
    Dict[str, Any]
        Dictionary with 'files' (file paths) and 'data' (extracted data for dashboard)
    """
    all_files = {}
    extracted_data = {}  # Data for dashboard display

    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 60)
    logger.info("COMPREHENSIVE RESULTS EXPORT")
    logger.info(f"Output directory: {output_dir}")
    logger.info("=" * 60)

    # 1. Solver solution files
    if export_solver_files:
        solver_dir = os.path.join(output_dir, "solver")
        solver_files = export_solver_solution(model, solver_dir)
        all_files.update({f"solver_{k}": v for k, v in solver_files.items()})

    # 2. Thermal network results
    if network_manager is not None and hasattr(network_manager, 'nodes'):
        network_files = export_thermal_network_results(
            model, network_manager, time_set, output_dir, dt_h
        )
        all_files.update({f"network_{k}": v for k, v in network_files.items()})

        # Extract data for dashboard
        extracted_data['network'] = _extract_network_data_for_dashboard(
            model, network_manager, time_set, dt_h
        )

    # 3. Export unified summary CSV (all timeseries in one file)
    unified_csv = _export_unified_timeseries(model, network_manager, time_set, output_dir, dt_h)
    if unified_csv:
        all_files['unified_timeseries'] = unified_csv

    # 4. Export manifest
    manifest = {
        'export_timestamp': datetime.now().isoformat(),
        'scenario_name': scenario_name,
        'output_dir': output_dir,
        'total_files': len(all_files),
        'files': all_files,
        'has_network_data': network_manager is not None,
    }

    manifest_path = os.path.join(output_dir, "export_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, default=str)
    all_files['manifest'] = manifest_path

    logger.info(f"\n{'=' * 60}")
    logger.info(f"EXPORT COMPLETE: {len(all_files)} files")
    logger.info(f"{'=' * 60}")

    return {
        'files': all_files,
        'data': extracted_data,
        'output_dir': output_dir,
    }


def _export_unified_timeseries(
    model,
    network_manager,
    time_set,
    output_dir: str,
    dt_h: float,
) -> str | None:
    """Export all timeseries data into one unified CSV file."""
    try:
        all_data = {'timestep': list(time_set)}

        # 1. DEMAND DATA
        if hasattr(model, 'heatd'):
            try:
                all_data['heat_demand_MW'] = [pyo.value(model.heatd[t]) for t in time_set]
            except Exception as e:
                logger.debug(f"Could not export heat_demand: {e}")

        # 2. ELECTRICITY/GRID
        if hasattr(model, 'P_buy'):
            try:
                all_data['electricity_purchase_MW'] = [pyo.value(model.P_buy[t]) for t in time_set]
            except Exception as e:
                logger.debug(f"Could not export P_buy: {e}")

        if hasattr(model, 'grid_co2'):
            try:
                all_data['grid_co2_intensity_kgMWh'] = [pyo.value(model.grid_co2[t]) for t in time_set]
            except Exception as e:
                logger.debug(f"Could not export grid_co2: {e}")

        # 3. GENERATION DATA
        if hasattr(model, 'Q_boiler'):
            try:
                all_data['boiler_output_MW'] = [pyo.value(model.Q_boiler[t]) for t in time_set]
            except Exception as e:
                logger.debug(f"Could not export Q_boiler: {e}")

        if hasattr(model, 'Q_hp'):
            try:
                all_data['heat_pump_output_MW'] = [pyo.value(model.Q_hp[t]) for t in time_set]
            except Exception as e:
                logger.debug(f"Could not export Q_hp: {e}")

        # 4. NETWORK LOSS
        if hasattr(model, 'network_Q_loss_per_timestep'):
            try:
                all_data['network_loss_MW'] = [
                    pyo.value(model.network_Q_loss_per_timestep[t]) for t in time_set
                ]
            except Exception as e:
                logger.debug(f"Could not export network_loss: {e}")

        # 5. STORAGE (summed across all storage units for multi-node models)
        _soc = _sum_storage_timeseries(model, time_set, 'SOC')
        if _soc is not None:
            all_data['storage_SOC_MWh'] = _soc

        _chg = _sum_storage_timeseries(model, time_set, 'Q_charge')
        if _chg is not None:
            all_data['storage_charge_MW'] = _chg

        _dis = _sum_storage_timeseries(model, time_set, 'Q_discharge')
        if _dis is not None:
            all_data['storage_discharge_MW'] = _dis

        # 6. HOURLY COSTS
        if hasattr(model, 'hourly_cost'):
            try:
                all_data['hourly_cost_EUR'] = [pyo.value(model.hourly_cost[t]) for t in time_set]
            except Exception as e:
                logger.debug(f"Could not export hourly_cost: {e}")

        # 7. NETWORK PIPES (if network model)
        if network_manager and hasattr(network_manager, 'pipes'):
            for pipe_id in network_manager.pipes:
                prefix = pipe_id.upper().replace('-', '_')

                for var_name in ['m_dot', 'velocity', 'delta_p_total', 'Q_consumer']:
                    try:
                        var = getattr(model, f'{prefix}_{var_name}', None)
                        if var is not None:
                            vals = [_val(var[t]) for t in time_set]
                            if any(v is not None for v in vals):
                                all_data[f'{pipe_id}_{var_name}'] = vals
                    except Exception as e:
                        logger.debug(f"Could not export pipe {pipe_id}.{var_name}: {e}")

        # 8. NETWORK NODES (if network model)
        if network_manager and hasattr(network_manager, 'nodes'):
            for node_id in network_manager.nodes:
                prefix = node_id.upper().replace('-', '_')

                for var_name in ['T_supply', 'T_return', 'Q_demand', 'm_dot_demand']:
                    try:
                        var = getattr(model, f'{prefix}_{var_name}', None)
                        if var is not None:
                            vals = [_val(var[t]) for t in time_set]
                            if any(v is not None for v in vals):
                                all_data[f'{node_id}_{var_name}'] = vals
                    except Exception as e:
                        logger.debug(f"Could not export node {node_id}.{var_name}: {e}")

        # Create DataFrame and save
        if len(all_data) > 1:  # More than just timestep
            df = pd.DataFrame(all_data)
            csv_path = os.path.join(output_dir, "unified_timeseries.csv")
            df.to_csv(csv_path, sep=';', index=False)
            logger.info(f"  Exported unified timeseries: {csv_path} ({len(all_data)} columns, {len(df)} rows)")
            return csv_path
        else:
            logger.warning("No timeseries data to export")
            return None

    except Exception as e:
        logger.warning(f"Failed to export unified timeseries: {e}")
        import traceback
        logger.debug(f"Unified timeseries export traceback: {traceback.format_exc()}")
        return None


def _extract_network_data_for_dashboard(
    model,
    network_manager,
    time_set,
    dt_h: float,
) -> dict[str, Any]:
    """Extract network data in a format suitable for dashboard display."""
    dashboard_data = {
        'nodes': {},
        'pipes': {},
        'summary': {},
        'timeseries': {},
    }

    list(time_set)

    # Extract node data
    for node_id, node_config in network_manager.nodes.items():
        prefix = node_id.upper().replace('-', '_')
        node_data = {
            'id': node_id,
            'type': node_config.get('type', 'unknown'),
            'name': node_config.get('name', node_id),
        }

        # Temperature timeseries
        T_supply = getattr(model, f'{prefix}_T_supply', None)
        T_return = getattr(model, f'{prefix}_T_return', None)

        if T_supply is not None:
            vals = [_val(T_supply[t]) for t in time_set]
            finite = [v for v in vals if v is not None]
            if finite:
                node_data['T_supply_series'] = vals
                node_data['T_supply_avg'] = sum(finite) / len(finite)
                dashboard_data['timeseries'][f'{node_id}_T_supply'] = vals

        if T_return is not None:
            vals = [_val(T_return[t]) for t in time_set]
            finite = [v for v in vals if v is not None]
            if finite:
                node_data['T_return_series'] = vals
                node_data['T_return_avg'] = sum(finite) / len(finite)
                dashboard_data['timeseries'][f'{node_id}_T_return'] = vals

        dashboard_data['nodes'][node_id] = node_data

    # Extract pipe data
    for pipe_id, pipe_config in network_manager.pipes.items():
        prefix = pipe_id.upper().replace('-', '_')
        pipe_data = {
            'id': pipe_id,
            'from_node': pipe_config.get('from_node'),
            'to_node': pipe_config.get('to_node'),
            'length_m': pipe_config.get('length_m', 0),
        }

        # Flow and pressure
        m_dot = getattr(model, f'{prefix}_m_dot', None)
        delta_p = getattr(model, f'{prefix}_delta_p_total', None)
        velocity = getattr(model, f'{prefix}_velocity', None)

        if m_dot is not None:
            vals = [pyo.value(m_dot[t]) for t in time_set]
            pipe_data['m_dot_series'] = vals
            pipe_data['m_dot_avg'] = sum(vals) / len(vals)
            pipe_data['m_dot_max'] = max(vals)
            dashboard_data['timeseries'][f'{pipe_id}_m_dot'] = vals

        if delta_p is not None:
            vals = [pyo.value(delta_p[t]) for t in time_set]
            pipe_data['delta_p_series'] = vals
            pipe_data['delta_p_avg'] = sum(vals) / len(vals)
            pipe_data['delta_p_max'] = max(vals)
            dashboard_data['timeseries'][f'{pipe_id}_delta_p'] = vals

        if velocity is not None:
            vals = [pyo.value(velocity[t]) for t in time_set]
            pipe_data['velocity_series'] = vals
            pipe_data['velocity_avg'] = sum(vals) / len(vals)
            pipe_data['velocity_max'] = max(vals)
            dashboard_data['timeseries'][f'{pipe_id}_velocity'] = vals

        # Heat losses
        Q_loss_s = getattr(model, f'{prefix}_Q_loss_supply', None)
        Q_loss_r = getattr(model, f'{prefix}_Q_loss_return', None)

        total_loss = 0
        if Q_loss_s is not None:
            vals = [pyo.value(Q_loss_s[t]) for t in time_set]
            total_loss += sum(vals) * dt_h
        if Q_loss_r is not None:
            vals = [pyo.value(Q_loss_r[t]) for t in time_set]
            total_loss += sum(vals) * dt_h

        pipe_data['total_heat_loss_mwh'] = total_loss

        dashboard_data['pipes'][pipe_id] = pipe_data

    # Summary statistics
    if hasattr(model, 'network_Q_loss_per_timestep'):
        loss_vals = [pyo.value(model.network_Q_loss_per_timestep[t]) for t in time_set]
        dashboard_data['summary']['total_network_loss_mwh'] = sum(loss_vals) * dt_h
        dashboard_data['summary']['avg_network_loss_mw'] = sum(loss_vals) / len(loss_vals)
        dashboard_data['timeseries']['network_loss'] = loss_vals

    dashboard_data['summary']['total_pipe_length_m'] = sum(
        p.get('length_m', 0) for p in network_manager.pipes.values()
    )
    dashboard_data['summary']['num_nodes'] = len(network_manager.nodes)
    dashboard_data['summary']['num_pipes'] = len(network_manager.pipes)

    return dashboard_data
