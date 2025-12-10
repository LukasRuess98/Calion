# Thermal Network Dashboard Preparation

**Date**: 2025-12-10
**Status**: Data structures ready, visualization pending
**Priority**: Short-term (1-2 weeks)

## Overview

This document outlines the data structures and preparation work for the thermal network visualization dashboard. All backend infrastructure is in place - network results are extracted, exported, and ready for visualization.

## Current Status ✅

### 1. Data Extraction (COMPLETE)

**Location**: `energis/run/rolling_horizon.py:1118-1175`

Network results are automatically extracted from solved models in `_collect_timeseries_and_summary()`:

```python
# Node time series
NET_{node_id}_T_supply_C        # Supply temperature [°C]
NET_{node_id}_T_return_C        # Return temperature [°C]
NET_{node_id}_Q_demand_MW       # Heat demand [MW]

# Pipe time series
NET_{pipe_id}_flow_kg_s         # Mass flow rate [kg/s]
NET_{pipe_id}_T_supply_in_C     # Inlet temperature [°C]
NET_{pipe_id}_T_supply_out_C    # Outlet temperature [°C]
NET_{pipe_id}_Q_loss_supply_kW  # Supply heat loss [kW]
NET_{pipe_id}_Q_loss_return_kW  # Return heat loss [kW]
```

**Summary Statistics**:
- Total heat delivered [MWh]
- Total heat losses [MWh]
- Heat loss percentage [%]
- Total pipe length [m]
- Number of nodes
- Number of pipes

### 2. Data Export (COMPLETE)

**Location**: `energis/run/rolling_horizon.py:2430-2463`

Three export formats available:

#### A. Network Time Series CSV
**Files**: `pf_network_timeseries.csv`, `rh_network_timeseries.csv`, `mpc_network_timeseries.csv`

- All network time series with timestamps
- One column per variable (NET_* prefix)
- Standard CSV format for easy loading

#### B. Network Summary CSV
**Files**: `pf_network_summary.csv`, `rh_network_summary.csv`, `mpc_network_summary.csv`

- Key performance indicators
- Total heat losses and percentages
- Network configuration

#### C. Dashboard JSON (Prepared, not yet exported)
**Method**: `NetworkManager.export_for_dashboard()`
**Location**: `energis/models/network_manager.py:416-498`

Structured JSON format:
```json
{
  "metadata": {
    "network_name": "Stadtbach District Heating Network",
    "total_nodes": 12,
    "total_pipes": 11
  },
  "network_topology": {
    "nodes": [{
      "id": "plant_ost",
      "name": "Erzeugungsanlagen Ost",
      "type": "plant",
      "coordinates": {"x": 3000, "y": 0},
      "elevation_m": 466.0,
      "avg_supply_temp_c": 95.2,
      "avg_return_temp_c": 55.1,
      "network": "nord"
    }],
    "pipes": [{
      "id": "main_ost_to_nord_zentral",
      "from": "plant_ost",
      "to": "zone_nord_zentral",
      "length_m": 1800,
      "diameter_current_mm": 300,
      "total_heat_loss_mwh": 1.2,
      "loss_percentage": 0.5
    }]
  },
  "time_series": {
    "pipe_flows": {
      "main_ost_to_nord_zentral": [12.5, 11.8, ...]
    },
    "temperatures": {
      "plant_ost_supply": [95.0, 94.8, ...],
      "plant_ost_return": [55.0, 55.2, ...]
    },
    "heat_losses": {
      "main_ost_to_nord_zentral": [0.05, 0.048, ...]
    }
  },
  "summary": {
    "total_heat_delivered_mwh": 840.2,
    "total_heat_loss_mwh": 5.8,
    "loss_percentage": 0.69
  }
}
```

## Dashboard Visualization Requirements

### 1. Network Map View

**Priority**: HIGH
**Complexity**: Medium

**Requirements**:
- Interactive 2D network topology
- Nodes positioned by coordinates (x, y from config)
- Pipes drawn as lines connecting nodes
- Color-coded by node type:
  - 🔴 Production plants (red)
  - 🔵 Consumer zones (blue)
  - 🟡 Junction/pump stations (yellow)

**Interactions**:
- Click node → Show node details panel
- Click pipe → Show pipe details panel
- Hover → Quick tooltip with key metrics
- Zoom/pan for large networks

**Data Source**: `network_topology` section of dashboard JSON

### 2. Time Series Charts

**Priority**: HIGH
**Complexity**: Low

**Charts**:
1. **Temperature Profiles**
   - X-axis: Time
   - Y-axis: Temperature [°C]
   - Lines: T_supply and T_return for selected node
   - Interactive legend to toggle nodes

2. **Heat Losses**
   - X-axis: Time
   - Y-axis: Heat loss [kW]
   - Stacked area chart: Supply vs Return losses
   - Total loss percentage indicator

3. **Mass Flow Rates**
   - X-axis: Time
   - Y-axis: Flow [kg/s]
   - Lines: Flow rate per pipe
   - Filter by pipe ID

**Data Source**: `time_series` section of dashboard JSON or network time series CSV

### 3. Performance KPI Cards

**Priority**: MEDIUM
**Complexity**: Low

**Metrics** (Top of dashboard):
```
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│  Total Heat Delivered   │   Total Heat Losses     │   Loss Percentage       │
│      840.2 MWh          │       5.8 MWh           │        0.69%            │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│   Avg Supply Temp       │   Avg Return Temp       │   Total Pipe Length     │
│      95.2°C             │       55.1°C            │      13.4 km            │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

**Data Source**: `summary` section

### 4. Node Details Panel (Side panel)

**Priority**: MEDIUM
**Complexity**: Low

When a node is selected:
```
Node: zone_nord_zentral
Type: Consumer
Network: Nord (PN 25)

Metrics:
  Avg Supply Temp:    94.5°C
  Avg Return Temp:    55.0°C
  Total Demand:       168.0 MWh
  Demand Fraction:    20%

Connected Pipes:
  → From plant_ost (1800m, DN300)
  → To zone_nord_west (1200m, DN200)
```

### 5. Pipe Details Panel

**Priority**: MEDIUM
**Complexity**: Low

When a pipe is selected:
```
Pipe: main_ost_to_nord_zentral
From: plant_ost → To: zone_nord_zentral

Physical:
  Length:            1800 m
  Diameter:          300 mm (DN300)
  Elevation change:  +4 m
  Installation:      2010

Performance:
  Avg Flow:          12.3 kg/s
  Total Heat Loss:   1.2 MWh (0.5%)
  Supply Loss:       0.7 MWh
  Return Loss:       0.5 MWh
  Avg Temp Drop:     0.8°C

Upgrade Status:
  Upgrade Available: Yes
  Recommended Dia:   350 mm
```

## Technology Stack Recommendations

### Frontend Options

#### Option 1: Web Dashboard (Recommended)
**Tech**: React + D3.js + Material-UI
**Pros**:
- Interactive, professional
- D3.js excellent for network graphs
- Easy to share (web link)
- Material-UI for polished interface

**Cons**:
- Requires separate frontend project
- More development time

#### Option 2: Jupyter Dashboard
**Tech**: Plotly Dash + NetworkX
**Pros**:
- Python-based (same stack)
- Faster to prototype
- Good for internal use

**Cons**:
- Less interactive than React
- NetworkX graph layout basic

#### Option 3: Streamlit
**Tech**: Streamlit + Plotly + NetworkX
**Pros**:
- Fastest to develop
- Pure Python
- Auto-refresh on data change

**Cons**:
- Limited customization
- Basic UI components

### Recommended: Streamlit (Phase 1) → React (Phase 2)

**Rationale**:
1. **Phase 1 (1-2 weeks)**: Streamlit prototype for internal validation
2. **Phase 2 (1-2 months)**: Professional React dashboard for client delivery

## Implementation Roadmap

### Week 1: Streamlit Prototype

**Goals**:
- Load CSV exports
- Display network map with NetworkX
- Show time series charts with Plotly
- KPI cards
- Basic interactivity

**Deliverable**: Working prototype on `localhost:8501`

**Code Structure**:
```
dashboard/
├── app.py              # Main Streamlit app
├── data_loader.py      # Load CSVs and JSONs
├── network_viz.py      # Network graph visualization
├── time_series.py      # Plotly charts
└── requirements.txt    # streamlit, plotly, networkx, pandas
```

### Week 2: Polish & Features

**Goals**:
- Node/pipe selection and details
- Time range filter
- Download visualizations as PNG
- Compare scenarios (PF vs RH vs MPC)
- Deploy to internal server

**Deliverable**: Production-ready Streamlit dashboard

### Weeks 3-8: React Dashboard (Optional)

**Goals**:
- Professional UI with Material-UI
- Advanced D3.js network visualization
- Real-time data updates
- User authentication (if needed)
- Export to PDF reports

## Next Steps

### Immediate Actions (This Week)

1. **Test CSV Export** ✅
   ```bash
   python -m energis.run configs/base.yaml configs/systems/test_simple_with_network.system.yaml
   # Check exports/ for network CSV files
   ```

2. **Create Streamlit App**
   ```bash
   pip install streamlit plotly networkx pandas
   cd dashboard
   streamlit run app.py
   ```

3. **Verify Data Loading**
   - Load `pf_network_timeseries.csv`
   - Load `pf_network_summary.csv`
   - Parse network topology from config YAMLs

### Future Enhancements (Weeks 3-4)

1. **Dashboard JSON Export**
   - Store network_manager reference in WorkflowResult
   - Call `export_for_dashboard()` in `export_workflow_results()`
   - Export to `{outdir}/network_dashboard.json`

2. **Investment Optimization Display**
   - Show recommended pipe upgrades
   - Calculate ROI for insulation improvements
   - Visualize diameter changes

3. **Scenario Comparison**
   - Load multiple exports
   - Side-by-side KPI comparison
   - Difference heatmaps

## Data Structure Examples

### Loading CSV in Python
```python
import pandas as pd

# Load time series
df = pd.read_csv('exports/20251210_120000_stadtbach/pf_network_timeseries.csv',
                 index_col=0, parse_dates=True)

# Extract node temperatures
node_id = 'plant_ost'
T_supply = df[f'NET_{node_id}_T_supply_C']
T_return = df[f'NET_{node_id}_T_return_C']

# Plot
import plotly.express as px
fig = px.line(df, y=[f'NET_{node_id}_T_supply_C', f'NET_{node_id}_T_return_C'],
              title=f'Temperature Profile: {node_id}')
fig.show()
```

### Loading Summary in Python
```python
summary = pd.read_csv('exports/20251210_120000_stadtbach/pf_network_summary.csv',
                      index_col=0, squeeze=True).to_dict()

print(f"Heat Loss: {summary['Total_heat_loss_MWh']:.1f} MWh")
print(f"Loss %: {summary['Heat_loss_percentage']:.2f}%")
```

## References

- **Data Extraction Code**: `energis/run/rolling_horizon.py:1118-1175`
- **Data Export Code**: `energis/run/rolling_horizon.py:2430-2463`
- **Dashboard JSON Method**: `energis/models/network_manager.py:416-498`
- **Network Configuration**: `configs/networks/stadtbach_network.yaml`
- **Test Results**: `scripts/test_thermal_network.py`

## Contact

For questions or implementation support:
- Check this document first
- Review exported CSV/JSON structure
- Test with Stadtbach network (12 nodes, 11 pipes)

---

**Status**: ✅ Data infrastructure complete, ready for visualization implementation
