# MPC Integration Plan - Technical Details

**Goal:** Integrate Model Predictive Control (MPC) with forecast updates into the existing PF/RH workflow system.

**Timeline:** 2-3 weeks
**Complexity:** Medium (builds on existing RH implementation)

---

## 1. Architecture Overview

### Current System (energis/run/rolling_horizon.py)

The framework uses a **clean workflow registration pattern**:

```python
# Line 1022-1027: Existing workflow registration
def _register_default_steps() -> None:
    register_workflow_step("PF", _pf_step)
    register_workflow_step("RH", _rh_step)

_register_default_steps()
```

**Key Components:**
1. **WorkflowContext** (Line 121-131): Carries state between steps
2. **Step Handlers**: Functions like `_pf_step()`, `_rh_step()`
3. **Result Classes**: `ScenarioResult`, `RollingHorizonResult`
4. **Configuration**: Loaded from YAML, passed through context

**Our Extension:**
```python
# Add MPC to the workflow system
register_workflow_step("MPC", _mpc_step)  # ← We'll create this
```

---

## 2. Integration Points

### 2.1 WorkflowContext Extension

**Current (Line 121-131):**
```python
@dataclass
class WorkflowContext:
    """Mutable state shared between workflow steps."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan
    pf_result: Optional[ScenarioResult] = None
    rh_result: Optional[RollingHorizonResult] = None
    design: Optional[DesignData] = None
```

**Extended (NEW):**
```python
@dataclass
class WorkflowContext:
    """Mutable state shared between workflow steps."""

    cfg: Dict[str, Any]
    table: TimeSeriesTable
    dt_h: float
    solver_name: str
    plan: WorkflowPlan
    pf_result: Optional[ScenarioResult] = None
    rh_result: Optional[RollingHorizonResult] = None
    mpc_result: Optional[RollingHorizonResult] = None  # ← ADD THIS
    design: Optional[DesignData] = None
```

**Why `RollingHorizonResult`?**
- MPC uses same window-based structure as RH
- Can reuse result aggregation logic
- Natural fit: MPC is "RH with forecast updates"

---

### 2.2 Configuration Schema

**Add to `configs/base.yaml`:**

```yaml
scenario:
  run_mode: PF_ONLY  # or MPC_ONLY, PF_THEN_MPC
  workflow: ["PF"]   # or ["MPC"], ["PF", "MPC"]
  fix_design: false

  # Existing RH config
  rolling_horizon:
    heat_horizon_hours: 168.0
    step_hours: 24.0
    terminal_policy: free

  # NEW: MPC config
  mpc:
    forecast_method: "persistence"  # or "perfect_noise", "analog"
    forecast_horizon_hours: 168.0  # Same as RH for fair comparison
    update_frequency_hours: 24.0   # How often to update forecast

    # Forecast-specific parameters
    noise_std_dev: 0.10            # For "perfect_noise" method
    analog_window_days: 7          # For "analog" method
    analog_history_days: 365       # Historical data to search
```

**New run modes:**
```python
# In _parse_workflow_plan():
mapping = {
    "PF_ONLY": ["PF"],
    "RH_ONLY": ["RH"],
    "PF_THEN_RH": ["PF", "RH"],
    "MPC_ONLY": ["MPC"],          # ← ADD
    "PF_THEN_MPC": ["PF", "MPC"],  # ← ADD
}
```

---

### 2.3 Module Structure

**New files to create:**

```
energis/
├── run/
│   ├── rolling_horizon.py      # ← EXTEND: Add _mpc_step()
│   └── mpc.py                  # ← NEW: MPC-specific logic
├── forecasting/                # ← NEW MODULE
│   ├── __init__.py
│   ├── base.py                 # ForecastGenerator base class
│   ├── persistence.py          # Naive persistence forecast
│   ├── perfect_noise.py        # Perfect + Gaussian noise
│   └── analog.py               # Historical analog forecast
└── utils/
    └── timeseries.py           # ← EXTEND: Add forecast utilities
```

---

## 3. Implementation Details

### 3.1 Forecast Generator Interface

**File: `energis/forecasting/base.py`**

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from energis.utils.timeseries import TimeSeriesTable

class ForecastGenerator(ABC):
    """Base class for forecast generation methods."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def generate_forecast(
        self,
        historical_data: TimeSeriesTable,
        current_index: int,
        horizon_hours: float,
        dt_h: float,
    ) -> TimeSeriesTable:
        """Generate forecast starting from current_index.

        Parameters
        ----------
        historical_data:
            Full historical time series (contains "true" future data)
        current_index:
            Current time index (start of forecast)
        horizon_hours:
            Forecast horizon in hours
        dt_h:
            Time step in hours

        Returns
        -------
        Forecasted time series for the next horizon_hours
        """
        pass

    @abstractmethod
    def get_method_name(self) -> str:
        """Return human-readable method name for logging."""
        pass
```

---

### 3.2 Persistence Forecast (Simplest)

**File: `energis/forecasting/persistence.py`**

```python
from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run import orchestrator

class PersistenceForecast(ForecastGenerator):
    """Naive persistence: tomorrow = today."""

    def generate_forecast(
        self,
        historical_data: TimeSeriesTable,
        current_index: int,
        horizon_hours: float,
        dt_h: float,
    ) -> TimeSeriesTable:
        """Copy current day's pattern into future."""

        # Calculate number of steps
        horizon_steps = int(horizon_hours / dt_h)
        pattern_steps = min(24 // dt_h, horizon_steps)  # 24h pattern

        # Extract current pattern (last 24 hours)
        pattern_start = max(0, current_index - pattern_steps)
        pattern_end = current_index

        # Build forecast by repeating pattern
        forecast_indices = []
        for i in range(horizon_steps):
            pattern_idx = pattern_start + (i % pattern_steps)
            forecast_indices.append(pattern_idx)

        # Slice and return
        return orchestrator._slice_table(historical_data, forecast_indices)

    def get_method_name(self) -> str:
        return "Persistence (Naive)"
```

**Why this works:**
- Simplest possible forecast
- Repeats yesterday's pattern
- Good baseline to show MPC improvement over RH

---

### 3.3 Perfect + Noise Forecast

**File: `energis/forecasting/perfect_noise.py`**

```python
import numpy as np
from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run import orchestrator

class PerfectNoiseForecast(ForecastGenerator):
    """Perfect forecast with additive Gaussian noise."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.std_dev = config.get('mpc', {}).get('noise_std_dev', 0.10)
        self.seed = config.get('mpc', {}).get('random_seed', 42)
        self.rng = np.random.RandomState(self.seed)

    def generate_forecast(
        self,
        historical_data: TimeSeriesTable,
        current_index: int,
        horizon_hours: float,
        dt_h: float,
    ) -> TimeSeriesTable:
        """Use true future data + noise."""

        horizon_steps = int(horizon_hours / dt_h)
        end_index = min(current_index + horizon_steps, len(historical_data))

        # Get perfect forecast
        indices = list(range(current_index, end_index))
        forecast = orchestrator._slice_table(historical_data, indices)

        # Add noise to demand series
        if 'demand_mw' in forecast.series:
            demand = np.array(forecast.series['demand_mw'])
            noise = self.rng.normal(0, self.std_dev * demand.mean(), len(demand))
            forecast.series['demand_mw'] = (demand + noise).clip(min=0).tolist()

        # Add noise to prices (lognormal is better for prices)
        if 'price_elec_eur_mwh' in forecast.series:
            price = np.array(forecast.series['price_elec_eur_mwh'])
            noise = self.rng.lognormal(0, self.std_dev, len(price))
            forecast.series['price_elec_eur_mwh'] = (price * noise).clip(min=0).tolist()

        return forecast

    def get_method_name(self) -> str:
        return f"Perfect + Noise (σ={self.std_dev:.0%})"
```

**Why this is useful:**
- Controls forecast quality precisely
- Can vary noise level for sensitivity studies
- Shows value of forecast accuracy

---

### 3.4 MPC Step Implementation

**File: `energis/run/rolling_horizon.py` (extend existing file)**

```python
# Add after _rh_step() definition (around line 580)

@dataclass
class _MPCParams:
    """Configuration for MPC with forecast updates."""

    forecast_method: str
    forecast_horizon_hours: float
    update_frequency_hours: float
    config: Dict[str, Any]  # Full config for forecast generator


def _load_mpc_params(cfg: Dict[str, Any]) -> _MPCParams:
    """Extract MPC parameters from merged config."""

    mpc_cfg = cfg.get("scenario", {}).get("mpc", {})

    return _MPCParams(
        forecast_method=mpc_cfg.get("forecast_method", "persistence"),
        forecast_horizon_hours=mpc_cfg.get("forecast_horizon_hours", 168.0),
        update_frequency_hours=mpc_cfg.get("update_frequency_hours", 24.0),
        config=cfg,
    )


def _create_forecast_generator(params: _MPCParams) -> ForecastGenerator:
    """Factory function to create forecast generator."""

    from energis.forecasting.persistence import PersistenceForecast
    from energis.forecasting.perfect_noise import PerfectNoiseForecast

    method = params.forecast_method.lower()

    if method == "persistence":
        return PersistenceForecast(params.config)
    elif method in ("perfect_noise", "perfect_with_noise"):
        return PerfectNoiseForecast(params.config)
    else:
        raise ValueError(f"Unknown forecast method: {params.forecast_method}")


def _mpc_step(context: WorkflowContext) -> None:
    """Model Predictive Control with forecast updates.

    Similar to RH but regenerates forecast at each step based on
    the configured forecast method (persistence, perfect+noise, etc.).
    """

    params = _load_mpc_params(context.cfg)
    fix_design = context.plan.fix_design and context.design is not None

    if context.plan.fix_design and context.design is None:
        logger.warning(
            "Design fixation requested but no PF design data available – "
            "proceeding without fixation."
        )

    # Create forecast generator
    forecast_gen = _create_forecast_generator(params)
    logger.info(f"MPC using forecast method: {forecast_gen.get_method_name()}")

    # Run MPC with forecast updates
    context.mpc_result = _run_mpc(
        base_cfg=context.cfg,
        historical_data=context.table,
        dt_h=context.dt_h,
        solver_name=context.solver_name,
        params=params,
        forecast_gen=forecast_gen,
        design=context.design,
        fix_design=fix_design,
    )

    # Propagate design if RH found one
    if context.mpc_result.design is not None:
        context.design = context.design or context.mpc_result.design
```

---

### 3.5 MPC Runner Implementation

**File: `energis/run/mpc.py` (NEW)**

```python
"""MPC implementation with forecast updates."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Optional, Set
from collections import OrderedDict

from energis.forecasting.base import ForecastGenerator
from energis.utils.timeseries import TimeSeriesTable
from energis.run import orchestrator
from energis.run.rolling_horizon import (
    RollingHorizonResult,
    WindowResult,
    DesignData,
    _MPCParams,
    _initial_soc,
    _storage_enabled,
    _apply_terminal_policy,
    _set_initial_soc,
    _apply_design_fix,
    _solve_scenario,
    _aggregate_rolling_results,
    _hours_to_steps,
    _load_cost_plan,
)

logger = logging.getLogger(__name__)


def _run_mpc(
    base_cfg: Dict[str, Any],
    historical_data: TimeSeriesTable,
    dt_h: float,
    solver_name: str,
    params: _MPCParams,
    forecast_gen: ForecastGenerator,
    design: Optional[DesignData],
    fix_design: bool,
) -> RollingHorizonResult:
    """Run Model Predictive Control with forecast updates.

    Key difference from RH: At each step, we regenerate the forecast
    using the forecast_gen instead of using a static slice of historical_data.

    Parameters
    ----------
    base_cfg:
        Configuration dictionary
    historical_data:
        Full historical data (used to generate forecasts)
    dt_h:
        Time step in hours
    solver_name:
        Solver to use (e.g., 'gurobi', 'glpk')
    params:
        MPC parameters (horizon, update frequency, etc.)
    forecast_gen:
        Forecast generator instance
    design:
        Optional pre-computed design to fix
    fix_design:
        Whether to fix the design

    Returns
    -------
    Aggregated MPC result
    """

    n = len(historical_data)
    if n == 0:
        empty_series: OrderedDict[str, List[float]] = OrderedDict()
        return RollingHorizonResult(historical_data, empty_series, {}, [], design)

    # Calculate step sizes
    horizon_steps = _hours_to_steps(params.forecast_horizon_hours, dt_h, "MPC_HORIZON")
    update_steps = _hours_to_steps(params.update_frequency_hours, dt_h, "MPC_UPDATE")

    if update_steps > horizon_steps:
        raise ValueError("MPC update frequency must not exceed forecast horizon")

    # Initialize aggregation
    aggregated_indices: List[int] = []
    aggregated_series: OrderedDict[str, List[float]] = OrderedDict()
    aggregated_costs: Dict[str, float] = {}
    windows: List[WindowResult] = []

    design_state = design
    cost_plan = _load_cost_plan(base_cfg, fix_design)
    once_costs: Set[str] = set()

    soc_next = _initial_soc(base_cfg)
    base_storage_enabled = _storage_enabled(base_cfg)

    # MPC main loop: update forecast at each step
    current_index = 0
    window_idx = 0

    logger.info(
        f"Starting MPC: horizon={params.forecast_horizon_hours}h, "
        f"update_freq={params.update_frequency_hours}h, n={n} steps"
    )

    while current_index < n:
        # 1. Generate forecast from current position
        logger.debug(f"MPC window {window_idx}: current_index={current_index}/{n}")

        forecast_table = forecast_gen.generate_forecast(
            historical_data=historical_data,
            current_index=current_index,
            horizon_hours=params.forecast_horizon_hours,
            dt_h=dt_h,
        )

        # 2. Prepare window configuration
        window_cfg = copy.deepcopy(base_cfg)

        # Apply terminal policy
        terminal_policy = params.config.get("scenario", {}).get("rolling_horizon", {}).get("terminal_policy", "free")
        if terminal_policy:
            _apply_terminal_policy(window_cfg, terminal_policy)

        # Set initial SOC from previous window
        if soc_next is not None and base_storage_enabled:
            _set_initial_soc(window_cfg, soc_next)

        # Fix design if requested
        should_fix_design = bool(
            design_state is not None and (fix_design or (design is None and window_idx > 0))
        )
        if should_fix_design:
            window_cfg = _apply_design_fix(window_cfg, design_state)

        # 3. Solve optimization with forecast
        window_result = _solve_scenario(
            forecast_table,
            window_cfg,
            dt_h,
            solver_name,
        )

        # 4. Extract design from first window (if not fixed)
        if window_idx == 0 and design_state is None:
            from energis.run.rolling_horizon import _extract_design_data
            design_state = _extract_design_data(window_result.summary)

        # 5. Extract committed portion (first update_steps)
        commit_steps = min(update_steps, len(forecast_table), n - current_index)
        committed_indices = list(range(current_index, current_index + commit_steps))

        # Store window result
        window_res = WindowResult(
            table=forecast_table,
            series=window_result.series,
            summary=window_result.summary,
            costs=window_result.costs,
            solver=window_result.solver,
            start_index=current_index,
            commit_steps=commit_steps,
        )
        windows.append(window_res)

        # 6. Aggregate committed portion
        for i, idx in enumerate(committed_indices):
            aggregated_indices.append(idx)
            for key, values in window_result.series.items():
                if i < len(values):
                    aggregated_series.setdefault(key, []).append(values[i])

        # 7. Aggregate costs (scale by committed fraction)
        commit_fraction = commit_steps / len(forecast_table) if len(forecast_table) > 0 else 1.0

        for cost_key, cost_val in window_result.costs.items():
            # Investment costs: amortize once
            if cost_key in cost_plan.once_keys and cost_key not in once_costs:
                aggregated_costs[cost_key] = aggregated_costs.get(cost_key, 0.0) + cost_val
                once_costs.add(cost_key)
            # Operational costs: scale by commit fraction
            elif cost_key not in cost_plan.once_keys:
                aggregated_costs[cost_key] = aggregated_costs.get(cost_key, 0.0) + cost_val * commit_fraction

        # 8. Extract final SOC for next window
        if base_storage_enabled and 'TES_E' in window_result.series:
            soc_values = window_result.series['TES_E']
            if commit_steps > 0 and commit_steps <= len(soc_values):
                soc_next = soc_values[commit_steps - 1]

        # 9. Advance to next update
        current_index += commit_steps
        window_idx += 1

        if commit_steps == 0:
            logger.warning(f"MPC stuck at index {current_index}, breaking")
            break

    logger.info(f"MPC completed: {window_idx} windows, {len(aggregated_indices)} committed steps")

    # Build final result
    result_table = orchestrator._slice_table(historical_data, aggregated_indices)

    return RollingHorizonResult(
        table=result_table,
        series=aggregated_series,
        costs=aggregated_costs,
        windows=windows,
        design=design_state,
    )
```

**Key Differences from RH:**
1. **Forecast regeneration**: `forecast_gen.generate_forecast()` at each step
2. **Same aggregation logic**: Reuses RH cost aggregation
3. **Same result type**: Returns `RollingHorizonResult` for easy comparison

---

### 3.6 Registration

**File: `energis/run/rolling_horizon.py`**

Update the registration function (around line 1022):

```python
def _register_default_steps() -> None:
    register_workflow_step("PF", _pf_step)
    register_workflow_step("RH", _rh_step)
    register_workflow_step("MPC", _mpc_step)  # ← ADD THIS LINE

_register_default_steps()
```

---

## 4. Usage Examples

### 4.1 Configuration File

**File: `configs/scenarios/mpc_persistence.scenario.yaml` (NEW)**

```yaml
scenario:
  title: MPC with Persistence Forecast
  run_mode: MPC_ONLY
  workflow:
    - MPC

  mpc:
    forecast_method: "persistence"
    forecast_horizon_hours: 168.0  # 1 week
    update_frequency_hours: 24.0   # Daily updates

  horizon:
    type: full_year
    year: 2023
```

**File: `configs/scenarios/pf_then_mpc.scenario.yaml` (NEW)**

```yaml
scenario:
  title: PF Design with MPC Operation
  run_mode: PF_THEN_MPC
  workflow:
    - PF
    - MPC
  fix_design: true

  mpc:
    forecast_method: "perfect_noise"
    forecast_horizon_hours: 168.0
    update_frequency_hours: 24.0
    noise_std_dev: 0.10  # 10% forecast error
    random_seed: 42

  horizon:
    type: full_year
    year: 2023
```

### 4.2 Command Line

```bash
# Run MPC only
python -m energis.run.rolling_horizon \
    configs/base.yaml \
    configs/tech_catalog.yaml \
    configs/sites/default.site.yaml \
    configs/systems/baseline.system.yaml \
    configs/scenarios/mpc_persistence.scenario.yaml

# Run PF then MPC
python -m energis.run.rolling_horizon \
    configs/base.yaml \
    configs/tech_catalog.yaml \
    configs/sites/default.site.yaml \
    configs/systems/baseline.system.yaml \
    configs/scenarios/pf_then_mpc.scenario.yaml

# Override forecast method
python -m energis.run.rolling_horizon \
    configs/base.yaml \
    ... \
    --run-mode MPC_ONLY \
    --mpc-forecast-method perfect_noise \
    --mpc-noise-std-dev 0.15
```

### 4.3 Python API

```python
from energis.run.rolling_horizon import run_workflow

# Run MPC
result = run_workflow(
    config_paths=[
        "configs/base.yaml",
        "configs/tech_catalog.yaml",
        "configs/sites/default.site.yaml",
        "configs/systems/baseline.system.yaml",
        "configs/scenarios/mpc_persistence.scenario.yaml",
    ]
)

# Access results
mpc_result = result.mpc_result
print(f"Total cost: {sum(mpc_result.costs.values()):.2f} EUR")
print(f"Number of windows: {len(mpc_result.windows)}")
print(f"Design: {mpc_result.design}")
```

---

## 5. Testing Strategy

### 5.1 Unit Tests

**File: `tests/test_mpc.py` (NEW)**

```python
import pytest
from energis.run.rolling_horizon import run_workflow
from energis.forecasting.persistence import PersistenceForecast
from energis.forecasting.perfect_noise import PerfectNoiseForecast

def test_mpc_persistence_forecast():
    """Test MPC with persistence forecast."""
    result = run_workflow(
        config_paths=[
            "configs/base.yaml",
            "configs/scenarios/mpc_persistence.scenario.yaml",
        ],
        overrides={"scenario": {"horizon": {"type": "week"}}},  # Fast test
    )

    assert result.mpc_result is not None
    assert len(result.mpc_result.windows) > 0
    assert sum(result.mpc_result.costs.values()) > 0


def test_mpc_vs_rh_same_forecast():
    """MPC with perfect forecast should equal RH."""
    # Run RH
    rh_result = run_workflow(
        config_paths=["configs/base.yaml", ...],
        overrides={"scenario": {"workflow": ["RH"]}},
    )

    # Run MPC with perfect (no noise) forecast
    mpc_result = run_workflow(
        config_paths=["configs/base.yaml", ...],
        overrides={
            "scenario": {
                "workflow": ["MPC"],
                "mpc": {"forecast_method": "perfect_noise", "noise_std_dev": 0.0}
            }
        },
    )

    # Costs should be very close
    rh_cost = sum(rh_result.rh_result.costs.values())
    mpc_cost = sum(mpc_result.mpc_result.costs.values())
    assert abs(mpc_cost - rh_cost) / rh_cost < 0.01  # Within 1%


def test_pf_then_mpc_design_fixation():
    """Test PF→MPC workflow with design fixation."""
    result = run_workflow(
        config_paths=[...],
        overrides={
            "scenario": {
                "workflow": ["PF", "MPC"],
                "fix_design": True,
            }
        },
    )

    assert result.pf_result is not None
    assert result.mpc_result is not None
    assert result.design is not None  # From PF

    # MPC should use PF design
    # (Check that capacities match)


def test_forecast_generator_interface():
    """Test forecast generator creates valid forecasts."""
    from energis.utils.timeseries import TimeSeriesTable

    # Create dummy data
    table = TimeSeriesTable(...)

    # Test persistence
    gen = PersistenceForecast({})
    forecast = gen.generate_forecast(table, current_index=24, horizon_hours=168, dt_h=1.0)
    assert len(forecast) == 168

    # Test perfect+noise
    gen = PerfectNoiseForecast({"mpc": {"noise_std_dev": 0.1}})
    forecast = gen.generate_forecast(table, current_index=24, horizon_hours=168, dt_h=1.0)
    assert len(forecast) == 168
```

### 5.2 Integration Tests

**File: `tests/test_mpc_integration.py` (NEW)**

```python
def test_full_year_mpc_persistence():
    """Test full year MPC run with persistence."""
    result = run_workflow(
        config_paths=[
            "configs/base.yaml",
            "configs/tech_catalog.yaml",
            "configs/sites/default.site.yaml",
            "configs/systems/baseline.system.yaml",
            "configs/scenarios/mpc_persistence.scenario.yaml",
        ]
    )

    assert result.mpc_result is not None
    assert len(result.mpc_result.series['demand_mw']) == 8760  # Full year

    # Check all windows solved successfully
    for window in result.mpc_result.windows:
        assert window.solver['termination_condition'] == 'optimal'


def test_mpc_methods_comparison():
    """Compare different MPC forecast methods."""
    base_configs = ["configs/base.yaml", ...]

    results = {}
    for method in ["persistence", "perfect_noise"]:
        result = run_workflow(
            config_paths=base_configs,
            overrides={
                "scenario": {
                    "workflow": ["MPC"],
                    "mpc": {"forecast_method": method}
                }
            }
        )
        results[method] = sum(result.mpc_result.costs.values())

    # Perfect+noise should be better than persistence
    assert results["perfect_noise"] < results["persistence"]
```

---

## 6. Comparison Framework

### 6.1 Benchmark Runner

**File: `energis/comparison/benchmark.py` (NEW)**

```python
"""Benchmark runner for comparing forecast methods."""

from typing import Dict, List, Tuple
import pandas as pd
from energis.run.rolling_horizon import run_workflow

def run_method_comparison(
    base_configs: List[str],
    methods: List[Tuple[str, Dict]],
    num_runs: int = 1,
) -> pd.DataFrame:
    """Run comparison of multiple methods.

    Parameters
    ----------
    base_configs:
        List of config file paths (base, tech_catalog, site, system)
    methods:
        List of (name, override_dict) tuples
        Example: [("PF", {"scenario": {"workflow": ["PF"]}}), ...]
    num_runs:
        Number of repetitions for stochastic methods

    Returns
    -------
    DataFrame with comparison results
    """

    results = []

    for method_name, overrides in methods:
        print(f"Running {method_name}...")

        for run_idx in range(num_runs):
            result = run_workflow(base_configs, overrides)

            # Extract costs
            if result.pf_result:
                costs = result.pf_result.costs
            elif result.rh_result:
                costs = result.rh_result.costs
            elif result.mpc_result:
                costs = result.mpc_result.costs
            else:
                continue

            total_cost = sum(costs.values())

            results.append({
                'method': method_name,
                'run': run_idx,
                'total_cost_eur': total_cost,
                'capex_eur': costs.get('cost_capex', 0),
                'opex_eur': total_cost - costs.get('cost_capex', 0),
                **costs,  # Include all cost components
            })

    return pd.DataFrame(results)


# Example usage
if __name__ == "__main__":
    methods = [
        ("PF", {"scenario": {"workflow": ["PF"]}}),
        ("RH", {"scenario": {"workflow": ["RH"]}}),
        ("PF→RH", {"scenario": {"workflow": ["PF", "RH"], "fix_design": True}}),
        ("MPC-Persistence", {"scenario": {"workflow": ["MPC"], "mpc": {"forecast_method": "persistence"}}}),
        ("MPC-Noise-10%", {"scenario": {"workflow": ["MPC"], "mpc": {"forecast_method": "perfect_noise", "noise_std_dev": 0.10}}}),
        ("PF→MPC", {"scenario": {"workflow": ["PF", "MPC"], "fix_design": True, "mpc": {"forecast_method": "persistence"}}}),
    ]

    df = run_method_comparison(
        base_configs=[
            "configs/base.yaml",
            "configs/tech_catalog.yaml",
            "configs/sites/default.site.yaml",
            "configs/systems/baseline.system.yaml",
        ],
        methods=methods,
    )

    # Print comparison
    print("\n=== Method Comparison ===")
    print(df.groupby('method')['total_cost_eur'].describe())

    # Save results
    df.to_csv("exports/method_comparison.csv", index=False)
```

---

## 7. Implementation Checklist

### Week 1: Core Implementation
- [ ] Create `energis/forecasting/` module
- [ ] Implement `ForecastGenerator` base class
- [ ] Implement `PersistenceForecast`
- [ ] Implement `PerfectNoiseForecast`
- [ ] Extend `WorkflowContext` with `mpc_result`
- [ ] Implement `_MPCParams` dataclass
- [ ] Implement `_mpc_step()` function
- [ ] Create `energis/run/mpc.py` with `_run_mpc()`
- [ ] Register MPC workflow step
- [ ] Add MPC to run_mode mapping

### Week 2: Testing & Validation
- [ ] Write unit tests for forecast generators
- [ ] Write unit tests for MPC step
- [ ] Write integration tests (full year)
- [ ] Validate MPC vs RH equivalence (perfect forecast)
- [ ] Test PF→MPC workflow
- [ ] Add CLI arguments for MPC parameters
- [ ] Update documentation

### Week 3: Comparison & Analysis
- [ ] Create benchmark runner
- [ ] Run PF vs RH vs MPC comparison
- [ ] Create comparison plots
- [ ] Write comparison summary
- [ ] Create example configs
- [ ] Add Jupyter notebook example

---

## 8. Expected Results

### 8.1 Performance Metrics

| Method | Total Cost | vs. PF | Solve Time | Windows |
|--------|------------|--------|------------|---------|
| PF | 100,000 EUR | 0% (baseline) | 5 min | 1 |
| RH | 110,000 EUR | +10% | 15 min | 365 |
| PF→RH | 105,000 EUR | +5% | 20 min | 1 + 365 |
| MPC-Perfect | 110,000 EUR | +10% | 15 min | 365 |
| MPC-Noise-10% | 108,000 EUR | +8% | 15 min | 365 |
| MPC-Persistence | 112,000 EUR | +12% | 15 min | 365 |
| PF→MPC | 106,000 EUR | +6% | 20 min | 1 + 365 |

**Key Insights:**
- MPC with good forecast (10% noise) performs 20% better than naive persistence
- PF→MPC slightly better than PF→RH (adaptive operation)
- MPC computational cost same as RH (both solve 365 windows)

---

## 9. Next Steps After MPC

Once MPC is working and validated:

**Option A: Publish with MPC**
- 4 methods: PF, RH, PF→RH, MPC
- Story: Forecast quality impact
- Timeline: +2-3 weeks for paper writing

**Option B: Add Scenario-Based RH**
- 5 methods: Add SB-RH
- Story: Deterministic vs stochastic
- Timeline: +3-4 weeks

**Decision Point:** Review MPC results and decide

---

## 10. File Summary

**New Files:**
```
energis/forecasting/__init__.py           # Module init
energis/forecasting/base.py              # ForecastGenerator interface
energis/forecasting/persistence.py       # Persistence forecast
energis/forecasting/perfect_noise.py     # Perfect + noise
energis/run/mpc.py                       # MPC runner
energis/comparison/benchmark.py          # Benchmark utilities
tests/test_mpc.py                        # Unit tests
tests/test_mpc_integration.py            # Integration tests
configs/scenarios/mpc_persistence.scenario.yaml
configs/scenarios/pf_then_mpc.scenario.yaml
```

**Modified Files:**
```
energis/run/rolling_horizon.py           # Add _mpc_step(), _MPCParams
```

**Total Lines of Code:** ~800-1000 LOC

---

## Conclusion

MPC integrates **cleanly** into the existing architecture:
- ✅ Reuses workflow registration pattern
- ✅ Reuses RH result aggregation logic
- ✅ Minimal changes to existing code
- ✅ Easy to extend with more forecast methods
- ✅ Fair comparison (same cost accounting)

**Ready to implement?** Start with Week 1 checklist!
