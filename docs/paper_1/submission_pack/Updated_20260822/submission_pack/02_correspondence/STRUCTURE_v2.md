# Manuscript structure — matched to the example paper
**Model:** Akter et al., *Applied Energy* 359 (2024) 122662
**Decision:** adopt its architecture. Four sections, literature inside the Introduction,
**Results and discussion combined**, case study folded into the methodology.

---

## What the example actually does

| § | Example paper | Notable |
|---|---|---|
| — | Highlights, then boxed **Nomenclature** on p. 2 | Nomenclature is front matter, not an appendix |
| 1 | Introduction | |
| 1.1 | Extensive literature review and identification of the research gaps | Literature is *inside* the Introduction, no standalone section |
| — | Roadmap paragraph closing §1 | "This paper was structured as follows: Section 2 detailed… Section 3 addressed…" |
| 2 | **Experimental design and methodology** | |
| 2.1 | Experimental design | **The experiment comes first, before any equation** |
| 2.2 | Methodology — study area, data sources, data preparation; characterisation | Case study lives *here*, not in its own section |
| 2.3 | Mathematical approach | Equations arrive last, after the logic is established |
| 3 | **Results and discussion** | **Combined, not split** |
| 4 | Conclusions and future scope | |

**This reverses my earlier recommendation.** I suggested splitting Results and Discussion
because most recent Applied Energy papers do. The paper you have chosen does not — it
combines them and folds the case study into the methodology, reaching four sections
instead of six. Your instruction is the example paper, so that is what this plan follows.
It is also the lower-risk option: it moves material rather than requiring new connective
prose, and the drafted Results subsections already interleave interpretation with
evidence, which is what a combined section wants.

---

## Target structure

### 1. Introduction
Motivation and the two-axis framing (`introduction_opening_v2.tex`, drafted), then the
framing paragraph on the two limitations of the fidelity literature.

**1.1 Literature review and research gap** — `related_work_v2.tex` (drafted), retitled from
"Related work" so it matches the example's phrasing and reads as part of the Introduction
rather than a section that happens to sit inside one. Ends with `tab_prior_work`.

**1.2 Contributions and research questions** — existing drafted text, with the four RQs
stated so that each maps to exactly one subsection of §3.

**Closing roadmap paragraph** — new, three sentences, following the example's pattern.

### 2. Experimental design and methodology

**2.1 Experimental design** — the fidelity ladder, the decomposition controls, and
`tab_contrasts`. This leads, before any equation. It is the section that answers R2.1: the
contribution is the experimental structure, so the experimental structure is what the
reader meets first.

**2.2 Case studies and data** — Memmingen and the synthetic factorial, moved wholesale
from the current §3. Carries `tab_case_summary` and `tab_synthetic`.

**2.3 Base formulation** — `base_formulation_v2.tex` (drafted).

**2.4 Copperplate with aggregate losses** — existing drafted text.

**2.5 Forward evaluator and decision regret** — existing drafted text.

**2.6 Extended thermo-hydraulic formulation** — from
`extended_physics_validation_implementation_v2.tex` (drafted), including the
station-resolved subsection.

**2.7 Cost accounting: economic cost versus the solver objective** — new; you have
`SECTION_2_6_objective_vs_economic.md` staged for this. It is referenced by the response
letter and does not yet exist in the manuscript.

**2.8 Validation protocol** — drafted.

**2.9 Computational setup** — drafted. Per the brief's §2.8 checklist, report solver
(Gurobi 13.0), hardware (66 cores, 180 GB), tolerances (1e-4 linear, 1e-3 synthetic),
`NonConvex=2` where applicable, seeds, instance counts, and the reproducibility pointer.

### 3. Results and discussion

Combined. Order follows the research questions, with interpretation attached to each
result rather than deferred:

| §3.x | Content | RQ |
|---|---|---|
| 3.1 | Validation | — establishes what can and cannot be claimed |
| 3.2 | Estimation bias: loss visibility versus spatial resolution | RQ1 |
| 3.3 | Decision regret and physical deliverability | RQ2 |
| 3.4 | Zone-clustering sensitivity | R1.6 — promote from the response letter, with `F_r16_clustering` |
| 3.5 | Thermo-hydraulic effect, to the transmission station | RQ3 |
| 3.6 | Robustness to a flexible supply temperature | RQ3 |
| 3.7 | Linearisation error and transport delay, separated | RQ3 |
| 3.8 | Generalisability and out-of-sample prediction | RQ4 |
| 3.9 | Fidelity gap versus computational cost | — merges the current computation subsection with the trade-off framing |
| 3.10 | Sensitivity and robustness | — |
| 3.11 | Why the extended physics matters so little here | — the mechanism discussion; see below |
| 3.12 | Implications for modelling practice | — |
| 3.13 | Limitations | `limitations_v2.tex` (drafted) |

**§3.11 is the one genuinely new subsection**, and it is the most valuable thing the brief
identifies. The nulls we report — hydraulics, delay, linearisation — could mean the physics
does not matter, or could mean our assumptions removed the degrees of freedom through
which it would act. Both readings are live, and a reviewer will supply the second if we do
not. Fixed capacities, a prescribed heating curve, precomputed COP and hourly resolution
each close a specific channel, and we can say which. The T_sup study is the proof of
concept: open one channel and hydraulics move from negligible cost to binding constraint.
Written honestly, this converts the paper's weakest-looking results into its most careful
argument, and it answers R1.5 in the Discussion where the reviewer asked for it rather
than only in the Limitations.

### 4. Conclusions and future scope
No subheadings. Three to four paragraphs: what was developed and tested; what was found;
what it means for model selection; scope and extensions.

### Front matter
Move the nomenclature from the appendix to a boxed table early in §1, per the example.

---

## What moves where

| From | To |
|---|---|
| §3 Case studies (whole section) | §2.2 |
| §2.1 Fidelity ladder | §2.1, unchanged in content, now leads |
| §4.10 Computational performance | §3.9, merged with the fidelity/complexity trade-off |
| §4.12 Limitations | §3.13 |
| §5 Conclusions | §4 |
| Appendix nomenclature | §1 front matter |
| R1.6 result (response letter only) | new §3.4 |
| — | new §2.7, new §3.11 |

Section count 5 → 4. Every `\ref` and every §-pointer in the response letter changes; do
that mechanically at the end, once, against the compiled PDF.

---

## Note on the ChatGPT brief

The brief is a reasonable checklist and its terminology audit (§11) and causal-isolation
challenge (§18) are worth running. But it predates this revision and several of its
premises are now wrong — it assumes topology dominance is the finding, refers to 36
synthetic configurations, and treats the old five-level structure as the thing to defend.
Our results say loss visibility rather than topology sets the requirement, the factorial
is 135 cells, and the ladder was rebuilt. Where the brief and the data disagree, the data
win. Two specific corrections:

- The brief's suggested titles both foreground topology ("Topology Matters More Than
  Thermo-Hydraulic Fidelity"). That is the claim the decomposition overturned. The current
  title is right and should not be changed toward the brief.
- The brief recommends splitting Results and Discussion (§8, §9). The example paper you
  chose does not. Following the example.

Where the brief is right and we are not yet complete: §3.11 above, the fidelity-versus-cost
trade-off (§3.9), and the terminology audit.

---

## Item 3 — the decomposition controls in the base formulation

You asked me to make the suggestion rather than wait on verification. It stands as written
in `base_formulation_v2.tex`:

- the copperplate balance carries an exogenous aggregate loss term `L_t`, zero for `CP`
  and supplied for `CP+L`;
- the nodal balance carries a switch `κ ∈ {0,1}` on the pipe-loss term, zero for `ND⁰` and
  one for `L1` upward.

Setting the two independently generates the four corners of a 2×2 design, which is what
makes the decomposition additive with no residual by construction rather than by fit.

**This needs one check against the implementation before submission.** If the controls are
realised differently — for example by zeroing the `U` values rather than by a switch on the
loss term, or by modifying the demand series rather than adding `L_t` to the balance — the
equations must be rewritten to match, because the exactness of the decomposition is
asserted from them. A referee who reproduces the design from these two equations and gets a
residual will not be forgiving. Everything else in that file is a faithful transcription
with the level names remapped; this is the only inference.
