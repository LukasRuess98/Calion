# Stratified Thermal Storage - User Guide

## 🎯 Overview

EnerGIS now supports **two types of thermal energy storage**:

1. **Simple Storage** (default): Single-zone storage with uniform temperature
2. **Stratified Storage** (advanced): Two-zone thermocline model with hot/cold layers

The stratified storage model provides more accurate representation of large-scale thermal storage systems with temperature stratification.

---

## 🌡️ Stratified Storage Model

### Physical Model

The stratified storage uses a **two-zone model**:

```
┌─────────────────────┐
│   HOT ZONE (90°C)   │  ← Heat pumps charge here
│    (top layer)      │
├─────────────────────┤  ← Thermocline
│  COLD ZONE (40°C)   │  ← Return flow from consumer
│   (bottom layer)    │
└─────────────────────┘
```

### Key Features

✅ **Two-Zone Stratification**
   - Hot zone (top): Typically 90°C
   - Cold zone (bottom): Typically 40°C
   - Thermocline interface between zones

✅ **Volume-Based Energy Calculation**
   - E = ρ × V × cp × (T - T_ref)
   - Dynamic volume allocation based on charge/discharge

✅ **Geometry-Based Heat Losses**
   - Cylindrical tank geometry
   - Surface area calculation: top, side, bottom
   - U-values (heat transfer coefficients) for each surface
   - Heat loss to ambient/ground

✅ **Linear Formulation**
   - Compatible with MIP solvers (Gurobi, CPLEX)
   - Fixed design temperatures (no non-linear constraints)
   - Piecewise-linear loss approximation

---

## 🚀 Usage

### Option 1: Network Designer Dashboard

1. **Start Dashboard:**
   ```bash
   python start_network_designer.py
   ```

2. **Add Storage Component:**
   - Click "Speicher" tool
   - Place storage on canvas

3. **Configure Storage:**
   - Select storage component
   - Properties panel opens on the right
   - **Speicher-Typ**: Select `stratified`
   - Set capacity (MWh)
   - Set efficiency

4. **Export:**
   - Click "YAML exportieren"
   - File saved to: `exports/network_designer_export.yaml`

The exported YAML will include:
```yaml
system:
  storage:
    enabled: true
    type: stratified  # ← Key parameter
    T_hot_C: 90.0
    T_cold_C: 40.0
    T_ambient_C: 15.0
    T_ground_C: 10.0
    aspect_ratio: 1.5
    geometry_type: tank
    U_top: 0.3
    U_side: 0.2
    U_bottom: 0.15
    # ... other parameters
```

### Option 2: Manual YAML Configuration

Edit your system configuration file:

```yaml
system:
  storage:
    enabled: true
    type: stratified  # 'simple' or 'stratified'

    # Common parameters
    soc0_mwh: 0.0
    eff_charge: 0.98
    eff_discharge: 0.98

    # Investment parameters
    investment:
      enabled: true
      energy_capacity_min_mwh: 10.0
      energy_capacity_max_mwh: 200.0
      power_capacity_min_mw: 5.0
      power_capacity_max_mw: 100.0

    # Stratified storage specific parameters
    T_hot_C: 90.0          # Hot zone temperature
    T_cold_C: 40.0         # Cold zone temperature
    T_ambient_C: 15.0      # Ambient temperature for losses
    T_ground_C: 10.0       # Ground temperature for bottom losses

    # Geometry
    aspect_ratio: 1.5      # Height/Diameter ratio
    geometry_type: tank    # 'tank' or 'pit'

    # Heat transfer coefficients [W/(m²·K)]
    U_top: 0.3             # Top surface
    U_side: 0.2            # Side surface
    U_bottom: 0.15         # Bottom surface (better insulated)

    # Initial state
    V_hot_init_fraction: 0.5  # Initial hot zone fraction (0-1)
```

### Option 3: Programmatic API

```python
from energis.io.network_designer import create_network_designer

designer = create_network_designer()

# Add storage with stratified type
designer.add_component(x=400, y=300, comp_type='storage')
storage = designer.components[-1]

# Configure as stratified
storage.properties['storage_type'] = 'stratified'
storage.properties['capacity_mwh'] = 100.0
storage.properties['efficiency'] = 0.98
storage.status = 'investment'

# Export
designer.export_to_yaml('exports/my_network.yaml')
```

---

## 📊 Comparison: Simple vs. Stratified

| Feature | Simple Storage | Stratified Storage |
|---------|----------------|-------------------|
| **Model** | Single uniform temperature | Two-zone (hot/cold) |
| **Temperature** | Not explicitly modeled | Explicit T_hot, T_cold |
| **Heat Losses** | Constant % per hour | Geometry-based (surface area) |
| **Complexity** | Lower (fewer variables) | Higher (volume dynamics) |
| **Accuracy** | Good for small systems | Better for large systems |
| **Use Cases** | - Small buffers<br>- Simple analysis | - District heating<br>- Large PTES<br>- Detailed analysis |
| **Solver Time** | Faster | Slightly slower |

### When to Use Each

**Use Simple Storage when:**
- System is small (< 10 MWh)
- Temperature stratification is not critical
- Fast optimization is needed
- Initial design/screening studies

**Use Stratified Storage when:**
- Large-scale systems (> 50 MWh)
- Temperature stratification matters
- Detailed performance analysis needed
- Pit thermal energy storage (PTES)
- District heating applications

---

## 🔧 Configuration Parameters

### Thermal Parameters

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `T_hot_C` | 90.0 | °C | Hot zone temperature (top) |
| `T_cold_C` | 40.0 | °C | Cold zone temperature (bottom) |
| `T_ambient_C` | 15.0 | °C | Ambient temperature for losses |
| `T_ground_C` | 10.0 | °C | Ground temperature for bottom losses |

**Typical Values:**
- **District Heating**: T_hot = 90-95°C, T_cold = 40-50°C
- **Industrial**: T_hot = 80-120°C, T_cold = 30-60°C
- **PTES**: T_hot = 80-90°C, T_cold = 30-40°C

### Geometry Parameters

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `aspect_ratio` | 1.5 | - | Height/Diameter ratio |
| `geometry_type` | tank | - | 'tank' or 'pit' |

**Aspect Ratios:**
- **Above-ground tanks**: 1.5-2.0 (tall, cylindrical)
- **PTES (pit storage)**: 0.3-0.5 (shallow, wide)
- **Underground tanks**: 1.0-1.5 (medium)

Geometry is automatically calculated from capacity (MWh) and aspect ratio.

### Heat Transfer Coefficients

| Parameter | Default | Unit | Description |
|-----------|---------|------|-------------|
| `U_top` | 0.3 | W/(m²·K) | Top surface U-value |
| `U_side` | 0.2 | W/(m²·K) | Side surface U-value |
| `U_bottom` | 0.15 | W/(m²·K) | Bottom surface U-value |

**Typical Values:**
- **Well-insulated tanks**: 0.1-0.3 W/(m²·K)
- **Standard tanks**: 0.3-0.5 W/(m²·K)
- **PTES (ground contact)**: 0.05-0.15 W/(m²·K) (better insulation from ground)

**Note:** Lower U-values = better insulation = less heat loss

---

## 📐 Geometry Calculation

The model automatically calculates tank dimensions based on:

### Above-Ground Tank (geometry_type='tank')

```python
# Input: capacity_mwh = 100 MWh, aspect_ratio = 1.5

# Convert to volume
V = capacity / (ρ × cp × ΔT) = 100 MWh / (1000 kg/m³ × 4.186 kJ/kg·K × 50K)
V ≈ 478 m³

# Calculate dimensions (H = 1.5 × D)
D ≈ 8.5 m (diameter)
H ≈ 12.8 m (height)

# Surface areas
A_top = A_bottom ≈ 57 m²
A_side ≈ 342 m²
A_total ≈ 456 m²
```

### Pit Thermal Energy Storage (geometry_type='pit')

```python
# Input: capacity_mwh = 1000 MWh, aspect_ratio = 0.4 (automatically capped at 0.5)

# Much larger, shallower
V ≈ 4780 m³
D ≈ 36 m (diameter)
H ≈ 14 m (height)

# Larger surface area
A_total ≈ 3600 m²

# Benefits: Ground contact provides insulation
```

---

## 📊 Results and Outputs

After optimization, the stratified storage provides:

### Optimization Results

```python
{
    'capacity_energy_mwh': 85.3,      # Optimized total capacity
    'capacity_power_mw': 42.7,         # Optimized power capacity
    'geometry': {
        'diameter_m': 7.8,
        'height_m': 11.7,
        'A_total_m2': 382.5
    }
}
```

### Timeseries Results

```python
{
    'Q_charge': [0, 15.3, 22.1, ...],      # Charging power [MW]
    'Q_discharge': [18.2, 0, 0, ...],      # Discharging power [MW]
    'E_stored': [45.2, 60.5, 82.6, ...],   # Total stored energy [MWh]
    'V_hot_m3': [215, 287, 392, ...],      # Hot zone volume [m³]
    'V_cold_m3': [263, 191, 86, ...],      # Cold zone volume [m³]
    'SOC': [0.53, 0.71, 0.97, ...],        # State of charge [0-1]
    'Q_loss': [0.8, 0.9, 1.2, ...],        # Heat losses [MW]
}
```

### Loss Analysis

Heat losses depend on:
1. **Surface area** (larger storage = more losses)
2. **Temperature difference** (ΔT to ambient/ground)
3. **U-values** (insulation quality)

```python
Q_loss = (A_top × U_top × (T_hot - T_ambient) +
          A_side × U_side × (T_avg - T_ambient) +
          A_bottom × U_bottom × (T_cold - T_ground)) / 1000  # MW
```

Typical losses: 0.5-2% of capacity per day

---

## 🔬 Advanced Configuration Examples

### Example 1: Large District Heating PTES

```yaml
system:
  storage:
    type: stratified
    geometry_type: pit
    aspect_ratio: 0.4

    # High temperatures
    T_hot_C: 95.0
    T_cold_C: 45.0
    T_ambient_C: 10.0
    T_ground_C: 8.0

    # Better insulation for underground
    U_top: 0.15
    U_side: 0.10
    U_bottom: 0.08

    # Large capacity
    investment:
      enabled: true
      energy_capacity_max_mwh: 5000.0
      power_capacity_max_mw: 250.0
```

### Example 2: Industrial High-Temperature Storage

```yaml
system:
  storage:
    type: stratified
    geometry_type: tank
    aspect_ratio: 2.0  # Tall tank

    # Higher temperatures
    T_hot_C: 120.0
    T_cold_C: 60.0
    T_ambient_C: 20.0

    # Standard insulation
    U_top: 0.35
    U_side: 0.25
    U_bottom: 0.20

    # Medium capacity
    investment:
      enabled: true
      energy_capacity_max_mwh: 150.0
      power_capacity_max_mw: 75.0
```

### Example 3: Seasonal Storage

```yaml
system:
  storage:
    type: stratified
    geometry_type: pit
    aspect_ratio: 0.35  # Very shallow

    # Moderate temperatures
    T_hot_C: 85.0
    T_cold_C: 35.0
    T_ambient_C: 12.0
    T_ground_C: 10.0

    # Excellent insulation
    U_top: 0.10
    U_side: 0.08
    U_bottom: 0.06

    # Very large capacity
    investment:
      enabled: true
      energy_capacity_max_mwh: 10000.0  # 10 GWh
      power_capacity_max_mw: 100.0
```

---

## 🐛 Troubleshooting

### Issue: "Storage losses too high"

**Symptoms:** Excessive heat losses in results

**Solutions:**
1. Check U-values - should be < 0.5 W/(m²·K) for good insulation
2. Verify temperatures - large ΔT increases losses
3. Consider `geometry_type: 'pit'` for underground storage
4. Increase insulation: Lower U_top, U_side, U_bottom

### Issue: "Infeasible solution with stratified storage"

**Symptoms:** Solver cannot find solution

**Solutions:**
1. Try increasing capacity bounds
2. Check that T_hot > T_cold (must be strictly greater)
3. Verify power/energy ratio is reasonable (P ≈ E/2 to E/4)
4. Try simple storage first to debug other issues

### Issue: "Results similar to simple storage"

**Symptoms:** Minimal difference between models

**Possible Causes:**
- Storage capacity too small (< 10 MWh)
- Low utilization (rarely charged/discharged)
- Temperature difference too small

**Expected:** For large systems (> 50 MWh), stratified model should show 2-5% lower losses

---

## 📚 References

### Model Documentation

- **Stratified Storage Block**: `energis/models/blocks/stratified_storage.py`
- **Simple Storage Block**: `energis/models/blocks/storage.py`
- **System Builder**: `energis/models/system_builder.py` (lines 576-631)

### Related Literature

1. **PTES (Pit Thermal Energy Storage):**
   - Bauer et al., "Pit and borehole thermal energy storage", Solar Energy (2012)
   - Large-scale seasonal storage for solar district heating

2. **Stratified Storage Modeling:**
   - Kleinbach et al., "Performance of one-dimensional models for stratified thermal storage tanks"
   - Two-zone models balance accuracy and computational efficiency

3. **District Heating:**
   - IEA District Heating and Cooling Programme
   - Guidelines for thermal storage in district heating systems

---

## ✅ Summary

**Stratified Storage is now fully integrated!**

- ✅ Two-zone thermocline model implemented
- ✅ Geometry-based heat loss calculation
- ✅ Linear formulation (MIP-compatible)
- ✅ Network Designer UI support
- ✅ YAML configuration support
- ✅ System builder integration complete

**Choose the right model for your use case:**
- **Simple**: Fast, good for screening
- **Stratified**: Accurate, good for detailed design

For questions or issues, see examples in:
- `notebooks/complete_workflow.ipynb`
- `examples/stratified_storage_example.py` (to be created)
