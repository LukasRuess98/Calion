# F6 future-year grid emission factors — method (common Applied-Energy approach)

**Decision 2026-09-02 (user):** figure out the future-EF construction with the approach
commonly used in Applied Energy. Below is the standard, defensible method; the base year is
already implemented (real hourly `grid_co2_kg_MWh`). Future years are a **scenario axis of F6**,
constructed — not measured — and clearly labelled as such.

## Choice: AVERAGE emission factor (AEF), shape-preserving rescale

Applied-Energy DH/heat-pump *investment* studies overwhelmingly use the **average** grid EF
(attributional accounting of delivered electricity), not the marginal EF (MEF). MEF is for
real-time operational/consequential questions and needs a full future-grid dispatch model —
out of scope for a siting/sizing paper. We already use the hourly AEF for the base year, so
staying with AEF keeps base and future years consistent.

**Construction of a future year Y:**
1. Take the real base-year hourly shape `s(t) = grid_co2(t) / mean(grid_co2)` (electricitymaps
   2025, mean ≈ 278 kg/MWh) — dimensionless, mean 1.0, preserves diurnal/seasonal structure.
2. Multiply by the projected **annual-mean** AEF `Ē_Y` from an official national decarbonization
   scenario: `grid_co2_Y(t) = s(t) · Ē_Y`.
3. Feed as the hourly EF series (the model already consumes an hourly series).

This is the widely-used "shape-preserving rescale to a projected annual mean." It is transparent,
reproducible, and needs only ONE published number per future year.

## Annual-mean anchors (to CONFIRM against an official source before building F6)

Germany, indicative order of magnitude — cite the exact source when finalizing:
- **2025 base:** ~278 kg/MWh (our electricitymaps series mean) — real, used as-is.
- **2030:** ~150–190 kg/MWh (≈65–80% RES; e.g. UBA / Agora / Ariadne / NECP projections).
- **2045:** ~0–50 kg/MWh (climate-neutral target — near-zero grid).

Recommended primary source to pin the two numbers: a single consistent scenario family
(e.g. Ariadne, Agora "Klimaneutrales Deutschland", or the German LTS/NECP) so 2030 and 2045
come from the same trajectory. Report the source + values in T2/§7.

## Documented caveat (put in §8 limitations)

Shape-preserving rescale is a **first-order** approximation: as the RES share rises, the hourly
shape actually FLATTENS (more near-zero-EF hours, lower variance), which a uniform rescale does
not capture. This slightly understates the future value of load-shifting/storage. A refined
variant would use scenario hourly profiles from an energy-system model (Ariadne / openENTRANCE /
ENTSO-E TYNDP); noted as future work. For F6's break-even map this is acceptable because the
2026 point uses the REAL series and the future years are explicitly scenario points.

## Where it plugs in
- F6 = heatmap `c_CO2` × `c_el/c_gas` with a break-even contour; the 2026 point uses the real
  series; 2030/2045 appear as marked scenario points (per the plan's F6 spec).
- Implementation: a small helper that emits `grid_co2_<year>.csv` = `s(t)·Ē_Y`, selected per run
  via the same column the model already reads. No model change needed.

## Sources (landscape scan 2026-09-02)
- IEA Emission Factors 2025 methodology: https://iea.blob.core.windows.net/assets/2b5f6d31-3263-44bf-85bc-b754d1c69cd3/IEA_Methodology_Emission_Factors.pdf
- Hourly marginal EF estimation (fundamental+statistical): https://arxiv.org/pdf/2412.17379
- (Confirm the German 2030/2045 annual-mean anchors against Ariadne/Agora/UBA before finalizing.)
