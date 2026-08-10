# P8 — Figures

**Depends on:** P7 · **Blocks:** P9
Spec in `../03_FIGURE_SPEC.md`. Implementation notes here.

## Requirements

- Extend `tools/figgen.py`; keep the existing publication style
- Vector PDF for the manuscript, 300 dpi PNG for preview
- Single column 88 mm; double column (`figure*`) 180 mm; ≥7 pt at final size
- Every figure reads a CSV from `results/v2/analysis/` and writes a sidecar
  `{name}.source.txt` naming file and columns
- Colour-blind safe; never encode an essential distinction by colour alone
- **NDA:** no Stadtbach figure may show identifiable consumer-level data.
  Aggregate, normalise or anonymise. Check before writing.

## Figure list

| ID | Status | Content |
|---|---|---|
| F1 | redesign | T×P grid with the seven isolated contrasts; `T0P1` and `T2P3` badged NEW |
| F2 | fix | Memmingen topology — **all assets at j1** |
| F3 | keep | Stage 1 validation, winter week |
| F4 | keep | BCM scatter, now with in-sample/out-of-sample split |
| F5 | keep | BCM January time series |
| **F6** | **NEW** | **Bias vs regret** — the headline |
| F7 | update | Synthetic overview, 81 configs, three decomposition terms |
| F8 | update | Gap surface, balanced factorial |
| F9 | update | Effect hierarchy in the new contrast sequence |
| F10 | update | Accuracy vs solve time, `T0P1b` added as a point |
| **F11** | **NEW** | **Stadtbach measured vs modelled Δp** |
| F12 | NEW | Clustering robustness with `loss_main` reference line |
| F13 | NEW | Optimality-bound intervals |
| **F14** | **NEW** | **Two-network contrast: central vs distributed generation** |
| **F15** | **NEW** | **Out-of-sample prediction of Stadtbach** |
| F16 | NEW | Stadtbach network topology (3 arms, 6 producers, bidirectional trunk) |

## The four that matter most

### F6 — Bias vs regret (double column)
(a) Scatter: bias on x, regret on y, one point per (case, level), 1:1 line. If
points fall well below the diagonal, the paper's message is visible in one glance.
(b) Bar: bias and regret side by side per level, per case.
(c) Physical violations per level — hours and violation energy. If low-fidelity
schedules are undeliverable, this panel carries the strongest result in the paper.

### F11 — Stadtbach Δp validation (single column)
Measured vs modelled Δp per shaft pair, coloured by flow, 1:1 line, MAE/bias/R²
annotated, **fitted and held-out pairs marked differently**. This is the direct
answer to R2.4 and the thing v1 could not produce.

### F14 — Generation topology contrast (single column)
`loss_main`, `topo_main` and `interaction` for Memmingen (central) beside
Stadtbach (distributed). If `topo_main` is ≈0 in one and material in the other,
this single figure carries the moderator claim. If both are ≈0, the figure still
works and the caption changes — prepare both.

### F15 — Out-of-sample prediction (single column)
Predicted vs actual bias: fitted points (Memmingen + 81 synthetic) in one colour,
the Stadtbach prediction as a distinct held-out marker with its CI. Annotate that
Stadtbach lies beyond the fitted pipe-length range. Honest whichever way it lands.

## Also regenerate

**Graphical abstract** — three v1 defects: HP drawn at a remote node in the L2/L3
panels (all Memmingen assets are at j1); "+10,5 %" versus the paper's 10.4 %; the
typo "topolpgy". Reframe around bias vs regret and the two networks.

**Highlights** — 3–5 bullets, **≤85 characters each including spaces**, checked
programmatically. Draft after P7.

## Report

`revision/audit/P8_figures.md`: contact sheet, per-figure source CSV, width check,
NDA check, and any figure whose message changed versus v1.
