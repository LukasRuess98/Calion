# Building the clean and marked-up versions from one source

Elsevier wants both a clean manuscript and one showing the changes. Build them from the
**same** `.tex` so they cannot drift apart — the failure mode is a marked-up copy that
disagrees with the clean one, which is worse than submitting no markup at all.

## Mechanism

Add to the preamble of `paper_COMPILE.tex`:

```latex
\usepackage{xcolor}
%% Toggle: comment the next line to produce the CLEAN version.
\newif\ifmarkup \markuptrue

\ifmarkup
  \newcommand{\new}[1]{\textcolor[HTML]{1A5FB4}{#1}}   % new in revision
  \newcommand{\chg}[1]{\textcolor[HTML]{0F7A5A}{#1}}   % v1 text, materially rewritten
  \newcommand{\gone}[1]{\textcolor[HTML]{9A9996}{[removed: #1]}}
\else
  \newcommand{\new}[1]{#1}
  \newcommand{\chg}[1]{#1}
  \newcommand{\gone}[1]{}
\fi
```

Then:

```
# marked-up
pdflatex paper_COMPILE && bibtex paper_COMPILE && pdflatex paper_COMPILE && pdflatex paper_COMPILE
mv paper_COMPILE.pdf paper_MARKUP.pdf

# clean: set \markupfalse, rebuild
mv paper_COMPILE.pdf paper_CLEAN.pdf
```

## Rules for applying the markup

**Wrap at paragraph granularity, not sentence.** The revision rewrote most of the
manuscript; sentence-level colouring would produce a page of confetti and tell the editor
nothing. One `\new{...}` around a whole paragraph is readable and honest.

**Which macro for which content:**

| Content | Macro |
|---|---|
| The eleven merged section files, except where they transcribe v1 | `\new` |
| Sections that transcribe v1 with level names remapped | `\chg` |
| Numbers that changed with the 135-net grid | `\chg` |
| Whole subsections that are new (§2.7 cost accounting, §3.4 clustering, §3.11 physics nulls, §3.9 fidelity vs cost) | `\new` |
| v1 material deliberately dropped | `\gone`, sparingly — see below |

**Use `\gone` for exactly three things**, because they are removals a reviewer would
otherwise read as evasion:

1. v1's BCM cross-check (the ×1.330 trunk U-multiplier) — removed because the multiplier
   is what R2.4 objected to.
2. v1's limitation conceding that linearisation and transport delay could not be separated
   — removed because the revision separates them.
3. v1's physics-scope mapping table — removed per R2.5's taxonomy-consistency request.

Everything else that disappeared did so because it was rewritten, and the `\chg` colour
already says so.

## Legend

Put a boxed legend under the title in the markup build only:

```latex
\ifmarkup
\begin{center}\footnotesize\fbox{\parbox{0.9\linewidth}{%
\textbf{Marked-up copy.} \textcolor[HTML]{1A5FB4}{Blue} marks material new in this
revision; \textcolor[HTML]{0F7A5A}{green} marks text carried from the original submission
and materially rewritten; \textcolor[HTML]{9A9996}{grey} marks deletions we judged a
reader would want flagged. Unmarked text is unchanged. Because the manuscript was
restructured and the model levels renamed, marking is at paragraph rather than sentence
granularity.}}\end{center}
\fi
```

That last sentence matters. It pre-empts the obvious objection — that the markup is
coarse — by giving the reason before the editor forms it.

## Before you build

The manuscript now `\input`s twelve files from `sections/`. Create that folder and copy
them from `03_draft_revision/02_revision_hand_in/`:

`introduction_opening_v2`, `related_work_v2`, `base_formulation_v2`,
`cost_accounting_v2`, `extended_physics_v2`, `validation_protocol_v2`,
`computational_setup_v2`, `validation_results_v2`, `fidelity_vs_cost_v2`,
`physics_null_mechanisms_v2`, `limitations_v2`, `nomenclature_v2`.

Also still required: `Paper20_Literatur.bib` into `paper1_dh_fidelity/`, with the VSS
entries merged or the `\bibliography` line extended.
