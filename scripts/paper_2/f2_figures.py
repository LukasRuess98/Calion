"""F2 sizing-curve figures from the atmospheric f2_*.csv (2026-09-14).

Renders the geometric-storage sizing curves (TAC_full vs storage size), showing the
inner cost optimum, for both networks. Reads output/paper2_sweeps/f2_<...>.csv and writes
PNG+PDF to output/paper2_sweeps/figures/.

Usage: PYTHONPATH=. python scripts/paper_2/f2_figures.py
"""
from __future__ import annotations
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_SW = _ROOT / "output" / "paper2_sweeps"
_FIG = _SW / "figures"
_FIG.mkdir(parents=True, exist_ok=True)

# Fraunhofer-ish palette
C = {"HK0": "#179C7D", "HK1": "#005B7F", "HK2": "#B90276", "SB": "#005B7F", "cap": "#8DA3B0"}


def _load(name: str):
    p = _SW / f"{name}.csv"
    if not p.exists():
        return None
    rows = []
    for r in csv.DictReader(open(p, encoding="utf-8")):
        def f(k):
            v = r.get(k, "")
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        rows.append({"R": f("rung_mwh"), "opex": f("opex_tac"), "capex": f("capex_annual"),
                     "tac": f("tac_full"), "gap": f("gap"), "status": r.get("status", "")})
    return rows


def _argmin(rows):
    v = [r for r in rows if r["tac"] is not None and r["R"] and r["R"] > 0]
    return min(v, key=lambda r: r["tac"]) if v else None


def fig_mm_heatcurve():
    """MM-S3 across HK0/HK1/HK2 — TAC_full vs size, one axes."""
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    any_data = False
    for hk in ("HK0", "HK1", "HK2"):
        rows = _load(f"f2_MM-S3-{hk}")
        if not rows:
            continue
        any_data = True
        pts = [(r["R"], r["tac"]) for r in rows if r["tac"] is not None and r["R"] is not None]
        pts.sort()
        xs = [p[0] for p in pts]; ys = [p[1] / 1e3 for p in pts]
        ax.plot(xs, ys, "-o", ms=4, color=C[hk], label=f"{hk}")
        s0 = next((r["tac"] for r in rows if r["R"] == 0), None)
        best = _argmin(rows)
        if best:
            ax.plot(best["R"], best["tac"] / 1e3, "*", ms=14, color=C[hk], zorder=5)
            sav = 100 * (s0 - best["tac"]) / s0 if s0 else 0
            ax.annotate(f"{best['R']:g} MWh\n-{sav:.1f}%", (best["R"], best["tac"] / 1e3),
                        textcoords="offset points", xytext=(6, 6), fontsize=8, color=C[hk])
    if not any_data:
        plt.close(fig); return
    ax.set_xlabel("TES size [MWh]"); ax.set_ylabel("Total annual cost [k€/a]")
    ax.set_title("Memmingen S3 — storage sizing vs heat curve (atmospheric)", fontsize=11)
    ax.legend(title="Heat curve", frameon=False); ax.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(_FIG / f"F2_MM_S3_heatcurve.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote F2_MM_S3_heatcurve.png/pdf")


def fig_network(name: str, title: str, out: str):
    """Single-scenario stacked OPEX+CAPEX -> TAC_full vs size, optimum marked."""
    rows = _load(name)
    if not rows:
        print(f"skip {name} (no data)"); return
    pos = [r for r in rows if r["R"] and r["R"] > 0 and r["tac"] is not None]
    pos.sort(key=lambda r: r["R"])
    if not pos:
        print(f"skip {name} (no positive rungs)"); return
    xs = [r["R"] for r in pos]
    scale = 1e6 if pos[0]["tac"] > 1e6 else 1e3
    unit = "M€/a" if scale == 1e6 else "k€/a"
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot(xs, [r["opex"] / scale for r in pos], "--", color=C["cap"], label="OPEX")
    ax.plot(xs, [r["tac"] / scale for r in pos], "-o", ms=4, color=C["SB"], label="TAC (OPEX+CAPEX)")
    s0 = next((r["tac"] for r in rows if r["R"] == 0), None)
    if s0:
        ax.axhline(s0 / scale, ls=":", color="0.4", label="S0 (no storage)")
    best = _argmin(rows)
    if best:
        ax.plot(best["R"], best["tac"] / scale, "*", ms=16, color="#B90276", zorder=5,
                label=f"optimum {best['R']:g} MWh")
        if s0:
            sav = 100 * (s0 - best["tac"]) / s0
            ax.annotate(f"-{sav:.1f}%", (best["R"], best["tac"] / scale),
                        textcoords="offset points", xytext=(8, -12), fontsize=9, color="#B90276")
    ax.set_xlabel("TES size [MWh]"); ax.set_ylabel(f"Annual cost [{unit}]")
    ax.set_title(title); ax.legend(frameon=False); ax.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(_FIG / f"{out}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}.png/pdf")


if __name__ == "__main__":
    fig_mm_heatcurve()
    fig_network("f2_MM-S3-HK0", "Memmingen — S3 storage sizing (atmospheric)", "F2_MM_S3_HK0")
    fig_network("f2_SB-S1-HK0", "Stadtbach — S1 storage sizing (atmospheric)", "F2_SB_S1_HK0")
    print(f"figures -> {_FIG}")
