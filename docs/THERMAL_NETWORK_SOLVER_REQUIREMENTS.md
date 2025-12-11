# Thermal Network Solver Requirements

## Problem Classification

The thermal network model with explicit temperature and flow modeling is a **Mixed Integer Quadratic Program (MIQP)** or **Mixed Integer Nonlinear Program (MINLP)**, not a pure MILP.

### Why MIQP?

The energy balance equation in pipes creates **bilinear terms**:

```python
# Temperature drop constraint:
m_dot[t] * cp * (T_in[t] - T_out[t]) == Q_loss[t] * 1000
```

This multiplies two decision variables:
- `m_dot[t]` (mass flow rate)
- `(T_in[t] - T_out[t])` (temperature difference)

The product `m_dot[t] * (T_in - T_out)` is **bilinear**, making the problem MIQP.

Similarly, when pipe upgrades are enabled, the heat loss calculation creates bilinear terms:
```python
# Heat loss with insulation choice:
Q_loss = insulation_choice[type] * U_value * Length * (T_avg - T_ground)
```

Where `insulation_choice` is binary and `T_avg` involves decision variables.

## Supported Solvers

| Solver | Type | Status | Notes |
|--------|------|--------|-------|
| **Gurobi** | Commercial MIQP | ✅ Recommended | Used in baseline, handles bilinear terms |
| **CPLEX** | Commercial MIQP | ✅ Supported | Alternative commercial solver |
| **SCIP** | Open-source MINLP | ⚠️ Possible | Free, but setup complex |
| **CBC** | Open-source MILP | ❌ Not supported | Cannot handle bilinear terms |
| **GLPK** | Open-source MILP | ❌ Not supported | Linear programs only |

## Solutions and Workarounds

### Option 1: Use Gurobi (Recommended)

The EnerGIS baseline already uses Gurobi. Simply ensure Gurobi is installed and licensed:

```bash
# Test Gurobi availability
python -c "import pyomo.environ as pyo; print(pyo.SolverFactory('gurobi').available())"
```

### Option 2: Linearization (Future Work)

To support free solvers like CBC/GLPK, the model would need linearization:

1. **Fixed Flow Rates**: Assume constant mass flow (not optimal for brownfield)
2. **Piecewise Linear Approximation**: Discretize flow/temperature relationship
3. **McCormick Envelopes**: Add auxiliary variables and big-M constraints
4. **Simplified Heat Loss**: Use fixed temperature assumptions

**Complexity**: Significant model redesign required.

### Option 3: Use SCIP (Open-source MINLP)

SCIP can handle nonlinear constraints but requires:
- Complex installation
- Potentially slower solve times
- Less mature than Gurobi

## Current Test Status

### Configuration Fixes Applied

1. ✅ Fixed import path for `StratifiedStorageBlock`
2. ✅ Fixed heat pump config structure (added `system:` wrapper)
3. ✅ Added `tech_catalog.yaml` to test loading
4. ✅ Added `cop_fallback: 3.5` to tech catalog
5. ✅ Fixed config_dir path resolution
6. ✅ Installed CBC and GLPK solvers

### Model Build Status

- ✅ Model builds successfully
- ✅ Network topology loads correctly
- ✅ 459 variables, 530 constraints
- ✅ 2 nodes, 1 pipe attached
- ✅ Heat losses integrated
- ❌ Cannot solve with CBC/GLPK due to MIQP formulation

### Test Command

```bash
# Requires Gurobi
python scripts/test_thermal_network.py --hours 24 --solver gurobi
```

## Recommendations

1. **Short-term**: Use Gurobi (already baseline requirement)
2. **Medium-term**: Add SCIP support for open-source option
3. **Long-term**: Implement linearization for CBC/GLPK support

## Impact on Integration

- **Runners**: No changes needed (already use Gurobi)
- **Scenarios**: Compatible with existing infrastructure
- **Dashboard**: Network results will export correctly once solved
- **Stadtbach**: Ready for optimization with Gurobi

## References

- Pyomo MIQP documentation: https://pyomo.readthedocs.io/en/stable/
- Gurobi bilinear terms: https://www.gurobi.com/documentation/
- SCIP nonlinear: https://scipopt.org/

---

**Date**: 2025-12-10
**Author**: Thermal Network Implementation Team
**Status**: Model validated, awaiting Gurobi testing
