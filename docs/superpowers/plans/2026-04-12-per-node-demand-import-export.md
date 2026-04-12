# Per-Node Demand Import/Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `demand_fraction` (percentage split of global heat demand) with per-node `demand_column` references, so each consumer node imports its own independent demand timeseries and exports its own CSV file.

**Architecture:** Consumer nodes currently receive `demand_fraction * global_demand`. After this change every consumer node must reference a dedicated input column (`demand_column`) that maps directly to a time-series column in the input CSV/XLSX. On the export side, instead of one combined `nodes_timeseries.csv`, each node gets its own file under `thermal_network/nodes/{node_id}_timeseries.csv`. All `demand_fraction` fields, auto-distribution logic, validation, and tests are removed.

**Tech Stack:** Python 3.x, Pyomo (model params), Pydantic v2 (config schemas), pandas (CSV export), pytest.

---

## File Map

| File | Change |
|------|--------|
| `calion/models/blocks/thermal_node.py` | Remove fraction logic; require `heatd_{node_id}` or `demand_profile` |
| `calion/models/model_finalizer.py` | Remove `demand_fraction` from `_unified_to_network_cfg()` and `_preflight_network_check()` |
| `calion/config/unified_config.py` | Remove `demand_fraction` field from `NodeConfig` |
| `calion/config/schema.py` | Remove demand_fraction sum validation from `validate_thermal_network()` |
| `calion/config/validation.py` | Remove `_validate_network_physics` demand_fraction block |
| `calion/network.py` | Remove `demand_fraction` param from `add_node()`; remove auto-distribution in `_build_config()` |
| `calion/io/network_loader.py` | Remove `demand_frac_col` from `_load_nodes()`; update template |
| `calion/models/network_manager.py` | Update docstring example (demand_fraction → demand_column) |
| `calion/run/export.py` | Write per-node CSV files in `_write_network_data_to_dir()` |
| `calion/io/thermal_network_exporter.py` | Write per-node CSV files in `_export_node_results()` |
| `tests/test_network_api.py` | Replace `demand_fraction` tests with `demand_column` equivalents |
| `scripts/run_network_scenarios_programmatic.py` | Replace `demand_fraction=` with `demand_column=` |

---

## Task 1: Remove `demand_fraction` from `thermal_node.py`

**Files:**
- Modify: `calion/models/blocks/thermal_node.py`
- Test: `tests/test_thermal_node_demand.py` (create new)

- [ ] **Step 1: Write failing tests**

Create `tests/test_thermal_node_demand.py`:

```python
"""Tests that ThermalNodeBlock uses demand_column (heatd_{id}) directly, not demand_fraction."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")

from calion.models.blocks.thermal_node import ThermalNodeBlock


def _make_model(demand_values: list[float]) -> "pyo.ConcreteModel":
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, len(demand_values))
    # Simulate what system_builder creates: heatd_mynode
    m.heatd_mynode = pyo.Param(m.t, initialize={i + 1: v for i, v in enumerate(demand_values)}, mutable=True)
    return m


def test_consumer_uses_demand_column_directly():
    """Consumer node Q_demand equals heatd_{node_id} values without any fraction."""
    demand = [10.0, 20.0, 30.0]
    m = _make_model(demand)
    config = {
        "id": "mynode",
        "type": "consumer",
        "demand_column": "col_mynode",  # signal to use heatd_mynode
    }
    ThermalNodeBlock.attach(m, m.t, config, buses={}, network_pipes={})
    q_demand = getattr(m, "MYNODE_Q_demand")
    values = [pyo.value(q_demand[t]) for t in m.t]
    assert values == pytest.approx(demand), f"Expected {demand}, got {values}"


def test_consumer_validate_config_requires_demand_column_or_profile():
    """validate_config raises when neither demand_column nor demand_profile is present."""
    with pytest.raises(ValueError, match="demand_column or demand_profile"):
        ThermalNodeBlock.validate_config({"id": "x", "type": "consumer"})


def test_consumer_validate_config_accepts_demand_column():
    """validate_config accepts config with demand_column."""
    ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_column": "col_x"})


def test_consumer_validate_config_accepts_demand_profile():
    """validate_config accepts config with demand_profile."""
    ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_profile": {1: 5.0}})


def test_no_demand_fraction_attribute_accepted():
    """validate_config raises if only demand_fraction is provided (no longer valid)."""
    with pytest.raises(ValueError, match="demand_column or demand_profile"):
        ThermalNodeBlock.validate_config({"id": "x", "type": "consumer", "demand_fraction": 0.5})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "C:\Users\LKR\Downloads\tespy-dev\Planing-Framework-for-Heat"
python -m pytest tests/test_thermal_node_demand.py -v 2>&1 | head -60
```

Expected: `FAILED` — `demand_fraction` is still the only accepted config key.

- [ ] **Step 3: Modify `thermal_node.py`**

In `calion/models/blocks/thermal_node.py`, make three changes:

**a) `validate_config` — replace the demand check:**

Old (line 78–82):
```python
        if config['type'] == 'consumer':
            if 'demand_fraction' not in config and 'demand_profile' not in config:
                raise ValueError(
                    f"Consumer node {config['id']}: must specify demand_fraction or demand_profile"
                )
```

New:
```python
        if config['type'] == 'consumer':
            if 'demand_column' not in config and 'demand_profile' not in config:
                raise ValueError(
                    f"Consumer node {config['id']}: must specify demand_column or demand_profile"
                )
```

**b) `attach` — remove fraction logic in the demand initialization block:**

Old (lines 200–222 approximately):
```python
        if node_type == 'consumer':
            demand_fraction = config.get('demand_fraction', 0.0)

            _node_heatd_attr = f'heatd_{node_id}'
            if hasattr(model, _node_heatd_attr):
                _node_heatd = getattr(model, _node_heatd_attr)
                def demand_init(m, t, _h=_node_heatd):
                    return pyo.value(_h[t]) * demand_fraction
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_init))
            elif hasattr(model, 'heatd'):
                def demand_init(m, t):
                    return pyo.value(m.heatd[t]) * demand_fraction
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_init))
            elif 'demand_profile' in config:
                demand_profile = config['demand_profile']
                setattr(model, f'{prefix}_Q_demand',
                        pyo.Param(time_set, initialize=demand_profile))
            else:
                raise ValueError(f"Consumer node {node_id}: no demand data available")
```

New:
```python
        if node_type == 'consumer':
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
                    f"Consumer node {node_id}: no demand data available. "
                    f"Set demand_column in the node config so a heatd_{node_id} param is created."
                )
```

**c) `attach` — remove `demand_fraction` from the result dict** (near end of function, around line 433):

Old:
```python
            result['demand_fraction'] = config.get('demand_fraction', 0.0)
```

Remove that line entirely.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_thermal_node_demand.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add calion/models/blocks/thermal_node.py tests/test_thermal_node_demand.py
git commit -m "refactor: replace demand_fraction with demand_column in ThermalNodeBlock"
```

---

## Task 2: Remove `demand_fraction` from config and validation

**Files:**
- Modify: `calion/config/unified_config.py`
- Modify: `calion/config/schema.py`
- Modify: `calion/config/validation.py`
- Test: `tests/test_unified_config.py` (update)

- [ ] **Step 1: Write failing tests for NodeConfig**

Add to `tests/test_unified_config.py` (append at end of file):

```python
def test_node_config_has_no_demand_fraction():
    """NodeConfig no longer has demand_fraction field."""
    from calion.config.unified_config import NodeConfig
    node = NodeConfig.from_dict("c1", {
        "type": "consumer",
        "demand": {"column": "col_c1"},
    })
    assert not hasattr(node, 'demand_fraction'), "demand_fraction must not exist on NodeConfig"


def test_node_config_ignores_demand_fraction_in_raw():
    """Parsing a raw dict with demand_fraction does not populate a field."""
    from calion.config.unified_config import NodeConfig
    node = NodeConfig.from_dict("c1", {
        "type": "consumer",
        "demand": {"column": "col_c1"},
        "demand_fraction": 0.5,  # legacy — should be silently ignored
    })
    assert not hasattr(node, 'demand_fraction')
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
python -m pytest tests/test_unified_config.py::test_node_config_has_no_demand_fraction -v
```

Expected: FAILED — field still exists.

- [ ] **Step 3: Edit `calion/config/unified_config.py`**

In `NodeConfig`:

Old:
```python
    demand: DemandConfig | None = None
    demand_fraction: float | None = Field(default=1.0)  # Default to 100% (no scaling) if not specified

    @staticmethod
    def from_dict(node_id: str, raw: dict[str, Any]) -> NodeConfig:
        ...
        demand_fraction = raw.get("demand_fraction", 1.0)

        return NodeConfig(id=node_id, type=node_type, assets=assets, demand=demand, demand_fraction=demand_fraction)
```

New:
```python
    demand: DemandConfig | None = None

    @staticmethod
    def from_dict(node_id: str, raw: dict[str, Any]) -> NodeConfig:
        ...
        return NodeConfig(id=node_id, type=node_type, assets=assets, demand=demand)
```

(Remove the `demand_fraction` field definition and the `demand_fraction = raw.get(...)` line and the `demand_fraction=demand_fraction` in the constructor call.)

- [ ] **Step 4: Edit `calion/config/schema.py` — remove demand_fraction validation**

In `validate_thermal_network()`, remove the block that sums and checks `demand_fraction`:

Old (around lines 91–116):
```python
    # Consumer zones
    total_demand_fraction = 0.0
    for consumer in network_cfg.get("consumer_zones", []):
        ...
        # Track demand fraction
        demand_fraction = consumer.get("demand_fraction", 0)
        if demand_fraction is not None:
            _require_in_range(demand_fraction, f"consumer {node_id}.demand_fraction", 0, 1)
            total_demand_fraction += demand_fraction
        ...

    # Check demand fractions sum to ~1.0
    if network_cfg.get("consumer_zones"):
        if abs(total_demand_fraction - 1.0) > 0.01:
            warnings.append(
                f"Consumer demand_fractions sum to {total_demand_fraction:.3f}, expected 1.0"
            )
```

New (keep only non-fraction lines):
```python
    # Consumer zones
    for consumer in network_cfg.get("consumer_zones", []):
        node_id = consumer.get("node_id")
        if not node_id:
            raise ValueError("Consumer zone missing 'node_id'")
        if node_id in all_nodes:
            raise ValueError(f"Duplicate node_id: {node_id}")
        all_nodes.add(node_id)

        # Validate return temperature
        return_temp = consumer.get("return_temp_c")
        if return_temp is not None:
            _require_in_range(return_temp, f"consumer {node_id}.return_temp_c", 20, 100)
```

- [ ] **Step 5: Edit `calion/config/validation.py` — remove demand_fraction block**

In `_validate_network_physics()`, remove the demand-fraction sum check:

Old (around lines 256–270):
```python
        # Demand-fraction sum validation
        fractions = []
        for _nid, node in nodes.items():
            frac = getattr(node, 'demand_fraction', None)
            if frac is not None:
                fractions.append(float(frac))

        if fractions:
            total = sum(fractions)
            if not (0.99 <= total <= 1.01):
                self.result.add_error(
                    "network",
                    f"Network '{net_id}': demand_fraction values sum to {total:.4f} "
                    f"(must be in [0.99, 1.01]). Check consumer node demand_fraction fields.",
                )
```

Remove that entire block (the docstring comment `2. Demand fractions: ...` on line 211 can also be removed).

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_unified_config.py tests/test_config_schemas.py tests/test_config_validation.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add calion/config/unified_config.py calion/config/schema.py calion/config/validation.py tests/test_unified_config.py
git commit -m "refactor: remove demand_fraction from config schema and validation"
```

---

## Task 3: Remove `demand_fraction` from `Network` API

**Files:**
- Modify: `calion/network.py`
- Modify: `tests/test_network_api.py`

- [ ] **Step 1: Update `tests/test_network_api.py`**

Replace the following test methods (search and replace the full method bodies):

**`test_add_consumer_node`** — old:
```python
    def test_add_consumer_node(self):
        net = Network()
        net.add_node("north", "consumer", demand_fraction=0.4, peak_demand_mw=40.0)
        assert net._nodes["north"]["type"] == "consumer"
        assert net._nodes["north"]["demand_fraction"] == 0.4
        assert net._nodes["north"]["demand"]["peak_demand_mw"] == 40.0
```

New:
```python
    def test_add_consumer_node(self):
        net = Network()
        net.add_node("north", "consumer", demand_column="demand_north_MW", peak_demand_mw=40.0)
        assert net._nodes["north"]["type"] == "consumer"
        assert net._nodes["north"]["demand"]["column"] == "demand_north_MW"
        assert net._nodes["north"]["demand"]["peak_demand_mw"] == 40.0
```

**`test_config_includes_network`** — replace the consumer assertion:

Old:
```python
        # Consumer node has demand_fraction
        consumer = [n for n in tn["nodes"] if n["type"] == "consumer"][0]
        assert consumer["demand_fraction"] == 0.5
```

New:
```python
        # Consumer node has demand_column
        consumer = [n for n in tn["nodes"] if n["type"] == "consumer"][0]
        assert "demand_fraction" not in consumer
```

Also update the `add_node` call above it from `demand_fraction=0.5` to `demand_column="col_c1"`:
```python
        net.add_node("c1", "consumer", demand_column="col_c1")
```

**`test_fluent_topology`** — replace `demand_fraction=1.0` with `demand_column="col_c1"`:

Old:
```python
            .add_node("c1", "consumer", demand_fraction=1.0)
```

New:
```python
            .add_node("c1", "consumer", demand_column="col_c1")
```

**`test_auto_demand_fraction`** — delete the entire method (it tests removed behaviour).

- [ ] **Step 2: Run tests to confirm failures**

```bash
python -m pytest tests/test_network_api.py -v 2>&1 | head -60
```

Expected: failures in the three updated methods.

- [ ] **Step 3: Edit `calion/network.py` — update `add_node()`**

Old signature and body:
```python
    def add_node(
        self,
        id: str,
        type: str = "junction",
        *,
        assets: list[str] | None = None,
        demand_fraction: float | None = None,
        demand_column: str | None = None,
        peak_demand_mw: float | None = None,
    ) -> Network:
        """Add a network node (producer, consumer, or junction).
        ...
        demand_fraction : float, optional
            Fraction of global heat demand served by this consumer (0–1).
            Required for consumer nodes when using network topology.
        ...
        """
        node: dict[str, Any] = {"type": type}
        if assets:
            node["assets"] = assets
        if demand_fraction is not None:
            node["demand_fraction"] = demand_fraction
        if demand_column or peak_demand_mw:
            demand: dict[str, Any] = {}
            if demand_column:
                demand["column"] = demand_column
            if peak_demand_mw is not None:
                demand["peak_demand_mw"] = peak_demand_mw
            node["demand"] = demand
        self._nodes[id] = node
        return self
```

New:
```python
    def add_node(
        self,
        id: str,
        type: str = "junction",
        *,
        assets: list[str] | None = None,
        demand_column: str | None = None,
        peak_demand_mw: float | None = None,
    ) -> Network:
        """Add a network node (producer, consumer, or junction).

        Parameters
        ----------
        id : str
            Unique node identifier.
        type : str
            One of ``"producer"``, ``"consumer"``, ``"junction"``.
        assets : list of str, optional
            Component IDs attached to this node.
        demand_column : str, optional
            Time-series column name for consumer demand (required for consumer nodes).
        peak_demand_mw : float, optional
            Peak demand for consumer nodes.
        """
        node: dict[str, Any] = {"type": type}
        if assets:
            node["assets"] = assets
        if demand_column or peak_demand_mw:
            demand: dict[str, Any] = {}
            if demand_column:
                demand["column"] = demand_column
            if peak_demand_mw is not None:
                demand["peak_demand_mw"] = peak_demand_mw
            node["demand"] = demand
        self._nodes[id] = node
        return self
```

- [ ] **Step 4: Edit `calion/network.py` — remove auto-distribution in `_build_config()`**

Find and remove the entire auto-distribution block (around lines 435–468):

Old:
```python
        if self._nodes and self._pipes:
            # Auto-distribute demand fractions among consumers if not set
            consumers = [
                nid for nid, nd in self._nodes.items()
                if nd.get("type") == "consumer"
            ]
            consumers_without_fraction = [
                nid for nid in consumers
                if self._nodes[nid].get("demand_fraction") is None
            ]
            if consumers_without_fraction:
                # Compute remaining fraction after explicit fractions
                used = sum(
                    self._nodes[nid].get("demand_fraction", 0.0)
                    for nid in consumers
                    if self._nodes[nid].get("demand_fraction") is not None
                )
                remaining = max(0.0, 1.0 - used)
                auto_frac = remaining / len(consumers_without_fraction) if consumers_without_fraction else 0.0
                for nid in consumers_without_fraction:
                    self._nodes[nid]["demand_fraction"] = round(auto_frac, 6)

            nodes_list = []
            for nid, ndata in self._nodes.items():
                node_entry: dict[str, Any] = {
                    "id": nid,
                    "type": ndata.get("type", "junction"),
                }
                # Attach component references for producer nodes
                assets = ndata.get("assets", [])
                if assets:
                    node_entry["components"] = assets
                # Consumer demand fraction (required by ThermalNodeBlock)
                if ndata.get("demand_fraction") is not None:
                    node_entry["demand_fraction"] = ndata["demand_fraction"]
                nodes_list.append(node_entry)
```

New:
```python
        if self._nodes and self._pipes:
            nodes_list = []
            for nid, ndata in self._nodes.items():
                node_entry: dict[str, Any] = {
                    "id": nid,
                    "type": ndata.get("type", "junction"),
                }
                assets = ndata.get("assets", [])
                if assets:
                    node_entry["components"] = assets
                # Consumer demand column
                demand = ndata.get("demand")
                if demand:
                    node_entry["demand_column"] = demand.get("column")
                nodes_list.append(node_entry)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_network_api.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add calion/network.py tests/test_network_api.py
git commit -m "refactor: remove demand_fraction from Network API, require demand_column per node"
```

---

## Task 4: Remove `demand_fraction` from model finalizer

**Files:**
- Modify: `calion/models/model_finalizer.py`

- [ ] **Step 1: Edit `_preflight_network_check()`**

Old:
```python
        has_demand = (
            node_cfg.get('demand_column')
            or node_cfg.get('demand_fraction') is not None
            or node_cfg.get('Q_demand') is not None
        )
        if not has_demand:
            issues.append(
                f"Consumer node '{node_id}': missing demand_column, demand_fraction, or Q_demand"
            )
```

New:
```python
        has_demand = (
            node_cfg.get('demand_column')
            or node_cfg.get('Q_demand') is not None
        )
        if not has_demand:
            issues.append(
                f"Consumer node '{node_id}': missing demand_column or Q_demand"
            )
```

- [ ] **Step 2: Edit `_unified_to_network_cfg()`**

Old (around lines 272–276):
```python
            if node.demand is not None:
                node_dict["demand_column"] = node.demand.column
            if node.demand_fraction is not None:
                node_dict["demand_fraction"] = node.demand_fraction
```

New:
```python
            if node.demand is not None:
                node_dict["demand_column"] = node.demand.column
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -v -k "finalizer or model_finalizer or network" --tb=short 2>&1 | tail -30
```

Expected: no new failures.

- [ ] **Step 4: Commit**

```bash
git add calion/models/model_finalizer.py
git commit -m "refactor: remove demand_fraction from ModelFinalizer preflight and config conversion"
```

---

## Task 5: Remove `demand_fraction` from network loader and network manager docstring

**Files:**
- Modify: `calion/io/network_loader.py`
- Modify: `calion/models/network_manager.py`

- [ ] **Step 1: Edit `calion/io/network_loader.py` — `_load_nodes()`**

Remove `demand_frac_col` entirely:

Old (around lines 216 and 255–256):
```python
    demand_frac_col = _find_column(header, ["demand_fraction", "anteil_bedarf", "demand_share"])
    ...
        if demand_frac_col is not None and len(row) > demand_frac_col:
            node_config["demand_fraction"] = _to_float(row[demand_frac_col], 0.0)
```

New: delete both the `demand_frac_col = ...` line and the `if demand_frac_col ...` block.

- [ ] **Step 2: Update the template in `create_network_excel_template()`**

Replace the template comment that shows `demand_fraction` column:

Old:
```python
        "| node_id     | name        | type     | elevation_m | supply_temp_c | demand_fraction |\n"
        "|-------------|-------------|----------|-------------|---------------|-----------------|\n"
        "| plant_main  | Main Plant  | plant    | 470         | 100           |                 |\n"
        "| zone_nord   | Zone North  | consumer | 465         |               | 0.4             |\n"
        "| zone_sued   | Zone South  | consumer | 480         |               | 0.6             |\n\n"
```

New:
```python
        "| node_id     | name        | type     | elevation_m | supply_temp_c | demand_column        |\n"
        "|-------------|-------------|----------|-------------|---------------|----------------------|\n"
        "| plant_main  | Main Plant  | plant    | 470         | 100           |                      |\n"
        "| zone_nord   | Zone North  | consumer | 465         |               | demand_north_MW      |\n"
        "| zone_sued   | Zone South  | consumer | 480         |               | demand_south_MW      |\n\n"
```

- [ ] **Step 3: Edit `calion/models/network_manager.py` docstring**

At the top of the file (around lines 33–37), update the YAML example:

Old:
```yaml
  - id: consumer_A
    type: consumer
    demand_fraction: 0.6
```

New:
```yaml
  - id: consumer_A
    type: consumer
    demand_column: demand_A_MW
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: no failures.

- [ ] **Step 5: Commit**

```bash
git add calion/io/network_loader.py calion/models/network_manager.py
git commit -m "refactor: remove demand_fraction from network_loader and update docstring"
```

---

## Task 6: Per-node export in `calion/run/export.py`

**Files:**
- Modify: `calion/run/export.py`
- Test: `tests/test_model_export.py` (update/extend)

- [ ] **Step 1: Write a failing test**

Add to `tests/test_model_export.py`:

```python
import os
import json
import tempfile
import pytest


def test_write_network_data_per_node_files():
    """Each node gets its own CSV file under thermal_network/nodes/."""
    from calion.run.export import _write_network_data_to_dir

    network_data = {
        "nodes": {
            "plant": {
                "T_supply_series": [90.0, 91.0],
                "T_return_series": [50.0, 51.0],
                "type": "producer",
            },
            "north": {
                "T_supply_series": [88.0, 89.0],
                "T_return_series": [49.0, 50.0],
                "type": "consumer",
            },
        },
        "pipes": {},
        "summary": {},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        written = _write_network_data_to_dir(network_data, tmpdir)

        # Per-node files must exist
        plant_csv = os.path.join(tmpdir, "thermal_network", "nodes", "plant_timeseries.csv")
        north_csv = os.path.join(tmpdir, "thermal_network", "nodes", "north_timeseries.csv")
        assert os.path.isfile(plant_csv), f"Missing {plant_csv}"
        assert os.path.isfile(north_csv), f"Missing {north_csv}"

        # Combined nodes_timeseries.csv must NOT exist
        combined = os.path.join(tmpdir, "thermal_network", "nodes_timeseries.csv")
        assert not os.path.isfile(combined), "Combined nodes_timeseries.csv should not exist"

        # Keys in returned dict contain both node ids
        assert "node_plant" in written
        assert "node_north" in written
```

- [ ] **Step 2: Run test to confirm failure**

```bash
python -m pytest tests/test_model_export.py::test_write_network_data_per_node_files -v
```

Expected: FAILED — combined file written, no per-node files.

- [ ] **Step 3: Edit `_write_network_data_to_dir()` in `calion/run/export.py`**

Replace the "Node timeseries" block:

Old:
```python
    # Node timeseries
    node_ts: dict[str, list] = {}
    node_summary: dict[str, dict] = {}
    for node_id, node_info in network_data.get('nodes', {}).items():
        for key in ('T_supply_series', 'T_return_series'):
            col = f"{node_id}_{key.replace('_series', '')}"
            if key in node_info:
                node_ts[col] = node_info[key]
        node_summary[node_id] = {
            k: v for k, v in node_info.items()
            if not k.endswith('_series') and k not in ('id',)
        }

    if node_ts:
        node_csv = os.path.join(net_dir, "nodes_timeseries.csv")
        pd.DataFrame(node_ts).to_csv(node_csv, sep=';', index=True)
        written['nodes_timeseries'] = node_csv
        logger.info("[EXPORT] Thermal network nodes -> %s", node_csv)
```

New:
```python
    # Node timeseries — one file per node
    nodes_dir = os.path.join(net_dir, "nodes")
    os.makedirs(nodes_dir, exist_ok=True)
    node_summary: dict[str, dict] = {}
    for node_id, node_info in network_data.get('nodes', {}).items():
        node_ts: dict[str, list] = {}
        for key in ('T_supply_series', 'T_return_series', 'Q_demand_series'):
            if key in node_info:
                col = key.replace('_series', '')
                node_ts[col] = node_info[key]
        if node_ts:
            node_csv = os.path.join(nodes_dir, f"{node_id}_timeseries.csv")
            pd.DataFrame(node_ts).to_csv(node_csv, sep=';', index=True)
            written[f"node_{node_id}"] = node_csv
            logger.info("[EXPORT] Node %s -> %s", node_id, node_csv)
        node_summary[node_id] = {
            k: v for k, v in node_info.items()
            if not k.endswith('_series') and k not in ('id',)
        }
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_model_export.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add calion/run/export.py tests/test_model_export.py
git commit -m "feat: write per-node timeseries CSV files instead of combined nodes_timeseries.csv"
```

---

## Task 7: Per-node export in `calion/io/thermal_network_exporter.py`

**Files:**
- Modify: `calion/io/thermal_network_exporter.py`

- [ ] **Step 1: Edit `_export_node_results()`**

Read the current file from offset 189 to understand the full function, then replace the timeseries write block.

Old (around lines 272–278):
```python
    # Save node timeseries CSV
    if node_timeseries:
        ts_df = pd.DataFrame(node_timeseries, index=list(time_set))
        ts_path = os.path.join(nodes_dir, "nodes_timeseries.csv")
        ts_df.to_csv(ts_path, sep=';')
        files['nodes_timeseries'] = ts_path
```

New — write one CSV per node by grouping columns by their `{node_id}_` prefix:

```python
    # Save per-node timeseries CSV
    if node_timeseries:
        # Group columns by node_id prefix
        node_columns: dict[str, dict[str, list]] = {}
        for col_key, col_values in node_timeseries.items():
            # col_key format: "{node_id}_{variable}" e.g. "plant_T_supply"
            # Find which node_id this column belongs to (match longest prefix)
            matched_node = None
            for node_id in network_manager.nodes:
                prefix = f"{node_id}_"
                if col_key.startswith(prefix):
                    matched_node = node_id
                    break
            if matched_node is None:
                # fallback: use the full key as column name in an 'unknown' file
                matched_node = "_misc"
            node_columns.setdefault(matched_node, {})[col_key] = col_values

        for node_id, columns in node_columns.items():
            ts_df = pd.DataFrame(columns, index=list(time_set))
            ts_path = os.path.join(nodes_dir, f"{node_id}_timeseries.csv")
            ts_df.to_csv(ts_path, sep=';')
            files[f'node_{node_id}_timeseries'] = ts_path
            logger.info(f"  → {node_id}_timeseries.csv")
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: no failures.

- [ ] **Step 3: Commit**

```bash
git add calion/io/thermal_network_exporter.py
git commit -m "feat: per-node timeseries CSV in thermal_network_exporter"
```

---

## Task 8: Update scripts

**Files:**
- Modify: `scripts/run_network_scenarios_programmatic.py`

- [ ] **Step 1: Replace all `demand_fraction=` with `demand_column=`**

In `scripts/run_network_scenarios_programmatic.py`, every `add_node(...)` call with `demand_fraction=X` must be updated. The script has 4 scenario functions. Change each consumer node to use a unique `demand_column` name.

For example (scenario 1):
```python
# Old
net.add_node("north", "consumer", demand_fraction=0.40)
net.add_node("south", "consumer", demand_fraction=0.35)
net.add_node("east", "consumer", demand_fraction=0.25)

# New
net.add_node("north", "consumer", demand_column="demand_north_MW")
net.add_node("south", "consumer", demand_column="demand_south_MW")
net.add_node("east", "consumer", demand_column="demand_east_MW")
```

Apply the same pattern to all 4 scenarios in the file (all 14 `demand_fraction=` occurrences).

- [ ] **Step 2: Add a note at the top of the file**

After the module docstring, add:
```python
# NOTE: Each consumer node requires its own demand column in the input CSV.
# Column names must match what is provided in demand_column= below.
```

- [ ] **Step 3: Verify no `demand_fraction` references remain in non-archive Python files**

```bash
grep -r "demand_fraction" calion/ scripts/ tests/ --include="*.py" -l
```

Expected output: empty (no files). If any remain, fix them before committing.

- [ ] **Step 4: Commit**

```bash
git add scripts/run_network_scenarios_programmatic.py
git commit -m "refactor: update scripts to use demand_column instead of demand_fraction"
```

---

## Task 9: Final sweep — run full test suite

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -50
```

Expected: all tests pass. If any fail, read the error, fix the root cause, re-run.

- [ ] **Step 2: Verify no lingering `demand_fraction` in production code**

```bash
grep -rn "demand_fraction" calion/ --include="*.py"
```

Expected: zero matches. (Archive and test files may still have references if they document the old behaviour — that's acceptable. Production code must be clean.)

- [ ] **Step 3: Final commit**

```bash
git add -u
git commit -m "chore: final cleanup after demand_fraction removal"
```

---

## Self-Review Checklist

- [x] **`thermal_node.py`** — fraction multiplication removed; `validate_config` rejects `demand_fraction`-only configs
- [x] **`unified_config.py`** — `NodeConfig` has no `demand_fraction` field
- [x] **`schema.py`** — `validate_thermal_network()` no longer checks demand_fraction sums
- [x] **`validation.py`** — `_validate_network_physics()` demand-fraction block removed
- [x] **`network.py`** — `add_node()` signature has no `demand_fraction`; `_build_config()` has no auto-distribution
- [x] **`model_finalizer.py`** — `_preflight_network_check()` and `_unified_to_network_cfg()` updated
- [x] **`network_loader.py`** — `demand_frac_col` removed
- [x] **Export (both exporters)** — per-node CSV files instead of combined
- [x] **Tests** — `test_network_api.py` updated; new `test_thermal_node_demand.py` added; `test_unified_config.py` extended
- [x] **Scripts** — `run_network_scenarios_programmatic.py` updated
