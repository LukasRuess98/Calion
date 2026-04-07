# Quick Start: Testing Independent Zone Demands

## Overview

This guide shows how to switch from demand-fraction-based zones to independent zone demands.

**What's been created:**
1. ✅ **Guide document**: [docs/INDEPENDENT_ZONE_DEMANDS_GUIDE.md](docs/INDEPENDENT_ZONE_DEMANDS_GUIDE.md)
2. ✅ **Python generator script**: `scripts/generate_zone_demands.py`
3. ✅ **Example config**: `configs/paper/L3_independent_zones_dispatch.yaml`
4. ✅ **Code fix**: `calion/config/unified_config.py` (defaults `demand_fraction=1.0`)

---

## Step-by-Step: Try It Now

### Step 1: Generate Zone-Specific Demand Data

```powershell
cd c:\Users\LKR\Downloads\tespy-dev\Planing-Framework-for-Heat

# Generate independent zone demands (base + daily + hourly variation)
python scripts/generate_zone_demands.py
```

**Output**: `data/Import_Data_yearly_zones.csv` with columns:
- `zone_01_demand_MWth`, `zone_02_demand_MWth`, ..., `zone_23_demand_MWth`
- Each with independent 8760-hour timeseries
- Total demand conserved (≈517 GWh/year)

---

### Step 2: Run Optimization with Independent Zones

```powershell
# Run L3 with independent zone demands
python scripts/paper/run_single_level.py configs/paper/L3_independent_zones_dispatch.yaml
```

Expected output directory:
```
outputs/paper_results/
  └── L3_independent_zones_results.csv
```

---

### Step 3: Compare Results

```python
import pandas as pd

# Load original (fractioned) vs. new (independent) results
l3_frac = pd.read_csv('outputs/paper_results/L3_results.csv')
l3_indep = pd.read_csv('outputs/paper_results/L3_independent_zones_results.csv')

# Compare total cost
print(f"L3 (fractioned):    €{l3_frac['total_cost'].iloc[0]:,.0f}")
print(f"L3 (independent):   €{l3_indep['total_cost'].iloc[0]:,.0f}")
print(f"Difference:         {100*(l3_indep['total_cost'].iloc[0] - l3_frac['total_cost'].iloc[0])/l3_frac['total_cost'].iloc[0]:.1f}%")

# Compare dispatch patterns
print("\nHP utilization:")
print(f"  Fractioned:     {l3_frac['hp_output_mwh'].sum():.0f} MWh/year")
print(f"  Independent:    {l3_indep['hp_output_mwh'].sum():.0f} MWh/year")
```

---

## Understanding the Differences

### Before (Demand Fractions):

```yaml
zone_01:
  type: consumer
  demand_fraction: 0.06        # Zone gets 6% of global demand
  demand:
    column: "waermebedarf_MWth"
```

**Result**:
- Zone 01 = `waermebedarf_MWth[t] × 0.06`
- All zones follow **same temporal pattern** (just different scales)
- Unrealistic — real zones have independent demand drivers

---

### After (Independent Demands):

```yaml
zone_01:
  type: consumer
  demand:
    column: "zone_01_demand_MWth"  # Zone reads its own timeseries
```

**Result**:
- Zone 01 = `zone_01_demand_MWth[t]` (full independent timeseries)
- Each zone can have **different peak times** and patterns
- Realistic — reflects heterogeneous demand (industrial, residential, etc.)

---

## Code Changes Summary

### 1. Config Parser (calion/config/unified_config.py)

**Changed**: Defaults `demand_fraction` to 1.0 when not specified

```python
# BEFORE:
demand_fraction = raw.get("demand_fraction")

# AFTER:
demand_fraction = raw.get("demand_fraction", 1.0)  # Default to 100%
```

**Why**: Allows per-node demands to be used at 100% scale without explicit fractions.

---

### 2. Model Systems (NO CHANGES NEEDED!)

✅ **Good news**: The model already supports per-node demands!

In `calion/models/system_builder.py` and `calion/models/blocks/thermal_node.py`:
- Per-node demand parameters (`heatd_zone_01`, `heatd_zone_02`, etc.) are already created
- System preferentially uses per-node params over global demand
- Demand fraction is applied as a multiplier (set to 1.0 to disable scaling)

---

## Files Modified

```
calion/
  config/
    unified_config.py          ← +2 lines (demand_fraction default)
    
scripts/
  generate_zone_demands.py     ← NEW (zone demand generator)

configs/paper/
  L3_independent_zones_dispatch.yaml  ← NEW (L3 config with zone columns)

docs/
  INDEPENDENT_ZONE_DEMANDS_GUIDE.md   ← NEW (detailed guide)
```

---

## Key Architecture Points

### Why This Works (No Major Code Changes)

1. **System builder already creates per-node params**: 
   ```python
   # Line 125-145 in system_builder.py
   for nid, node in ucfg.nodes.items():
       actual_col = _find_demand_column(table, node.demand.column)
       setattr(m, f"heatd_{nid}", pyo.Param(...))  # ← Already does this!
   ```

2. **Thermal node blocks already read per-node params**:
   ```python
   # Line 212-230 in thermal_node.py
   _node_heatd_attr = f'heatd_{node_id}'
   if hasattr(model, _node_heatd_attr):
       # ← Already prefers per-node param!
   ```

3. **Demand fraction is applied as multiplier**:
   ```python
   return pyo.value(_h[t]) * demand_fraction  # ← Just multiply by 1.0 to disable
   ```

### Result

✅ Independent zone demands are a **config-driven feature**, not a code change.

The model architecture was already designed to support per-node demands — we just added the ability to omit demand fractions!

---

## Expected Results

**Dispatch Differences**:
- Heat pump operation may shift to align with independent zone peaks
- Network flows change (zones peak at different times)
- Total cost may increase (more complex dispatch) or decrease (better alignment)
- Network losses remain similar (~26 GWh/year)

**Data Changes**:
- Total annual demand: ~517 GWh (conserved)
- Zone demand profiles: Unique per zone (±8% daily, ±5% hourly variation)
- Peak load: May shift from original 76 MW

---

## Next Steps

1. ✅ Generate zone data: `python scripts/generate_zone_demands.py`
2. ✅ Run optimization: `python scripts/paper/run_single_level.py configs/paper/L3_independent_zones_dispatch.yaml`
3. ✅ Compare results vs. standard L3
4. ✅ Update paper with findings if differences are significant (>2%)

---

## Troubleshooting

### Error: "No module named 'zone_XX_demand_MWth'"

**Cause**: Zone demand columns not in CSV file.

**Fix**:
```powershell
python scripts/generate_zone_demands.py  # Regenerate with zone columns
```

### Error: "demand_fraction values sum to..."

**Cause**: Some zones still have explicit fractions in config.

**Fix**: Remove `demand_fraction` lines or set to 1.0:
```yaml
zone_01:
  type: consumer
  # demand_fraction: 0.06  ← DELETE THIS
  demand:
    column: "zone_01_demand_MWth"
```

### Different total cost than L3_detailed_dispatch

**Expected**: Dispatch patterns differ due to independent peaks. ±5–10% cost variation is normal.

**Validate**: Sum of all zone annual demands should ≈ 517 GWh:
```python
import pandas as pd
df = pd.read_csv('data/Import_Data_yearly_zones.csv')
total = sum(df[f'zone_{i:02d}_demand_MWth'].sum() for i in range(1, 24))
print(f"Total zone demand: {total:.1f} GWh")  # Should be ≈517
```

---

## Questions?

See [docs/INDEPENDENT_ZONE_DEMANDS_GUIDE.md](docs/INDEPENDENT_ZONE_DEMANDS_GUIDE.md) for detailed theory and implementation details.
