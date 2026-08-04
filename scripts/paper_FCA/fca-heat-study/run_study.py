"""Command-line driver for the study.

Examples
--------
    python run_study.py --smoke                       # 1 site, 1 month, ~1 min
    python run_study.py --years 2024 --resolution 1h  # screening
    python run_study.py --years 2023 2024 2025 --resolution 15min --mpc --contract-space
"""
from __future__ import annotations

import argparse
import time

from fcaheat import (CFG, add_relative_kpis, export_metadata, export_tables, load_inputs,
                     run_batch, run_contract_space, run_mpc_all_sites, run_sensitivity_oat)
from fcaheat import figures as F


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--years", nargs="+", type=int)
    p.add_argument("--months", nargs="+", type=int)
    p.add_argument("--resolution", choices=["15min", "1h"])
    p.add_argument("--sites", nargs="+")
    p.add_argument("--fcas", nargs="+")
    p.add_argument("--scenarios", nargs="+")
    p.add_argument("--tag", default="main")
    p.add_argument("--smoke", action="store_true", help="1 site, 1 month, 1 h resolution")
    p.add_argument("--mpc", action="store_true")
    p.add_argument("--contract-space", action="store_true")
    p.add_argument("--sensitivity", action="store_true")
    p.add_argument("--no-figures", action="store_true")
    a = p.parse_args()

    if a.smoke:
        CFG.update(years=[2024], months=[1], resolution="1h", sites=None)
    for k in ("years", "months", "resolution", "sites", "fcas", "scenarios"):
        if getattr(a, k):
            CFG[k] = getattr(a, k)

    t0 = time.time()
    inp = load_inputs()
    if a.smoke and CFG["sites"] is None:
        CFG["sites"] = [inp.sites["site_id"].iloc[0]]
    print(f"{len(inp.sites)} sites · {len(inp.fca)} regimes · "
          f"{CFG['resolution']} · years {CFG['years']} · months {CFG['months']}")

    kpi, ts = run_batch(inp, sites=CFG["sites"], tag=a.tag)
    kpix = add_relative_kpis(kpi)
    kpix.to_csv(CFG_OUT := (__import__("fcaheat").OUT_DIR / f"kpi_{a.tag}_extended.csv"), index=False)
    print(f"wrote {CFG_OUT}")

    if not a.no_figures:
        site0 = kpix["site"].iloc[0]
        F.fig_demand_overview(inp)
        F.fig_duration_curves(inp)
        F.fig_limit_profile(inp, site0)
        F.fig_feasibility_matrix(kpix)
        F.fig_storage_vs_regime(kpix)
        for fc in CFG["fcas"]:
            if (site0, "S4_TES_BES", fc) in ts:
                F.fig_dispatch(ts, site0, "S4_TES_BES", fc)
                break
        F.fig_grid_duration(ts, site0, inp=inp)
        F.fig_kpi_comparison(kpix)
        F.fig_cost_stack(kpix)

    if a.contract_space:
        run_contract_space(inp, sites=CFG["sites"])
    if a.sensitivity:
        s = run_sensitivity_oat(inp, site=kpix["site"].iloc[0], scenario="S4_TES_BES")
        F.fig_tornado(s, "Etes_MWh", "TES size [MWh]")
    if a.mpc:
        m = run_mpc_all_sites(inp, kpix, fca="FCA_DYNAMIC", notices=(0.25, 24.0), seeds=(0,))
        F.fig_notice_value(m)

    export_tables(kpix)
    export_metadata(inp)
    print(f"done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
