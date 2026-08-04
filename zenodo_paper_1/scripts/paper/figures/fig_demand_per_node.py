"""Annual demand share per node for L3 and L2."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from scripts.paper.figures.fig_utils import apply_style, polish_axes, save_fig

RUNS = ROOT / "output" / "paper_runs"

COL_L3 = "#009B77"
COL_L2 = "#003E6E"
COL_REF = "#8C9EA8"

ZONE_MEMBERS = {
    "zone_B": "j2, j3",
    "zone_C": "j4-j5",
    "zone_D": "j6-j8",
    "zone_E": "j9-j11",
    "zone_F": "j12, j13",
    "zone_G": "j14, j15",
}


def _fmt_node(nid: str) -> str:
    if nid.startswith("j_"):
        return rf"$j_{{{nid[2:]}}}$"
    return nid.replace("zone_", "Zone ")


def _load_demand_pct(run_id: str) -> pd.Series | None:
    path = RUNS / run_id / "nodes_summary.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path).set_index("node_id")
    df = df[df["Q_demand_total_mwh"] > 0]
    total = df["Q_demand_total_mwh"].sum()
    if total == 0:
        return None
    return df["Q_demand_total_mwh"] / total * 100


def _gini(values: np.ndarray) -> float:
    x = np.sort(values)
    n = len(x)
    idx = np.arange(1, n + 1)
    return float((2 * np.dot(idx, x) - (n + 1) * x.sum()) / (n * x.sum()))


def _top3_share(series: pd.Series) -> float:
    return float(series.nlargest(3).sum())


def _draw_panel(
    ax: plt.Axes,
    series: pd.Series,
    *,
    color: str,
    panel_label: str,
    n_total_nodes: int,
    zone_members: dict[str, str] | None = None,
    x_max: float,
) -> None:
    series = series.sort_values(ascending=True)
    y_pos = np.arange(len(series))

    bars = ax.barh(
        y_pos, series.values, color=color, alpha=0.82,
        height=0.58, zorder=3, linewidth=0,
    )

    if zone_members:
        labels = [f"{_fmt_node(nid)} ({zone_members.get(nid, '')})" for nid in series.index]
    else:
        labels = [_fmt_node(nid) for nid in series.index]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)

    for bar, val in zip(bars, series.values):
        ax.text(
            val + x_max * 0.012,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center", ha="left", fontsize=6.2, color="#222222",
        )

    uniform = 100.0 / n_total_nodes
    ax.axvline(
        uniform, color=COL_REF, lw=0.8, ls=(0, (4, 3)), zorder=2,
        label=f"Uniform ({uniform:.1f}%)",
    )

    ann_text = f"Gini = {_gini(series.values):.2f}\nTop-3 = {_top3_share(series):.1f}%"
    ax.text(
        0.985, 0.97, ann_text,
        transform=ax.transAxes, fontsize=6.5, va="top", ha="right",
        color=color,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                  edgecolor=COL_REF, linewidth=0.5, alpha=0.9),
    )

    ax.set_title(panel_label, loc="left", color=color)
    ax.set_xlim(0, x_max)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
    ax.legend(
        loc="lower right", frameon=True, framealpha=0.9,
        borderpad=0.3, handlelength=1.3, handletextpad=0.35,
    )
    polish_axes(ax, grid_axis="x")


def main() -> None:
    apply_style()

    l3_data = _load_demand_pct("L3")
    l2_data = _load_demand_pct("L2")
    if l3_data is None or l2_data is None:
        missing = []
        if l3_data is None:
            missing.append("output/paper_runs/L3/nodes_summary.csv")
        if l2_data is None:
            missing.append("output/paper_runs/L2/nodes_summary.csv")
        print(f"[fig_demand_per_node] Missing demand data: {', '.join(missing)} - skipping")
        return

    assert "j_1" not in l3_data.index
    assert "zone_A" not in l2_data.index

    n_l3 = len(l3_data)
    n_l2 = len(l2_data)
    x_max = max(l3_data.max(), l2_data.max()) * 1.20

    fig, (ax_l3, ax_l2) = plt.subplots(
        2, 1,
        figsize=(4.65, 5.4),
        gridspec_kw={"height_ratios": [n_l3, n_l2]},
    )

    _draw_panel(
        ax_l3, l3_data, color=COL_L3,
        panel_label="(a) L3 - 14 consumer nodes",
        n_total_nodes=n_l3, x_max=x_max,
    )
    ax_l3.set_xlabel("")
    ax_l3.tick_params(labelbottom=False)

    _draw_panel(
        ax_l2, l2_data, color=COL_L2,
        panel_label="(b) L2 - 6 aggregated zones",
        n_total_nodes=n_l2, zone_members=ZONE_MEMBERS, x_max=x_max,
    )
    ax_l2.set_xlabel("Annual demand share [% of system total]")

    fig.tight_layout(pad=0.5, h_pad=1.0)
    save_fig(fig, "fig_demand_per_node")


if __name__ == "__main__":
    main()
