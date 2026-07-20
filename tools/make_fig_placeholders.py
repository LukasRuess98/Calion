"""
Generate placeholder skeleton figures for F5, F6, F8, F10, F11, F12.
These require actual Gurobi run outputs. Placeholders show structure only.
Run after Gurobi results are available to replace with real data.
"""
from __future__ import annotations
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "output" / "paper_runs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
DPI = 300


def _note(ax, text: str) -> None:
    ax.text(0.5, 0.5, f"[PLACEHOLDER]\n{text}\nRequires Gurobi run data",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=9, color="#cc0000", fontfamily="serif",
            bbox=dict(boxstyle="round", facecolor="#fff0f0", alpha=0.8))


def _save(fig, stem: str) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(FIG_DIR / f"{stem}.{ext}", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  {stem}.pdf/.png written")


def make_f5() -> None:
    categories = ["L3 baseline", "+Pumping", "-Loss reduction", "+-Dispatch shift", "L3+ net"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(categories, [0]*5, color=["#2196F3","#F44336","#4CAF50","#FF9800","#9C27B0"])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("Delta Cost [EUR]", fontfamily="serif")
    ax.set_title("F5: Cost Waterfall L3 -> L3+ (placeholder)", fontfamily="serif")
    _note(ax, "Need L3 and L3+ annual run outputs")
    fig.tight_layout()
    _save(fig, "fig_cost_waterfall")
    with open(FIG_DIR / "fig_cost_waterfall.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["component", "delta_eur"])
        for c in categories:
            w.writerow([c, 0])


def make_f6() -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_xlabel("P_pump PWL [MW] (L3+)", fontfamily="serif")
    ax.set_ylabel("P_pump Quad [MW] (L3NL)", fontfamily="serif")
    ax.set_title("F6: Pump PWL vs Quadratic (placeholder)", fontfamily="serif")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5, label="1:1")
    ax.legend(fontsize=8)
    ax.text(0.05, 0.95, "R2 = n/a", transform=ax.transAxes, fontsize=9, va="top", fontfamily="serif")
    _note(ax, "Need L3+ and L3NL hourly pump dispatch")
    fig.tight_layout()
    _save(fig, "fig_pump_pwl_vs_quad")
    with open(FIG_DIR / "fig_pump_pwl_vs_quad.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["P_pump_pwl_MW", "P_pump_quad_MW", "flow_level"])


def make_f8() -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_xlabel("Hour of day", fontfamily="serif")
    ax.set_ylabel("Count of optimal charge events", fontfamily="serif")
    ax.set_title("F8: Storage Charge Hour Distribution - Winter (placeholder)", fontfamily="serif")
    ax.set_xlim(0, 24)
    _note(ax, "Need annual dispatch for all 5 levels")
    fig.tight_layout()
    _save(fig, "fig_storage_charge_hour")
    with open(FIG_DIR / "fig_storage_charge_hour.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hour", "level", "count"])


def make_f10() -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_xlabel("Total pipe length [km]", fontfamily="serif")
    ax.set_ylabel("L1->L2 cost gap [%]", fontfamily="serif")
    ax.set_title("F10: Topology Gap vs Pipe Length (placeholder)", fontfamily="serif")
    _note(ax, "Need 36 synthetic L1/L2 Gurobi runs")
    fig.tight_layout()
    _save(fig, "fig_synth_topology_gap")
    with open(FIG_DIR / "fig_synth_topology_gap.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["synth_id", "length_km", "HI", "gap_pct"])


def make_f11() -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.set_xlabel("Max transport delay tau_max [h]", fontfamily="serif")
    ax.set_ylabel("L3->L3+ cost gap [%]", fontfamily="serif")
    ax.set_title("F11: Physics Gap vs Transport Delay (placeholder)", fontfamily="serif")
    _note(ax, "Need 36 synthetic L3/L3+ Gurobi runs")
    fig.tight_layout()
    _save(fig, "fig_synth_physics_gap")
    with open(FIG_DIR / "fig_synth_physics_gap.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["synth_id", "tau_max_h", "length_km", "gap_pct"])


def make_f12() -> None:
    fig, axes = plt.subplots(1, 4, figsize=(14, 4))
    xlabels = ["n_nodes", "length_km", "HI", "storage_h"]
    for ax, xl in zip(axes, xlabels):
        ax.set_xlabel(xl, fontfamily="serif")
        ax.set_ylabel("L3+->L3NL gap [%]", fontfamily="serif")
        ax.text(0.5, 0.5, "[PLACEHOLDER]", transform=ax.transAxes,
                ha="center", va="center", color="#cc0000", fontsize=8, fontfamily="serif")
    fig.suptitle("F12: Linearization Gap vs Synth Parameters (placeholder)", fontfamily="serif")
    fig.tight_layout()
    _save(fig, "fig_synth_lin_error")
    with open(FIG_DIR / "fig_synth_lin_error.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["synth_id", "n_nodes", "length_km", "HI", "storage_h", "gap_pct"])


if __name__ == "__main__":
    make_f5()
    make_f6()
    make_f8()
    make_f10()
    make_f11()
    make_f12()
    print("All Gurobi-dependent figure placeholders written.")
