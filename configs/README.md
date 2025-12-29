# Configuration System Guide

**NEW:** Modular config structure with inheritance support! 🎉

## 🚀 Quick Start

### Simple: Use a Preset

```bash
# Quick test (1 week, baseline system)
python -m energis.run configs/presets/quick_test.yaml

# Production run (RH with full system)
python -m energis.run configs/presets/rh_full_system.yaml

# Storage investment study
python -m energis.run configs/presets/storage_study.yaml

# Heat pump optimization
python -m energis.run configs/presets/hp_optimization.yaml
```

### Advanced: Custom Composition

```bash
# Mix & match configs as needed
python -m energis.run \
  configs/00_base/solver.yaml \
  configs/01_tech/fuels.yaml \
  configs/02_site/stadtbach/data_source.yaml \
  configs/03_systems/full.yaml \
  configs/04_scenarios/rh_q1_2023.yaml
```

---

## 📁 Folder Structure

```
configs/
├── 00_base/                    # Global defaults (solver, costs, grid)
│   ├── solver.yaml             # Gurobi settings
│   ├── costs.yaml              # Economic parameters
│   └── grid.yaml               # Grid limits and tariffs
│
├── 01_tech/                    # Technology parameters
│   ├── fuels.yaml              # Fuel prices & emissions
│   ├── generators.yaml         # Generator efficiencies
│   ├── heat_pumps.yaml         # HP COP, investment defaults
│   └── storage.yaml            # Storage investment defaults
│
├── 02_site/                    # Site-specific data
│   └── stadtbach/
│       ├── data_source.yaml    # Excel file + column mappings
│       └── assets.yaml         # Installed assets (brownfield)
│
├── 03_systems/                 # System configurations
│   ├── baseline.yaml           # Existing assets only
│   ├── with_storage.yaml       # + Thermal storage
│   ├── with_hp.yaml            # + Heat pumps
│   └── full.yaml               # All technologies
│
├── 04_scenarios/               # Optimization scenarios
│   ├── test_1week.yaml         # Quick test (PF, 1 week)
│   ├── rh_q1_2023.yaml         # RH Q1 2023
│   └── full_year_2023.yaml     # Full year PF
│
├── 05_networks/                # Network topologies
│   └── brownfield.yaml         # District heating network
│
├── presets/                    # Pre-composed configurations
│   ├── quick_test.yaml         # Fast development test
│   ├── rh_full_system.yaml     # Production RH run
│   ├── storage_study.yaml      # Storage optimization
│   └── hp_optimization.yaml    # Heat pump sizing
│
└── _deprecated/                # Old configs (for reference)
```

---

## 🎨 Config Inheritance with `_extends:`

**NEW FEATURE:** Configs can now inherit from other configs!

### Basic Inheritance

```yaml
# my_config.yaml
_extends: ../00_base/solver.yaml

# Override specific settings
run:
  solver_options:
    TimeLimit: 1800  # Override to 30 minutes
```

### Multiple Parents

```yaml
# Inherit from multiple configs (merged left-to-right)
_extends:
  - ../00_base/solver.yaml
  - ../00_base/costs.yaml
  - ../01_tech/fuels.yaml

# Your custom settings
costs:
  co2_price_eur_per_t: 150.0  # Override CO2 price
```

### How Presets Work

Presets use `_extends:` to compose complete configurations:

```yaml
# configs/presets/quick_test.yaml
_extends:
  - ../00_base/solver.yaml          # Solver defaults
  - ../00_base/costs.yaml           # Cost parameters
  - ../00_base/grid.yaml            # Grid limits
  - ../01_tech/fuels.yaml           # Fuel prices
  - ../01_tech/generators.yaml      # Generator specs
  - ../02_site/stadtbach/data_source.yaml  # Data mapping
  - ../02_site/stadtbach/assets.yaml       # Assets
  - ../03_systems/baseline.yaml     # System config
  - ../04_scenarios/test_1week.yaml # Scenario

# All settings inherited - ready to run!
```

### Circular Dependency Protection

The system automatically detects and prevents circular dependencies:

```yaml
# a.yaml
_extends: b.yaml

# b.yaml
_extends: a.yaml  # ❌ ERROR: Circular dependency!
```

---

## 📝 Creating Custom Configurations

### Option 1: Use a Preset as Template

```bash
# Copy existing preset
cp configs/presets/quick_test.yaml configs/presets/my_custom.yaml

# Edit to add your changes
vim configs/presets/my_custom.yaml
```

### Option 2: Compose from Scratch

```yaml
# configs/my_scenarios/winter_peak.yaml
_extends:
  - configs/00_base/solver.yaml
  - configs/01_tech/fuels.yaml
  - configs/02_site/stadtbach/data_source.yaml
  - configs/03_systems/full.yaml

# Winter scenario
scenario:
  title: "Winter Peak Analysis"
  tag: "winter-2023"
  workflow: [PF]
  horizon:
    type: "date_range"
    start: "2023-12-01 00:00"
    end: "2023-02-28 23:00"

# Higher gas prices for winter
fuels:
  gas:
    price_eur_mwh: 75.0  # Winter peak pricing
```

### Option 3: Override Existing Preset

```yaml
# configs/my_scenarios/quick_test_custom.yaml
_extends: configs/presets/quick_test.yaml

# Just override what you need
run:
  solver_options:
    LogToConsole: 1  # Enable solver output
```

---

## 🎯 Common Use Cases

### 1. Quick Development Test
```bash
python -m energis.run configs/presets/quick_test.yaml
```
- **Time**: ~5-10 minutes
- **Scope**: 1 week (168 hours)
- **System**: Baseline (existing assets only)
- **Purpose**: Fast iteration, debugging

### 2. Full System Optimization
```bash
python -m energis.run configs/presets/rh_full_system.yaml
```
- **Time**: ~1-2 hours
- **Scope**: Q1 2023 (~2500 hours)
- **System**: Full (HP + Storage + investment)
- **Purpose**: Production optimization

### 3. Storage Sizing Study
```bash
python -m energis.run configs/presets/storage_study.yaml
```
- **Time**: ~2-4 hours
- **Scope**: Full year 2023
- **System**: Storage only (no HP)
- **Purpose**: Optimal storage capacity

### 4. Heat Pump Investment Analysis
```bash
python -m energis.run configs/presets/hp_optimization.yaml
```
- **Time**: ~2-4 hours
- **Scope**: Full year 2023
- **System**: 4 HPs with WRG (no storage)
- **Purpose**: Optimal HP sizing

### 5. Custom Solver Settings
```yaml
# fast_solver.yaml
_extends: configs/presets/quick_test.yaml

run:
  solver_options:
    TimeLimit: 300     # 5 minutes
    MIPGap: 0.05       # 5% gap (faster, less optimal)
```

```bash
python -m energis.run fast_solver.yaml
```

---

## 🔍 Configuration Layers

Configs are organized by **change frequency**:

| Layer | Folder | Change Frequency | Examples |
|-------|--------|------------------|----------|
| **Base** | `00_base/` | Rarely | Solver settings, grid limits |
| **Tech** | `01_tech/` | Rarely | Fuel prices, tech specs |
| **Site** | `02_site/` | Rarely | Data sources, existing assets |
| **System** | `03_systems/` | Sometimes | Enabled technologies |
| **Scenario** | `04_scenarios/` | Often | Time periods, workflows |
| **Preset** | `presets/` | Often | Complete use cases |

**Principle**: Lower numbers = change less often

---

## ⚙️ Config Merging Rules

### Precedence (Later Overrides Earlier)

```bash
python -m energis.run file1.yaml file2.yaml file3.yaml
#                      ▲          ▲          ▲
#                      │          │          └─ Highest priority
#                      │          └─ Medium priority
#                      └─ Lowest priority
```

### Deep Merge Behavior

```yaml
# file1.yaml
run:
  solver: gurobi
  solver_options:
    MIPGap: 0.02
    TimeLimit: 3600

# file2.yaml
run:
  solver_options:
    TimeLimit: 1800  # Override only TimeLimit

# Result: MIPGap=0.02, TimeLimit=1800 (merged!)
```

### List Replacement (Not Merge)

```yaml
# parent.yaml
system:
  heat_pumps:
    - id: HP1
    - id: HP2

# child.yaml
system:
  heat_pumps:
    - id: HP3

# Result: Only HP3 (lists are REPLACED, not merged)
```

---

## 🚨 Troubleshooting

### "Column not found" Error
```
KeyError: 'WRG1_Q_MW'
```
**Fix**: Check `02_site/stadtbach/data_source.yaml` column mappings

### "Config not found" Error
```
FileNotFoundError: Config not found
```
**Fix**: Run from project root, or use absolute paths in `_extends:`

### "Circular dependency detected"
```
ValueError: Circular dependency detected: /path/to/config.yaml
```
**Fix**: Remove circular `_extends:` references (A → B → A)

### Solver Infeasibility
```
Problem proven to be infeasible
```
**Common causes:**
1. Wrong WRG column names → No HP capacity
2. Terminal constraint too strict → Check `scenario.horizon.enforce`
3. Investment + terminal conflict → Set `scenario.fix_design: true`

**Debug:**
```bash
# Check merged config
python -c "
from energis.config.merge import load_and_merge
cfg = load_and_merge(['configs/presets/quick_test.yaml'])
print('Merged from:', cfg['meta']['merged_from'])
print('Inheritance:', cfg['meta']['inheritance_enabled'])
"
```

---

## 📖 Best Practices

### 1. **Use Presets for Common Tasks**
❌ Don't: Manually compose 10 configs every time
✅ Do: Create a preset and reuse it

### 2. **Layer Your Overrides**
❌ Don't: Copy entire config files
✅ Do: Use `_extends:` and override only what changes

### 3. **Keep Site Data Separate**
❌ Don't: Hardcode column mappings in scenarios
✅ Do: Define once in `02_site/stadtbach/data_source.yaml`

### 4. **Document Your Presets**
```yaml
# =============================================================================
# PRESET: My Custom Optimization
# =============================================================================
# Purpose: Winter peak analysis with high CO2 prices
# Runtime: ~2 hours
# Use case: Policy sensitivity study
# =============================================================================
_extends: ...
```

### 5. **Test Before Production**
```bash
# Always test with quick_test first
python -m energis.run configs/presets/quick_test.yaml

# Then scale to full scenario
python -m energis.run configs/presets/rh_full_system.yaml
```

---

## 🔄 Migration from Old Structure

### Old Way (Deprecated)
```bash
python -m energis.run configs/stadtbach.yaml
# 245 lines, everything in one file
```

### New Way (Recommended)
```bash
python -m energis.run configs/presets/rh_full_system.yaml
# Modular, reusable, DRY
```

### Migration Steps
1. **Identify your use case** (test, production, study)
2. **Find matching preset** in `presets/`
3. **Test preset**: Run and verify results
4. **Customize if needed**: Create custom config with `_extends:`
5. **Delete old monolithic configs** (optional)

---

## 🆕 What's New

### Phase 2 & 3 Features
- ✅ **Modular structure**: Configs organized by change frequency
- ✅ **Config inheritance**: `_extends:` support
- ✅ **Presets**: Ready-to-use complete configurations
- ✅ **Circular dependency detection**: Prevents config loops
- ✅ **Better documentation**: This guide!

### Removed
- ❌ `stadtbach.yaml` (monolith)
- ❌ `base.yaml` (split into `00_base/*`)
- ❌ `tech_catalog.yaml` (split into `01_tech/*`)
- ❌ Old `scenarios/*.yaml` (replaced with `04_scenarios/*`)
- ❌ Old `systems/*.yaml` (replaced with `03_systems/*`)

**All old configs moved to `_deprecated/` for reference.**

---

## 📚 Further Reading

- **Detailed Analysis**: `docs/config_structure_analysis.md`
- **Code**: `energis/config/merge.py` (inheritance implementation)
- **Examples**: `configs/presets/` (working examples)

---

## 💬 Need Help?

1. **Check presets**: `configs/presets/` has working examples
2. **Read examples**: Each preset is documented
3. **Debug merging**: Use `cfg['meta']['merged_from']` to see what was merged
4. **Ask questions**: Open an issue with config snippet

---

**Happy optimizing! 🚀**
