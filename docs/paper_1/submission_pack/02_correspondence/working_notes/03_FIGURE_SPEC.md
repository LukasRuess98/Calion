# Figure specification v2

> **ALIGNED to `00_MASTER_STATUS.md` (2026-08-10).** Shape A: drop Stadtbach-specific
> figures (F11 Δp, F14 two-network, F16 Stadtbach topology) → the moderator figure now
> uses the **synthetic** central-vs-distributed factor; F11-equivalent Δp validation
> uses the **Memmingen pressure study** (pandapipes agreement + Wilo pump budget). ADD:
> (i) the **fidelity-ladder decomposition bar** (CP→CP+L→…→L6, loss vs topology vs
> station-hydraulics contributions); (ii) **L4/L5 station-hydraulics** panel (pump
> budget vs installed, dynamic-Δp effect ≈ 0); (iii) the **defensible-U vs v1-inflated
> loss** comparison showing coarse levels undercount last-mile loss. F1 must show the
> redesigned ladder from `08_LEVEL_REDESIGN.md`.

16 figures: 6 new, 5 redesigned, 5 carried over. Implementation in `prompts/P8_figures.md`.

## Constraints
Vector PDF + 300 dpi PNG · single column 88 mm, double 180 mm · ≥7 pt at final
size · colour-blind safe, never colour alone · every figure from a CSV with a
sidecar source file. (Shape A: no Stadtbach data enters Paper 1, so the NDA is moot.)

## List

| ID | Status | Col | Content |
|---|---|---|---|
| F1 | redesign | 1 | T×P grid; seven contrasts; `T0P1`/`T2P3` badged NEW |
| F2 | fix | 1 | Memmingen topology, all assets at j1 |
| F3 | keep | 1 | Stage 1 validation winter week |
| F4 | keep | 1 | BCM scatter, in-sample vs out-of-sample marked |
| F5 | keep | 1 | BCM January time series |
| **F6** | **NEW** | **2** | **Bias vs regret vs violations — headline** |
| F7 | update | 2 | Synthetic overview, 81 configs, three terms |
| F8 | update | 1 | Gap surface, balanced |
| F9 | update | 1 | Effect hierarchy, new contrast order |
| F10 | update | 1 | Accuracy vs solve time, `T0P1b` added |
| **F11** | **NEW** | 1 | **Memmingen modelled Δp vs pandapipes cross-check (station hydraulics, L4/L5)** |
| F12 | NEW | 1 | Clustering robustness, `loss_main` reference line |
| F13 | NEW | 1 | Optimality-bound intervals |
| **F14** | **NEW** | 1 | **Synthetic central vs distributed generation contrast (moderator)** |
| **F15** | **NEW** | 1 | **Out-of-sample prediction on held-out synthetic nets + parameterised L4** |
| ~~F16~~ | CUT | — | ~~Stadtbach topology~~ — dropped under Shape A |

## The four load-bearing figures

**F6 — Bias vs regret.** (a) scatter, bias on x, regret on y, one point per
(case, level), 1:1 line — if points sit far below the diagonal the message is
visible instantly. (b) paired bars per level per case. (c) physical violations:
hours and violation energy. Panel (c) may be the strongest result in the paper —
a schedule that looks cheap but is not deliverable is a harder criticism of low
fidelity than any cost figure, and no prior study reports it.

**F11 — Station-hydraulics validation (Memmingen pressure study).** Modelled trunk
Δp vs an independent **pandapipes** solve (agreement <0.007 bar), plus the pump
budget: ~3 kW station+lateral hydraulic need vs 110.8 kW installed (Wilo datasheet),
and the dynamic flow-dependent station Δp effect ≈ 0. This is the direct, real-component
answer to R2.4 — and the finding that even station-level detail does not change decisions.

**F14 — Generation-topology contrast (synthetic moderator).** `loss_main`,
`topo_main`, `interaction` for the synthetic **central** vs **distributed**
generation factor. Under central generation `topo_main`≈0 is proven across 42 nets;
the distributed arm is the moderator test. **Prepare both captions** — if the
distributed effect is also ≈0 the figure still works and says something more
surprising (routing null even under distributed generation). NB: the distributed
arm depends on the synth-model source-injection redesign (master §5b) — if it stays
scope-limited, this figure carries the central result + an explicit open question.

**F15 — Out-of-sample prediction.** Predicted vs actual bias; fitted points
(Memmingen + a training subset of the synthetic factorial) in one colour, held-out
synthetic nets (longer pipe lengths, beyond the fitted range) as extrapolation
markers with CI, plus the parameterised L4 point. Honest either way.

## Graphical abstract — regenerate

Fix: HP drawn at a remote node (all Memmingen assets are at j1); "+10,5 %" vs the
paper's 10.4 %; typo "topolpgy". Reframe around bias vs regret and the fidelity
ladder (Memmingen + synthetic factorial; no second real network).

## Highlights — ≤85 characters each, checked in code

Draft, finalise after P7:
```
Decision regret separates estimation bias from dispatch quality in DH models
Copperplate bias comes from loss visibility, not from spatial routing
Loss dominance holds across a balanced synthetic network factorial
Station-resolved hydraulics validated on real component data change decisions by ~0
Simplified schedules can be cheap on paper yet physically undeliverable
```
