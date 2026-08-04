"""Figure library. Every function writes results/figures/<name>.html (+ .svg with kaleido)."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from .config import CFG, FIG_DIR, res_step
from .data import Inputs
from .fca import build_grid_limit
from .model import slice_horizon

C = dict(base="#9ecae1", hp="#08519c", eb="#e6550d", gas="#7f7f7f",
         tes_ch="#2ca02c", tes_dis="#98df8a", bes_ch="#7d3ac1", bes_dis="#c5b0d5",
         grid="#111111", limit="#c00000", price="#f6a600", soc="#7d3ac1",
         restricted="#c00000", flex="#2ca02c")
SCEN_COLOR = {"S0_BASE": "#7f7f7f", "S1_NOSTOR": "#c00000", "S2_TES": "#2ca02c",
              "S3_BES": "#7d3ac1", "S4_TES_BES": "#08519c"}
FCA_COLOR = {"FCA_FIRM": "#111111", "FCA_UPGRADE": "#9ecae1", "FCA_STATIC": "#7f7f7f",
             "FCA_WINDOW": "#08519c", "FCA_WINDOW_WIDE": "#6baed6", "FCA_DYNAMIC": "#e6550d",
             "FCA_TDTR": "#2ca02c"}

pio.templates.default = "plotly_white"
_t = pio.templates["plotly_white"]
_t.layout.font = dict(family="Arial", size=13, color="#222222")
_t.layout.xaxis.update(showline=True, linewidth=1, linecolor="#444", mirror=True,
                       ticks="outside", gridcolor="#e8e8e8")
_t.layout.yaxis.update(showline=True, linewidth=1, linecolor="#444", mirror=True,
                       ticks="outside", gridcolor="#e8e8e8")
PLOT_CONFIG = {"displaylogo": False, "toImageButtonOptions": {"format": "svg", "scale": 2}}
IN_NOTEBOOK = "ipykernel" in sys.modules


def show(fig, name: str, w: int = 1100, h: int = 520):
    fig.update_layout(width=w, height=h, margin=dict(l=70, r=30, t=60, b=60),
                      legend=dict(orientation="h", y=-0.18, x=0), title_x=0.0)
    fig.write_html(FIG_DIR / f"{name}.html", include_plotlyjs="cdn")
    try:
        fig.write_image(FIG_DIR / f"{name}.svg")
    except Exception:
        pass
    if IN_NOTEBOOK:
        fig.show(config=PLOT_CONFIG)
    return fig


def _blocks(mask, index):
    """Contiguous True runs of `mask` as (start, end) timestamps — for shading."""
    out, run = [], None
    for i, v in enumerate(mask):
        if v and run is None:
            run = index[i]
        elif not v and run is not None:
            out.append((run, index[i])); run = None
    if run is not None:
        out.append((run, index[-1]))
    return out


def fig_demand_overview(inp: Inputs, year=None):
    year = year or CFG["years"][0]
    sites = list(inp.sites["site_id"])
    names = dict(zip(inp.sites["site_id"], inp.sites["site_name"]))
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5],
                        vertical_spacing=0.10,
                        subplot_titles=("Electricity demand — monthly mean [MW]",
                                        "Heat demand — monthly mean [MW<sub>th</sub>]"))
    pal = ["#08519c", "#e6550d", "#2ca02c", "#7d3ac1", "#c00000"]
    for i, s in enumerate(sites):
        e = inp.el.loc[inp.el.index.year == year, s].resample("ME").mean()
        q = inp.heat.loc[inp.heat.index.year == year, s].resample("ME").mean()
        fig.add_trace(go.Scatter(x=e.index, y=e, name=names[s], line=dict(color=pal[i], width=2),
                                 legendgroup=s), row=1, col=1)
        fig.add_trace(go.Scatter(x=q.index, y=q, name=names[s], line=dict(color=pal[i], width=2),
                                 legendgroup=s, showlegend=False), row=2, col=1)
    fig.update_layout(title=f"Site demand profiles ({year})")
    return show(fig, "F1_demand_overview", h=680)


def fig_duration_curves(inp: Inputs, year=None):
    year = year or CFG["years"][0]
    names = dict(zip(inp.sites["site_id"], inp.sites["site_name"]))
    pal = ["#08519c", "#e6550d", "#2ca02c", "#7d3ac1", "#c00000"]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Electricity", "Heat"))
    for i, s in enumerate(inp.sites["site_id"]):
        for c, (src, col) in enumerate([(inp.el, 1), (inp.heat, 2)]):
            y = np.sort(src.loc[src.index.year == year, s].to_numpy())[::-1]
            x = np.arange(1, len(y) + 1) * 0.25
            fig.add_trace(go.Scatter(x=x, y=y, name=names[s], line=dict(color=pal[i], width=2),
                                     legendgroup=s, showlegend=(col == 1)), row=1, col=col)
    fig.update_xaxes(title_text="hours per year [h]")
    fig.update_yaxes(title_text="power [MW]", row=1, col=1)
    fig.update_layout(title=f"Load duration curves ({year})")
    return show(fig, "F2_duration_curves", h=460)


def fig_archetype_scatter(inp: Inputs):
    """F2b — load factor against heat-to-power ratio, one marker per site, size = annual heat.

    The go/no-go on the multi-site framing: if the five sites cluster here, the paper cannot be
    carried by cross-site variation and must be restructured around one site with a parameter
    sweep (see FIGURES.md). Build and read this the moment real profiles land."""
    s = inp.sites.copy()
    pal = ["#08519c", "#e6550d", "#2ca02c", "#7d3ac1", "#c00000"]
    # annual heat demand [GWh_th], robust to the series' calendar span
    heat_gwh = np.array([inp.heat[sid].mean() * 8760.0 / 1000.0 for sid in s["site_id"]])
    lf = s["load_factor"].to_numpy()
    htp = s["heat_to_power"].to_numpy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=lf, y=htp, mode="markers+text",
        text=s["site_name"], textposition="top center",
        textfont=dict(size=11),
        marker=dict(size=heat_gwh, sizemode="area",
                    sizeref=2.0 * max(heat_gwh.max(), 1e-9) / (46.0 ** 2), sizemin=6,
                    color=pal[:len(s)], line=dict(width=1, color="#333")),
        customdata=np.stack([s["sector"], heat_gwh], axis=-1),
        hovertemplate=("<b>%{text}</b><br>sector: %{customdata[0]}<br>"
                       "load factor: %{x:.2f}<br>heat/power: %{y:.2f}<br>"
                       "annual heat: %{customdata[1]:.1f} GWh<extra></extra>")))
    fig.update_layout(
        title="Site archetypes — load factor vs heat-to-power ratio (marker area = annual heat)",
        xaxis_title="load factor  ⟨P<sub>el</sub>⟩ / max P<sub>el</sub>  [–]",
        yaxis_title="heat-to-power ratio  ∑Q<sub>th</sub> / ∑E<sub>el</sub>  [–]")
    return show(fig, "F2b_archetype_scatter", h=560)


def fig_limit_profile(inp: Inputs, site: str, fcas=None, days=7, start=None):
    """The connection limit as the model sees it — the paper's explanatory figure."""
    fcas = fcas or CFG["fcas"]
    P0 = float(inp.sites.set_index("site_id").loc[site, "P_grid_exist_MW"])
    df, dt = slice_horizon(inp, site, tuple(CFG["years"]), CFG["resolution"])
    start = start or df.index[0] + pd.Timedelta(days=14)
    idx = df.loc[start:start + pd.Timedelta(days=days)].index
    fig = go.Figure()
    for fc in fcas:
        lim, free, restr, _ = build_grid_limit(inp, fc, idx, P0,
                                               df.loc[idx, "price"].to_numpy(), dt)
        if free:
            continue
        fig.add_trace(go.Scatter(x=idx, y=lim, name=fc, line_shape="hv",
                                 line=dict(color=FCA_COLOR.get(fc), width=2)))
    fig.add_trace(go.Scatter(x=idx, y=df.loc[idx, "el"], name="existing electricity demand",
                             line=dict(color=C["base"], width=1.5), fill="tozeroy"))
    fig.update_layout(title=f"Connection limit P<sub>limit</sub>(t) by regime — {site}",
                      yaxis_title="power [MW]")
    return show(fig, f"F3_limit_profile_{site}")


def fig_feasibility_matrix(kpi: pd.DataFrame):
    """Which (configuration, regime) combinations can supply 100 % of the heat demand?"""
    k = kpi[kpi["scenario"] != "S0_BASE"]
    piv = k.pivot_table(index=["scenario"], columns="fca",
                        values="unserved_share_pct", aggfunc="mean")
    fig = go.Figure(go.Heatmap(z=piv.values, x=list(piv.columns), y=list(piv.index),
                               colorscale="Reds", zmin=0,
                               colorbar=dict(title="unserved<br>heat [%]"),
                               text=np.round(piv.values, 2), texttemplate="%{text}"))
    fig.update_layout(title="Unserved heat by storage configuration and connection regime "
                            "(mean over sites)")
    return show(fig, "F4_feasibility_matrix", h=420)


def fig_storage_vs_regime(kpi: pd.DataFrame):
    k = kpi[kpi["scenario"].isin(["S2_TES", "S3_BES", "S4_TES_BES"])]
    fig = make_subplots(rows=1, cols=2, subplot_titles=("TES [MWh<sub>th</sub>]",
                                                        "BES [MWh<sub>el</sub>]"))
    for fc in k["fca"].unique():
        d = k[k["fca"] == fc]
        g = d.groupby("scenario")[["Etes_MWh", "Ebes_MWh"]].mean()
        fig.add_bar(x=g.index, y=g["Etes_MWh"], name=fc, marker_color=FCA_COLOR.get(fc),
                    legendgroup=fc, row=1, col=1)
        fig.add_bar(x=g.index, y=g["Ebes_MWh"], name=fc, marker_color=FCA_COLOR.get(fc),
                    legendgroup=fc, showlegend=False, row=1, col=2)
    fig.update_layout(barmode="group", title="Storage size required by connection regime "
                                             "(mean over sites)")
    return show(fig, "F5_storage_vs_regime", h=460)


def fig_dispatch(ts_store, site: str, scenario: str, fca: str = "FCA_WINDOW",
                 start=None, days=7):
    ts = ts_store[(site, scenario, fca)]
    start = start or ts.index[0] + pd.Timedelta(days=14)
    w = ts.loc[start:start + pd.Timedelta(days=days)]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.40, 0.34, 0.26],
                        vertical_spacing=0.06,
                        subplot_titles=("Electricity side [MW]", "Heat side [MW<sub>th</sub>]",
                                        "Storage level / price"))
    # electricity
    for col, nm, cc in [("el_base", "existing load", C["base"]), ("p_hp", "heat pump", C["hp"]),
                        ("p_eb", "electrode boiler", C["eb"]), ("bes_ch", "BES charge", C["bes_ch"])]:
        fig.add_trace(go.Scatter(x=w.index, y=w[col], name=nm, line_shape="hv", stackgroup="e",
                                 line=dict(width=0, color=cc)), row=1, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w["grid"], name="grid draw",
                             line=dict(color=C["grid"], width=2), line_shape="hv"), row=1, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w["P_limit"], name="P<sub>limit</sub>(t)",
                             line=dict(color=C["limit"], width=2, dash="dash"),
                             line_shape="hv"), row=1, col=1)
    for a, b in _blocks(w["restricted"].to_numpy(), w.index):
        fig.add_vrect(x0=a, x1=b, fillcolor=C["restricted"], opacity=0.07, line_width=0,
                      layer="below", row=1, col=1)
    # heat
    for col, nm, cc in [("q_hp", "HP heat", C["hp"]), ("q_eb", "EB heat", C["eb"]),
                        ("tes_dis", "TES discharge", C["tes_dis"])]:
        fig.add_trace(go.Scatter(x=w.index, y=w[col], name=nm, line_shape="hv", stackgroup="h",
                                 line=dict(width=0, color=cc)), row=2, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w["heat_dem"], name="heat demand",
                             line=dict(color="#111", width=2, dash="dot"), line_shape="hv"),
                  row=2, col=1)
    # storage + price
    fig.add_trace(go.Scatter(x=w.index, y=w["tes_soc"], name="TES SOC [MWh]",
                             line=dict(color=C["tes_ch"], width=2), fill="tozeroy"), row=3, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w["bes_soc"], name="BES SOC [MWh]",
                             line=dict(color=C["soc"], width=2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=w.index, y=w["price"] / 10, name="price [10 EUR/MWh]",
                             line=dict(color=C["price"], width=1.2, dash="dot")), row=3, col=1)
    fig.update_layout(title=f"Dispatch — {site} · {scenario} · {fca} · "
                            f"{start:%d %b %Y} + {days} d")
    return show(fig, f"F6_dispatch_{site}_{scenario}_{fca}", h=760)


def fig_grid_duration(ts_store, site: str, scenario="S4_TES_BES", fcas=None, inp=None):
    fcas = fcas or CFG["fcas"]
    fig = go.Figure()
    for fc in fcas:
        if (site, scenario, fc) not in ts_store:
            continue
        y = np.sort(ts_store[(site, scenario, fc)]["grid"].to_numpy())[::-1]
        x = np.arange(1, len(y) + 1) * res_step()
        fig.add_trace(go.Scatter(x=x, y=y, name=fc,
                                 line=dict(color=FCA_COLOR.get(fc), width=2)))
    if inp is not None:
        fig.add_hline(y=float(inp.sites.set_index("site_id").loc[site, "P_grid_exist_MW"]),
                      line=dict(color=C["limit"], dash="dash"),
                      annotation_text="P<sub>grid,exist</sub>")
    fig.update_layout(title=f"Grid draw duration curve — {site} · {scenario}",
                      xaxis_title="hours [h]", yaxis_title="grid draw [MW]")
    return show(fig, f"F7_grid_duration_{site}_{scenario}")


def fig_kpi_comparison(kpi: pd.DataFrame, scenario="S4_TES_BES"):
    metrics = [("Etes_MWh", "TES size [MWh]"), ("LCOH_EUR_MWh", "LCOH [EUR/MWh<sub>th</sub>]"),
               ("peak_grid_MW", "peak grid draw [MW]"),
               ("unserved_share_pct", "unserved heat [%]")]
    fig = make_subplots(rows=2, cols=2, subplot_titles=[m[1] for m in metrics],
                        vertical_spacing=0.16)
    for i, (col, _) in enumerate(metrics):
        r, c = divmod(i, 2)
        for fc in kpi["fca"].dropna().unique():
            d = kpi[(kpi["fca"] == fc) & (kpi["scenario"] == scenario)]
            fig.add_bar(x=d["site"], y=d[col], name=fc, marker_color=FCA_COLOR.get(fc),
                        legendgroup=fc, showlegend=(i == 0), row=r + 1, col=c + 1)
    fig.update_layout(barmode="group",
                      title=f"Connection regime comparison across sites — {scenario}")
    return show(fig, "F8_kpi_comparison", h=760)


def fig_cost_stack(kpi: pd.DataFrame):
    k = kpi[(kpi["scenario"] != "S0_BASE") & (kpi["fca"] == "FCA_WINDOW")].copy()
    k["x"] = k["site"] + "<br>" + k["scenario"]
    fig = go.Figure()
    for col, nm, cc in [("cost_capex_EUR", "annualised CAPEX+OPEX", C["hp"]),
                        ("cost_energy_EUR", "energy", C["eb"]),
                        ("cost_capacity_EUR", "grid capacity charge", C["base"])]:
        fig.add_bar(x=k["x"], y=k[col] / 1e6, name=nm, marker_color=cc)
    fig.update_layout(barmode="stack", title="Annual cost structure",
                      yaxis_title="cost [MEUR/a]")
    return show(fig, "F9_cost_structure", h=560)


def fig_tornado(sens: pd.DataFrame, kpi_col="Etes_MWh", label="TES size [MWh]"):
    rows = []
    for pid, g in sens.groupby("param_id"):
        g = g.sort_values("value")
        base = g.iloc[(g["value"] - g["base"]).abs().argsort()].iloc[0][kpi_col]
        rows.append(dict(param=pid, low=g.iloc[0][kpi_col] - base,
                         high=g.iloc[-1][kpi_col] - base, base=base))
    t = pd.DataFrame(rows)
    t["span"] = (t["high"] - t["low"]).abs()
    t = t.sort_values("span")
    fig = go.Figure()
    fig.add_bar(y=t["param"], x=t["low"], orientation="h", name="low", marker_color="#9ecae1")
    fig.add_bar(y=t["param"], x=t["high"], orientation="h", name="high", marker_color="#c00000")
    fig.update_layout(barmode="overlay", title=f"Sensitivity of {label}",
                      xaxis_title=f"change in {label}")
    return show(fig, f"F9_tornado_{kpi_col}", h=520)


def fig_notice_value(mpc: pd.DataFrame):
    """What a longer notification interval is worth, at identical hardware."""
    fig = go.Figure()
    for nh, g in mpc.groupby("notice_h"):
        d = g.groupby("site")["foresight_gap_MWh"].mean()
        fig.add_bar(x=d.index, y=d.values, name=f"notice {nh:g} h")
    fig.update_layout(barmode="group", yaxis_title="unserved heat above perfect foresight [MWh]",
                      title="Value of the notification interval — same design, different contract")
    return show(fig, "F12_notice_value")


def fig_restriction_bite(kpi: pd.DataFrame, scenario="S4_TES_BES"):
    """F13 — reserved restriction time against the share that actually binds.

    `restricted_share` is what the operator reserves the right to curtail; `restriction_bite_share`
    is the share of the whole year in which the limit really constrains the plant. The gap between
    them is capacity the operator reserves but never needs — the plant's strongest argument for a
    narrower agreement, and a new KPI, so it gets its own figure."""
    k = kpi[kpi["scenario"] == scenario].copy()
    k = k[k["restricted_share"] > 1e-9]                     # drop firm / upgrade (nothing reserved)
    g = k.groupby("fca")[["restricted_share", "restriction_bite_share"]].mean() * 100
    g = g.sort_values("restricted_share", ascending=False)
    fig = go.Figure()
    fig.add_bar(x=g.index, y=g["restricted_share"], name="reserved (operator right)",
                marker_color="#9ecae1")
    fig.add_bar(x=g.index, y=g["restriction_bite_share"], name="binding (actual bite)",
                marker_color="#c00000")
    fig.update_layout(barmode="group", yaxis_title="share of the year [%]",
                      title=f"Restriction bite — reserved vs binding by regime · {scenario} "
                            "(mean over sites)")
    return show(fig, "F13_restriction_bite", h=460)


def fig_block_length_vs_storage(kpi: pd.DataFrame, ts_store, site: str, scenario="S4_TES_BES"):
    """F14 — longest recurring restricted block against required thermal storage.

    The mechanism behind the paper's most surprising result: what drives storage capital is how
    long the longest recurring restricted block is, not how many hours are restricted in total. A
    predictable daily window is the worst case on that measure, so it lands high and to the right
    even when it reserves less time than a dispersed dynamic regime. Block length comes from the
    `restricted` mask via `_blocks`; the fitted line makes the correlation legible."""
    xs, ys, cs, names = [], [], [], []
    for fc in CFG["fcas"]:
        if (site, scenario, fc) not in ts_store:
            continue
        mask = ts_store[(site, scenario, fc)]["restricted"].to_numpy().astype(bool)
        idx = ts_store[(site, scenario, fc)].index
        if not mask.any():
            continue                                        # firm / upgrade: no block to bridge
        blocks = _blocks(mask, idx)
        longest = max((b - a).total_seconds() / 3600.0 for a, b in blocks)
        row = kpi[(kpi["site"] == site) & (kpi["scenario"] == scenario) & (kpi["fca"] == fc)]
        if row.empty:
            continue
        xs.append(longest); ys.append(float(row["Etes_MWh"].iloc[0]))
        cs.append(FCA_COLOR.get(fc)); names.append(fc)
    fig = go.Figure()
    if len(xs) >= 2:                                        # least-squares trend line
        m, c = np.polyfit(xs, ys, 1)
        xl = np.array([min(xs), max(xs)])
        fig.add_trace(go.Scatter(x=xl, y=m * xl + c, mode="lines", name="fit",
                                 line=dict(color="#888", width=1.5, dash="dash")))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=names,
                             textposition="top center", textfont=dict(size=10),
                             marker=dict(size=13, color=cs, line=dict(width=1, color="#333")),
                             showlegend=False))
    fig.update_layout(title=f"Why windows cost more — {site} · {scenario}",
                      xaxis_title="longest recurring restricted block [h]",
                      yaxis_title="required TES [MWh<sub>th</sub>]")
    return show(fig, f"F14_block_length_vs_storage_{site}_{scenario}", h=520)


def fig_sensitivity_grid(grid: pd.DataFrame, z_col="bes_share",
                         z_label="BES share of storage [–]"):
    """F15 — two-way sensitivity heat map over the grid from `runner.run_sensitivity_grid`.

    The default pair (TES CAPEX × day-ahead price spread) traces the boundary where the battery
    stops losing to thermal storage: BES needs cheap-enough TES to look expensive and a wide-enough
    price spread to earn arbitrage, so its share rises to the upper-left."""
    piv = grid.pivot_table(index="b", columns="a", values=z_col)
    ta = grid["target_a"].iloc[0]; tb = grid["target_b"].iloc[0]
    fig = go.Figure(go.Heatmap(z=piv.values, x=list(piv.columns), y=list(piv.index),
                               colorscale="Viridis", colorbar=dict(title=z_label),
                               hovertemplate=f"{ta} %{{x:.2f}}<br>{tb} %{{y:.2f}}<br>"
                                             f"{z_label} %{{z:.2f}}<extra></extra>"))
    fig.update_layout(title=f"Two-way sensitivity — {z_label}",
                      xaxis_title=ta, yaxis_title=tb)
    return show(fig, f"F15_sensitivity_grid_{z_col}", h=500)


def fig_year_validation(df: pd.DataFrame, metric="unserved_share_pct",
                        metric_label="unserved heat [%]"):
    """F20 — a design fixed from one year, operated over all years, one bar group per site.

    The design year is marked; the other years are the out-of-sample operation check. A design
    that only just works in its sizing year and fails elsewhere is the reviewer's worry, and this
    is where it would show. Consumes `runner.run_year_validation`."""
    fig = go.Figure()
    years = sorted(df["year"].unique())
    dyear = int(df["design_year"].iloc[0])
    pal = ["#08519c", "#e6550d", "#2ca02c", "#7d3ac1", "#c00000", "#7f7f7f"]
    for i, y in enumerate(years):
        d = df[df["year"] == y]
        label = f"{y} (design)" if y == dyear else str(y)
        fig.add_bar(x=d["site"], y=d[metric], name=label,
                    marker_color=pal[i % len(pal)],
                    marker_pattern_shape="/" if y == dyear else "")
    fig.update_layout(barmode="group", yaxis_title=metric_label,
                      title=f"Design year vs operation years — sized on {dyear}")
    return show(fig, f"F20_year_validation_{metric}", h=480)


def fig_hp_eb_split(kpi: pd.DataFrame, inp: Inputs, scenario="S4_TES_BES", fca="FCA_WINDOW"):
    """F17 — heat supplied by heat pump vs electrode boiler, sites ordered by supply temperature.

    The 160 °C admissibility gate (`HP.T_sink_max_C`) is why the high-temperature sites lean on the
    electrode boiler; ordering by supply temperature makes that visible and justifies the gate."""
    tsup = inp.sites.set_index("site_id")["T_supply_C"]
    tmax = float(inp.par("HP", "T_sink_max_C", 160))
    k = kpi[(kpi["scenario"] == scenario) & (kpi["fca"] == fca)].copy()
    k["T_supply_C"] = k["site"].map(tsup)
    k = k.sort_values("T_supply_C")
    k["hp_heat"] = k["hp_share"] * k["E_heat_MWh"] / 1000.0            # GWh_th
    k["eb_heat"] = (1 - k["hp_share"]) * k["E_heat_MWh"] / 1000.0
    x = [f"{s}<br>{t:.0f} °C" for s, t in zip(k["site"], k["T_supply_C"])]
    fig = go.Figure()
    fig.add_bar(x=x, y=k["hp_heat"], name="heat pump", marker_color=C["hp"])
    fig.add_bar(x=x, y=k["eb_heat"], name="electrode boiler", marker_color=C["eb"])
    admissible = (k["T_supply_C"] <= tmax).all()
    note = (f"all sites ≤ {tmax:.0f} °C HP-admissible" if admissible
            else f"sites &gt; {tmax:.0f} °C fall to the electrode boiler")
    fig.add_annotation(x=1.0, xref="paper", y=1.06, yref="paper", showarrow=False,
                       xanchor="right", text=note, font=dict(size=11, color="#555"))
    fig.update_layout(barmode="stack", yaxis_title="annual heat supplied [GWh<sub>th</sub>]",
                      title=f"Technology split by supply temperature · {scenario} · {fca}")
    return show(fig, "F17_hp_eb_split", h=480)


def fig_co2_accounting(kpi: pd.DataFrame, scenario_filter=None):
    """F18 — certificate CO₂ against physical CO₂, baseline and each configuration.

    Makes the biomethane-certificate assumption visible instead of buried: points on the diagonal
    account the same either way; the biomethane baseline sits below it, because the certificate
    zeroes emissions that are physically still emitted. Pre-empts the obvious reviewer objection."""
    k = kpi.copy()
    if scenario_filter:
        k = k[k["scenario"].isin(list(scenario_filter) + ["S0_BASE"])]
    hi = float(np.nanmax([k["CO2_phys_t"].max(), k["CO2_cert_t"].max()])) * 1.05
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, hi], y=[0, hi], mode="lines", name="cert = physical",
                             line=dict(color="#888", width=1.2, dash="dash")))
    for sc in k["scenario"].unique():
        d = k[k["scenario"] == sc]
        fig.add_trace(go.Scatter(x=d["CO2_phys_t"], y=d["CO2_cert_t"], mode="markers",
                                 name=sc, marker=dict(size=11, color=SCEN_COLOR.get(sc, "#333"),
                                 line=dict(width=1, color="#333"),
                                 symbol="diamond" if sc == "S0_BASE" else "circle"),
                                 hovertext=d["site"]))
    fig.update_layout(xaxis_title="physical CO₂ [t]", yaxis_title="certificate CO₂ [t]",
                      title="Two carbon accountings — certificate vs physical emissions")
    return show(fig, "F18_co2_accounting", h=520)


def fig_seed_robustness(df: pd.DataFrame, site: str, scenario="S4_TES_BES"):
    """F19 — required TES across many operator-call seeds, one box per dynamic regime.

    The dynamic-regime storage results depend on a proxy for when the operator calls a
    restriction; this figure shows how tightly the required storage clusters across seeds, which
    is what makes those results defensible. Consumes `runner.run_seed_robustness`. Do not present
    the dynamic results without it (FIGURES.md)."""
    d = df[(df["site"] == site) & (df["scenario"] == scenario)]
    fig = go.Figure()
    for fc in d["fca"].unique():
        y = d[d["fca"] == fc]["Etes_MWh"]
        fig.add_trace(go.Box(y=y, name=fc, marker_color=FCA_COLOR.get(fc), boxpoints="all",
                             jitter=0.4, pointpos=0, marker=dict(size=5),
                             line=dict(width=1.5)))
    n = int(d.groupby("fca").size().max()) if not d.empty else 0
    fig.update_layout(showlegend=False, yaxis_title="required TES [MWh<sub>th</sub>]",
                      title=f"Call-pattern robustness — {site} · {scenario} ({n} seeds/regime)")
    return show(fig, f"F19_seed_robustness_{site}_{scenario}", h=500)


def fig_contract_space(grid: pd.DataFrame, scenario: str | None = None, ncols: int = 3):
    """F11 — the contract space: which agreements a given design can accommodate.

    Background shades each (restriction width, granted uplift β) cell by feasibility; contour lines
    give the required thermal storage inside the feasible region. This is the object a plant needs
    when negotiating — a set of admissible agreements rather than one sizing number — and the
    graphical-abstract candidate. Consumes the frame from `runner.run_contract_grid`."""
    g = grid if scenario is None else grid[grid["scenario"] == scenario]
    sites = list(dict.fromkeys(g["site"]))
    n = len(sites)
    ncols = min(ncols, n)
    nrows = -(-n // ncols)
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=sites,
                        horizontal_spacing=0.09, vertical_spacing=0.14)
    # feasible = pale, infeasible = dark: separable in greyscale, not by hue alone
    feas_scale = [[0.0, "#c00000"], [0.5, "#c00000"], [0.5, "#dcecdc"], [1.0, "#dcecdc"]]
    for i, s in enumerate(sites):
        r, c = i // ncols + 1, i % ncols + 1
        d = g[g["site"] == s]
        feas = d.pivot_table(index="beta", columns="window_width_h", values="feasible")
        tes = d.pivot_table(index="beta", columns="window_width_h", values="Etes_MWh")
        tes_masked = tes.where(feas > 0.5)
        x, y = list(feas.columns), list(feas.index)
        fig.add_trace(go.Heatmap(z=feas.values.astype(float), x=x, y=y, zmin=0, zmax=1,
                                 colorscale=feas_scale, showscale=False,
                                 hovertemplate="width %{x:.1f} h<br>β %{y:.2f}<br>"
                                               "feasible %{z:.0f}<extra></extra>"),
                      row=r, col=c)
        if np.isfinite(tes_masked.values).any():
            fig.add_trace(go.Contour(z=tes_masked.values, x=x, y=y,
                                     contours=dict(coloring="lines", showlabels=True,
                                                   labelfont=dict(size=10, color="#111")),
                                     line=dict(width=1.4), colorscale="Greys", showscale=False,
                                     hovertemplate="width %{x:.1f} h<br>β %{y:.2f}<br>"
                                                   "TES %{z:.0f} MWh<extra></extra>"),
                          row=r, col=c)
        fig.update_xaxes(title_text="restriction width [h/working day]", row=r, col=c)
        fig.update_yaxes(title_text="granted uplift β [–]", row=r, col=c)
    ttl = "Contract space — feasibility (shaded) and required TES [MWh] (contours)"
    if scenario:
        ttl += f" · {scenario}"
    fig.update_layout(title=ttl)
    return show(fig, f"F11_contract_space{('_'+scenario) if scenario else ''}",
                h=340 * nrows + 80, w=380 * ncols + 120)


def fig_shadow_price(ts_store, site: str, scenario="S4_TES_BES", fcas=None):
    """F16 — dual of the connection constraint: EUR/MW value of withdrawal capacity.

    Left: duration curve of the per-interval shadow price. Right: monthly mean. Answers "what
    would this plant pay to jump the queue?" and, for the operator, "what is firm capacity worth?"
    Reads the `shadow_conn_EUR_MW` column that `solve_case` extracts from `m.dual`; requires a run
    whose time series were stored (run_batch(..., store_ts=True))."""
    fcas = fcas or CFG["fcas"]
    fig = make_subplots(rows=1, cols=2, column_widths=[0.58, 0.42],
                        subplot_titles=("Shadow price duration curve",
                                        "Monthly mean shadow price"))
    for fc in fcas:
        if (site, scenario, fc) not in ts_store:
            continue
        col = ts_store[(site, scenario, fc)].get("shadow_conn_EUR_MW")
        if col is None or not np.isfinite(col.to_numpy()).any():
            continue                              # firm regime with no active limit -> nothing to show
        sp = col.fillna(0.0)
        y = np.sort(sp.to_numpy())[::-1]
        x = np.arange(1, len(y) + 1) * res_step()
        fig.add_trace(go.Scatter(x=x, y=y, name=fc, legendgroup=fc,
                                 line=dict(color=FCA_COLOR.get(fc), width=2)), row=1, col=1)
        mm = sp.groupby(sp.index.month).mean()
        fig.add_bar(x=mm.index, y=mm.values, name=fc, legendgroup=fc, showlegend=False,
                    marker_color=FCA_COLOR.get(fc), row=1, col=2)
    fig.update_xaxes(title_text="hours [h]", row=1, col=1)
    fig.update_xaxes(title_text="month", row=1, col=2, dtick=1)
    fig.update_yaxes(title_text="shadow price [EUR/MW]", row=1, col=1)
    fig.update_layout(barmode="group",
                      title=f"Value of connection capacity — {site} · {scenario}")
    return show(fig, f"F16_shadow_price_{site}_{scenario}", h=480)
