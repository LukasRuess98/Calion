"""Paper 2 publication tables T1 & T2 (campaign-independent).

T1  Network characteristics   — nodes, pipes, peak load, annual energy,
                                generator portfolio, per network side by side.
                                Sources: the two topology YAMLs + the demand
                                xlsx (peak/energy computed from the exact
                                consumer columns each config declares).
T2  Scenario-matrix definition — compact form of the 46-run matrix
                                (family × network × heat-curve stage, TES/HP
                                node, feature flags). Source: scenarios.yaml.

Each table is written as CSV + a booktabs LaTeX snippet to results/paper2_figures/.

Usage:
    python scripts/paper_2/figures/gen_tables.py          # both
    python scripts/paper_2/figures/gen_tables.py T1        # one
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _style import FIG_DIR  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
from scripts.paper_2 import validation_p2  # noqa: E402

NETWORKS = {
    "Stadtbach": {
        "config": _ROOT / "configs" / "paper_2" / "Stadtbach_topo.yaml",
        "data": _ROOT / "data" / "Stadtbach" / "stadtbach_acron_combined_cleaned.xlsx",
    },
    "Memmingen": {
        "config": _ROOT / "configs" / "paper_2" / "Memmingen_P2_base.yaml",
        "data": _ROOT / "data" / "Import_Data_Memmingen_epronet_cleaned.xlsx",
    },
}
SCENARIOS_YAML = _ROOT / "configs" / "paper_2" / "scenarios.yaml"


# ── helpers ──────────────────────────────────────────────────────────────────
def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _nodes(cfg: dict) -> dict:
    return cfg.get("network", {}).get("nodes", {}) or {}


def _pipes(cfg: dict) -> dict:
    return cfg.get("network", {}).get("pipes", {}) or {}


def _classify_nodes(cfg: dict) -> dict[str, int]:
    """Match the model's node-type inference (Implementation Statement A.1)."""
    counts = {"producer": 0, "consumer": 0, "junction": 0, "mixed": 0}
    for spec in _nodes(cfg).values():
        spec = spec or {}
        has_a = bool(spec.get("assets"))
        has_c = bool(spec.get("consumers"))
        if has_a and has_c:
            counts["mixed"] += 1
        elif has_a:
            counts["producer"] += 1
        elif has_c:
            counts["consumer"] += 1
        else:
            counts["junction"] += 1
    return counts


def _demand_columns(cfg: dict) -> list[str]:
    cols: list[str] = []
    for spec in _nodes(cfg).values():
        for c in (spec or {}).get("consumers", []) or []:
            if c.get("column"):
                cols.append(c["column"])
    return cols


def _peak_and_energy(cfg: dict, data_path: Path) -> dict:
    """Peak [MW] and annual energy [GWh] from the summed declared demand columns.

    FIX (2026-07-20, found via a reviewer-style check on T1: Memmingen's implied
    mean load, annual_gwh*1000/8760, exceeded its own peak_mw — physically
    impossible for a system-wide metric). Two compounding bugs, both silent
    because they only matter for a raw input file that (a) is not exactly one
    calendar year and/or (b) is not hourly-sampled:
    1. This previously summed EVERY row in the raw xlsx as if it were exactly
       one calendar year. Stadtbach's file genuinely is 8760 hourly rows (one
       year), so it was never wrong there. Memmingen's raw file spans ~1.24
       years (2025-01-01 through part of 2026-03) — summing all of it and
       calling the result "annual" overstated Memmingen's annual energy.
    2. It also assumed dt=1h between rows. Memmingen's raw file is sampled
       every 15 minutes (dt=0.25h), so summing MW values directly (instead of
       MW * dt) overstated the energy integral 4x on top of bug 1.
    Fix: infer the true dt from the datetime column (median row-to-row gap,
    robust to either network's native resolution) and restrict to the same
    `scenario.horizon.start/end` calendar window the actual MILP solves use
    (`cfg["site"]["columns"]["datetime"]` names the column, default "Datum")
    — so this table describes exactly the same year the model optimizes
    over, not an arbitrary raw-file span. A no-op for Stadtbach (whole file
    already is exactly one year at dt=1h, no horizon override present).
    """
    cols = _demand_columns(cfg)
    out = {"peak_mw": None, "annual_gwh": None, "n_zones": len(cols),
           "n_hours": None, "n_gap_hours": None, "missing_cols": []}
    if not data_path.exists():
        out["error"] = f"data file not found: {data_path}"
        return out
    df = pd.read_excel(data_path)
    present = [c for c in cols if c in df.columns]
    out["missing_cols"] = [c for c in cols if c not in df.columns]
    if not present:
        out["error"] = "no declared demand columns found in data file"
        return out

    datetime_col = cfg.get("site", {}).get("columns", {}).get("datetime", "Datum")
    dt_hours = 1.0
    mask = pd.Series(True, index=df.index)
    if datetime_col in df.columns:
        ts = pd.to_datetime(df[datetime_col], errors="coerce")
        diffs = ts.diff().dropna()
        if len(diffs):
            dt_hours = diffs.median().total_seconds() / 3600.0
        horizon = cfg.get("scenario", {}).get("horizon", {}) or {}
        if horizon.get("start") and horizon.get("end"):
            start, end = pd.to_datetime(horizon["start"]), pd.to_datetime(horizon["end"])
            mask = (ts >= start) & (ts <= end)

    demand = df.loc[mask, present].apply(pd.to_numeric, errors="coerce")
    total = demand.sum(axis=1, skipna=True)          # network load per row [MW]
    any_valid = demand.notna().any(axis=1)           # rows with >=1 real reading
    out["peak_mw"] = float(total[any_valid].max())
    out["annual_gwh"] = float(total.sum()) * dt_hours / 1000.0  # MW * dt_hours = MWh → GWh
    out["n_hours"] = round(int(mask.sum()) * dt_hours, 1)
    out["n_gap_hours"] = round(int((~any_valid).sum()) * dt_hours, 1)
    return out


_TECH = {
    ("thermal_generator", "gas", True): "Gas CHP",
    ("thermal_generator", "gas", False): "Gas boiler",
    ("thermal_generator", "biomass", True): "Biomass CHP",
    ("thermal_generator", "biomass", False): "Biomass boiler",
    ("thermal_generator", "waste_heat", False): "Waste-heat feed-in",
}


def _generators(cfg: dict, network: str) -> list[dict]:
    rows: list[dict] = []
    assets = cfg.get("assets", {}) or {}
    for aid, a in assets.items():
        a = a or {}
        atype = a.get("type")
        inv = a.get("investment", {}) or {}
        investable = bool(inv.get("enabled")) or atype == "geometric_storage"
        if atype == "thermal_generator":
            tech = _TECH.get((atype, a.get("fuel"), "el_eff" in a), a.get("fuel", "generator"))
            cap = f"{a.get('capacity_mw', 0):g} MW"
            eff = f"η_th {a.get('thermal_efficiency', float('nan')):.3g}"
            if "el_eff" in a:
                eff += f", η_el {a['el_eff']:.3g}"
        elif atype == "p2h":
            tech = "Electrode boiler"
            eff = f"η {a.get('efficiency', float('nan')):.3g}"
            cap = (f"0–{inv.get('capacity_max_mw'):g} MW (inv.)" if investable
                   else f"{a.get('capacity_mw', 0):g} MW")
        elif atype == "heat_pump":
            tech = "Heat pump (WP)"
            eff = "COP ~3 (Lorenz, time-var.)"
            cap = f"0–{inv.get('capacity_max_mw'):g} MW (inv.)"
        elif atype == "geometric_storage":
            tech = "Thermal storage (TES)"
            rt = a.get("eff_charge", 1) * a.get("eff_discharge", 1)
            eff = f"η_rt {rt:.2f}"
            cap = f"{a.get('V_min_m3', 0):g}–{a.get('V_max_m3', 0):g} m³ (inv.)"
        else:
            continue
        capex = ""
        if atype == "geometric_storage":
            capex = f"{a.get('alpha_tes_eur_per_m3', 0):g} €/m³ + {a.get('beta_tes_eur', 0):g} €"
        elif inv:
            capex = f"{inv.get('capex_eur_per_mw', 0):g} €/MW + {inv.get('activation_cost_eur', 0):g} €"
        rows.append({
            "Network": network, "Asset": aid,
            "Role": "Investable" if investable else "Fixed",
            "Technology": tech, "Capacity": cap, "Efficiency": eff, "CAPEX": capex,
        })
    # Fixed first, then investable — stable, readable ordering
    rows.sort(key=lambda r: (r["Role"] != "Fixed", r["Asset"]))
    return rows


def _to_latex(df: pd.DataFrame, caption: str, label: str, align: str | None = None) -> str:
    align = align or "l" * len(df.columns)
    esc = lambda s: (str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
                     .replace("η", r"$\eta$").replace("³", r"$^3$").replace("²", r"$^2$")
                     .replace("₂", r"$_2$").replace("€", "EUR").replace("Δ", r"$\Delta$")
                     .replace("–", "--").replace("~", r"$\sim$").replace("°", r"$^\circ$"))
    lines = [r"\begin{table}[htbp]", r"  \centering",
             f"  \\caption{{{caption}}}", f"  \\label{{{label}}}",
             f"  \\begin{{tabular}}{{{align}}}", r"  \toprule",
             "  " + " & ".join(esc(c) for c in df.columns) + r" \\", r"  \midrule"]
    for _, row in df.iterrows():
        lines.append("  " + " & ".join(esc(v) for v in row.values) + r" \\")
    lines += [r"  \bottomrule", r"  \end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def _write(df: pd.DataFrame, stem: str, caption: str, label: str, align: str | None = None) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(FIG_DIR / f"{stem}.csv", index=False)
    (FIG_DIR / f"{stem}.tex").write_text(_to_latex(df, caption, label, align), encoding="utf-8")
    print(f"  [OK] {stem}: .csv + .tex -> {FIG_DIR}")


# ── T1 — network characteristics ─────────────────────────────────────────────
def build_t1() -> None:
    print("T1 — network characteristics:")
    cols, chars = [], {}
    gen_rows: list[dict] = []
    for net, paths in NETWORKS.items():
        cfg = _load_yaml(paths["config"])
        nc = _classify_nodes(cfg)
        pipes = _pipes(cfg)
        total_len_km = sum(float(p.get("length_m", 0)) for p in pipes.values()) / 1000.0
        meshed = any(p.get("bidirectional") for p in pipes.values())
        pe = _peak_and_energy(cfg, paths["data"])
        net_cfg = cfg.get("network", {})
        cols.append(net)
        chars[net] = {
            "Nodes (total)": sum(nc.values()),
            "  — producer / mixed / consumer / junction":
                f"{nc['producer']} / {nc['mixed']} / {nc['consumer']} / {nc['junction']}",
            "Pipes (supply+return pairs)": len(pipes),
            "Total route length [km]": f"{total_len_km:.1f}",
            "Topology": "meshed (1 bidirectional trunk)" if meshed else "radial tree",
            "Demand zones": pe["n_zones"],
            "Peak heat load [MW]": (f"{pe['peak_mw']:.1f}" if pe.get("peak_mw") is not None
                                    else pe.get("error", "n/a")),
            "Annual heat supplied [GWh]": (f"{pe['annual_gwh']:.1f}" if pe.get("annual_gwh") is not None
                                           else "n/a"),
            "Design supply temp. [°C]": f"{net_cfg.get('supply_temp_c', '?')}",
            "Return temp. [°C]": f"{net_cfg.get('return_temp_c', '?')}",
            "Fixed generators": sum(1 for a in (cfg.get('assets') or {}).values()
                                    if a and not (a.get('investment', {}) or {}).get('enabled')
                                    and a.get('type') not in ('geometric_storage',)),
            "Investable assets": "WP, EK, TES",
        }
        if pe.get("n_gap_hours"):
            print(f"    note[{net}]: {pe['n_gap_hours']} h with no valid reading "
                  f"(of {pe['n_hours']}); annual energy excludes gaps")
        if pe.get("missing_cols"):
            print(f"    WARN[{net}]: demand columns absent from data: {pe['missing_cols']}")
        gen_rows.extend(_generators(cfg, net))

    order = list(next(iter(chars.values())).keys())
    df = pd.DataFrame({"Characteristic": order,
                       **{net: [chars[net][k] for k in order] for net in cols}})
    _write(df, "tab_T1a_network_characteristics",
           "Key characteristics of the two case-study networks.",
           "tab:t1_networks", align="l" + "r" * len(cols))

    gdf = pd.DataFrame(gen_rows)[["Network", "Asset", "Role", "Technology",
                                  "Capacity", "Efficiency", "CAPEX"]]
    _write(gdf, "tab_T1b_generator_portfolio",
           "Generator and investable-asset portfolio per network "
           "(capacities: fixed = installed, investable = optimiser bounds).",
           "tab:t1_generators", align="llll rrl"[:0] + "lllllll")


# ── T2 — scenario matrix ─────────────────────────────────────────────────────
# Per-(network, family) descriptions — S4/S5 differ by network (Stadtbach = fixed
# alternative sites; Memmingen = endogenous), so a shared string would be wrong.
_FAMILY_DESC = {
    ("Stadtbach", "BC"): "Baseline (Bestand, no investment)",
    ("Stadtbach", "S0"): "WP+EK investment, no TES",
    ("Stadtbach", "S1"): "TES at central node (HKW)",
    ("Stadtbach", "S2"): "TES at WP node (MAN)",
    ("Stadtbach", "S3"): "TES at WP node, hot charging",
    ("Stadtbach", "S4"): "TES at Pumpstation Süd",
    ("Stadtbach", "S5"): "TES at Pumpstation West",
    ("Stadtbach", "S6"): "Free WP+TES siting (endogenous)",
    ("Stadtbach", "S7"): "Free siting, co-located, hot charging",
    ("Memmingen", "BC"): "Baseline (Bestand, no investment)",
    ("Memmingen", "S0"): "WP+EK investment, no TES",
    ("Memmingen", "S1"): "TES at central node (Zentrale)",
    ("Memmingen", "S2"): "TES at WP node (j_12)",
    ("Memmingen", "S3"): "TES at WP node, hot charging",
    ("Memmingen", "S4"): "Free WP+TES siting (endogenous)",
    ("Memmingen", "S5"): "Free siting, co-located, hot charging",
}


def _resolve_node(scen: dict, cfg_scen: dict) -> str:
    net = scen["network"]
    if scen.get("endogenous"):
        cands = cfg_scen.get("endogenous_candidates", {}).get(net, [])
        return "solver-chosen (" + ", ".join(cands) + ")"
    tn = scen.get("tes_node")
    if not tn:
        return "— (no TES)"
    return cfg_scen.get("tes_nodes", {}).get(net, {}).get(tn, tn)


def _resolve_hp(scen: dict, cfg_scen: dict) -> str:
    net = scen["network"]
    if scen.get("endogenous"):
        return "solver-chosen" + (" (= TES)" if scen.get("colocate") else "")
    hp = scen.get("hp_node")
    if not hp:
        return cfg_scen.get("hp_nodes", {}).get(net, {}).get(
            "J12" if net == "memmingen" else "J4", "fixed WP node")
    return cfg_scen.get("hp_nodes", {}).get(net, {}).get(hp, hp)


def build_t2() -> None:
    print("T2 — scenario matrix:")
    cfg_scen = _load_yaml(SCENARIOS_YAML)
    scenarios = cfg_scen.get("scenarios", [])
    # aggregate scenario entries into families (network, family-id)
    agg: dict[tuple, dict] = {}
    total_runs = 0
    for s in scenarios:
        total_runs += 1
        sid = s["id"]
        parts = sid.split("-")
        fam = "BC" if parts[0] == "BC" else parts[1]
        stage = "TVLFIX" if parts[0] == "BC" else (parts[2] if len(parts) > 2 else parts[1])
        net = "Stadtbach" if s["network"] == "stadtbach" else "Memmingen"
        key = (net, fam)
        if key not in agg:
            feats = []
            if s.get("hot_charging"):
                feats.append("hot charging")
            if s.get("endogenous"):
                feats.append("endogenous siting")
            if s.get("colocate"):
                feats.append("co-located WP+TES")
            agg[key] = {
                "Case study": net, "Family": fam,
                "Description": _FAMILY_DESC.get((net, fam), s.get("description", "")[:40]),
                "TES node": _resolve_node(s, cfg_scen),
                "WP/EK node": _resolve_hp(s, cfg_scen),
                "Features": ", ".join(feats) if feats else "—",
                "_stages": set(), "_runs": 0,
            }
        agg[key]["_stages"].add(stage)
        agg[key]["_runs"] += 1

    stage_order = {"TVLFIX": 0, "HK0": 1, "HK1": 2, "HK2": 3}
    rows = []
    for (net, fam), d in sorted(
            agg.items(), key=lambda kv: (kv[0][0] != "Stadtbach", kv[0][1])):
        stages = sorted(d["_stages"], key=lambda x: stage_order.get(x, 9))
        rows.append({
            "Case study": d["Case study"], "Family": fam, "Description": d["Description"],
            "TES node": d["TES node"], "WP/EK node": d["WP/EK node"],
            "Heat-curve stages": ", ".join(stages), "Runs": d["_runs"],
            "Features": d["Features"],
        })
    df = pd.DataFrame(rows)
    _write(df, "tab_T2_scenario_matrix",
           f"Scenario matrix ({len(df)} families → {total_runs} MILP runs). "
           "Heat-curve stages: TVLFIX (constant $T_{VL}$), HK0/HK1/HK2 "
           "(slope $k$ = 1.0 / 0.8 / 0.6).",
           "tab:t2_scenarios", align="llp{3.2cm}llllp{2.8cm}"[:0] + "ll" + "l" * 6)
    print(f"    families={len(df)}  total runs={total_runs}")


# ── T3 / T4 — per-network scenario KPI tables ────────────────────────────────
OUT_RUNS = _ROOT / "output" / "paper2_runs"
_STAGE_ORDER = {"TVLFIX": 0, "HK0": 1, "HK1": 2, "HK2": 3}


def _fmt(x, nd=1) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    return "—" if pd.isna(v) else f"{v:.{nd}f}"


def _load_kpis() -> pd.DataFrame | None:
    p = OUT_RUNS / "scenarios_kpis.csv"
    if not p.exists():
        print(f"  [SKIP] {p} missing — run kpi_calculator first")
        return None
    df = pd.read_csv(p)
    # Exclude diagnostic/test runs and the F3 endogenous-siting enumeration
    # sub-pairs (scenario_id pattern "{base}__hp_{site}__tes_{site}", see
    # scripts/paper_2/enumerate_endog_siting.py) — those are per-candidate
    # helper solves, not reportable scenarios in their own right.
    mask = df["scenario_id"].str.contains("TEST|DIAG|ZZ|__hp_.*__tes_", na=False, regex=True)
    return df[~mask].copy()


def _scenario_kpi_table(net_key: str, net_label: str, stem: str, caption: str) -> None:
    df = _load_kpis()
    if df is None:
        return
    sub = df[df["network"] == net_key].copy()
    if sub.empty:
        print(f"  [SKIP] {stem}: no rows for {net_label}")
        return
    sub["_fam"] = sub["scenario_id"].map(lambda s: "BC" if s.split("-")[0] == "BC"
                                         else s.split("-")[1])
    sub["_stg"] = sub["heat_curve_stage"].map(lambda s: _STAGE_ORDER.get(s, 9))
    sub = sub.sort_values(["baseline", "_fam", "_stg"], ascending=[False, True, True])
    rows = [{
        "Scenario": r["scenario_id"],
        "TES": r["tes_node"] if pd.notna(r.get("tes_node")) else "—",
        "HK": r["heat_curve_stage"],
        "TAC [M€/a]": _fmt(float(r["TAC_eur_per_a"]) / 1e6, 3),
        "LCOH [€/MWh]": _fmt(r["LCOH_eur_per_MWh"], 2),
        "Δcost [%]": _fmt(r["cost_reduction_pct"], 1),
        "CO₂ [t/a]": _fmt(r["co2_t_per_a"], 0),
        "Q_WP [MW]": _fmt(r.get("Q_WP_opt_MW"), 1),
        "E_TES [MWh]": _fmt(r.get("E_TES_MWh"), 1),
        "COP": _fmt(r.get("COP_annual_mean"), 2),
    } for _, r in sub.iterrows()]
    _write(pd.DataFrame(rows), stem, caption, f"tab:{stem}",
           align="ll l" + "r" * 7)
    print(f"    {net_label}: {len(rows)} scenarios")


def build_t3() -> None:
    print("T3 — Stadtbach scenario KPIs:")
    _scenario_kpi_table("stadtbach", "Stadtbach", "tab_T3_stadtbach_kpis",
                        "Stadtbach scenario KPIs (all solved runs): total annual cost, "
                        "LCOH, cost reduction, CO₂, WP/TES sizing, annual COP.")


def build_t4() -> None:
    print("T4 — Memmingen scenario KPIs:")
    _scenario_kpi_table("memmingen", "Memmingen", "tab_T4_memmingen_kpis",
                        "Memmingen scenario KPIs (all solved runs): total annual cost, "
                        "LCOH, cost reduction, CO₂, WP/TES sizing, annual COP.")


# ── T5 — validation table ────────────────────────────────────────────────────
def build_t5() -> None:
    print("T5 — validation table:")
    import numpy as np
    from collections import Counter
    canonical_ids = {s["id"] for s in _load_yaml(SCENARIOS_YAML).get("scenarios", [])}
    # SB-S6/MM-S4 (endogenous siting): the canonical run dir, where it exists, is the known-bad
    # pre-decomposition monolithic attempt (G.6-G.8) — the real winner per stage comes from the
    # enumeration decomposition and lives in tab_T3b_T4b_f3_endogenous_siting_FINAL.csv instead.
    # Their monolithic solver stats (e.g. MM-S4-HK0's sign-flipped-bound 47349% gap, G.10) are not
    # meaningful campaign statistics and are excluded here rather than "fixed" per G.10's guidance.
    endogenous_superseded = {s for s in canonical_ids if s.startswith(("SB-S6-", "MM-S4-"))}
    gaps, statuses = [], []
    good_closures, good_losses, suspect_runs = [], [], []   # converged / loss-frac / flagged
    excluded_dirs = []   # non-canonical run dirs (F3 enumeration sub-pairs, diagnostics, TEST/DIAG) — reported separately, not mixed into T5
    superseded_dirs = []  # canonical SB-S6/MM-S4 dirs holding the superseded monolithic attempt
    for d in sorted(p for p in OUT_RUNS.iterdir() if p.is_dir()):
        if d.name in endogenous_superseded:
            superseded_dirs.append(d.name)
            continue
        if d.name not in canonical_ids:
            excluded_dirs.append(d.name)
            continue
        vj, mj = d / "validation.json", d / "meta.json"
        status = None
        if mj.exists():
            try:
                m = json.loads(mj.read_text())
                status = str(m.get("status", "?"))
                statuses.append(status)
                if m.get("mip_gap") is not None:
                    gaps.append(float(m["mip_gap"]))
            except Exception:  # noqa: BLE001
                pass
        if vj.exists():
            try:
                eb = json.loads(vj.read_text()).get("energy_balance", {})
                if not eb:
                    continue
                ce = eb.get("closure_error_pct")
                optimal = status is None or "optimal" in status.lower()
                if ce is None:                       # guarded-out stale/wrong-net run
                    suspect_runs.append(d.name)
                elif optimal:                        # trust only converged runs
                    good_closures.append((d.name, float(ce), bool(eb.get("closure_pass"))))
                    if eb.get("network_loss_pct") is not None:
                        good_losses.append(float(eb["network_loss_pct"]))
            except Exception:  # noqa: BLE001
                pass
    rows: list[dict] = []
    def add(metric, value, note=""):
        rows.append({"Validation metric": metric, "Value": value, "Note": note})

    add("Campaign population", f"{len(canonical_ids)} canonical scenarios",
        f"{len(statuses)} reported here directly; {len(endogenous_superseded)} SB-S6/MM-S4 ids "
        "resolved via enumeration decomposition instead of a monolithic solve (per G.8) — see "
        "tab_T3b_T4b_f3_endogenous_siting_FINAL.csv for their KPIs; "
        f"{len(excluded_dirs)} further diagnostic/enumeration run dirs (F3 sub-pairs, TEST/DIAG, "
        "superseded re-solves) excluded from this table — see tab_T5_supplement_excluded_runs")

    if good_closures:
        errs = [c[1] for c in good_closures]
        worst = max(good_closures, key=lambda c: c[1])
        add("MW closure error (mean)", f"{np.mean(errs):.2f} %",
            f"{len(good_closures)} converged runs; gen+storage vs demand")
        add("MW closure error (max)", f"{worst[1]:.2f} %", f"worst: {worst[0]}")
        add("Runs passing closure gate (≤2%)", f"{sum(c[2] for c in good_closures)}/{len(good_closures)}",
            "converged runs only")
        if good_losses:
            add("Network loss fraction (mean)", f"{np.mean(good_losses):.2f} %",
                "thermal diagnostic — not an imbalance (dispatch balance is MW-lossless)")
    else:
        add("Energy-balance closure", "n/a", "no converged run with a plausible balance yet")
    if suspect_runs:
        add("Runs excluded (implausible balance)", str(len(suspect_runs)),
            "stale/wrong-network dispatch — refreshes on re-run")
    if gaps:
        add("MIP gap (median)", f"{np.median(gaps) * 100:.3f} %", f"{len(gaps)} runs report a gap")
        add("MIP gap (max)", f"{max(gaps) * 100:.3f} %", "")
    else:
        add("MIP gap", "n/a", "meta.json mip_gap null — see solver status")
    if statuses:
        add("Solver status", "; ".join(f"{k}: {v}" for k, v in Counter(statuses).items()),
            f"{len(statuses)} runs")
    df = _load_kpis()
    if df is not None:
        cop = pd.to_numeric(df["COP_annual_mean"], errors="coerce").dropna()
        if len(cop):
            add("Annual COP range", f"{cop.min():.2f} – {cop.max():.2f}",
                "plausibility (Lorenz surrogate)")
    p1c = validation_p2.check_paper1_consistency(OUT_RUNS)
    if p1c.get("ok") is not None:
        add("Memmingen P1 OPEX consistency", f"{p1c['error_pct']:.2f} %",
            f"P2={p1c['opex_p2']:,.0f} EUR vs P1={p1c['opex_p1']:,.0f} EUR "
            f"({'pass' if p1c['ok'] else 'FAIL'}, gate <=2%)")
    else:
        add("Memmingen P1 OPEX consistency", "pending", p1c.get("detail", "inputs missing"))

    sweep_files = sorted((_ROOT / "results").glob("sweep_*_optimum.json")) \
        if (_ROOT / "results").exists() else []
    if sweep_files:
        for sf in sweep_files:
            sc = json.loads(sf.read_text()).get("sweep_consistency")
            if not sc:
                continue
            add(f"Sweep-MILP optimum consistency ({sf.stem.replace('_optimum', '')})",
                sc["verdict"],
                f"TAC dev {sc['tac_dev_pct']:+.1f}% (gate <=10%), grid dist "
                f"Q={sc['grid_steps_q']} V={sc['grid_steps_v']} steps (gate <=1 each)")
    else:
        add("Sweep–MILP optimum consistency", "pending", "Part A sweep not run yet (spec A.5)")
    _write(pd.DataFrame(rows), "tab_T5_validation",
           "Model validation summary across the campaign.", "tab:t5_validation",
           align="llp{5cm}"[:0] + "lll")

    # Supplement: the non-canonical run population T5 now excludes (F3 endogenous-siting
    # enumeration sub-pairs, TEST/DIAG runs, superseded re-solves) — kept visible, not silently
    # dropped, per the reviewer request to report diagnostics separately from the 46-run headline.
    excl_rows = []
    for name in sorted(excluded_dirs) + sorted(superseded_dirs):
        mj = OUT_RUNS / name / "meta.json"
        st, gap = "?", None
        if mj.exists():
            try:
                m = json.loads(mj.read_text())
                st = str(m.get("status", "?"))
                gap = m.get("mip_gap")
            except Exception:  # noqa: BLE001
                pass
        kind = ("SB-S6/MM-S4 superseded monolithic (G.8)" if name in superseded_dirs
                else "F3 enumeration sub-pair" if "__hp_" in name and "__tes_" in name
                else "TEST/DIAG" if ("TEST" in name or "DIAG" in name or "ZZ" in name)
                else "other diagnostic/superseded")
        excl_rows.append({"Run dir": name, "Kind": kind, "Status": st,
                           "MIP gap": f"{gap * 100:.2f} %" if gap is not None else "—"})
    _write(pd.DataFrame(excl_rows), "tab_T5_supplement_excluded_runs",
           "Non-canonical run directories excluded from tab\\_T5\\_validation (F3 "
           "endogenous-siting enumeration sub-pairs, diagnostic/test runs, superseded "
           "re-solves) — reported here for transparency, not part of the 46-scenario campaign.",
           "tab:t5_supplement_excluded", align="lllr")
    print(f"    metrics={len(rows)}  canonical_found={len(statuses)}/{len(canonical_ids)}  "
          f"superseded_monolithic={len(superseded_dirs)}  "
          f"converged_closures={len(good_closures)}  excluded_non_canonical={len(excluded_dirs)}  "
          f"gaps={len(gaps)}")


_ALL = {"T1": build_t1, "T2": build_t2, "T3": build_t3, "T4": build_t4, "T5": build_t5}

if __name__ == "__main__":
    which = [a.upper() for a in sys.argv[1:] if a.upper() in _ALL] or list(_ALL)
    for key in which:
        _ALL[key]()
