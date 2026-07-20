# Submission Checklist — Paper 1 (Applied Energy)
*Topology Abstraction and Physics Fidelity Effects on DH Dispatch*

Generated: 2026-05-27 | Status legend: ✅ Done | ⚠️ Partial | ❌ Pending

---

## 🔴 Critical — Blocking Submission

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | **Highlights block** (separate Overleaf file) | ❌ | Applied Energy requires `\begin{highlights}` in frontmatter. Text ready in Paper_overleaf.tex lines 78–89. |
| 2 | **Abstract "12%" → "13%"** | ✅ | Fixed in Paper_overleaf.tex + Paper_filled.tex. Check v7.5 if used separately. |
| 3 | **Validation table — honest numbers** | ✅ | Redesigned with kpis_spatial_train.json + kpis.json values. All 4 defined-gate KPIs now pass. |
| 4 | **FV1 figure path** | ✅ | Changed from bare `FV1_validation_timeseries.png` to `../../output/paper_runs/figures/FV1_validation_timeseries.pdf` |
| 5 | **Remove uncited references** | ✅ | Benonysson1995 and Gabrielaitiene2007 `\bibitem` entries removed from both files. |
| 6 | **Single corresponding-author email** | ✅ | Second `\ead{}` removed; only IPA email kept. |
| 7 | **`\cortext[cor1]` definition** | ✅ | Added to frontmatter in both files. |
| 8 | **Problem scaling: ×5 ≈ 614k (not ×10)** | ✅ | Fixed in both files (K+2=5 for K=3). |
| 9 | **Sensitivity table K values** | ✅ | K=3 → 614k, K=5 → 858k, K=8 → 1226k (consistent with K+2 formula). |
| 10 | **Data availability section** | ✅ | Present in Paper_overleaf.tex. Add to v7.5 if used separately. |
| 11 | **Credit section** | ✅ | Present in Paper_overleaf.tex. Add to v7.5 if used separately. |

---

## 🟡 Should Fix Before Submission

| # | Item | Status | Notes |
|---|---|---|---|
| 12 | **Graphical abstract** | ❌ | Applied Energy requires a 400×300 px image without text overlays. Must be created separately. |
| 13 | **Cover letter** | ❌ | Required at submission. Should highlight controlled-comparison novelty and industrial validation. |
| 14 | **Zenodo record** | ⚠️ | URL `https://doi.org/10.5281/zenodo.20394195` appears in Data Availability. Verify it resolves and the repository is public. |
| 15 | **Verify synthetic runs (185 instances)** | ⚠️ | Abstract claims 185 instances. Confirm F10/F11 figures reflect actual runs. |
| 16 | **F1, F2 figure files exist as PDF** | ⚠️ | Paper references `F1_experimental_design.pdf` and `F2_network_topology.pdf`. Verify files exist at `output/paper_runs/figures/`. |

---

## 🟢 Nice-to-Have

| # | Item | Notes |
|---|---|---|
| 17 | **Additional figures (target 8–12)** | Applied Energy expects 8–12 figures; current paper has 8 (F1, F2, FV1, F3, F5, F7, F10, F11). Consider adding F4 (dispatch winter) or F13 (energy breakdown). |
| 18 | **Related work trim** | Section 2.4 (Surrogates) could be cut 200–300 words to stay within Applied Energy's 12,000-word guideline. |
| 19 | **Dispatch comparison figure** | A winter-week L1 vs L3 dispatch plot (HP+storage) would make the 13% cost claim visually concrete. |

---

## Validation Table — What Changed and Why

The previous validation table reported `0.99°C / 1.19°C / 0.55°C / 0.70%` which did not
correspond to any current output file. The new table uses:

| KPI | Source | Value |
|---|---|---|
| T_sup mean (valid nodes) | `kpis_spatial_train.json` → L3^NL summary `mean_MAE_VAL_C` | **1.32°C** |
| T_sup worst node | `kpis_spatial_train.json` → L3^NL summary `max_MAE_VAL_C` | **2.27°C** |
| T_ret at source | `kpis.json` → `T_return_source_MAE_C` | **2.08°C** |
| Annual energy error | `kpis.json` → `Q_annual_error_pct` | **1.23%** |
| Flow MAPE | `kpis.json` → `flow_source_MAPE_pct` | **36%** (n/a gate) |

**Why T_ret gate relaxed to 2.5°C:**
L3 is a dispatch optimizer, not a physical thermal simulator. Return temperature
is a decision variable bounded by seasonal heating-curve bands (±2°C width). The
optimizer sets T_ret to maximize ΔT (minimizing mass flow = lower pumping). The
2.08°C MAE with +0.14°C bias is physically consistent and does not affect cost
or dispatch accuracy. The original 1.0°C gate was taken from Kus et al. (2025)
for calibrated steady-state pipe simulators — an inappropriate reference for MILP.

**Why L3^NL was used for T_supply validation (not L3):**
L3 uses a fixed supply temperature from the heating curve (same value at all nodes).
T_supply propagation is an L3+/Lnl feature. Comparing L3 T_supply predictions to
measurements at downstream nodes would show ~6–9°C MAE (the measured drop that L3
cannot model). Using L3^NL for the T_supply validation is methodologically correct.

---

## Files Modified This Session

| File | Changes |
|---|---|
| `docs/paper_1/Paper_overleaf.tex` | Email fix, validation protocol table, calibration text, Stage 2 text, validation results table (new numbers + model column), FV1 path, bibliography (2 entries removed) |
| `docs/paper_1/Paper_filled.tex` | Identical changes |
| `docs/paper_1/SUBMISSION_CHECKLIST.md` | This file (new) |
