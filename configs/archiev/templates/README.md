# Example Configurations

Three example configs that demonstrate the unified config schema at different
detail levels.

## Prerequisites

All examples expect an Excel file **`Import_Data.xlsx`** in the working
directory (or the path configured under `site.input_xlsx`).  The file must
contain at least the columns referenced by the config's `site.columns` and
`network.nodes.*.demand.column` entries.

## Configs

| File | Level | Runnable? | Description |
|---|---|---|---|
| `level1_copperplate.yaml` | 1 | Yes (with data) | Single node, no pipes, no network physics |
| `level2_5node.yaml` | 2 | Yes (with data) | 5-node network with pipes, heat loss and pressure drop |
| `level3_30node_template.yaml` | 3 | **No** (template) | 30-node structure template — requires 23 zone demand columns that are not in the standard data file |

## Running

```bash
# Level 1 — copperplate
python -m calion.run configs/templates/level1_copperplate.yaml

# Level 2 — 5-node network
python -m calion.run configs/templates/level2_5node.yaml

# With Rolling Horizon instead of Perfect Foresight
python -m calion.run configs/templates/level1_copperplate.yaml --run-mode RH_ONLY
```
