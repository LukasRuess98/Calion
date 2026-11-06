"""v12 A1: hourly system balance R(t) computed from the MODEL variables of a full_solution_dump.json.

R(t) = sum generation - demand - sum pipe losses (supply+return) - sum dump - (TES charge - discharge)
Sign: R < 0 means demand/losses were covered without generation (phantom heat).
Model time index is 1-based ('1'..'8760'); dispatch_hourly.csv rows are 0-based -> demand row i = model t = i+1.
Demand is taken from dispatch_hourly.csv `Q_demand_total_MW` (= the model's own heat_demand series, extract_artefacts.py).
usage: python a1_balance_from_dump.py <run_dir> [--json out.json]
"""
import json, sys
import numpy as np, pandas as pd

GEN_SUFFIX = ("_Qth",)
GEN_EXTRA = ("hp_sb_Q", "hp_main_Q")


def series(v, name, T):
    d = v.get(name)
    a = np.zeros(T)
    if isinstance(d, dict):
        for k, x in d.items():
            a[int(k) - 1] = float(x or 0.0)
    return a


def balance(run_dir):
    dump = json.load(open(f"{run_dir}/full_solution_dump.json"))["vars"]
    disp = pd.read_csv(f"{run_dir}/dispatch_hourly.csv")
    T = len(disp)
    gen_names = [k for k in dump if k.endswith(GEN_SUFFIX) and isinstance(dump[k], dict)] + \
                [k for k in GEN_EXTRA if k in dump]
    gen = sum(series(dump, k, T) for k in gen_names)
    loss_s = sum(series(dump, k, T) for k in dump if k.endswith("_Q_loss_supply"))
    loss_r = sum(series(dump, k, T) for k in dump if k.endswith("_Q_loss_return"))
    dumpq = sum(series(dump, k, T) for k in dump if k.startswith("Q_dump_"))
    tes_c = sum(series(dump, k, T) for k in dump if k.endswith("_Qc"))
    tes_d = sum(series(dump, k, T) for k in dump if k.endswith("_Qd"))
    slack = sum(series(dump, k, T) for k in dump if k.endswith("_Q_demand_slack"))
    dem = disp["Q_demand_total_MW"].to_numpy()
    R = gen - dem + slack - loss_s - loss_r - dumpq - (tes_c - tes_d)
    out = dict(gen_MWh=gen.sum(), demand_MWh=dem.sum(), demand_slack_MWh=float(np.sum(slack)),
               loss_supply_MWh=loss_s.sum(), loss_return_MWh=loss_r.sum(),
               export_loss_MWh=float(disp["Q_loss_total_MW"].sum()), dump_MWh=float(np.sum(dumpq)),
               tes_net_MWh=float(np.sum(tes_c - tes_d)), R_sum_MWh=R.sum(), R_min_MW=R.min(), R_max_MW=R.max(),
               R_p50_MW=float(np.median(R)), hours_R_neg_005=int((R < -0.05).sum()),
               hours_absR_gt_001=int((np.abs(R) > 0.01).sum()), peak_demand_MW=dem.max(), gen_assets=gen_names)
    return out, R


if __name__ == "__main__":
    o, R = balance(sys.argv[1])
    for k, x in o.items():
        print(f"{k:22s} {x if isinstance(x, list) else round(float(x), 4)}")
    if "--json" in sys.argv:
        json.dump({k: (x if isinstance(x, list) else float(x)) for k, x in o.items()},
                  open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
