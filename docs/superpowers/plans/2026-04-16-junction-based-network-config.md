# Junction-Based Network Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace mandatory `type: producer/consumer/junction` in `network.nodes` YAML with role inference from `assets`/`consumers` keys; add inline `consumers` list per junction.

**Architecture:** Three-layer change — (1) `unified_config.py` parses new format + infers types, (2) `system_builder.py` creates per-consumer demand params, (3) `thermal_node.py` handles `consumers` list with N demand vars. `model_finalizer._unified_to_network_cfg()` bridges layers 1→3 by passing `consumers` through the network dict.

**Tech Stack:** Python 3.11, Pydantic v2, Pyomo, PyYAML

---

## File Map

| File | Change |
|---|---|
| `calion/config/unified_config.py` | Add `ConsumerConfig`; update `NodeConfig` (type inference, `consumers` list, legacy compat) |
| `calion/models/system_builder.py` | Per-consumer `heatd_{nid}_i` params + `heatd_{nid}` sum |
| `calion/models/model_finalizer.py` | `_unified_to_network_cfg()`: pass `consumers` list into node dict |
| `calion/models/blocks/thermal_node.py` | `validate_config` + `attach` + `get_results` handle `consumers` list |
| `configs/memmingen/Memmingen_L3.yaml` | Remove `type:`, replace `demand:` → `consumers:` |
| `tests/test_unified_config.py` | New tests for type inference and `consumers` parsing |
| `tests/test_thermal_node_demand.py` | New tests for multi-consumer attach |

---

## Task 1: `ConsumerConfig` + `NodeConfig` type inference in `unified_config.py`

**Files:**
- Modify: `calion/config/unified_config.py`
- Test: `tests/test_unified_config.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_unified_config.py`:

```python
from calion.config.unified_config import (
    parse_unified_config,
    UnifiedSystemConfig,
    NodeConfig,
    ConsumerConfig,   # new import
)


def test_consumer_config_from_dict_column():
    c = ConsumerConfig.from_dict({"column": "my_col"})
    assert c.column == "my_col"


def test_node_config_infers_producer_from_assets():
    n = NodeConfig.from_dict("E_1", {"assets": ["boiler_1"]})
    assert n.type == "producer"
    assert n.consumers == []


def test_node_config_infers_consumer_from_consumers_list():
    n = NodeConfig.from_dict("V_1", {"consumers": [{"column": "V_1_demand_MWth"}]})
    assert n.type == "consumer"
    assert len(n.consumers) == 1
    assert n.consumers[0].column == "V_1_demand_MWth"


def test_node_config_infers_mixed_when_both():
    n = NodeConfig.from_dict("J_x", {
        "assets": ["chp"],
        "consumers": [{"column": "local_demand"}],
    })
    assert n.type == "mixed"
    assert n.assets == ["chp"]
    assert len(n.consumers) == 1


def test_node_config_infers_junction_when_empty():
    n = NodeConfig.from_dict("j_1", {})
    assert n.type == "junction"
    assert n.consumers == []


def test_node_config_legacy_demand_converted_to_consumers():
    """Old demand: {column: ...} still works, converted to consumers[0]."""
    n = NodeConfig.from_dict("V_old", {
        "type": "consumer",
        "demand": {"column": "old_col"},
    })
    assert n.type == "consumer"
    assert len(n.consumers) == 1
    assert n.consumers[0].column == "old_col"


def test_node_config_explicit_type_overrides_inference():
    """Explicit type: producer overrides inference even without assets."""
    n = NodeConfig.from_dict("E_x", {"type": "producer"})
    assert n.type == "producer"


def test_parse_unified_config_new_format_no_type():
    """Full config without any type: fields parses successfully."""
    cfg = {
        "assets": {
            "boiler_1": {"type": "thermal_generator", "fuel": "gas",
                         "capacity_mw": 50.0, "thermal_efficiency": 0.9},
        },
        "network": {
            "nodes": {
                "E_1": {"assets": ["boiler_1"]},
                "j_1": {},
                "V_1": {"consumers": [{"column": "demand_V1"}]},
            },
            "pipes": {
                "E1_j1": {"from": "E_1", "to": "j_1", "length_m": 100, "diameter_mm": 300},
                "j1_V1": {"from": "j_1", "to": "V_1", "length_m": 80, "diameter_mm": 200},
            },
        },
        "grid": {}, "fuels": {"gas": {"price_eur_mwh": 45.0, "ef_kg_per_mwh_fuel": 200.0}},
        "costs": {"co2_price_eur_per_t": 100.0, "dump_cost_eur_per_mwh_th": 1.0},
    }
    ucfg = parse_unified_config(cfg)
    assert ucfg.nodes["E_1"].type == "producer"
    assert ucfg.nodes["j_1"].type == "junction"
    assert ucfg.nodes["V_1"].type == "consumer"
    assert ucfg.nodes["V_1"].consumers[0].column == "demand_V1"


def test_parse_unified_config_backward_compat_type_field():
    """Old configs with type: producer/consumer/junction still work."""
    cfg = {
        "assets": {
            "boiler_1": {"type": "thermal_generator", "fuel": "gas",
                         "capacity_mw": 50.0, "thermal_efficiency": 0.9},
        },
        "network": {
            "nodes": {
                "plant": {"type": "producer", "assets": ["boiler_1"]},
                "zone": {"type": "consumer", "demand": {"column": "demand_col"}},
            },
        },
        "grid": {}, "fuels": {"gas": {"price_eur_mwh": 45.0, "ef_kg_per_mwh_fuel": 200.0}},
        "costs": {"co2_price_eur_per_t": 100.0, "dump_cost_eur_per_mwh_th": 1.0},
    }
    ucfg = parse_unified_config(cfg)
    assert ucfg.nodes["plant"].type == "producer"
    assert ucfg.nodes["zone"].type == "consumer"
    assert ucfg.nodes["zone"].consumers[0].column == "demand_col"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /c/Users/LKR/Downloads/tespy-dev/Planing-Framework-for-Heat
python -m pytest tests/test_unified_config.py -k "consumer_config or infers or legacy_demand or new_format or backward_compat" -v 2>&1 | tail -20
```

Expected: `ImportError: cannot import name 'ConsumerConfig'` or similar failures.

- [ ] **Step 3: Implement `ConsumerConfig` and updated `NodeConfig`**

In `calion/config/unified_config.py`, after the `DemandConfig` class (around line 67), add:

```python
class ConsumerConfig(BaseModel):
    """Inline consumer definition at a junction node."""

    model_config = ConfigDict(populate_by_name=True)

    column: str

    @staticmethod
    def from_dict(raw: Any) -> ConsumerConfig:
        if isinstance(raw, str):
            return ConsumerConfig(column=raw)
        if isinstance(raw, dict):
            col = raw.get("column")
            if not col:
                raise ValueError("consumer config must have 'column' key")
            return ConsumerConfig(column=col)
        raise ValueError(f"Invalid consumer config: {raw!r}")
```

Replace the `NodeConfig` class (lines 86-113) with:

```python
class NodeConfig(BaseModel):
    """Configuration for a single network node."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str  # "producer", "consumer", "junction", "mixed"
    assets: list[str] = Field(default_factory=list)
    demand: DemandConfig | None = None        # kept for backward compat
    consumers: list[ConsumerConfig] = Field(default_factory=list)

    @staticmethod
    def _infer_type(assets: list, consumers: list) -> str:
        has_assets = bool(assets)
        has_consumers = bool(consumers)
        if has_assets and has_consumers:
            return 'mixed'
        if has_assets:
            return 'producer'
        if has_consumers:
            return 'consumer'
        return 'junction'

    @staticmethod
    def from_dict(node_id: str, raw: dict[str, Any]) -> NodeConfig:
        if raw is None:
            raw = {}

        assets = raw.get("assets", [])
        if not isinstance(assets, list):
            assets = [assets]

        # Parse consumers list (new format)
        consumers_raw = raw.get("consumers", [])
        consumers = [ConsumerConfig.from_dict(c) for c in consumers_raw]

        # Legacy: demand.column → consumers[0]
        demand = None
        demand_raw = raw.get("demand")
        if demand_raw is not None:
            demand = DemandConfig.from_dict(demand_raw)
            if not consumers:
                consumers = [ConsumerConfig(column=demand.column)]

        # Type: explicit override or inferred
        explicit_type = raw.get("type")
        if explicit_type is not None:
            if explicit_type not in ("producer", "consumer", "junction", "mixed", "plant"):
                raise ValueError(
                    f"Node '{node_id}': type must be producer/consumer/junction/mixed, "
                    f"got '{explicit_type}'"
                )
            node_type = "producer" if explicit_type == "plant" else explicit_type
        else:
            node_type = NodeConfig._infer_type(assets, consumers)

        return NodeConfig(
            id=node_id,
            type=node_type,
            assets=assets,
            demand=demand,
            consumers=consumers,
        )
```

- [ ] **Step 4: Update `parse_unified_config()` validation rules**

In `parse_unified_config()`, replace the validation blocks (around lines 296-327) that check types:

```python
    # 3. Every consumer/mixed node must have at least one consumer defined
    for nid, node in nodes.items():
        if node.type in ("consumer", "mixed") and not node.consumers:
            issues.append(
                f"Consumer/mixed node '{nid}' must have 'consumers' list or 'demand.column' specified"
            )

    # 4. At least one producer or mixed node (has assets)
    producer_ids = [nid for nid, n in nodes.items() if n.type in ("producer", "mixed")]
    if not producer_ids and nodes:
        issues.append("At least one node with 'assets' (producer or mixed) is required")
```

Also update `UnifiedSystemConfig` helper methods:

```python
    def consumer_nodes(self) -> dict[str, NodeConfig]:
        """Return all consumer and mixed nodes (have demands)."""
        return {nid: n for nid, n in self.nodes.items() if n.type in ("consumer", "mixed")}

    def producer_nodes(self) -> dict[str, NodeConfig]:
        """Return all producer and mixed nodes (have assets)."""
        return {nid: n for nid, n in self.nodes.items() if n.type in ("producer", "mixed")}
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_unified_config.py -k "consumer_config or infers or legacy_demand or new_format or backward_compat" -v 2>&1 | tail -25
```

Expected: all new tests pass, existing tests unaffected.

- [ ] **Step 6: Run full test suite for regressions**

```bash
python -m pytest tests/test_unified_config.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add calion/config/unified_config.py tests/test_unified_config.py
git commit -m "feat(config): add ConsumerConfig, junction type inference, consumers list

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Per-consumer demand params in `system_builder.py`

**Files:**
- Modify: `calion/models/system_builder.py:122-146`
- Test: `tests/test_system_builder.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_system_builder.py`:

```python
import pytest
from calion.utils.timeseries import TimeSeriesTable
import pandas as pd

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")

from calion.models.system_builder import build_model


def _make_table_two_consumers():
    """TimeSeriesTable with two consumer demand columns."""
    df = pd.DataFrame({
        "Datum": pd.date_range("2025-01-01", periods=3, freq="h"),
        "strompreis_EUR_MWh": [50.0, 51.0, 52.0],
        "grid_co2_kg_MWh": [300.0, 310.0, 320.0],
        "demand_A": [10.0, 12.0, 14.0],
        "demand_B": [5.0, 6.0, 7.0],
    })
    return TimeSeriesTable(df)


def _cfg_two_consumers():
    return {
        "assets": {
            "boiler_1": {"type": "thermal_generator", "fuel": "gas",
                         "capacity_mw": 500.0, "thermal_efficiency": 0.9},
        },
        "network": {
            "nodes": {
                "E_1": {"assets": ["boiler_1"]},
                "V_AB": {
                    "consumers": [
                        {"column": "demand_A"},
                        {"column": "demand_B"},
                    ],
                },
            },
            "pipes": {
                "E1_VAB": {"from": "E_1", "to": "V_AB",
                           "length_m": 100, "diameter_mm": 300},
            },
        },
        "grid": {"max_import_mw": 1000.0, "max_export_mw": 1000.0},
        "fuels": {"gas": {"price_eur_mwh": 45.0, "ef_kg_per_mwh_fuel": 200.0}},
        "costs": {"co2_price_eur_per_t": 100.0, "dump_cost_eur_per_mwh_th": 1.0},
        "run": {"dt_h": 1.0},
        "scenario": {"milp_linearize": False},
    }


def test_individual_consumer_params_created():
    """heatd_V_AB_0 and heatd_V_AB_1 are created for two consumers."""
    table = _make_table_two_consumers()
    cfg = _cfg_two_consumers()
    m = build_model(table, cfg, dt_h=1.0)
    assert hasattr(m, "heatd_V_AB_0"), "heatd_V_AB_0 not on model"
    assert hasattr(m, "heatd_V_AB_1"), "heatd_V_AB_1 not on model"


def test_individual_consumer_param_values():
    """heatd_V_AB_0 = demand_A, heatd_V_AB_1 = demand_B."""
    table = _make_table_two_consumers()
    cfg = _cfg_two_consumers()
    m = build_model(table, cfg, dt_h=1.0)
    vals_A = [pyo.value(m.heatd_V_AB_0[t]) for t in m.t]
    vals_B = [pyo.value(m.heatd_V_AB_1[t]) for t in m.t]
    assert vals_A == pytest.approx([10.0, 12.0, 14.0])
    assert vals_B == pytest.approx([5.0, 6.0, 7.0])


def test_sum_param_heatd_created():
    """heatd_V_AB = sum of individual consumers (backward compat)."""
    table = _make_table_two_consumers()
    cfg = _cfg_two_consumers()
    m = build_model(table, cfg, dt_h=1.0)
    assert hasattr(m, "heatd_V_AB"), "heatd_V_AB sum param not on model"
    vals = [pyo.value(m.heatd_V_AB[t]) for t in m.t]
    assert vals == pytest.approx([15.0, 18.0, 21.0])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_system_builder.py -k "individual_consumer or sum_param" -v 2>&1 | tail -15
```

Expected: `AssertionError: heatd_V_AB_0 not on model`.

- [ ] **Step 3: Update demand loading in `system_builder.py`**

In `calion/models/system_builder.py`, replace the multi-node demand loading block (lines 122-131, the `else:` branch of `if ucfg.is_copperplate:`):

```python
    else:
        # Multi-node: per-node demand parameters
        m.node_demand = {}
        for nid, node in ucfg.nodes.items():
            # New format: consumers list
            if node.consumers:
                individual_cols = []
                for i, consumer in enumerate(node.consumers):
                    actual_col = _find_demand_column(table, consumer.column)
                    demand_data = {i2 + 1: float(table[actual_col][i2]) for i2 in range(T)}
                    param_name = f"heatd_{nid}_{i}"
                    setattr(m, param_name, pyo.Param(m.t, initialize=demand_data, mutable=True))
                    individual_cols.append(actual_col)

                # Sum param for backward compat (used by ThermalNodeBlock via heatd_{nid})
                sum_data = {
                    i2 + 1: sum(float(table[col][i2]) for col in individual_cols)
                    for i2 in range(T)
                }
                param_name_sum = f"heatd_{nid}"
                setattr(m, param_name_sum, pyo.Param(m.t, initialize=sum_data, mutable=True))
                m.node_demand[nid] = getattr(m, param_name_sum)

            # Legacy format: single demand.column (no consumers list)
            elif node.demand is not None:
                actual_col = _find_demand_column(table, node.demand.column)
                demand_data = {i + 1: float(table[actual_col][i]) for i in range(T)}
                param_name = f"heatd_{nid}"
                setattr(m, param_name, pyo.Param(m.t, initialize=demand_data, mutable=True))
                m.node_demand[nid] = getattr(m, param_name)

        # Global m.heatd = sum of all node demands (for compatibility)
        all_demand_cols = []
        for node in ucfg.nodes.values():
            for consumer in node.consumers:
                actual_col = _find_demand_column(table, consumer.column)
                all_demand_cols.append(actual_col)
            if not node.consumers and node.demand is not None:
                actual_col = _find_demand_column(table, node.demand.column)
                all_demand_cols.append(actual_col)
        if all_demand_cols:
            global_demand = {
                i + 1: sum(float(table[col][i]) for col in all_demand_cols)
                for i in range(T)
            }
        else:
            global_demand = {i + 1: 0.0 for i in range(T)}
        m.heatd = pyo.Param(m.t, initialize=global_demand, mutable=True)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_system_builder.py -k "individual_consumer or sum_param" -v 2>&1 | tail -15
```

Expected: all 3 new tests pass.

- [ ] **Step 5: Run full builder tests for regressions**

```bash
python -m pytest tests/test_system_builder.py tests/test_unified_config.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add calion/models/system_builder.py tests/test_system_builder.py
git commit -m "feat(builder): per-consumer heatd params + sum for backward compat

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Bridge `consumers` into network node dict in `model_finalizer.py`

**Files:**
- Modify: `calion/models/model_finalizer.py:263-310`

No separate tests needed — covered by integration in Tasks 4 and 5.

- [ ] **Step 1: Update `_unified_to_network_cfg()`**

In `calion/models/model_finalizer.py`, replace the `nodes_list` building loop (lines 265-275):

```python
        nodes_list = []
        for nid, node in ucfg.nodes.items():
            node_dict: dict[str, Any] = {
                "id": nid,
                "type": node.type if node.type != "mixed" else "consumer",
            }
            # Pass consumers list for multi-consumer support in ThermalNodeBlock
            if node.consumers:
                node_dict["consumers"] = [{"column": c.column} for c in node.consumers]
                # demand_column = first consumer (used by validate_config backward compat)
                node_dict["demand_column"] = node.consumers[0].column
            elif node.demand is not None:
                node_dict["demand_column"] = node.demand.column
            if node.assets:
                node_dict["components"] = {aid: {} for aid in node.assets}
            # Mixed nodes need both consumers AND components
            if node.type == "mixed":
                node_dict["type"] = "mixed"
            nodes_list.append(node_dict)
```

- [ ] **Step 2: Run integration smoke test**

```bash
python -m pytest tests/test_full_system.py tests/test_system_builder.py -v 2>&1 | tail -20
```

Expected: all pass (no regressions from the dict shape change).

- [ ] **Step 3: Commit**

```bash
git add calion/models/model_finalizer.py
git commit -m "feat(finalizer): pass consumers list into network node dict

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: `ThermalNodeBlock` handles `consumers` list + `mixed` type

**Files:**
- Modify: `calion/models/blocks/thermal_node.py`
- Test: `tests/test_thermal_node_demand.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_thermal_node_demand.py`:

```python
def _make_model_with_two_consumers(demand_a: list, demand_b: list):
    """Model with heatd_{nid}_0 and heatd_{nid}_1 plus sum heatd_{nid}."""
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, len(demand_a))
    m.heatd_junc_0 = pyo.Param(
        m.t, initialize={i + 1: float(v) for i, v in enumerate(demand_a)}, mutable=True
    )
    m.heatd_junc_1 = pyo.Param(
        m.t, initialize={i + 1: float(v) for i, v in enumerate(demand_b)}, mutable=True
    )
    sum_vals = [a + b for a, b in zip(demand_a, demand_b)]
    m.heatd_junc = pyo.Param(
        m.t, initialize={i + 1: float(v) for i, v in enumerate(sum_vals)}, mutable=True
    )
    return m


def test_validate_config_accepts_consumers_list():
    """validate_config accepts node config with 'consumers' list."""
    ThermalNodeBlock.validate_config({
        "id": "junc",
        "type": "consumer",
        "consumers": [{"column": "col_A"}, {"column": "col_B"}],
    })


def test_multi_consumer_q_demand_params_created():
    """attach creates JUNC_Q_demand_0 and JUNC_Q_demand_1 for two consumers."""
    m = _make_model_with_two_consumers([10.0, 20.0], [5.0, 8.0])
    config = {
        "id": "junc",
        "type": "consumer",
        "consumers": [{"column": "col_A"}, {"column": "col_B"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    assert hasattr(m, "JUNC_Q_demand_0"), "JUNC_Q_demand_0 not created"
    assert hasattr(m, "JUNC_Q_demand_1"), "JUNC_Q_demand_1 not created"


def test_multi_consumer_q_demand_values():
    """Individual Q_demand params match heatd_{nid}_i values."""
    demand_a = [10.0, 20.0]
    demand_b = [5.0, 8.0]
    m = _make_model_with_two_consumers(demand_a, demand_b)
    config = {
        "id": "junc",
        "type": "consumer",
        "consumers": [{"column": "col_A"}, {"column": "col_B"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    vals_a = [pyo.value(m.JUNC_Q_demand_0[t]) for t in m.t]
    vals_b = [pyo.value(m.JUNC_Q_demand_1[t]) for t in m.t]
    assert vals_a == pytest.approx(demand_a)
    assert vals_b == pytest.approx(demand_b)


def test_multi_consumer_mass_balance_constraint_created():
    """attach creates JUNC_mass_balance with Σ m_dot_demand_i."""
    m = _make_model_with_two_consumers([10.0, 20.0], [5.0, 8.0])
    # Add a fake incoming pipe mass flow for the balance to reference
    m.PIPE_IN_m_dot = pyo.Var(m.t, domain=pyo.NonNegativeReals)
    config = {
        "id": "junc",
        "type": "consumer",
        "consumers": [{"column": "col_A"}, {"column": "col_B"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={},
                            network_pipes={"pipe_in": {"to_node": "junc", "from_node": "up"}})
    assert hasattr(m, "JUNC_mass_balance"), "JUNC_mass_balance not created"


def test_get_results_includes_consumers_breakdown():
    """get_results returns per-consumer breakdown under 'consumers' key."""
    demand_a = [10.0, 20.0]
    demand_b = [5.0, 8.0]
    m = _make_model_with_two_consumers(demand_a, demand_b)
    config = {
        "id": "junc",
        "type": "consumer",
        "consumers": [{"column": "col_A"}, {"column": "col_B"}],
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    results = ThermalNodeBlock.get_results(m, m.t, config)
    assert "consumers" in results
    assert len(results["consumers"]) == 2
    assert results["consumers"][0]["column"] == "col_A"
    assert results["consumers"][1]["column"] == "col_B"
    assert results["consumers"][0]["total_demand_mwh"] == pytest.approx(30.0)
    assert results["consumers"][1]["total_demand_mwh"] == pytest.approx(13.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_thermal_node_demand.py -k "consumers" -v 2>&1 | tail -15
```

Expected: `ValueError: demand_column or demand_profile` or assertion errors.

- [ ] **Step 3: Update `validate_config` in `thermal_node.py`**

In `calion/models/blocks/thermal_node.py`, replace `validate_config` (lines 66-82):

```python
    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        """Validate thermal node configuration."""
        required = ['id', 'type']
        for field in required:
            if field not in config:
                raise ValueError(f"ThermalNode config missing required field: {field}")

        # Accept 'plant' as an alias for 'producer' and 'mixed' as combined type
        valid_types = ['producer', 'plant', 'consumer', 'junction', 'mixed']
        if config['type'] not in valid_types:
            raise ValueError(f"Node {config['id']}: type must be one of {valid_types}")

        if config['type'] in ('consumer', 'mixed'):
            has_demand = (
                'demand_column' in config
                or 'demand_profile' in config
                or bool(config.get('consumers'))
            )
            if not has_demand:
                raise ValueError(
                    f"Consumer node {config['id']}: must specify demand_column, "
                    f"demand_profile, or consumers list"
                )
```

- [ ] **Step 4: Update `attach` to handle `consumers` list**

In `calion/models/blocks/thermal_node.py`, in the `attach` method, replace the demand variable section (starting at line 216, `if node_type == 'consumer':`). The goal is: when `config.get('consumers')` is a non-empty list, create N individual `Q_demand_i`/`m_dot_demand_i` pairs; total `m_dot_demand` for mass balance = Σ m_dot_demand_i.

Replace from `# Demand variables (consumer nodes only)` through `m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')` (approx lines 217-245), and the subsequent `# (3) Heat demand satisfaction` block for consumers, with:

```python
        # Demand variables (consumer nodes only)
        Q_demand = None
        m_dot_demand = None
        delta_p_valve_var = None
        delta_p_min_station = 0.5
        consumers_list = config.get('consumers', [])  # list of {column: ...} dicts
        n_consumers = len(consumers_list)

        if node_type in ('consumer', 'mixed'):
            delta_p_min_station = config.get('delta_p_min_consumer_bar', 0.5)

            if n_consumers > 0:
                # New format: N consumers inline
                _consumer_Q_demands = []
                _consumer_m_dots = []

                for i, cons in enumerate(consumers_list):
                    _attr = f'heatd_{node_id}_{i}'
                    if hasattr(model, _attr):
                        _hp = getattr(model, _attr)
                        def _qi_init(m, t, _h=_hp):
                            return pyo.value(_h[t])
                        setattr(model, f'{prefix}_Q_demand_{i}',
                                pyo.Param(time_set, initialize=_qi_init))
                    else:
                        # Fallback: use sum param (single-consumer compat)
                        _attr_sum = f'heatd_{node_id}'
                        if hasattr(model, _attr_sum) and i == 0:
                            _hp = getattr(model, _attr_sum)
                            def _qi_init_sum(m, t, _h=_hp):
                                return pyo.value(_h[t])
                            setattr(model, f'{prefix}_Q_demand_{i}',
                                    pyo.Param(time_set, initialize=_qi_init_sum))
                        else:
                            raise ValueError(
                                f"Consumer node {node_id}: no param heatd_{node_id}_{i} on model"
                            )

                    qi = getattr(model, f'{prefix}_Q_demand_{i}')
                    _consumer_Q_demands.append(qi)

                    setattr(model, f'{prefix}_m_dot_demand_{i}',
                            pyo.Var(time_set, domain=pyo.NonNegativeReals))
                    mi = getattr(model, f'{prefix}_m_dot_demand_{i}')
                    _consumer_m_dots.append(mi)

                # Aggregated demand var (sum) — used by mass balance and legacy code
                setattr(model, f'{prefix}_m_dot_demand',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals))
                m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

                # Sum constraint: m_dot_demand = Σ m_dot_demand_i
                def _sum_mdot_rule(m, t, _mds=_consumer_m_dots):
                    return m_dot_demand[t] == sum(md[t] for md in _mds)
                setattr(model, f'{prefix}_m_dot_demand_sum',
                        pyo.Constraint(time_set, rule=_sum_mdot_rule))

                # Convenience: Q_demand = sum of all Q_demand_i (used by result export)
                # Store Q_demands list on config dict for get_results
                config['_consumer_Q_demands'] = _consumer_Q_demands
                config['_consumer_m_dots'] = _consumer_m_dots
                # For legacy compat: set Q_demand to first consumer (used below in heat_demand)
                Q_demand = _consumer_Q_demands[0] if n_consumers == 1 else None

            else:
                # Legacy single-demand path (demand_column or demand_profile)
                _node_heatd_attr = f'heatd_{node_id}'
                if hasattr(model, _node_heatd_attr):
                    _node_heatd = getattr(model, _node_heatd_attr)
                    def demand_init(m, t, _h=_node_heatd):
                        return pyo.value(_h[t])
                    setattr(model, f'{prefix}_Q_demand',
                            pyo.Param(time_set, initialize=demand_init))
                elif 'demand_profile' in config:
                    demand_profile = config['demand_profile']
                    setattr(model, f'{prefix}_Q_demand',
                            pyo.Param(time_set, initialize=demand_profile))
                else:
                    raise ValueError(
                        f"Consumer node {node_id}: no demand data available."
                    )
                Q_demand = getattr(model, f'{prefix}_Q_demand')
                setattr(model, f'{prefix}_m_dot_demand',
                        pyo.Var(time_set, domain=pyo.NonNegativeReals))
                m_dot_demand = getattr(model, f'{prefix}_m_dot_demand')

            setattr(model, f'{prefix}_delta_p_valve',
                    pyo.Var(time_set, domain=pyo.NonNegativeReals, bounds=(0, 20.0)))
            delta_p_valve_var = getattr(model, f'{prefix}_delta_p_valve')
```

Then in the `# (3) Heat demand satisfaction (consumer nodes only)` block, add handling for multi-consumer case. After the existing consumer block, add:

```python
        # IMPORTANT: the existing `# (3) Heat demand satisfaction` block in thermal_node.py
        # uses `Q_demand` directly. Guard it so it only runs when n_consumers <= 1:
        #   if node_type == 'consumer' and n_consumers <= 1:
        #       <existing block unchanged>
        # The (3d) block below handles the n_consumers > 1 case instead.

        # (3d) Multi-consumer heat demand constraints
        if node_type in ('consumer', 'mixed') and n_consumers > 1:
            _consumer_Q_demands = config.get('_consumer_Q_demands', [])
            _consumer_m_dots = config.get('_consumer_m_dots', [])
            for i, (qi, mi) in enumerate(zip(_consumer_Q_demands, _consumer_m_dots)):
                if milp_linearize and not outgoing_pipes and _node_milp_temps is not None:
                    def _heat_demand_i_milp(m, t, _qi=qi, _mi=mi, _temps=_node_milp_temps):
                        dT = _temps[t][0] - _temps[t][1]
                        if dT <= 0:
                            dT = 35.0
                        return _mi[t] == _qi[t] * 1000 / (cp_water * dT)
                    setattr(model, f'{prefix}_heat_demand_{i}',
                            pyo.Constraint(time_set, rule=_heat_demand_i_milp))
                elif not milp_linearize:
                    def _heat_demand_i(m, t, _qi=qi, _mi=mi):
                        return _qi[t] * 1000 == _mi[t] * cp_water * (T_supply[t] - T_return[t])
                    setattr(model, f'{prefix}_heat_demand_{i}',
                            pyo.Constraint(time_set, rule=_heat_demand_i))
```

- [ ] **Step 5: Update `get_results` to return per-consumer breakdown**

In `calion/models/blocks/thermal_node.py`, in `get_results`, add after the existing consumer result block:

```python
        if node_type == 'consumer':
            # ... existing code ...

            # Per-consumer breakdown
            consumers_list = config.get('consumers', [])
            consumers_results = []
            for i, cons in enumerate(consumers_list):
                qi_attr = f'{prefix}_Q_demand_{i}'
                mi_attr = f'{prefix}_m_dot_demand_{i}'
                if hasattr(model, qi_attr):
                    qi = getattr(model, qi_attr)
                    qi_series = [pyo.value(qi[t]) for t in time_set]
                    consumers_results.append({
                        'index': i,
                        'column': cons.get('column', f'consumer_{i}'),
                        'Q_demand_mw': qi_series,
                        'total_demand_mwh': sum(qi_series) * dt_h,
                        'peak_demand_mw': max(qi_series),
                        'avg_demand_mw': sum(qi_series) / len(qi_series),
                    })
            if consumers_results:
                result['consumers'] = consumers_results
```

- [ ] **Step 6: Run new tests**

```bash
python -m pytest tests/test_thermal_node_demand.py -v 2>&1 | tail -25
```

Expected: all tests pass including new multi-consumer tests.

- [ ] **Step 7: Run broader regression check**

```bash
python -m pytest tests/test_thermal_node_demand.py tests/test_unified_config.py tests/test_system_builder.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add calion/models/blocks/thermal_node.py tests/test_thermal_node_demand.py
git commit -m "feat(thermal_node): multi-consumer support with per-consumer demand vars

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Update `Memmingen_L3.yaml` to new format

**Files:**
- Modify: `configs/memmingen/Memmingen_L3.yaml`

- [ ] **Step 1: Update `nodes:` section — remove `type:`, replace `demand:` → `consumers:`**

In `configs/memmingen/Memmingen_L3.yaml`, replace the entire `nodes:` block (lines 108-239):

```yaml
  nodes:
    # ── Production (plant with all assets) ────────────────────────────────
    E_1:
      assets: [boiler_main, tes_main]

    # ── Central junctions (routing, no demand) ────────────────────────────
    j_1: {}
    j_2: {}
    j_3: {}
    j_4: {}
    j_5: {}
    j_6: {}
    j_7: {}

    # ── Consumer Junctions (each with one inline consumer) ─────────────────
    V_1:
      consumers:
        - column: "V_1_demand_MWth"
    V_2:
      consumers:
        - column: "V_2_demand_MWth"
    V_3:
      consumers:
        - column: "V_3_demand_MWth"
    V_4:
      consumers:
        - column: "V_4_demand_MWth"
    V_5:
      consumers:
        - column: "V_5_demand_MWth"
    V_6:
      consumers:
        - column: "V_6_demand_MWth"
    V_7:
      consumers:
        - column: "V_7_demand_MWth"
    V_8:
      consumers:
        - column: "V_8_demand_MWth"
    V_9:
      consumers:
        - column: "V_9_demand_MWth"
    V_10:
      consumers:
        - column: "V_10_demand_MWth"
    V_11:
      consumers:
        - column: "V_11_demand_MWth"
    V_12:
      consumers:
        - column: "V_12_demand_MWth"
    V_13:
      consumers:
        - column: "V_13_demand_MWth"
    V_14:
      consumers:
        - column: "V_14_demand_MWth"
    V_15:
      consumers:
        - column: "V_15_demand_MWth"
    V_16:
      consumers:
        - column: "V_16_demand_MWth"
    V_17:
      consumers:
        - column: "V_17_demand_MWth"
    V_18:
      consumers:
        - column: "V_18_demand_MWth"
    V_19:
      consumers:
        - column: "V_19_demand_MWth"
    V_20:
      consumers:
        - column: "V_20_demand_MWth"
    V_21:
      consumers:
        - column: "V_21_demand_MWth"
    V_22:
      consumers:
        - column: "V_22_demand_MWth"
    V_23:
      consumers:
        - column: "V_23_demand_MWth"
    V_24:
      consumers:
        - column: "V_24_demand_MWth"
    V_25:
      consumers:
        - column: "V_25_demand_MWth"
    V_26:
      consumers:
        - column: "V_26_demand_MWth"
    V_27:
      consumers:
        - column: "V_27_demand_MWth"
```

- [ ] **Step 2: Verify YAML parses without errors**

```bash
cd /c/Users/LKR/Downloads/tespy-dev/Planing-Framework-for-Heat
python -c "
import yaml
from calion.config.unified_config import parse_unified_config
with open('configs/memmingen/Memmingen_L3.yaml') as f:
    cfg = yaml.safe_load(f)
ucfg = parse_unified_config(cfg)
print('Nodes:', len(ucfg.nodes))
producers = [n for n, c in ucfg.nodes.items() if c.type == 'producer']
consumers = [n for n, c in ucfg.nodes.items() if c.type == 'consumer']
junctions = [n for n, c in ucfg.nodes.items() if c.type == 'junction']
print(f'Producers: {producers}')
print(f'Consumers: {len(consumers)}')
print(f'Junctions: {len(junctions)}')
assert producers == ['E_1'], f'Expected [E_1], got {producers}'
assert len(consumers) == 27, f'Expected 27 consumers, got {len(consumers)}'
assert len(junctions) == 7, f'Expected 7 junctions, got {len(junctions)}'
print('OK')
"
```

Expected output:
```
Nodes: 35
Producers: ['E_1']
Consumers: 27
Junctions: 7
OK
```

- [ ] **Step 3: Commit**

```bash
git add configs/memmingen/Memmingen_L3.yaml
git commit -m "feat(config): migrate Memmingen_L3 to junction-based node format

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Final integration check + regression run

**Files:** No changes — validation only.

- [ ] **Step 1: Run full test suite**

```bash
cd /c/Users/LKR/Downloads/tespy-dev/Planing-Framework-for-Heat
python -m pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: all previously passing tests still pass.

- [ ] **Step 2: Spot-check config loading end-to-end**

```bash
python -c "
import yaml
from calion.config.unified_config import parse_unified_config
with open('configs/memmingen/Memmingen_L3.yaml') as f:
    cfg = yaml.safe_load(f)
ucfg = parse_unified_config(cfg)
for nid, node in ucfg.nodes.items():
    if node.consumers:
        print(f'{nid}: {node.type}, consumers={[c.column for c in node.consumers]}')
    elif node.type == 'producer':
        print(f'{nid}: {node.type}, assets={node.assets}')
    else:
        print(f'{nid}: {node.type}')
" 2>&1 | head -40
```

Expected: E_1=producer, j_1..j_7=junction, V_1..V_27=consumer each with one consumer column.

- [ ] **Step 3: Commit final tag**

```bash
git add .
git commit -m "feat: junction-based network config complete (Memmingen L3 migrated)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
