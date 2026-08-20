# Submission pack — APEN-D-26-15734 (Applied Energy, major revision)

**"Estimation Bias versus Decision Regret in District-Heating Dispatch Optimisation:
Loss Visibility, not Network Topology, Sets the Fidelity Requirement"**

Assembled 2026-08-12. Two self-contained folders.

```
submission_pack/
├── 01_latex_build/          → everything to compile the manuscript + figure data
│   ├── paper_COMPILE.tex        the compile-ready manuscript (\result macros filled)
│   ├── paper_source_skeleton.tex the source (\result macros unfilled; regen only)
│   ├── tables/                  18 \input tables (auto-generated)
│   ├── figures/                 5 analytical figures (PDF+PNG) + validation/ subfolder
│   ├── elsevier_class/          cas-dc.cls, cas-common.sty, cas-model2-names.bst
│   ├── data/                    analysis CSVs (time series behind every figure)
│   ├── scripts/                 figure/table/fill generators (reference)
│   ├── paper1_dh_fidelity/      ← DROP Paper20_Literatur.bib HERE (only missing file)
│   └── README_BUILD.md          build steps, figure-wiring map, regeneration
│
└── 02_correspondence/       → reviewer + editor correspondence
    ├── Reviewer_Mail.md         the reviewers' comments (R1.x, R2.x)
    ├── response_letter.md       point-by-point response (all R1.1–R1.7, R2.1–R2.5)
    ├── extension_request.md     deadline-extension letter to the editor
    └── working_notes/           planning/status/prompt docs (internal, not for submission)
```

## Status

- Manuscript: all prose drafted, all value macros resolved, no content gaps.
- Response letter: every reviewer point answered.
- Figures (5 analytical + validation set) and 18 tables: current, regenerated 2026-08-12.
- **One external file required to complete the build:** `Paper20_Literatur.bib`
  (see `01_latex_build/paper1_dh_fidelity/`).

## Remaining author-only items (marked `<<AUTHOR-CONFIRM:...>>` in the .tex)

1. Fill Acknowledgments (funding / data provider), the generative-AI declaration, and
   the CRediT author roles.
2. Add the bibliography `.bib` and compile on your Elsevier `cas-dc` toolchain.
3. In the response letter, the `[... Table ..., Figure ...]` tags take final numbers
   after compilation.
4. Set the final extension date in `extension_request.md`, then submit.
