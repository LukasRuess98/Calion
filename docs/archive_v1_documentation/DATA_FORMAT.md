# Data Format Specification

This document describes the input data requirements for CALION.

## 1. Input Data File

CALION accepts input data in Excel (.xlsx) or CSV format.

### 1.1 Required Columns

| Column | Unit | Description |
|--------|------|-------------|
| Datum / Date | datetime | Timestamp (hourly) |
| Day_Ahead_Price | €/MWh | Electricity spot price |
| Wärmebedarf / Heat_Demand | MW | Thermal load |
| CO2_consumption_based | kg/MWh | Grid electricity emission factor |

### 1.2 Optional Columns (Waste Heat Recovery)

| Column | Unit | Description |
|--------|------|-------------|
| WRG1_Q MW | MW | Available waste heat from source 1 |
| WRG1_T °C | °C | Temperature of waste heat source 1 |
| WRG2_Q MW | MW | Available waste heat from source 2 |
| WRG2_T °C | °C | Temperature of waste heat source 2 |
| ... | ... | Up to 4 waste heat sources supported |

### 1.3 Example Data

```csv
Datum,Day_Ahead_Price,Wärmebedarf_MW,CO2_consumption_based,WRG1_Q MW,WRG1_T °C
2023-01-01 00:00,85.5,120.5,380,25.0,45.0
2023-01-01 01:00,82.3,118.2,375,24.5,44.8
2023-01-01 02:00,78.1,115.0,370,24.0,44.5
...
```

## 2. Column Name Mapping

Column names are flexible. Configure mapping in YAML:

```yaml
site:
  columns:
    price_candidates: [Day_Ahead_Price, "Day_Ahead_Price €/MWh", strompreis]
    heat_candidates: [Waermebedarf_MW, "Wärmebedarf MW", waermebedarf]
    co2_candidates: [CO2_consumption_based, "CO2_consumption_based kgCO2/MWh", co2]
    wrg1_q_candidates: ["WRG1Q MW", "WRG1_Q MW"]
    wrg1_t_candidates: ["WRG1_T °C", "WRG1 T °C"]
```

The loader tries each candidate in order until a match is found.

## 3. Data Quality Requirements

### 3.1 Timestamps

- Hourly resolution required
- Consistent time zone (configure in `site.tz`)
- No gaps in time series (will be interpolated if missing)

### 3.2 Numeric Values

- Non-negative for prices and demands
- NaN/empty cells are forward-filled
- Units must match expected (MW, €/MWh, kg/MWh)

### 3.3 Coverage

- Data must cover the optimization horizon
- For annual runs: 8760 hours (8784 for leap years)
- Partial years are supported

## 4. Thermal Network Topology

Network topology is defined in a separate YAML file.

### 4.1 File Structure

```yaml
# configs/networks/brownfield.yaml

nodes:
  - id: source
    type: source
    name: "Heat Plant"
  - id: junction1
    type: junction
    name: "Main Junction"
  - id: consumer1
    type: consumer
    name: "District A"
    demand_fraction: 0.4
  - id: consumer2
    type: consumer
    name: "District B"
    demand_fraction: 0.6

pipes:
  - id: P1
    from_node: source
    to_node: junction1
    length_m: 1000
    diameter_mm: 300
    u_value_w_per_mk: 0.5
  - id: P2
    from_node: junction1
    to_node: consumer1
    length_m: 500
    diameter_mm: 200
    u_value_w_per_mk: 0.5
  - id: P3
    from_node: junction1
    to_node: consumer2
    length_m: 800
    diameter_mm: 250
    u_value_w_per_mk: 0.5

parameters:
  T_supply_K: 363.15      # 90°C supply temperature
  T_return_K: 323.15      # 50°C return temperature
  T_ground_K: 283.15      # 10°C ground temperature
```

### 4.2 Pipe Parameters

| Parameter | Unit | Description |
|-----------|------|-------------|
| length_m | m | Pipe length |
| diameter_mm | mm | Inner diameter |
| u_value_w_per_mk | W/(m·K) | Overall heat transfer coefficient |

### 4.3 Heat Loss Calculation

For each pipe:
```
Q_loss = U × L × (T_supply - T_ground) / 1000  [kW]
```

Total network loss is sum over all pipes.

## 5. Output Data Format

### 5.1 Timeseries Export (CSV)

```csv
timestamp,P_buy,P_sell,HP1_Q,HP2_Q,TES_E,TES_Qc,TES_Qd,HKW_Qth,...
2023-01-01 00:00,50.5,0.0,25.0,30.0,450.0,10.0,0.0,75.0,...
2023-01-01 01:00,48.2,0.0,26.5,28.0,440.0,0.0,5.0,72.0,...
```

### 5.2 Summary Export (JSON)

```json
{
  "scenario": "stadtbach",
  "horizon": {
    "start": "2023-01-01T00:00:00",
    "end": "2023-12-31T23:00:00",
    "timesteps": 8760
  },
  "costs": {
    "total_eur": 5678901.23,
    "fuel_eur": 2345678.90,
    "electricity_eur": 1234567.89,
    "co2_eur": 456789.01,
    "capex_eur": 123456.78
  },
  "emissions": {
    "total_tco2": 45678.9,
    "from_fuels_tco2": 34567.8,
    "from_grid_tco2": 11111.1
  },
  "investment": {
    "HP1_cap_mw": 75.5,
    "HP2_cap_mw": 50.0,
    "TES_energy_mwh": 2500.0
  }
}
```

## 6. Synthetic Data Generation

For testing without real data, use the synthetic data generator:

```bash
python scripts/generate_stadtbach_synthetic_data.py
```

This creates a CSV with:
- Sinusoidal electricity prices (50-150 €/MWh)
- Seasonal heat demand (scaled by outdoor temperature)
- Variable CO₂ intensity (300-500 kg/MWh)
- Constant waste heat availability

## 7. Data Validation

The loader performs automatic validation:

1. **Timestamp parsing**: Multiple formats supported
2. **Column detection**: Fuzzy matching of column names
3. **Gap filling**: Forward-fill for missing values
4. **Year filtering**: Extract data for target year
5. **Unit verification**: Warnings for suspicious values

Validation errors are reported with specific row/column information.
