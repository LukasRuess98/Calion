# LaTeX build pack — APEN-D-26-15734 (revised)

Everything needed to compile the revised manuscript, plus the data behind every
figure so additional figures can be regenerated. Generated 2026-08-12.

## What to compile

**`paper_COMPILE.tex`** — the compile-ready manuscript. All `\result{...}` value
macros have already been substituted with numbers, so it is plain LaTeX.
Document class: `cas-dc` (Elsevier CAS).

> **Verified 2026-08-12:** this file compiles cleanly with MiKTeX `pdflatex`
> (`cas-dc` class) — **11 pages, 0 errors, 0 undefined references** after two passes.
> The included `paper_COMPILE.pdf` is that build. The only warnings are 6 undefined
> **citations**, which disappear once `Paper20_Literatur.bib` is added (below).
> A prior `\mathrm`-outside-math error in the level-name macros was fixed
> (they now use `\ensuremath`).

```
pdflatex paper_COMPILE.tex
bibtex   paper_COMPILE
pdflatex paper_COMPILE.tex
pdflatex paper_COMPILE.tex
```

`paper_source_skeleton.tex` is the *source* version that still contains
`\result{key}` macros; do not compile it directly — it is only used to
regenerate `paper_COMPILE.tex` (see "Regenerating", below).

## The ONE thing missing (required)

- **`paper1_dh_fidelity/Paper20_Literatur.bib`** — the bibliography database is not
  in the repository checkout (it lives in your local submission environment). Drop
  your `.bib` into the `paper1_dh_fidelity/` folder here; the manuscript's last line
  (`\bibliography{paper1_dh_fidelity/Paper20_Literatur}`) then resolves. Until then,
  the body compiles but citations render as `[?]`.

## Provided dependencies

- `tables/` — all 18 tables that the manuscript `\input`s (auto-generated, current).
  (`tab_cases.tex` and `tab_hydraulic_val.tex` are legacy stubs, **no longer**
  `\input` by the manuscript — safe to ignore.)
- `figures/` — the five analytical figures (PDF + PNG, 600 dpi).
- `figures/validation/` — the Memmingen validation figures (stage-1/stage-2, corridor,
  spatial), for the validation section.
- `elsevier_class/` — `cas-dc.cls`, `cas-common.sty`, `cas-model2-names.bst`. These
  usually resolve from your MiKTeX/TeX Live install; copy them next to the `.tex`
  only if your distribution lacks them. `\bibliographystyle{elsarticle-num-names}`
  uses the `elsarticle` package's `.bst`, which ships with MiKTeX/TeX Live.
- `data/` — every analysis CSV behind the figures ("time series for additional figures").
- `scripts/` — the generators (see below).

## Figure wiring status (author action)

Only **`figures/F_rule`** is currently `\includegraphics`'d (the fidelity-rule
nomogram, new in this revision). The other figures are referenced by `%% Figure ...`
**comments** at their intended locations — insert them as you finalise. Map:

| File | Paper role |
|---|---|
| `figures/F_rule` | Fidelity design rule nomogram (§ generalisability) — **already wired** |
| `figures/F_decomp` | Loss/topology/interaction decomposition (Memmingen + synthetic) |
| `figures/F_regret` | Estimation bias vs decision regret (headline) |
| `figures/F_drift` | Frozen-adder drift vs pipe length |
| `figures/F_tsup` | Supply-temperature flexibility sensitivity |
| `figures/validation/stage1_*`, `corridor_*`, `spatial_*` | Validation section (F3–F5) |
| `figures/validation/stage2_*` | Dispatch/KPI validation |

## Regenerating (optional)

From the **repository root** (not this folder — the scripts read repo paths and the
faithful `../paper1_faithful_c19d690` worktree):

```
python tools/figgen_p1_v2.py     # -> results/v2/figures/*  (the analytical figures)
python tools/tablegen_p1.py      # -> docs/paper_1/review_draft_1/tables/*
python tools/fill_paper.py --auto --src <skeleton>.tex --out <compile>.tex
```

`scripts/` here holds copies of those generators plus `fidelity_rule.py` and
`linearisation_solved.py` (the two new-analysis scripts) for reference.

## Provenance of the new content in this revision

- Fidelity design rule `b = λ/(1+λ)` — `data/fidelity_rule.csv`, `scripts/fidelity_rule.py`.
- Solved linearisation error (−0.15 % winter / −0.33 % autumn) —
  `data/linearisation_solved.csv`, `scripts/linearisation_solved.py`.
- Exact decomposition / regret — `data/decomposition_live.csv`, `data/regret_decomp.csv`.
