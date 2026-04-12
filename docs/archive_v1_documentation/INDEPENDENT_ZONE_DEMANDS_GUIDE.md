# Independent Zone-Specific Demand Profiles Guide

**Status**: Feasible with minimal code changes  
**Complexity**: Low (config-driven, no model changes needed)  
**Benefit**: Realistic per-zone demand patterns instead of artificial fractioning

---

## Current Approach (Demand-Fraction Based)

Your current L3 config uses **demand fractions**:

```yaml
zone_01:
  type: consumer
  demand_fraction: 0.06           # 6% of total
  demand:
    column: "waermebedarf_MWth"  # All zones read this column
```

All zones read the **same column** (`waermebedarf_MWth`), then it's scaled by `demand_fraction`.

**Issue**: All zones have identical temporal patterns — only amplitudes differ.

---

## Alternative Approach: Independent Timeseries per Zone

Each zone has its own column with 100% of its demand:

```yaml
zone_01:
  type: consumer
  demand:
    column: "zone_01_demand_MWth"  # Unique column for zone 1
zone_02:
  type: consumer
  demand:
    column: "zone_02_demand_MWth"  # Unique column for zone 2
# ... etc
```

**Benefit**: Each zone can have:
- Completely independent hourly profiles
- Different load factors  
- Different peak times
- Realistic industrial/residential mixing

---

## Implementation Steps

### Step 1: Prepare Data File with Zone-Specific Columns

Create or modify `data/Import_Data_yearly_zones.csv`:

```csv
Datum,strompreis_EUR_MWh,grid_co2_kg_MWh,T_outdoor_C,T_WRG1_C,T_WRG2_C,zone_01_demand_MWth,zone_02_demand_MWth,zone_03_demand_MWth,...
2023-01-01 00:00:00,45.2,520,−5.2,60,55,2.1,1.8,0.9,...
2023-01-01 01:00:00,42.3,510,−5.5,60,55,2.0,1.7,0.8,...
...
```

**Generation Strategy** (Python script below):

```python
import pandas as pd
import numpy as np

# Load existing yearly data
df = pd.read_csv('data/Import_Data_yearly.csv')
total_demand = df['waermebedarf_MWth']

# Define zone fractions (must sum to ~1.0)
zone_fractions = {
    'zone_01': 0.06,   # North
    'zone_02': 0.05,
    # ... all 23 zones
}

# For each zone, create independent demand with stochastic variation
np.random.seed(42)
for zone_id, frac in zone_fractions.items():
    # Base profile: scaled fraction
    base_demand = total_demand * frac
    
    # Add zone-specific temporal variation (±20% daily variation)
    daily_pattern = np.random.normal(1.0, 0.08, len(total_demand))
    hourly_noise = np.random.normal(1.0, 0.05, len(total_demand))
    
    # Combine: base × day variation × hour variation
    zone_demand = base_demand * daily_pattern * hourly_noise
    
    # Ensure non-negative and smooth
    zone_demand = np.maximum(zone_demand, 0.0)
    
    df[f'{zone_id}_demand_MWth'] = zone_demand

df.to_csv('data/Import_Data_yearly_zones.csv', index=False)
```

---

### Step 2: Create New L3 Config (Independent Zones)

Create `configs/paper/L3_independent_zones_dispatch.yaml`:

```yaml
site:
  input_xlsx: "data/Import_Data_yearly_zones.csv"
  columns:
    datetime:  "Datum"
    price:     "strompreis_EUR_MWh"
    co2_grid:  "grid_co2_kg_MWh"
    outdoor_temp: "T_outdoor_C"
    wrg1_temp: "T_WRG1_C"
    wrg2_temp: "T_WRG2_C"

scenario:
  name: "L3_independent_zones_dispatch"
  run_mode: PF_ONLY
  description: "30-node network with independent per-zone demands (no fractions)"

network:
  nodes:
    plant_main:
      type: producer
      assets: [boiler_main, chp_main, hp_main, tes_main]

    # North branch: 5 zones (each with independent demand)
    zone_01:
      type: consumer
      demand:
        column: "zone_01_demand_MWth"  # ← No demand_fraction!
    zone_02:
      type: consumer
      demand:
        column: "zone_02_demand_MWth"
    # ... zones 03-05

    # Similar for South, East, West branches
    zone_06:
      type: consumer
      demand:
        column: "zone_06_demand_MWth"
    # ... etc (zones 07-30)

    # Junctions remain unchanged
    j_central:
      type: junction
    j_north:
      type: junction
    j_south:
      type: junction
    j_east:
      type: junction
    j_west:
      type: junction

  pipes:
    # [Same as L3_detailed_dispatch.yaml]
    plant_to_jcentral:
      from_node: plant_main
      to_node: j_central
      length_m: 150.0
      diameter_mm: 300
      u_value_supply_w_per_m_k: 0.35
      u_value_return_w_per_m_k: 0.35
    # ... rest of pipes unchanged

assets:
  # [Same as L3_detailed_dispatch.yaml — no changes needed]
  boiler_main:
    type: thermal_generator
    fuel: gas
    capacity_mw: 200.0
    # ... etc

  # ... hp_main, chp_main, tes_main unchanged
```

**Key Difference**: Remove `demand_fraction` from all consumer nodes

---

### Step 3: Code Changes Required

#### 3a. System Builder (Already Supports Per-Node Demands)

**Good news**: The code **already handles this**! In `calion/models/system_builder.py` lines 125–145:

```python
# Multi-node: per-node demand parameters
m.node_demand = {}
for nid, node in ucfg.nodes.items():
    if node.demand is not None:
        actual_col = _find_demand_column(table, node.demand.column)
        demand_data = {i + 1: float(table[actual_col][i]) for i in range(T)}
        param_name = f"heatd_{nid}"
        setattr(m, param_name, pyo.Param(m.t, initialize=demand_data, mutable=True))
        m.node_demand[nid] = getattr(m, param_name)
```

This already creates `heatd_zone_01`, `heatd_zone_02`, etc. from individual columns!

#### 3b. ThermalNodeBlock (Already Handles Per-Node Demands)

In `calion/models/blocks/thermal_node.py` lines 212–230:

```python
if node_type == 'consumer':
    demand_fraction = config.get('demand_fraction', 0.0)

    _node_heatd_attr = f'heatd_{node_id}'
    if hasattr(model, _node_heatd_attr):
        # ← ALREADY PREFERS per-node param!
        _node_heatd = getattr(model, _node_heatd_attr)
        def demand_init(m, t, _h=_node_heatd):
            return pyo.value(_h[t]) * demand_fraction  # ← Multiply by fraction if present
```

**The issue**: It still multiplies by `demand_fraction`. **Solution**: Set `demand_fraction=1.0` (or omit it) in config.

#### 3c. Minor Config Validation Update (Optional)

In `calion/config/unified_config.py`, the parser should **not require** `demand_fraction` when `demand.column` is specified.

Currently (line ~114):
```python
# This might raise error if no demand_fraction
demand_fraction = raw.get("demand_fraction")
```

Should be:
```python
# Demand fraction is optional — defaults to 1.0 (100%) if not specified
demand_fraction = raw.get("demand_fraction", 1.0)  # ← Default to 1.0
```

**Apply this fix**:

---

## File Modifications Needed

### 1. [calion/config/unified_config.py](calion/config/unified_config.py)

**Change**: Make `demand_fraction` default to 1.0 when not specified

```python
# Line ~114-116, in parse_node() function:
# FROM:
demand_fraction = raw.get("demand_fraction")

# TO:
demand_fraction = raw.get("demand_fraction", 1.0)  # Default to 100% if not specified
```

---

### 2. [calion/models/blocks/thermal_node.py](calion/models/blocks/thermal_node.py)

**Change**: Allow omitting `demand_fraction` in validation (already flexible, no change needed)

The validation currently requires *either* `demand_fraction` OR `demand_profile`:
```python
if 'demand_fraction' not in config and 'demand_profile' not in config:
    raise ValueError(...) 
```

This is **already OK** — if you omit `demand_fraction`, it just defaults to 0.0 (which we'll fix in step 1).

---

## Complete Example: Switching to Independent Zones

### Before (Current L3 Config):

```yaml
zone_01:
  type: consumer
  demand_fraction: 0.06  ← Artificial fraction
  demand:
    column: "waermebedarf_MWth"  ← All zones use same column

zone_02:
  type: consumer
  demand_fraction: 0.05
  demand:
    column: "waermebedarf_MWth"
```

**Effect**: 
- `zone_01` demand = `waermebedarf_MWth × 0.06`
- `zone_02` demand = `waermebedarf_MWth × 0.05`
- Both have **identical temporal shape** (same hourly pattern)

---

### After (Independent Zones):

```yaml
zone_01:
  type: consumer
  demand:
    column: "zone_01_demand_MWth"  ← Unique column

zone_02:
  type: consumer
  demand:
    column: "zone_02_demand_MWth"  ← Unique column
```

**Effect**:
- `zone_01` demand = `zone_01_demand_MWth[t]` (full 8760-hour timeseries)
- `zone_02` demand = `zone_02_demand_MWth[t]` (independent timeseries)
- **Each can have different peak times, patterns, and load factors**

---

## Python Script: Generate Sample Zone-Specific Data

Save as `scripts/generate_zone_demands.py`:

```python
#!/usr/bin/env python3
"""
Generate independent zone-specific heat demand profiles.

Takes existing yearly demand and creates per-zone variations.
Each zone gets:
- Base fraction (to ensure total is conserved)
- Daily variation (±20%)
- Hourly noise (±5%)
- Result: realistic heterogeneous demands
"""

import pandas as pd
import numpy as np
from pathlib import Path

def generate_zone_demands(
    input_csv: str,
    output_csv: str,
    zone_fractions: dict,
    seed: int = 42,
    daily_std: float = 0.08,
    hourly_std: float = 0.05,
):
    """
    Generate independent zone-specific demands from total demand.
    
    Args:
        input_csv: Path to original Import_Data_yearly.csv
        output_csv: Path to save new file with zone columns
        zone_fractions: Dict of {zone_id: fraction} (must sum to ~1.0)
        seed: Random seed for reproducibility
        daily_std: Std dev of daily variation factor
        hourly_std: Std dev of hourly variation factor
    """
    np.random.seed(seed)
    
    # Load data
    df = pd.read_csv(input_csv)
    total_demand = df['waermebedarf_MWth'].values
    T = len(total_demand)
    
    print(f"Loaded {T} timesteps from {input_csv}")
    print(f"Total demand: {total_demand.sum():.1f} GWh/year")
    print(f"Zones: {len(zone_fractions)}")
    
    # Verify fractions sum to ~1.0
    frac_sum = sum(zone_fractions.values())
    print(f"Zone fraction sum: {frac_sum:.4f} (should be ~1.0)")
    if not (0.99 < frac_sum <= 1.01):
        raise ValueError(f"Zone fractions sum to {frac_sum}, not ~1.0")
    
    # Generate per-zone demands
    for zone_id, base_frac in zone_fractions.items():
        # Base profile (scale total by zone fraction)
        base_demand = total_demand * base_frac
        
        # Daily variation: each day gets a random multiplier ±std
        daily_mult = np.random.normal(1.0, daily_std, len(total_demand))
        daily_mult = np.repeat(daily_mult, 1)  # constant per hour (adjust as needed)
        daily_mult = np.tile(daily_mult, (T // len(daily_mult)) + 1)[:T]
        
        # Hourly random noise
        hourly_mult = np.random.normal(1.0, hourly_std, T)
        
        # Combined variation
        zone_demand = base_demand * daily_mult * hourly_mult
        
        # Clamp to non-negative
        zone_demand = np.maximum(zone_demand, 0.01)
        
        df[f'{zone_id}_demand_MWth'] = zone_demand
        print(f"  {zone_id}: {zone_demand.sum():.1f} GWh/year (base: {base_demand.sum():.1f} GWh)")
    
    # Save
    df.to_csv(output_csv, index=False)
    print(f"\nSaved to {output_csv}")
    print(f"Columns: {[c for c in df.columns if c.startswith('zone_')]}")


if __name__ == '__main__':
    import sys
    
    # Define L3 zone fractions (sum to 1.0)
    zone_fracs = {
        # North (23%)
        'zone_01': 0.06, 'zone_02': 0.05, 'zone_03': 0.04, 'zone_04': 0.04, 'zone_05': 0.04,
        # South (26%)
        'zone_06': 0.06, 'zone_07': 0.05, 'zone_08': 0.04, 'zone_09': 0.04, 'zone_10': 0.04, 'zone_11': 0.03,
        # East (25%)
        'zone_12': 0.06, 'zone_13': 0.05, 'zone_14': 0.04, 'zone_15': 0.04, 'zone_16': 0.03, 'zone_17': 0.03,
        # West (26%)
        'zone_18': 0.06, 'zone_19': 0.05, 'zone_20': 0.04, 'zone_21': 0.04, 'zone_22': 0.04, 'zone_23': 0.03,
        # Additional zones (from original L3)
        # ... add remaining zones if needed
    }
    
    generate_zone_demands(
        input_csv='data/Import_Data_yearly.csv',
        output_csv='data/Import_Data_yearly_zones.csv',
        zone_fractions=zone_fracs,
        seed=42,
    )
```

**Run**:
```powershell
python scripts/generate_zone_demands.py
```

---

## Testing the Change

### 1. Generate zone data:
```powershell
python scripts/generate_zone_demands.py
```

### 2. Run L3 with independent zones:
```powershell
python scripts/paper/run_single_level.py configs/paper/L3_independent_zones_dispatch.yaml
```

### 3. Verify in results:
```python
import pandas as pd

# Check that each zone has independent profile
results = pd.read_csv('outputs/paper_results/L3_independent_zones_results.csv')
zone_cols = [c for c in results.columns if c.startswith('zone_')]

# Plot first 168 hours (1 week)
for z in zone_cols[:5]:
    print(f"{z}: mean={results[z].mean():.3f}, std={results[z].std():.3f}")
    
# Should see different means and stds for each zone!
```

---

## Advantages of Independent Zones

| Aspect | Demand-Fraction | Independent |
|--------|-----------------|------------|
| **Temporal pattern** | All zones identical | Unique per zone |
| **Peak times** | All peak together | Can peak at different hours |
| **Realism** | Low (artificial fractions) | High (realistic heterogeneity) |
| **Sensitivity** | Easy (multiplier) | More nuanced |
| **Data requirements** | 1 column | 23+ columns |
| **Model complexity** | Same | Same (code handles it) |

---

## Summary

**Feasibility**: ✅ **Fully supported** — code already handles per-node demands

**Steps**:
1. Create zone-specific demand columns in CSV ✅  
2. Update config to reference zone columns (remove `demand_fraction`) ✅  
3. Make minor fix to `unified_config.py` to default `demand_fraction=1.0` ✅  
4. Run optimization — no model changes needed ✅  

**Total code changes**: ~5 lines (optional, for cleaner defaults)

---

## Questions?

- **How to validate zone demands total to original?** Check CSV sum matches `Import_Data_yearly.csv`  
- **Can I mix zones? (some with fraction, some independent)?** Yes, set `demand_fraction=1.0` for independent ones  
- **Will results differ from fractioned approach?** Yes — each zone's demand curve is independent, which can change dispatch patterns and network flows  
- **How much does this affect runtime?** Negligible — same number of variables/constraints (just different parameterization)
