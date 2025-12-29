# Configuration Guide

## 🎯 Quick Start

### Option 1: Single File (Simple)
```bash
# Use the monolithic config (works but not recommended)
python -m energis.run configs/stadtbach.yaml
```

### Option 2: Modular (Recommended)
```bash
# Combine multiple configs for flexibility
python -m energis.run \
  configs/tech_defaults.yaml \
  configs/site_stadtbach.yaml \
  configs/scenarios/test_1week_modular.yaml
```

---

## 📁 File Structure

### Current Files

```
configs/
├── tech_defaults.yaml          ⭐ NEW: Solver + Tech parameters (selten ändern)
├── site_stadtbach.yaml         ⭐ NEW: Site data + Assets (selten ändern)
│
├── scenarios/
│   ├── test_1week_modular.yaml ⭐ NEW: Quick test (oft ändern)
│   ├── rh_2023_q1.yaml         ⭐ NEW: RH optimization (oft ändern)
│   ├── one_week.yaml           ⚠️  OLD: Redundant, use test_1week_modular.yaml
│   ├── full_year.yaml          ⚠️  OLD: Redundant
│   └── high_hp_year.yaml       ⚠️  OLD: Redundant
│
├── systems/
│   ├── baseline.yaml           ⚠️  OLD: Broken (wrong column names)
│   └── high_hp.yaml            ⚠️  OLD: Broken
│
├── networks/
│   └── brownfield.yaml         ✅ Network topology (unchanged)
│
├── stadtbach.yaml              ⚠️  DEPRECATED: Monolith (245 lines)
├── base.yaml                   ⚠️  DEPRECATED: Use tech_defaults.yaml
└── tech_catalog.yaml           ⚠️  DEPRECATED: Use tech_defaults.yaml
```

---

## 🔄 Config Merging

Configs are merged **left to right** (later overrides earlier):

```bash
python -m energis.run file1.yaml file2.yaml file3.yaml
#                      ▲          ▲          ▲
#                      │          │          └─ Highest priority (overrides all)
#                      │          └─ Medium priority
#                      └─ Lowest priority (defaults)
```

### Example: Custom Scenario

```bash
# Base defaults + Site data + Custom scenario
python -m energis.run \
  configs/tech_defaults.yaml \      # Solver, grid, tech params
  configs/site_stadtbach.yaml \     # Excel file, column mappings, assets
  configs/scenarios/my_scenario.yaml  # Your custom scenario
```

---

## 📝 Creating New Scenarios

### Minimal Scenario Template

```yaml
# configs/scenarios/my_custom_scenario.yaml

scenario:
  title: "My Custom Scenario"
  tag: "custom"
  workflow: [PF]  # or [RH]

  horizon:
    type: "date_range"
    start: "2023-06-01 00:00"
    end: "2023-06-30 23:00"
    enforce: false

# Override specific settings
run:
  solver_options:
    TimeLimit: 1800  # 30 minutes

# Enable/disable technologies
system:
  heat_pumps:
    - id: HP1
      enabled: true
      # ... HP config ...

  storage:
    enabled: true
    # ... storage config ...
```

### Run Your Scenario

```bash
python -m energis.run \
  configs/tech_defaults.yaml \
  configs/site_stadtbach.yaml \
  configs/scenarios/my_custom_scenario.yaml
```

---

## 🎨 Use Cases

### 1. Quick Development Test
```bash
python -m energis.run \
  configs/tech_defaults.yaml \
  configs/site_stadtbach.yaml \
  configs/scenarios/test_1week_modular.yaml

# Fast: 1 week, PF only, no HP/storage
```

### 2. Full Rolling Horizon Optimization
```bash
python -m energis.run \
  configs/tech_defaults.yaml \
  configs/site_stadtbach.yaml \
  configs/scenarios/rh_2023_q1.yaml

# Production: Q1 2023, RH with storage & HP
```

### 3. Custom Solver Settings
```bash
# Create custom_solver.yaml:
run:
  solver_options:
    TimeLimit: 7200  # 2 hours
    MIPGap: 0.001    # 0.1% gap (higher quality)

# Then merge:
python -m energis.run \
  configs/tech_defaults.yaml \
  custom_solver.yaml \              # Overrides solver settings
  configs/site_stadtbach.yaml \
  configs/scenarios/rh_2023_q1.yaml
```

### 4. Different Sites
```bash
# For a different site, create site_newcity.yaml
# Then use it instead of site_stadtbach.yaml:
python -m energis.run \
  configs/tech_defaults.yaml \
  configs/site_newcity.yaml \       # Different site!
  configs/scenarios/test_1week_modular.yaml
```

---

## ⚠️ Common Pitfalls

### 1. **Wrong Column Names**
```yaml
# ❌ WRONG (old configs)
wrg_capacity_column: WRG1_Q_cap  # Doesn't exist in Excel!

# ✅ CORRECT
wrg_capacity_column: WRG1_Q_MW
```

### 2. **Duplicate Column Mappings**
```yaml
# ❌ WRONG (redundant)
# Don't define site.columns in scenarios - already in site_stadtbach.yaml

# ✅ CORRECT
# Let site_stadtbach.yaml define columns, scenarios just reference them
```

### 3. **Wrong Merge Order**
```bash
# ❌ WRONG ORDER
python -m energis.run \
  configs/scenarios/test.yaml \         # Scenario first
  configs/tech_defaults.yaml            # Defaults overwrite scenario!

# ✅ CORRECT ORDER
python -m energis.run \
  configs/tech_defaults.yaml \          # Defaults first
  configs/scenarios/test.yaml           # Scenario overrides defaults
```

---

## 📋 Migration Guide

### From Old to New

**Old (monolithic):**
```bash
python -m energis.run configs/stadtbach.yaml
```

**New (modular):**
```bash
python -m energis.run \
  configs/tech_defaults.yaml \
  configs/site_stadtbach.yaml \
  configs/scenarios/rh_2023_q1.yaml
```

### Why Migrate?

| Old (stadtbach.yaml) | New (Modular) |
|---------------------|---------------|
| ❌ 245 lines | ✅ 3 small files (~50-80 lines each) |
| ❌ Change one thing → edit 245 lines | ✅ Change one thing → edit 1 file |
| ❌ WRG columns duplicated 4x | ✅ Defined once in site_stadtbach.yaml |
| ❌ Hard to test variations | ✅ Mix & match scenarios easily |
| ❌ Copy-paste errors | ✅ DRY (Don't Repeat Yourself) |

---

## 🔍 Troubleshooting

### "Column not found" Error
```
KeyError: 'WRG1_Q_MW'
```
**Solution:** Check `site_stadtbach.yaml` → `site.columns.wrg1_q_candidates`

### "Config not found" Error
```
FileNotFoundError: Config not found: configs/...
```
**Solution:** Run from project root, or use absolute paths

### Solver Infeasibility
```
Problem proven to be infeasible
```
**Common causes:**
1. Wrong WRG column names → No HP capacity → Infeasible
2. Terminal constraint too strict → Check `scenario.horizon.enforce`
3. Investment + Terminal conflict → Set `scenario.fix_design: true`

**Debug:**
```bash
# Check what configs are actually merged
python -c "
from energis.config.merge import load_and_merge
cfg = load_and_merge([
    'configs/tech_defaults.yaml',
    'configs/site_stadtbach.yaml',
    'configs/scenarios/test_1week_modular.yaml'
])
print('Merged from:', cfg['meta']['merged_from'])
print('Config hash:', cfg['meta']['config_hash'])
"
```

---

## 🚀 Next Steps

1. **Test modular configs:**
   ```bash
   python -m energis.run \
     configs/tech_defaults.yaml \
     configs/site_stadtbach.yaml \
     configs/scenarios/test_1week_modular.yaml
   ```

2. **Create your own scenario:**
   - Copy `configs/scenarios/test_1week_modular.yaml`
   - Modify time range, enabled technologies, etc.
   - Run with tech_defaults + site_stadtbach + your scenario

3. **Deprecate old files:**
   - Stop using `stadtbach.yaml` (monolith)
   - Use modular approach for all new work

4. **Read full analysis:**
   - See `docs/config_structure_analysis.md` for detailed recommendations
