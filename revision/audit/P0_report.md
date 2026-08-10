# P0 — Repository audit (in progress)

Date: 2026-08-09 · Branch: main · Repo: calion

This report is grounded in direct inspection of the current working tree. Items
marked **[pending]** still need the full inventory sweep; items marked **[done]**
were verified this pass.

---

## 0. MOST CRITICAL — the current tree cannot reproduce Paper 1

`output/paper1_corrected/README.md` establishes that the v1 results come from an
**isolated git worktree at commit `c19d690`** (+ pump-attribution and
demand-fraction patches). The current `main` has diverged ~39 commits with
**Paper-2 physics** (temperature-propagation PWL → lightweight offset, 420k→79k
binaries); on it the same Paper-1 input gives **−22 % cost with L3+ cheaper than
L3** — a different model.

**Implication the revision pack does not account for:** every v2 re-run (P3 new
cells, P4/P5 campaigns) must be built on the **pinned `c19d690` baseline in a
worktree**, not on `main`. The pack's P2 acceptance test ("re-running any v1 config
through the new wrapper reproduces the frozen v1 objective") will FAIL on `main` by
design. This must be the first line of P2/P3. v1 is frozen at
`results/v1_frozen/` (manifest + small artifacts; 1.5 GB raw runs left in place).

## 0b. The pump fix is already done — and R2.4 is still NOT resolved

The pump-attribution bug (13 of 14 pipes' pumping work dropped from the objective on
the radial network) is already found and fixed (BFS ownership,
`pump_attribution_fix.patch`). Corrected: L3→L3+ = **+0.33 %/+735 EUR** (paper said
+0.11 %/+255), pump electricity **10.6 MWh** (paper 2.4). **But 10.6 MWh on a ~40 GWh
thermal network is still ~0.03 %, two orders below Frederiksen & Werner's 1–5 %.**
So the attribution fix does not close R2.4 — the residual is the base
differential-pressure / Δp_crit term not driving pump work (the 0.6 bar station Δp
"cancels" in level comparisons but should still consume electricity). **P1 remains a
genuine physics rework**, now with a quantified target.

## 0c. R1.3 / R2.3 (isolated linearisation) already has a strong existing answer

`L3NL_LINEARIZATION_ANALYSIS.md` + `pump_linearization_error.json`: the full L3NL
re-solve is **intractable** (58,774 bilinear constraints, 24 h/window, no incumbent).
The linearisation error was instead isolated by **exact decomposition**: pump-friction
PWL-vs-cubic error = **0.031 %/0.027 %** of total (Jan/Feb), station Δp is linear and
cancels, temperature linearisation unchanged → corrected L3+→L3NL gap 0.32 %/0.47 %.

This already delivers what R1.3/R2.3 asked for (linearisation isolated from delay, at
0.031 %). **Recommendation:** make the exact decomposition the primary R1.3/R2.3
answer; treat the pack's `T2P3` intermediate MIQCP as a confirmatory nice-to-have and
**expect it to be intractable at full year** — do not budget the "attempt full-year
T2P4" as if it will converge.

---

## 1. Critical finding — the P1 config-diff premise is STALE

The revision pack (`00_CONTEXT.md`, `P1_hydraulics_validate_transfer.md`) treats
the pump-energy anomaly as a **config gap** and instructs the agent's first action
to be a config diff, expecting:

| | plan claims Memmingen v1 | plan claims Stadtbach |
|---|---|---|
| `pipe_roughness_mm` | 0.05 | 0.5 |
| `pump_efficiency` | 0.70 | 0.75 |
| `delta_p_min_consumer_bar` | absent | 0.7 |

**This is no longer true of the current repo.** The current
`configs/memmingen/Memmingen_L3_MILP.yaml` and `Memmingen_L3_NLP.yaml` already carry:

- `pipe_roughness_mm: 0.5` (matches the paper's stated value)
- `pump_efficiency: 0.75` (matches the paper)
- `delta_p_min_consumer_bar: 0.7` (present, not absent)
- `max_velocity_m_s: 2.5`, `max_pressure_drop_bar: 2.0`

These were harmonised in the earlier config-parity work (see memory
`project_paper2_hp_capex_asymmetry`, and the backup dir
`output/paper1_backup_pre_deltap_pumpfix_20260726`). **The "Memmingen is the
outlier" hypothesis is falsified.**

Consequence for P1: the low pump-energy figure (2.4 MWh/yr, +255 EUR/yr, `<5` kW
peak — confirmed present in `MainEingereicht06072026.tex:1619-1620`) is **not**
explained by wrong roughness/efficiency. The real structural facts are:

- `Memmingen_L3_MILP.yaml:66` → `pressure_drop: false`. Pumping is **off** in the
  MILP dispatch config; the manuscript confirms `C^pump = 0` for L1/L2/L3
  (`tex:744`). Pumping only enters at L3+/L3NL (`Memmingen_L3_NLP.yaml:28`
  → `pressure_drop: true`).
- So the 2.4 MWh number comes from the L3+/NLP run **already using roughness 0.5,
  η 0.75, Δp_min 0.7** — i.e. with the "correct" parameters. That makes the
  implausibly-low pumping energy a genuine **model-physics** issue, not a config
  flip.

**Recommendation:** P1 Step 1 should be demoted to a two-line confirmation ("params
already correct"), and the effort moved to P1 Step 2 (the unit-chain trace
`Q → ṁ → Δp → P_pump`). Prime suspects, in order: (a) `Δp_crit` at the critical
consumer not entering the pump sum — the paper's Eq. `eq:pump_power` sums only pipe
hydraulic work, so the base differential-pressure requirement (the dominant term in
real DH pumping) may be excluded by construction; (b) velocities/flows are tiny
because the network is oversized; (c) supply-only vs supply+return. This is likely
a **rework**, not a correction — the pack's optimistic "largely a config
correction plus re-runs" framing should be dropped.

---

## 2. Prior pump/pressure work to reuse (do not re-derive) — [done]

Substantial prior work exists and must be read before P1 touches anything:

- `output/paper1_backup_pre_deltap_pumpfix_20260726/` — pre-fix snapshot.
- `output/paper1_corrected/` — contains `L1 L2 L3 L3plus`, plus
  `_pump_linearization_error.py`, `L3NL_LINEARIZATION_ANALYSIS.md`,
  `MANUSCRIPT_UPDATE_PROMPT.md`, `_impact_analysis.json`, `_week_linearization/`.
- `output/pressure_runs/`.
- `configs/pressure/` — `Memmingen_pressure.yaml`,
  `Memmingen_pressure_stations.yaml`, `Memmingen_pump_pressure_study.ipynb`,
  `Memmingen_pandapipes_crosscheck.ipynb`, `Memmingen_componenets_spec`.
- Memory: `project_memmingen_pump_pressure_study`,
  `project_memmingen_pandapipes_crosscheck`,
  `project_paper1_l3nl_intractable_decomposition` (the L3NL re-solve is INTRACTABLE;
  linearisation error was resolved by exact decomposition, +0.031%/+0.027% friction,
  station Δp cancels → submitted +0.35%/+0.50% stands). **This directly bears on
  P3/P4's `T2P3`/`T2P4` plan — the native-quadratic full-year run is already known
  intractable; the pack should lean on the existing exact-decomposition result
  rather than re-attempting the solve.**

## 3. Bound recording — [done] gap confirmed

`scripts/paper/extract_artefacts.py` captures `mip_gap` (line 119-130) but **not**
the absolute objective bound (`ObjBound`). P2's requirement (record `objective` AND
`bound`) is a real, small addition — bound is derivable from `obj` and `gap`, but
should be stored explicitly from the Gurobi solver result for the R2.3 answer.

## 4. Schedule fix-and-evaluate path — [done] must be built

No existing `fix()`-and-evaluate or standalone cost-accounting entry point found in
`run_paper_full.py`. There is a Pyomo expression-evaluation helper
(`network_manager.py:2498`) reusable for accounting, but the P11 forward evaluator
must be built new. Confirmed: P11 is greenfield.

## 5. Orphaned config — [done]

`Memmingen_L3_NoPhys.yaml` is **not** at the config root; it sits in
`configs/memmingen/Archiev/`. P10's "orphaned config" cleanup is already partly
done (it's archived, not live). Verify nothing references the Archiev copy.

## 6. Infrastructure present — [done]

`scripts/paper/run_paper_full.py`, `extract_artefacts.py`, `paper_runner.py`,
`run_synth_parallel.py`, `sensitivity_runner.py`, `run_linearization_windows.py`;
`zenodo_paper_1/tools/{figgen,fill_paper,tablegen,validation_runner}.py`. The v2
pack can extend these rather than start fresh.

## 7. Manuscript pump contradiction — [done] confirmed real

`MainEingereicht06072026.tex`:
- line 438: "Reported pumping costs range from 1--5\% of thermal [energy cost]".
- line 1619-1620: L3+ "increases annual cost by +0.11\%, attributable entirely to
  pumping power (+255 EUR/yr on 2.4 MWh additional pump...)".
- line 744: "$C^{pump} = 0$ for L1/L2/L3".

The internal contradiction R2.4 points at is present as described. Valid critique.

---

## Still pending (full P0 scope)

- [ ] `revision/audit/inventory.csv` — full path/kind/SHA/referenced-by sweep.
- [ ] Freeze v1 → `results/v1_frozen/` with MANIFEST (headline numbers + SHAs).
- [ ] Config-consistency PASS/FAIL table, full Memmingen-vs-Stadtbach side-by-side
      (duplicate YAML keys, demand fractions → 1.000, CO2 factors, seed, horizon).
- [ ] Runtime/hardware baseline (66-core / 180 GB) per level per network.

## Open questions for the author

1. **Manuscript record**: letter is APEN-D-26-15734, PDF header APEN-S-26-20346.
   Which record does the revision upload against? (Confirm with the editor.)
2. **Extension**: deadline 2026-08-29 is not feasible for the full pack (see
   critical assessment). Request extension to mid/late October — and by what date?
3. **Title pre-commit** and **Stadtbach-in-figures under NDA** — see pack §11.
