"""
Test script for thermal network implementation.

Runs a simple 3-node network case to validate:
- Component attachment
- Temperature calculations
- Heat loss modeling
- Optimization convergence
- Results extraction

Usage:
    python scripts/test_thermal_network.py
"""

import sys
from pathlib import Path
import json
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pyomo.environ as pyo

from energis.utils.timeseries import TimeSeriesTable
from energis.config.merge import load_and_merge
from energis.models.system_builder import build_model

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_data(hours=24):
    """
    Create minimal test data for network validation.

    Args:
        hours: Number of hours to simulate

    Returns:
        TimeSeriesTable with test data
    """
    logger.info(f"Creating test data for {hours} hours")

    # Create simple hourly profiles
    time_index = pd.date_range('2024-01-01', periods=hours, freq='H')

    # Heat demand: sinusoidal pattern (peak at noon)
    import numpy as np
    hour_of_day = np.arange(hours) % 24
    demand_pattern = 5 + 3 * np.sin((hour_of_day - 6) * 2 * np.pi / 24)  # 2-8 MW

    # Electricity price: higher during day
    price_pattern = 50 + 20 * np.sin((hour_of_day - 12) * 2 * np.pi / 24)  # 30-70 EUR/MWh

    # Grid CO2 intensity: varies with renewable availability
    co2_pattern = 400 - 100 * np.sin((hour_of_day - 12) * 2 * np.pi / 24)  # 300-500 kg/MWh

    # Outdoor temperature: cold night, warm day
    temp_pattern = 5 + 8 * np.sin((hour_of_day - 6) * 2 * np.pi / 24)  # -3°C to 13°C

    df = pd.DataFrame({
        'datetime': time_index,
        'waermebedarf_MWth': demand_pattern,
        'strompreis_EUR_MWh': price_pattern,
        'grid_co2_kg_MWh': co2_pattern,
        'T_outdoor': temp_pattern,
    })

    df.set_index('datetime', inplace=True)

    logger.info(f"Test data created: {df.shape}")
    logger.info(f"  Heat demand: {df['waermebedarf_MWth'].min():.2f} - {df['waermebedarf_MWth'].max():.2f} MW")
    logger.info(f"  Price range: {df['strompreis_EUR_MWh'].min():.2f} - {df['strompreis_EUR_MWh'].max():.2f} EUR/MWh")
    logger.info(f"  Outdoor temp: {df['T_outdoor'].min():.2f} - {df['T_outdoor'].max():.2f} °C")

    return df


def run_test(hours=24, solver='cbc'):
    """
    Run simple network test.

    Args:
        hours: Number of hours to simulate
        solver: Pyomo solver to use (cbc, glpk, gurobi)

    Returns:
        Tuple of (model, solver_results, success)
    """
    logger.info("=" * 80)
    logger.info("THERMAL NETWORK TEST")
    logger.info("=" * 80)

    # Create test data
    table = create_test_data(hours)

    # Load configuration
    config_files = [
        'configs/base.yaml',
        'configs/tech_catalog.yaml',
        'configs/systems/test_simple_with_network.system.yaml'
    ]

    logger.info("\nLoading configuration...")
    cfg = load_and_merge(config_files)

    # Add config directory for relative path resolution
    cfg['config_dir'] = str(Path.cwd())

    logger.info(f"  Thermal network enabled: {cfg.get('thermal_network', {}).get('enabled')}")
    logger.info(f"  Topology file: {cfg.get('thermal_network', {}).get('topology_file')}")

    # Build model
    logger.info("\nBuilding Pyomo model...")
    try:
        model = build_model(table, cfg, dt_h=1.0)
        logger.info("  ✓ Model built successfully")
    except Exception as e:
        logger.error(f"  ✗ Model building failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None, False

    if model is None:
        logger.error("  ✗ Model is None (Pyomo not available?)")
        return None, None, False

    # Log model statistics
    logger.info("\nModel statistics:")
    num_vars = sum(1 for _ in model.component_data_objects(pyo.Var))
    num_constraints = sum(1 for _ in model.component_data_objects(pyo.Constraint))
    num_binary = sum(1 for v in model.component_data_objects(pyo.Var) if v.is_binary())
    logger.info(f"  Variables: {num_vars} (binary: {num_binary})")
    logger.info(f"  Constraints: {num_constraints}")

    # Check for network components
    if hasattr(model, 'network_manager'):
        logger.info("  ✓ Network manager attached")
        if hasattr(model, 'network_total_pipe_capex'):
            logger.info("  ✓ Network CAPEX included")
        if hasattr(model, 'network_heat_loss_expr'):
            logger.info("  ✓ Network heat losses included")
    else:
        logger.warning("  ⚠ Network manager not found!")

    # Solve model
    logger.info(f"\nSolving with {solver}...")
    try:
        solver_obj = pyo.SolverFactory(solver)
        if not solver_obj.available():
            logger.error(f"  ✗ Solver {solver} not available!")
            logger.info("  Available solvers: glpk, cbc")
            return model, None, False

        results = solver_obj.solve(model, tee=True)

        # Check termination condition
        if results.solver.termination_condition == pyo.TerminationCondition.optimal:
            logger.info("  ✓ Optimization successful (optimal solution found)")
            success = True
        elif results.solver.termination_condition == pyo.TerminationCondition.feasible:
            logger.warning("  ⚠ Feasible solution found (not proven optimal)")
            success = True
        else:
            logger.error(f"  ✗ Optimization failed: {results.solver.termination_condition}")
            success = False

    except Exception as e:
        logger.error(f"  ✗ Solver error: {e}")
        import traceback
        traceback.print_exc()
        return model, None, False

    return model, results, success


def validate_results(model):
    """
    Validate and report network results.

    Args:
        model: Solved Pyomo model
    """
    logger.info("\n" + "=" * 80)
    logger.info("RESULTS VALIDATION")
    logger.info("=" * 80)

    if not hasattr(model, 'network_manager'):
        logger.error("No network manager found!")
        return

    # Extract network results
    logger.info("\nExtracting network results...")
    network_results = model.network_manager.get_results(model, model.t)

    # Validate pipe results
    logger.info("\nPipe Results:")
    for pipe_id, pipe_res in network_results['pipes'].items():
        logger.info(f"\n  {pipe_id}:")
        logger.info(f"    Length: {pipe_res['length_m']} m")
        logger.info(f"    From: {pipe_res['from_node']} → To: {pipe_res['to_node']}")
        logger.info(f"    Current diameter: {pipe_res['current_diameter_mm']} mm")
        logger.info(f"    Selected diameter: {pipe_res['selected_diameter_mm']} mm")
        logger.info(f"    Upgrade recommended: {pipe_res['upgrade_recommended']}")
        logger.info(f"    Average flow: {pipe_res['avg_flow_kg_s']:.2f} kg/s")
        logger.info(f"    Heat delivered: {pipe_res['total_heat_delivered_mwh']:.1f} MWh")
        logger.info(f"    Heat losses: {pipe_res['total_heat_loss_mwh']:.1f} MWh ({pipe_res['loss_percentage']:.2f}%)")
        logger.info(f"    Supply temp in: {pipe_res['avg_supply_temp_in_c']:.1f}°C")

    # Validate node results
    logger.info("\nNode Results:")
    for node_id, node_res in network_results['nodes'].items():
        logger.info(f"\n  {node_id} ({node_res['type']}):")
        logger.info(f"    Avg supply temp: {node_res['avg_supply_temp_c']:.2f}°C")
        logger.info(f"    Avg return temp: {node_res['avg_return_temp_c']:.2f}°C")
        if node_res['type'] == 'consumer':
            logger.info(f"    Total demand: {node_res['total_demand_mwh']:.1f} MWh")
            logger.info(f"    Peak demand: {node_res['peak_demand_mw']:.2f} MW")

    # Overall summary
    summary = network_results['summary']
    logger.info("\n" + "=" * 80)
    logger.info("NETWORK SUMMARY")
    logger.info("=" * 80)
    logger.info(f"  Total heat delivered: {summary['total_heat_delivered_mwh']:.1f} MWh")
    logger.info(f"  Total heat losses: {summary['total_heat_loss_mwh']:.1f} MWh")
    logger.info(f"  Loss percentage: {summary['loss_percentage']:.2f}%")
    logger.info(f"  Total pipe length: {summary['total_pipe_length_m']:.0f} m")

    # Validation checks
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION CHECKS")
    logger.info("=" * 80)

    checks_passed = 0
    checks_total = 0

    # Check 1: Heat losses reasonable (should be < 15%)
    checks_total += 1
    if summary['loss_percentage'] < 15:
        logger.info(f"  ✓ Heat losses reasonable: {summary['loss_percentage']:.2f}% < 15%")
        checks_passed += 1
    else:
        logger.warning(f"  ⚠ Heat losses high: {summary['loss_percentage']:.2f}% >= 15%")

    # Check 2: Supply temperature drop reasonable (should be < 5°C for 1km)
    checks_total += 1
    for pipe_id, pipe_res in network_results['pipes'].items():
        temp_drop = pipe_res['avg_supply_temp_in_c'] - pipe_res['T_supply_out_c'][0]
        if temp_drop < 5:
            logger.info(f"  ✓ Temperature drop reasonable: {temp_drop:.2f}°C < 5°C")
            checks_passed += 1
        else:
            logger.warning(f"  ⚠ Temperature drop high: {temp_drop:.2f}°C >= 5°C")

    # Check 3: Heat delivered matches demand
    checks_total += 1
    total_demand = sum(
        node_res['total_demand_mwh']
        for node_res in network_results['nodes'].values()
        if node_res['type'] == 'consumer'
    )
    delivery_ratio = summary['total_heat_delivered_mwh'] / total_demand if total_demand > 0 else 0
    if 0.95 <= delivery_ratio <= 1.05:
        logger.info(f"  ✓ Heat delivery matches demand: {delivery_ratio:.3f} ≈ 1.0")
        checks_passed += 1
    else:
        logger.warning(f"  ⚠ Heat delivery mismatch: {delivery_ratio:.3f} (should be ≈ 1.0)")

    logger.info(f"\nValidation: {checks_passed}/{checks_total} checks passed")

    return network_results


def export_dashboard_data(model, network_results, output_file='results/test_network_dashboard.json'):
    """
    Export network results for dashboard visualization.

    Args:
        model: Solved Pyomo model
        network_results: Network results dict
        output_file: Output JSON file path
    """
    logger.info(f"\nExporting dashboard data to: {output_file}")

    if not hasattr(model, 'network_manager'):
        logger.error("No network manager found!")
        return

    # Generate dashboard data
    dashboard_data = model.network_manager.export_for_dashboard(network_results)

    # Save to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(dashboard_data, f, indent=2)

    logger.info(f"  ✓ Dashboard data exported: {output_path}")
    logger.info(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    """Main test execution."""
    import argparse

    parser = argparse.ArgumentParser(description='Test thermal network implementation')
    parser.add_argument('--hours', type=int, default=24, help='Hours to simulate (default: 24)')
    parser.add_argument('--solver', type=str, default='cbc', help='Solver to use (default: cbc)')

    args = parser.parse_args()

    # Run test
    model, results, success = run_test(hours=args.hours, solver=args.solver)

    if not success:
        logger.error("\n❌ TEST FAILED")
        sys.exit(1)

    # Validate results
    network_results = validate_results(model)

    # Export dashboard data
    if network_results:
        export_dashboard_data(model, network_results)

    logger.info("\n" + "=" * 80)
    logger.info("✅ TEST COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
