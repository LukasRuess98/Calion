"""
Objective vs. economic cost for the hardened decomposition lineage
(CP=T0P0, CP+L=T0P1a, CP+Lb=T0P1b, ND0=T2P0, L1=T2P1_defU).

Purpose: supply the §2.6 methods note on the CURRENT run lineage, replacing the stale
results/v2/analysis/economic_gaps.csv (OLD lineage L1..L3plus; its "residual dominated by
the return-temperature regularizer" claim does NOT hold here).

Pure post-processing of existing run outputs. NO solve.

============================================================================
FINDING (what the ~39-41 % objective/economic gap actually is on this lineage)
============================================================================
The three terms named in the review are ALL STRUCTURALLY ZERO here (verified in the
configs + calion source, not assumed):
  * terminal_value = 0  -- every config uses  terminal.policy: equal  (hard cyclic SOC
    constraint); component_assembler._build_terminal_value_term returns None for
    policy not in {value, soft}, so no penalty term enters the objective.
  * return_anchor  = 0  -- return_temp_soft_anchor_enabled defaults False
    (thermal_node.py L174) and is not set in any of these configs.
  * demand_slack   = 0  -- allow_heat_demand_slack defaults False (thermal_node.py L250)
    and summer_warmup_hours defaults 0 (pipe_pair.py L419); neither is set.

The residual is instead TWO real (non-regularizer) pieces:

  (1) CHP CO2 self-use correction.  The Gurobi objective minimises the GROSS CO2 cost
      (co2_cost_total_expr, all fuel+grid emissions at costs.co2_price_eur_per_t).
      result_collector then OVERWRITES the *reported* CO2 with a CHP-self-use-corrected
      NET value (result_collector.py L615-623): the CO2 attributed to CHP electricity that
      is self-consumed (not sold) is credited back, selfuse_fraction=(chp_el-p_sell)/chp_el.
      economics.csv cost_co2_eur (hence z_econ, hence bias/regret) uses the NET; the
      objective used the GROSS. Their difference (~55-58 kEUR/run) is the bulk of the gap.
  (2) TES cycling cost.  cycling_cost_eur_per_mwh (=2) x charge+discharge throughput
      (~24-26 kEUR/run); in the objective, absent from the six economic columns.

  (1)+(2) reproduce the residual to within ~1.4-1.6 kEUR/run (0.7-0.8 % of objective);
  the small remainder is gross-CO2-expr / cycling-basis detail not persisted per run
  (the full result_collector `objective` breakdown dict is not saved to these run dirs).

Implication for §2.6: report bias/regret on ECONOMIC cost (z_econ) because the objective
carries (a) a CO2 term on a GROSS basis that the reporting corrects to the standard CHP
self-use net, and (b) a TES cycling penalty -- neither is the marginal economic cost of the
schedule. This is NOT the return-temperature regularizer story from the old lineage.

Outputs: results/v2/analysis/objective_decomposition.csv
"""
import json
import os

import pandas as pd
import yaml

WT = "../paper1_faithful_c19d690"
OUT = f"{WT}/output/paper1_v2"
CFG = f"{WT}/configs/memmingen"

LEVELS = {
    "CP":    ("T0P0",      "Memmingen_T0P0"),
    "CP+L":  ("T0P1a",     "Memmingen_T0P1a"),
    "CP+Lb": ("T0P1b",     "Memmingen_T0P1b"),
    "ND0":   ("T2P0",      "Memmingen_T2P0"),
    "L1":    ("T2P1_defU", "Memmingen_T2P1_defU"),
}

# economic components (sign): identical to tools/economic_cost.py and regret_decomp z_econ
ECON = [
    ("cost_energy_buy_eur", +1),
    ("revenue_sell_eur", -1),
    ("cost_fuel_eur", +1),
    ("cost_co2_eur", +1),          # NET (CHP-self-use-corrected) CO2, as reported
    ("cost_dump_eur", +1),
    ("cost_demand_charge_eur", +1),
    ("cost_pump_eur", +1),
]


def _cfg(stem):
    with open(f"{CFG}/{stem}.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _cycling_rate(cfg):
    def _walk(o):
        if isinstance(o, dict):
            if "cycling_cost_eur_per_mwh" in o:
                try:
                    return float(o["cycling_cost_eur_per_mwh"])
                except Exception:
                    return None
            for v in o.values():
                r = _walk(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = _walk(v)
                if r is not None:
                    return r
        return None
    r = _walk(cfg)
    return float(r) if r is not None else 0.0


def main():
    rows = []
    for lv, (rid, stem) in LEVELS.items():
        rd = f"{OUT}/{rid}"
        ec = pd.read_csv(f"{rd}/economics.csv").iloc[0]
        meta = json.load(open(f"{rd}/meta.json"))
        cfg = _cfg(stem)
        disp = pd.read_csv(f"{rd}/dispatch_hourly.csv")

        obj = float(meta["objective"])
        econ = sum(s * float(ec.get(c, 0.0) or 0.0) for c, s in ECON)
        residual = obj - econ

        # (1) CHP CO2 self-use correction: objective charges GROSS, economics reports NET.
        co2_price = float(cfg.get("costs", {}).get("co2_price_eur_per_t", 0.0))
        gross_co2_eur = float(ec.get("co2_total_t", 0.0) or 0.0) * co2_price
        net_co2_eur = float(ec.get("cost_co2_eur", 0.0) or 0.0)
        co2_selfuse_correction = gross_co2_eur - net_co2_eur

        # (2) TES cycling cost: rate x (charge+discharge) throughput.
        thru = 0.0
        if {"Q_storage_charge_MW", "Q_storage_discharge_MW"} <= set(disp.columns):
            thru = float(disp["Q_storage_charge_MW"].clip(lower=0).sum()
                         + disp["Q_storage_discharge_MW"].clip(lower=0).sum())
        tes_cycling = _cycling_rate(cfg) * thru

        closure = residual - co2_selfuse_correction - tes_cycling  # ~1.4-1.6k, see docstring

        rows.append({
            "level": lv,
            "run_id": rid,
            "gurobi_objective_eur": round(obj, 2),
            "econ_cost_eur": round(econ, 2),
            "residual_eur": round(residual, 2),
            "residual_pct": round(100.0 * residual / obj, 3) if obj else float("nan"),
            # verified structural zeros (the three review-named terms):
            "terminal_value_eur": 0.0,
            "return_anchor_eur": 0.0,
            "demand_slack_eur": 0.0,
            # the residual's real composition:
            "co2_selfuse_correction_eur": round(co2_selfuse_correction, 2),
            "tes_cycling_eur": round(tes_cycling, 2),
            "closure_residual_eur": round(closure, 2),
        })

    df = pd.DataFrame(rows)
    os.makedirs("results/v2/analysis", exist_ok=True)
    dst = "results/v2/analysis/objective_decomposition.csv"
    df.to_csv(dst, index=False)
    pd.set_option("display.width", 240, "display.float_format", lambda x: f"{x:,.2f}")
    print(df.to_string(index=False))
    print(f"\nwrote {dst}")


if __name__ == "__main__":
    main()
