# Blockers and substitutes – central TES study

Status: 2026-10-08. Format of spec section 13. None of the items below stops the runs; each is replaced by a documented
substitute and listed as a question.

```text
BLOCKER B1 (resolved with data, flagged):
  parameter: partner A waste heat Q_avail(t), T_source(t)
  why needed: HP source limit and COP
  where it enters the model: src constraint, COP series
  minimum acceptable substitute: measured 2023 water-based streams (v2: all four merged, 37.5 GWh/a) mapped to 2025
                                 (weekday-preserving); waste-heat fee 5 EUR/MWh (author decision, sensitivity 0/10/20)
  can a sensitivity replace it? yes, B1 (scale 50-125 %); holidays are not aligned
  NOTE: measured source temperature ≈ 17 °C (flow-weighted, P95 24 °C), not ≈ 40 °C as assumed in the specification

BLOCKER B2 (resolved by decision):
  parameter: HP capacity and performance map
  substitute: one HP 5 MW_th, Carnot fraction 0.50 (literature), lift flag 70 K
  sensitivity: B3 (η_C 0.4-0.6)

BLOCKER B3 (substitute):
  parameter: partner B electricity-cost components
  why needed: heat price c = (λ + c_el,var)/η + π
  minimum acceptable substitute: low/high pair from published 2025 components
    low  ≈ 12 EUR/MWh (v2, literature check: non-waivable levy floor ≈ 11.4; was 9): HV grid energy price ≈ 5 EUR/MWh (to be verified against the DSO price sheet), KWKG and offshore
                       surcharge limited to 15 % (EnFG, electricity-cost-intensive sector) 0.4 + 1.2, §19 surcharge 0.25 (C'),
                       electricity tax 0.5 (§9b relief), concession fee 1.1 EUR/MWh
    high ≈ 60 EUR/MWh: MV grid energy price ≈ 25 EUR/MWh (to be verified), KWKG 2.77, offshore 8.16, §19 0.5 (B'),
                       electricity tax 20.5 (no relief for heat sold to a third party), concession fee 1.1 EUR/MWh
  sources: 2025 levies (KWKG 0.277, offshore 0.816, §19 1.558/0.050/0.025, concession fee 0.11 ct/kWh) from a 2025 DSO
           price sheet; electricity tax 2.05 ct/kWh, §9b relief 2.0 ct/kWh
  can a sensitivity replace it? yes, A5 (low/high × demand charge none/full); reference = high (conservative)

BLOCKER B4 (substitute):
  parameter: TES reference volume, design pressure, T_low
  substitute: 5 000 m³ pressurised vessel (literature size class), 120 °C, T_low = P95 return 67.5 °C, 0.01 %/h loss
  sensitivity: A1 (0-20 000 m³ × 10-80 MW), A3 (temperature strategy)

BLOCKER B8 (question):
  parameter: plant capacities (plan A vs. existing configuration) and the 9.9 MW electric boiler at the KWK
  substitute: plan A values, boiler disabled (config switch `plants.existing_eb_at_kwk.enabled`); v2 sensitivity P
              (eb_kwk_9.9): F000 −54 kEUR/a, v(F111) 529 kEUR/a
```

## Resolved

| # | Item | Resolution |
|---|---|---|
| B5 | prices | DE-LU day-ahead 2023–2025 downloaded (`data/prices/`); v2: gas 48 EUR/MWh, CO2 72 EUR/t from 2025 EEX futures means (D12) |
| B6 | pump curves | generic curves (shut-off ratio 1.2) anchored at plan A; the MVA curve is exceeded by measured 2025 operation in 64 h (max +1.5 bar at the converted flows) → head scaled ×1.18 to the 2025 envelope (G2 item, needs approval) |
| B7 | link DN | DN 400 from the operator valve table |
| – | summer Δp master | KWK remains the pressure holder at ≈ zero net flow (2025 data) |
