"""
Regret sensitivity (Paper 1, P11) — how the copperplate regret depends on the two
documented assumptions: the marginal heat cost used to charge the extra loss a
coarser model ignored, and the demand disaggregation rule.

Marginal-cost anchors (Memmingen assets, config-grounded):
  biomass+CO2  ~47.1   (40/0.85 + 20/0.85*0.1)
  gas fuel-only 50.0   (45/0.90)               <- previous base (understates: no CO2)
  gas+CO2      ~72.2   (45/0.90 + 200/0.90*0.1) <- most complete for extra gas burn
  EK-ish       ~90     (grid elec + grid CO2 via electrode boiler)

Disaggregation: 'demand' = real per-node demand (the physical truth for Memmingen,
central generation), 'uniform' = equal per consumer (robustness — regret must not be
an artifact of the rule).

Output: results/v2/analysis/regret_sensitivity.csv
"""
import dataclasses
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import evaluator as E  # noqa: E402

BASE = "../paper1_faithful_c19d690/configs/memmingen/"
CFG_FILES = {"L1": "Memmingen_L1.yaml", "L2": "Memmingen_L2.yaml",
             "L3": "Memmingen_L3_MILP.yaml", "L3plus": "Memmingen_L3_MILP.yaml"}
RUNS = {lv: f"output/paper1_corrected/{lv}" for lv in CFG_FILES}
REF = "L3"
MARGINALS = {47.1: "biomass+CO2", 50.0: "gas fuel-only",
             72.2: "gas+CO2", 90.0: "EK-ish"}


def models_loss(lv, cfgs):
    c = cfgs[lv]
    return bool((c.get("network", c).get("physics", {}) or {}).get("heat_loss", True))


def main():
    cfgs = {lv: E._load_yaml(BASE + f) for lv, f in CFG_FILES.items()}
    base_cost = E.cost_params_from_config(cfgs[REF])
    rows = []
    for rule in ("demand", "uniform"):
        # physical network built ONCE from the T2 (ref) config; only the schedule varies
        ref_run = E.load_run(RUNS[REF])
        net = E.network_from_run(ref_run, cfgs[REF], share_rule=rule)
        for m, mlabel in MARGINALS.items():
            cost = dataclasses.replace(base_cost, marginal_heat_cost_eur_mwh=m)
            zev, extra = {}, {}
            for lv, rd in RUNS.items():
                r = E.load_run(rd)
                res = E.evaluate(r, net, cost, physics="full",
                                 models_loss=models_loss(lv, cfgs))
                zev[lv] = res.total_cost
                extra[lv] = res.cost_components["extra_loss_mwh"]
            for lv in RUNS:
                rows.append({
                    "share_rule": rule, "marginal_eur_mwh": m, "marginal_label": mlabel,
                    "level": lv,
                    "regret_pct": 100.0 * (zev[lv] - zev[REF]) / zev[REF],
                    "z_eval_eur": zev[lv], "extra_loss_mwh": extra[lv],
                })
    df = pd.DataFrame(rows)
    os.makedirs("results/v2/analysis", exist_ok=True)
    df.to_csv("results/v2/analysis/regret_sensitivity.csv", index=False)

    pd.set_option("display.width", 220, "display.float_format", lambda x: f"{x:,.2f}")
    print("=== L1 (copperplate) regret_pct across assumptions ===")
    piv = df[df.level == "L1"].pivot(index="marginal_label",
                                     columns="share_rule", values="regret_pct")
    print(piv.to_string())
    print("\n=== full regret_pct table (share_rule=demand) ===")
    dd = df[df.share_rule == "demand"].pivot(index="level",
                                             columns="marginal_label", values="regret_pct")
    print(dd.to_string())
    print("\nwrote results/v2/analysis/regret_sensitivity.csv")


if __name__ == "__main__":
    main()
