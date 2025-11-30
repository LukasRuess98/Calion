#!/usr/bin/env python3
"""
Dashboard demo with mock data - NO optimization required!

This shows the dashboard interface without running actual optimization.
"""

import sys
from pathlib import Path
from collections import OrderedDict
from datetime import datetime, timedelta

# Setup path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("="*70)
print("🎛️ Dashboard Demo mit Mock-Daten (KEINE Optimierung benötigt)")
print("="*70)

# Create mock data structures
from energis.run.rolling_horizon import WorkflowContext, WorkflowPlan, ScenarioResult, DesignData
from energis.utils.timeseries import TimeSeriesTable

print("\n1. Erstelle Mock-Daten...")

# Create timestamps (one week hourly)
n_steps = 168  # One week
start_date = datetime(2023, 1, 1)
timestamps = [start_date + timedelta(hours=i) for i in range(n_steps)]

# Create mock table data
import numpy as np
demand = 5.0 + 3.0 * np.sin(np.arange(n_steps) * 2 * np.pi / 24)  # Daily pattern
strompreis = 50.0 + 20.0 * np.sin(np.arange(n_steps) * 2 * np.pi / 24 + np.pi)

table = TimeSeriesTable(
    index=timestamps,
    columns=['waermebedarf_MWth', 'strompreis_eur_per_mwh'],
    data={
        'waermebedarf_MWth': list(demand),
        'strompreis_eur_per_mwh': list(strompreis)
    }
)

# Create mock series (optimization results)
hp1_output = demand * 0.6
hp2_output = demand * 0.3
tes_discharge = demand * 0.1
tes_soc = 20.0 + 10.0 * np.sin(np.arange(n_steps) * 2 * np.pi / 168)
tes_charge = np.maximum(0, -np.diff(tes_soc, prepend=20.0)) * 10
tes_discharge_power = np.maximum(0, np.diff(tes_soc, prepend=20.0)) * 10

p_buy = hp1_output / 3.5 + hp2_output / 4.0  # Assume COPs of 3.5 and 4.0

series = OrderedDict({
    'HP1_Q_th_MW': list(hp1_output),
    'HP2_Q_th_MW': list(hp2_output),
    'TES_discharge_MW': list(tes_discharge_power),
    'TES_charge_MW': list(tes_charge),
    'TES_SOC_MWh': list(tes_soc),
    'HP1_Pel_MW': list(hp1_output / 3.5),
    'HP2_Pel_MW': list(hp2_output / 4.0),
    'P_buy_MW': list(p_buy),
})

# Create mock costs
costs = {
    'objective.OBJ_value_EUR': 234567.89,
    'objective.Grid_energy_cost_EUR': 123456.78,
    'objective.Electricity_base_cost_EUR': 80000.00,
    'objective.Electricity_energy_fee_EUR': 25000.00,
    'objective.Electricity_grid_fee_EUR': 15000.00,
    'objective.Demand_charge_cost_EUR': 3456.78,
    'objective.Fuel_cost_EUR': 50000.00,
    'objective.Capex_cost_EUR': 45000.00,
    'objective.Capex_heat_pumps_EUR': 35000.00,
    'objective.Capex_storage_EUR': 10000.00,
    'objective.CO2_cost_EUR': 16111.11,
}

# Create mock summary
summary = {
    'objective': costs
}

# Create mock result
mock_result = ScenarioResult(
    table=table,
    series=series,
    summary=summary,
    costs=costs,
    solver={'status': 'ok', 'termination_condition': 'optimal'}
)

# Create mock design
mock_design = DesignData(
    heat_pumps={
        'HP1': {'capacity_mw': 3.5},
        'HP2': {'capacity_mw': 2.8},
    },
    storage={'capacity_mwh': 50.0}
)

# Create mock workflow
class MockWorkflow:
    def __init__(self):
        self.plan = WorkflowPlan(steps=['PF'], fix_design=False)
        self.pf_result = mock_result
        self.rh_result = None
        self.mpc_result = None
        self.design = mock_design
        self.config = {}

workflow = MockWorkflow()

print("   ✅ Mock-Daten erstellt")
print(f"   - {n_steps} Zeitschritte")
print(f"   - 2 Wärmepumpen")
print(f"   - 1 Thermischer Speicher")
print(f"   - Gesamtkosten: {costs['objective.OBJ_value_EUR']:,.2f} EUR")

print("\n2. Erstelle Dashboard...")

from energis.io.dashboard import create_dashboard

dashboard = create_dashboard(workflow, title="Demo Dashboard (Mock-Daten)")

print("   ✅ Dashboard erstellt!")

print("\n" + "="*70)
print("✅ SUCCESS! Dashboard ist bereit!")
print("="*70)

print("\n📊 Das Dashboard enthält:")
print("  ✅ Overview Tab mit KPIs")
print("  ✅ Interaktive Zeitreihen")
print("  ✅ Kosten-Analyse")
print("  ✅ Anlagen-Design")

print("\n🎨 Um das Dashboard anzuzeigen:")
print("\n  Option 1: Als Webapp")
print("    1. Füge am Ende hinzu: dashboard.servable()")
print("    2. Führe aus: panel serve demo_dashboard_mock.py --show")
print("    3. Browser öffnet sich automatisch")

print("\n  Option 2: In Jupyter Notebook")
print("    1. Kopiere diesen Code in Notebook")
print("    2. Am Ende: dashboard")
print("    3. Dashboard wird inline angezeigt")

print("\n💡 Für echte Optimierung:")
print("   pip install pyomo")
print("   sudo apt-get install glpk-utils  # Oder anderer Solver")
print("   Dann: python demo_dashboard.py")

print("\n" + "="*70)

# Enable webapp mode:
dashboard.servable()
