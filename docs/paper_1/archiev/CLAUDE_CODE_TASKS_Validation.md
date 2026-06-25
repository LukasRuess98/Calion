# ============================================================
# VALIDATION FRAMEWORK — Memmingen District Heating Model
# Two-Stage: Network Calibration + Asset Sanity Checks
# ============================================================

## CONTEXT
You are working on a district heating network (DHN) optimization 
framework for Memmingen, Germany. The framework includes:
- Four model levels: L1 (aggregated), L2 (regional), L3-MILP, L3-MIQP
- Assets: CHP (0.2 MW), gas boiler (13 MW), biomass boiler (3.3 MW),
  electrode boiler / eboiler (5 MW), heat pump / HP (5 MW COP-based),
  thermal storage TES
- Network: 15 nodes, 14 pipes (DN100–DN450), tree topology
- Historical measured data available: hourly/15-min flow [m³/h],
  supply/return temperature [°C], pressure [bar] at key nodes
- IMPORTANT: Historical data is from the LEGACY network — no HP,
  TES, or electrode boiler were installed during the measurement period

## TASK
Implement a two-stage validation pipeline in Python. Structure it as 
follows:

### STAGE 1: Network Hydraulic & Thermal Validation
Goal: Validate pipe model (heat losses, pressure drop, temperature 
propagation) against historical pre-upgrade data.

1a. DATA LOADING & PREPROCESSING
- Load historical CSV/Excel time series (flow, T_supply, T_return, 
  pressure at available measurement points)
- Apply quality checks: detect gaps (>2h), outliers (±3σ), 
  physically implausible values (T_supply < T_return, negative flow)
- Identify steady-state periods (variance of flow < 5% over 1h window)
  for steady-state model comparison
- Identify representative winter week, summer week, transition week

1b. MODEL SIMULATION — NETWORK ONLY (no new assets)
- Run the L3-MILP/MIQP model with HP and electrode boiler DISABLED
  (set capacity = 0 or add a flag). Use only legacy assets (CHP + 
  gas boiler + biomass).
- Extract simulated: T_supply at each junction, T_return at source, 
  pressure drop per pipe segment, heat losses per pipe, total flow

1c. KPI COMPUTATION
Compute the following metrics between simulated and measured values:
For each measurement point (source + available substations):
  - MAE [°C] for supply temperature
  - RMSE [°C] for supply temperature  
  - MAPE [%] for flow
  - Relative error [%] for pressure drop along main trunk
  - Energy balance error: (Q_produced - Q_consumed - Q_losses) / Q_produced

Target thresholds (from Ku´s et al. 2025 and Maldonado et al. 2024):
  - T_supply MAE < 1.0°C (good: < 0.5°C)
  - T_return at source RMSE < 1.0°C
  - Flow MAPE < 5%
  - Pressure drop relative error < 5%
  - Energy balance error < 2%

1d. CALIBRATION LOOP (if thresholds not met)
- Adjust u_value_supply/return per pipe using RMSE minimization
- Use scipy.optimize.minimize with bounds [0.1 * nominal, 3 * nominal]
- Calibrate branch by branch (main trunk first, then laterals)
- Document: which pipes needed adjustment and by how much

### STAGE 2: Asset-Level Sanity Checks (Indirect Validation)
Goal: Verify that HP, electrode boiler, and storage dispatch is 
physically plausible — no measured data but physics-based bounds.

2a. HEAT PUMP PLAUSIBILITY
For each timestep where HP is dispatched:
  - Verify COP is within bounds: COP_min=2.5, COP_max=5.5
    given T_source and T_supply from the network model
  - Flag timesteps where HP runs below min_load=0.2
  - Plot COP vs. (T_supply - T_source) scatter — should follow 
    Carnot-like trend
  - Compute: annual HP heat output vs. installed capacity (full-load hours)
    Expected range: 2000–5000 h/year (flag if outside)

2b. ELECTRODE BOILER PLAUSIBILITY  
For each timestep where eboiler is dispatched:
  - Verify thermal output <= 5 MW (capacity constraint)
  - Check correlation with low spot electricity prices 
    (eboiler should dispatch when strompreis < threshold)
  - Compute efficiency = Q_thermal / P_electric → should be ~0.95–0.99
  - Plot: eboiler dispatch vs. electricity price (should be anti-correlated)

2c. THERMAL STORAGE (TES) PLAUSIBILITY
  - Check SOC (State of Charge) stays within [0.05, 0.95] of capacity
  - Verify charge/discharge power <= 50 MW
  - Compute: cycling frequency (full cycles/year) — expected 50–200
  - Plot: SOC time series, charging vs. discharging events
  - Verify: no simultaneous charging AND discharging

2d. ENERGY BALANCE VALIDATION (whole system)
For every timestep:
  - Q_demand + Q_losses + ΔQ_storage = Q_CHP + Q_boiler + Q_biomass 
                                       + Q_eboiler + Q_HP
  - Compute hourly balance error — should be < 0.1% for MILP,
    < 1% for MIQP
  - Flag any timestep with error > 5% as numerical issue

### STAGE 3: VISUALIZATION SUITE
Generate all plots in a /outputs/validation/ directory:

PLOT 1 — Time Series Comparison (Stage 1)
  - 4 subplots: T_supply_source, T_return_source, flow_main, 
    pressure_drop_main
  - Simulated vs. measured, 2 representative weeks (winter + summer)
  - Include shaded ±measurement_uncertainty band

PLOT 2 — Error Distribution Histograms (Stage 1)
  - 2x2 grid: T_supply MAE per junction, T_return RMSE, 
    flow MAPE, pressure relative error
  - Vertical line at target threshold

PLOT 3 — Scatter: Simulated vs. Measured (Stage 1)
  - T_supply: all junctions, color-coded by distance from source
  - Include R², RMSE annotation
  - 1:1 reference line + ±0.5°C and ±1.0°C tolerance bands

PLOT 4 — Heatmap: Hourly Temperature Error (Stage 1)
  - X-axis: hour of day (0–23), Y-axis: day of year
  - Color: T_supply error [°C] at main measurement point
  - Reveals systematic biases (e.g., morning ramp-up issues)

PLOT 5 — COP Scatter (Stage 2a)
  - X-axis: T_lift = T_supply - T_source [K]
  - Y-axis: COP_simulated
  - Color: ambient temperature
  - Overlay: Carnot COP * 0.5 reference curve

PLOT 6 — Electrode Boiler Dispatch vs. Price (Stage 2b)
  - Dual axis: eboiler power [MW] + electricity price [€/MWh]
  - 2 representative weeks showing price-response behavior

PLOT 7 — TES State of Charge (Stage 2c)
  - SOC time series, full year
  - Shade: charging (green) / discharging (red) / idle (grey)

PLOT 8 — Annual Energy Sankey / Stacked Bar (Stage 2d)
  - Monthly stacked bar: Q_CHP, Q_boiler, Q_biomass, Q_eboiler, Q_HP
  - Separate bar: Q_demand + Q_losses
  - Shows asset dispatch mix across seasons

PLOT 9 — Validation Summary Table
  - Rendered as a formatted table (matplotlib or HTML):
    | KPI | Measured | Simulated | MAE | MAPE | Threshold | Pass/Fail |
  - For all Stage 1 KPIs

### OUTPUT STRUCTURE
outputs/
  validation/
    stage1_timeseries_winter.png
    stage1_timeseries_summer.png
    stage1_error_histograms.png
    stage1_scatter_Tsupply.png
    stage1_heatmap_Terr.png
    stage2_COP_scatter.png
    stage2_eboiler_price.png
    stage2_TES_SOC.png
    stage2_energy_stacked_bar.png
    validation_summary_table.png
    validation_report.md   ← auto-generated text for paper

### PAPER INTEGRATION (validation_report.md template)
Auto-generate a markdown file with:
  - Table 1: Case study description (topology, n_consumers, pipe lengths)
  - Table 2: Stage 1 KPI summary with thresholds
  - Table 3: Stage 2 sanity check results
  - Key sentences for the Discussion section:
    "The calibrated model achieved a mean absolute temperature error 
     of X°C at the heat source (target: <1.0°C), consistent with 
     Maldonado et al. (2024) who reported errors below 0.5°C 
     after calibration."

### TECHNICAL REQUIREMENTS
- Python 3.10+, pandas, numpy, matplotlib, scipy
- Input: simulation results CSV from framework + measured data CSV
- All plots: 300 DPI, consistent color scheme (use seaborn-paper style)
- Figures sized for two-column journal layout (width: 88mm or 180mm)
- All KPI computations in a separate validation_kpis.py module
  with unit tests

### IMPORTANT FRAMING NOTE
In the paper, frame the validation as follows:
"Since HP and electrode boiler were installed after the measurement 
period, direct validation of asset dispatch is not feasible. Instead, 
we adopt a split validation strategy: (1) direct validation of 
network hydraulics and thermics against pre-upgrade monitoring data, 
and (2) indirect validation of asset dispatch through physics-based 
plausibility checks and energy balance verification — consistent 
with the indirect validation approach described in Ku´s et al. (2025)."