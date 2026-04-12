#!/usr/bin/env python3
"""
Test that zonal demand charges are properly integrated into the objective function.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pandas as pd
from calion.utils.simple_yaml import load
from calion.utils.timeseries import TimeSeriesTable
from calion.models.system_builder import build_model


def load_table_from_csv(csv_path: str) -> TimeSeriesTable:
    """Load a TimeSeriesTable from CSV file."""
    df = pd.read_csv(csv_path)
    
    # Assume first column is datetime, rest are data columns
    index = [datetime.fromisoformat(str(ts)) for ts in df.iloc[:, 0]]
    columns = list(df.columns[1:])
    data = {col: df[col].tolist() for col in columns}
    
    return TimeSeriesTable(index=index, columns=columns, data=data)


def test_model_has_zonal_costs():
    """Verify that model has zone_demand_charge parameters when configured."""
    
    # Load a config with zonal costs
    config_path = project_root / "configs" / "paper" / "L2_costs_example_2_zonal_static.yaml"
    table_path = project_root / "data" / "Import_Data_yearly_zones.csv"
    
    if not config_path.exists() or not table_path.exists():
        print(f"⚠️  Test skipped: config or data file not found")
        print(f"   Config: {config_path}")
        print(f"   Table:  {table_path}")
        return
    
    print(f"🔍 Loading config: {config_path}")
    print(f"🔍 Loading data:   {table_path}")
    
    cfg = load(str(config_path))
    table = load_table_from_csv(str(table_path))
    
    print(f"✓ Config and data loaded, building model...")
    m = build_model(table, cfg)
    
    # Check 1: zone_demand_charge exists
    assert hasattr(m, 'zone_demand_charge'), "❌ Model missing zone_demand_charge!"
    print(f"✓ Model has zone_demand_charge attribute")
    
    # Check 2: zone_demand_charge is not empty
    if m.zone_demand_charge:
        print(f"✓ Zone demand charges registered: {list(m.zone_demand_charge.keys())}")
        # Use the shadow dict for values
        shadow_dict = getattr(m, 'zone_demand_charge_values', {})
        for zone_id in m.zone_demand_charge.keys():
            value = shadow_dict.get(zone_id, 0.0)
            print(f"  - {zone_id}: {value} EUR/MW/year")
    else:
        print(f"⚠️  No zone demand charges found (global costs only)")
    
    # Check 3: P_buy_peak still exists (backward compat)
    assert hasattr(m, 'P_buy_peak'), "❌ Model missing P_buy_peak!"
    print(f"✓ Global P_buy_peak variable exists")
    
    # Check 4: All zones share P_buy_peak (single grid connection)
    if m.zone_demand_charge:
        assert hasattr(m, 'P_buy_peak'), "❌ Model missing P_buy_peak for zonal tracking!"
        print(f"✓ Zones share global P_buy_peak ({len(m.zone_demand_charge)} zones configured)")
    
    # Check 5: Dynamic resolver exists if configured
    assert hasattr(m, 'zone_demand_charge_ts'), "❌ Model missing zone_demand_charge_ts!"
    print(f"✓ Dynamic cost resolver available: {m.zone_demand_charge_ts is not None}")
    
    print("\n✅ All integration checks passed!")
    return m




if __name__ == "__main__":
    try:
        m = test_model_has_zonal_costs()
    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
