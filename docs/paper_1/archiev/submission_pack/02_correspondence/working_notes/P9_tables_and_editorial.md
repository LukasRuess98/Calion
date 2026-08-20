# P9 — Tables, placeholder filling, editorial passes

**Depends on:** P7, P8
**Output:** `paper/tables/*.tex`, filled manuscript, `revision/audit/P9_report.md`

## Part A — Tables (all generated, never hand-edited)

| Tag | Content | Source |
|---|---|---|
| `tab:design_grid` | T×P grid with physics flags | `taxonomy_map.csv` |
| `tab:prior_work` | Positioning — **add columns "isolates loss from topology" and "evaluates decisions"**; all prior entries including our v1 are "No" | manual |
| `tab:cases` | **NEW** — three cases, roles, validation resolution | manual |
| `tab:validation` | Stage 1 KPIs, in-sample and out-of-sample | validation runner |
| `tab:hydraulic_val` | **NEW** — Stadtbach Δp validation | P1 |
| `tab:decomposition` | **NEW** — bias decomposition, cost and CO2 | `decomposition.csv` |
| `tab:regret` | **NEW** — bias vs regret vs violations | `bias_regret.csv` |
| `tab:linearisation` | **NEW** — point estimate, rigorous bound, gaps | `linearisation_bounds.csv` |
| `tab:synth_anova` | **NEW** — variance decomposition | `synthetic_anova.csv` |
| `tab:prediction` | **NEW** — out-of-sample Stadtbach | `prediction_oos.csv` |
| `tab:robustness` | clustering + calibration | `robustness.csv` |
| `tab:criteria` | **rewrite as observations, not guidelines** | derived |
| `tab:computation` | problem size and solve time | `computational.csv` |
| `tab:gap_stability` | 11 scenarios | `decomposition.csv` |

**Deleted:** v1 Table 6 (physics-scope mapping). Its deletion is part of the R2.5
answer — the taxonomy defect it patched no longer exists.

**`tab:criteria` rewrite:** R2.5 asked that thresholds be presented as
case-specific observations unless justified. Change caption and headers from
prescriptive ("Recommended model selection criteria" / "Conditions") to
observational ("Fidelity requirements observed in the tested regimes" / "Regime in
which the simplification held"). Footnote the tested scope. Where the
out-of-sample Stadtbach prediction succeeds, that specific rule may be stated more
strongly — and say why.

## Part B — Placeholder filling

`tools/fill_paper.py` resolves every `\result{key}` from the P7 CSVs and **fails
the build** on: any unresolved `\result{}`, any `\todo{}`, any remaining
`%% <<GAP:...>>`. The GAP markers are prose a human must write; the build must
never silently ship with them.

## Part C — Editorial passes

1. **De-lump citations** (editor). Reduce every multi-key `\cite{}` to the single
   most relevant reference or split into separate sentences. Known: `[1–3]`,
   `[6,7]`, `[8,9]`, `[12,13]`, `[15,22,23]`, `[5,24,25]`, `[10,27–29]`,
   `[24,45]`, `[28,30]`, `[5,25]`. Add a build check that fails on any survivor.
2. **Abstract → one paragraph.**
3. **Conclusions → no subheadings.** Remove the four `\paragraph{}` headings;
   convert to continuous prose.
4. **Terminology sweep.** Apply `02_STUDY_REDESIGN.md` §9. "Accuracy" is now
   permitted where it refers to decisions (regret) and forbidden as a property of
   a model level. Delete "statistically meaningful bound".
5. **Structure migration** 7 → 5 sections; update all `\Cref{}`; assert zero
   broken references.
6. **Consistency assertions:** no percentage appears with two values anywhere
   including the graphical abstract; Memmingen assets stated at j1 everywhere;
   every figure referenced and every referenced figure exists; Stadtbach total
   pipe length consistent with the P12 reconciliation.

## Report

`revision/audit/P9_report.md`: table inventory, unresolved-placeholder count
(must be 0), citation check, terminology diff, broken-reference check.
