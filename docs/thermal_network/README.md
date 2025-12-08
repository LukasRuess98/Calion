# Thermal Network Features - Planning Documentation

⚠️ **IMPORTANT: STATUS = PLANNING ONLY - NOT IMPLEMENTED** ⚠️

## Overview

This directory contains **comprehensive planning documentation** for future thermal network features. These documents describe advanced thermal-hydraulic network modeling capabilities that are **NOT YET IMPLEMENTED** in the codebase.

## Status: 📋 PLANNING / 🚫 NOT IMPLEMENTED

The documentation in this directory is **design documentation only**. The described features do NOT exist in code. This is reference material for future development.

## What's Documented Here

### 1. Requirements Specification
**File:** `thermal_network_requirements.md` (65 KB)

Detailed requirements for:
- Geographic network modeling (nodes with coordinates)
- Supply/return pipe topology
- Pressure, temperature, and mass flow physics
- Pipe components with heat loss and pressure drop
- Investment optimization for pipe diameters

### 2. Mathematical Design
**File:** `thermal_network_mathematical_design.md` (31 KB)

Mathematical formulations:
- Sets, indices, and notation
- Variables (continuous, binary, SOS2)
- Constraints (mass balance, energy balance, pressure drop)
- Linearization techniques (PWL, McCormick envelopes)
- Objective function components

### 3. Implementation Plan
**File:** `thermal_network_implementation_plan.md` (74 KB)

Step-by-step implementation roadmap:
- Phase 1: Core infrastructure
- Phase 2: Basic network components
- Phase 3: Physics and constraints
- Phase 4: Investment optimization
- Phase 5: Validation and testing

### 4. Cooling & Heat Recovery Extension
**File:** `thermal_network_cooling_heat_recovery_extension.md` (26 KB)

Extensions for:
- Cooling networks (4-pipe systems)
- Waste heat recovery integration
- Bidirectional flows
- Multi-temperature networks

### 5. Future Extensions
**File:** `thermal_network_future_extensions.md` (16 KB)

Long-term vision:
- Dynamic network operation
- Stochastic optimization
- Multi-objective optimization
- Real-time control integration

## What EXISTS in the Codebase

✅ **Excel-to-YAML Parser** (`energis/utils/thermal_network_excel_parser.py`)
- Parses thermal network scenarios from Excel
- Includes pipe, node, producer, consumer data structures
- **BUT**: Does NOT create actual network physics constraints
- **Purpose**: Data structure only, not thermal-hydraulic simulation

✅ **Brownfield Configuration Support** (Config YAML)
- `existing` vs `invest` flags for components
- Investment optimization framework
- **BUT**: Only for point components (heat pumps, storage)
- **NOT**: For network topology optimization

## What Does NOT Exist

❌ **Network Physics Implementation**
- No pipe pressure drop constraints
- No heat loss calculations
- No mass flow balances
- No temperature mixing
- No geodetic pressure terms

❌ **Network Components**
- No `PipeBlock` class
- No `NodeBlock` class
- No `JunctionBlock` class
- No `PumpBlock` class

❌ **Geographic Modeling**
- No coordinate-based layout
- No distance calculations
- No GIS integration
- No network visualization

❌ **Thermal-Hydraulic Solver**
- No coupled temperature-pressure solution
- No return pipe generation in solver
- No network flow direction optimization

## When Will This Be Implemented?

**Timeline:** TBD - Requires dedicated development effort

**Estimated effort:** 6-8 weeks for basic implementation
- Week 1-2: Core infrastructure (PipeBlock, NodeBlock)
- Week 3-4: Physics constraints (pressure, temperature, flow)
- Week 5-6: Investment optimization
- Week 7-8: Testing, validation, documentation

**Recommendation:** Treat as separate Epic/Project when resources available

## How to Use This Documentation

### For Future Development
1. Read `thermal_network_requirements.md` first
2. Review `thermal_network_mathematical_design.md` for equations
3. Follow `thermal_network_implementation_plan.md` as roadmap
4. Reference extension docs for advanced features

### For Current Users
**Do NOT expect these features to work!**

The Excel parser can **read** network data, but the framework does **NOT**:
- Optimize pipe diameters
- Calculate pressure drops
- Model heat losses
- Enforce temperature constraints
- Optimize network topology

For now, use the framework for:
- ✅ Point-source optimization (heat pumps, storage, generators)
- ✅ Investment planning (existing vs new components)
- ✅ Energy balance optimization
- ✅ Cost minimization
- ❌ **NOT** full thermal network simulation

## Contact & Questions

If you need thermal network features:
1. Check if point-source optimization is sufficient
2. Consider external tools (e.g., TESPy, Modelica) for detailed network simulation
3. Integrate results back into EnerGIS for system-level optimization

## Related Documentation

See also:
- `docs/excel_import_feature.md` - Excel import functionality (works!)
- `docs/brownfield_quickstart_guide.md` - Brownfield scenarios (works!)
- `FRAMEWORK_ARCHITECTURE_ANALYSIS.md` - Current framework capabilities
- `IMPROVEMENT_RECOMMENDATIONS.md` - Enhancement suggestions

---

**Last Updated:** 2025-12-08
**Status:** Planning Documentation Only
**Implementation:** Not Started
