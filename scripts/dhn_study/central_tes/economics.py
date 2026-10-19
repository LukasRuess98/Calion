"""Break-even investment table (spec 8, post-processing; no CAPEX in the operating MILP except the expansion boiler).

Max. justifiable investment I_max = annual operational value / annuity factor(i, n). Compared with literature-based
investment (config `economics`, `heat_pump.capex_eur_per_MW`, `new_boiler.capex_eur_per_MW`).

    python -m scripts.dhn_study.central_tes.economics
"""

from __future__ import annotations

import json

import pandas as pd

from . import config as C
from .metrics import annuity_factor


def table(cfg: dict) -> pd.DataFrame:
    r = C.root() / cfg["paths"]["results"]
    sh = json.loads((r / "scenario_runs" / "shapley.json").read_text())["E"]
    v = sh["v"]
    ec, hp = cfg["economics"], cfg["heat_pump"]
    i = ec["discount_rate"]
    af_tes, af_hp, af_link = annuity_factor(i, ec["lifetime_tes_a"]), annuity_factor(i, hp["lifetime_a"]), annuity_factor(i, ec["lifetime_link_a"])
    V = cfg["tes"]["volume_m3"]
    tes_cost = {k: c * V + ec["tes_capex_fixed_eur"] for k, c in ec["tes_capex_eur_per_m3"].items()}
    hp_cost = hp["capex_eur_per_MW"] * hp["Q_max_MW"]
    link_cost = ec["link_capex_eur_per_m"] * ec["link_length_m"]
    rows = []
    for name, val in {"TES alone (F001 − F000)": v["F001"], "TES with A+B (F111 − F110)": sh["storage_value"]["F111-F110"],
                      "TES Shapley": sh["phi"]["TES"]}.items():
        rows.append({"asset": "TES 5 000 m³", "value basis": name, "value_kEUR_a": val / 1e3, "lifetime_a": ec["lifetime_tes_a"],
                     "I_max_MEUR": val / af_tes / 1e6, "I_lit_low_MEUR": tes_cost["low"] / 1e6, "I_lit_ref_MEUR": tes_cost["ref"] / 1e6,
                     "I_lit_high_MEUR": tes_cost["high"] / 1e6})
    for name, val in {"A alone (F100 − F000)": v["F100"], "A Shapley": sh["phi"]["A"]}.items():
        rows.append({"asset": "HP 5 MW (partner A)", "value basis": name, "value_kEUR_a": val / 1e3, "lifetime_a": hp["lifetime_a"],
                     "I_max_MEUR": val / af_hp / 1e6, "I_lit_ref_MEUR": hp_cost / 1e6})
    rows.append({"asset": "connection pipe", "value basis": "needed for any central asset", "value_kEUR_a": v["F111"] / 1e3,
                 "lifetime_a": ec["lifetime_link_a"], "I_max_MEUR": v["F111"] / af_link / 1e6, "I_lit_ref_MEUR": link_cost / 1e6})
    rows.append({"asset": "whole concept (TES + HP + link)", "value basis": "F111 − F000", "value_kEUR_a": v["F111"] / 1e3,
                 "lifetime_a": None, "I_max_MEUR": None,
                 "annual_capital_cost_kEUR_a": (tes_cost["ref"] * af_tes + hp_cost * af_hp + link_cost * af_link) / 1e3})
    return pd.DataFrame(rows)


def tes_sizes(cfg: dict) -> pd.DataFrame:
    """Break-even specific investment [EUR/m³] per TES size and power (A1), value relative to F110 (Mode E, PF)."""
    r = C.root() / cfg["paths"]["results"]
    a1 = pd.read_csv(r / "sensitivities" / "A1" / "summary.csv")
    ref = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario").at["F110", "C_E"]
    a1 = a1[a1["case"] != "V0"].copy()
    a1["V_m3"] = a1["case"].str.extract(r"V(\d+)_").astype(float)
    a1["Q_MW"] = a1["case"].str.extract(r"_Q(\d+)").astype(float)
    af = annuity_factor(cfg["economics"]["discount_rate"], cfg["economics"]["lifetime_tes_a"])
    a1["value_kEUR_a"] = (ref - a1["C_E"]) / 1e3
    a1["I_max_MEUR"] = a1["value_kEUR_a"] * 1e3 / af / 1e6
    a1["break_even_EUR_per_m3"] = (a1["I_max_MEUR"] * 1e6 - cfg["economics"]["tes_capex_fixed_eur"]) / a1["V_m3"]
    return a1[["V_m3", "Q_MW", "tau_h", "value_kEUR_a", "I_max_MEUR", "break_even_EUR_per_m3"]].sort_values(["V_m3", "Q_MW"])


def main():
    cfg = C.load()
    try:
        ts = tes_sizes(cfg)
        ts.to_csv(C.root() / cfg["paths"]["results"] / "economics_tes_sizes.csv", index=False)
        print(ts.round(1).to_string(index=False))
    except FileNotFoundError:
        pass
    t = table(cfg)
    out = C.root() / cfg["paths"]["results"] / "economics_break_even.csv"
    t.to_csv(out, index=False)
    pd.set_option("display.width", 220)
    print(t.round(2).to_string())


if __name__ == "__main__":
    main()
