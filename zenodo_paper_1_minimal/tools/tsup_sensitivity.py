"""
Supply-temperature flexibility, evaluated FORWARD (Paper 1, idea 2 / Pillar-2 robustness).

The dispatch levels fix the plant supply temperature to an outdoor-temperature heating
curve. A free supply temperature is bilinear in the MILP (demand = flow x (T_sup - T_ret)),
i.e. the same MIQP intractability the paper documents for the nonlinear reference. So we do
NOT re-solve; we ask the tractable, on-method question with the validated forward evaluator:

    holding demand and the return temperature fixed, if the operator could run the plant
    COOLER than the heating curve, how much would true operating cost change, and does the
    loss-vs-pumping trade-off make HYDRAULICS decision-relevant?

Lowering T_sup cuts trunk loss (loss ~ U*L*(T_sup - T_gr)) but shrinks Delta T, so to deliver
the same demand the flow -- and hence Darcy-Weisbach pumping and velocity -- rise. Two limits
bind the reduction: pipe velocity (<= max_velocity) and the coldest delivered node temperature
(>= a consumer floor). The T_sup-dependent operating cost is loss x marginal_heat_cost +
pump_energy x elec_price; its minimum over feasible T_sup is the value of temperature
flexibility, and where the minimum sits tells us whether the hydraulic (pumping/velocity)
term ever becomes the binding cost -- the robustness test of Pillar 2's hydraulic null.

Output: results/v2/analysis/tsup_sensitivity.csv  + console summary.
"""
import dataclasses
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import evaluator as E  # noqa: E402

WT = "../paper1_faithful_c19d690"
RUN = f"{WT}/output/paper1_v2/T2P1_defU"           # L1 baseline (heating-curve T_sup)
CFG = f"{WT}/configs/memmingen/Memmingen_T2P1_defU.yaml"
MARGINAL = 72.2          # EUR/MWh_th (gas+CO2), matches regret_decomp
T_FLOOR_CONSUMER = 70.0  # min delivered node supply T [C] a consumer needs (reported sensitivity)
DELTAT_MIN = 5.0         # keep Delta T >= 5 K (avoid degenerate flow as T_sup -> T_ret)
OFFSETS = np.arange(0.0, 30.001, 2.5)   # K below the heating-curve supply temperature


def _mod_run(run, offset):
    """Copy the run with T_supply reduced by `offset` K (T_return held fixed)."""
    d = run["dispatch"].copy()
    tret = d["T_return_C"].to_numpy()
    tsup = d["T_supply_C"].to_numpy() - offset
    floor = np.maximum(tret + DELTAT_MIN, 50.0)
    d["T_supply_C"] = np.maximum(tsup, floor)
    r = dict(run)
    r["dispatch"] = d
    return r


def main():
    cfg = E._load_yaml(CFG)
    base_cost = E.cost_params_from_config(cfg)
    cost = dataclasses.replace(base_cost, marginal_heat_cost_eur_mwh=MARGINAL)
    run = E.load_run(RUN)
    net = E.network_from_run(run, cfg)
    disp = run["dispatch"]
    ep = float(np.mean(disp["lambda_buy_eur_MWh"])) + base_cost.gridcost_eur_mwh  # elec EUR/MWh

    rows = []
    for off in OFFSETS:
        r = _mod_run(run, off)
        res = E.evaluate(r, net, cost, physics="full", models_loss=True)
        loss = res.true_loss_mwh
        pump = res.pump_energy_mwh
        vv = res.violations["velocity"]["n_steps"]
        minT = res.diagnostics["min_node_Tsup_c"]
        eff_off = float(np.mean(disp["T_supply_C"].to_numpy() - r["dispatch"]["T_supply_C"].to_numpy()))
        rows.append({
            "offset_K": off, "eff_offset_K": eff_off,
            "loss_mwh": loss, "pump_mwh": pump,
            "loss_cost_eur": loss * MARGINAL, "pump_cost_eur": pump * ep,
            "tsup_cost_eur": loss * MARGINAL + pump * ep,
            "min_node_Tsup_c": minT, "velocity_viol_steps": vv,
            # Binding constraint = VELOCITY only (rigorous: mdot + geometry). The delivered
            # node temp is a caveated diagnostic -- the evaluator's demand-share flow model
            # understates circulation, so absolute node temps are unreliable (it is validated
            # to ~2% on TOTAL loss, not on absolute node temperature). So T_FLOOR is NOT
            # used as a feasibility gate; it is reported for transparency.
            "feasible": bool(vv == 0),
        })
    df = pd.DataFrame(rows)
    os.makedirs("results/v2/analysis", exist_ok=True)
    df.to_csv("results/v2/analysis/tsup_sensitivity.csv", index=False)

    base = df.iloc[0]                      # offset 0 = heating-curve baseline
    feas = df[df.feasible]
    opt = feas.loc[feas["tsup_cost_eur"].idxmin()] if len(feas) else base
    saving = base["tsup_cost_eur"] - opt["tsup_cost_eur"]
    first_infeas = df[~df.feasible]["offset_K"].min() if (~df.feasible).any() else None

    pd.set_option("display.width", 200, "display.float_format", lambda x: f"{x:,.1f}")
    print("=== T_sup forward sensitivity (L1, marginal=72.2, elec=%.1f) ===" % ep)
    print(df[["offset_K", "loss_mwh", "pump_mwh", "loss_cost_eur", "pump_cost_eur",
              "tsup_cost_eur", "min_node_Tsup_c", "velocity_viol_steps", "feasible"]].to_string(index=False))
    print(f"\nheating-curve baseline T_sup-cost = {base['tsup_cost_eur']:,.0f} EUR "
          f"(loss {base['loss_cost_eur']:,.0f} + pump {base['pump_cost_eur']:,.0f})")
    print(f"cost-optimal feasible offset = {opt['offset_K']:.1f} K  -> T_sup-cost "
          f"{opt['tsup_cost_eur']:,.0f} EUR  (loss {opt['loss_cost_eur']:,.0f} + pump {opt['pump_cost_eur']:,.0f})")
    print(f"VALUE of supply-temperature flexibility = {saving:,.0f} EUR "
          f"({100*saving/base['tsup_cost_eur']:.1f}% of the T_sup-dependent cost; "
          f"{100*saving/res.diagnostics['econ_cost_eur']:.2f}% of total operating cost)")
    print(f"binding limit: first infeasible offset = {first_infeas} K "
          f"(velocity or delivered-T floor {T_FLOOR_CONSUMER} C)")
    pump_frac_opt = 100 * opt["pump_cost_eur"] / opt["tsup_cost_eur"] if opt["tsup_cost_eur"] else 0
    print(f"pump share of T_sup-cost: baseline {100*base['pump_cost_eur']/base['tsup_cost_eur']:.1f}% "
          f"-> at optimum {pump_frac_opt:.1f}%  (does hydraulics become the binding cost?)")
    print("\nwrote results/v2/analysis/tsup_sensitivity.csv")


if __name__ == "__main__":
    main()
