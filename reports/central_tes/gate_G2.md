## Gate G2 report — 2026-10-08
**Status:** PARTIAL — the G2 stop condition was hit (F000 violates hydraulic limits) and resolved by D3–D5; approval needed

### Done
- Hydraulic evaluation of hourly schedules on the calibrated meshed Ersatznetz (variants A, C, B), vectorised (8 759 h in ≈ 0.5 s) (`hydraulics.py`).
- Control: KWK pressure holder all year (2025 data), Δp = min. value for V06 ≥ 1.2 bar and Mitte ≥ 1.0 bar.
- Plant Δp anchored to the measured value of the hour; absolute return pressures from the symmetric supply/return split (checked against 2025: MVA return pressure, slope 1.02, R² 0.97).
- Hard limits: pump curves, plant shutdown pressures, PN25, KWK reverse flow; soft limits reported; saturation margin, pump power.
- Measured 2025 dispatch evaluated: feasible in all hours with the envelope-anchored curves.
- F000 (energy-only) evaluated: **violates in 93 h (A), 93 h (C), 100 h (B)** → G2 stop → diagnosis and resolution below.

### Files added / changed
- `scripts/dhn_study/central_tes/hydraulics.py` — evaluator
- `scripts/dhn_study/central_tes/coupling.py` — Mode E validation, attribution test, Mode H

### Tests
Mass balance (≤ 1e-6 kg/s), loop residual (≤ 1e-5 bar), node mapping, measured dispatch feasible: passed.

### Key numbers
| metric | value | unit | scenario |
|---|---|---|---|
| generic pump curve (nominal anchor) exceeded by measured 2025 operation | MVA 64 h, max +1.5 bar; others 0 h | – | measured |
| head scale to the 2025 envelope | MVA ×1.18, others ×1.0 | – | – |
| F000-E violating hours | 93 / 93 / 100 | h | A / C / B |
| … by limit (A) | MVA pump 79, GT pump 13, KWK pump 1 | h | F000-E |
| … by month (A) | Mar 42, Oct 30, Feb 10, Jan 4, May 3, Sep 3, Dec 1 | h | F000-E |
| required KWK Δp P50 / P95 / max | 2.07 / 4.33 / 7.42 (measured dispatch 2.21 / 3.18 / 4.43) | bar | F000-E (A) |
| KWK > 4.0 bar (soft) | 673 h (measured dispatch 6 h) | h | F000-E (A) |
| MVA > 7.5 bar (soft) | 1 420 h (measured 559 h) | h | F000-E (A) |
| binding station | V06 85 %, V23 14 % | – | F000-E (A) |
| min. plant return pressure | MVA 5.17 (trip 5.0), GT 5.11 (trip 4.4) | bar | F000-E (A) |
| min. saturation margin | 8.2 | bar | F000-E |
| pump electricity | 2 627 | MWh/a | F000-E (A) |

### Diagnosis
The violations are caused by the dispatch of the **existing** plants, not by the central feed-in (F000 has none):
in the violating hours the energy-only MILP runs HW1 at 0 MW (measured: 11 MW) and the GT at 15 MW (measured: 6 MW).
Without HW1 the KWK must raise its Δp to keep V06 at 1.2 bar (mean 3.5 bar vs 2.35 bar measured in the same hours);
the east plants feed against this Δp (≈ 1:1 coupling) and exceed their pump curves. The operator evidently runs HW1 also
as south-end pressure support — an operational rule the energy layer does not know.

### Deviations from spec (+ reason)
- D3: Mode H acts on all feed-ins with linearised hydraulic cuts (bisection on Q_central alone cannot repair violations that exist at Q_central = 0).
- D4: plan-A mass-flow limits in the energy layer (without them F000 violates in 485 h).
- D5: pump heads scaled to the 2025 envelope (reported here, not silent).
- Consequence for the metrics: ΔC_hyd(S) contains the cost of making the existing-plant dispatch feasible (≈ ΔC_hyd(F000)); the share caused by the new assets is ΔC_hyd(S) − ΔC_hyd(F000).

### New assumptions
- `hydraulics.pump_curve.shutoff_ratio` 1.20 (Gülich range 1.1–1.35), anchor `envelope`.
- `hydraulics.cut_margin_bar` 0.02, `k_max` 8.
- Station-to-plant offsets a_g of the return pressure fitted on 2025 (MVA +0.77, GT +0.11, Bio +0.47, HW1 −0.98 bar).

### Questions for the authors
1. Accept D3 (cut-based Mode H on all feed-ins) as the paper's Mode H, with the spec method reported as a variant?
2. Accept the envelope-anchored pump curves (MVA ×1.18), or provide manufacturer curves / pump speed limits?
3. Should the operator's experience values (KWK 4.0 bar, east 7.5 bar) become hard limits in a sensitivity (B4)? With KWK ≤ 4.0 bar as hard limit, F000 would be infeasible in ≈ 670 h, mainly Jan/Feb.

### Proposed next step
G3: Mode E factorial with post-hoc validation (all three calibrations).
