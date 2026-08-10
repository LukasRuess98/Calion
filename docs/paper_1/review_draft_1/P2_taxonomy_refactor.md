# P2 — Taxonomy refactor and run infrastructure

> **ALIGNED 2026-08-10:** target taxonomy is the redesigned ladder in
> `08_LEVEL_REDESIGN.md` (CP·T0P0 / CP+L·T0P1 / ZN·T1P1 / ND⁰·T2P0 / L1·T2P1 / L2·T2P2
> +temp-prop / L3·T2P3 +trunk pressure / **L4·T2P4 +station+laterals** / **L5·T2P5
> +dynamic station Δp** / L6·T2P6 +delay / NL ref). Add `level_code` + orthogonal
> physics flags incl. `station_resolution`, `lateral_losses`, `station_dp_mode`
> (flat|dynamic), `n_transfer_stations`. Runs on the c19d690 worktree. Keep bound
> recording. Config validator must also assert the defensible-U calibration (no ×4.7)
> on L1–L3 and that laterals appear only at L4+.

**Depends on:** P0 · **Blocks:** P4, P5
**Output:** `revision/taxonomy_map.csv`, config `level_code` fields, bound recording

Read `02_STUDY_REDESIGN.md` §2 first.

## Target

Topology `T0|T1|T2` × Physics `P0|P1|P2|P3|P4`. Every run is one cell `T{i}P{j}`,
meaning the same thing in Memmingen, Stadtbach and the synthetic study. This
deletes v1 Table 6, whose existence was the defect R2.5 objected to.

## Tasks

1. **Add `level_code` to every config**, keep the legacy `level` as an alias so v1
   remains reproducible. Write `revision/taxonomy_map.csv`:
   `legacy_label, level_code, topology, physics, formulation, delay_active, case`.

2. **Orthogonal explicit physics flags** at the top of each config:
   `heat_loss`, `pressure_drop`, `pumping_power`, `temperature_propagation`,
   `transport_delay`, `formulation` (`milp`|`miqcp`), `pwl_segments`.
   Fail loudly on any combination outside the defined grid (e.g. `T0` with
   `pressure_drop: true`).

3. **Config validator** before every solve: no duplicate YAML keys (this bug
   silently removed CHP and HP from a config once already); demand fractions sum
   to 1.000 ± 1e-9; ΣU·L of a `T1` config matches its `T2` reference; emission
   factors, solver, horizon and seed identical within a comparison set. Emit a
   diff table on failure.

4. **Record objective bounds.** Every solve writes `run_manifest.json`:
   `run_id, case, level_code, scenario, config_sha256, git_sha, solver,
   solver_version, seed, threads, objective, bound, gap_rel, status, wall_time_s,
   n_vars, n_bin, n_quad, time_limit_s, warm_start_from`.
   Without `bound` the revision cannot answer R2.3.

5. **`tools/compare_levels.py`** implementing point estimate, rigorous bound and
   both gaps. Every comparison in the paper goes through it — no ad-hoc arithmetic.

6. **Results schema** `results/v2/{case}/{level_code}/{scenario}/` with a tidy CSV
   (`run_id, case, level_code, scenario, config_id, metric, value, unit`).

7. **Stadtbach `T1` definition:** aggregation to the shaft/zone resolution from
   P12, not an arbitrary clustering. Document the mapping in the config.

## Acceptance

- Re-running any v1 config through the new wrapper reproduces the frozen v1
  objective within solver tolerance. If not, stop and report.
- Structural check passes: `T2P4` with quadratics deactivated reproduces `T2P1`
  within 0.01 %.
