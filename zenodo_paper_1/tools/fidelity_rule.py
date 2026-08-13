"""
Fidelity design rule (Paper 1, advancement #1). First-principles, a-priori criterion for the
copperplate-to-baseline cost gap (the loss burden a copperplate misses).

Derivation: a copperplate generates the demand; the node-resolved model additionally generates
the network loss. If cost scales with heat produced, the burden b = loss_cost/total_cost obeys
    b = lambda / (1 + lambda),   lambda = annual_loss / annual_demand,
where lambda -- a dimensionless "loss number" -- is computable a priori from the network:
    annual_loss [MWh] = (sum_p U^s_p L_p (T_sup - T_g) + sum_p U^r_p L_p (T_ret - T_g)) * 8760 / 1e6.

We validate b = lambda/(1+lambda) against the measured burden (total_pct) on the 42 synthetic
networks and Memmingen. If it holds, it is a design rule: compute lambda from your network, read
off the burden, and decide whether a copperplate (small b), a loss adder, or a node-resolved
model (large b) is required -- without solving anything.

Output: results/v2/analysis/fidelity_rule.csv + console fit + nomogram data.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import evaluator as E  # noqa: E402  (reuse its yaml loader)

WT = Path("../paper1_faithful_c19d690")
SYNTH_CFG = WT / "synth_configs"
SYNTH_OUT = WT / "output/paper1_v2/synth_decomp"
A = "results/v2/analysis"
HOURS = 8760.0


def loss_number(cfg, demand_mwh):
    net = cfg["network"]
    tg = float(net.get("ground_temp_c", 10.0))
    # temperatures: use the seasonal/nominal supply & return
    tsup = float(net.get("supply_temp_c", 90.0))
    tret = float(net.get("return_temp_c", 50.0))
    pipes = net["pipes"]
    sUsL = sum(float(p.get("u_value_supply_w_per_m_k", 0)) * float(p["length_m"]) for p in pipes.values())
    sUrL = sum(float(p.get("u_value_return_w_per_m_k", 0)) * float(p["length_m"]) for p in pipes.values())
    loss_mwh = (sUsL * (tsup - tg) + sUrL * (tret - tg)) * HOURS / 1.0e6
    return loss_mwh / demand_mwh if demand_mwh else np.nan, loss_mwh


def demand_of(run_dir):
    d = pd.read_csv(run_dir / "dispatch_hourly.csv")
    return float(d["Q_demand_total_MW"].sum())


def main():
    meas = pd.read_csv(f"{A}/synth_factorial_decomposition.csv")
    rows = []
    for net in meas["net"]:
        cfgp = SYNTH_CFG / f"{net}.yaml"
        rundir = SYNTH_OUT / f"{net}_T2P1"
        if not cfgp.exists() or not (rundir / "dispatch_hourly.csv").exists():
            continue
        cfg = E._load_yaml(cfgp)
        dem = demand_of(rundir)
        lam, loss = loss_number(cfg, dem)
        b_pred = 100 * lam / (1 + lam)
        b_meas = float(meas.loc[meas.net == net, "total_pct"].iloc[0])
        rows.append({"net": net, "lambda": lam, "loss_mwh": loss, "demand_mwh": dem,
                     "b_pred_pct": b_pred, "b_meas_pct": b_meas})
    df = pd.DataFrame(rows)

    # Memmingen point (defensible-U L1)
    try:
        mcfg = E._load_yaml(WT / "configs/memmingen/Memmingen_T2P1_defU.yaml")
        mdem = demand_of(WT / "output/paper1_v2/T2P1_defU")
        mlam, mloss = loss_number(mcfg, mdem)
        mb_pred = 100 * mlam / (1 + mlam)
        mb_meas = 15.12  # decomposition_live total as % of L1
        df = pd.concat([df, pd.DataFrame([{"net": "Memmingen", "lambda": mlam, "loss_mwh": mloss,
                        "demand_mwh": mdem, "b_pred_pct": mb_pred, "b_meas_pct": mb_meas}])],
                       ignore_index=True)
    except Exception as exc:  # noqa: BLE001
        print("Memmingen point skipped:", exc)

    os.makedirs(A, exist_ok=True)
    df.to_csv(f"{A}/fidelity_rule.csv", index=False)

    v = df.dropna(subset=["b_pred_pct", "b_meas_pct"])
    err = v["b_pred_pct"] - v["b_meas_pct"]
    ss = ((v["b_meas_pct"] - v["b_meas_pct"].mean()) ** 2).sum()
    r2 = 1 - (err ** 2).sum() / ss if ss else np.nan
    mae = float(err.abs().mean())
    # calibrated form b = a * [lambda/(1+lambda)] + c_topo (c_topo absorbs the ~const topology term)
    x = (v["lambda"] / (1 + v["lambda"])).to_numpy()
    Amat = np.column_stack([x, np.ones(len(x))])
    (a, c), *_ = np.linalg.lstsq(Amat, v["b_meas_pct"].to_numpy(), rcond=None)
    fit = Amat @ np.array([a, c])
    r2c = 1 - ((v["b_meas_pct"] - fit) ** 2).sum() / ss if ss else np.nan
    df["b_cal_pct"] = a * (df["lambda"] / (1 + df["lambda"])) + c
    df.to_csv(f"{A}/fidelity_rule.csv", index=False)
    print(f"n={len(v)}  b = lambda/(1+lambda) vs measured burden:")
    print(f"  zero-parameter (pure physics):  R2 = {r2:.3f}   MAE = {mae:.1f} pts")
    print(f"  calibrated b = {a:.2f}*L/(1+L) + {c:.1f}:  R2 = {r2c:.3f}  (c={c:.1f} ~ topology term)")
    print(f"  lambda range: {v['lambda'].min():.3f}--{v['lambda'].max():.3f}")
    m = df[df.net == "Memmingen"]
    if len(m):
        print(f"  Memmingen: lambda={m['lambda'].iloc[0]:.3f}  b_pred={m['b_pred_pct'].iloc[0]:.1f}%  b_meas={m['b_meas_pct'].iloc[0]:.1f}%")
    print("wrote fidelity_rule.csv")


if __name__ == "__main__":
    main()
