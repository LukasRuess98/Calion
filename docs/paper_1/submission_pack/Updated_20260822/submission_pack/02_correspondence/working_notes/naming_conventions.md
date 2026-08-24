# Naming conventions (pack v2)

## Level codes
`T{0|1|2}P{0|1|2|3|4}`. Sub-variants lowercase: `T0P1a`, `T0P1b_frozen`,
`T0P1c`, `T1P1_distance`, `T2P1_calibconstrained`.

## Cases
`mem_legacy` · `stadtbach` · `mem_upgraded` · `synth`

## Paths
```
configs/v2/{case}/{level_code}.yaml
configs/v2/{case}/sensitivity/{scenario}/{level_code}.yaml
configs/v2/synth/{config_id}/{level_code}.yaml
results/v1_frozen/...                       # never modified
results/v2/{case}/{level_code}/{scenario}/
results/v2/analysis/*.csv                   # everything the paper cites
figures/v2/{Fxx}_{slug}.pdf|.png|.source.txt
paper/tables/tab_{slug}.tex
revision/audit/P{n}_*.md
data/Stadtbach/derived/*.csv                # NDA-safe derived only
```

## Synthetic config id
`L{pipe_km}_H{HI}_N{nodes}_S{storage_h}_G{c|d}` — trailing `G` is the
generation-topology factor (central / distributed). Zero-padded.

## Tidy results CSV
`run_id, case, level_code, scenario, config_id, metric, value, unit`
Metrics: `cost_total`, `cost_fuel`, `cost_elec`, `cost_pump`, `cost_co2`,
`co2_t`, `heat_loss_mwh`, `pump_energy_mwh`, `objective`, `bound`, `gap_rel`,
`wall_time_s`, and from the evaluator `z_eval`, `regret_abs`,
`n_violation_steps`, `violation_energy_mwh`.

## Run manifest
`run_id, case, level_code, scenario, config_sha256, git_sha, solver,
solver_version, seed, threads, objective, bound, gap_rel, status, wall_time_s,
n_vars, n_bin, n_quad, time_limit_s, warm_start_from`

## Comparison keys
`{A}__{B}`, A = baseline, B = richer model. e.g. `T2P2__T2P3`.
