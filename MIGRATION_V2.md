# Migration Guide: EnerGIS Framework v2.0

## Overview

Version 2.0 introduces a **unified, workflow-based API** that replaces the legacy `orchestrator.run_all()` approach. This migration provides:

- ✅ **Consistent API**: Single entry point for all scenarios (PF, RH, MPC)
- ✅ **Better organization**: Scenarios fully controlled via config files
- ✅ **No duplicate work**: Efficient single-pass execution
- ✅ **Backwards compatible**: Old code continues to work (with deprecation warnings)

---

## Quick Migration

### Old Code (Deprecated)
```python
from energis.run.orchestrator import run_all

result = run_all(config_paths)
# Results available in result['scenario_xlsx'], result['costs'], etc.
```

### New Code (Recommended)
```python
from energis.run import rolling_horizon as rh

workflow = rh.run_workflow(config_paths)
result = rh.export_workflow_results(workflow)
# Same result structure as before
```

---

## What Changed?

### 1. Configuration Structure

**Before v2.0:**
- `base.yaml` contained scenario-specific settings (`run_mode`, `fix_design`, etc.)
- Mixing of technical and scenario concerns

**After v2.0:**
- `base.yaml` contains **only** technical defaults (solver, dt_h, costs, grid)
- **All scenario settings** moved to `configs/scenarios/*.scenario.yaml`
- Clear separation of concerns

### Example: base.yaml (v2.0)

```yaml
# ============================================================================
# BASE CONFIGURATION
# ============================================================================
# This file contains ONLY technical defaults and global parameters.
# Scenario-specific settings (run_mode, workflows, etc.) belong in
# configs/scenarios/*.scenario.yaml
# ============================================================================

run:
  dt_h: 1.0
  solver: gurobi
  solver_options:
    MIPGap: 0.02
    TimeLimit: 3600
    Threads: 0

costs:
  include_gridcost_in_energy: true
  co2_price_eur_per_t: 100.0

grid:
  max_import_mw: 200.0
  max_export_mw: 100.0
```

### 2. Scenario Files

All scenario files must now include complete workflow configuration:

```yaml
scenario:
  title: "Perfect Forecast Full Year"
  run_mode: PF_ONLY
  workflow:
    - PF
  fix_design: false
  rolling_horizon:
    heat_horizon_hours: 168.0
    step_hours: 24.0
    terminal_policy: free
  horizon:
    type: full_year
    year: 2023
    enforce: true
```

### 3. API Migration

#### Notebooks

**Before:**
```python
from energis.run.orchestrator import run_all

res = run_all(cfg_paths, overrides=overrides)
# res contains exports and costs
```

**After:**
```python
from energis.run import rolling_horizon as rh

workflow = rh.run_workflow(cfg_paths, overrides=overrides)
res = rh.export_workflow_results(workflow)
# Same result structure
```

#### Python Scripts

**Before:**
```python
from energis.run.orchestrator import run_all

result = run_all([
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/mysite.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_only.scenario.yaml",
])

print(f"Total costs: {result['costs']['objective.OBJ_value_EUR']}")
```

**After:**
```python
from energis.run import rolling_horizon as rh

workflow = rh.run_workflow([
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/mysite.site.yaml",
    "configs/systems/baseline.system.yaml",
    "configs/scenarios/pf_only.scenario.yaml",
])

result = rh.export_workflow_results(workflow)

print(f"Total costs: {result['costs']['objective.OBJ_value_EUR']}")
print(f"Workflow steps: {workflow.plan.steps}")
```

---

## Benefits of v2.0

### 1. Unified Workflow API

**All scenarios** use the same API:
- `PF_ONLY`: Perfect Forecast only
- `RH_ONLY`: Rolling Horizon only
- `MPC_ONLY`: Model Predictive Control
- `PF_THEN_RH`: PF for design, then RH operation
- `PF_THEN_MPC`: PF for design, then MPC operation

### 2. No More Duplicate Work

**Before (v1.x):**
```python
# runner.ipynb did this:
workflow = rh.run_workflow(CONFIG_PATHS)        # 16 minutes
export_meta = orchestrator.run_all(CONFIG_PATHS)  # +1 minute (duplicate!)
# Total: 17 minutes
```

**After (v2.0):**
```python
workflow = rh.run_workflow(CONFIG_PATHS)           # 16 minutes
result = rh.export_workflow_results(workflow)      # +0 seconds (reuses workflow)
# Total: 16 minutes
```

### 3. Better Organization

**Scenario files** are now the **single source of truth** for workflow configuration:

```bash
configs/scenarios/
├── perfect_forecast_full_year.scenario.yaml   # PF_ONLY
├── rolling_horizon_only.scenario.yaml         # RH_ONLY
├── pf_then_rh.workflow.scenario.yaml          # PF_THEN_RH
├── mpc_persistence.scenario.yaml              # MPC_ONLY
└── pf_then_mpc.scenario.yaml                  # PF_THEN_MPC
```

---

## Backwards Compatibility

The old API continues to work, but shows deprecation warnings:

```python
from energis.run.orchestrator import run_all

# This works but shows:
# DeprecationWarning: orchestrator.run_all() is deprecated and will be
# removed in version 3.0. Use rolling_horizon.run_workflow() instead.
result = run_all(config_paths)
```

**Under the hood**, `run_all()` now delegates to the new workflow API:

```python
def run_all(config_paths, overrides=None):
    # Shows deprecation warning
    workflow = rh.run_workflow(config_paths, overrides=overrides)
    result = rh.export_workflow_results(workflow)
    return result
```

---

## Migration Checklist

- [ ] Review `configs/base.yaml` and remove scenario-specific settings
- [ ] Ensure all `configs/scenarios/*.yaml` have complete workflow configuration
- [ ] Update notebooks to use `rh.run_workflow()` + `rh.export_workflow_results()`
- [ ] Update Python scripts to use new API
- [ ] Test scenarios still run correctly
- [ ] Update documentation/README

---

## FAQ

### Q: Do I need to migrate immediately?

**A:** No. The old API continues to work. However, we recommend migrating to benefit from:
- Cleaner code
- Better performance (no duplicate work)
- Access to new features (MPC, etc.)

### Q: What if my custom code imports orchestrator?

**A:** It will continue to work but show deprecation warnings. Plan to migrate before v3.0.

### Q: Where did `pf_design_json` go in the result?

**A:** It's now `design_json`. The new export function uses consistent naming.

### Q: How do I suppress the deprecation warning temporarily?

**A:**
```python
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    result = orchestrator.run_all(config_paths)
```

### Q: When will the old API be removed?

**A:** Version 3.0 (tentative: Q4 2025). You'll have plenty of time to migrate.

---

## Support

For questions or issues:
- GitHub Issues: https://github.com/LukasRuess98/Planing-Framework-for-Heat/issues
- Documentation: See `README.md` and `docs/` folder

---

**Last updated:** 2025-11-24
**Version:** 2.0.0
