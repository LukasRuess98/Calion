# Supplementary Material S2: Complete Parameter Tables

**For:** EnerGIS: A Modular MILP Framework for Industrial Heat Network Planning and Operations
**Journal:** Applied Energy
**Date:** 2025-11-18

---

## Overview

This document provides comprehensive parameter tables for all components, costs, and configurations used in the case study. All values are based on real technology data or established literature sources.

---

## Table of Contents

1. [Heat Pump Parameters](#1-heat-pump-parameters)
2. [Thermal Generator Parameters](#2-thermal-generator-parameters)
3. [Storage Parameters](#3-storage-parameters)
4. [Grid and Cost Parameters](#4-grid-and-cost-parameters)
5. [Fuel Specifications](#5-fuel-specifications)
6. [Economic Parameters](#6-economic-parameters)
7. [Time Series Data Sources](#7-time-series-data-sources)
8. [Parameter Sensitivity Ranges](#8-parameter-sensitivity-ranges)

---

## 1. Heat Pump Parameters

### 1.1 HP1 - Large-Scale Heat Pump (Low Temperature Lift)

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Capacity ($Q_h^{\max}$) | 25.0 | MW | Case study network |
| Minimum Load ($Q_h^{\min}$) | 5.0 | MW | Manufacturer data |
| Investment Cost ($c_h^{\text{inv}}$) | 800 | €/kW | Literature avg [Bloess2018] |
| Fixed O&M ($c_h^{\text{fix}}$) | 16 | €/kW/year | 2% of CAPEX |
| Variable O&M ($c_h^{\text{var}}$) | 2.0 | €/MWh | Operating experience |
| Lifetime ($L_h$) | 20 | years | Standard assumption |
| COP Range | 3.0 - 6.0 | - | Temp-dependent (see Table 1.5) |
| Waste Heat Recovery Efficiency ($\eta_h^{\text{wrg}}$) | 0.80 | - | Design spec |

### 1.2 HP2 - Medium Temperature Lift

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Capacity | 20.0 | MW | Case study network |
| Minimum Load | 4.0 | MW | Manufacturer data |
| Investment Cost | 900 | €/kW | Higher lift → higher cost |
| Fixed O&M | 18 | €/kW/year | 2% of CAPEX |
| Variable O&M | 2.5 | €/MWh | Operating experience |
| Lifetime | 20 | years | Standard assumption |
| COP Range | 2.5 - 5.0 | - | Temp-dependent |
| Waste Heat Recovery Efficiency | 0.75 | - | Design spec |

### 1.3 HP3 & HP4 - High Temperature Lift

| Parameter | HP3 Value | HP4 Value | Unit | Source/Reference |
|-----------|-----------|-----------|------|------------------|
| Maximum Capacity | 15.0 | 15.0 | MW | Case study network |
| Minimum Load | 3.0 | 3.0 | MW | Manufacturer data |
| Investment Cost | 1000 | 1050 | €/kW | High-temp technology |
| Fixed O&M | 20 | 21 | €/kW/year | 2% of CAPEX |
| Variable O&M | 3.0 | 3.0 | €/MWh | Operating experience |
| Lifetime | 20 | 20 | years | Standard assumption |
| COP Range | 2.0 - 4.0 | 2.0 - 4.0 | - | Temp-dependent |
| Waste Heat Recovery Efficiency | 0.70 | 0.70 | - | Design spec |

### 1.4 Heat Pump COP Lookup Tables

**HP1 COP Table (Source Temperature vs. Sink Temperature)**

| T_source [°C] | T_sink=60 | T_sink=70 | T_sink=80 | T_sink=90 |
|---------------|-----------|-----------|-----------|-----------|
| 10 | 4.5 | 3.8 | 3.2 | 2.7 |
| 20 | 5.2 | 4.5 | 3.8 | 3.2 |
| 30 | 6.0 | 5.2 | 4.5 | 3.8 |
| 40 | 7.0 | 6.0 | 5.2 | 4.5 |

**Source:** Manufacturer data, bilinear interpolation used for intermediate values

**For other heat pumps:** Similar tables with adjusted performance curves (available in repository: `configs/tech_catalog.yaml`)

### 1.5 COP Calculation Method

- **Primary:** Bilinear interpolation from lookup tables
- **Fallback:** Carnot-based analytical formula with LMTD correction
  $$\text{COP} = \eta_{\text{Carnot}} \cdot \frac{T_{\text{sink}} + \Delta T_{\text{lift}}}{T_{\text{sink}} - T_{\text{source}}}$$
  where $\eta_{\text{Carnot}} = 0.55$ and $\Delta T_{\text{lift}} = 5$ K
- **Bounds:** COP $\in [1.01, 12.0]$ for numerical stability

---

## 2. Thermal Generator Parameters

### 2.1 HKW - Combined Heat and Power (Gas)

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Capacity | 30.0 | MW_th | Existing installation |
| Thermal Efficiency ($\eta_g^{\text{th}}$) | 0.50 | - | High-efficiency CHP |
| Electrical Efficiency | 0.35 | - | High-efficiency CHP |
| Power-to-Heat Ratio ($\alpha_g$) | 0.70 | - | $P_{elec}/Q_{heat}$ |
| Investment Cost | 600 | €/kW_th | CHP premium |
| Fixed O&M | 30 | €/kW/year | 5% of CAPEX |
| Variable O&M | 5.0 | €/MWh | Maintenance |
| Lifetime | 25 | years | Industrial CHP |
| Fuel Type | Natural Gas | - | - |

### 2.2 GTOST - Gas Turbine (Backup)

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Capacity | 20.0 | MW | Existing installation |
| Thermal Efficiency | 0.85 | - | Condensing technology |
| Power-to-Heat Ratio | 0.0 | - | Heat-only mode |
| Investment Cost | 300 | €/kW | Simple gas boiler |
| Fixed O&M | 10 | €/kW/year | Low maintenance |
| Variable O&M | 2.0 | €/MWh | Minimal |
| Lifetime | 20 | years | Boiler standard |
| Fuel Type | Natural Gas | - | - |

### 2.3 BMHKW - Biomass CHP

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Capacity | 15.0 | MW_th | Existing installation |
| Thermal Efficiency | 0.60 | - | Biomass CHP |
| Electrical Efficiency | 0.25 | - | Lower than gas CHP |
| Power-to-Heat Ratio | 0.42 | - | Biomass typical |
| Investment Cost | 1200 | €/kW_th | High CAPEX |
| Fixed O&M | 60 | €/kW/year | High maintenance |
| Variable O&M | 8.0 | €/MWh | Fuel handling |
| Lifetime | 20 | years | Biomass standard |
| Fuel Type | Biomass (wood chips) | - | - |

### 2.4 AVA - Waste Incineration (Existing)

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Capacity | 25.0 | MW | Existing facility |
| Thermal Efficiency | 0.70 | - | Waste-to-energy |
| Power-to-Heat Ratio | 0.30 | - | Lower elec output |
| Investment Cost | 0 | €/kW | Existing (sunk cost) |
| Fixed O&M | 80 | €/kW/year | High for waste |
| Variable O&M | 10.0 | €/MWh | Emissions treatment |
| Lifetime | 30 | years | Long-lived |
| Fuel Type | Municipal waste | - | - |

---

## 3. Storage Parameters

### 3.1 Thermal Energy Storage (TES)

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Maximum Energy Capacity ($E_s^{\max}$) | 100.0 | MWh | Design specification |
| Maximum Charging Power ($P_s^{\text{c,max}}$) | 25.0 | MW | Design specification |
| Maximum Discharging Power ($P_s^{\text{d,max}}$) | 25.0 | MW | Design specification |
| Charging Efficiency ($\eta_s^{\text{c}}$) | 0.95 | - | Heat exchanger losses |
| Discharging Efficiency ($\eta_s^{\text{d}}$) | 0.95 | - | Heat exchanger losses |
| Standby Loss Rate ($\sigma_s$) | 0.002 | 1/h | 0.2% per hour |
| Investment Cost (Energy) ($c_s^{\text{inv,E}}$) | 30 | €/kWh | Typical for large TES |
| Investment Cost (Power) ($c_s^{\text{inv,P}}$) | 100 | €/kW | Heat exchanger cost |
| Fixed O&M | 1.5 | €/kWh/year | 5% of energy CAPEX |
| Lifetime | 30 | years | Long-lived infrastructure |

### 3.2 Terminal Policies for Rolling Horizon

| Policy | Description | Constraint |
|--------|-------------|------------|
| Equal | Final SOC equals initial | $E_{s,T} = E_{s,0}$ |
| GEQ | Final SOC ≥ initial | $E_{s,T} \geq E_{s,0}$ |
| Free | No constraint | - |

**Used in case study:** GEQ policy (allows flexibility but prevents storage depletion)

---

## 4. Grid and Cost Parameters

### 4.1 Electricity Grid

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Grid Connection Capacity ($P^{\text{grid,max}}$) | 50.0 | MW | Existing substation |
| Annual Demand Charge ($c^{\text{demand}}$) | 50,000 | €/MW/year | Utility tariff |
| Average Energy Price | 60 | €/MWh | 2023 average |
| Price Range (time-varying) | 20 - 150 | €/MWh | Day-ahead market |
| Grid CO₂ Intensity (avg) | 400 | kg CO₂/MWh | National grid mix 2023 |
| CO₂ Intensity Range | 200 - 600 | kg CO₂/MWh | Time-varying |

### 4.2 Cost Parameters

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| CO₂ Price ($c^{\text{CO}_2}$) | 100 | €/t CO₂ | EU ETS 2023 avg |
| Heat Dumping Penalty ($c^{\text{dump}}$) | 1000 | €/MWh | Very high to prevent |
| Big-M Value ($M$) | 1000 | MW | Sufficient for all constraints |
| Discount Rate ($r$) | 0.04 | - | 4% real rate |

---

## 5. Fuel Specifications

### 5.1 Natural Gas

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Price ($\pi_f$) | 40 | €/MWh | 2023 avg (volatile) |
| CO₂ Emission Factor ($\rho_f^{\text{CO}_2}$) | 202 | kg CO₂/MWh | Combustion standard |
| Lower Heating Value | 10.0 | kWh/m³ | Standard |

### 5.2 Biomass (Wood Chips)

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Price | 25 | €/MWh | Regional market |
| CO₂ Emission Factor | 0 | kg CO₂/MWh | Carbon-neutral assumption |
| Lower Heating Value | 3.5 | MWh/t | Dry basis |

### 5.3 Municipal Waste

| Parameter | Value | Unit | Source/Reference |
|-----------|-------|------|------------------|
| Price | -10 | €/MWh | Tipping fee credit |
| CO₂ Emission Factor | 100 | kg CO₂/MWh | Biogenic fraction |
| Lower Heating Value | 2.5 | MWh/t | Mixed waste |

---

## 6. Economic Parameters

### 6.1 Capital Recovery Factor (CRF)

$$\text{CRF}(L, r) = \frac{r(1+r)^L}{(1+r)^L - 1}$$

| Lifetime (years) | CRF (r=4%) |
|------------------|------------|
| 15 | 0.0899 |
| 20 | 0.0736 |
| 25 | 0.0640 |
| 30 | 0.0578 |

### 6.2 Annualization Example

For a heat pump with:
- Investment cost: €800/kW
- Capacity: 10 MW = 10,000 kW
- Lifetime: 20 years
- Discount rate: 4%

**Total CAPEX:** €8,000,000
**CRF:** 0.0736
**Annualized CAPEX:** €588,800/year

---

## 7. Time Series Data Sources

### 7.1 Heat Demand

- **Source:** Hourly measurements from district heating network
- **Years:** 2022-2023
- **Resolution:** 1 hour
- **Range:** 10 - 45 MW (winter peak)
- **Annual total:** ~180,000 MWh/year
- **Profile:** Strong diurnal and seasonal variation

### 7.2 Electricity Price

- **Source:** Day-ahead market (EPEX Spot)
- **Years:** 2023
- **Resolution:** 1 hour
- **Range:** 20 - 150 €/MWh
- **Average:** 60 €/MWh (2023)
- **Profile:** Diurnal pattern with renewable penetration effects

### 7.3 Grid CO₂ Intensity

- **Source:** National grid operator (real-time data)
- **Years:** 2023
- **Resolution:** 1 hour
- **Range:** 200 - 600 kg CO₂/MWh
- **Average:** 400 kg CO₂/MWh
- **Profile:** Varies with renewable generation share

### 7.4 Waste Heat Recovery Sources

| Source | Temp [°C] | Availability [MW] | Profile |
|--------|-----------|-------------------|---------|
| WRG1 - Industrial Process | 60 | 0 - 8 | Process-dependent |
| WRG2 - Data Center | 30 | 3 - 5 | Constant base |
| WRG3 - Wastewater | 15 | 2 - 4 | Seasonal variation |

---

## 8. Parameter Sensitivity Ranges

### 8.1 Sensitivity Scenarios

| Parameter | Base Case | Low | High | Unit |
|-----------|-----------|-----|------|------|
| CO₂ Price | 100 | 0 | 200 | €/t |
| Gas Price | 40 | 25 | 60 | €/MWh |
| Elec Price (multiplier) | 1.0 | 0.5 | 1.5 | - |
| HP Investment Cost | 800 | 600 | 1000 | €/kW |
| Discount Rate | 4% | 2% | 6% | - |
| Heat Pump COP (multiplier) | 1.0 | 0.9 | 1.1 | - |

### 8.2 Rolling Horizon Sensitivity

| Parameter | Base Case | Range Tested |
|-----------|-----------|--------------|
| Horizon Length | 168 h | 24, 72, 168, 336, 720 h |
| Commit Step | 24 h | 6, 12, 24, 48 h |
| Overlap | 144 h | 0, 24, 72, 144 h |
| Terminal Policy | GEQ | Equal, GEQ, Free |

---

## References

All parameter sources are documented in the main manuscript bibliography. Key references:

1. **Heat Pumps:** Bloess et al. (2018), Applied Energy
2. **CHP Technology:** Ashouri et al. (2013), Energy
3. **Storage:** Dahash et al. (2019), Applied Energy
4. **Economic Parameters:** Danish Energy Agency Technology Catalog
5. **Emissions:** IPCC Guidelines for National Greenhouse Gas Inventories

---

## Data Availability

- **Synthetic test data:** Available in repository `data/synthetic_site/`
- **Real case study data:** Anonymized aggregated data in Supplementary S3
- **Configuration files:** All parameters in YAML format: `configs/tech_catalog.yaml`

---

**Note:** All values in this document are based on the case study and may not be directly applicable to other sites without adjustment. Users should verify parameters against local conditions and technology offerings.
