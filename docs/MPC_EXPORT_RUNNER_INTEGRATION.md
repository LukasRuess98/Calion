# MPC Export & Runner Integration Analysis

**Status:** Infrastructure check for MPC integration
**Date:** 2025-11-18

---

## Executive Summary

✅ **Good News:** Export-Infrastruktur ist bereits generisch und funktioniert für MPC!
⚠️ **Action Needed:** `WorkflowResult` und `run_workflow()` müssen für MPC erweitert werden.

---

## Current State Analysis

### 1. WorkflowResult Structure (energis/run/rolling_horizon.py:457-464)

**Current Implementation:**
```python
@dataclass
class WorkflowResult:
    """Return value for :func:`run_workflow`."""

    config: Dict[str, Any]
    pf_result: Optional[ScenarioResult]
    rh_result: Optional[RollingHorizonResult]
    design: Optional[DesignData]
    plan: WorkflowPlan
```

**Problem:**
- ❌ Kein `mpc_result` Feld
- ❌ Kann MPC-Ergebnisse nicht speichern
- ❌ Exports können nicht auf MPC-Daten zugreifen

---

### 2. run_workflow() Return Statement (energis/run/rolling_horizon.py:521)

**Current Implementation:**
```python
def run_workflow(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> WorkflowResult:
    """Execute the configured workflow (PF, RH or PF→RH)."""  # ← Docstring veraltet!

    # ... execution ...

    return WorkflowResult(
        inputs.cfg,
        context.pf_result,   # ✅ PF enthalten
        context.rh_result,   # ✅ RH enthalten
        # ❌ context.mpc_result FEHLT!
        context.design,
        inputs.plan
    )
```

**Problem:**
- ❌ MPC-Result wird nicht zurückgegeben
- ❌ Selbst wenn `WorkflowContext.mpc_result` gesetzt ist, geht es verloren

---

### 3. Export Infrastructure (energis/io/exporter.py, publication_exporter.py)

**Current Implementation:**
```python
def write_scenario_workbook(
    path: str,
    *,
    meta_sections: Mapping[str, Mapping[str, object]] | None = None,
    timeseries_sections: Sequence[Mapping[str, object]] | None = None,
    cost_sections: Mapping[str, Mapping[str, object]] | None = None,
    design: Mapping[str, object] | None = None,
) -> None:
    # Generische Export-Funktion - arbeitet mit beliebigen Daten!
```

**Analysis:**
- ✅ **Generisch:** Funktionen akzeptieren beliebige Datenstrukturen
- ✅ **Methoden-agnostisch:** Egal ob PF, RH oder MPC - solange Daten korrekt strukturiert
- ✅ **Keine Änderungen nötig!**

---

## Required Changes

### Change 1: Extend WorkflowResult ⭐ CRITICAL

**File:** `energis/run/rolling_horizon.py` (Line 457-464)

**Before:**
```python
@dataclass
class WorkflowResult:
    """Return value for :func:`run_workflow`."""

    config: Dict[str, Any]
    pf_result: Optional[ScenarioResult]
    rh_result: Optional[RollingHorizonResult]
    design: Optional[DesignData]
    plan: WorkflowPlan
```

**After:**
```python
@dataclass
class WorkflowResult:
    """Return value for :func:`run_workflow`."""

    config: Dict[str, Any]
    pf_result: Optional[ScenarioResult]
    rh_result: Optional[RollingHorizonResult]
    mpc_result: Optional[RollingHorizonResult]  # ← ADD THIS
    design: Optional[DesignData]
    plan: WorkflowPlan
```

**Impact:** Minimal - nur ein neues optionales Feld

---

### Change 2: Update run_workflow() Return ⭐ CRITICAL

**File:** `energis/run/rolling_horizon.py` (Line 496-521)

**Before:**
```python
def run_workflow(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> WorkflowResult:
    """Execute the configured workflow (PF, RH or PF→RH)."""

    inputs = _build_workflow_inputs(config_paths, overrides)
    context = WorkflowContext(inputs.cfg, inputs.table, inputs.dt_h, inputs.solver_name, inputs.plan)

    # ... design loading ...

    for step in inputs.plan.steps:
        handler = _STEP_HANDLERS.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        handler(context)

    return WorkflowResult(inputs.cfg, context.pf_result, context.rh_result, context.design, inputs.plan)
```

**After:**
```python
def run_workflow(config_paths: List[str], overrides: Optional[Dict[str, Any]] = None) -> WorkflowResult:
    """Execute the configured workflow (PF, RH, MPC or combinations)."""  # ← Update docstring

    inputs = _build_workflow_inputs(config_paths, overrides)
    context = WorkflowContext(inputs.cfg, inputs.table, inputs.dt_h, inputs.solver_name, inputs.plan)

    # ... design loading ...

    for step in inputs.plan.steps:
        handler = _STEP_HANDLERS.get(step)
        if handler is None:
            raise ValueError(f"Unsupported workflow step: {step}")
        handler(context)

    return WorkflowResult(
        inputs.cfg,
        context.pf_result,
        context.rh_result,
        context.mpc_result,  # ← ADD THIS
        context.design,
        inputs.plan
    )
```

**Impact:** Minimal - nur ein zusätzliches Argument

---

### Change 3: Update _parse_workflow_plan() Mapping (Optional but recommended)

**File:** `energis/run/rolling_horizon.py` (Line 524-549)

**Before:**
```python
def _parse_workflow_plan(scenario_cfg: Mapping[str, Any]) -> WorkflowPlan:
    run_mode = str(scenario_cfg.get("run_mode", "")).strip().upper() or "PF_ONLY"
    workflow = scenario_cfg.get("workflow")

    if workflow is not None:
        # ... existing logic ...
    else:
        mapping = {
            "PF_ONLY": ["PF"],
            "RH_ONLY": ["RH"],
            "PF_THEN_RH": ["PF", "RH"],
            "PF_AND_RH": ["PF", "RH"],
        }
        steps_upper = mapping.get(run_mode, ["PF"])
```

**After:**
```python
def _parse_workflow_plan(scenario_cfg: Mapping[str, Any]) -> WorkflowPlan:
    run_mode = str(scenario_cfg.get("run_mode", "")).strip().upper() or "PF_ONLY"
    workflow = scenario_cfg.get("workflow")

    if workflow is not None:
        # ... existing logic ...
    else:
        mapping = {
            "PF_ONLY": ["PF"],
            "RH_ONLY": ["RH"],
            "PF_THEN_RH": ["PF", "RH"],
            "PF_AND_RH": ["PF", "RH"],
            "MPC_ONLY": ["MPC"],              # ← ADD
            "PF_THEN_MPC": ["PF", "MPC"],     # ← ADD
        }
        steps_upper = mapping.get(run_mode, ["PF"])
```

**Impact:** Enables convenient run_mode shortcuts for MPC

---

## Usage Patterns After Integration

### Pattern 1: Accessing Results

```python
from energis.run.rolling_horizon import run_workflow

# Run workflow
result = run_workflow([
    "configs/base.yaml",
    "configs/scenarios/mpc_persistence.scenario.yaml"
])

# Access method-specific results
if result.pf_result:
    print(f"PF Cost: {sum(result.pf_result.costs.values())}")

if result.rh_result:
    print(f"RH Cost: {sum(result.rh_result.costs.values())}")

if result.mpc_result:  # ← NEW!
    print(f"MPC Cost: {sum(result.mpc_result.costs.values())}")
    print(f"MPC Windows: {len(result.mpc_result.windows)}")
```

---

### Pattern 2: Generic Result Extraction

```python
def get_active_result(workflow_result: WorkflowResult):
    """Extract the 'active' result from workflow regardless of method."""

    # Priority: MPC > RH > PF (last executed wins)
    if workflow_result.mpc_result:
        return workflow_result.mpc_result
    elif workflow_result.rh_result:
        return workflow_result.rh_result
    elif workflow_result.pf_result:
        return workflow_result.pf_result
    else:
        raise ValueError("No results available")

# Usage
result = run_workflow(configs)
active = get_active_result(result)
print(f"Total cost: {sum(active.costs.values())}")
```

---

### Pattern 3: Method Comparison

```python
def compare_methods(workflow_result: WorkflowResult) -> dict:
    """Compare costs across all executed methods."""

    comparison = {}

    if workflow_result.pf_result:
        comparison['PF'] = sum(workflow_result.pf_result.costs.values())

    if workflow_result.rh_result:
        comparison['RH'] = sum(workflow_result.rh_result.costs.values())

    if workflow_result.mpc_result:
        comparison['MPC'] = sum(workflow_result.mpc_result.costs.values())

    return comparison

# Usage
result = run_workflow(
    configs,
    overrides={"scenario": {"workflow": ["PF", "RH", "MPC"]}}
)

costs = compare_methods(result)
print(costs)
# Output: {'PF': 100000, 'RH': 110000, 'MPC': 108000}
```

---

### Pattern 4: Export with Method Identification

```python
from energis.io.exporter import write_scenario_workbook

def export_workflow_result(result: WorkflowResult, outdir: str):
    """Export results with method identification."""

    import os

    # Determine which methods were run
    methods_executed = []
    if result.pf_result:
        methods_executed.append("PF")
    if result.rh_result:
        methods_executed.append("RH")
    if result.mpc_result:
        methods_executed.append("MPC")

    workflow_name = "_".join(methods_executed)

    # Export each method's results
    if result.pf_result:
        _export_single_result(
            result.pf_result,
            os.path.join(outdir, f"{workflow_name}_PF.xlsx"),
            method_name="PF"
        )

    if result.rh_result:
        _export_single_result(
            result.rh_result,
            os.path.join(outdir, f"{workflow_name}_RH.xlsx"),
            method_name="RH"
        )

    if result.mpc_result:
        _export_single_result(
            result.mpc_result,
            os.path.join(outdir, f"{workflow_name}_MPC.xlsx"),
            method_name="MPC"
        )


def _export_single_result(result, path: str, method_name: str):
    """Export a single result (works for PF, RH, MPC)."""

    # Build metadata
    meta_sections = {
        "Method": {
            "name": method_name,
            "total_cost_eur": sum(result.costs.values()),
        }
    }

    # Build timeseries section
    timeseries_sections = [{
        "label": f"{method_name} Results",
        "timestamps": result.table.index,
        "series": result.series,
    }]

    # Build cost section
    cost_sections = {
        "Cost Breakdown": result.costs
    }

    # Extract design if available
    design = None
    if hasattr(result, 'design') and result.design:
        design = {
            "heat_pumps": result.design.heat_pumps if hasattr(result.design, 'heat_pumps') else {},
            "storage": result.design.storage if hasattr(result.design, 'storage') else {},
        }

    # Export using generic function
    write_scenario_workbook(
        path,
        meta_sections=meta_sections,
        timeseries_sections=timeseries_sections,
        cost_sections=cost_sections,
        design=design,
    )
```

---

### Pattern 5: Benchmark Export (All Methods in One File)

```python
def export_method_comparison(result: WorkflowResult, path: str):
    """Export comparison of all methods in a single Excel file."""

    from energis.io.exporter import _write_simple_xlsx
    from collections import OrderedDict

    sheets = OrderedDict()

    # Summary sheet
    summary_rows = [
        ["Method", "Total Cost (EUR)", "CAPEX (EUR)", "OPEX (EUR)", "Solve Time (s)"]
    ]

    if result.pf_result:
        total = sum(result.pf_result.costs.values())
        capex = result.pf_result.costs.get('cost_capex', 0)
        solve_time = result.pf_result.solver.get('time', 0)
        summary_rows.append(["PF", total, capex, total - capex, solve_time])

    if result.rh_result:
        total = sum(result.rh_result.costs.values())
        capex = result.rh_result.costs.get('cost_capex', 0)
        solve_time = sum(w.solver.get('time', 0) for w in result.rh_result.windows)
        summary_rows.append(["RH", total, capex, total - capex, solve_time])

    if result.mpc_result:
        total = sum(result.mpc_result.costs.values())
        capex = result.mpc_result.costs.get('cost_capex', 0)
        solve_time = sum(w.solver.get('time', 0) for w in result.mpc_result.windows)
        summary_rows.append(["MPC", total, capex, total - capex, solve_time])

    sheets["Summary"] = summary_rows

    # Cost breakdown sheet
    cost_rows = [["Cost Component", "PF", "RH", "MPC"]]

    # Get all cost keys
    all_cost_keys = set()
    if result.pf_result:
        all_cost_keys.update(result.pf_result.costs.keys())
    if result.rh_result:
        all_cost_keys.update(result.rh_result.costs.keys())
    if result.mpc_result:
        all_cost_keys.update(result.mpc_result.costs.keys())

    for cost_key in sorted(all_cost_keys):
        pf_val = result.pf_result.costs.get(cost_key, 0) if result.pf_result else 0
        rh_val = result.rh_result.costs.get(cost_key, 0) if result.rh_result else 0
        mpc_val = result.mpc_result.costs.get(cost_key, 0) if result.mpc_result else 0
        cost_rows.append([cost_key, pf_val, rh_val, mpc_val])

    sheets["Cost Breakdown"] = cost_rows

    # Design comparison sheet
    design_rows = [["Component", "PF", "RH", "MPC"]]

    # Heat pump capacities
    if result.design and hasattr(result.design, 'heat_pumps'):
        for hp_id, hp_data in result.design.heat_pumps.items():
            cap = hp_data.get('capacity_mw', 0)
            design_rows.append([f"HP_{hp_id}_capacity_MW", cap, cap, cap])

    # Storage capacity
    if result.design and hasattr(result.design, 'storage'):
        storage_cap = result.design.storage.get('capacity_mwh', 0)
        storage_pow = result.design.storage.get('power_mw', 0)
        design_rows.append(["Storage_capacity_MWh", storage_cap, storage_cap, storage_cap])
        design_rows.append(["Storage_power_MW", storage_pow, storage_pow, storage_pow])

    sheets["Design"] = design_rows

    # Write to Excel
    _write_simple_xlsx(path, sheets)
```

---

## Command Line Interface Updates

### Add MPC CLI Arguments (Optional Enhancement)

**File:** `energis/run/rolling_horizon.py` (Line 1030+)

```python
def main(argv: Optional[Sequence[str]] = None) -> int:
    """Simple command line interface for :mod:`energis.run.rolling_horizon`."""

    parser = argparse.ArgumentParser(description="Run PF/RH/MPC workflows using merged EnerGIS configs")

    # ... existing arguments ...

    parser.add_argument(
        "--run-mode",
        type=_parse_run_mode,
        choices=["PF_ONLY", "RH_ONLY", "PF_THEN_RH", "MPC_ONLY", "PF_THEN_MPC"],  # ← ADD MPC modes
        help="Override scenario.run_mode (env: RUN_MODE)",
    )

    # NEW: MPC-specific arguments
    parser.add_argument(
        "--mpc-forecast-method",
        choices=["persistence", "perfect_noise", "analog"],
        help="MPC forecast method (env: MPC_FORECAST_METHOD)",
    )

    parser.add_argument(
        "--mpc-forecast-horizon-hours",
        type=float,
        help="MPC forecast horizon in hours (env: MPC_FORECAST_HORIZON_HOURS)",
    )

    parser.add_argument(
        "--mpc-update-frequency-hours",
        type=float,
        help="MPC forecast update frequency in hours (env: MPC_UPDATE_FREQUENCY_HOURS)",
    )

    parser.add_argument(
        "--mpc-noise-std-dev",
        type=float,
        help="Standard deviation for perfect_noise forecast (env: MPC_NOISE_STD_DEV)",
    )

    # ... rest of main() ...
```

---

## Example Notebook/Script Usage

### Comparison Script

```python
"""
Compare PF, RH, and MPC methods on the same system.
"""

from energis.run.rolling_horizon import run_workflow
import pandas as pd

# Base configuration files
base_configs = [
    "configs/base.yaml",
    "configs/tech_catalog.yaml",
    "configs/sites/default.site.yaml",
    "configs/systems/baseline.system.yaml",
]

# Method configurations
methods = {
    "PF": {"scenario": {"workflow": ["PF"]}},
    "RH": {"scenario": {"workflow": ["RH"]}},
    "MPC-Persistence": {
        "scenario": {
            "workflow": ["MPC"],
            "mpc": {"forecast_method": "persistence"}
        }
    },
    "MPC-Noise10%": {
        "scenario": {
            "workflow": ["MPC"],
            "mpc": {
                "forecast_method": "perfect_noise",
                "noise_std_dev": 0.10
            }
        }
    },
    "PF→RH": {
        "scenario": {
            "workflow": ["PF", "RH"],
            "fix_design": True
        }
    },
    "PF→MPC": {
        "scenario": {
            "workflow": ["PF", "MPC"],
            "fix_design": True,
            "mpc": {"forecast_method": "persistence"}
        }
    },
}

# Run all methods
results = {}
for method_name, overrides in methods.items():
    print(f"Running {method_name}...")
    result = run_workflow(base_configs, overrides)
    results[method_name] = result

# Extract costs
comparison_data = []
for method_name, result in results.items():
    # Get the active result (last executed method)
    active_result = None
    if result.mpc_result:
        active_result = result.mpc_result
    elif result.rh_result:
        active_result = result.rh_result
    elif result.pf_result:
        active_result = result.pf_result

    if active_result:
        total_cost = sum(active_result.costs.values())
        capex = active_result.costs.get('cost_capex', 0)
        opex = total_cost - capex

        comparison_data.append({
            'Method': method_name,
            'Total Cost (EUR)': total_cost,
            'CAPEX (EUR)': capex,
            'OPEX (EUR)': opex,
        })

# Create comparison table
df_comparison = pd.DataFrame(comparison_data)
df_comparison['Cost vs PF (%)'] = (
    (df_comparison['Total Cost (EUR)'] / df_comparison.loc[0, 'Total Cost (EUR)'] - 1) * 100
)

print("\n=== Method Comparison ===")
print(df_comparison.to_string(index=False))

# Export to CSV
df_comparison.to_csv("exports/method_comparison.csv", index=False)

# Export individual results
for method_name, result in results.items():
    export_workflow_result(result, f"exports/{method_name}/")
```

**Expected Output:**
```
=== Method Comparison ===
     Method  Total Cost (EUR)  CAPEX (EUR)  OPEX (EUR)  Cost vs PF (%)
         PF        100000.00      20000.00    80000.00            0.00
         RH        110000.00      18000.00    92000.00           10.00
MPC-Persistence   112000.00      18000.00    94000.00           12.00
 MPC-Noise10%     108000.00      19000.00    89000.00            8.00
      PF→RH        105000.00      20000.00    85000.00            5.00
     PF→MPC        106000.00      20000.00    86000.00            6.00
```

---

## Testing Checklist

### Unit Tests

```python
def test_workflow_result_has_mpc_field():
    """Ensure WorkflowResult has mpc_result field."""
    from energis.run.rolling_horizon import WorkflowResult

    result = WorkflowResult(
        config={},
        pf_result=None,
        rh_result=None,
        mpc_result=None,  # Should not raise error
        design=None,
        plan=None
    )

    assert hasattr(result, 'mpc_result')


def test_run_workflow_returns_mpc_result():
    """Test that run_workflow returns MPC result."""
    result = run_workflow(
        ["configs/base.yaml", ...],
        overrides={"scenario": {"workflow": ["MPC"]}}
    )

    assert result.mpc_result is not None
    assert isinstance(result.mpc_result, RollingHorizonResult)


def test_export_mpc_result():
    """Test exporting MPC result."""
    result = run_workflow(
        ["configs/base.yaml", ...],
        overrides={"scenario": {"workflow": ["MPC"]}}
    )

    export_path = "test_exports/mpc_result.xlsx"
    export_workflow_result(result, os.path.dirname(export_path))

    assert os.path.exists(export_path)
```

---

## Summary of Required Changes

| File | Change | Lines | Effort | Priority |
|------|--------|-------|--------|----------|
| `energis/run/rolling_horizon.py` | Add `mpc_result` to `WorkflowResult` | ~1 | Trivial | ⭐⭐⭐ Critical |
| `energis/run/rolling_horizon.py` | Update `run_workflow()` return | ~1 | Trivial | ⭐⭐⭐ Critical |
| `energis/run/rolling_horizon.py` | Add MPC run_modes to mapping | ~2 | Trivial | ⭐⭐ High |
| `energis/run/rolling_horizon.py` | Update `run_workflow()` docstring | ~1 | Trivial | ⭐ Low |
| `energis/run/rolling_horizon.py` | Add MPC CLI arguments | ~20 | Easy | ⭐ Optional |
| Examples/notebooks | Add MPC usage examples | ~50 | Medium | ⭐⭐ High |

**Total Code Changes:** ~5 lines critical, ~75 lines total

---

## Migration Path for Existing Code

### Backward Compatibility

The changes are **100% backward compatible**:

```python
# Old code still works
result = run_workflow(["configs/base.yaml", ...])
pf_cost = sum(result.pf_result.costs.values())  # ✅ Still works
rh_cost = sum(result.rh_result.costs.values())  # ✅ Still works

# New code also works
mpc_cost = sum(result.mpc_result.costs.values()) if result.mpc_result else None  # ✅ New!
```

**No breaking changes!** All existing code continues to work.

---

## Conclusion

✅ **Export infrastructure is already generic** - no changes needed!
✅ **Only 2-3 trivial changes required** to `WorkflowResult` and `run_workflow()`
✅ **100% backward compatible** - existing code unaffected
✅ **MPC integrates seamlessly** with existing patterns

**Recommendation:** Make these minimal changes as part of MPC implementation Week 1.

---

**Next Steps:**
1. Implement changes to `WorkflowResult` (1 line)
2. Update `run_workflow()` return (1 line)
3. Add run_mode mappings (2 lines)
4. Test with simple MPC workflow
5. Create example notebook

**Total implementation time:** <30 minutes for runner/export changes!
