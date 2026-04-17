# PWL Temperature Linearization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded nominal temperatures in MILP mode with load-dependent temperatures computed at model-build time via three switchable methods (fixed, global, pwl), and fix `model_finalizer.py` silently overriding user config.

**Architecture:** A new `temperature_linearization.py` module computes `{t: (T_supply, T_return)}` dicts from demand timeseries at model-build time (pure Python, no Pyomo). `pipe_pair.py` and `thermal_node.py` each call it once and create `pyo.Param` objects from the result — eliminating the separate MILP/non-MILP branching for temperature setup. `network_manager.py` pre-computes total demand and passes it alongside `linearization` config into each pipe/node's enriched config dict.

**Tech Stack:** Python 3.10+, Pyomo, pytest, PyYAML (config only)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `calion/models/blocks/temperature_linearization.py` | **CREATE** | All temperature-method logic: fixed, global, pwl, interpolation |
| `tests/test_temperature_linearization.py` | **CREATE** | Unit tests for all public and private functions |
| `calion/models/model_finalizer.py` | **MODIFY line 299** | Read `milp_linearize` from user config instead of hardcoding `True` |
| `calion/models/network_manager.py` | **MODIFY** `_attach_all_pipes` + `_attach_all_nodes` | Pre-compute demand totals + pass `demand_series`, `peak_demand_mw`, `linearization` config |
| `calion/models/blocks/pipe_pair.py` | **MODIFY lines 203–291** | Replace hardcoded-nominal MILP temp params with `build_temperatures` call |
| `calion/models/blocks/thermal_node.py` | **MODIFY lines 144–374** | Replace hardcoded-nominal MILP T_supply/T_return setup and `dT_nominal` heat_demand with `build_temperatures` |
| `configs/memmingen/Memmingen_L3.yaml` | **MODIFY** | Add `linearization` config block (optional, for testing) |

---

## Task 1: Create `temperature_linearization.py` with failing tests

**Files:**
- Create: `calion/models/blocks/temperature_linearization.py`
- Create: `tests/test_temperature_linearization.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_temperature_linearization.py
import pytest
from calion.models.blocks.temperature_linearization import build_temperatures


TIME_SET = list(range(3))  # t=0,1,2


def _demands(vals):
    return {t: v for t, v in zip(TIME_SET, vals)}


# ── fixed ──────────────────────────────────────────────────────────────────

def test_fixed_returns_nominal():
    temps = build_temperatures('fixed', {}, _demands([0, 50, 100]), 100.0, 100.0, 40.0, TIME_SET)
    for t in TIME_SET:
        assert temps[t][0] == 100.0
        assert temps[t][1] == 40.0


def test_fixed_is_default_when_method_empty():
    temps = build_temperatures('', {}, _demands([0, 50, 100]), 100.0, 80.0, 35.0, TIME_SET)
    for t in TIME_SET:
        assert temps[t] == (80.0, 35.0)


# ── global ─────────────────────────────────────────────────────────────────

GLOBAL_CFG = {
    'global_profile': {
        'T_supply_min_c': 70.0,
        'T_supply_max_c': 95.0,
        'T_return_max_c': 55.0,
        'T_return_min_c': 45.0,
    }
}


def test_global_at_zero_load():
    temps = build_temperatures('global', GLOBAL_CFG, _demands([0, 0, 0]), 100.0, 90.0, 50.0, TIME_SET)
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(70.0)
    assert T_r == pytest.approx(55.0)


def test_global_at_full_load():
    temps = build_temperatures('global', GLOBAL_CFG, _demands([100, 100, 100]), 100.0, 90.0, 50.0, TIME_SET)
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(95.0)
    assert T_r == pytest.approx(45.0)


def test_global_at_half_load():
    temps = build_temperatures('global', GLOBAL_CFG, _demands([50, 50, 50]), 100.0, 90.0, 50.0, TIME_SET)
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(82.5)   # 70 + 0.5*(95-70)
    assert T_r == pytest.approx(50.0)   # 55 - 0.5*(55-45)


# ── pwl ────────────────────────────────────────────────────────────────────

PWL_CFG = {
    'temperature_profile': {
        'load_fractions': [0.0, 0.5, 1.0],
        'T_supply_c':     [70.0, 82.5, 95.0],
        'T_return_c':     [55.0, 50.0, 45.0],
    }
}


def test_pwl_at_breakpoints():
    demands = _demands([0.0, 50.0, 100.0])
    temps = build_temperatures('pwl', PWL_CFG, demands, 100.0, 90.0, 50.0, TIME_SET)
    assert temps[0] == pytest.approx((70.0, 55.0))
    assert temps[1] == pytest.approx((82.5, 50.0))
    assert temps[2] == pytest.approx((95.0, 45.0))


def test_pwl_between_breakpoints():
    # λ = 0.25 → halfway between breakpoints 0 and 1
    temps = build_temperatures('pwl', PWL_CFG, {0: 25.0}, 100.0, 90.0, 50.0, [0])
    T_s, T_r = temps[0]
    assert T_s == pytest.approx(76.25)  # 70 + 0.5*(82.5-70)
    assert T_r == pytest.approx(52.5)   # 55 + 0.5*(50-55)


# ── invariants ─────────────────────────────────────────────────────────────

def test_supply_gt_return_all_methods():
    demands = _demands([0.0, 50.0, 100.0])
    for method, cfg in [
        ('fixed', {}),
        ('global', GLOBAL_CFG),
        ('pwl', PWL_CFG),
    ]:
        temps = build_temperatures(method, cfg, demands, 100.0, 100.0, 40.0, TIME_SET)
        for t in TIME_SET:
            T_s, T_r = temps[t]
            assert T_s > T_r, f"method={method} t={t}: T_supply ({T_s}) not > T_return ({T_r})"


def test_heat_delivered_balance():
    """Q = m_dot * cp * dT / 1000 with cp=4.186 kJ/(kg·K)"""
    temps = build_temperatures('global', GLOBAL_CFG, {0: 50.0}, 100.0, 90.0, 50.0, [0])
    T_s, T_r = temps[0]
    m_dot = 10.0   # kg/s
    cp = 4.186     # kJ/(kg·K)
    Q_expected = m_dot * cp * (T_s - T_r) / 1000  # MW
    assert Q_expected > 0.0
    assert T_s - T_r == pytest.approx(82.5 - 50.0)


# ── validation ─────────────────────────────────────────────────────────────

def test_invalid_pwl_raises_on_bad_fractions():
    bad_cfg = {
        'temperature_profile': {
            'load_fractions': [0.0, 1.5],   # > 1
            'T_supply_c':     [70.0, 95.0],
            'T_return_c':     [55.0, 45.0],
        }
    }
    with pytest.raises(ValueError, match="load_fractions"):
        build_temperatures('pwl', bad_cfg, {0: 50.0}, 100.0, 90.0, 50.0, [0])


def test_invalid_pwl_raises_on_supply_le_return():
    bad_cfg = {
        'temperature_profile': {
            'load_fractions': [0.0, 1.0],
            'T_supply_c':     [70.0, 95.0],
            'T_return_c':     [80.0, 45.0],  # T_return > T_supply at breakpoint 0
        }
    }
    with pytest.raises(ValueError, match="T_supply"):
        build_temperatures('pwl', bad_cfg, {0: 50.0}, 100.0, 90.0, 50.0, [0])


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="Unknown"):
        build_temperatures('nonexistent', {}, {0: 0.0}, 1.0, 90.0, 40.0, [0])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Users/LKR/Downloads/tespy-dev/Planing-Framework-for-Heat
python -m pytest tests/test_temperature_linearization.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — `temperature_linearization` does not exist yet.

- [ ] **Step 3: Implement `temperature_linearization.py`**

```python
# calion/models/blocks/temperature_linearization.py
"""
Temperature Linearization for MILP District Heating Networks

Computes load-dependent supply and return temperatures from a demand timeseries
at model-build time (pure Python, no Pyomo). Returns a plain dict.

Public API:
    build_temperatures(method, lin_cfg, demand_series, peak_demand_mw,
                       nominal_supply_c, nominal_return_c, time_set)
    -> dict[int, tuple[float, float]]  # {t: (T_supply_c, T_return_c)}

Methods:
    "fixed"  — constant nominal temperatures (backward-compatible default)
    "global" — linear interpolation between min/max endpoints using load fraction
    "pwl"    — piecewise-linear interpolation over N breakpoints
"""


def build_temperatures(
    method: str,
    lin_cfg: dict,
    demand_series: dict,
    peak_demand_mw: float,
    nominal_supply_c: float,
    nominal_return_c: float,
    time_set,
) -> dict:
    """
    Compute supply and return temperatures for every timestep.

    Args:
        method:           "fixed" | "global" | "pwl"
        lin_cfg:          Full linearization sub-config dict (contains
                          'global_profile' or 'temperature_profile' sub-keys)
        demand_series:    {t: Q_demand_MW} for all t in time_set
        peak_demand_mw:   Peak (maximum) network demand in MW; used to normalise
                          the load fraction λ[t] = demand[t] / peak_demand_mw
        nominal_supply_c: Fallback / nominal supply temperature (°C)
        nominal_return_c: Fallback / nominal return temperature (°C)
        time_set:         Iterable of timestep indices

    Returns:
        {t: (T_supply_c, T_return_c)} for all t in time_set
    """
    if not method or method == 'fixed':
        return _fixed(nominal_supply_c, nominal_return_c, time_set)
    if method == 'global':
        return _global(
            lin_cfg.get('global_profile', {}),
            demand_series, peak_demand_mw, time_set,
            nominal_supply_c, nominal_return_c,
        )
    if method == 'pwl':
        return _pwl(
            lin_cfg.get('temperature_profile', {}),
            demand_series, peak_demand_mw, time_set,
        )
    raise ValueError(
        f"Unknown temperature linearization method: {method!r}. "
        f"Must be 'fixed', 'global', or 'pwl'."
    )


# ── private helpers ────────────────────────────────────────────────────────

def _fixed(nominal_supply_c: float, nominal_return_c: float, time_set) -> dict:
    """Return constant nominal temperatures for all timesteps."""
    return {t: (float(nominal_supply_c), float(nominal_return_c)) for t in time_set}


def _global(
    cfg: dict,
    demand_series: dict,
    peak_demand_mw: float,
    time_set,
    nominal_supply_c: float,
    nominal_return_c: float,
) -> dict:
    """
    Linear interpolation between two endpoints.

    λ[t] = Q[t] / peak  (clamped to [0, 1])
    T_supply[t] = T_s_min + λ × (T_s_max - T_s_min)
    T_return[t] = T_r_max - λ × (T_r_max - T_r_min)
    """
    T_s_min = float(cfg.get('T_supply_min_c', 70.0))
    T_s_max = float(cfg.get('T_supply_max_c', 95.0))
    T_r_max = float(cfg.get('T_return_max_c', 55.0))
    T_r_min = float(cfg.get('T_return_min_c', 45.0))

    result = {}
    for t in time_set:
        lam = max(0.0, min(1.0, demand_series.get(t, 0.0) / peak_demand_mw))
        T_s = T_s_min + lam * (T_s_max - T_s_min)
        T_r = T_r_max - lam * (T_r_max - T_r_min)
        result[t] = (T_s, T_r)
    return result


def _pwl(cfg: dict, demand_series: dict, peak_demand_mw: float, time_set) -> dict:
    """
    Piecewise-linear interpolation over N breakpoints.

    Config keys (under 'temperature_profile'):
        load_fractions: [f_0, ..., f_N]  strictly increasing, f_0>=0, f_N<=1
        T_supply_c:     [s_0, ..., s_N]  supply temps at each breakpoint
        T_return_c:     [r_0, ..., r_N]  return temps at each breakpoint

    Validates: T_supply[i] > T_return[i] for all i.
    """
    load_fracs = cfg.get('load_fractions')
    T_supply_pts = cfg.get('T_supply_c')
    T_return_pts = cfg.get('T_return_c')

    if load_fracs is None or T_supply_pts is None or T_return_pts is None:
        raise ValueError(
            "PWL method requires config key 'temperature_profile' with "
            "'load_fractions', 'T_supply_c', and 'T_return_c' lists."
        )
    n = len(load_fracs)
    if len(T_supply_pts) != n or len(T_return_pts) != n:
        raise ValueError(
            "PWL breakpoints: load_fractions, T_supply_c, T_return_c must "
            "all have the same length."
        )
    if load_fracs[0] < 0.0 or load_fracs[-1] > 1.0:
        raise ValueError(
            f"PWL load_fractions must lie within [0, 1]. "
            f"Got first={load_fracs[0]}, last={load_fracs[-1]}."
        )
    for i in range(n - 1):
        if load_fracs[i] >= load_fracs[i + 1]:
            raise ValueError(
                f"PWL load_fractions must be strictly increasing. "
                f"Violation at index {i}: {load_fracs[i]} >= {load_fracs[i+1]}."
            )
    for i in range(n):
        if T_supply_pts[i] <= T_return_pts[i]:
            raise ValueError(
                f"PWL breakpoint {i}: T_supply ({T_supply_pts[i]}) must be "
                f"> T_return ({T_return_pts[i]})."
            )

    result = {}
    for t in time_set:
        lam = max(0.0, min(1.0, demand_series.get(t, 0.0) / peak_demand_mw))
        T_s = _interpolate(lam, load_fracs, T_supply_pts)
        T_r = _interpolate(lam, load_fracs, T_return_pts)
        result[t] = (T_s, T_r)
    return result


def _interpolate(x: float, xs: list, ys: list) -> float:
    """
    Linear interpolation. x is clamped to [xs[0], xs[-1]].
    No numpy required — operates on plain Python lists.
    """
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return float(ys[i]) + t * (float(ys[i + 1]) - float(ys[i]))
    return float(ys[-1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_temperature_linearization.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add calion/models/blocks/temperature_linearization.py tests/test_temperature_linearization.py
git commit -m "feat: add temperature_linearization module with fixed/global/pwl methods"
```

---

## Task 2: Fix `model_finalizer.py` — stop overriding user `milp_linearize`

**Files:**
- Modify: `calion/models/model_finalizer.py:299`

- [ ] **Step 1: Locate the line**

Open `calion/models/model_finalizer.py` and find line ~299. The current code inside `_integrate_network_unified` reads:

```python
            "milp_linearize": True,
```

- [ ] **Step 2: Apply the fix**

Replace that single line so it reads the user's config:

```python
            "milp_linearize": self.cfg.get('thermal_network', {}).get('milp_linearize', False),
```

The surrounding context (for orientation) looks like:

```python
        return {
            "enabled": True,
            "nodes": nodes_list,
            "pipes": pipes_list,
            "parameters": {
                "supply_temp_nominal_c": ucfg.physics.supply_temp_c,
                "return_temp_nominal_c": ucfg.physics.return_temp_c,
                "ground_temp_default_c": ucfg.physics.ground_temp_c,
            },
            "milp_linearize": self.cfg.get('thermal_network', {}).get('milp_linearize', False),
        }
```

- [ ] **Step 3: Run existing tests to verify nothing broke**

```bash
python -m pytest tests/test_model_settings.py tests/test_system_builder.py -v 2>&1 | tail -20
```

Expected: same pass/fail as before the change (this fix only prevents silent override; actual MILP behaviour in tests stays controlled by individual configs).

- [ ] **Step 4: Commit**

```bash
git add calion/models/model_finalizer.py
git commit -m "fix: model_finalizer no longer silently forces milp_linearize=True"
```

---

## Task 3: Update `network_manager.py` — propagate demand + linearization config

**Files:**
- Modify: `calion/models/network_manager.py` — `_attach_all_pipes` (~line 472) and `_attach_all_nodes` (~line 510)

This task adds two small blocks: one that computes the total network demand series once before the pipe loop, and one that passes `demand_series`, `peak_demand_mw`, and `linearization` into every enriched config.

- [ ] **Step 1: Locate `_attach_all_pipes` in `network_manager.py`**

The method starts around line 472 and currently reads:

```python
    def _attach_all_pipes(self, model, time_set, buses, temp_setup) -> dict:
        """Phase 1: Validate and attach all pipe pair blocks."""
        supply_temp = temp_setup['supply_temp']
        return_temp = temp_setup['return_temp']
        use_outdoor_temp = temp_setup['use_outdoor_temp']

        pipe_components: dict = {}
        logger.info(f"\nAttaching {len(self.pipes)} pipe pairs...")

        # Propagate milp_linearize and pressure_drop flags from thermal_network config
        tn_cfg = self.config.get('thermal_network', {})
        milp_linearize = tn_cfg.get('milp_linearize', False)
        physics_cfg = tn_cfg.get('physics', {})
        pressure_drop_enabled = physics_cfg.get('pressure_drop', True)

        for pipe_id, pipe_config in self.pipes.items():
            pipe_dict = pipe_config if isinstance(pipe_config, dict) else pipe_config.__dict__
            enriched_config = {
                **pipe_dict,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
                'milp_linearize': milp_linearize,
                'pressure_drop_enabled': pressure_drop_enabled,
                'state_validation': self.config.get('state_validation', {}),
                **self.parameters,
            }
```

- [ ] **Step 2: Add demand computation and `linearization` propagation**

After the existing `pressure_drop_enabled = ...` line and before the `for pipe_id` loop, insert:

```python
        lin_cfg = tn_cfg.get('linearization', {})

        # Pre-compute total network demand for temperature linearization.
        # Sums all consumer node heatd_* Params already on the model.
        # Both pipes (no individual demand) and nodes share this network-wide
        # load fraction for temperature computation.
        total_demand: dict = {t: 0.0 for t in time_set}
        for nid, ncfg in self.nodes.items():
            nd = ncfg if isinstance(ncfg, dict) else ncfg.__dict__
            if nd.get('type') == 'consumer':
                attr = f'heatd_{nid}'
                if hasattr(model, attr):
                    hp = getattr(model, attr)
                    for t in time_set:
                        import pyomo.environ as _pyo
                        total_demand[t] += _pyo.value(hp[t])
        peak_demand_mw = max(total_demand.values()) if total_demand else 1.0
        if peak_demand_mw <= 0:
            peak_demand_mw = 1.0
```

Then inside the loop, extend `enriched_config` with three new keys:

```python
            enriched_config = {
                **pipe_dict,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_nominal_c': return_temp,
                'use_outdoor_temperature': use_outdoor_temp,
                'pipe_catalog': self.pipe_catalog,
                'milp_linearize': milp_linearize,
                'pressure_drop_enabled': pressure_drop_enabled,
                'state_validation': self.config.get('state_validation', {}),
                'linearization': lin_cfg,
                'demand_series': total_demand,
                'peak_demand_mw': peak_demand_mw,
                **self.parameters,
            }
```

- [ ] **Step 3: Locate `_attach_all_nodes` (~line 510) and add same three keys**

The node enriched_config currently ends with:

```python
            enriched_config = {
                **node_dict,
                'id': node_id,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_c': return_temp,
                'milp_linearize': milp_linearize,
                'pressure_drop_enabled': pressure_drop_enabled,
                'delta_p_min_consumer_bar': delta_p_min_consumer,
                'state_validation': self.config.get('state_validation', {}),
            }
```

Add `lin_cfg` reading after the existing `milp_linearize` line at the top of the method:

```python
        lin_cfg = tn_cfg.get('linearization', {})
```

Then extend `enriched_config`:

```python
            enriched_config = {
                **node_dict,
                'id': node_id,
                'supply_temp_nominal_c': supply_temp,
                'return_temp_c': return_temp,
                'milp_linearize': milp_linearize,
                'pressure_drop_enabled': pressure_drop_enabled,
                'delta_p_min_consumer_bar': delta_p_min_consumer,
                'state_validation': self.config.get('state_validation', {}),
                'linearization': lin_cfg,
                'demand_series': total_demand,
                'peak_demand_mw': peak_demand_mw,
            }
```

Note: `total_demand` and `peak_demand_mw` were computed in `_attach_all_pipes`. To avoid recomputing, move the demand-computation block into a helper method or the outer `attach_to_model` method. The cleanest solution is to compute it once in `attach_to_model` before calling `_attach_all_pipes`, store as instance attributes `self._demand_series` and `self._peak_demand_mw`, and reference them in both methods.

**Full revised approach — compute demand in `attach_to_model`:**

In `attach_to_model` (the method that calls `_attach_all_pipes` then `_attach_all_nodes`, around line 350), add this block right before `pipe_components = self._attach_all_pipes(...)`:

```python
        # Pre-compute total network demand for temperature linearization
        self._total_demand_series = {t: 0.0 for t in time_set}
        for nid, ncfg in self.nodes.items():
            nd = ncfg if isinstance(ncfg, dict) else ncfg.__dict__
            if nd.get('type') == 'consumer':
                attr = f'heatd_{nid}'
                if hasattr(model, attr):
                    hp = getattr(model, attr)
                    import pyomo.environ as _pyo
                    for t in time_set:
                        self._total_demand_series[t] += _pyo.value(hp[t])
        _peak = max(self._total_demand_series.values()) if self._total_demand_series else 1.0
        self._peak_demand_mw = _peak if _peak > 0 else 1.0
```

Then in `_attach_all_pipes`, use `self._total_demand_series` and `self._peak_demand_mw` (no local computation needed). Same in `_attach_all_nodes`.

- [ ] **Step 4: Run network-related tests**

```bash
python -m pytest tests/test_thermal_network_improvements.py tests/test_thermal_node_demand.py tests/test_network_api.py -v 2>&1 | tail -30
```

Expected: same pass/fail as before.

- [ ] **Step 5: Commit**

```bash
git add calion/models/network_manager.py
git commit -m "feat: network_manager propagates demand_series and linearization config to pipes/nodes"
```

---

## Task 4: Update `pipe_pair.py` — use `build_temperatures` in MILP mode

**Files:**
- Modify: `calion/models/blocks/pipe_pair.py` — lines 203–291

- [ ] **Step 1: Locate the MILP temperature block (lines 203–219)**

Current code:

```python
        milp_linearize = config.get('milp_linearize', False)

        if milp_linearize:
            # Fix temperatures at nominal values → all T×m_dot products become linear
            T_supply_in = pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True)
            T_supply_out = pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True)
            T_return_in = pyo.Param(time_set, initialize=return_temp_nominal_c, mutable=True)
            T_return_out = pyo.Param(time_set, initialize=return_temp_nominal_c, mutable=True)
        else:
            T_supply_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                  bounds=(supply_temp_min, supply_temp_max))
            ...
```

- [ ] **Step 2: Replace the MILP branch with `build_temperatures` call**

Replace only the `if milp_linearize:` branch (keep the `else:` branch unchanged):

```python
        milp_linearize = config.get('milp_linearize', False)

        if milp_linearize:
            from .temperature_linearization import build_temperatures
            _lin_cfg = config.get('linearization', {})
            _demand_series = config.get('demand_series', {t: 0.0 for t in time_set})
            _peak_demand_mw = config.get('peak_demand_mw', 1.0)
            _pipe_temps = build_temperatures(
                _lin_cfg.get('method', 'fixed'),
                _lin_cfg,
                _demand_series,
                _peak_demand_mw,
                supply_temp_nominal_c,
                return_temp_nominal_c,
                time_set,
            )
            _T_s = {t: _pipe_temps[t][0] for t in time_set}
            _T_r = {t: _pipe_temps[t][1] for t in time_set}
            T_supply_in  = pyo.Param(time_set, initialize=lambda m, t: _T_s[t], mutable=True)
            T_supply_out = pyo.Param(time_set, initialize=lambda m, t: _T_s[t], mutable=True)
            T_return_in  = pyo.Param(time_set, initialize=lambda m, t: _T_r[t], mutable=True)
            T_return_out = pyo.Param(time_set, initialize=lambda m, t: _T_r[t], mutable=True)
        else:
            T_supply_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                  bounds=(supply_temp_min, supply_temp_max))
            T_supply_out = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                   bounds=(supply_temp_min, supply_temp_max))
            T_return_in = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                  bounds=(return_temp_min, return_temp_max))
            T_return_out = pyo.Var(time_set, domain=pyo.NonNegativeReals,
                                   bounds=(return_temp_min, return_temp_max))
```

- [ ] **Step 3: Locate the MILP heat loss + heat_delivered block (lines ~267–291)**

Current code:

```python
        if milp_linearize:
            # MILP mode: heat losses computed from fixed nominal temperatures
            def heat_loss_supply_rule_milp(m, t):
                T_avg = supply_temp_nominal_c  # fixed nominal
                return Q_loss_supply[t] == (u_value_supply * length_m * (T_avg - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_supply',
                    pyo.Constraint(time_set, rule=heat_loss_supply_rule_milp))

            def heat_loss_return_rule_milp(m, t):
                T_avg = return_temp_nominal_c  # fixed nominal
                return Q_loss_return[t] == (u_value_return * length_m * (T_avg - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_return',
                    pyo.Constraint(time_set, rule=heat_loss_return_rule_milp))

            # MILP mode: Q_delivered linked to m_dot via fixed ΔT (linear)
            def heat_delivered_rule_milp(m, t):
                dT = supply_temp_nominal_c - return_temp_nominal_c
                return Q_delivered[t] * 1000 == m_dot[t] * cp_water * dT

            setattr(model, f'{prefix}_heat_delivered',
                    pyo.Constraint(time_set, rule=heat_delivered_rule_milp))

            # No temp_drop constraints needed — temperatures are fixed Params
```

- [ ] **Step 4: Replace with load-dependent temperature rules**

Replace the `if milp_linearize:` constraint block (keep `else:` unchanged):

```python
        if milp_linearize:
            # MILP mode: heat losses and Q_delivered use load-dependent Param temperatures
            # _T_s and _T_r are the dicts built above from build_temperatures
            def heat_loss_supply_rule_milp(m, t, _Ts=_T_s):
                return Q_loss_supply[t] == (u_value_supply * length_m * (_Ts[t] - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_supply',
                    pyo.Constraint(time_set, rule=heat_loss_supply_rule_milp))

            def heat_loss_return_rule_milp(m, t, _Tr=_T_r):
                return Q_loss_return[t] == (u_value_return * length_m * (_Tr[t] - T_ground[t])) / 1e6

            setattr(model, f'{prefix}_heat_loss_return',
                    pyo.Constraint(time_set, rule=heat_loss_return_rule_milp))

            def heat_delivered_rule_milp(m, t, _Ts=_T_s, _Tr=_T_r):
                dT = _Ts[t] - _Tr[t]
                return Q_delivered[t] * 1000 == m_dot[t] * cp_water * dT

            setattr(model, f'{prefix}_heat_delivered',
                    pyo.Constraint(time_set, rule=heat_delivered_rule_milp))

            # No temp_drop constraints needed — temperatures are fixed Params
```

- [ ] **Step 5: Run pipe-related tests**

```bash
python -m pytest tests/test_thermal_network_improvements.py tests/test_pipe_delay_warmup.py tests/test_pump_model.py -v 2>&1 | tail -30
```

Expected: same pass/fail as before.

- [ ] **Step 6: Commit**

```bash
git add calion/models/blocks/pipe_pair.py
git commit -m "feat: pipe_pair uses build_temperatures for MILP temp params"
```

---

## Task 5: Update `thermal_node.py` — use `build_temperatures` and load-specific ΔT

**Files:**
- Modify: `calion/models/blocks/thermal_node.py` — lines 144–184 (T variable setup) and lines 348–374 (heat_demand constraint)

- [ ] **Step 1: Locate the T_supply / T_return setup block (lines 144–184)**

Current code structure:

```python
        # T_supply: Var by default, but fixed Param in MILP-linearized mode
        milp_linearize_temp = config.get('milp_linearize', False)

        if milp_linearize_temp and node_type in ('consumer', 'junction', 'producer'):
            # MILP mode: fix supply temperature to nominal value → eliminates bilinear products
            setattr(model, f'{prefix}_T_supply',
                    pyo.Param(time_set, initialize=supply_temp_nominal_c, mutable=True))
        else:
            setattr(model, f'{prefix}_T_supply',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(supply_temp_min, supply_temp_max)))
        T_supply = getattr(model, f'{prefix}_T_supply')

        # T_return: Param for constant consumer return temps, Var otherwise
        return_temp_profile = config.get('return_temp_profile', None)
        return_temp_range = config.get('return_temp_range', None)
        return_temp_load_factor = config.get('return_temp_load_factor', 0.0)

        if node_type == 'consumer' and return_temp_profile is not None:
            ...
        elif node_type == 'consumer' and return_temp_range is None and return_temp_load_factor == 0:
            setattr(model, f'{prefix}_T_return',
                    pyo.Param(time_set, initialize=return_temp_c, mutable=True))
        else:
            ...
        T_return = getattr(model, f'{prefix}_T_return')
```

- [ ] **Step 2: Replace the entire T_supply/T_return setup block**

Replace from the `milp_linearize_temp = ...` line through the `T_return = getattr(...)` line with:

```python
        milp_linearize_temp = config.get('milp_linearize', False)
        _node_milp_temps = None  # populated below if MILP mode; used by heat_demand later

        if milp_linearize_temp:
            # MILP mode: both T_supply and T_return are load-dependent Params
            from .temperature_linearization import build_temperatures
            _lin_cfg = config.get('linearization', {})
            _demand_series = config.get('demand_series', {t: 0.0 for t in time_set})
            _peak_demand_mw = config.get('peak_demand_mw', 1.0)
            if _peak_demand_mw <= 0:
                _peak_demand_mw = 1.0
            _node_milp_temps = build_temperatures(
                _lin_cfg.get('method', 'fixed'),
                _lin_cfg,
                _demand_series,
                _peak_demand_mw,
                supply_temp_nominal_c,
                return_temp_c,
                time_set,
            )
            setattr(model, f'{prefix}_T_supply',
                    pyo.Param(time_set, initialize=lambda m, t: _node_milp_temps[t][0], mutable=True))
            setattr(model, f'{prefix}_T_return',
                    pyo.Param(time_set, initialize=lambda m, t: _node_milp_temps[t][1], mutable=True))
        else:
            # Non-MILP: T_supply is Var; T_return is Param or Var depending on config
            setattr(model, f'{prefix}_T_supply',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals,
                           bounds=(supply_temp_min, supply_temp_max)))

            return_temp_profile = config.get('return_temp_profile', None)
            return_temp_range = config.get('return_temp_range', None)
            return_temp_load_factor = config.get('return_temp_load_factor', 0.0)

            if node_type == 'consumer' and return_temp_profile is not None:
                def return_temp_init(m, t):
                    return return_temp_profile.get(t, return_temp_c)
                setattr(model, f'{prefix}_T_return',
                        pyo.Param(time_set, initialize=return_temp_init, mutable=True))
                logger.info(
                    f"    Node {node_id}: using return temp profile "
                    f"(range: {min(return_temp_profile.values()):.1f}-"
                    f"{max(return_temp_profile.values()):.1f}°C)"
                )
            elif node_type == 'consumer' and return_temp_range is None and return_temp_load_factor == 0:
                setattr(model, f'{prefix}_T_return',
                        pyo.Param(time_set, initialize=return_temp_c, mutable=True))
            else:
                T_ret_min = return_temp_range[0] if return_temp_range else return_temp_min
                T_ret_max = return_temp_range[1] if return_temp_range else return_temp_max
                setattr(model, f'{prefix}_T_return',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals,
                               bounds=(T_ret_min, T_ret_max)))

        T_supply = getattr(model, f'{prefix}_T_supply')
        T_return = getattr(model, f'{prefix}_T_return')
```

- [ ] **Step 3: Locate the `heat_demand` MILP passthrough block (~line 357)**

Current code (inside `if node_type == 'consumer':` → `elif milp_linearize:`):

```python
            elif milp_linearize:
                # MILP passthrough consumer: still needs m_dot_demand for mass balance
                dT_nominal = supply_temp_nominal_c - return_temp_c
                if dT_nominal <= 0:
                    dT_nominal = 35.0  # safe fallback

                def heat_demand_rule_milp(m, t):
                    return m_dot_demand[t] == Q_demand[t] * 1000 / (cp_water * dT_nominal)

                setattr(model, f'{prefix}_heat_demand',
                        pyo.Constraint(time_set, rule=heat_demand_rule_milp))
```

- [ ] **Step 4: Replace with per-timestep ΔT from `_node_milp_temps`**

Replace only the `elif milp_linearize:` branch:

```python
            elif milp_linearize:
                # MILP passthrough consumer: use load-specific ΔT for m_dot
                def heat_demand_rule_milp(m, t, _temps=_node_milp_temps):
                    dT = _temps[t][0] - _temps[t][1]
                    if dT <= 0:
                        dT = 35.0  # safe fallback (should never happen after build-time validation)
                    return m_dot_demand[t] == Q_demand[t] * 1000 / (cp_water * dT)

                setattr(model, f'{prefix}_heat_demand',
                        pyo.Constraint(time_set, rule=heat_demand_rule_milp))
```

- [ ] **Step 5: Run node-related tests**

```bash
python -m pytest tests/test_thermal_node_demand.py tests/test_thermal_network_improvements.py tests/test_system_builder.py -v 2>&1 | tail -30
```

Expected: same pass/fail as before.

- [ ] **Step 6: Commit**

```bash
git add calion/models/blocks/thermal_node.py
git commit -m "feat: thermal_node uses build_temperatures for MILP T_supply/T_return and load-specific dT"
```

---

## Task 6: Integration smoke-test and optional config update

**Files:**
- Modify: `configs/memmingen/Memmingen_L3.yaml` (optional — add `linearization` block)

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -40
```

Expected: no new failures. Any pre-existing failures unrelated to temperature are acceptable.

- [ ] **Step 2: Verify backward compatibility — `fixed` method equals old behavior**

Run a small integration test that exercises the MILP pipeline with `method: fixed`:

```bash
python -m pytest tests/test_regression.py tests/test_full_system.py -v -k "milp or network" 2>&1 | tail -30
```

Expected: PASS (fixed method produces identical Param values to old hardcoded nominal).

- [ ] **Step 3: (Optional) Add `linearization` block to Memmingen_L3.yaml**

In `configs/memmingen/Memmingen_L3.yaml`, inside the `thermal_network:` block, add after `return_temp_c: 40`:

```yaml
  linearization:
    method: "global"           # fixed (default) | global | pwl

    # Only for method: global
    global_profile:
      T_supply_min_c: 80     # supply temp at 0 % load
      T_supply_max_c: 100    # supply temp at 100 % load
      T_return_max_c: 45     # return temp at 0 % load
      T_return_min_c: 38     # return temp at 100 % load
```

- [ ] **Step 4: Verify config loads without error**

```bash
python -c "
import yaml
with open('configs/memmingen/Memmingen_L3.yaml') as f:
    cfg = yaml.safe_load(f)
lin = cfg['thermal_network'].get('linearization', {})
print('method:', lin.get('method'))
print('Config loaded OK')
"
```

Expected:
```
method: global
Config loaded OK
```

- [ ] **Step 5: Final commit**

```bash
git add configs/memmingen/Memmingen_L3.yaml
git commit -m "config: add global temperature linearization profile to Memmingen_L3"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `temperature_linearization.py` — all three methods + public interface matching spec signature
- [x] `model_finalizer.py` line 299 fix
- [x] `pipe_pair.py` — MILP temp block replaced, heat loss + heat_delivered use `_T_s`/`_T_r`
- [x] `thermal_node.py` — T_supply/T_return MILP block replaced, heat_demand uses per-timestep dT
- [x] `network_manager.py` — demand_series + peak_demand_mw + linearization propagated
- [x] Config schema extension in Memmingen_L3.yaml
- [x] Unit tests for all 9 spec-listed test cases (plus 2 extras for coverage)
- [x] Non-MILP path untouched in both pipe_pair and thermal_node

**Placeholder scan:** None found — all steps include complete code.

**Type consistency:** `build_temperatures` signature used identically in Tasks 1, 4, and 5. `_node_milp_temps` variable available in scope where `heat_demand_rule_milp` closure captures it in Task 5.

**Edge case:** `peak_demand_mw <= 0` guarded in both network_manager (Task 3) and thermal_node (Task 5) with fallback to 1.0.
