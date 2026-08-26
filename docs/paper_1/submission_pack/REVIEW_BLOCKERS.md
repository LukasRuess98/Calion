# REVIEW_BLOCKERS — items needing author input or deferred

Nothing here blocks the compiled manuscript (it builds clean). These are follow-ups.

## Needs an author decision
- **None outstanding.** The one decision that moved numbers — the CO₂ net-vs-gross convention —
  was resolved (kept net, gross robustness documented). See CHANGELOG § O.

## RESOLVED (this pass)
1. ~~Overleaf mirror master-inline sync~~ **DONE** — all inline edits propagated to
   `overleaf/main.tex`; it builds clean (0 undef, 37 pp) and matches the pack, including the
   `tab_contrasts` main-text placement and the new recourse paragraph.
2. ~~Supplement rebuild~~ **DONE** — `supplementary_material.pdf` rebuilt (3 pp); S1–S5 render in
   order (objdecomp, hydraulics, gap-stability, robustness, prediction).
3. ~~Two unused stub files~~ **DONE** — `tab_cases.tex` and `tab_hydraulic_val.tex` deleted from
   pack and mirror (they were only referenced in comments).
6. ~~C (recourse mapping)~~ **DONE** — added a "Fixed schedule, recomputed state, and recourse"
   paragraph formalising $M_\ell$ and the fixed / recomputed / recourse / slack classification.

## Automated tests (prompt § Q) — DONE (16 tests, all pass; run with `--no-cov`)
`01_latex_build/tests/test_audit.py` (11) + `test_physics.py` (5):
- **Q1** dimensional conventions (H2 CO₂ kg / H3 mass-flow 1e6 / H4 pump-power 1e-6 / H9 delay s→h).
- **Q2** feature activation — the synthetic set solves only the decomposition configs
  (T0P0/T2P0/T2P1); **no T2P2 (L2)** is solved (skips if the git-ignored worktree output is absent).
- **Q3** factorial identity closes exactly.
- **Q4** 135 = 3×5×3×3.
- **Q5** dispatch invariants (storage cyclic, generation≈demand; the exact per-step balance is
  enforced/validated inside the pipeline, not re-derived from exported columns).
- **Q6** PWL pressure drop: exact at breakpoints, error ≤ k·m̄²/(4K²), monotone.
- **Q7** Darcy-Weisbach hand pipe + **pandapipes** cross-check (agrees to <2 % on the same λ).
- **Q8** objective ↔ economic reconciliation + gross-CO₂ robustness (97.0/3.5, −12.2).
- **Q9** table numbers vs canonical `objective_decomposition.csv` (95.8/4.7, bias −15.1).

Test-surfaced repo-hygiene note: **stale decomposition CSVs** — `data/decomposition.csv`
(topo 3.5 %) is a superseded lineage; the manuscript correctly uses
`objective_decomposition.csv` (topo 4.7 %), which the tests assert against. Consider moving the
stale files to `data/superseded/` so a table is never regenerated from the wrong source.

## Genuinely remaining (code-release integration hardening, not the manuscript)
- Full per-config **code-path activation** via live model build (Q2 covers the load-bearing
  "L2 not solved" claim from outputs; a build-time assertion for every level/flag would need the
  solver harness).
- Exact per-step forward-evaluation **energy conservation** as a standalone test (currently
  validated inside the pipeline via the KPI energy-balance).
5. **H8 (Darcy supply+return)** — the text states supply and return are both prescribed and the
   resistance is per-pipe; a numerical regression test against pandapipes for one pipe (prompt
   § Q7) would close it definitively. The existing pandapipes cross-check (0.007 bar agreement)
   already supports it.

## Verified NOT to be problems (checked, no change needed)
- H1 storage exponent; H10 delay-zero framing; abstract makes no DG/bound/overreach claim;
  no `Section ??` broken refs; forward-evaluated spelling is consistent (noun vs adjective).

6. **C (recourse mapping, prompt §C)** — partially addressed: the evaluator subsection states it
   takes a *fixed* dispatch schedule and adds a caveat on baseline-relative regret, but a formal
   per-variable fixed/recourse/prohibited/slack schema (M_l mapping) was not added as its own
   subsection. Consider adding for the resubmission.

## Reviewer-response pass (23-item list) — status
Items #1-21 fixed in source (build clean, 0 undefined). Verified #1 (storage Eq) was already
correct in source — the reviewer read an older PDF. Details in CHANGELOG_REVIEW.

### Needs author decision / verification (#23)
- **AI-model name:** `back_matter_v2.tex` says "Claude Opus 5" — there is no Opus 5 in the
  current lineup (latest is Opus 4.x in the Claude 5 family). Confirm the exact model actually
  used and correct it.
- **Gurobi version:** `computational_setup_v2.tex` says "Gurobi 13.0" — verify this version
  number is correct/available for the run.
- **References/admin:** verify all 2026 refs are genuinely published/online-first, DOI metadata,
  the project-period + funding line, and that the Zenodo DOI resolves with all claimed artifacts.

### #22 ligature/dash extraction — improved, residual is a tooling limit
- Added `\input glyphtounicode` + `\pdfgentounicode=1` + explicit `\pdfglyphtounicode` maps.
  Body extraction improved substantially (clean "fidelity" 30->53). **Residual** artifacts
  remain (~10 "delity"/"eect"/"L1L6" on copy-paste): stix2's ligature/dash glyphs lack usable
  ToUnicode and neither glyphtounicode nor microtype `\DisableLigatures` overrides them (microtype
  font-expansion also clashes with the Type 3 figure fonts). The **visual PDF is correct** — this
  is copy-paste/search/accessibility only. Options before submission: (a) verify on the
  publisher's TeX compile (Elsevier's setup may map stix2 ToUnicode); (b) switch body font to one
  with proper ligature ToUnicode (e.g. newtx) — but that reverts the crisp-table fix; (c) accept
  as a known extraction limitation. Recommend (a).

### Mirror master-inline sync (deferred)
Section/table edits synced to `overleaf/`. The many inline edits in `paper_COMPILE.tex` this pass
(recourse paragraph, pumping reconciliation, one-phenomenon scoping, screening rule, glyphtounicode
preamble, etc.) still need propagating to `overleaf/main.tex` before the next Overleaf upload.
`paper_CLEAN.pdf` (pack) is authoritative.

## UPDATE — #23 + mirror sync resolved
- **Gurobi 13.0**: confirmed correct by author.
- **Claude Opus 5**: confirmed correct by author (model post-dates the assistant's Jan-2026
  knowledge cutoff; no change). #23 model/solver items closed.
- **Mirror master-inline sync: DONE** — `overleaf/main.tex` regenerated from the pack master
  (paths flattened) so every inline edit (recourse, pumping reconciliation, one-phenomenon
  scoping, screening rule, glyphtounicode, etc.) is propagated. Mirror builds clean (39 pp,
  0 undefined), identical to the pack.

Remaining open items are now only: #22 residual ligature extraction (tooling; visual PDF correct),
and the general reference/DOI/Zenodo verification.

## Second reviewer pass — items still needing deeper work / author input
- **#5 CP-vs-ND0 EUR961 equivalence test (code run needed).** Reviewer asks for an automated test:
  disable loss + network/hydraulic limits, map the CP solution onto ND0, verify identical solver
  objective, and report any active constraint explaining the residual EUR961 (labelled the
  "topology effect"). Not run this pass. The 4.7% topology attribution is not fully secured until
  this is explained.
- **#7 Table 3 (tab_design_grid) is user-owned.** Code confirms L1/L3/L6 fix temperatures
  (milp_linearize) so L3 has NO temperature propagation, and L6 = L3 + delay (not L4/L5). If
  tab_design_grid shows L3 with temperature propagation or L6 with station resolution/dynamic
  pressure, those cells contradict the code and the corrected prose -> please review/adjust, or
  authorise me to edit that table.
- **#16 flow-uncertainty -> pumping sensitivity (re-run needed).** 33.8% source-flow MAPE should be
  propagated into pump-energy/peak-power ranges (pressure ~ flow^2, power ~ flow^3). Needs a
  sensitivity run with +/- flow bands; not done this pass. pandapipes verifies numerical
  consistency at the model's own flows, not the flows against reality.
- **#8 NL-72h documentation.** Class fixed to "nonlinear programme"; still owed: exact list of
  fixed integers vs re-optimised continuous vars, window start dates/boundary conditions, solver
  time limit, incumbent/bound/status/gap, and the exact full-year status (or remove the summer
  infeasibility from the main results pending an IIS).
- **#11 remaining spots.** Abstract reframed; Sections 1.2, 3.6, 3.11, Table 15 and the conclusion
  still need the same "forward evaluation of the fixed schedule, not changed decisions" wording,
  plus the note that pandapipes cross-checks trunk pressure only.
- **#13 cumulative path delay.** Units resolved (tau in s, k_p=floor(tau/3600)); still owed: report
  the maximum cumulative source-to-consumer path delay, since per-pipe flooring can erase a
  cumulative delay > 1 h.
- **#17 leftovers.** Define the zero-flow treatment of the native exponential; make the CP<=L1
  monotonicity statement conditional on the economic-cost basis (currently empirical, likely fine).
- **Editorial leftovers.** Check for remaining "central-generation arm"/"distributed-generation
  arm" phrasing and any malformed S2.4/S4.7 cross-references; the reproducibility statement should
  separate NDA-protected Memmingen inputs from the reproducible synthetic artifacts.
