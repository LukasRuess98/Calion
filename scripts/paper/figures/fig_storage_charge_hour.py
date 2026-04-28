"""F8 — Histogram: optimal TES charge hour-of-day per level (winter week)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scripts.paper.figures.fig_utils import apply_style, save_fig, LEVEL_COLORS, LEVEL_LABELS

RUNS = ROOT / "output" / "paper_runs"
LEVELS = ["L1", "L2", "L3", "L3plus"]
WINTER_HOURS = list(range(0, 24 * 7 * 13))  # approx Jan–Mar + Nov–Dec = ~13 weeks


def _load_charge_hours(run_id: str) -> np.ndarray | None:
    p = RUNS / run_id / "dispatch_hourly.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    tes_col = next((c for c in df.columns if "tes" in c.lower() and "charge" in c.lower()), None)
    if tes_col is None:
        tes_col = next((c for c in df.columns if "storage" in c.lower()), None)
    if tes_col is None:
        return None
    charging = df[tes_col].clip(lower=0)
    winter_mask = (df.index.month <= 3) | (df.index.month >= 11)
    charge_winter = charging[winter_mask]
    hours = charge_winter[charge_winter > 0.1].index.hour
    return hours.values if len(hours) > 0 else None


def _placeholder_hours(run_id: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # Simulate off-peak charging pattern (night + midday solar dip)
    probs = np.ones(24) * 0.02
    probs[1:7]  += 0.15   # night valley
    probs[11:15] += 0.08  # midday
    probs /= probs.sum()
    n = {"L1": 200, "L2": 220, "L3": 240, "L3plus": 260}.get(run_id, 200)
    return rng.choice(24, size=n, p=probs)


def main() -> None:
    apply_style()
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 5.5), sharex=True, sharey=False)
    axes_flat = axes.flatten()

    placeholder_used = False
    rows = []

    for i, run_id in enumerate(LEVELS):
        ax = axes_flat[i]
        hours = _load_charge_hours(run_id)
        if hours is None:
            hours = _placeholder_hours(run_id, seed=i)
            placeholder_used = True

        color = LEVEL_COLORS.get(run_id, "gray")
        ax.hist(hours, bins=np.arange(25) - 0.5, color=color,
                edgecolor="white", linewidth=0.5, density=True)
        ax.set_xlim(-0.5, 23.5)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_title(LEVEL_LABELS.get(run_id, run_id), fontsize=8)
        ax.set_ylabel("Density" if i % 2 == 0 else "")
        ax.set_xlabel("Hour of day" if i >= 2 else "")

        for h in hours:
            rows.append({"run_id": run_id, "hour": int(h)})

    fig.suptitle("TES charging hour-of-day distribution (winter, >0.1 MW)",
                 fontsize=9, y=1.01)
    plt.tight_layout()

    if placeholder_used:
        fig.text(0.5, -0.02, "[PLACEHOLDER — no run data]", ha="center",
                 fontsize=7, color="gray", style="italic")

    out = RUNS / "figures"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "fig_storage_charge_hour.csv", index=False)

    save_fig(fig, "fig_storage_charge_hour")


if __name__ == "__main__":
    main()
