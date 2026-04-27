# Config Resolution Log — §1 Decisions

## U-values (§1.4)

Approach (a): explicit `u_value_supply_w_per_m_k` / `u_value_return_w_per_m_k` per pipe.

| DN range | Supply U [W/(m·K)] | Return U [W/(m·K)] | Source |
|----------|--------------------|--------------------|--------|
| DN ≤ 200 | 0.28 (framework default) | 0.30 (framework default) | EN 253 small-DN avg |
| DN ≥ 250 | 0.32 | 0.34 | EN 253 large-DN avg |

Applied to: Memmingen_L2.yaml, Memmingen_L3_MILP.yaml, Memmingen_L3_MIQP.yaml.
L1 has no pipes — not applicable.

## Electrode Boiler (§1.2)

Not present at Memmingen site. Omitted from all configs.
Document in paper §6 Limitations: "An electrode boiler was not included as the Memmingen plant does not operate one."

## HP Capacity (§1.3)

Kept at 100 MW per user instruction. User will adjust manually.
Warning: peak network demand ≈ 76 MW — HP oversized by 32%. May suppress gas/CHP dispatch.

## CO₂ EF (B2)

Natural gas: 200 kg CO₂/MWh_fuel (≈ 0.20 t/MWh_HHV). Applied to all configs.
Previous incorrect value in L1/L2/L3_MILP: 500 kg/MWh (was roughly double reality).

## Pipe Roughness (B7)

0.5 mm (aged steel) confirmed by user. Previously 0.05 mm in all configs.
Friction factor impact: Colebrook-White at Re~1e6, ε/D~0.001 → f≈0.020 (smooth) vs f≈0.023 (0.5mm rough), ~15% higher pressure drop.

## Dump Cost (B7)

Raised from 10 → 1000 €/MWh_th. Effectively penalises curtailment to zero.

## Time Horizon (B8)

Full year: 2025-01-01 00:00 → 2025-12-31 23:00 (8760 h).

## Solver (B6)

All configs: Gurobi. L3_MIQP: NonConvex=2, MIPGap=0.005, TimeLimit=86400, NumericFocus=3, Heuristics=0.2.
L1/L2/L3_MILP: MIPGap=0.01, TimeLimit=3600.

## Journal (Q9)

Applied Energy → author-year bibliography (`\bibliographystyle{elsarticle-harv}`).
