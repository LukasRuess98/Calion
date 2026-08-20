# P0 — Repository audit and baseline freeze

**Depends on:** nothing. Run first. **Output:** `revision/audit/P0_report.md`

1. **Inventory** (`revision/audit/inventory.csv`): path, kind, last modified, git
   SHA, referenced-by. Cover all YAML configs for **both networks**,
   `scripts/paper/run_paper_full.py`, `extract_artefacts.py`, `tools/tablegen.py`,
   `fill_paper.py`, `validation_runner.py`, `figgen.py`, `synth_gap_analysis.py`,
   the Pyomo model modules, `scripts/preprocess/merge_acron_sb.py`,
   `clean_stadtbach_west.py`, and all result directories.

2. **Freeze v1** to `results/v1_frozen/` with a `MANIFEST.md` recording git SHA,
   date and the current headline numbers (13.0 %, 10.4 %, 2.6 %, +0.11 %, +0.35 %,
   +0.50 %, 772/835/846 t CO2, solve times). Never modify it afterwards.

3. **Locate prior pressure work.** Search repo, notebooks, `analysis/`,
   `studies/`, `scratch/` for `pressure`, `druck`, `pump`, `darcy`, `dp_`,
   `delta_p`, `hydraul`. The author recalls a Memmingen pressure study. Report
   what exists, what it computed, whether it agrees with `<5 kW` / `2.4 MWh/yr`.
   **Do not re-derive what it already established.**

4. **Schedule-evaluation path.** Determine whether calion can fix all dispatch
   variables and evaluate cost without optimising (a `fix()`-and-solve path, or a
   post-processing cost accounting function). P11 needs to know whether the
   evaluator can reuse existing accounting code or must build it. Report the exact
   entry points.

5. **Config consistency, both networks.** `eta_pump`, roughness, CO2 factors,
   solver, horizon, seed, duplicate YAML keys, demand fractions summing to 1.000,
   presence of orphaned `Memmingen_L3_NoPhys.yaml`. Report a PASS/FAIL table and a
   **side-by-side Memmingen vs Stadtbach** column — the differences are
   diagnostic for P1.

6. **Bound recording:** does the pipeline capture the solver objective bound?
   If not, note where to add it (implemented in P2).

7. **Runtime and hardware baseline** on the 66-core / 180 GB machine: measured
   wall time per level per network, thread settings, memory. P4 needs this to
   budget the full-year MIQCP attempt.

Report with an explicit **Open questions for the author** section.

**Rules:** read-only with respect to model semantics; report discrepancies, do not
fix them here.
