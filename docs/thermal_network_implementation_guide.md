# Thermal Network Implementation Guide

**Practical guide for implementing pipe modeling in EnerGIS**

---

## Quick Start: Phase 1 Implementation

### 1. Create Pipe Component

**File:** `energis/models/blocks/pipe.py`

```python
"""
Pipe component for district heating networks.
Implements linear thermal and hydraulic modeling.
"""
from typing import Dict, Any
import pyomo.environ as pyo
from ..component import BaseComponent
from ..registry import register_component


@register_component("pipe")
class PipeBlock(BaseComponent):
    """
    Pipe component connecting two nodes in thermal network.

    Variables:
        - flow[t]: Mass flow through pipe (kg/s)
        - diameter_choice[d]: Binary - which diameter is selected
        - heat_delivered[t]: Heat output after losses (MW)

    Parameters:
        - from_node: Source node ID
        - to_node: Destination node ID
        - length_m: Pipe length in meters
        - diameter_options: List of available DN sizes
        - supply_temp_c: Supply temperature (default 90°C)
    """

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """Validate pipe configuration."""
        required = ['id', 'from_node', 'to_node', 'length_m']
        for field in required:
            if field not in config:
                raise ValueError(f"Pipe config missing required field: {field}")

        if config['length_m'] <= 0:
            raise ValueError(f"Pipe {config['id']}: length must be positive")

        if 'diameter_options' in config:
            if not config['diameter_options']:
                raise ValueError(f"Pipe {config['id']}: diameter_options cannot be empty")

    @staticmethod
    def attach(model, time_set, config: Dict[str, Any], buses: Dict) -> Dict[str, Any]:
        """
        Attach pipe component to Pyomo model.

        Returns dict with flow variables for connection to buses.
        """
        pipe_id = config['id']
        prefix = pipe_id.upper()

        # ============================================================
        # PARAMETERS
        # ============================================================

        length_m = config['length_m']

        # Pipe catalog from tech_catalog
        pipe_catalog = config.get('pipe_catalog', {})
        diameter_options = config.get('diameter_options', ['DN100'])

        # Thermal parameters
        supply_temp_c = config.get('supply_temp_c', 90.0)
        ambient_temp_c = config.get('ambient_temp_c', 10.0)
        delta_T = supply_temp_c - ambient_temp_c

        # ============================================================
        # SETS
        # ============================================================

        setattr(model, f'{prefix}_diameter_options',
                pyo.Set(initialize=diameter_options))

        # ============================================================
        # VARIABLES
        # ============================================================

        # Mass flow (kg/s) - could be negative for bidirectional flow
        setattr(model, f'{prefix}_flow',
                pyo.Var(time_set, domain=pyo.Reals,
                       bounds=(-1000, 1000)))  # Adjust bounds as needed

        # Diameter selection (binary)
        setattr(model, f'{prefix}_diam',
                pyo.Var(getattr(model, f'{prefix}_diameter_options'),
                       domain=pyo.Binary))

        # Heat input/output (MW)
        setattr(model, f'{prefix}_Q_in',
                pyo.Var(time_set, domain=pyo.NonNegativeReals))
        setattr(model, f'{prefix}_Q_out',
                pyo.Var(time_set, domain=pyo.NonNegativeReals))

        # Investment decision (if enabled)
        if config.get('investment', {}).get('enabled', False):
            setattr(model, f'{prefix}_build',
                   pyo.Var(domain=pyo.Binary))

        # Retrieve variables
        flow_var = getattr(model, f'{prefix}_flow')
        diam_var = getattr(model, f'{prefix}_diam')
        Q_in_var = getattr(model, f'{prefix}_Q_in')
        Q_out_var = getattr(model, f'{prefix}_Q_out')

        # ============================================================
        # CONSTRAINTS
        # ============================================================

        # (1) Exactly one diameter must be selected
        def one_diameter_rule(m):
            return sum(diam_var[d] for d in diameter_options) == 1

        setattr(model, f'{prefix}_one_diameter',
                pyo.Constraint(rule=one_diameter_rule))

        # (2) Heat loss calculation (simplified linear model)
        # Q_loss = U * length * ΔT
        # Q_out = Q_in - Q_loss

        def heat_loss_rule(m, t):
            # Calculate weighted U-value based on diameter selection
            q_loss_mw = 0
            for d in diameter_options:
                if d in pipe_catalog:
                    u_value = pipe_catalog[d].get('u_value_w_per_m_k', 0.3)
                    # Convert W to MW: (W/m-K) * m * K / 1e6
                    q_loss_per_diam = (u_value * length_m * delta_T) / 1e6
                    q_loss_mw += diam_var[d] * q_loss_per_diam

            return Q_out_var[t] == Q_in_var[t] - q_loss_mw

        setattr(model, f'{prefix}_heat_loss',
                pyo.Constraint(time_set, rule=heat_loss_rule))

        # (3) Flow-heat relationship (simplified)
        # Q = ṁ * c_p * ΔT
        # For water: c_p ≈ 4.186 kJ/kg-K, ΔT_network ≈ 40K (90°C - 50°C)
        # Q[MW] = flow[kg/s] * 4.186 * 40 / 1000 = flow * 0.167

        cp_water = 4.186  # kJ/kg-K
        network_delta_t = config.get('network_delta_t_k', 40.0)  # Supply - return
        conversion = (cp_water * network_delta_t) / 1000.0  # To MW

        def flow_heat_relation_rule(m, t):
            # Q_in = |flow| * conversion
            # Use auxiliary variable for absolute value or assume unidirectional
            # For simplicity: assume flow ≥ 0 (unidirectional)
            return Q_in_var[t] == flow_var[t] * conversion

        setattr(model, f'{prefix}_flow_heat',
                pyo.Constraint(time_set, rule=flow_heat_relation_rule))

        # (4) Pressure drop (linear approximation)
        # ΔP = K * flow
        # K depends on diameter (smaller diameter → higher K)

        # Store pressure drop for later use in pressure balance
        # (will be used when NodeComponent is implemented)

        # (5) Investment constraint (if applicable)
        if config.get('investment', {}).get('enabled', False):
            build_var = getattr(model, f'{prefix}_build')

            # Flow can only exist if pipe is built
            def build_gate_rule(m, t):
                M_FLOW = 1000  # Big-M for flow
                return flow_var[t] <= M_FLOW * build_var

            setattr(model, f'{prefix}_build_gate',
                   pyo.Constraint(time_set, rule=build_gate_rule))

        # ============================================================
        # COST CALCULATION
        # ============================================================

        # CAPEX: diameter-dependent cost
        capex_expr = 0
        for d in diameter_options:
            if d in pipe_catalog:
                cost_per_m = pipe_catalog[d].get('capex_eur_per_m', 500)
                capex_expr += diam_var[d] * (cost_per_m * length_m)

        # If investment decision:
        if config.get('investment', {}).get('enabled', False):
            build_var = getattr(model, f'{prefix}_build')
            capex_expr = capex_expr * build_var

        # Annualize CAPEX
        lifetime_years = config.get('lifetime_years', 40)
        period_years = getattr(model, 'period_years', 1.0)
        annualization = period_years / lifetime_years

        annual_capex = capex_expr * annualization

        # Store in model
        if not hasattr(model, 'pipe_capex_costs'):
            model.pipe_capex_costs = {}
        model.pipe_capex_costs[pipe_id] = annual_capex

        # ============================================================
        # RETURN FLOW REFERENCES
        # ============================================================

        return {
            'flow': flow_var,
            'Q_in': Q_in_var,
            'Q_out': Q_out_var,
            'from_node': config['from_node'],
            'to_node': config['to_node'],
            'capex': annual_capex
        }

    @staticmethod
    def get_results(model, time_set, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract results from solved model."""
        pipe_id = config['id']
        prefix = pipe_id.upper()

        flow_var = getattr(model, f'{prefix}_flow')
        Q_in_var = getattr(model, f'{prefix}_Q_in')
        Q_out_var = getattr(model, f'{prefix}_Q_out')
        diam_var = getattr(model, f'{prefix}_diam')

        # Extract time series
        flow_series = [pyo.value(flow_var[t]) for t in time_set]
        Q_in_series = [pyo.value(Q_in_var[t]) for t in time_set]
        Q_out_series = [pyo.value(Q_out_var[t]) for t in time_set]

        # Extract diameter choice
        diameter_options = config.get('diameter_options', ['DN100'])
        selected_diameter = None
        for d in diameter_options:
            if pyo.value(diam_var[d]) > 0.5:  # Binary close to 1
                selected_diameter = d
                break

        # Investment decision
        build_decision = None
        if config.get('investment', {}).get('enabled', False):
            build_var = getattr(model, f'{prefix}_build')
            build_decision = bool(pyo.value(build_var) > 0.5)

        # Calculate total heat loss
        total_heat_loss_mwh = sum(
            pyo.value(Q_in_var[t] - Q_out_var[t]) * getattr(model, 'dt_h', 1.0)
            for t in time_set
        )

        return {
            'flow_kg_s': flow_series,
            'Q_in_mw': Q_in_series,
            'Q_out_mw': Q_out_series,
            'selected_diameter': selected_diameter,
            'build_decision': build_decision,
            'total_heat_loss_mwh': total_heat_loss_mwh,
            'pipe_length_m': config['length_m']
        }
```

---

### 2. Update System Builder

**File:** `energis/models/system_builder.py`

Add after existing component attachments (around line 400):

```python
# ============================================================
# PIPES (if thermal network enabled)
# ============================================================

if cfg.get('thermal_network', {}).get('enabled', False):
    logger.info("Building thermal network components...")

    # Load network topology
    network_config = cfg['thermal_network']
    network_file = network_config.get('topology_file')

    if network_file:
        # Load from file
        import yaml
        from pathlib import Path
        network_path = Path(network_file)
        if not network_path.is_absolute():
            network_path = Path(cfg.get('config_dir', '.')) / network_path

        with open(network_path, 'r') as f:
            network_data = yaml.safe_load(f)
    else:
        # Inline definition
        network_data = network_config

    # Pass pipe catalog to each pipe
    pipe_catalog = network_config.get('pipe_catalog', {})

    # Attach pipes
    pipe_flows = {}
    for pipe_cfg in network_data.get('pipes', []):
        pipe_cfg['pipe_catalog'] = pipe_catalog
        pipe_cfg['supply_temp_c'] = network_config.get('parameters', {}).get('supply_temperature_c', 90)
        pipe_cfg['ambient_temp_c'] = network_config.get('parameters', {}).get('ambient_temperature_c', 10)

        from .blocks.pipe import PipeBlock
        PipeBlock.validate_config(pipe_cfg)
        pipe_result = PipeBlock.attach(m, m.t, pipe_cfg, {})

        pipe_flows[pipe_cfg['id']] = pipe_result
        logger.info(f"  Attached pipe: {pipe_cfg['id']} ({pipe_cfg['from_node']} → {pipe_cfg['to_node']})")

    # Store for later use
    m.pipe_flows = pipe_flows

    # Add pipe CAPEX to objective
    if hasattr(m, 'pipe_capex_costs'):
        total_pipe_capex = sum(m.pipe_capex_costs.values())
        # Will be added to objective later
    else:
        total_pipe_capex = 0
```

Update objective function (around line 978):

```python
m.obj = pyo.Objective(
    expr = energy_cost
         + dump_cost
         + fuel_costs
         + co2_term
         + demand_term
         + capex_total
         + activation_total
         + tie_break_total
         + storage_install_total
         + total_pipe_capex  # NEW: Add pipe CAPEX
         ,
    sense = pyo.minimize
)
```

---

### 3. Example YAML Configuration

**File:** `configs/systems/stadtbach_with_network.system.yaml`

```yaml
# Stadtbach system with explicit pipe network

# Existing components (unchanged)
heat_pumps:
  - id: HP1
    location_node: central_plant  # NEW: spatial reference
    wrg_source_column: WRG1_T_K
    investment:
      enabled: true
      capacity_min_mw: 5.0
      capacity_max_mw: 100.0
      capex_eur_per_mw: 400000.0

  - id: HP2
    location_node: central_plant
    wrg_source_column: WRG2_T_K
    investment:
      enabled: true
      capacity_min_mw: 5.0
      capacity_max_mw: 100.0

  - id: HP3
    location_node: central_plant
    wrg_source_column: WRG3_T_K
    investment:
      enabled: true
      capacity_min_mw: 5.0
      capacity_max_mw: 100.0

generators:
  hkw:
    enabled: true
    location_node: central_plant
    cap_th_mw: 75.0
    fuel_type: gas
    eff_th: 0.743
    eff_el: 0.177

  ava:
    enabled: true
    location_node: central_plant
    cap_th_mw: 45.0
    fuel_type: waste
    eff_th: 1.0

storage:
  enabled: false  # Keep simple for initial testing

# NEW: Thermal network configuration
thermal_network:
  enabled: true

  parameters:
    supply_temperature_c: 90
    return_temperature_c: 50
    network_delta_t_k: 40  # Supply - Return
    ambient_temperature_c: 10
    min_node_pressure_bar: 2.0
    max_node_pressure_bar: 10.0

  # Pipe catalog with costs and properties
  pipe_catalog:
    DN50:
      diameter_mm: 50
      diameter_m: 0.05
      capex_eur_per_m: 400
      u_value_w_per_m_k: 0.35  # W/(m·K) for standard insulation
      max_pressure_bar: 16
      max_velocity_m_s: 2.5

    DN80:
      diameter_mm: 80
      diameter_m: 0.08
      capex_eur_per_m: 520
      u_value_w_per_m_k: 0.32
      max_pressure_bar: 16
      max_velocity_m_s: 2.5

    DN100:
      diameter_mm: 100
      diameter_m: 0.10
      capex_eur_per_m: 650
      u_value_w_per_m_k: 0.30
      max_pressure_bar: 16
      max_velocity_m_s: 2.5

    DN150:
      diameter_mm: 150
      diameter_m: 0.15
      capex_eur_per_m: 850
      u_value_w_per_m_k: 0.28
      max_pressure_bar: 16
      max_velocity_m_s: 2.5

    DN200:
      diameter_mm: 200
      diameter_m: 0.20
      capex_eur_per_m: 1100
      u_value_w_per_m_k: 0.26
      max_pressure_bar: 16
      max_velocity_m_s: 2.5

  # Network topology
  nodes:
    - id: central_plant
      type: source
      coordinates: {x: 0, y: 0}
      components:  # Components located at this node
        - HP1
        - HP2
        - HP3
        - hkw
        - ava

    - id: district_north
      type: consumer
      coordinates: {x: 1500, y: 800}
      demand_fraction: 0.35  # 35% of total Stadtbach demand

    - id: district_south
      type: consumer
      coordinates: {x: 1800, y: -400}
      demand_fraction: 0.40  # 40% of total demand

    - id: district_east
      type: consumer
      coordinates: {x: 2500, y: 200}
      demand_fraction: 0.25  # 25% of total demand

  # Pipe connections
  pipes:
    - id: main_north
      from_node: central_plant
      to_node: district_north
      length_m: 1700  # Calculated from coordinates: sqrt((1500)^2 + (800)^2)
      diameter_options: [DN150, DN200]
      investment:
        enabled: false  # Existing pipe, can choose diameter

    - id: main_south
      from_node: central_plant
      to_node: district_south
      length_m: 1850
      diameter_options: [DN150, DN200]
      investment:
        enabled: false

    - id: main_east
      from_node: central_plant
      to_node: district_east
      length_m: 2500
      diameter_options: [DN100, DN150, DN200]
      investment:
        enabled: false
```

---

### 4. Demand Splitting Script

**File:** `scripts/split_stadtbach_demand.py`

```python
"""
Split aggregated Stadtbach demand into spatial zones.
Creates modified Import_Data.xlsx with zone-specific demands.
"""
import pandas as pd
import yaml
from pathlib import Path

def split_demand(
    input_excel: str,
    output_excel: str,
    demand_column: str = 'heatd',
    fractions: dict = None
):
    """
    Split single demand column into multiple zones.

    Args:
        input_excel: Path to original Import_Data.xlsx
        output_excel: Path to output file
        demand_column: Column name with aggregated demand
        fractions: Dict of {zone_name: fraction}, e.g., {'north': 0.35, 'south': 0.40}
    """
    if fractions is None:
        fractions = {
            'district_north': 0.35,
            'district_south': 0.40,
            'district_east': 0.25
        }

    # Verify fractions sum to 1.0
    total = sum(fractions.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Fractions must sum to 1.0, got {total}")

    # Load data
    df = pd.read_excel(input_excel)

    if demand_column not in df.columns:
        raise ValueError(f"Column '{demand_column}' not found in {input_excel}")

    # Split demand
    for zone, fraction in fractions.items():
        new_col_name = f'demand_{zone}'
        df[new_col_name] = df[demand_column] * fraction
        print(f"Created {new_col_name}: {fraction*100:.1f}% of total demand")

    # Save
    df.to_excel(output_excel, index=False)
    print(f"\nSaved to: {output_excel}")
    print(f"Original demand column '{demand_column}' preserved.")
    print(f"New columns: {list(fractions.keys())}")

if __name__ == '__main__':
    split_demand(
        input_excel='data/Import_Data.xlsx',
        output_excel='data/Import_Data_with_zones.xlsx',
        demand_column='heatd',
        fractions={
            'district_north': 0.35,
            'district_south': 0.40,
            'district_east': 0.25
        }
    )
```

---

### 5. Test Case: Minimal Network

**File:** `configs/systems/test_simple_network.system.yaml`

```yaml
# Minimal test: 1 HP, 1 pipe, 1 consumer

heat_pumps:
  - id: HP_test
    location_node: source
    cop: 3.5
    investment:
      enabled: true
      capacity_min_mw: 1.0
      capacity_max_mw: 10.0
      capex_eur_per_mw: 400000.0

thermal_network:
  enabled: true

  parameters:
    supply_temperature_c: 80
    return_temperature_c: 50
    network_delta_t_k: 30
    ambient_temperature_c: 10

  pipe_catalog:
    DN50:
      diameter_mm: 50
      capex_eur_per_m: 400
      u_value_w_per_m_k: 0.35

    DN100:
      diameter_mm: 100
      capex_eur_per_m: 650
      u_value_w_per_m_k: 0.30

  nodes:
    - id: source
      type: source

    - id: consumer
      type: consumer
      demand_fraction: 1.0

  pipes:
    - id: test_pipe
      from_node: source
      to_node: consumer
      length_m: 500
      diameter_options: [DN50, DN100]
```

---

### 6. Unit Test

**File:** `tests/test_pipe_component.py`

```python
"""Unit tests for pipe component."""
import pytest
import pyomo.environ as pyo
from energis.models.blocks.pipe import PipeBlock


def test_pipe_basic():
    """Test basic pipe creation and constraints."""
    m = pyo.ConcreteModel()
    m.t = pyo.Set(initialize=[1, 2, 3])

    config = {
        'id': 'test_pipe',
        'from_node': 'A',
        'to_node': 'B',
        'length_m': 1000,
        'diameter_options': ['DN100', 'DN150'],
        'pipe_catalog': {
            'DN100': {
                'capex_eur_per_m': 650,
                'u_value_w_per_m_k': 0.30
            },
            'DN150': {
                'capex_eur_per_m': 850,
                'u_value_w_per_m_k': 0.28
            }
        },
        'supply_temp_c': 90,
        'ambient_temp_c': 10,
        'network_delta_t_k': 40
    }

    # Validate config
    PipeBlock.validate_config(config)

    # Attach component
    result = PipeBlock.attach(m, m.t, config, {})

    # Check variables exist
    assert hasattr(m, 'TEST_PIPE_flow')
    assert hasattr(m, 'TEST_PIPE_diam')
    assert hasattr(m, 'TEST_PIPE_Q_in')
    assert hasattr(m, 'TEST_PIPE_Q_out')

    # Check constraint exists
    assert hasattr(m, 'TEST_PIPE_one_diameter')
    assert hasattr(m, 'TEST_PIPE_heat_loss')

    # Check result structure
    assert 'flow' in result
    assert 'Q_in' in result
    assert 'Q_out' in result
    assert result['from_node'] == 'A'
    assert result['to_node'] == 'B'


def test_pipe_heat_loss_calculation():
    """Test that heat loss is calculated correctly."""
    m = pyo.ConcreteModel()
    m.t = pyo.Set(initialize=[1])

    config = {
        'id': 'test',
        'from_node': 'A',
        'to_node': 'B',
        'length_m': 1000,  # 1 km
        'diameter_options': ['DN100'],
        'pipe_catalog': {
            'DN100': {
                'capex_eur_per_m': 650,
                'u_value_w_per_m_k': 0.30  # W/(m·K)
            }
        },
        'supply_temp_c': 90,
        'ambient_temp_c': 10,
        'network_delta_t_k': 40
    }

    PipeBlock.attach(m, m.t, config, {})

    # Set Q_in to 10 MW
    m.TEST_Q_in[1].fix(10.0)

    # Fix diameter choice to DN100
    m.TEST_diam['DN100'].fix(1)

    # Solve for Q_out
    solver = pyo.SolverFactory('glpk')
    solver.solve(m)

    # Expected heat loss:
    # Q_loss = U * L * ΔT = 0.30 W/(m·K) * 1000 m * (90-10) K
    #        = 24000 W = 0.024 MW
    # Q_out = 10.0 - 0.024 = 9.976 MW

    q_out_value = pyo.value(m.TEST_Q_out[1])
    expected = 10.0 - 0.024

    assert abs(q_out_value - expected) < 0.001, \
        f"Expected Q_out ≈ {expected}, got {q_out_value}"


def test_pipe_diameter_selection():
    """Test that only one diameter is selected."""
    m = pyo.ConcreteModel()
    m.t = pyo.Set(initialize=[1])

    config = {
        'id': 'test',
        'from_node': 'A',
        'to_node': 'B',
        'length_m': 500,
        'diameter_options': ['DN50', 'DN100', 'DN150'],
        'pipe_catalog': {
            'DN50': {'capex_eur_per_m': 400, 'u_value_w_per_m_k': 0.35},
            'DN100': {'capex_eur_per_m': 650, 'u_value_w_per_m_k': 0.30},
            'DN150': {'capex_eur_per_m': 850, 'u_value_w_per_m_k': 0.28}
        }
    }

    PipeBlock.attach(m, m.t, config, {})

    # Add dummy objective to minimize CAPEX
    m.obj = pyo.Objective(expr=m.pipe_capex_costs['test'], sense=pyo.minimize)

    solver = pyo.SolverFactory('glpk')
    result = solver.solve(m)

    # Check that exactly one diameter is selected
    selected_count = sum(1 for d in ['DN50', 'DN100', 'DN150']
                        if pyo.value(m.TEST_diam[d]) > 0.5)

    assert selected_count == 1, "Exactly one diameter must be selected"

    # Should select DN50 (cheapest)
    assert pyo.value(m.TEST_diam['DN50']) > 0.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

---

## Running the Implementation

### Step 1: Install Dependencies (if needed)

```bash
# No new dependencies needed - uses existing Pyomo, pandas, yaml
```

### Step 2: Create the Pipe Component

```bash
# Copy the pipe.py code above to:
mkdir -p energis/models/blocks
# Create energis/models/blocks/pipe.py
```

### Step 3: Run Unit Tests

```bash
# Create test file
# tests/test_pipe_component.py

# Run tests
pytest tests/test_pipe_component.py -v
```

### Step 4: Create Test Configuration

```bash
# Create configs/systems/test_simple_network.system.yaml
# (Use YAML above)

# Create minimal scenario
# configs/scenarios/test_network.scenario.yaml
```

### Step 5: Run Simple Test

```bash
python -m energis.run \
    --config configs/systems/test_simple_network.system.yaml \
    --scenario configs/scenarios/pf.scenario.yaml \
    --hours 24
```

### Step 6: Analyze Results

```python
# In Python or Jupyter notebook
import pandas as pd
import json

# Load results
with open('results/test_simple_network_results.json', 'r') as f:
    results = json.load(f)

# Check pipe results
pipe_results = results['pipes']['test_pipe']
print(f"Selected diameter: {pipe_results['selected_diameter']}")
print(f"Total heat loss: {pipe_results['total_heat_loss_mwh']:.2f} MWh")
print(f"Pipe length: {pipe_results['pipe_length_m']} m")

# Plot flows
import matplotlib.pyplot as plt
plt.plot(pipe_results['Q_in_mw'], label='Q_in')
plt.plot(pipe_results['Q_out_mw'], label='Q_out')
plt.legend()
plt.xlabel('Hour')
plt.ylabel('Heat (MW)')
plt.title('Pipe Heat Flow')
plt.show()
```

---

## Next Steps After Phase 1

### Phase 2 Additions:

1. **Pressure Variables**
   - Add `pressure[t]` to nodes
   - Implement pressure balance constraints

2. **Pump Component**
   - Create `energis/models/blocks/pump.py`
   - Variables: `P_el[t]`, `delta_p[t]`, `build`

3. **Piecewise Linear Pressure Drop**
   - Replace linear approximation
   - Use Pyomo `Piecewise` component

4. **Network Validation**
   - Compare with TESPy simulation
   - Adjust linearization coefficients

---

## Troubleshooting

### Issue: Model doesn't solve

**Solution:**
- Check that `one_diameter` constraint is feasible
- Verify pipe catalog has valid data
- Check flow bounds (may need adjustment)

### Issue: Heat loss is negative

**Solution:**
- Ensure `ambient_temp_c < supply_temp_c`
- Check U-value units (W/(m·K), not kW)

### Issue: Selected diameter is always largest

**Solution:**
- Check that CAPEX term is in objective
- Verify annualization factor is correct
- May need to add pressure drop constraints to create trade-off

---

## Code Organization

```
energis/
├── models/
│   ├── blocks/
│   │   ├── pipe.py          # NEW: Pipe component
│   │   ├── pump.py          # Phase 2
│   │   ├── node.py          # Phase 2 (enhanced bus)
│   │   └── ...
│   ├── system_builder.py    # MODIFY: Add pipe attachment logic
│   └── ...
├── run/
│   └── ...
└── ...

configs/
├── networks/                 # NEW: Network topology definitions
│   ├── stadtbach_network.yaml
│   └── test_simple.yaml
├── systems/
│   ├── stadtbach_with_network.system.yaml  # NEW: Extended config
│   └── test_simple_network.system.yaml     # NEW: Test case
└── ...

tests/
├── test_pipe_component.py   # NEW: Unit tests
└── ...

scripts/
├── split_stadtbach_demand.py  # NEW: Utility script
└── ...
```

---

## Key Takeaways

1. **Start Simple:** Phase 1 uses linear approximations for quick implementation
2. **Incremental Complexity:** Add hydraulics (Phase 2) only after basic pipes work
3. **Validation:** Compare with TESPy for confidence in linearization
4. **Modularity:** Pipe component follows existing EnerGIS architecture
5. **YAML-First:** Network topology defined declaratively, not in code

---

**Ready to implement?** Start with the unit test, then build up to the full Stadtbach network!
