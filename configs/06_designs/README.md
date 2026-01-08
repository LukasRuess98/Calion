# Design Files

This directory contains design specifications for system configurations.

## What is a Design?

A design defines the **fixed capacities** for investment-optimizable components:
- Heat pump capacities (MW)
- Storage capacity (MWh) and power (MW)
- Which components are enabled/disabled

## Design Modes

In your scenario config, you can specify how designs are handled:

```yaml
scenario:
  design:
    mode: file                    # Load from JSON file
    file: 06_designs/optimal.json
```

Available modes:

| Mode | Description |
|------|-------------|
| `file` | Load design from JSON file |
| `optimize` | Optimize in Window 0, fix for subsequent windows |
| `inline` | Define values directly in scenario YAML |
| `none` | No fixation (all windows optimize independently) |

## File Format

```json
{
  "version": "1.0",
  "description": "Optimal design for Stadtbach Q1 2023",

  "heat_pumps": {
    "HP1": { "capacity_mw": 50.0, "enabled": true },
    "HP2": { "capacity_mw": 0.0, "enabled": false }
  },

  "storage": {
    "capacity_mwh": 10000.0,
    "power_mw": 200.0,
    "enabled": true
  }
}
```

## Creating a New Design

### Option 1: Run optimization and save result

```yaml
scenario:
  design:
    mode: optimize
    save_to: 06_designs/my_new_design.json
```

### Option 2: Create manually

Copy an existing design file and modify the values.

## Available Designs

- `stadtbach_optimal.json` - Optimized design for full system
- `stadtbach_baseline.json` - Baseline without HP/storage
- `stadtbach_max_storage.json` - Maximum storage configuration
