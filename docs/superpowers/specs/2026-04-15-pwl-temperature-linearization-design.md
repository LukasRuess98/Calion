# PWL Temperature Linearization — Design Spec
**Date:** 2026-04-15
**Status:** Approved

## Problem

Current MILP-linearization fixes all network temperatures to nominal constants
(`T_supply = 100 °C`, `T_return = 40 °C` everywhere, always). This eliminates
bilinear `T × m_dot` products but produces unrealistic physics: heat losses are
constant, mass-flow-to-heat conversion uses a single fixed ΔT, and return
temperatures never reflect actual load conditions.

Additionally `model_finalizer.py` hardcodes `"milp_linearize": True` regardless
of config, overriding user settings silently.

## Goal

Replace fixed nominal temperatures with **load-dependent temperatures** computed
from demand timeseries at model-build time. Three switchable methods via config.
Extract all temperature logic into a new focused module. Keep existing files slim.

---

## Architecture

```
calion/models/
├── blocks/
│   ├── pipe_pair.py             ← temperature block removed, 1 call replaces it
│   ├── thermal_node.py          ← temperature block removed, 1 call replaces it
│   └── temperature_linearization.py    ← NEW: all temperature logic here
└── model_finalizer.py           ← line 299 fix only
```

No changes to: `solver.py`, `registry.py`, `BaseComponent`, result collectors.

---

## New Module: `temperature_linearization.py`

### Key insight: pre-interpolation, not SOS2

`Q_demand` is a fixed input timeseries (Param), not a decision variable.
Therefore `T_supply[t]` and `T_return[t]` can be **computed at model-build time**
by interpolating from breakpoints using the known load fraction at each timestep.

Result: mutable `pyo.Param` objects — no SOS2 binaries, no extra integer
variables, full MILP compatibility.

SOS2 would only be needed if temperature were itself an optimization decision.

### Public interface

```python
def build_temperatures(
    method: str,                   # "fixed" | "global" | "pwl"
    lin_cfg: dict,                 # linearization sub-config
    demand_series: dict[int, float],  # {t: Q_demand_MW}
    peak_demand_mw: float,
    nominal_supply_c: float,
    nominal_return_c: float,
    time_set,                      # Pyomo Set
) -> dict[int, tuple[float, float]]:
    """Return {t: (T_supply_c, T_return_c)} for all timesteps."""
```

### Method: `fixed`
Returns `nominal_supply_c` and `nominal_return_c` for all `t`.
Identical to current behavior. Default when no `linearization` key in config.

### Method: `global`
Linear interpolation between two endpoints using total load fraction
`λ[t] = Q_demand[t] / peak_demand_mw ∈ [0, 1]`:

```
T_supply[t] = T_supply_min + λ[t] × (T_supply_max - T_supply_min)
T_return[t] = T_return_max - λ[t] × (T_return_max - T_return_min)
```

Config keys (`global_profile`):
- `T_supply_min_c`: supply temp at 0 % load (default 70)
- `T_supply_max_c`: supply temp at 100 % load (default 95)
- `T_return_min_c`: return temp at 100 % load (default 45)
- `T_return_max_c`: return temp at 0 % load (default 55)

### Method: `pwl`
Piecewise-linear interpolation over N breakpoints:

```
load_fractions: [f_0, f_1, ..., f_N]   # strictly increasing, f_0=0, f_N=1
T_supply_c:     [s_0, s_1, ..., s_N]   # strictly increasing
T_return_c:     [r_0, r_1, ..., r_N]   # strictly decreasing
```

At each `t`: find segment `i` where `f_i ≤ λ[t] < f_{i+1}`, interpolate linearly.
Validate: `T_supply_c[i] > T_return_c[i]` for all `i`.

Config keys (`temperature_profile`):
- `load_fractions`: list of floats
- `T_supply_c`: list of supply temps
- `T_return_c`: list of return temps

### Integration into pipe_pair and thermal_node

Both files call `build_temperatures(...)` once, receive a `{t: (T_s, T_r)}` dict,
and create `pyo.Param(time_set, initialize=lambda m, t: temps[t][0], mutable=True)`.

Heat loss formula becomes:
```
Q_loss_supply[t] = U × L × (T_supply[t] - T_ground[t]) / 1e6
Q_loss_return[t] = U × L × (T_return[t] - T_ground[t]) / 1e6
```

Heat delivered:
```
Q_delivered[t] × 1000 = m_dot[t] × cp × (T_supply[t] - T_return[t])
```

Both remain fully linear since T is a Param.

---

## Changes Per File

### `temperature_linearization.py` (new, ~120 lines)

Functions:
- `build_temperatures(method, lin_cfg, demand_series, peak_demand, nominal_supply, nominal_return, time_set) → dict`
- `_fixed(nominal_supply, nominal_return, time_set) → dict`
- `_global(cfg, demand_series, peak_demand, time_set) → dict`
- `_pwl(cfg, demand_series, peak_demand, time_set) → dict`
- `_interpolate(x, xs, ys) → float` (numpy-free linear interpolation)

### `pipe_pair.py` (remove ~50 lines, add ~10)

Remove:
- Lines 203–219: milp T-Param/Var block
- Lines 267–291: milp heat loss + heat_delivered block

Replace with:
```python
from .temperature_linearization import build_temperatures
temps = build_temperatures(method, lin_cfg, demand_series, peak_demand,
                           supply_temp_nominal_c, return_temp_nominal_c, time_set)
T_s = {t: temps[t][0] for t in time_set}
T_r = {t: temps[t][1] for t in time_set}
T_supply_in  = pyo.Param(time_set, initialize=lambda m, t: T_s[t], mutable=True)
T_supply_out = pyo.Param(time_set, initialize=lambda m, t: T_s[t], mutable=True)
T_return_in  = pyo.Param(time_set, initialize=lambda m, t: T_r[t], mutable=True)
T_return_out = pyo.Param(time_set, initialize=lambda m, t: T_r[t], mutable=True)
```

Heat loss and `Q_delivered` use these Params directly (always the same formula,
no milp/non-milp branching needed).

Non-MILP mode (bilinear QP) unchanged — only activated when `milp_linearize: false`.

### `thermal_node.py` (remove ~90 lines, add ~15)

Remove:
- Lines 144–183: T_supply/T_return variable setup block
- Lines 248–298: temp-mixing constraints (bilinear + milp branches)
- Lines 345–374: `heat_demand` milp branch with hardcoded `dT_nominal`

Replace with:
```python
from .temperature_linearization import build_temperatures
temps = build_temperatures(method, lin_cfg, demand_series, peak_demand,
                           supply_temp_nominal_c, return_temp_c, time_set)
T_supply = pyo.Param(time_set, initialize=lambda m, t: temps[t][0], mutable=True)
T_return  = pyo.Param(time_set, initialize=lambda m, t: temps[t][1], mutable=True)
```

`heat_demand` for consumer nodes uses load-specific ΔT:
```python
dT[t] = temps[t][0] - temps[t][1]
m_dot_demand[t] == Q_demand[t] * 1000 / (cp_water * dT[t])
```

### `model_finalizer.py` (1 line)

```python
# Line 299 — before:
"milp_linearize": True,
# after:
"milp_linearize": self.cfg.get('thermal_network', {}).get('milp_linearize', False),
```

### `network_manager.py`

No structural change needed. `milp_linearize` propagation already reads from
`thermal_network.milp_linearize` at lines 359/483/517/557. Verified correct.

---

## Config Schema Extension

```yaml
thermal_network:
  milp_linearize: true
  linearization:
    method: "pwl"            # fixed (default) | global | pwl

    # Only for method: global
    global_profile:
      T_supply_min_c: 70     # supply temp at 0 % load
      T_supply_max_c: 95     # supply temp at 100 % load
      T_return_max_c: 55     # return temp at 0 % load
      T_return_min_c: 45     # return temp at 100 % load

    # Only for method: pwl
    temperature_profile:
      load_fractions: [0.0, 0.33, 0.66, 1.0]
      T_supply_c:     [70,  78,   86,   95  ]
      T_return_c:     [55,  52,   48,   45  ]
```

Backward compatibility: if `linearization` key is absent → `method: fixed`.
If `milp_linearize: false` → temperature_linearization is bypassed entirely
(non-MILP bilinear path in pipe_pair/thermal_node remains untouched).

---

## Unit Tests — `tests/test_temperature_linearization.py`

| Test | Assertion |
|------|-----------|
| `test_fixed_returns_nominal` | T_supply == 100, T_return == 40 for all t |
| `test_global_at_zero_load` | T_supply == T_supply_min, T_return == T_return_max |
| `test_global_at_full_load` | T_supply == T_supply_max, T_return == T_return_min |
| `test_global_at_half_load` | T_supply == midpoint, T_return == midpoint |
| `test_pwl_at_breakpoints` | exact match at each load_fraction breakpoint |
| `test_pwl_between_breakpoints` | linear interpolation between adjacent points |
| `test_supply_gt_return_always` | T_supply > T_return for all methods, all t |
| `test_heat_delivered_balance` | Q = m_dot × 4.186 × ΔT / 1000 |
| `test_invalid_pwl_raises` | load_fractions not in [0,1] raises ValueError |

---

## Constraints

- No bilinear terms (T always Param when milp_linearize=true)
- No SOS2 or extra binary variables
- MILP-compatible (Gurobi, HiGHS, CBC)
- Energiebilanz: Q_in = Q_out + Q_loss enforced via existing constraints
- T_supply > T_return validated at build time (not as model constraint)
- `fixed` method = exact current behavior → zero regression risk
