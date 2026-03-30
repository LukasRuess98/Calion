# CALION Config Structure v2.0

## 📁 Directory Structure

```
configs/
├── tech_library/           # Technology templates (reusable)
│   ├── heat_pumps.yaml     # HP performance curves, COP models
│   ├── storage.yaml        # Storage efficiencies, thermal models
│   ├── generators.yaml     # Boilers, CHP efficiencies
│   ├── p2h.yaml            # Power-to-Heat conversion
│   ├── pipes.yaml          # Pipe friction, heat loss models
│   ├── fluids.yaml         # Water properties (cp, rho, μ)
│   └── fuels.yaml          # Fuel properties, prices, emissions
│
├── assets/                 # Site-specific asset definitions
│   └── stadtbach/
│       ├── components.yaml        # All components (existing + expansion)
│       ├── grid.yaml              # Grid connection & pricing
│       ├── network_topology.yaml  # Multi-node thermal network
│       └── data_sources.yaml      # Time series mappings
│
└── scenarios/              # Optimization scenarios
    ├── stadtbach_baseline_2023.yaml        # Dispatch only
    └── stadtbach_capacity_expansion.yaml   # Investment optimization
```

---

## 🎯 Key Concepts

### 1. **Unified Asset Model** (No More Brownfield/Greenfield!)

Every component has:
- `existing`: What's already installed
- `expansion`: What can be added

```yaml
heat_pumps:
  HP1:
    technology: high_temp_heat_pump    # References tech_library

    existing:
      thermal_capacity_mw: 25.0        # Already installed
      commissioning_year: 2018

    expansion:
      enabled: true
      min_additional_capacity_mw: 5.0  # Can add 5-75 MW
      max_additional_capacity_mw: 75.0
      capex_eur_per_mw: 400000
```

**Benefits:**
- ✅ Brownfield = `existing > 0`
- ✅ Greenfield = `existing = 0`
- ✅ Expansion = `existing > 0 AND expansion.enabled = true`
- ✅ **One model for everything!**

### 2. **Multi-Node Thermal Network**

```yaml
networks:
  DH_primary:
    nodes:
      central_plant:
        type: producer
        components: [HKW, GTOST, HP1, TES1]

      stadtbach_west:
        type: consumer
        demand_column: "demand_west_MW"

      junction_1:
        type: junction           # Distribution point

    pipes:
      pipe_plant_to_junction:
        from_node: central_plant
        to_node: junction_1
        length_m: 1200
        diameter_mm: 400
        # ✅ Pressure losses calculated
        # ✅ Temperature losses calculated
        # ✅ Time delay modeled
```

**Models:**
- ✅ Mass balance at each node
- ✅ Enthalpy balance at each node
- ✅ Pressure drop in pipes (Darcy-Weisbach)
- ✅ Temperature loss in pipes
- ✅ Transport time delay

### 3. **Technology Library** (Reusable Templates)

```yaml
# tech_library/heat_pumps.yaml
heat_pumps:
  high_temp_heat_pump:
    cop_model:
      type: lookup_table_2d
      lookup_table:
        source_temps_K: [273, 283, 293, ...]
        sink_temps_K: [343, 353, 363, ...]
        cop_values:
          - [2.45, 2.86, 3.43, ...]    # COP matrix
    costs:
      capex_eur_per_mw: 400000
      lifetime_yr: 15
```

**All technologies defined once, referenced everywhere!**

---

## 🚀 Usage Examples

### Example 1: Dispatch Optimization (Fixed Capacities)

```bash
calion optimize scenarios/stadtbach_baseline_2023.yaml
```

- Uses `existing` capacities (no investment)
- Optimizes hourly dispatch
- Fast (LP problem)

### Example 2: Capacity Expansion (Investment)

```bash
calion optimize scenarios/stadtbach_capacity_expansion.yaml
```

- Optimizes `expansion` capacities
- Determines which assets to build
- Slower (MILP problem)

### Example 3: Sensitivity Analysis

```bash
calion sensitivity scenarios/stadtbach_capacity_expansion.yaml \
  --param co2_price --range 80,120,200
```

---

## 📊 Complete Stadtbach Example

### Components (assets/stadtbach/components.yaml)

**Existing Assets:**
- CHP Plants: HKW (75 MW), GTOST (41.3 MW), BMHKW (15 MW)
- Boilers: HWS (45 MW), HWW (45 MW)
- P2H: 10 MW (can expand to 50 MW)
- Waste Heat: AVA (45 MW)
- Storage: 500 MWh (can expand to 2000 MWh)

**Investment Options:**
- Heat Pumps: HP1-HP4 (4 waste heat sources, 0-50 MW each)
- P2H Expansion: +5-40 MW
- Storage Expansion: +100-1500 MWh

### Network (assets/stadtbach/network_topology.yaml)

**6 Nodes:**
- 1 Producer (central_plant)
- 4 Consumers (north, west, east, industrial)
- 2 Junctions (distribution)

**6 Pipes:**
- DN250-DN400 pipes
- Total length: ~10 km
- Pressure/temperature modeled

### Scenarios

**Baseline 2023:** Dispatch only (€45M fuel + electricity)

**Capacity Expansion:** Investment + dispatch
- Heat Pump 1: +30 MW (@€12M)
- Heat Pump 2: +25 MW (@€10M)
- Storage: +800 MWh (@€4M)
- **Total Investment: €26M**
- **Annual Savings: €4.5M** (fuel + CO2)
- **Payback: 5.8 years**

---

## 🔄 Migration from Old Config

### Old Format:
```yaml
system:
  heat_pumps:
    - id: HP1
      max_th_mw: 50.0              # ❌ Mixed brownfield/greenfield
      investment:
        enabled: true
```

### New Format:
```yaml
heat_pumps:
  HP1:
    technology: high_temp_heat_pump
    existing:
      thermal_capacity_mw: 25.0    # ✅ Clear: 25 MW existing
    expansion:
      enabled: true
      max_additional_capacity_mw: 25.0  # ✅ Can add 25 MW more
```

---

## ✅ Validation

Check config before optimization:

```bash
calion config validate scenarios/stadtbach_capacity_expansion.yaml
```

**Checks:**
- ✅ All referenced technologies exist in tech_library
- ✅ All referenced components exist in assets
- ✅ Time series columns exist in data files
- ✅ Value ranges are valid
- ✅ Network topology is connected

---

## 📖 Full Documentation

See detailed documentation:
- `docs/CONFIG_REFACTORING_PROPOSAL.md` - Design rationale
- `docs/CONFIG_GAP_ANALYSIS.md` - Old vs new comparison
- `docs/NETWORK_PHYSICS_MODEL.md` - Multi-node network equations

---

**Version:** 1.0.0-alpha
**Status:** ✅ Complete Implementation
**Date:** 2026-03-28
