"""Publication figures (Elsevier *Energy*) of the central TES study — figure system v2 (2026-10-16).

Typeface: Latin Modern Roman (the Computer Modern of the elsarticle LaTeX class), 8 pt labels / 7.5 pt ticks at print
size; maths in Computer Modern. The Latin Modern OpenType files of the local TeX installation are converted once to
TrueType into ``results/central_tes/.fontcache`` (gitignored, local only) so that the PDF embeds clean Type 42 fonts;
without them the figures fall back to matplotlib's bundled Computer Modern.
Colours: the institute's corporate palette with fixed roles — TES green, partner A orange, partner B dark blue, reference
grey, other identities turquoise; temperature layers from blue (90 °C) to deep red (120 °C).
Plant labels: GCHP (gas CHP), WI (waste incineration), GT, BCHP (biomass CHP), GB (gas peak boiler in the south).
Sizes: 190 mm (double column) and 140 mm; vector PDF + 600 dpi PNG and TIFF.
Paper order: fig0 → Fig. 1, fig1 → 2, fig2 → 3, fig7 → 4, fig3 → 5, fig5 → 6, fig6 → 7, fig4 → 8.

    python -m scripts.dhn_study.central_tes.paper_figures
Output: results/central_tes/paper_figures/
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from . import config as C  # noqa: E402

MM = 1 / 25.4
W1, W15, W2 = 90 * MM, 140 * MM, 190 * MM

# ---- corporate palette of the institute, fixed roles
GREEN, GREEN_L, GREEN_XL = "#179C7D", "#7CC4B1", "#CFE8E1"        # TES (solid / tint / light)
ORANGE, ORANGE_L = "#F58220", "#FBC08F"                           # partner A (HP)
BLUE, BLUE_L = "#005B7F", "#8DB4C7"                               # partner B (EB)
GREY, GREY_L = "#A3A9AD", "#DADDDF"                               # reference without the asset
TURQ, TURQ_D = "#39C1CD", "#1C8FA0"                               # other identities (south site, models)
INK, INK2, MUTED, GRID = "#1E2328", "#4A5157", "#7C858B", "#E4E7E9"
SHADE = "#F1F2F3"
LAYER = {90: "#2C6FB7", 95: "#6FA3D6", 100: "#B5D3EC", 105: "#F3D3B8", 110: "#E9925F", 115: "#C94C2E", 120: "#9B1B1E"}
PLANT = {"KWK": "GCHP", "MVA": "WI", "GT": "GT", "BIO": "BCHP", "HW1": "GB"}
LIMIT_CHP = 4.0
LM = ("lmroman10-regular", "lmroman10-bold", "lmroman10-italic", "lmroman10-bolditalic")
FAMILY = "LMR10 local TT"           # family name of the locally converted TrueType copy (cache only, never distributed)


def _fonts() -> str:
    """Latin Modern Roman as TrueType (converted locally from the TeX OpenType files); fallback: bundled cmr10."""
    cache = C.root() / C.load()["paths"]["results"] / ".fontcache"
    src = Path("/usr/share/texmf/fonts/opentype/public/lm")
    try:
        cache.mkdir(parents=True, exist_ok=True)
        for name in LM:
            ttf = cache / f"{name}.ttf"
            if not ttf.exists() and (src / f"{name}.otf").exists():   # converted once; delete the cache to rebuild
                _otf_to_ttf(src / f"{name}.otf", ttf)
            if ttf.exists():
                font_manager.fontManager.addfont(str(ttf))
        if any(f.name == FAMILY for f in font_manager.fontManager.ttflist):
            return FAMILY
    except Exception as e:  # noqa: BLE001
        print("font conversion failed, using cmr10:", e)
    return "cmr10"


def _otf_to_ttf(src: Path, dst: Path):
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont, newTable
    f = TTFont(str(src))
    gs, order = f.getGlyphSet(), f.getGlyphOrder()
    glyf = newTable("glyf")
    glyf.glyphOrder, glyf.glyphs = order, {}
    for g in order:
        pen = TTGlyphPen(gs)
        gs[g].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyf.glyphs[g] = pen.glyph()
    f["glyf"], f["loca"] = glyf, newTable("loca")
    del f["CFF "]
    if "VORG" in f:
        del f["VORG"]
    f.sfntVersion = "\x00\x01\x00\x00"
    m = f["maxp"]
    m.tableVersion = 0x00010000
    for a in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs", "maxStackElements",
              "maxSizeOfInstructions", "maxComponentElements"):
        setattr(m, a, 0)
    m.maxZones = 1
    f["head"].glyphDataFormat, f["head"].indexToLocFormat = 0, 0
    style_ = {"regular": "Regular", "bold": "Bold", "italic": "Italic", "bolditalic": "Bold Italic"}[src.stem.split("-")[-1]]
    for rec in f["name"].names:                                   # local converted copy gets its own family name
        if rec.nameID in (1, 16):
            rec.string = FAMILY
        elif rec.nameID in (4,):
            rec.string = f"{FAMILY} {style_}"
        elif rec.nameID == 6:
            rec.string = f"{FAMILY.replace(' ', '')}-{style_.replace(' ', '')}"
    post = f["post"]
    post.formatType, post.extraNames, post.mapping, post.glyphOrder = 2.0, [], {}, order
    f.save(str(dst))


def style():
    fam = _fonts()
    plt.rcParams.update({
        "font.family": "serif", "font.serif": [fam, "cmr10", "DejaVu Serif"], "mathtext.fontset": "cm",
        "axes.formatter.use_mathtext": True, "axes.unicode_minus": True,
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5, "legend.frameon": False, "legend.handlelength": 1.8, "legend.borderaxespad": 0.3,
        "legend.labelspacing": 0.35,
        "axes.linewidth": 0.6, "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True, "ytick.right": True,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 3.0, "ytick.major.size": 3.0,
        "xtick.minor.size": 1.6, "ytick.minor.size": 1.6, "xtick.minor.width": 0.45, "ytick.minor.width": 0.45,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.45, "axes.axisbelow": True,
        "lines.linewidth": 1.2, "patch.linewidth": 0.5, "hatch.linewidth": 0.5,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.dpi": 600, "figure.dpi": 150, "text.color": INK,
    })


def label(ax, s, x=-0.02, y=1.02, inside=False):
    """Panel label, bold: above the upper-left corner of the axes, or inside it (stacked time-series panels)."""
    if inside:
        ax.text(0.008, 0.95, s, transform=ax.transAxes, ha="left", va="top", fontsize=9, fontweight="bold", color=INK, zorder=10,
                bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none", alpha=0.9))
        return
    ax.text(x, y, s, transform=ax.transAxes, ha="right", va="bottom", fontsize=9, fontweight="bold", color=INK)


def flabel(fig, ax, s, dx=0.0):
    """Panel label in figure coordinates at the left edge of the figure column of the axes (aligned across rows)."""
    pos = ax.get_position()
    fig.text(dx, pos.y1 + 0.012, s, ha="left", va="bottom", fontsize=9, fontweight="bold", color=INK)


def boxed(ax, x, y, s, color=INK, **kw):
    """Annotation on a white box (stays legible over lines and markers)."""
    return ax.text(x, y, s, color=color, fontsize=kw.pop("fontsize", 7.2), zorder=kw.pop("zorder", 6),
                   bbox=dict(boxstyle="round,pad=0.22", fc="white", ec=kw.pop("ec", "none"), lw=0.5, alpha=0.92), **kw)


def save(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf")
    fig.savefig(out / f"{name}.png", dpi=600)
    fig.savefig(out / f"{name}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def _j(p: Path) -> dict:
    return json.loads(p.read_text())


def k_(x) -> str:
    return f"{x:,.0f}".replace(",", " ")


# --------------------------------------------------------------------------------------------- Fig. 2: value
def fig_value(r: Path, out: Path):
    sh = _j(r / "scenario_runs" / "shapley.json")["E"]
    v, phi = sh["v"], sh["phi"]
    rh = _j(r / "rolling_horizon" / "F111-E_schedule_known_day_ahead" / "annual_metrics.json")["cost_total_EUR"]
    c0 = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario").at["F000", "C_E"]
    names = {"F010": "Partner B (EB)", "F100": "Partner A (HP)", "F110": "A + B", "F001": "TES",
             "F011": "TES + B", "F101": "TES + A", "F111": "TES + A + B"}
    order = sorted(names, key=lambda k: v[k])
    fig = plt.figure(figsize=(W2, 64 * MM))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.8, 1.05, 1.35], wspace=0.5, left=0.125, right=0.985, bottom=0.19, top=0.9)
    ax = fig.add_subplot(gs[0])
    y = np.arange(len(order))
    ax.barh(y, [v[k] / 1e3 for k in order], height=0.62, color=[GREEN if k[-1] == "1" else GREY for k in order],
            edgecolor=INK, linewidth=0.4)
    for i, k in enumerate(order):
        ax.text(v[k] / 1e3 + 9, i, k_(v[k] / 1e3), va="center", fontsize=7.5)
    ax.set_yticks(y, [names[k] for k in order])
    ax.tick_params(axis="y", which="both", length=0)
    ax.set_xlabel("Annual cost saving vs. reference without TES and partners [k€/a]")
    ax.set_xlim(0, 650)
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[Patch(fc=GREEN, ec=INK, lw=0.4, label="with TES"), Patch(fc=GREY, ec=INK, lw=0.4, label="without TES")],
              loc="lower right")
    label(ax, "(a)", x=-0.3)

    ax = fig.add_subplot(gs[1])
    tot = sum(phi.values())
    parts = [("TES", phi["TES"], GREEN), ("Partner A (HP)", phi["A"], ORANGE), ("Partner B (EB)", phi["B"], BLUE)]
    b, ys = 0.0, []
    for n, val, c in parts:
        ax.bar(0, val / 1e3, bottom=b / 1e3, width=0.5, color=c, edgecolor=INK, linewidth=0.4)
        ys.append((b + val / 2) / 1e3)
        b += val
    ty = [ys[0], ys[1] - 22, ys[2] + 52]                      # label positions, spread so they never touch
    for (n, val, c), yy, tyy in zip(parts, ys, ty):
        ax.annotate(f"{n}\n{k_(val / 1e3)}  ({100 * val / tot:.0f} %)", xy=(0.26, yy), xytext=(0.42, tyy), fontsize=7.2,
                    va="center", ha="left", linespacing=1.05,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5, shrinkA=0, shrinkB=0))
    ax.set_xlim(-0.4, 2.15)
    ax.set_xticks([])
    ax.tick_params(axis="x", which="both", top=False, bottom=False)
    ax.tick_params(axis="y", which="both", right=False)
    ax.set_ylabel("Shapley value [k€/a]")
    ax.set_ylim(0, 640)
    ax.grid(axis="x", visible=False)
    label(ax, "(b)", x=-0.2)

    ax = fig.add_subplot(gs[2])
    rhd = pd.read_csv(r / "rolling_horizon" / "tes_values_rh.csv")
    ref = rhd[(rhd["V_m3"] == 5000) & (rhd["Q_MW"] == 40)].iloc[0]
    groups = [("TES + A + B\nvs. reference", v["F111"], c0 - rh),
              ("TES\nvs. A + B", sh["storage_value"]["F111-F110"], ref["C_RH_F110"] - ref["C_RH_F111"])]
    wb = 0.36
    for i, (_, pf, rr) in enumerate(groups):
        ax.bar(i - wb / 2, pf / 1e3, width=wb, color=GREEN, edgecolor=INK, linewidth=0.4,
               label="perfect foresight" if i == 0 else None)
        ax.bar(i + wb / 2, rr / 1e3, width=wb, color=GREEN_XL, edgecolor=GREEN, linewidth=0.8, hatch="////",
               label="rolling horizon" if i == 0 else None)
        ax.text(i - wb / 2, pf / 1e3 + 10, k_(pf / 1e3), ha="center", va="bottom", fontsize=7.5)
        ax.text(i + wb / 2, rr / 1e3 + 10, k_(rr / 1e3), ha="center", va="bottom", fontsize=7.5)
        ax.text(i + wb / 2, rr / 1e3 * 0.5, f"{100 * rr / pf:.0f} %", ha="center", va="center", fontsize=7.5, rotation=90,
                fontweight="bold", color=INK, bbox=dict(boxstyle="square,pad=0.15", fc=GREEN_XL, ec="none"))
    ax.set_xticks([0, 1], [g[0] for g in groups])
    ax.tick_params(axis="x", which="both", length=0)
    ax.set_ylabel("Annual cost saving [k€/a]")
    ax.set_ylim(0, 720)
    ax.set_xlim(-0.6, 1.6)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right")
    label(ax, "(c)", x=-0.2)
    save(fig, out, "fig1_value_attribution")


# --------------------------------------------------------------------------------------------- Fig. 3: operation
def fig_operation(r: Path, out: Path, start="2025-03-17", days=7):
    eta_eb = float(C.load()["electrode_boiler"]["eta"])
    d = pd.read_parquet(r / "scenario_runs" / "F111-E" / "milp_timeseries.parquet")
    d0 = pd.read_parquet(r / "scenario_runs" / "F000-E" / "milp_timeseries.parquet")
    sl = slice(pd.Timestamp(start), pd.Timestamp(start) + pd.Timedelta(days=days) - pd.Timedelta(hours=1))
    w, w0 = d.loc[sl], d0.loc[sl]
    lay = sorted([int(c.split("_")[-1]) for c in d if c.startswith("E_class_")])
    t = w.index
    te = t.append(pd.DatetimeIndex([t[-1] + pd.Timedelta(hours=1)]))       # step edges
    neg = (w["price"] <= 0).to_numpy()

    def steps(s):
        return np.r_[s.to_numpy(), s.to_numpy()[-1]]

    fig, axs = plt.subplots(5, 1, figsize=(W2, 168 * MM), sharex=True,
                            gridspec_kw={"height_ratios": [0.75, 0.8, 1.45, 1.1, 0.95], "hspace": 0.16})
    fig.subplots_adjust(left=0.085, right=0.83, top=0.985, bottom=0.05)
    for a in axs:                                                          # hours with price <= 0
        for i in np.flatnonzero(neg):
            a.axvspan(te[i], te[i + 1], color=SHADE, lw=0, zorder=0)
    ax = axs[0]
    ax.fill_between(te, steps(w["price"]), 0, step="post", color=GREY_L, lw=0, zorder=1)
    ax.step(te, steps(w["price"]), where="post", color=INK, lw=0.8, zorder=2)
    ax.axhline(0, color=INK, lw=0.5)
    ax.set_ylabel("Day-ahead price\n[€/MWh]")
    ax.text(1.012, 0.5, "shaded:\nprice $\\leq$ 0", transform=ax.transAxes, fontsize=7.2, color=INK2, va="center")
    label(ax, "(a)", inside=True)
    ax = axs[1]
    txt = {100: "#5F8FBF", 105: "#C2865A"}
    for T in lay:
        ax.axhline(T, color=LAYER[T], lw=0.8, ls=(0, (3, 2)), zorder=1)
        ax.text(1.012, (T - 86) / (124 - 86), f"{T} °C", transform=ax.transAxes, fontsize=6.8, color=txt.get(T, LAYER[T]),
                va="center")
    ax.text(1.012, 1.04, "layer", transform=ax.transAxes, fontsize=6.8, color=INK2, va="bottom")
    ax.step(te, steps(w["T_VL"]), where="post", color=INK, lw=1.1, zorder=3)
    ax.set_ylabel("Supply\ntemperature [°C]")
    ax.set_ylim(86, 124)
    ax.set_yticks([90, 100, 110, 120])
    label(ax, "(b)", inside=True)
    ax = axs[2]
    ys = [steps(w[f"E_class_{T}"]) for T in lay]
    ax.stackplot(te, *ys, colors=[LAYER[T] for T in lay], step="post", edgecolor="white", linewidth=0.35, alpha=0.92, zorder=2)
    ax.step(te, np.sum(ys, axis=0), where="post", color=INK, lw=0.6, zorder=3)
    ax.set_ylabel("Stored energy\n[MWh]")
    ax.set_ylim(0, None)
    h = [Patch(fc=LAYER[T], ec="white", lw=0.4, label=f"{T} °C") for T in lay][::-1]
    ax.legend(handles=h, title="temperature\nlayer", title_fontsize=7.5, loc="center left", bbox_to_anchor=(1.005, 0.5),
              handlelength=1.3, handleheight=0.9, labelspacing=0.15)
    label(ax, "(c)", inside=True)
    ax = axs[3]
    dis, chg = w["Q_dis"], w["Q_ch_grid"]
    ax.fill_between(te, steps(dis), 0, step="post", color=GREEN, alpha=0.85, lw=0, label="TES discharge", zorder=2)
    ax.fill_between(te, -steps(chg), 0, step="post", fc=GREEN_XL, ec=GREEN, lw=0.4, hatch="////",
                    label="TES charge\n(from network)", zorder=2)
    ax.step(te, steps(w["Q_HP"]), where="post", color=ORANGE, lw=1.2, label="HP, partner A", zorder=4)
    ax.step(te, steps(w["P_EB"] * eta_eb), where="post", color=BLUE, lw=1.2, label="EB, partner B", zorder=4)
    ax.axhline(0, color=INK, lw=0.5)
    ax.set_ylabel("Heat at site S\n[MW]")
    lim = max(dis.max(), chg.max(), 12) * 1.08
    ax.set_ylim(-lim, lim)
    ax.legend(loc="center left", bbox_to_anchor=(1.005, 0.5), handlelength=1.4)
    label(ax, "(d)", inside=True)
    ax = axs[4]
    a1, a0 = steps(w["Q_KWK"]), steps(w0["Q_KWK"])
    ax.fill_between(te, a1, a0, where=a1 >= a0, step="post", color=GREEN, alpha=0.25, lw=0, zorder=1)
    ax.fill_between(te, a1, a0, where=a1 < a0, step="post", color=GREY, alpha=0.35, lw=0, zorder=1)
    ax.step(te, a0, where="post", color=MUTED, lw=1.0, label="no TES,\nno partners", zorder=2)
    ax.step(te, a1, where="post", color=GREEN, lw=1.1, label="TES +\npartners A, B", zorder=3)
    ax.set_ylabel("GCHP heat\n[MW]")
    ax.set_ylim(0, None)
    ax.legend(loc="center left", bbox_to_anchor=(1.005, 0.5), handlelength=1.4)
    label(ax, "(e)", inside=True)
    fig.align_ylabels(axs)
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d %b"))
    ax.set_xlim(te[0], te[-1])
    for a in axs:
        a.grid(axis="x", which="major", color=GRID, lw=0.45)
        a.grid(axis="y", color=GRID, lw=0.45)
    save(fig, out, "fig2_operation_week")
    return {"week": start, "TES_dis_MWh": float(w["Q_dis"].sum()), "CHP_shift": float((w["Q_KWK"] - w0["Q_KWK"]).abs().sum())}


# --------------------------------------------------------------------------------------------- Fig. 5: pressure
EDGE_LABEL = {"KWKi": "GCHP outlet", "M12": "M12  mesh L1 – city", "L1a": "L1a  trunk from GCHP", "L4a": "L4a  south trunk",
              "L5a": "L5a  east line to S", "L4d": "L4d  south line", "L1b": "L1b  L1 branch", "L4b": "L4b  south line",
              "L4c": "L4c  south line (PS1)", "L3": "L3  city feeder", "L5b": "L5b  east line", "L5c": "L5c  east line"}


def _dp_by_state(r: Path) -> pd.DataFrame:
    m = pd.read_parquet(r / "scenario_runs" / "F111-E" / "milp_timeseries.parquet").reset_index(drop=True)
    st = np.select([m["Q_ch_grid"] > 1, m["Q_dis"] > 1], ["charging", "discharging"], "idle")
    rows = []
    for v in ("A", "C", "B"):
        h1 = pd.read_parquet(r / "scenario_runs" / "F111-E" / f"hydraulic_timeseries_{v}.parquet").reset_index(drop=True)
        h0 = pd.read_parquet(r / "scenario_runs" / "F000-E" / f"hydraulic_timeseries_{v}.parquet").reset_index(drop=True)
        n = min(len(h0), len(h1), len(m))
        dd = h1["dp_KWK"].to_numpy()[:n] - h0["dp_KWK"].to_numpy()[:n]
        for s in ("charging", "discharging", "idle"):
            sel = st[:n] == s
            rows.append({"variant": v, "state": s, "hours": int(sel.sum()), "mean": float(dd[sel].mean())})
    return pd.DataFrame(rows)


def fig_pressure(r: Path, out: Path):
    h0 = pd.read_parquet(r / "scenario_runs" / "F000-E" / "hydraulic_timeseries_A.parquet")
    h1 = pd.read_parquet(r / "scenario_runs" / "F111-E" / "hydraulic_timeseries_A.parquet")
    rev = _j(r / "scenario_runs" / "F111-E" / "annual_metrics.json")["hydraulics"]["A"]["flow_reversals_vs_F000_h"]
    fig = plt.figure(figsize=(W2, 72 * MM))
    ax = fig.add_axes([0.065, 0.19, 0.33, 0.7])
    n = np.arange(1, len(h0) + 1)
    y0 = np.sort(h0["dp_KWK"].to_numpy())[::-1]
    y1 = np.sort(h1["dp_KWK"].to_numpy())[::-1]
    ax.axhspan(LIMIT_CHP, 7.2, color=SHADE, lw=0, zorder=0)
    ax.fill_between(n, y0, y1, color=GREEN, alpha=0.18, lw=0, zorder=1)
    ax.plot(n, y0, color=MUTED, lw=1.2, label="no TES, no partners", zorder=2)
    ax.plot(n, y1, color=GREEN, lw=1.4, label="TES + partners A, B", zorder=3)
    ax.axhline(LIMIT_CHP, color=INK, lw=0.7, ls=(0, (4, 2)), zorder=2)
    ax.text(1.15, LIMIT_CHP - 0.1, "operator experience value 4 bar", fontsize=7, color=INK2, va="top", ha="left")
    c0, c1 = int((h0["dp_KWK"] > LIMIT_CHP).sum()), int((h1["dp_KWK"] > LIMIT_CHP).sum())
    ax.annotate("", xy=(c1, LIMIT_CHP), xytext=(c0, LIMIT_CHP), arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.9,
                                                                                 mutation_scale=8), zorder=5)
    boxed(ax, 8000, 4.75, f"hours above 4 bar:\n{c0} h → {c1} h", color=INK, ha="right", va="bottom", fontsize=7.2, ec=INK)
    ax.set_xscale("log")
    ax.set_xlim(1, len(h0))
    ax.set_xticks([1, 10, 100, 1000, len(h0)], ["1", "10", "100", "1 000", k_(len(h0))])
    ax.set_ylim(0, 7.2)
    ax.set_xlabel("Hours of the year, sorted (log scale)")
    ax.set_ylabel("Required GCHP differential pressure [bar]")
    ax.legend(loc="lower left")
    label(ax, "(a)", x=-0.12)

    ax = fig.add_axes([0.47, 0.19, 0.17, 0.7])
    s = _dp_by_state(r)
    states = [("charging", "charging"), ("discharging", "dis-\ncharging"), ("idle", "idle")]
    for i, (st, lab) in enumerate(states):
        g = s[s["state"] == st].set_index("variant")
        a_ = g.at["A", "mean"]
        lo_, hi_ = g["mean"].min(), g["mean"].max()
        kw = dict(fc=GREEN_XL, ec=GREEN, lw=0.8, hatch="////") if st == "charging" else \
            (dict(fc=GREEN, ec=INK, lw=0.4) if st == "discharging" else dict(fc=GREY_L, ec=INK, lw=0.4))
        ax.bar(i, a_, width=0.6, **kw, zorder=2)
        ax.errorbar(i, a_, yerr=[[a_ - lo_], [hi_ - a_]], color=INK, lw=0.8, capsize=2.5, capthick=0.8, zorder=3)
        ax.text(i, max(hi_, 0) + 0.04 if a_ >= 0 else lo_ - 0.04, f"{a_:+.2f}" if abs(a_) >= 0.005 else "0.00", ha="center",
                va="bottom" if a_ >= 0 else "top", fontsize=7.5, fontweight="bold")
        ax.text(i, -0.42, f"{g.at['A', 'hours']:,} h".replace(",", " "), ha="center", va="top", fontsize=6.8, color=INK2)
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xticks(range(3), [x[1] for x in states], fontsize=7.2)
    ax.tick_params(axis="x", which="both", length=0)
    ax.set_xlabel("TES state")
    ax.set_ylim(-0.6, 1.15)
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylabel("Mean change in GCHP Δp [bar]")
    ax.grid(axis="x", visible=False)
    ax.text(0.97, 0.97, "calibration A\nwhisker: A, B, C", transform=ax.transAxes, ha="right", va="top", fontsize=6.6, color=INK2)
    label(ax, "(b)", x=-0.3)

    ax = fig.add_axes([0.815, 0.19, 0.16, 0.7])
    top = sorted(rev.items(), key=lambda kv: -kv[1])[:8][::-1]
    y = np.arange(len(top))
    ax.barh(y, [k[1] for k in top], height=0.6, color=GREEN, edgecolor=INK, linewidth=0.4)
    for i, (_, val) in enumerate(top):
        ax.text(val + 15, i, f"{val}", va="center", fontsize=7.2)
    ax.set_yticks(y, [EDGE_LABEL.get(k, k) for k, _ in top], fontsize=7)
    ax.tick_params(axis="y", which="both", length=0)
    ax.set_xlabel("Reversed flow [h/a]")
    ax.set_xlim(0, 1050)
    ax.set_xticks([0, 500, 1000])
    ax.grid(axis="y", visible=False)
    label(ax, "(c)", x=-0.88)
    save(fig, out, "fig3_pressure_footprint")


# --------------------------------------------------------------------------------------------- Fig. 8: economics
def fig_break_even(r: Path, out: Path, cfg: dict):
    """Break-even specific investment of the TES (value vs. A + B without TES), perfect foresight and rolling horizon
    (day-ahead forecasts) over the size grid; atmospheric tank (PF) against the DEA cost curve."""
    from .metrics import annuity_factor
    ec = cfg["economics"]
    af = annuity_factor(ec["discount_rate"], ec["lifetime_tes_a"])
    pf = pd.read_csv(r / "economics_tes_sizes.csv")
    rh = pd.read_csv(r / "rolling_horizon" / "tes_values_rh.csv")
    rh["break_even_EUR_per_m3"] = (rh["V_TES_RH_EUR"] / af - ec["tes_capex_fixed_eur"]) / rh["V_m3"]
    lo, ref, hi = (ec["tes_capex_eur_per_m3"][k] for k in ("low", "ref", "high"))
    powers = sorted(pf["Q_MW"].unique())
    cols = dict(zip(powers, ["#A9D9CC", "#5DB59C", "#179C7D", "#0B5E4B"]))
    fig, axs = plt.subplots(1, 2, figsize=(W2, 76 * MM), sharey=True, gridspec_kw={"wspace": 0.06})
    fig.subplots_adjust(left=0.075, right=0.815, bottom=0.17, top=0.9)
    refpts = {}
    for ax, d, title in ((axs[0], pf, "Perfect foresight"), (axs[1], rh, "Rolling horizon (day-ahead forecasts)")):
        ax.axhspan(lo, hi, color=SHADE, zorder=0, lw=0)
        ax.axhline(ref, color=INK2, lw=0.7, ls=(0, (4, 2)), zorder=1)
        for q in powers:
            g = d[d["Q_MW"] == q].sort_values("V_m3")
            ax.plot(g["V_m3"], g["break_even_EUR_per_m3"], marker="o", ms=4.2, color=cols[q], lw=1.3,
                    markeredgecolor=INK, markeredgewidth=0.4, zorder=3)
            if ax is axs[1]:
                ax.plot([], [], marker="o", ms=4.2, color=cols[q], lw=1.3, mec=INK, mew=0.4, label=f"{q:.0f} MW")
        g = d[(d["V_m3"] == cfg["tes"]["volume_m3"]) & (d["Q_MW"] == cfg["tes"]["Q_dis_max_MW"])].iloc[0]
        refpts[title] = g["break_even_EUR_per_m3"]
        ax.plot([g["V_m3"]], [g["break_even_EUR_per_m3"]], marker="o", ms=9, mfc="none", mec=INK, mew=1.1, ls="none", zorder=4)
        ax.set_xscale("log", base=2)
        ax.set_xticks([2500, 5000, 10000, 20000], ["2 500", "5 000", "10 000", "20 000"])
        ax.minorticks_off()
        ax.set_xlim(2100, 26000)
        ax.set_ylim(0, 2700)
        ax.set_xlabel("TES volume [m³]")
        ax.set_title(title, fontsize=8, loc="left", pad=4)
        ax.text(24500, ref + 30, f"reference cost {k_(ref)} €/m³", fontsize=7, color=INK2, va="bottom", ha="right")
        ax.text(2250, hi - 40, "pressurised-tank cost range (economic above)", fontsize=7, color=INK2, va="top")
    v_pf, v_rh = refpts["Perfect foresight"], refpts["Rolling horizon (day-ahead forecasts)"]
    boxed(axs[0], 2300, 180, "reference TES\n5\u2009000 m³, 40 MW\n" + f"{k_(v_pf)} €/m³", ha="left", va="bottom",
          ec=INK, fontsize=7.2)
    axs[0].annotate("", xy=(5000 * 0.95, v_pf - 60), xytext=(3500, 560), arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
    boxed(axs[1], 5000 * 1.12, v_rh + 330, f"{k_(v_rh)} €/m³\n({100 * (v_rh / v_pf - 1):+.0f} % vs. PF)", ha="left",
          va="bottom", ec=INK, fontsize=7.2)
    axs[1].annotate("", xy=(5000, v_rh + 60), xytext=(5000, v_pf), arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.9,
                                                                                    mutation_scale=8))
    axs[1].plot([5000], [v_pf], marker="o", ms=4, mfc="white", mec=INK2, mew=0.7, zorder=5)
    atp = r / "sensitivities" / "AT" / "summary.csv"
    if atp.exists():
        f = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
        at = pd.read_csv(atp)
        at["V"] = at["case"].str.extract(r"_V(\d+)_").astype(float)
        at["Q"] = at["case"].str.extract(r"_Q(\d+)").astype(float)
        at = at[(at["Q"] == 40) & (at["V"] <= 20000)].sort_values("V")
        be = ((f.at["F110", "C_E"] - at["C_E"]) / af - ec["tes_capex_fixed_eur"]) / at["V"]
        axs[0].plot(at["V"], be, marker="D", ms=4, ls=(0, (3, 2)), color=TURQ_D, lw=1.1, mec=INK, mew=0.4, zorder=3)
        dea = 3055.0 * at["V"] ** -0.309
        axs[0].plot(at["V"], dea, marker="_", ms=11, mew=1.6, ls="none", color=TURQ_D, zorder=3)
        axs[1].plot([], [], marker="D", ms=4, ls=(0, (3, 2)), color=TURQ_D, lw=1.1, mec=INK, mew=0.4,
                    label="atmospheric tank\n$\\leq$ 95 °C, 40 MW, PF")
        axs[1].plot([], [], marker="_", ms=11, mew=1.6, ls="none", color=TURQ_D, label="its DEA cost")
    axs[0].set_ylabel("Break-even specific investment [€/m³]")
    axs[1].legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), title="charge/discharge\npower", title_fontsize=7.5,
                  alignment="left", fontsize=7.2)
    label(axs[0], "(a)", x=-0.13)
    label(axs[1], "(b)", x=-0.02)
    save(fig, out, "fig4_break_even_investment")


# --------------------------------------------------------------------------------------------- Fig. 6: hosting
def fig_hosting(r: Path, out: Path):
    """South hosting capacity without new capacity: undelivered heat (pump-curve limits and GCHP <= 4 bar), redispatch
    cost and TES value vs. demand growth."""
    p = r / "hosting" / "summary.csv"
    if not p.exists():
        return
    s = pd.read_csv(p)
    f = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
    base = {"F000": dict(color=MUTED, marker="o", ls="-", mfc=MUTED, label="no TES"),
            "F001_S": dict(color=GREEN, marker="o", ls="-", mfc="white", label="TES at site S (5 000 m³, 40 MW)"),
            "F001_south": dict(color=TURQ_D, marker="^", ls=(0, (5, 2)), mfc="white", label="TES at the south end (5 000 m³, 40 MW)"),
            "F001_south_V20000_Q80": dict(color=TURQ_D, marker="s", ls="none", mfc=TURQ_D, label="TES at the south end (20 000 m³, 80 MW)")}
    today = {"F000": (0.0, 0.0), "F001_S": (f.at["F001", "dC_hyd_A"], f.at["F000", "C_H_A"] - f.at["F001", "C_H_A"])}
    fig, axs = plt.subplots(2, 2, figsize=(W2, 128 * MM))
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.2, top=0.955, wspace=0.26, hspace=0.42)

    def curve(ax, v, col, st, add_today=None, scale=1.0):
        g = s[s["variant"] == v].sort_values("share").dropna(subset=[col])
        if g.empty:
            return
        x, y = list(g["share"] * 100), list(g[col] * scale)
        if add_today is not None:
            x, y = [0.0] + x, [add_today * scale] + y
        ax.plot(x, y, color=st["color"], marker=st["marker"], ls=st["ls"], ms=4.6, lw=1.4, mfc=st["mfc"], mec=st["color"],
                mew=1.0, zorder=3)
        for _, rw in g[g["max_violation_H_bar"] > 0.05].iterrows():
            ax.text(rw["share"] * 100 + 0.6, rw[col] * scale, "*", color=st["color"], fontsize=10, va="center", fontweight="bold")

    def limit(ax, v, st, row):
        g = s[s["variant"] == v]
        ok, bad = g[g["unserved_H_MWh"] < 0.01]["share"], g[g["unserved_H_MWh"] >= 0.01]["share"]
        if ok.empty or bad.empty or bad.min() < ok.max():
            return
        hc = ok.max() * 100
        y1 = ax.get_ylim()[1]
        ax.plot([hc, hc], [0, y1 * (0.9 - 0.13 * row)], color=st["color"], lw=0.9, ls=(0, (2, 1.5)), zorder=2)
        boxed(ax, hc, y1 * (0.9 - 0.13 * row), f"+{hc:g} %", color=st["color"] if st["color"] != MUTED else INK, ha="center",
              va="bottom", fontsize=7.5, fontweight="bold", ec=st["color"])

    for ax, suffix, title in ((axs[0, 0], "", "Pump-curve limits (reference)"), (axs[0, 1], "_kwk4", "GCHP Δp $\\leq$ 4 bar enforced")):
        for v, st in base.items():
            curve(ax, v + suffix, "unserved_peak_H_MW", st)
        ax.set_ylim(0, 31)
        for row, v in enumerate(("F000", "F001_S", "F001_south")):
            limit(ax, v + suffix, base[v], row)
        ax.set_title(title, loc="left", fontsize=8, pad=4)
        ax.set_ylabel("Peak heat not deliverable\nto new customers [MW]")
    ax = axs[1, 0]
    for v, st in base.items():
        curve(ax, v, "dC_hyd_excl", st, add_today=today[v][0] if v in today else None, scale=1e-6)
    ax.set_ylabel("Cost of hydraulic feasibility\n(redispatch) [M€/a]")
    ax.set_ylim(0, None)
    ax = axs[1, 1]
    for v, st in base.items():
        if v != "F000":
            curve(ax, v, "value_vs_F000_H", st, add_today=today[v][1] if v in today else None, scale=1e-3)
    ax.set_ylabel("Value of the TES vs. no TES,\nequal delivered heat [k€/a]")
    ax.set_ylim(0, 540)
    boxed(ax, 16, 505, "market value at S", color=GREEN, ha="center", va="center", fontsize=7.2)
    boxed(ax, 33.5, 245, "grid value in the south", color=TURQ_D, ha="right", va="center", fontsize=7.2)
    for i, a in enumerate(axs.flat):
        a.set_xlabel("Additional south demand [% of today's total demand]")
        a.set_xlim(-1, 37)
        a.set_xticks([0, 5, 10, 15, 20, 25, 30, 35])
        a.minorticks_on()
        a.tick_params(axis="x", which="minor", bottom=False, top=False)
        label(a, f"({'abcd'[i]})", x=-0.1)
    h = [Line2D([], [], color=st["color"], marker=st["marker"], ls=st["ls"], ms=4.6, lw=1.4, mfc=st["mfc"], mec=st["color"])
         for st in base.values()]
    fig.legend(h, [st["label"] for st in base.values()], loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.055),
               columnspacing=2.2)
    fig.text(0.5, 0.012, "No new capacity: heat the existing network cannot deliver to the new south customers within the hydraulic "
             "limits is counted as unserved (perfect foresight, Mode H).\nBoxed values: hosting limit (last growth level without "
             "unserved heat).  * remaining violation 0.05–0.44 bar in $\\leq$ 2 h.", fontsize=6.8, color=INK2, ha="center",
             va="bottom", linespacing=1.3)
    save(fig, out, "fig5_south_hosting")


# --------------------------------------------------------------------------------------------- Fig. 7: validation
def _node_labels() -> dict:
    """Anonymised labels of the cross-check nodes (station codes; plant nodes by their new plant labels)."""
    from .. import netzmodell as nm
    st = {nm.STATIONEN[v]: lab for v, lab in (("V12", "V12 city"), ("V03", "V03 city centre"), ("V23", "V23 trunk L1"),
                                              ("V15", "V15"), ("V06", "V06 south end"))}
    return {**st, "S": "site S", **{k: v for k, v in PLANT.items() if k != "KWK"}}


def fig_validation(r: Path, out: Path):
    """pandapipes cross-check of the hydraulic states (today's Mode E/H schedules and the +20 % Mode H schedule)."""
    d = pd.read_csv(r / "pandapipes" / "pandapipes_hours.csv").dropna(subset=["dp_pandapipes"])
    d = d[d["case"].isin(["F000-E", "F111-E", "F111-H", "L20 F111-H"])].copy()
    d["err"] = d["dp_pandapipes"] - d["dp_ersatznetz"]
    laws = (("nikuradse", MUTED, "same friction law"), ("swamee-jain", TURQ_D, "Reynolds-dependent friction"))
    fig = plt.figure(figsize=(W2, 72 * MM))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.25, 0.95], wspace=0.5, left=0.065, right=0.975, bottom=0.17, top=0.9)
    ax = fig.add_subplot(gs[0])
    lim = [0, np.ceil(max(d["dp_ersatznetz"].max(), d["dp_pandapipes"].max()))]
    ax.plot(lim, lim, color=INK, lw=0.6, zorder=1)
    for m, c, lab in laws:
        g = d[d["model"] == m]
        ax.scatter(g["dp_ersatznetz"], g["dp_pandapipes"], s=3.5, color=c, alpha=0.55, linewidths=0, zorder=2, label=lab)
    ax.set_xlim(lim), ax.set_ylim(lim)
    ax.set_xticks(np.arange(0, lim[1] + 1, 4)), ax.set_yticks(np.arange(0, lim[1] + 1, 4))
    ax.set_aspect("equal")
    ax.set_xlabel("Δp, network model [bar]")
    ax.set_ylabel("Δp, pandapipes [bar]")
    ax.legend(loc="upper left", markerscale=3, handletextpad=0.3, fontsize=7)
    ins = ax.inset_axes([0.55, 0.08, 0.42, 0.42])
    for m, c, lab in laws:
        g = d[d["model"] == m]
        ins.scatter(g["dp_ersatznetz"], g["dp_pandapipes"], s=3, color=c, alpha=0.6, linewidths=0)
    ins.plot([0.5, 2.5], [0.5, 2.5], color=INK, lw=0.5)
    ins.set_xlim(0.6, 2.2), ins.set_ylim(0.6, 2.2)
    ins.tick_params(labelsize=6, length=1.5)
    ins.grid(False)
    ax.indicate_inset_zoom(ins, edgecolor=INK2, lw=0.5)
    label(ax, "(a)", x=-0.14)
    ax = fig.add_subplot(gs[1])
    bins = np.arange(0, lim[1] + 1.0, 1.0)
    for m, c, lab in laws:
        g = d[d["model"] == m]
        ax.scatter(g["dp_ersatznetz"], g["err"], s=2.5, color=c, alpha=0.18, linewidths=0, zorder=1)
        cut = pd.cut(g["dp_ersatznetz"], bins)
        cnt = g.groupby(cut, observed=True)["err"].size()
        q = g.groupby(cut, observed=True)["err"].quantile([0.05, 0.5, 0.95]).unstack()[cnt >= 20]
        xc = np.array([iv.mid for iv in q.index])
        ax.fill_between(xc, q[0.05], q[0.95], color=c, alpha=0.28, lw=0, zorder=2)
        ax.plot(xc, q[0.5], color=c, lw=1.4, zorder=3, label=f"{lab}: median, P5–P95")
    ax.axhline(0, color=INK, lw=0.6)
    for yv in (-0.1, 0.1):
        ax.axhline(yv, color=INK2, lw=0.5, ls=(0, (3, 2)))
    ax.set_xlim(lim)
    ax.set_ylim(-0.42, 0.38)
    ax.set_xlabel("Δp, network model [bar]")
    ax.set_ylabel("Deviation pandapipes − model [bar]")
    NODE_LABEL = _node_labels()
    from .hydraulics import node_of
    south = node_of("station:V06")
    sw = d[d["model"] == "swamee-jain"]
    imax = sw["err"].abs().idxmax()
    ax.annotate(f"max {sw.loc[imax, 'err']:+.2f} bar at {NODE_LABEL.get(sw.loc[imax, 'node'], sw.loc[imax, 'node'])}\n(low-flow hours)",
                xy=(sw.loc[imax, "dp_ersatznetz"], sw.loc[imax, "err"]), xytext=(2.4, 0.3), fontsize=6.8, va="center",
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5))
    nh = k_(d.groupby("model").size().iloc[0])
    ax.legend(loc="lower left", fontsize=6.6, handlelength=1.4, ncol=1, borderaxespad=0.2)
    ax.set_title(f"{d['case'].nunique()} schedules, {nh} node-hours", loc="right", fontsize=7, color=INK2, pad=4)
    label(ax, "(b)", x=-0.12)
    ax = fig.add_subplot(gs[2])
    sw = sw.assign(a=sw["err"].abs())
    q = sw.groupby("node")["a"].agg(p95=lambda x: x.quantile(0.95), mx="max").sort_values("p95")
    y = np.arange(len(q))
    colors = [GREEN if n == south else (TURQ_D if n == "S" else GREY_L) for n in q.index]
    ax.barh(y, q["p95"], height=0.6, color=colors, edgecolor=INK, lw=0.4, zorder=2)
    ax.plot(q["mx"], y, "|", color=INK, ms=6, mew=1.0, zorder=3)
    ax.set_yticks(y, [NODE_LABEL.get(n, n) for n in q.index], fontsize=7)
    ax.tick_params(axis="y", which="both", length=0)
    ax.set_xlabel("|Deviation| [bar]: bar P95, tick max")
    ax.set_xlim(0, 0.42)
    ax.grid(axis="y", visible=False)
    ax.set_title("Reynolds-dependent, per node", loc="left", fontsize=7.5, pad=4)
    for n_, txt_ in ((south, "sets the GCHP Δp"), ("S", "largest")):
        if n_ in q.index:
            i_ = list(q.index).index(n_)
            ax.text(q.loc[n_, "mx"] + 0.012, i_, txt_, va="center", fontsize=6.6, color=INK2)
    label(ax, "(c)", x=-0.42)
    save(fig, out, "fig6_hydraulic_validation")


# --------------------------------------------------------------------------------------------- Fig. 4: prosumers
def _ranges(ax, ref, rows, color, light, xmax):
    """Driver range plot: per driver a light band from the lowest to the highest value, one labelled marker per setting,
    the reference as a vertical line."""
    y = np.arange(len(rows))[::-1]
    for yy, (driver, items) in zip(y, rows):
        vals = [v for _, v in items] + [ref]
        ax.add_patch(plt.Rectangle((min(vals), yy - 0.17), max(vals) - min(vals), 0.34, fc=light, ec="none", zorder=1))
        last, below = -1e9, False
        for k, (setting, v) in enumerate(sorted(items, key=lambda it: it[1])):
            vv = min(v, xmax * 0.995)
            ax.plot([vv], [yy], marker="o", ms=4.6, mfc=color, mec=INK, mew=0.5, zorder=3)
            below = (not below) and (vv - last < 0.16 * xmax)          # close neighbour: alternate below the band
            ax.text(vv, yy - 0.24 if below else yy + 0.24, setting, ha="center", va="top" if below else "bottom",
                    fontsize=6.6, zorder=4)
            last = vv
    ax.axvline(ref, color=INK, lw=0.9, zorder=2)
    ax.text(ref, -0.82, f"ref. {ref:.0f}", ha="center", va="bottom", fontsize=6.8, fontweight="bold", zorder=5,
            bbox=dict(boxstyle="square,pad=0.12", fc="white", ec="none"))
    ax.set_yticks(y, [r_[0] for r_ in rows], fontsize=7.2)
    ax.tick_params(axis="y", which="both", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_ylim(-0.95, len(rows) - 0.25)


def fig_prosumers(r: Path, out: Path, cfg: dict):
    """(a, b) drivers of the value of partner A and partner B (each alone, perfect foresight); (c) partner-B premium
    window; (d) Shapley attribution under perfect foresight, rolling horizon, other price years and a lower gas price."""
    from .metrics import shapley
    f = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
    c0 = f.at["F000", "C_E"]
    vA, vB = (c0 - f.at["F100", "C_E"]) / 1e3, (c0 - f.at["F010", "C_E"]) / 1e3

    def sens(sid):
        p = r / "sensitivities" / sid / "summary.csv"
        return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=["case", "scenario", "C_E"])

    def val(sid, case, code, own_base=False):
        g = sens(sid)
        g = g[g["case"] == case].set_index("scenario")["C_E"]
        if code not in g:
            return None
        base = g["F000"] if own_base else c0
        return (base - g[code]) / 1e3

    pr, pg = "PR", "PG"
    A = [("HP size (ref. 5 MW)", [("2.5 MW", val(pr, "hp2.5", "F100")), ("10 MW", val(pr, "hp10", "F100")), ("15 MW", val(pr, "hp15", "F100"))]),
         ("Source temperature (ref. 17 °C)", [("+10 K", val(pr, "Tsrc+10", "F100")), ("+20 K", val(pr, "Tsrc+20", "F100"))]),
         ("Carnot fraction (ref. 0.5)", [("0.4", val(pr, "B3_etaC0.4", "F100")), ("0.6", val(pr, "B3_etaC0.6", "F100"))]),
         ("Waste-heat volume", [("× 0.5", val(pr, "B1_scale0.5", "F100")), ("× 1.25", val(pr, "B1_scale1.25", "F100"))]),
         ("Waste-heat fee (ref. 5 €/MWh)", [("20", val("P", "piA20", "F100")), ("0", val("P", "piA0", "F100"))]),
         ("HP grid fee (ref. 38 €/MWh)", [("76", val(pr, "hp_cel76", "F100")), ("55", val(pr, "hp_cel55", "F100"))]),
         ("Gas price (ref. 48 €/MWh)", [("37", val(pg, "gas37", "F100", True)), ("42", val(pg, "gas42", "F100", True))])]
    B = [("EB size (ref. 10 MW)", [("5 MW", val(pr, "eb5", "F010")), ("20 MW", val(pr, "eb20", "F010"))]),
         ("Electricity cost (ref. 60 €/MWh)", [("73", val("BL", "cel73", "F010")), ("54", val("BL", "cel54", "F010")),
                                              ("35", val("BL", "cel35", "F010"))]),
         ("Premium $\\pi$ (ref. 10 €/MWh)", [("60", val("A4", "pi60", "F010")), ("20", val("A4", "pi20", "F010")), ("0", val("A4", "pi0", "F010"))]),
         ("Demand charge", [("full", val("A5", "high_full", "F010"))]),
         ("Gas price (ref. 48 €/MWh)", [("37", val(pg, "gas37", "F010", True)), ("42", val(pg, "gas42", "F010", True))])]
    A = [(dname, [(s_, v_) for s_, v_ in it if v_ is not None]) for dname, it in A]
    B = [(dname, [(s_, v_) for s_, v_ in it if v_ is not None]) for dname, it in B]
    A = sorted(A, key=lambda kv: -(max(v for _, v in kv[1]) - min(v for _, v in kv[1]) if kv[1] else 0))
    B = sorted(B, key=lambda kv: -(max(v for _, v in kv[1]) - min(v for _, v in kv[1]) if kv[1] else 0))

    fig = plt.figure(figsize=(W2, 136 * MM))
    ax = fig.add_axes([0.205, 0.585, 0.285, 0.37])
    _ranges(ax, vA, A, ORANGE, ORANGE_L, 175)
    ax.set_xlim(0, 175)
    ax.set_xlabel("Value of partner A (HP) alone [k€/a]")
    flabel(fig, ax, "(a)", 0.005)
    ax = fig.add_axes([0.70, 0.585, 0.285, 0.37])
    low = val("A5", "low_none", "F010")
    _ranges(ax, vB, B, BLUE, BLUE_L, 130)
    ax.set_xlim(-4, 130)
    if low is not None:
        yy = len(B) - 1 - [n for n, _ in B].index("Electricity cost (ref. 60 €/MWh)")
        ax.annotate("", xy=(130, yy), xytext=(119, yy), arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=0.9, mutation_scale=8))
        ax.text(128, yy - 0.26, f"12 €/MWh: {low:.0f}", ha="right", va="top", fontsize=6.6, color=BLUE)
    ax.set_xlabel("Value of partner B (EB) alone [k€/a]")
    flabel(fig, ax, "(b)", 0.5)

    ax = fig.add_axes([0.075, 0.075, 0.38, 0.38])
    a4 = sens("A4")
    c101 = a4[a4["case"] == "ref_F101"]["C_E"].iloc[0]
    rows = []
    for case in [c for c in a4["case"].unique() if c.startswith("pi")]:
        g = a4[a4["case"] == case].set_index("scenario")
        p_ = float(case[2:])
        rows.append((p_, (c101 - g.at["F111", "C_E"]) / 1e3, p_ * g.at["F111", "B_heat_GWh"]))
    b = pd.DataFrame(rows, columns=["pi", "vB", "rev"]).sort_values("pi")
    ax.axvspan(10, 20, color=SHADE, lw=0, zorder=0)
    ax.text(15, 2, "negotiation\nwindow", ha="center", va="bottom", fontsize=6.8, color=INK2)
    ax.plot(b["pi"], b["vB"] + b["rev"], color=INK2, lw=1.0, ls=(0, (4, 2)), label="joint surplus")
    ax.plot(b["pi"], b["vB"], marker="o", ms=4, color=INK, mfc="white", label="net saving of the operator")
    ax.plot(b["pi"], b["rev"], marker="s", ms=4, color=BLUE, label="premium revenue of partner B")
    ax.set_xlabel("Heat-purchase premium $\\pi$ [€/MWh]")
    ax.set_ylabel("Annual value [k€/a]")
    ax.set_xlim(0, 62), ax.set_ylim(0, 60)
    ax.legend(loc="upper right", fontsize=7)
    flabel(fig, ax, "(c)", 0.005)

    ax = fig.add_axes([0.70, 0.075, 0.285, 0.38])
    sh = _j(r / "scenario_runs" / "shapley.json")["E"]["phi"]
    bars = [("PF, 2025", sh)]
    rhs = r / "rolling_horizon" / "shapley_rh.json"
    if rhs.exists():
        bars.append(("RH, 2025", _j(rhs)["phi"]))
    for sid, case, name in (("B2", "prices2024", "PF, 2024 prices"), ("B2", "prices2023", "PF, 2023 prices"),
                            ("PG", "gas37", "PF, gas 37 €/MWh")):
        g = sens(sid)
        g = g[g["case"] == case].set_index("scenario")["C_E"]
        if len(g) == 8:
            bars.append((name, shapley(g.to_dict())["phi"]))
    yb = np.arange(len(bars))[::-1]
    for (name, ph), yy in zip(bars, yb):
        left = 0.0
        for key, col in (("TES", GREEN), ("A", ORANGE), ("B", BLUE)):
            ax.barh(yy, ph[key] / 1e3, left=left, color=col, height=0.6, edgecolor=INK, linewidth=0.4)
            left += ph[key] / 1e3
        share = (ph["A"] + ph["B"]) / sum(ph.values())
        ax.text(left + 10, yy, f"A + B: {100 * share:.0f} %", va="center", fontsize=7.2,
                fontweight="bold" if name.startswith("RH") else "normal")
    ax.set_yticks(yb, [b_[0] for b_ in bars], fontsize=7.2)
    ax.tick_params(axis="y", which="both", length=0)
    ax.set_xlabel("Shapley value [k€/a]")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 800)
    ax.legend(handles=[Patch(fc=GREEN, ec=INK, lw=0.4, label="TES"), Patch(fc=ORANGE, ec=INK, lw=0.4, label="A (HP)"),
                       Patch(fc=BLUE, ec=INK, lw=0.4, label="B (EB)")], loc="lower center", ncol=3, columnspacing=0.9,
              handlelength=1.1, bbox_to_anchor=(0.5, 1.0))
    flabel(fig, ax, "(d)", 0.5)
    save(fig, out, "fig7_prosumers")


def main():
    style()
    cfg = C.load()
    r = C.root() / cfg["paths"]["results"]
    out = r / "paper_figures"
    fig_value(r, out)
    info = fig_operation(r, out)
    fig_pressure(r, out)
    fig_break_even(r, out, cfg)
    fig_hosting(r, out)
    fig_validation(r, out)
    if (r / "sensitivities" / "PR" / "summary.csv").exists():
        fig_prosumers(r, out, cfg)
    print("figures in", out, info)


if __name__ == "__main__":
    main()
