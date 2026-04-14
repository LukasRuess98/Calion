"""
Figure — Sensitivity index heatmap: L1 / L2 / L3 across 7 parameters.

Left panel  : heatmap (YlOrRd) with annotated index values.
Right panel : tornado-style horizontal bar chart for L3.

Usage:
    python scripts/paper/plot_sensitivity_heatmap.py \\
        [--input  outputs/paper/sensitivity/sensitivity_indices_by_level.csv] \\
        [--outdir outputs/paper/figures]

Input CSV columns:
    param_path, description, units,
    L1_index, L2_index, L3_index,
    L1_low, L1_base, L1_high,
    L2_low, L2_base, L2_high,
    L3_low, L3_base, L3_high

Produces:
    figX_sensitivity_heatmap.pdf  (vector — use in Overleaf)
    figX_sensitivity_heatmap.png  (300 DPI preview)
"""
import argparse
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from ecm_style import (
    apply_ecm_style,
    save_figure,
    DOUBLE_COL_W,
    H_STANDARD,
    C_L3,
    FONT_ANNOTATION,
    FONT_TICK,
    FONT_AXIS_LABEL,
)

apply_ecm_style()

# ── Placeholder data (used when input CSV is absent) ─────────────────────────
PLACEHOLDER_DATA = {
    "param_path": [
        "fuels.gas.price_eur_mwh",
        "costs.co2_price_eur_per_t",
        "heat_pumps.hp_main.eta_relative",
        "storage.tes_main.hourly_loss",
        "storage.tes_main.eff_charge",
        "electricity_price_scale",
        "demand_scale",
    ],
    "description": [
        "Natural gas price",
        "CO\u2082 price",
        "HP Carnot factor",
        "Storage loss rate",
        "Storage charge eff.",
        "Electricity price",
        "Annual heat demand",
    ],
    "units": [
        "EUR/MWh",
        "EUR/t",
        "-",
        "1/h",
        "-",
        "scale factor",
        "scale factor",
    ],
    "L1_index": [0.156, 0.132, 0.201, 0.045, 0.038, 0.187, 0.241],
    "L2_index": [0.148, 0.128, 0.189, 0.052, 0.041, 0.175, 0.267],
    "L3_index": [0.162, 0.141, 0.175, 0.061, 0.049, 0.168, 0.244],
    "L1_low":   [0.098, 0.080, 0.135, 0.028, 0.022, 0.120, 0.165],
    "L1_base":  [0.156, 0.132, 0.201, 0.045, 0.038, 0.187, 0.241],
    "L1_high":  [0.214, 0.184, 0.267, 0.062, 0.054, 0.254, 0.317],
    "L2_low":   [0.091, 0.075, 0.121, 0.032, 0.025, 0.113, 0.179],
    "L2_base":  [0.148, 0.128, 0.189, 0.052, 0.041, 0.175, 0.267],
    "L2_high":  [0.205, 0.181, 0.257, 0.072, 0.057, 0.237, 0.355],
    "L3_low":   [0.104, 0.086, 0.113, 0.038, 0.029, 0.108, 0.162],
    "L3_base":  [0.162, 0.141, 0.175, 0.061, 0.049, 0.168, 0.244],
    "L3_high":  [0.220, 0.196, 0.237, 0.084, 0.069, 0.228, 0.326],
}

LEVEL_COLS   = ["L1_index", "L2_index", "L3_index"]
LEVEL_LABELS = ["L1", "L2", "L3"]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data(csv_path: Path) -> pd.DataFrame:
    """Load sensitivity index CSV; fall back to placeholder if absent."""
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        required = {"param_path", "description", "units"} | set(LEVEL_COLS)
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Input CSV is missing columns: {missing}")
        return df
    else:
        warnings.warn(
            f"Input file not found: {csv_path}\n"
            "  Generating placeholder data for layout testing.",
            stacklevel=2,
        )
        print(f"WARNING: '{csv_path}' not found — using built-in placeholder data.")
        return pd.DataFrame(PLACEHOLDER_DATA)


# ── Figure construction ───────────────────────────────────────────────────────

def build_row_labels(df: pd.DataFrame) -> list[str]:
    """Combine description and units into a single y-axis label per row."""
    labels = []
    for _, row in df.iterrows():
        unit = str(row["units"]).strip()
        desc = str(row["description"]).strip()
        if unit and unit not in ("-", "", "nan"):
            labels.append(f"{desc} [{unit}]")
        else:
            labels.append(desc)
    return labels


def plot_sensitivity_heatmap(df: pd.DataFrame, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    n_params = len(df)
    row_labels = build_row_labels(df)

    # Matrix: shape (n_params, 3)  — rows = params, cols = L1/L2/L3
    index_matrix = df[LEVEL_COLS].values.astype(float)

    vmin = 0.0
    vmax = float(np.nanmax(index_matrix))
    if vmax == 0.0:
        vmax = 1.0  # guard against all-zero placeholder

    # Sort order for tornado panel (descending L3)
    l3_order = np.argsort(df["L3_index"].values)[::-1]

    # ── Layout ────────────────────────────────────────────────────────────────
    fig_w = DOUBLE_COL_W
    fig_h = H_STANDARD * 1.4
    fig, (ax_heat, ax_bar) = plt.subplots(
        1, 2,
        figsize=(fig_w, fig_h),
        gridspec_kw={"width_ratios": [1.15, 1.0], "wspace": 0.55},
    )

    # ── Left panel: heatmap ───────────────────────────────────────────────────
    cmap = plt.get_cmap("YlOrRd")
    im = ax_heat.imshow(
        index_matrix,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
        interpolation="nearest",
    )

    # Cell annotations
    for r in range(n_params):
        for c in range(3):
            val = index_matrix[r, c]
            # Choose text colour for legibility against heatmap background
            norm_val = (val - vmin) / (vmax - vmin)
            text_color = "white" if norm_val > 0.65 else "black"
            ax_heat.text(
                c, r,
                f"{val:.2f}",
                ha="center", va="center",
                fontsize=FONT_ANNOTATION,
                color=text_color,
                fontweight="bold",
            )

    ax_heat.set_xticks(range(3))
    ax_heat.set_xticklabels(LEVEL_LABELS, fontsize=FONT_TICK)
    ax_heat.set_yticks(range(n_params))
    ax_heat.set_yticklabels(row_labels, fontsize=FONT_TICK)
    ax_heat.tick_params(axis="both", length=0)

    # Thin grid lines between cells
    for x in np.arange(-0.5, 3, 1):
        ax_heat.axvline(x, color="white", linewidth=0.8)
    for y in np.arange(-0.5, n_params, 1):
        ax_heat.axhline(y, color="white", linewidth=0.8)

    ax_heat.set_title("Sensitivity indices", fontsize=FONT_AXIS_LABEL,
                       pad=6, fontweight="bold")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax_heat, orientation="vertical",
                        fraction=0.046, pad=0.04)
    cbar.set_label("Sensitivity index $S_i$", fontsize=FONT_TICK)
    cbar.ax.tick_params(labelsize=FONT_TICK)
    cbar.outline.set_linewidth(0.5)

    # Remove axis spines on heatmap (imshow adds them back by default)
    for spine in ax_heat.spines.values():
        spine.set_visible(False)

    # ── Right panel: tornado bar chart (L3 only, sorted descending) ──────────
    l3_vals     = df["L3_index"].values[l3_order].astype(float)
    bar_labels  = [row_labels[i] for i in l3_order]
    y_pos       = np.arange(len(l3_order))

    bars = ax_bar.barh(
        y_pos,
        l3_vals,
        height=0.55,
        color=C_L3,
        alpha=0.85,
        edgecolor="white",
        linewidth=0.5,
    )

    # Value labels at the end of each bar
    for bar, val in zip(bars, l3_vals):
        ax_bar.text(
            val + vmax * 0.02,
            bar.get_y() + bar.get_height() / 2.0,
            f"{val:.2f}",
            ha="left", va="center",
            fontsize=FONT_ANNOTATION,
        )

    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(bar_labels, fontsize=FONT_TICK)
    ax_bar.set_xlabel("Sensitivity index $S_i$", fontsize=FONT_AXIS_LABEL)
    ax_bar.set_title("L3 ranking", fontsize=FONT_AXIS_LABEL,
                     pad=6, fontweight="bold")
    ax_bar.set_xlim(0, vmax * 1.20)
    ax_bar.invert_yaxis()   # highest value at top
    ax_bar.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax_bar.grid(True, axis="x", linewidth=0.4, alpha=0.4)
    ax_bar.tick_params(axis="both", labelsize=FONT_TICK)

    # ── Save ──────────────────────────────────────────────────────────────────
    fig.tight_layout()
    stem = outdir / "figX_sensitivity_heatmap"
    save_figure(fig, stem)
    plt.close(fig)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render sensitivity index heatmap (L1/L2/L3)."
    )
    parser.add_argument(
        "--input",
        default="outputs/paper/sensitivity/sensitivity_indices_by_level.csv",
        metavar="CSV",
        help="Path to sensitivity indices CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--outdir",
        default="outputs/paper/figures",
        metavar="DIR",
        help="Output directory for figures (default: %(default)s)",
    )
    args = parser.parse_args()

    csv_path = Path(args.input)
    outdir   = Path(args.outdir)

    df = load_data(csv_path)
    plot_sensitivity_heatmap(df, outdir)


if __name__ == "__main__":
    main()
