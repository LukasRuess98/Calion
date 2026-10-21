"""New TES-investment-value figure set (2026-10-16, post-AA3/Z3/Z4/Z5).

Replaces the stale 2026-08 electrification/heat-curve figure program (F1-F9)
for the results this paper now actually argues: TES investment value as a
function of its own cost (AA3 c0-sweep), robustness to tariff structure and
price volatility (Z3), and the SB-S1-vs-S2/S3 siting finding. All numbers are
read directly from already-extracted, already-verified campaign outputs
(docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md SS4ck-SS4co,
tab_Z5_sb_mm_s1_sweep_and_sensitivities.csv) -- no new solves, no invented data.
"""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np

from _style import (
    CATEGORICAL_CORE, DIV_NEG, DIV_POS, FHG_BLUE, FHG_GREEN, FHG_ORANGE,
    GRID, INK, INK_MUTED, INK_SOFT, COL_DOUBLE_IN, COL_SINGLE_IN,
    apply_rcparams, save,
)

apply_rcparams()

# ── AA3 c0-sweep data (SB-S1-HK0 vs shared PIN0; SS4ck/SS4cn) ───────────────
# spec_cost for 1.3x/1.5x computed from the SAME bit-identical V=30379.4 m3
# as 1.0x (degressive cost curve, c0_eur=2.5M/v0=10000/b=0.70) -- shown with a
# hollow/caveated marker since Gurobi's own Solution-count=1 log signature
# means the discrete size decision likely never left the warmstart there.
SWEEP = [
    # (label, spec_cost_eur_m3, vmin, vmax, point(mid), robust?)
    ("x1.0\n(base)", 179.1, 165_215, 230_414, True),
    ("x1.3", 232.8, 50_853, 162_944, False),
    ("x1.5", 268.6, 0, 141_167, False),
    ("x2.0", 751.9, 0, 103_407, True),
]
# AC (2026-10-21): PURE storage value = TES-free reference (HP/EK free, no storage) vs free run, from
# tab_Z5b_package_vs_storage_only.csv (reference = proxy SB-S3 until ac3_s0free_notes finishes).
# The SWEEP above is the PACKAGE value (PIN0 vs free = HP+EK+TES) and over-states the storage by the HP value.
SWEEP_STORAGE = [  # (spec_cost, vmin, vmax)
    (179.1, 103_592, 176_528),
    (232.8, 0, 109_058),
    (268.6, 0, 87_281),
    (751.9, 0, 49_521),
]
# AC1: same c0x1.0 case with charge/discharge power priced at 280,274 EUR/MW -> optimum builds NO storage
PRICED_POWER = (179.1, 0, 42_047)
REAL_PROJECTS = [
    ("Friedrichshafen", 240), ("Haltikon", 244), ("Munich", 337),
    ("Hamburg", 453), ("Perlen", 978), ("Neukoelln*", 2022),
]

SIZE_POINTS = [  # (spec_cost, V_TES_m3, robust?)
    (179.1, 30379.4, True),
    (232.8, 30379.4, False),
    (268.6, 30379.4, False),
    (751.9, 2566.3, True),
]

SENS = [  # (label, vmin, vmax)
    ("Base case", 165_215, 230_414),
    ("Grid fee -50%", 170_167, 224_352),
    ("Monthly billing", 168_120, 218_653),
    ("Marketing discount -2EUR/MWh", 161_647, 230_410),
    ("Price amplitude x1.5", 396_832, 469_959),
    ("Price amplitude x2.0", 644_140, 721_324),
]
SENS_MM = [  # same order, MM EUR/yr (two orders of magnitude smaller)
    None,
    (1_688, 2_902),
    (1_719, 2_444),
    (1_275, 2_507),
    (1_478, 2_593),
    (2_746, 3_316),
]

TOPOLOGY = [  # (label, obj_eur, mip_gap_pct, note)
    ("PIN0\n(no storage)", 23_370_804, 0.144, "shared reference"),
    ("S1\n(at primary\nproducer)", 23_172_020, 0.137, "TES built, 30,379 m3"),
    # AC (2026-10-21): S2/S3 re-solved with a valid PIN0 start (the earlier 23.384 M was a rejected/stuck
    # S1 warmstart): no TES built, but a 1.8 MW heat pump (HP-only value ~52 kEUR/a vs PIN0).
    ("S2\n(at HP node)", 23_318_969, 0.187, "no TES built, HP 1.8 MW"),
    ("S3\n(HP node,\nhot-charging)", 23_316_919, 0.177, "no TES built"),
]


def fig1_value_vs_cost():
    fig, ax = plt.subplots(figsize=(COL_DOUBLE_IN, 8.3 * (1 / 2.54)))

    xs = [p[1] for p in SWEEP]
    vmins = np.array([p[2] for p in SWEEP])
    vmaxs = np.array([p[3] for p in SWEEP])
    mids = (vmins + vmaxs) / 2
    robust = [p[4] for p in SWEEP]

    ymax = max(vmaxs) * 1.22
    ymin = -ymax * 0.10
    ax.set_ylim(ymin, ymax)
    ax.set_xscale("log")
    ax.set_xlim(150, 2600)

    # Real-project reference lines first (background layer). Friedrichshafen
    # (240) and Haltikon (244) are only 4 EUR/m3 apart -- indistinguishable at
    # this log scale, so they share one combined label instead of overlapping.
    ref_labels = {}
    for name, cost in REAL_PROJECTS:
        ref_labels.setdefault(cost, []).append(name)
    merged_refs = []
    used = set()
    for name, cost in REAL_PROJECTS:
        if cost in used:
            continue
        used.add(cost)
        close = [c2 for n2, c2 in REAL_PROJECTS if abs(math.log(c2 / cost)) < 0.02 and c2 != cost]
        if close:
            names_here = ref_labels[cost] + sum((ref_labels[c] for c in close), [])
            merged_refs.append(("/".join(names_here), cost))
            used.update(close)
        else:
            merged_refs.append((name, cost))

    for name, cost in merged_refs:
        ax.axvline(cost, color=GRID, lw=1.0, zorder=0)
        ax.text(cost, ymax * 0.99, name, rotation=90, ha="right", va="top",
                 fontsize=6.3, color=INK_MUTED)

    ax.axhline(0, color=INK_SOFT, lw=0.8, ls="--", zorder=1)

    # three series per cost point: package (light, left), storage-only (main), priced power (orange, right)
    for x, lo, hi, mid, rob in zip(xs, vmins, vmaxs, mids, robust):
        ax.plot([x * 0.93] * 2, [lo, hi], color=INK_MUTED, lw=2.0, alpha=0.55,
                solid_capstyle="round", zorder=2)
    for (x, lo, hi), rob in zip(SWEEP_STORAGE, robust):
        color = FHG_GREEN if rob else INK_MUTED
        fc = color if rob else "white"
        ax.plot([x, x], [lo, hi], color=color, lw=2.6, solid_capstyle="round", zorder=3)
        ax.scatter([x], [(lo + hi) / 2], s=50, color=fc, edgecolor=color, lw=1.6, zorder=4)
        ax.annotate(f"{int(round(lo/1000))}-{int(round(hi/1000))}k", (x * 1.0, hi),
                    textcoords="offset points", xytext=(0, 5), ha="center", fontsize=7, color=INK)
    px, plo, phi = PRICED_POWER
    ax.plot([px * 1.08] * 2, [plo, phi], color=FHG_ORANGE, lw=2.6, solid_capstyle="round", zorder=3)
    ax.scatter([px * 1.08], [0], s=50, color=FHG_ORANGE, edgecolor=FHG_ORANGE, zorder=4)
    ax.annotate("0-42k\nno storage\nbuilt", (px * 1.08, phi), textcoords="offset points",
                xytext=(-5, 2), ha="right", va="bottom", fontsize=6.5, color=FHG_ORANGE)

    for p, x in zip(SWEEP, xs):
        ax.annotate(p[0], (x * (0.95 if p[0].startswith("x1.0") else 1.0), ymin * 0.18),
                    ha="center", va="top", fontsize=7, color=INK_SOFT)

    ax.set_xticks([200, 300, 500, 750, 1000, 1500, 2000])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.set_xlabel("TES specific cost (EUR/m$^3$, log scale)")
    ax.set_ylabel("Storage-only value vs. TES-free reference (EUR/yr)")
    ax.set_title("Storage value shrinks with tank cost and vanishes once "
                  "charge/discharge power is priced", fontsize=9.5, loc="left")
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=FHG_GREEN, marker="o", lw=2.2, markersize=6,
               label="robust (solver explored multiple sizes)"),
        Line2D([0], [0], color=INK_MUTED, marker="o", markerfacecolor="white",
               lw=2.2, markersize=6, label="caveat: size may be stuck at warmstart"),
        Line2D([0], [0], color=INK_MUTED, alpha=0.55, lw=2.0,
               label="light bar: package value (HP+EK+TES vs PIN0)"),
        Line2D([0], [0], color=FHG_ORANGE, marker="o", lw=2.6, markersize=6,
               label="power priced 280 kEUR/MW: nothing built"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.08),
              ncol=2, fontsize=6.5, handletextpad=0.6, columnspacing=1.0)
    save(fig, "F_TES1_value_vs_cost")


def fig2_size_elasticity():
    fig, ax = plt.subplots(figsize=(COL_SINGLE_IN, 7.0 * (1 / 2.54)))
    for cost, V, rob in SIZE_POINTS:
        color = FHG_BLUE if rob else INK_MUTED
        fc = color if rob else "white"
        ax.scatter([cost], [V], s=60, color=fc, edgecolor=color, lw=1.6, zorder=3)

    robust_pts = [(c, v) for c, v, r in SIZE_POINTS if r]
    (c1, v1), (c2, v2) = robust_pts
    xs_line = np.array([c1, c2])
    # log-log line through the two robust points
    slope = math.log(v2 / v1) / math.log(c2 / c1)
    ys_line = v1 * (xs_line / c1) ** slope
    ax.plot(xs_line, ys_line, color=FHG_BLUE, lw=1.2, ls=":", zorder=2)
    ax.annotate(f"elasticity dV/dP = {slope:.2f}", xy=(math.sqrt(c1 * c2), math.sqrt(v1 * v2)),
                xytext=(8, 10), textcoords="offset points", fontsize=7.5, color=FHG_BLUE)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("TES specific cost (EUR/m$^3$)")
    ax.set_ylabel("Built TES volume (m$^3$, log scale)")
    ax.set_title("Built storage size is highly cost-elastic", fontsize=9.5, loc="left")
    save(fig, "F_TES2_size_elasticity")


def fig3_sensitivity_tornado():
    fig, ax = plt.subplots(figsize=(COL_DOUBLE_IN, 7.5 * (1 / 2.54)))
    labels = [s[0] for s in SENS]
    y = np.arange(len(labels))[::-1]
    for yi, (label, vmin, vmax) in zip(y, SENS):
        color = FHG_ORANGE if "amplitude" in label else FHG_GREEN
        ax.plot([vmin, vmax], [yi, yi], color=color, lw=6, solid_capstyle="butt", zorder=2)
        ax.annotate(f"{vmin/1000:,.0f}-{vmax/1000:,.0f}k", (vmax, yi),
                     textcoords="offset points", xytext=(6, 0), va="center", fontsize=7.5)
    base_mid = (SENS[0][1] + SENS[0][2]) / 2
    ax.axvline(base_mid, color=INK_SOFT, lw=0.8, ls="--", zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("SB investment package value vs PIN0: HP + EK + TES (EUR/yr)")
    ax.set_title("Package value is robust to tariff structure, but scales "
                  "strongly with price volatility", fontsize=9.5, loc="left")
    save(fig, "F_TES3_sensitivity_tornado")


def fig4_topology():
    fig, ax = plt.subplots(figsize=(COL_SINGLE_IN, 7.5 * (1 / 2.54)))
    labels = [t[0] for t in TOPOLOGY]
    vals = [t[1] / 1e6 for t in TOPOLOGY]
    colors = [INK_MUTED, FHG_GREEN, FHG_ORANGE, FHG_ORANGE]
    bars = ax.bar(labels, vals, color=colors, width=0.62)
    ymin = min(vals) - 0.03
    ax.set_ylim(ymin, max(vals) + 0.03)
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:.3f}M", (b.get_x() + b.get_width() / 2, v),
                     textcoords="offset points", xytext=(0, 4), ha="center", fontsize=7.5)
    ax.set_ylabel("Total annualized cost (EUR/yr, millions)")
    ax.set_title("Storage only pays off co-located with the primary producer (S1)",
                  fontsize=9, loc="left")
    ax.tick_params(axis="x", labelsize=7.2)
    save(fig, "F_TES4_siting_topology")


if __name__ == "__main__":
    fig1_value_vs_cost()
    fig2_size_elasticity()
    fig3_sensitivity_tornado()
    fig4_topology()
