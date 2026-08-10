# Paper-1 v2 workflow — run the new things, keep Paper 2 steady

Written 2026-08-09. How the revision's new pieces plug into the EXISTING Paper-1
infrastructure without touching Paper 2 or the faithful model.

## Isolation guarantee (Paper 2 stays functional)

| | Paper 1 (this revision) | Paper 2 |
|---|---|---|
| tree | worktree `../paper1_faithful_c19d690` @ `c19d690` (+ pump/demand patches) | `main` (HEAD 2a971f2) |
| dispatch code | c19d690 model (faithful to submission) | main model (Paper-2 physics: offset temp-prop, 79k bin) |
| configs | worktree `configs/memmingen/` | `main` `configs/paper_2/`, `configs/stadtbach/` |
| run scripts | worktree `scripts/paper/` | `main` `scripts/paper_2/` |
| output | worktree `output/paper_runs/` → copied to `output/paper1_corrected/` | `output/paper2_runs/` |

**Rules:** (1) All Paper-1 *dispatch* runs happen in the worktree. **Never merge
main's Paper-2 physics into the worktree** — it changes the problem by ~22 %
(README of `output/paper1_corrected`). (2) Revision *analysis* tooling
(`tools/evaluator.py`, `tools/economic_cost.py`) lives in **main** and only *reads*
worktree/frozen output — it never runs the model, so it cannot affect Paper 2.
(3) Do not edit anything under `configs/paper_2/`, `scripts/paper_2/`, or the
Paper-2 model paths.

## Level taxonomy: pack ↔ existing worktree run_ids

| pack code | meaning | worktree run_id | config | status |
|---|---|---|---|---|
| T0P0 | copperplate, no loss | `L1cp` (`heat_loss:false`) / `L1` | `Memmingen_L1.yaml` | exists |
| **T0P1a/b/c** | copperplate + aggregate loss | **NEW** | NEW (demand-inflated) | **build** |
| T1P1 | zones + loss | `L2` | `Memmingen_L2.yaml` | exists |
| T2P1 | full topo + loss (baseline) | `L3` | `Memmingen_L3_MILP.yaml` | exists |
| T2P2 | + pressure/pumping | `L3plus` | `Memmingen_L3_MILP.yaml` (+press) | exists |
| T2P3 / T2P4 | linearisation / +delay | — | `Memmingen_L3_NLP.yaml` | **exact-decomp** (L3NL intractable) |

## The new things, and how each plugs in (least-invasive first)

### 1. Economic-cost reporting — DONE, zero model change
`tools/economic_cost.py` reads any set of run dirs and reports gaps on BOTH the
objective and economic cost (energy−sell+fuel+co2+dump+demand), plus the residual.
Run after any campaign:
```
python tools/economic_cost.py --runs L1=output/paper1_corrected/L1 \
  L2=.../L2 L3=.../L3 L3plus=.../L3plus --ref L3 \
  --out results/v2/analysis/economic_gaps.csv
```
Verified on frozen v1: economic gaps 16.6 / 3.6 / 1.08 % vs objective 13.0 / 2.5 /
0.33 %. **This is the corrected reporting basis for the revision.**

### 2. Regret / forward evaluator — built, needs accounting fix
`tools/evaluator.py` (P11). Run per schedule; regret is `z_eval(l) − z_eval(T2P1)`
on economic cost. TODO before use: retarget self-consistency to economic cost and
reconcile fuel/CO₂ term-by-term with `result_collector` (see `P11_status.md`).

### 3. `T0P1a/b/c` copperplate + aggregate losses — build via demand pre-inflation
**No model change** (keeps the faithful model and Paper 2 untouched). A preprocessing
script inflates the copperplate demand series by the aggregate loss L(t); the T0P1
configs are copies of the `L1cp` copperplate pointing at the inflated column:
- `T0P1a`: `L_const = E_loss_annual(L3)/8760` (constant adder)
- `T0P1b`: `L(t) = Σ_p U_p L_p (T_sup(t)+T_ret(t)−2 T_gr)/1e6` (heating-curve-consistent)
- `T0P1c`: measured annual generated − delivered / 8760
Then add `T0P1a/b/c` run_ids to `PRIMARY_RUNS` in `scripts/paper/run_paper_full.py`
(worktree). Test: variable count == `L1cp` (must stay LP; must not become a network).

### 4. Reporting fixes to carry (from the audit)
- Report on economic cost (tool #1); disclose the ~38 % return-anchor residual.
- Fix `generation_MWh` tally so `energy_balance` closes (add electric-boiler/P2H
  grid-heat); the 18–30 % gap is a reporting artifact, not free losses.
- Fix the L1 phantom-loss report (copperplate must show 0 network loss).

## Run order (worktree, unattended)
```
# in ../paper1_faithful_c19d690
python scripts/paper/run_paper_full.py --phases 1 --skip-nl      # L1/L2/L3/L3+
# (after T0P1 configs added) they run in phase 1 too
python scripts/paper/run_synth_parallel.py --levels L3 L3plus --workers 4
python scripts/paper/synth_gap_analysis.py
# then from main (analysis, reads worktree output):
python tools/economic_cost.py --runs ... --ref L3
python tools/evaluator.py <run_dir> --config <cfg>   # regret, once accounting fixed
```

## Do-not-touch checklist
- [ ] `configs/paper_2/*`, `scripts/paper_2/*`, Paper-2 model paths — untouched
- [ ] worktree model formulation stays faithful (T0P1 via demand inflation, not code)
- [ ] `results/v1_frozen/` and `output/paper1_corrected/` never modified
- [ ] main's uncommitted `thermal_node.py` (pressure-slack tweak) left as-is
