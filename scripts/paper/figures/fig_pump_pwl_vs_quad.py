"""F6 — Scatter: pump power PWL (L3+) vs quadratic (L3^NL)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scripts.paper.figures.fig_utils import apply_style, save_fig, LEVEL_COLORS

RUNS = ROOT / "output" / "paper_runs"


def _load_pipe_state(run_id: str) -> pd.DataFrame | None:
    p = RUNS / run_id / "pipe_state_hourly.parquet"
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception:
        return None


def _load_pump_from_dispatch(run_id: str) -> pd.Series | None:
    p = RUNS / run_id / "dispatch_hourly.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    col = next((c for c in df.columns if "pump" in c.lower()), None)
    return df[col] if col else None


def main() -> None:
    apply_style()

    p_l3p  = _load_pump_from_dispatch("L3plus")
    p_l3nl = _load_pump_from_dispatch("L3NL")
    placeholder = p_l3p is None or p_l3nl is None

    if placeholder:
        rng = np.random.default_rng(7)
        flow = np.clip(rng.normal(100, 40, 500), 5, 250)
        p_l3p_vals  = 0.003 * flow ** 1.05 + rng.normal(0, 0.5, 500)
        p_l3nl_vals = 0.0028 * flow ** 2.1 / flow + rng.normal(0, 0.4, 500)
    else:
        shared_idx = p_l3p.index.intersection(p_l3nl.index)
        p_l3p_vals  = p_l3p.loc[shared_idx].values
        p_l3nl_vals = p_l3nl.loc[shared_idx].values

    fig, ax = plt.subplots(figsize=(5.0, 4.5))
    ax.scatter(p_l3p_vals, p_l3nl_vals, s=8, alpha=0.4,
               color="#888888", edgecolors="none")

    lim_min = min(p_l3p_vals.min(), p_l3nl_vals.min())
    lim_max = max(p_l3p_vals.max(), p_l3nl_vals.max())
    ax.plot([lim_min, lim_max], [lim_min, lim_max],
            color="black", lw=0.8, linestyle="--", label="y = x")

    ax.set_xlabel(r"Pump power L3$^+$ (PWL) [MW]")
    ax.set_ylabel(r"Pump power L3$^\mathrm{NL}$ (quadratic) [MW]")
    ax.set_title(r"Pump power: L3$^+$ PWL vs L3$^\mathrm{NL}$ quadratic")
    ax.legend(fontsize=7)

    if placeholder:
        ax.text(0.05, 0.95, "[PLACEHOLDER — Gurobi data needed]",
                transform=ax.transAxes, fontsize=7, color="gray",
                style="italic", va="top")

    rows = [{"p_l3plus_MW": float(a), "p_l3nl_MW": float(b)}
            for a, b in zip(p_l3p_vals, p_l3nl_vals)]
    out = RUNS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "fig_pump_pwl_vs_quad.csv", index=False)

    save_fig(fig, "fig_pump_pwl_vs_quad")


if __name__ == "__main__":
    main()
