# §2.6 note — objective vs. economic cost (current lineage)

Provenance for the methods note that bias/regret are reported on **economic** cost, not the
raw Gurobi objective. Numbers from `results/v2/analysis/objective_decomposition.csv`
(generator `tools/objective_decomposition.py`; pure post-processing of the hardened runs,
no solve). **This replaces the stale `economic_gaps.csv`** (old L1..L3plus lineage), whose
"residual = return-temperature regularizer" premise does **not** hold here.

## Numbers (EUR)

| Level | run_id | Gurobi objective | Economic cost (z_econ) | Residual | Residual % |
|---|---|---:|---:|---:|---:|
| CP    | T0P0      | 195 994 | 115 551 | 80 443 | 41.0 % |
| CP+L  | T0P1a     | 221 502 | 135 288 | 86 214 | 38.9 % |
| CP+Lb | T0P1b     | 221 386 | 135 206 | 86 180 | 38.9 % |
| ND0   | T2P0      | 196 845 | 116 512 | 80 332 | 40.8 % |
| L1    | T2P1_defU | 222 227 | 136 142 | 86 085 | 38.7 % |

`z_econ` = energy_buy − revenue_sell + fuel + CO2(net) + dump + demand_charge + pump; it
matches `regret_decomp.csv` z_econ to the cent.

## What the ~39–41 % residual actually is

**The three terms named in the review are all structurally zero on this lineage** (verified in
configs + source, not assumed):

- **terminal_value = 0** — every config sets `terminal.policy: equal` (hard cyclic SOC
  constraint); `component_assembler._build_terminal_value_term` returns `None` unless the
  policy is `value`/`soft`, so no penalty term enters the objective.
- **return_anchor = 0** — `return_temp_soft_anchor_enabled` defaults `False`
  (`thermal_node.py` L174) and is not set in any of these configs.
- **demand_slack = 0** — `allow_heat_demand_slack` defaults `False` (`thermal_node.py` L250)
  and `summer_warmup_hours` defaults `0` (`pipe_pair.py` L419); neither is set.

The residual is two **real** (non-regularizer) pieces:

1. **CHP CO2 self-use correction (~55–58 k / run, the bulk).** The Gurobi objective minimises
   the **gross** CO2 cost (`co2_cost_total_expr`, all fuel+grid emissions at
   `co2_price_eur_per_t = 100`). `result_collector` then **overwrites** the *reported* CO2
   with a CHP-self-use-corrected **net** value (`result_collector.py` L615–623): the CO2
   attributed to CHP electricity that is self-consumed rather than sold is credited back,
   `selfuse_fraction = (chp_el − p_sell)/chp_el` (≈0.18–0.20 here). economics.csv
   `cost_co2_eur` — hence `z_econ`, hence bias/regret — uses the **net** (~22–26 k, ≈29 €/t
   effective); the objective used the **gross** (~77–84 k, 100 €/t).
2. **TES cycling cost (~24–26 k / run).** `cycling_cost_eur_per_mwh = 2` × charge+discharge
   throughput; in the objective, absent from the six economic columns.

(1)+(2) reproduce the residual to within **~1.4–1.6 k / run (0.7–0.8 % of objective)**; the
small remainder is gross-CO2-expr / cycling-basis detail not persisted per run (the full
`result_collector` objective breakdown dict is not exported to these run dirs).

## Suggested §2.6 wording (drop-in skeleton)

> The optimiser minimises a model objective that, for numerical and accounting reasons,
> differs from the marginal economic cost of the resulting schedule by a systematic
> 39–41 % (Table X). Two mechanisms account for it. First, CO2 enters the objective on a
> **gross** basis (every tonne of fuel and grid electricity at the carbon price), whereas the
> reported cost applies the standard cogeneration self-use allocation, crediting back the CO2
> of CHP electricity that is self-consumed rather than exported; on this network that
> correction is ≈55–58 kEUR. Second, the objective carries a thermal-storage cycling penalty
> (2 €/MWh throughput, ≈24–26 kEUR) that is a solver-shaping term, not an operating cost.
> Because both are accounting artefacts of the objective rather than the marginal cost a
> planner would incur, all bias and regret figures in §X are reported on the **economic**
> cost — energy, fuel, net CO2, and demand charges — not the raw objective.

## CO2 convention — DECIDED (2026-08-12): report on the NET (CHP self-use) basis

The CO2 gross/net choice is a modelling decision. **Decision: keep the NET (CHP self-use /
substitution) basis** that `z_econ` already uses — the CO2 of CHP electricity exported to the
grid is credited (treated as displacing grid emissions), the standard avoided-emissions
convention in CHP/DH studies. Rationale: (i) it is a defensible, common method; (ii) switching
to gross would require re-deriving every bias/regret number and figure via the evaluator, for an
accounting choice that is defensible as-is; (iii) the paper's thesis (loss visibility dominates)
is invariant to the choice.

**Required in §2.6 (two sentences):**
1. State the convention explicitly: economic cost credits the CO2 of exported CHP electricity
   (avoided-emissions / substitution method); the objective minimises gross CO2, and the
   reported economic cost applies this credit — hence the gap in the table above.
2. Robustness line: because the CHP-CO2 credit is near-constant across model levels
   (≈55–58 kEUR here), loss-dominance and the sign of every bias/regret figure are invariant to
   the gross/net choice; only the magnitudes shift by ≈2–3 pts (e.g. CP bias −15.1 % net vs
   −12.2 % gross). No re-runs required.
