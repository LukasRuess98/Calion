# Paper Study Configs — Spatial Resolution Comparison

Three configurations for the 1-node / 5-node / 30-node comparison study.
All three represent **the same physical system** at increasing spatial resolution.
The only thing that changes between levels is the network topology.

## Controlled variables (identical across all three)

| Parameter | Value |
|-----------|-------|
| Gas boiler capacity | 200 MW |
| Boiler thermal efficiency | 0.90 (LHV) |
| Heat pump capacity | 100 MW |
| HP minimum load | 20 % |
| HP default COP | 3.5 |
| HP waste-heat sources | WRG1, WRG2 |
| Storage energy capacity | 500 MWh |
| Storage power capacity | 50 MW |
| Grid electricity surcharge | 20 EUR/MWh |
| Gas price | 45 EUR/MWh |
| Gas CO₂ factor | 200 kg CO₂/MWh_fuel |
| CO₂ price | 100 EUR/tCO₂ |
| Heat dump penalty | 10 EUR/MWh_th |
| Timestep | 1 h |
| Solver | HiGHS (appsi_highs) |
| Forecast mode | Perfect foresight (PF_ONLY) |
| Input data | data/Import_Data.csv |
| Supply temperature | 90 °C |
| Return temperature | 55 °C |
| Ground temperature | 10 °C |
| Pipe U-value (both pipes) | 0.15 W/(m·K) |

## Variable (network topology only)

| Feature | L1 (1-node) | L2 (5-node) | L3 (30-node) |
|---------|------------|------------|-------------|
| Nodes | 1 | 5 | 30 |
| Consumer nodes | 0 | 3 | 23 |
| Junction nodes | 0 | 1 | 5 |
| Pipes | 0 | 4 | 22 |
| Total pipe length | 0 m | 6 300 m | 14 250 m |
| Heat loss modelled | No | Yes | Yes |
| Pressure drop | No | Yes | Yes |
| Demand distribution | Lumped (100 %) | 3 zones (30/40/30 %) | 23 zones |

## What was changed from the original templates

| Issue | Old value | Normalized to |
|-------|-----------|--------------|
| L1 boiler capacity | 150 MW | 200 MW |
| L1 HP capacity | 80 MW | 100 MW |
| L1 storage | none | 500 MWh / 50 MW |
| L1 WRG sources | WRG1–4 | WRG1, WRG2 |
| L2 HP capacity | 150 MW (plant) + 40 MW (south) | 100 MW (plant only) |
| L2 distributed HP at south node | present | removed |
| L2 temperature key | `supply_temp_nominal_c` | `supply_temp_c` |
| L3 boiler efficiency | 0.92 | 0.90 |
| L3 HP capacity | 100 MW (correct) | unchanged |
| L3 storage | 1 000 MWh / 100 MW | 500 MWh / 50 MW |
| L3 WRG sources | none | WRG1, WRG2 |
| L3 HP min_load | not set | 0.2 |

## Expected result structure

Because L2 and L3 model pipe heat losses that L1 ignores, the optimizer
in L2 and L3 must dispatch **more** generation to cover the same end-user demand.
This means:

```
Total cost L1 ≤ Total cost L2 ≤ Total cost L3
              ↑                 ↑
         copperplate       5-node vs
           error           30-node
                           refinement
```

The magnitude of the gaps is the central result of the paper.

## Running the study

```bash
# Baseline runs (one per level)
python -m calion run --config configs/paper/L1_copperplate.yaml --output outputs/paper/L1/
python -m calion run --config configs/paper/L2_5node.yaml       --output outputs/paper/L2/
python -m calion run --config configs/paper/L3_30node.yaml      --output outputs/paper/L3/

# Sensitivity runs (7 parameters × 3 levels — use benchmark script)
python -m calion sensitivity --config configs/paper/L1_copperplate.yaml --output outputs/paper/sensitivity/L1/
python -m calion sensitivity --config configs/paper/L2_5node.yaml       --output outputs/paper/sensitivity/L2/
python -m calion sensitivity --config configs/paper/L3_30node.yaml      --output outputs/paper/sensitivity/L3/
```
