"""
Build the T0P1 (copperplate + aggregate losses) demand data for Paper 1 (R2.2).

T0P1 is the copperplate (L1) with demand inflated by the aggregate network loss L(t),
so it stays a pure LP (no model change). Two calibrations are produced as new demand
columns added to a copy of the Memmingen input workbook:

  T0P1a  constant adder   L_a = E_loss_annual(T2P1)/8760       [flat MW every hour]
  T0P1b  heating-curve    L_b(t) = ΣU_s·L·(T_sup(t)-T_gr) + ΣU_r·L·(T_ret(t)-T_gr)
                          using the seasonal temperature frame (month -> T_sup/T_ret)

(T0P1c, measurement-calibrated = annual generated - delivered from the monitoring
record, needs the measured loss figure and is added separately.)

Reads/writes the c19d690 worktree so Paper 2 (main) is untouched.
"""
import os

import pandas as pd
import yaml

WT = r"c:/Users/LKR/Documents/GitHub/Energy_Framwork/paper1_faithful_c19d690"
CFG = os.path.join(WT, "configs/memmingen/Memmingen_T2P1_defU.yaml")  # defensible-U
SRC = os.path.join(WT, "data/Import_Data_Memmingen_epronet.xlsx")
DST = os.path.join(WT, "data/Import_Data_Memmingen_epronet_T0P1.xlsx")
DEMAND_COL = "Waermebedarf_MWth"
E_LOSS_ANNUAL_T2P1 = 1185.1   # MWh, defensible-U T2P1 exported total network loss


def main():
    cfg = yaml.safe_load(open(CFG, encoding="utf-8"))
    net = cfg["network"]
    T_gr = float(net.get("ground_temp_c", 10.0))
    pipes = net["pipes"]
    sumUsL = sum(p["u_value_supply_w_per_m_k"] * p["length_m"] for p in pipes.values())
    sumUrL = sum(p["u_value_return_w_per_m_k"] * p["length_m"] for p in pipes.values())
    print(f"sumUsL={sumUsL:,.0f} W/K  sumUrL={sumUrL:,.0f} W/K")

    seasons = net["temperature_frame"]["seasons"]
    m2t = {}
    for _, v in seasons.items():
        for m in v["months"]:
            m2t[m] = (float(v["supply_c"]), float(v["return_c"]))

    print("reading source workbook (96 MB) ...")
    x = pd.read_excel(SRC)
    print(f"  shape {x.shape}")
    dt = pd.to_datetime(x["Datum"])
    mon = dt.dt.month
    Tsup = mon.map(lambda m: m2t[m][0])
    Tret = mon.map(lambda m: m2t[m][1])

    L_a = E_LOSS_ANNUAL_T2P1 / 8760.0                      # MW, flat
    L_b = (sumUsL * (Tsup - T_gr) + sumUrL * (Tret - T_gr)) / 1.0e6  # MW per row

    x["Waermebedarf_MWth_T0P1a"] = x[DEMAND_COL] + L_a
    x["Waermebedarf_MWth_T0P1b"] = x[DEMAND_COL] + L_b

    # validate annual added loss on the 2025 horizon at hourly resolution
    xh = x.set_index(dt).loc["2025-01-01":"2025-12-31"].resample("1h").mean(numeric_only=True)
    ann_a = (xh["Waermebedarf_MWth_T0P1a"] - xh[DEMAND_COL]).sum()
    ann_b = (xh["Waermebedarf_MWth_T0P1b"] - xh[DEMAND_COL]).sum()
    print(f"annual added loss (hourly-resampled 2025): a={ann_a:,.1f} MWh  b={ann_b:,.1f} MWh")
    print(f"target (T2P1) = {E_LOSS_ANNUAL_T2P1:,.1f} MWh  ->  a err {100*(ann_a-E_LOSS_ANNUAL_T2P1)/E_LOSS_ANNUAL_T2P1:+.2f}%  b err {100*(ann_b-E_LOSS_ANNUAL_T2P1)/E_LOSS_ANNUAL_T2P1:+.2f}%")

    print(f"writing {DST} ...")
    x.to_excel(DST, index=False)
    print("DONE")


if __name__ == "__main__":
    main()
