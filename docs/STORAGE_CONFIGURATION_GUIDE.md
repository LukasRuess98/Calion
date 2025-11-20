# Storage Configuration Guide

This guide explains how to configure thermal energy storage in the EnerGIS framework, including the choice between simple and stratified storage models.

---

## Overview

The framework supports two storage models:

1. **Simple Storage** (`type: simple`) - Single-zone model with constant losses
2. **Stratified Storage** (`type: stratified`) - Advanced 2-zone thermocline model

---

## 1. Simple Storage (Default)

### When to Use
- Fast prototyping and initial system design
- When thermal stratification effects are negligible
- When detailed temperature dynamics are not required
- For smaller storage volumes (< 100 m³)

### Configuration
```yaml
system:
  storage:
    enabled: true
    type: simple  # or omit (default)

    # Capacity
    min_energy_mwh: 0.0
    max_energy_mwh: 100.0
    max_power_mw: 30.0

    # Efficiency
    eff_charge: 0.95
    eff_discharge: 0.95
    loss_hour: 0.0005  # Constant hourly loss rate

    # Initial state
    soc0_mwh: 50.0

    # Investment (optional)
    investment:
      enabled: false
```

### Features
- ✅ Fast computation
- ✅ Simple parameterization
- ✅ Constant loss rate
- ✅ Power/energy decoupling
- ❌ No thermal stratification
- ❌ No temperature-dependent losses

---

## 2. Stratified Storage (Advanced)

### When to Use
- Large-scale district heating storage (> 100 m³)
- When thermal stratification is important
- For accurate thermal loss modeling
- When comparing different storage geometries
- For publication-quality results

### Configuration
```yaml
system:
  storage:
    enabled: true
    type: stratified  # ← KEY DIFFERENCE

    # Capacity (same as simple)
    min_energy_mwh: 0.0
    max_energy_mwh: 200.0
    max_power_mw: 50.0

    # Thermal parameters (stratified-specific)
    T_hot_C: 90.0        # Hot zone temperature [°C]
    T_cold_C: 40.0       # Cold zone temperature [°C]
    T_ambient_C: 15.0    # Ambient air temperature [°C]
    T_ground_C: 10.0     # Ground temperature [°C]

    # Geometry (stratified-specific)
    aspect_ratio: 1.5    # Height/Diameter ratio
    geometry_type: tank  # "tank" or "pit"

    # Heat transfer coefficients [W/(m²·K)]
    U_top: 0.3          # Top surface
    U_side: 0.2         # Side walls
    U_bottom: 0.15      # Bottom surface

    # Efficiency (applies to both types)
    eff_charge: 0.95
    eff_discharge: 0.95

    # Initial state
    soc0_mwh: 50.0
    V_hot_init_fraction: 0.5  # 0.0 = fully cold, 1.0 = fully hot
```

### Features
- ✅ Realistic thermal stratification
- ✅ Temperature-dependent losses
- ✅ Geometry-aware (tank vs pit)
- ✅ Separate hot/cold zones
- ✅ More accurate for large storage
- ❌ Slower computation (more variables)
- ❌ More parameters to configure

---

## Parameter Selection Guide

### Temperature Levels

**T_hot_C (Hot Zone Temperature)**
- District heating supply: 80-95°C
- Industrial process heat: 100-150°C
- Low-temperature networks: 50-70°C

**T_cold_C (Cold Zone Temperature)**
- District heating return: 35-50°C
- Industrial return: 40-60°C
- Low-temperature return: 25-40°C

**ΔT (Temperature Difference)**
- Larger ΔT → Better stratification
- Minimum 20°C recommended
- Typical: 40-50°C

**T_ambient_C (Ambient Temperature)**
- Use annual average for your location
- Europe: 8-15°C
- Southern Europe: 12-18°C
- Northern Europe: 5-10°C

**T_ground_C (Ground Temperature)**
- Typically 2-5°C below ambient
- Europe: 8-12°C at 5m depth
- Fairly constant year-round

### Geometry

**Aspect Ratio (H/D)**
- **Above-ground tanks:** 1.0-2.0
  - Higher ratio → Better stratification
  - Lower ratio → Easier construction
  - Typical: 1.5

- **Pit storage:** 0.3-1.0
  - Lower ratio → Lower cost
  - Larger surface area
  - Typical: 0.5

**Geometry Type**
- **tank:** Cylindrical steel tank (above ground)
- **pit:** Excavated pit storage (underground)

### Heat Transfer Coefficients [W/(m²·K)]

**Above-Ground Insulated Tank:**
```yaml
U_top: 0.3      # Highest losses (convection + radiation)
U_side: 0.2     # Medium losses (insulation)
U_bottom: 0.15  # Lower losses (foundation)
```

**Underground Pit Storage:**
```yaml
U_top: 0.25     # Cover with insulation
U_side: 0.1     # Earth provides insulation
U_bottom: 0.08  # Deep earth, stable temperature
```

**High-Performance Insulation:**
```yaml
U_top: 0.15
U_side: 0.12
U_bottom: 0.10
```

### Initial State

**soc0_mwh (Initial Energy Content)**
- Start with realistic value
- For cyclic operation: Use typical mid-range value
- For target operation: Use target value

**V_hot_init_fraction (Initial Hot Fraction)**
- `0.0` - Fully cold (all return temperature)
- `0.5` - Half hot, half cold (typical start)
- `1.0` - Fully hot (all supply temperature)
- Affects first few timesteps only
- For cyclic operation: Less critical (converges)

---

## Comparison: Simple vs Stratified

| Aspect | Simple Storage | Stratified Storage |
|--------|----------------|-------------------|
| **Computation Time** | Fast | Slower (~2-3x) |
| **Variables per Timestep** | 3-5 | 10-15 |
| **Loss Modeling** | Constant rate | Temperature-dependent |
| **Thermal Stratification** | No | Yes (hot/cold zones) |
| **Geometry Awareness** | No | Yes (tank/pit) |
| **Parameter Count** | Low (~5) | High (~15) |
| **Use Case** | Preliminary design | Detailed analysis |
| **Accuracy** | Good for small storage | Excellent for large storage |

---

## Example: Comparing Both Models

### Run with Simple Storage
```bash
python -m energis.run \
  configs/base.yaml \
  configs/systems/baseline.system.yaml \
  configs/scenarios/perfect_forecast_full_year.scenario.yaml
```

### Run with Stratified Storage
```bash
python -m energis.run \
  configs/base.yaml \
  configs/systems/stratified_storage_example.system.yaml \
  configs/scenarios/perfect_forecast_full_year.scenario.yaml
```

### Compare Results
The stratified model will typically show:
- Higher losses in summer (larger ΔT to ambient)
- Lower losses in winter (smaller ΔT to ambient)
- More realistic cycling patterns
- Better representation of part-load operation

---

## Investment Optimization

Both storage types support investment optimization:

```yaml
storage:
  investment:
    enabled: true
    energy_capacity_min_mwh: 50.0    # Minimum size
    energy_capacity_max_mwh: 500.0   # Maximum size
    power_capacity_min_mw: 10.0
    power_capacity_max_mw: 100.0
    initial_energy_capacity_mwh: 100.0  # Starting guess
    initial_power_capacity_mw: 30.0

    # Cost parameters
    energy_capex_eur_per_mwh: 50.0    # €/MWh for energy capacity
    power_capex_eur_per_mw: 200.0     # €/MW for power capacity
    lifetime_years: 20.0
```

**Note:** Stratified storage typically has:
- Higher specific costs (€/MWh) due to insulation
- But better performance (lower losses)
- Optimization finds the cost-optimal trade-off

---

## Terminal Conditions

Both storage types support the same terminal conditions:

### Cyclic Operation (Recommended)
```yaml
storage:
  terminal:
    state: cyclic   # SOC(T) = SOC(0)
    policy: equal   # Enforce equality
```

### Free Terminal State
```yaml
storage:
  terminal:
    state: free     # No constraint on SOC(T)
```

### Target Terminal State
```yaml
storage:
  terminal:
    state: target   # SOC(T) = target_mwh
    policy: equal   # or "geq" for ≥ constraint
    target_mwh: 50.0
```

---

## Troubleshooting

### Stratified Storage Not Loading
**Error:** `[BUILD] Using simple storage (single-zone model)`

**Solution:** Check `type: stratified` is set correctly
```yaml
storage:
  type: stratified  # Must be lowercase
```

### Unrealistic Losses
**Symptom:** Very high or very low storage losses

**Check:**
1. U-values are in W/(m²·K), not W/(m·K)
2. Temperatures are in °C, not K
3. Temperature differences are realistic (T_hot > T_cold)

### Poor Stratification
**Symptom:** Hot zone volume oscillates unrealistically

**Solutions:**
1. Increase aspect_ratio (makes stratification more stable)
2. Check T_hot and T_cold are sufficiently different (> 20°C)
3. Verify initial V_hot_init_fraction is reasonable (0.3-0.7)

---

## References

For detailed information on the stratified storage model:
- See `energis/models/blocks/stratified_storage.py` for implementation
- See `examples/stratified_storage_integration.py` for usage example
- See original research papers on stratified thermal storage

---

## Quick Start Checklist

**For Simple Storage:**
- [ ] Set `type: simple` (or omit)
- [ ] Configure capacity (energy, power)
- [ ] Set efficiencies
- [ ] Set loss_hour
- [ ] Done!

**For Stratified Storage:**
- [ ] Set `type: stratified`
- [ ] Configure capacity (energy, power)
- [ ] Set efficiencies
- [ ] Define temperature levels (T_hot_C, T_cold_C, T_ambient_C, T_ground_C)
- [ ] Choose geometry (aspect_ratio, geometry_type)
- [ ] Set U-values (U_top, U_side, U_bottom)
- [ ] Set initial state (soc0_mwh, V_hot_init_fraction)
- [ ] Done!

---

**Need help?** Check the example config: `configs/systems/stratified_storage_example.system.yaml`
