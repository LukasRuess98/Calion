# Coverage, trims, and the dash pass

---

## 1. Reviewer coverage — complete

Every point has a home in the final structure. Nothing is unanswered.

| # | Point | Where |
|---|---|---|
| R1.1 | "dominates" overclaims | Title, §1, §2.9, §3.14 |
| R1.2 | accuracy vs sensitivity | §2.1, §2.4 |
| R1.3 | L3⁺/L3ᴺᴸ confounded | §2.1, §2.6, §3.8 |
| R1.4 | pre-upgrade validation | §2.9, §3.14 |
| R1.5 | assumptions constrain physics | **§3.12** (own subsection), §3.14 |
| R1.6 | clustering arbitrariness | **§3.4** (own subsection, with data) |
| R1.7 | deterministic, hourly, no reserves | §3.14 |
| R2.1 | novelty | §1.2, §2.4, §3.3, §3.9 |
| R2.2 | topology/loss confound | §2.3, §3.2, **§2.5** |
| R2.3 | linearisation rigour | §2.6, §3.8 |
| R2.4 | validation, pumping energy | §2.6, §3.1, §3.6 |
| R2.5 | generality, filtering | §2.9, §3.9 |
| Editor | de-lump refs, one-paragraph abstract, no subheadings in conclusions, restructure | done |

Three answers are stronger than the reviewer asked for: R1.6 became a solved experiment
rather than a discussion, R2.5 eliminated the filtering rather than justifying it, and R1.5
got a dedicated mechanism subsection rather than a limitations line.

---

## 2. Trims — roughly 2–3 pages, no loss of substance

### 2.1 The mixing-valve explanation is stated five times

It appears in §2.7 (validation protocol), §2.9 (Memmingen), §3.1 (twice), the appendix, and
two table captions. Once is evidence; five times reads as defensive, and it is the single
biggest source of redundancy in the paper.

**Keep in full at §3.1**, where the failed gates are reported and the explanation is load
bearing. Everywhere else reduce to a cross-reference:

- §2.7: *"The temperature gates apply to the propagating formulation only; what the metering
  can and cannot support is set out in Section 3.1."*
- §2.9: delete the metering discussion entirely (see 2.2 below).
- Appendix: keep the per-node grouping, drop the restatement of why.
- `tab_val_targets` caption: one clause, not three.

### 2.2 §2.9 Memmingen duplicates §3.1

The case-study subsection currently explains the mixing valves, the flow sensitivity, the
annual-loss anchoring and the far-end corridor. All four are done properly in §3.1.

**Reduce §2.9 to** the network description, the portfolio, the statement that all generation
is co-located (which is load bearing for §3.5), and the pre-upgrade limitation pointer.
Saves most of a column.

### 2.3 §3.10 Sensitivity and robustness is a table of pointers

Every row restates a result established elsewhere with its own evidence: the multiplier
correction (§3.2), the two CP+L calibrations (§3.3), the disaggregation rule (§3.3), the gap
tightening (§2.8 and `tab_gap_stability`), the supply-temperature study (§3.7).

**Reduce to three sentences plus `tab_robustness`.** The table is the useful artefact; the
prose around it is a second telling.

### 2.4 `tab_design_grid` duplicates `tab_contrasts`

The eleven-column scope grid in the appendix and the seven-contrast table in §2.1 carry the
same information, and §2.1's is the one the argument uses. **Drop the appendix grid.**

### 2.5 Pump numbers stated three times

110.8 kW installed against ~3 kW needed, and the 0.03 % share, appear in §2.6 prose, §3.6
prose and `tab_hydraulics`. **Keep in §3.6 and the table**; in §2.6 say only that the
magnitude is reconciled physically in the results.

### 2.6 The λ worked example appears twice

§3.13 opens with "Zeroth, and most concretely…" and §4's third paragraph makes the same
point with the same numbers. **Keep the §3.13 version** (it belongs with the practical
guidance) and let the conclusion state the rule without re-deriving the example.

### 2.7 Optional, if more is needed

The fourteen-row per-node table in the appendix. The group means in §3.1 carry the argument;
the table is supporting evidence a reviewer can request.

**Do not trim** §3.1, §2.5 or §3.12. Each exists because something was missing, and each
answers a reviewer directly.

---

## 3. Housekeeping

`sections/extended_physics_validation_implementation_v2.tex` is the superseded bundled file,
replaced by the three splits. It is not `\input` anywhere. **Delete it** so nobody edits the
wrong copy.

---

## 4. The dash pass

133 spaced dashes across the section files. They read as a stylistic tic and should go.

**Safe rule — replace only the spaced form.**

- Replace `` -- `` (space, two hyphens, space) → recast the sentence.
- **Leave `X--Y` untouched** (no surrounding spaces). Those are ranges: `3.2--81.2`,
  `48--64`, `L1--L6`, `[2.5, 5.5]`. A blind replace breaks every one of them.

**How to recast**, in order of preference:

| Original pattern | Prefer |
|---|---|
| A ` -- ` aside ` -- ` B | commas: *A, aside, B* |
| A ` -- ` and B is a full clause | semicolon or full stop |
| A ` -- ` restating A more precisely | colon |
| A ` -- ` short emphatic tail | comma, or drop the tail into the next sentence |

Two cautions. Do not simply swap every dash for a comma; several sentences already carry two
or three commas and will become unreadable. And where the dash separates a list from its
summary (*"node count, pipe length, demand heterogeneity -- over the full range"*), a comma
creates a false list item; use a full stop or restructure.

Highest-density files, worth doing by hand: `nomenclature_v2` (22, mostly in table cells
where a comma is fine), `limitations_v2` (11), `base_formulation_v2` (10),
`related_work_v2` (10), `physics_null_mechanisms_v2` (9).

Also check the skeleton's own prose, which was not written by this pass but shares the habit.

---

## 5. What is left for the coding agent

| Task | Effort |
|---|---|
| Delete the orphaned `\subsection{Computational performance}` line | trivial |
| Apply the pointer map from `FINAL_POINTERS.md` to the response letter | small |
| Fill the `[Table/Figure]` tags from the compiled PDF | small |
| The dash pass, per §4 above | moderate, needs judgement |
| Trims §2.1–§2.6 above | moderate |
| Delete the superseded bundled section file | trivial |
| Fix the stray `%}` bib entry | trivial |
| Regenerate, rebuild both PDFs, re-verify the four zeros | small |

**Not the agent's:** the competing-interest text, the graphical abstract re-export, and the
three stylistic patches still deferred in `FOLLOWUP_PATCHES.md` (abstract reorder, moderator
trim, fidelity-residual sentence) — those are voice calls that belong with the author, though
the agent can apply them verbatim if you approve the wording as written.
