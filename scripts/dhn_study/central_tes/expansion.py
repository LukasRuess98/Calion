"""Summary and figure of the south-expansion study (sensitivity sets X and X4).

    python -m scripts.dhn_study.central_tes.expansion
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import config as C  # noqa: E402
from .figures import INK2, SLOTS  # noqa: E402
from .metrics import annuity_factor  # noqa: E402


def summary(cfg: dict, sid: str = "X") -> pd.DataFrame:
    r = C.root() / cfg["paths"]["results"] / "sensitivities" / sid / "summary.csv"
    d = pd.read_csv(r)
    d["level"] = d["case"].str.extract(r"L(\d+)").astype(int)
    d["tes_node"] = np.where(d["case"].str.contains("south"), "south end", np.where(d["scenario"].str[-1] == "1", "S", "-"))
    d["variant"] = d["scenario"] + np.where(d["tes_node"] == "south end", " (TES south)", "")
    keep = ["level", "variant", "C_E", "C_H", "dC_hyd", "C_new_MW_E", "C_new_MW_H", "NEW_heat_GWh_H", "viol_E", "attr_E",
            "dpKWK_p95_E", "dpKWK_p95_H", "soft_KWK_h_E", "TES_dis_GWh", "TES_ext_GWh", "conv_H", "iter_H"]
    return d[[k for k in keep if k in d]].sort_values(["level", "variant"])


def tes_values(s: pd.DataFrame) -> pd.DataFrame:
    """TES value per expansion level and location, Mode E and H, relative to F110 (A+B without TES)."""
    rows = []
    for L, g in s.groupby("level"):
        g = g.set_index("variant")
        if "F110" not in g.index:
            continue
        for v in ("F111", "F111 (TES south)"):
            if v in g.index:
                rows.append({"level": L, "TES": "S" if v == "F111" else "south end",
                             "V_TES_E_kEUR": (g.at["F110", "C_E"] - g.at[v, "C_E"]) / 1e3,
                             "V_TES_H_kEUR": (g.at["F110", "C_H"] - g.at[v, "C_H"]) / 1e3,
                             "new_boiler_MW_H": g.at[v, "C_new_MW_H"], "new_boiler_MW_H_noTES": g.at["F110", "C_new_MW_H"],
                             "dC_hyd_kEUR": g.at[v, "dC_hyd"] / 1e3, "dC_hyd_noTES_kEUR": g.at["F110", "dC_hyd"] / 1e3})
    return pd.DataFrame(rows)


def _level0(cfg: dict) -> pd.DataFrame:
    """Today's load (0 %) from the reference factorial (no new boiler), for the figure."""
    r = C.root() / cfg["paths"]["results"] / "scenario_runs"
    f = pd.read_csv(r / "factorial_summary.csv").set_index("scenario")
    import json
    rows = []
    for v in ("F000", "F110", "F111"):
        h = json.loads((r / f"{v}-H" / "A" / "annual_metrics.json").read_text())["hydraulics"]
        rows.append({"level": 0, "variant": v, "C_new_MW_H": 0.0, "dC_hyd": f.at[v, "dC_hyd_A"],
                     "dpKWK_p95_H": h["dp_KWK_required"]["p95"]})
    return pd.DataFrame(rows)


def figure(cfg: dict, s: pd.DataFrame, out, s4: pd.DataFrame | None = None):
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    try:
        s = pd.concat([_level0(cfg), s], ignore_index=True)
    except (FileNotFoundError, KeyError):
        pass
    cols = {"F000": SLOTS[0], "F110": SLOTS[1], "F111": SLOTS[2], "F001 (TES south)": SLOTS[3], "F111 (TES south)": SLOTS[4]}
    for v, c in cols.items():
        g = s[s["variant"] == v].sort_values("level")
        if g.empty:
            continue
        ax[0].plot(g["level"], g["C_new_MW_H"], marker="o", color=c, label=v)
        ax[1].plot(g["level"], g["dC_hyd"] / 1e3, marker="o", color=c, label=v)
        ax[2].plot(g["level"], g["dpKWK_p95_H"], marker="o", color=c, label=v)
    if s4 is not None:
        for v in ("F000", "F110", "F111"):
            g = s4[s4["variant"] == v].sort_values("level")
            if g.empty:
                continue
            lab = f"{v}, KWK ≤ 4 bar"
            ax[0].plot(g["level"], g["C_new_MW_H"], marker="s", ls="none", ms=7, color=cols[v], mfc="white", label=lab)
            ax[1].plot(g["level"], g["dC_hyd"] / 1e3, marker="s", ls="none", ms=7, color=cols[v], mfc="white", label=lab)
            ax[2].plot(g["level"], g["dpKWK_p95_H"], marker="s", ls="none", ms=7, color=cols[v], mfc="white", label=lab)
    ax[0].set(xlabel="additional demand in the south [% of today's total]", ylabel="new south boiler, Mode H [MW]")
    ax[1].set(xlabel="additional demand [%]", ylabel="ΔC_hyd = C_H − C_E [kEUR/a]")
    ax[2].axhline(4.0, color=INK2, ls=":", lw=1)
    ax[2].set(xlabel="additional demand [%]", ylabel="required KWK Δp P95, Mode H [bar]")
    for a in ax:
        a.set_xticks([0, 10, 20, 30])
    ax[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "fig8_south_expansion.png")
    plt.close(fig)


def main():
    cfg = C.load()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    out = C.root() / cfg["paths"]["results"] / "figures"
    out.mkdir(parents=True, exist_ok=True)
    res = {}
    for sid in ("X", "X4"):
        p = C.root() / cfg["paths"]["results"] / "sensitivities" / sid / "summary.csv"
        if not p.exists():
            continue
        s = summary(cfg, sid)
        t = tes_values(s)
        s.to_csv(p.parent / "expansion_summary.csv", index=False)
        t.to_csv(p.parent / "expansion_tes_values.csv", index=False)
        res[sid] = s
        print(sid)
        print(s.round(2).to_string(index=False))
        print(t.round(1).to_string(index=False))
    if "X" in res:
        figure(cfg, res["X"], out, res.get("X4"))
    nb = cfg["new_boiler"]
    print("annualised boiler cost [EUR/MW/a]:", round(nb["capex_eur_per_MW"] * annuity_factor(cfg["economics"]["discount_rate"], nb["lifetime_a"]) + nb["om_fix_eur_per_MW_a"]))


if __name__ == "__main__":
    main()
