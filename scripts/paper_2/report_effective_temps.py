"""Effective network temperatures + supply-temperature duration curve (Paper 2, T2/supplement).

Reproduces, per (network, HK stage), the EFFECTIVE T_VL,min and T_return AFTER the
VDI-6002 minimum-spread floor (min_supply_delta_T_k), the design ΔT, and how often the
floor is active. The configured T_VL,min (e.g. SB-HK0 70 °C) is raised by the floor to
75 °C, so the config value is NOT what is computed — this table is the authoritative
source for all temperatures in the paper (replaces config values).

Also emits the supply-temperature DURATION CURVE (T_VL sorted descending) for the
supplement, with the 15 K-floor level marked and the fraction of hours at the floor.

The design ΔT is NOT "confirmed by the heating curve" (circular — the floor forces the
curve there). It is the ENFORCED VDI-6002 bound; the duration curve shows the bound is
active in ~1/3 of heating hours, so the design ΔT equals the bound.

Outputs (to results/paper2_figures/):
    tab_effective_temps.csv          six-row table
    fig_tvl_duration.(png|pdf)        duration curve, both networks, HK0

Run:  PYTHONPATH=. python scripts/paper_2/report_effective_temps.py
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from calion.utils.heizkurve import compute_heizkurve

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "paper2_figures"
OUT.mkdir(parents=True, exist_ok=True)
CACHE = Path(__file__).resolve().parent / "_taus_cache"
CACHE.mkdir(exist_ok=True)

MIN_DT = 15.0  # network.min_supply_delta_T_k (VDI 6002), both configs
# Fraunhofer-ish palette
C = {"SB": "#179c7d", "MM": "#005b7f", "floor": "#a6093d"}

NET = {
    "SB": dict(name="Stadtbach", xlsx="data/Stadtbach/stadtbach_acron_combined_cleaned.xlsx",
               stages={"HK0": (1.0, 70, 122, 60.0), "HK1": (0.8, 65, 122, 50.0), "HK2": (0.6, 60, 122, 45.0)}),
    "MM": dict(name="Memmingen", xlsx="data/Import_Data_Memmingen_epronet_cleaned.xlsx",
               stages={"HK0": (1.0, 74, 100, 63.6), "HK1": (0.8, 70, 100, 55.0), "HK2": (0.6, 66, 100, 51.0)}),
}


def _load_taus(key: str, xlsx: str) -> np.ndarray:
    """Outdoor temperature series, cached (the source xlsx is slow to open)."""
    c = CACHE / f"taus_{key}.csv"
    if c.exists():
        return pd.read_csv(c)["outdoor_temp_C"].astype(float).values
    s = pd.read_excel(ROOT / xlsx, usecols=["outdoor_temp_C"])["outdoor_temp_C"].astype(float)
    s.to_csv(c, index=False)
    return s.values


def build() -> pd.DataFrame:
    rows = []
    tvl_hk0 = {}
    for key, info in NET.items():
        taus = _load_taus(key, info["xlsx"])
        rec = len(taus); yrs = rec / 8760.0
        for st, (k, tvmin, tvmax, ret) in info["stages"].items():
            eff = max(tvmin, ret + MIN_DT)
            tvl = np.maximum(compute_heizkurve(k, tvmin, tvmax, taus), eff)
            nfloor = int((tvl <= eff + 0.5).sum())
            rows.append(dict(net=key, network=info["name"], hk=st,
                             TVLmin_config=tvmin, TVLmin_effective=round(eff, 1),
                             T_return=ret, dT_design_K=round(eff - ret),
                             floor_pct_record=round(100 * nfloor / rec), floor_h_per_yr=round(nfloor / yrs)))
            if st == "HK0":
                tvl_hk0[key] = (tvl, eff, ret, yrs)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "tab_effective_temps.csv", index=False)
    return df, tvl_hk0


def duration_figure(tvl_hk0: dict) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    for key, (tvl, eff, ret, yrs) in tvl_hk0.items():
        s = np.sort(tvl)[::-1]
        x = np.linspace(0, 100, len(s))
        ax.plot(x, s, color=C[key], lw=1.8, label=f"{NET[key]['name']} HK0")
        ax.axhline(eff, color=C[key], ls=":", lw=1.0, alpha=0.7)
        frac = 100 * (tvl <= eff + 0.5).mean()
        ax.annotate(f"{NET[key]['name']} floor {eff:.0f} °C  ({frac:.0f} % of hours)",
                    xy=(2, eff), xytext=(2, eff - 6), fontsize=7, color=C[key])
    ax.set_xlabel("share of hours exceeded [%]")
    ax.set_ylabel(r"supply temperature $T_{VL}$ [°C]")
    ax.set_title("Supply-temperature duration curve (HK0) — floor active ≈ ⅓ of hours", fontsize=9)
    ax.set_xlim(0, 100); ax.grid(alpha=0.25); ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_tvl_duration.{ext}", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    df, tvl_hk0 = build()
    pd.set_option("display.width", 120)
    print(df.to_string(index=False))
    duration_figure(tvl_hk0)
    print(f"\nwrote {OUT/'tab_effective_temps.csv'}")
    print(f"wrote {OUT/'fig_tvl_duration.png'} (+ .pdf)")
