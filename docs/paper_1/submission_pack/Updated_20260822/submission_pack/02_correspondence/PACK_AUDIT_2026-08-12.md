# Submission-pack audit — APEN-D-26-15734
**Date:** 2026-08-12 · **Deadline:** 2026-08-29 (17 days) · **Auditor pass:** code edits, results, reviewer match

---

## Verdict

**The science answers the review. The manuscript does not yet exist as a submittable document.**

Every substantive thing the reviewers demanded has been *computed* and is defensible:
the CP+L control (R2.2), the exact decomposition, decision regret (R1.2), the solved
nonlinear reference (R2.3), station-resolved hydraulics on real component data (R2.4),
the synthetic factorial (R2.5). The numbers in the drafted prose match the shipped CSVs
almost everywhere.

But `paper_COMPILE.tex` is a **revision skeleton**: the newly drafted sections are
written, and the sections carried over from v1 are *empty placeholder comments*.
It compiles to 11 pages with **one figure and six citations** — none in the body text.
Submitting this would be rejected on sight.

Two things additionally are **wrong, not merely missing**, and both are in the response
letter — the document the editor reads first.

---

## A. Blocking gaps (cannot submit without)

### A1. Empty sections — v1 carry-over never merged
`<<KEEP:...>>` markers with no prose under them:

| Section | Marker | Consequence |
|---|---|---|
| §1 Introduction, opening | `KEEP:intro-motivation` | paper opens mid-argument, no motivation |
| §1.1 Related work | `KEEP:rw-milp-topology`, `rw-thermohydraulic`, `rw-positioning` | **no related-work prose at all** — only the positioning table |
| §2.2 Base formulation | `KEEP:objective/balances/losses/hp/storage/emissions` | **the model is never stated** |
| §2.5 (extended) | `KEEP:pressure-drop/temp-prop/delay` | equations absent (comments say "author: insert DW eqns") |
| §2.6 Validation protocol | `KEEP:stage1`, `KEEP:stage2` | the two-stage protocol is never described |
| §2.7 Implementation | `KEEP:implementation` | solver/hardware only in the drafted bound paragraph |
| §4.1 Validation results | `KEEP:validation-results` | table with no prose |
| §4.10 Computational performance | `KEEP:computation` | table with no prose |
| §4.12 Limitations | `KEEP:limitations-other` | R1.5/R1.7 items listed as a comment, **not written** |
| Nomenclature + appendix | 10 × `KEEP:` | absent |

R1.5 and R1.7 are answered in the response letter with "accepted; limitations expanded" —
**but the expansion is a comment, not text.** A reviewer checking that pointer finds nothing.

### A2. Zero citations in the body
The only `\cite{}` calls in the whole manuscript are the six in `tab_prior_work.tex`.
An Applied Energy paper with no cited literature in Introduction, Methods or Discussion
is not reviewable. This also makes the Senior Editor's "avoid lumping references [1-3]"
comment impossible to verify as addressed.

### A3. Missing bibliography
`Paper20_Literatur.bib` is not in the pack (README_BUILD flags this). All citations
render `[?]`.

### A4. Only one figure is actually in the paper
`F_rule` is the sole `\includegraphics`. The other 5 analytical figures and all 15
validation figures exist as PDF/PNG but are referenced only by `%% Figure Fx` comments.
The validation figures are the visual evidence for R2.4 — the reviewer will look for them.

### A5. Mandatory Elsevier items absent
- **Highlights** (mandatory, 3–5 bullets ≤85 chars) — not in the pack.
- **Graphical abstract** — response letter says "a corrected graphical abstract
  resubmitted"; no such file exists here.
- Acknowledgments, CRediT, AI declaration are bracketed templates.

### A6. Response letter is a skeleton, not a letter
Header still reads *"Response to reviewers — skeleton (pack v2). Fill after P7."*
Section pointers are placeholders/off-by-one (see C3).

---

## B. Factual errors in the response letter (fix before anything else)

### B1. R2.2 methods note attributes the wrong numbers to the copperplate ❌
> *"the copperplate's estimation bias reads **−13.0 %** on the objective but **−16.6 %**
> on the economic cost"*

Those two numbers are from `economic_gaps.csv`, and they are the **L1-vs-L3 gap in the
old (pre-defensible-U) lineage** — not the copperplate. In the current hardened lineage
(`regret_decomp.csv`) the copperplate bias is **−15.12 % economic** (115,551 vs
136,142 €). The paper correctly says −15.1 %. The letter contradicts the paper by 1.5 pts
on the headline bias figure, sourced from a superseded run.

The 38–41 % scaffolding share *is* correct (`residual_pct` 38.0–41.0), but it too comes
from the old lineage and is not recomputed for CP.

**Also:** the letter cites this as **§2.6**. There is no economic-cost methods subsection
in the manuscript at all — §2.6 is *Validation protocol*. The whole
"we report economic cost, not the solver objective" argument is **missing from the paper**.
This is load-bearing: without it, a reviewer recomputing from the objective gets −13 %, not
−15.1 %, and concludes the numbers don't reconcile.

### B2. R2.5 claims all 81 configurations were solved ❌
> *"All 81 synthetic configurations are now solved"*

The pack contains **42 networks** (`synth_factorial_decomposition.csv`), and the paper
says 42 throughout. Worse: the redesigned grid in `tab_synthetic.tex` is
3 nodes × **5** lengths × 3 heterogeneity × 3 storage = **135** cells, not 81. So the
letter's "81" refers to the *old* design and its "all solved" is false either way.

This is the single most dangerous line in the pack, because R2.5 attacked **exactly this**:
*"Only 36 of the 81 synthetic configurations were retained… justify the filtering procedure."*
Answering a filtering complaint with an incorrect claim of completeness invites rejection.

### B3. "Balanced factorial" is not balanced
Paper, abstract, conclusions and `tab_synthetic` all say *balanced*. The 42 nets are an
irregular subset:

- node count: n05 = 16 nets, n15 = 13, n30 = 13
- trunk length: 30 km and 50 km appear **once per node count** (3 nets each);
  15 km appears 13 times, 5 km 13 times
- heterogeneity × storage combinations vary by cell

`tab_synth_anova` reports a *variance decomposition by factor* on this design. On an
unbalanced, non-orthogonal subset those variance shares (82/11/6/1 %) are confounded with
the design, which is the technical form of R2.5's "use a more balanced statistical analysis."
**Either** call it a *fractional / screening design* and state the sampling rule, **or**
fill the grid. Do not print "balanced" — R2 will check.

### B4. Drift range "17–94 %" / "17–95 %" is not in the data
`frozen_adder_drift.csv` columns: `mean_abs_drift_pts` 17.2–36.9, `max_abs_drift_pts`
32.3–63.97, `worst_underprov_pts` −0.43–63.97. **Nothing reaches 94/95.** The abstract
(*"drift 17–95 %"*) and the letter (*"drifts 17–94 %"*, *"under-provisions by 53–94 %"*)
either use an undocumented normalisation (% of true loss rather than points of cost) or are
stale. The paper body is correct and conservative (17.2 mean / 32.3 max pts) — the abstract
is the one overclaiming. **Fix the abstract, not the paper.**

### B5. Extension request is internally contradictory and factually stale
- Header: *"Requested new deadline: [author to set / on hold]"* vs body:
  *"we request an extension to 24 October 2026."*
- Body promises *"a second real network with measured pressure data"* — Stadtbach was
  **cut** under Shape A. Sending this promises a deliverable that isn't coming.
- Body: *"running the complete balanced factorial"* — same problem as B2/B3.

With 17 days left this letter is time-critical. Fix or drop it today.

---

## C. Verified correct (no action)

Numbers traced from CSV → table → prose. All of these hold:

| Claim | Source | Status |
|---|---|---|
| Decomposition 95.8 / 4.7 / −0.5 %, residual 0.0 € | `decomposition_live.csv` | ✅ exact |
| Total gap 20,591 €, 15.1 % of L1 | same | ✅ |
| CP bias −15.12 %, regret +46.10 % | `regret_decomp.csv` | ✅ |
| CP+L bias −0.63 %, regret −0.54 % | same | ✅ |
| ND⁰ bias −14.42 %, regret +46.81 % | same | ✅ |
| Regret pricing 46.1 / 61.2 / 831.7 % | `regret_decomp_pricing.csv` | ✅ |
| Violations = 0 at every level | same | ✅ |
| Synthetic loss 99.4–100.7 %, median 100.0 % | `synth_factorial_decomposition.csv` | ✅ |
| Topology within ±0.72 % on every net (min −0.715, max +0.574) | same | ✅ |
| Burden 3.4–67.4 % of cost | same | ✅ |
| Frozen adder: most-transferable 17.2 mean / 32.3 max pts | `frozen_adder_drift.csv` | ✅ |
| Linearisation −0.146 / −0.331 %, gaps 0.0085 / 0.0252 % | `linearisation_solved.csv` | ✅ |
| T_sup optimum 17.5 K, 6,220 €/yr, 4.6 % of cost | `tsup_sensitivity.csv` | ✅ (78,285 vs 84,505) |
| Loss −8,645 € / pump +2,425 €; saving is pure loss effect | same | ✅ |
| Pump 7.9 → 32.3 MWh; velocity binds at 20 K (3 viol. steps) | same | ✅ |
| λ range 0.03–1.7; Memmingen λ=0.12, 11 % pred vs 15 % meas | `fidelity_rule.csv` | ✅ |
| OOS prediction: train R²=0.999, held-out MAPE 14 % | `prediction_oos_summary.csv` | ✅ |

**Not verifiable in this pack:** the fidelity-rule fit `R²=0.86` / MAE 4.8 pts /
calibrated R²=0.93. The raw columns are present (43 rows) but the fit statistic isn't
stored anywhere; recompute and store it before submission — it's a headline claim.

---

## D. Reviewer-by-reviewer standing

Scoring: **Answered** = computed *and* written into the paper. **Computed only** = the
result exists but the manuscript doesn't yet contain it.

### Reviewer 1

| # | Point | Standing |
|---|---|---|
| R1.1 | "dominates" overclaims scope | **Answered.** Title changed; scope restrictions converted into synthetic factors; the ring/bidirectional boundary is stated concretely (signed-flow variables needed) — an unusually strong reply. |
| R1.2 | accuracy vs sensitivity | **Answered.** Regret is a decision quantity; the two reference roles are defined in §2.1. Terminology discipline is held throughout. |
| R1.3 | L3+/L3NL confounded | **Answered.** Delay isolated as L6; `tab_contrasts` shows one phenomenon per arrow. |
| R1.4 | pre-upgrade validation | **Answered.** Concedes first, then three reasons the comparative conclusions survive. Written into §3.1 *and* §4.12. Best-argued response in the pack. |
| R1.5 | assumptions constrain the physics | **Computed only.** The limitations text under `KEEP:limitations-other` is a comment. The T_sup study (§4.6) partly answers it and is excellent — but R1.5 also covers precomputed COP and sub-hourly dynamics, which are unaddressed in text. |
| R1.6 | L2 clustering arbitrariness | **NOT ANSWERED.** The letter says *"Three alternative clusterings plus a null distribution; spread […]"* — with the ellipsis literally unfilled. No clustering data exists in `data/`, no result in the paper. Worse, the redesign dropped ZN (zone) from the reported results entirely, so the comment is now sidestepped rather than answered. **Decide: run it, or state that zone aggregation is no longer a reported level and why.** |
| R1.7 | deterministic, hourly, no reserves | **Computed only** (i.e. not at all). "Limitations expanded" — the expansion doesn't exist. |

### Reviewer 2

| # | Point | Standing |
|---|---|---|
| R2.1 | novelty | **Answered, strongly.** Concedes the formulations are established, then rests on two pillars + the parameter-free `b = λ/(1+λ)` design rule. The rule is the best new material in the revision. Caveat: it leans on the unverified R²=0.86. |
| R2.2 | topology/loss confound | **Answered — decisively.** Exactly the requested model, exact identity closing to 0 €, hardened gaps, plus the drift result that stops CP+L from making the ladder redundant. This is the strongest part of the revision. **But** see B1 — the accompanying economic-cost methods note is missing from the paper. |
| R2.3 | linearisation not rigorous | **Answered.** All three requested remedies plus a *solved* nonlinear reference. Reporting the non-convergent full year and the infeasible summer week as results is the right call and will read well. |
| R2.4 | validation / pumping energy | **Answered.** Physical explanation (110.8 kW installed vs ~3 kW need), pandapipes <0.007 bar, DXF laterals, defensible U-values, honest mixing-valve limitation. The one soft spot: **corridor temperature MAE 8.3 °C** sits in `tab_validation` and is explained as metering-limited — defensible, but expect a push-back; make sure the loss-based validation (1.2 %) is what the caption leads with. Note L4/L5 are **forward-evaluated, not re-solved** — the paper flags this only in a comment (line 639). It must be in the text; if a reviewer discovers it unstated it looks like concealment. |
| R2.5 | generality / filtering | **WEAKEST.** Filtering answered with a false claim (B2); design called balanced when it isn't (B3); ANOVA on an unbalanced subset (B3); taxonomy unification is genuinely done ✅; OOS test done and honestly reported ✅ (17 pts error at 50 km reported as-is — good). |

### Senior Editor

| Item | Standing |
|---|---|
| No lumped references | **Unverifiable** — there are no references in the body. Letter claims a build-time check; no such check is in the pack. |
| Abstract one paragraph | ✅ Done. |
| No subheadings in Conclusions | ✅ Done. |
| Restructure per recent journal papers | ✅ Five sections. (This is what you want to revisit next.) |
| Source files, not PDF | ✅ `.tex` provided; **`.bib` missing**. |
| Highlights | ❌ Missing. |

---

## E. Code / reproducibility

- `scripts/` holds 5 files, but `fidelity_rule.py` imports `evaluator` and reads
  `../paper1_faithful_c19d690` + `results/v2/analysis` — **it will not run from this pack.**
  Fine as "for reference", not fine as the Zenodo release the Data Availability statement
  promises.
- **Stale CSVs shipped alongside current ones.** `bias_regret.csv` (L1 regret 23.4 %,
  superseded by the defensible-U lineage), `regret_sensitivity.csv`,
  `decomposition_defensibleU.csv` (95.45/3.95/**+0.60** — the pre-hardening split whose
  interaction later flipped sign), `_synth_legacy_backup.csv`, `economic_gaps.csv`.
  README_BUILD advertises `data/` as "every analysis CSV behind the figures".
  **A reviewer who opens `decomposition_defensibleU.csv` finds a different decomposition
  than the paper reports.** Delete or move to `data/superseded/` with a README line.
- `tab_cases.tex` / `tab_hydraulic_val.tex` are documented legacy stubs — harmless, but
  delete them for a clean release.
- Open item from MASTER_STATUS §8: **CP+Lb has a broken temperature export**
  (T_sup/T_ret NaN in 8016/8760 h) yet its bias/regret (−0.69 / −0.60 %) is printed in
  `tab_regret`. Confirm the cost numbers are unaffected by the NaN export, or drop the row.

---

## F. What to do, in order

**Today (unblocks everything else)**
1. Fix or drop `extension_request.md` (B5) — 17 days left; the deadline decision gates the plan.
2. Correct R2.2's −13.0/−16.6 % to the CP lineage (B1) and R2.5's "all 81" (B2) in the letter.

**Before restructuring**
3. Decide R1.6 (clustering): run the three clusterings, or write the honest "zone level is
   no longer a reported level because…" paragraph.
4. Decide the synthetic design wording: *fractional/screening* + stated sampling rule, or
   fill the grid (B3). This determines whether `tab_synth_anova` survives as-is.
5. Recompute and store the fidelity-rule fit statistics (R²=0.86 / MAE 4.8 / cal. R²=0.93).
6. Reconcile the drift range in the abstract with `frozen_adder_drift.csv` (B4).

**Then — the restructuring pass you have planned**
7. Merge the v1 carry-over sections (A1), including the missing economic-cost methods
   subsection and the L4/L5 forward-evaluation statement.
8. Restore citations + drop in the `.bib` (A2, A3).
9. Wire the figures (A4).
10. Write Highlights + graphical abstract; fill Acknowledgments / CRediT / AI declaration (A5).
11. Turn the response letter from skeleton into letter, and re-check every §/Table/Figure
    pointer against the final compile (currently off by one from §4.6 onward).

**Effort estimate:** the analysis is done. What remains is roughly 4–6 focused days of
writing and assembly, plus whatever R1.6 costs. That fits inside 17 days — but only if the
writing starts now and the restructuring is done *once*, not twice.
