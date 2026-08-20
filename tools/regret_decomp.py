"""
Live regret + deliverability for the decomposition levels on the DEFENSIBLE-U lineage
(CP / CP+L / ND0 / L1), plus the review's #4 shortfall-pricing sensitivity.

Replaces the STALE regret_sensitivity.csv (its source runs, output/paper1_corrected/L1..L3,
were deleted; it also carried the pre-U-leak L1 regret 23.4%). Here every schedule is
executed on the SAME forward network built once from T2P1_defU (=L1), the finest clean
defensible-U level, which is also the regret reference.

Per-level loss crediting (models_loss), the subtle part:
  CP   (T0P0)     heat_loss:false, provisions NOTHING -> models_loss=False -> charged for
                  the full forward loss (correct: it ignored loss).
  CP+L (T0P1a/b)  copperplate whose demand is pre-inflated by the aggregate loss adder;
                  the run exports Q_loss_total = adder, so models_loss=True credits it that
                  provisioned loss (extra_loss = forward_loss - adder). Without this it
                  would be double-charged.
  ND0  (T2P0)     full topology, U=0 pipes -> modelled zero loss -> models_loss=False.
  L1   (T2P1_defU) node-resolved trunk loss -> models_loss=True (credit modelled loss).

#4 shortfall pricing: the copperplate's un-provisioned loss can be topped up at
  (a) the marginal running unit, (b) the peak/most-expensive unit, or (c) penalised as
  unmet demand at the dump price (config dump_cost = 1000 EUR/MWh). Regret must stay the
  same SIGN across all three. We report all.

Outputs: results/v2/analysis/regret_decomp.csv, regret_decomp_pricing.csv
"""
import dataclasses
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import evaluator as E  # noqa: E402

WT = "../paper1_faithful_c19d690"
CFG = f"{WT}/configs/memmingen"
OUT = f"{WT}/output/paper1_v2"

# level -> (run_dir, config_file, models_loss)
LEVELS = {
    "CP":   (f"{OUT}/T0P0",       f"{CFG}/Memmingen_T0P0.yaml",       False),
    "CP+L": (f"{OUT}/T0P1a",      f"{CFG}/Memmingen_T0P1a.yaml",      True),
    "CP+Lb":(f"{OUT}/T0P1b",      f"{CFG}/Memmingen_T0P1b.yaml",      True),  # heating-curve adder
    "ND0":  (f"{OUT}/T2P0",       f"{CFG}/Memmingen_T2P0.yaml",       False),
    "L1":   (f"{OUT}/T2P1_defU",  f"{CFG}/Memmingen_T2P1_defU.yaml",  True),
    # loss-aware node-resolved ladder (regret ~ bias, no calibration; the real content is the
    # contrast with CP/ND0 at +46 % regret, since z_eval-z_econ is a near-constant offset here).
    "L3":   (f"{OUT}/T2P3_defU",  f"{CFG}/Memmingen_T2P3_defU.yaml",  True),   # + trunk pressure/pumping
    "L6":   (f"{OUT}/T2P6_defU",  f"{CFG}/Memmingen_T2P6_defU.yaml",  True),   # + transport delay
    # L2 (T2P2, temperature propagation) is DELIBERATELY EXCLUDED from the solved regret table:
    # its MILP is non-convex/degenerate -- the optimiser floors T_supply at ~56 C for 91 % of hours,
    # collapsing losses and giving a spurious -7.2 % (6x the forward-evaluated -2 % of loss). Per
    # §2.4/§4.7 temperature propagation is FORWARD-EVALUATED, not solved; see tab_linearisation.
}
REF = "L1"
REFCFG = f"{CFG}/Memmingen_T2P1_defU.yaml"

# #4 shortfall-pricing anchors (EUR/MWh_th): marginal, peak, unmet-penalty
PRICING = {"marginal_gas+CO2": 72.2, "peak_EK": 90.0, "unmet_penalty_dump": 1000.0}


def main():
    refcfg = E._load_yaml(REFCFG)
    base_cost = E.cost_params_from_config(refcfg)
    ref_run = E.load_run(LEVELS[REF][0])
    net = E.network_from_run(ref_run, refcfg)          # forward network built ONCE from L1

    # --- main table: bias + regret + violations at the default marginal (gas+CO2) -----
    cost0 = dataclasses.replace(base_cost, marginal_heat_cost_eur_mwh=72.2)
    res, econ, zev = {}, {}, {}
    for lv, (rd, _cf, ml) in LEVELS.items():
        r = E.load_run(rd)
        res[lv] = E.evaluate(r, net, cost0, physics="full", models_loss=ml)
        econ[lv] = res[lv].diagnostics["econ_cost_eur"]
        zev[lv] = res[lv].total_cost
    rows = []
    for lv in LEVELS:
        v = res[lv].violations
        rows.append({
            "level": lv, "z_econ": econ[lv], "z_eval": zev[lv],
            "bias_abs": econ[lv] - econ[REF],
            "bias_pct": 100.0 * (econ[lv] - econ[REF]) / econ[REF],
            "regret_abs": zev[lv] - zev[REF],
            "regret_pct": 100.0 * (zev[lv] - zev[REF]) / zev[REF],
            "true_loss_mwh": res[lv].true_loss_mwh,
            "extra_loss_mwh": res[lv].cost_components["extra_loss_mwh"],
            "pump_mwh": res[lv].pump_energy_mwh,
            "viol_velocity": v["velocity"]["n_steps"],
            "viol_dp": v["dp_consumer"]["n_steps"],
            "viol_unmet": v["unmet_demand"]["n_steps"],
        })
    df = pd.DataFrame(rows)
    os.makedirs("results/v2/analysis", exist_ok=True)
    df.to_csv("results/v2/analysis/regret_decomp.csv", index=False)

    # --- #4 shortfall-pricing sensitivity: regret sign across the three schemes -------
    prows = []
    for label, m in PRICING.items():
        cost = dataclasses.replace(base_cost, marginal_heat_cost_eur_mwh=m)
        zz = {}
        for lv, (rd, _cf, ml) in LEVELS.items():
            r = E.load_run(rd)
            zz[lv] = E.evaluate(r, net, cost, physics="full", models_loss=ml).total_cost
        for lv in LEVELS:
            prows.append({"pricing": label, "marginal_eur_mwh": m, "level": lv,
                          "regret_pct": 100.0 * (zz[lv] - zz[REF]) / zz[REF]})
    pdf = pd.DataFrame(prows)
    pdf.to_csv("results/v2/analysis/regret_decomp_pricing.csv", index=False)

    # --- review R2.3 recourse table: quantify the shortfall the loss-blind schedule
    # leaves for price-based recourse, and confirm hydraulic feasibility after it.
    # Per-hour extra loss = forward loss - the level's per-step provisioned loss (0 for
    # the copperplates). Pure post-processing of the already-evaluated schedules. -------
    import numpy as np
    rrows = []
    for lv in LEVELS:
        d = res[lv].diagnostics
        ls = np.asarray(d["loss_series_mwh"], dtype=float)
        provisioned = d["loss_assumed_per_step_mwh"]        # 0.0 for CP/ND0
        per_hour_shortfall = np.maximum(ls - provisioned, 0.0)
        v = res[lv].violations
        rrows.append({
            "level": lv,
            "annual_shortfall_mwh": round(float(per_hour_shortfall.sum()), 1),
            "hours_with_shortfall": int((per_hour_shortfall > 1e-6).sum()),
            "max_hourly_shortfall_mw": round(float(per_hour_shortfall.max()), 4),
            "mean_hourly_shortfall_mw": round(float(per_hour_shortfall.mean()), 4),
            "unserved_before_recourse_mwh": round(float(per_hour_shortfall.sum()), 1),
            "viol_velocity_h_after": v["velocity"]["n_steps"],
            "viol_dp_h_after": v["dp_consumer"]["n_steps"],
            "viol_unmet_h_after": v["unmet_demand"]["n_steps"],
        })
    rdf = pd.DataFrame(rrows)
    rdf.to_csv("results/v2/analysis/regret_recourse.csv", index=False)

    pd.set_option("display.width", 200, "display.float_format", lambda x: f"{x:,.2f}")
    print("=== regret_decomp (ref = L1, defensible-U, marginal=72.2) ===")
    print(df[["level", "bias_pct", "regret_pct", "true_loss_mwh", "extra_loss_mwh",
              "viol_velocity", "viol_dp", "viol_unmet"]].to_string(index=False))
    print("\n=== #4 shortfall-pricing: copperplate (CP) regret sign invariance ===")
    piv = pdf.pivot(index="level", columns="pricing", values="regret_pct")
    print(piv.to_string())
    print("\n=== R2.3 recourse table (shortfall + post-recourse feasibility) ===")
    print(rdf.to_string(index=False))
    print("\nwrote regret_decomp.csv + regret_decomp_pricing.csv + regret_recourse.csv")


if __name__ == "__main__":
    main()
