"""
tab_synth_parameter_effects.py
==============================
Generates four supplementary tables for the Paper 1 synthetic study:

  Tab A  (tab_hi_within_pipe_bands.csv)
         HI marginal effect within each pipe-length band.

  Tab B  (tab_decomp_extremes.csv)
         Top-3 / Bottom-3 configs by total gap with Routing / Loss / ΔP breakdown.

  Tab C  (tab_l3plus_gap_by_pipe.csv)
         L3→L3+ gap statistics per pipe-length band.

  Tab D  (tab_parameter_influence.csv)
         Consolidated parameter-influence ranking (range of median gaps).

Usage:
    python scripts/paper/tab_synth_parameter_effects.py

Outputs are written to output/paper_runs/tables/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SYNTH_DIR = ROOT / "output" / "paper_runs" / "synth"
OUT_DIR   = ROOT / "output" / "paper_runs" / "tables"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LEVELS = ["L1cp", "L1", "L2", "L3", "L3plus"]

# Pipe-length bands used in the "standard" sweep (exclude L30 / L50 extensions)
STANDARD_PIPES = {1.0, 5.0, 15.0}


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def _load_all() -> pd.DataFrame:
    rows = []
    for d in sorted(SYNTH_DIR.iterdir()):
        eco = d / "economics.csv"
        if not eco.exists():
            continue
        m = re.match(r"^(.+)_(L1cp|L1|L2|L3plus|L3)$", d.name)
        if not m:
            continue
        config, level = m.group(1), m.group(2)
        if not re.match(r"synth_n\d+_L", config):
            continue
        # Skip _L1cp suffix variants (used for separate L1cp baseline runs)
        if "_L1cp" in config:
            continue

        p = re.match(r"synth_n(\d+)_L([\dp]+)km_hi([\dp]+)_s(\d+)h", config)
        if not p:
            continue

        n_nodes   = int(p.group(1))
        pipe_km   = float(p.group(2).replace("p", "."))
        hi        = float(p.group(3).replace("p", "."))
        storage_h = int(p.group(4))

        df_eco = pd.read_csv(eco).iloc[0]

        disp = d / "dispatch_hourly.csv"
        demand_mwh = 0.0
        if disp.exists():
            dp = pd.read_csv(disp, parse_dates=["timestamp"])
            if "Q_demand_total_MW" in dp.columns and len(dp) > 1:
                dt_h = (dp["timestamp"].iloc[1] - dp["timestamp"].iloc[0]).total_seconds() / 3600
                demand_mwh = float(dp["Q_demand_total_MW"].sum()) * dt_h

        rows.append({
            "config":    config,
            "level":     level,
            "n_nodes":   n_nodes,
            "pipe_km":   pipe_km,
            "hi":        hi,
            "storage_h": storage_h,
            "cost_eur":  float(df_eco["cost_total_eur"]),
            "demand_mwh": demand_mwh,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Pivot to wide format: one row per config, columns = level costs
    cost_piv    = df.pivot_table(index="config", columns="level", values="cost_eur",    aggfunc="first")
    demand_piv  = df.pivot_table(index="config", columns="level", values="demand_mwh",  aggfunc="first")
    meta        = df.drop_duplicates("config").set_index("config")[
                      ["n_nodes", "pipe_km", "hi", "storage_h"]
                  ]
    wide = meta.join(cost_piv, how="left").join(
        demand_piv.rename(columns=lambda c: f"demand_{c}"), how="left"
    )
    wide = wide.reset_index()

    # ── Gap columns (% relative to hi-level cost, sign: positive = hi > lo) ──
    def gap_pct(lo_col, hi_col):
        lo  = wide[lo_col]
        hi  = wide[hi_col]
        ref = wide.get(f"demand_{hi_col}", hi)
        ref = ref.replace(0, np.nan)
        return (hi - lo) / hi.abs() * 100

    def gap_eur_mwh(lo_col, hi_col):
        lo  = wide[lo_col]
        hi  = wide[hi_col]
        ref = wide.get(f"demand_{hi_col}", None)
        if ref is None:
            return pd.Series(np.nan, index=wide.index)
        ref = ref.replace(0, np.nan)
        return (hi - lo) / ref

    for lo, hi_col in [
        ("L1cp", "L3"),
        ("L1cp", "L1"),
        ("L1",   "L2"),
        ("L2",   "L3"),
        ("L3",   "L3plus"),
    ]:
        if lo in wide.columns and hi_col in wide.columns:
            wide[f"gap_pct_{lo}_{hi_col}"]     = gap_pct(lo, hi_col)
            wide[f"gap_eur_mwh_{lo}_{hi_col}"] = gap_eur_mwh(lo, hi_col)

    # Decomposition in kEUR (absolute)
    KEUR = 1000.0
    for lo, hi_col in [("L1cp", "L1"), ("L1", "L2"), ("L2", "L3")]:
        if lo in wide.columns and hi_col in wide.columns:
            wide[f"delta_keur_{lo}_{hi_col}"] = (wide[hi_col] - wide[lo]) / KEUR

    return wide


# ─────────────────────────────────────────────────────────────────────────────
# Table A: HI effect within pipe-length bands
# ─────────────────────────────────────────────────────────────────────────────

def _table_hi_within_pipe_bands(wide: pd.DataFrame) -> pd.DataFrame:
    gap_col = "gap_pct_L1cp_L3"
    if gap_col not in wide.columns:
        print("[Tab A] gap column missing – skipping")
        return pd.DataFrame()

    # Restrict to standard pipe lengths for clean within-band analysis
    df = wide[wide["pipe_km"].isin(STANDARD_PIPES) & wide[gap_col].notna()].copy()

    rows = []
    for pipe in sorted(df["pipe_km"].unique()):
        band = df[df["pipe_km"] == pipe]
        for hi_val in sorted(band["hi"].unique()):
            cell = band[band["hi"] == hi_val][gap_col]
            rows.append({
                "pipe_km":    pipe,
                "hi":         hi_val,
                "n_configs":  len(cell),
                "mean_gap_%": round(cell.mean(), 2),
                "median_gap_%": round(cell.median(), 2),
                "min_gap_%":  round(cell.min(), 2),
                "max_gap_%":  round(cell.max(), 2),
            })

    tab = pd.DataFrame(rows)
    if tab.empty:
        return tab

    # Add Δ(HI_max − HI_min) per pipe band
    for pipe, grp in tab.groupby("pipe_km"):
        if grp["hi"].nunique() < 2:
            continue
        lo_med = grp.loc[grp["hi"].idxmin(), "median_gap_%"]
        hi_med = grp.loc[grp["hi"].idxmax(), "median_gap_%"]
        tab.loc[tab["pipe_km"] == pipe, "delta_hi_max_min_%"] = round(hi_med - lo_med, 2)

    return tab


# ─────────────────────────────────────────────────────────────────────────────
# Table B: Top-3 / Bottom-3 by total gap with decomposition
# ─────────────────────────────────────────────────────────────────────────────

def _table_decomp_extremes(wide: pd.DataFrame) -> pd.DataFrame:
    needed = ["L1cp", "L1", "L2", "L3"]
    if not all(c in wide.columns for c in needed):
        print("[Tab B] Not all levels present - skipping")
        return pd.DataFrame()

    # Restrict to standard pipe lengths to exclude large-network extensions
    df = wide[wide["pipe_km"].isin(STANDARD_PIPES)].dropna(subset=needed).copy()
    df["total_keur"] = (df["L3"] - df["L1cp"]) / 1000.0

    total = df["L3"] - df["L1cp"]
    total_safe = total.replace(0, np.nan)

    df["routing_pct"] = ((df["L1"] - df["L1cp"]) / total_safe * 100).round(1)
    df["heatloss_pct"] = ((df["L2"] - df["L1"]) / total_safe * 100).round(1)
    df["pressure_pct"] = ((df["L3"] - df["L2"]) / total_safe * 100).round(1)

    df_s = df.sort_values("total_keur", ascending=False)
    top3    = df_s.head(3).copy()
    bottom3 = df_s.tail(3).copy()
    extremes = pd.concat([top3, bottom3]).reset_index(drop=True)
    extremes["rank"] = (
        [f"Top-{i+1}" for i in range(len(top3))] +
        [f"Bot-{i+1}" for i in range(len(bottom3))]
    )

    cols = ["rank", "config", "pipe_km", "hi", "n_nodes", "storage_h",
            "routing_pct", "heatloss_pct", "pressure_pct", "total_keur"]
    return extremes[[c for c in cols if c in extremes.columns]]


# ─────────────────────────────────────────────────────────────────────────────
# Table C: L3→L3+ gap by pipe-length band
# ─────────────────────────────────────────────────────────────────────────────

def _table_l3plus_gap(wide: pd.DataFrame) -> pd.DataFrame:
    # NOTE: In the synthetic study (run_synth_parallel.py), L3 already has
    # pressure_drop=True. L3plus adds only transport_delay=True, which does not
    # affect annual operating costs. The 0.0% gap reported here is therefore
    # expected and correct — it confirms that transport delay alone has no
    # material cost impact across all network sizes tested.
    gap_pct_col = "gap_pct_L3_L3plus"
    gap_eur_col = "gap_eur_mwh_L3_L3plus"

    if gap_pct_col not in wide.columns:
        print("[Tab C] L3+ gap column missing - skipping")
        return pd.DataFrame()

    df = wide[wide[gap_pct_col].notna()].copy()

    rows = []
    s_pct = df[gap_pct_col]
    s_eur = df[gap_eur_col] if gap_eur_col in df.columns else pd.Series(dtype=float)
    rows.append({
        "pipe_km":            "All",
        "n_configs":          len(s_pct),
        "median_gap_%":       round(s_pct.median(), 4),
        "p90_gap_%":          round(float(np.percentile(s_pct.dropna(), 90)), 4),
        "max_gap_%":          round(s_pct.max(), 4),
        "median_gap_EUR_MWh": round(s_eur.median(), 5) if not s_eur.empty else None,
        "max_gap_EUR_MWh":    round(s_eur.max(), 5) if not s_eur.empty else None,
        "note": "transport_delay only; pressure_drop already in L3",
    })

    for pipe in sorted(df["pipe_km"].unique()):
        band = df[df["pipe_km"] == pipe]
        s_pct = band[gap_pct_col]
        s_eur = band[gap_eur_col] if gap_eur_col in band.columns else pd.Series(dtype=float)
        rows.append({
            "pipe_km":            pipe,
            "n_configs":          len(s_pct),
            "median_gap_%":       round(s_pct.median(), 4),
            "p90_gap_%":          round(float(np.percentile(s_pct.dropna(), 90)), 4),
            "max_gap_%":          round(s_pct.max(), 4),
            "median_gap_EUR_MWh": round(s_eur.median(), 5) if not s_eur.empty else None,
            "max_gap_EUR_MWh":    round(s_eur.max(), 5) if not s_eur.empty else None,
            "note": "",
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Table D: Consolidated parameter influence ranking
# ─────────────────────────────────────────────────────────────────────────────

def _table_parameter_influence(wide: pd.DataFrame) -> pd.DataFrame:
    gap_col = "gap_pct_L1cp_L3"
    if gap_col not in wide.columns:
        print("[Tab D] gap column missing – skipping")
        return pd.DataFrame()

    df = wide[wide[gap_col].notna()].copy()

    params = {
        "pipe_km":   "Pipe length [km]",
        "hi":        "Demand HI",
        "n_nodes":   "Node count",
        "storage_h": "Storage capacity [h]",
    }
    rows = []
    for param, label in params.items():
        levels = sorted(df[param].unique())
        medians = {
            v: df[df[param] == v][gap_col].median()
            for v in levels
        }
        min_level = min(levels)
        max_level = max(levels)
        med_at_min = medians[min_level]
        med_at_max = medians[max_level]

        rows.append({
            "Parameter":                  label,
            "Range tested":               f"{min_level} - {max_level}",
            "Median gap at min [%]":      round(med_at_min, 2),
            "Median gap at max [%]":      round(med_at_max, 2),
            "delta_median_gap_%":         round(med_at_max - med_at_min, 2),
            "n_configs":                  len(df),
        })

    tab = pd.DataFrame(rows).sort_values("delta_median_gap_%", ascending=False)
    tab.insert(0, "Rank", range(1, len(tab) + 1))
    return tab.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Loading synthetic run data...")
    wide = _load_all()
    if wide.empty:
        print("[ERROR] No data loaded from", SYNTH_DIR)
        return
    print(f"  {len(wide)} configs loaded across {wide['pipe_km'].nunique()} pipe lengths")

    # ── Table A ──────────────────────────────────────────────────────────────
    tab_a = _table_hi_within_pipe_bands(wide)
    if not tab_a.empty:
        path = OUT_DIR / "tab_hi_within_pipe_bands.csv"
        tab_a.to_csv(path, index=False)
        print(f"\n[Tab A] HI within pipe bands  ->  {path.name}")
        print(tab_a.to_string(index=False))

    # ── Table B ──────────────────────────────────────────────────────────────
    tab_b = _table_decomp_extremes(wide)
    if not tab_b.empty:
        path = OUT_DIR / "tab_decomp_extremes.csv"
        tab_b.to_csv(path, index=False)
        print(f"\n[Tab B] Decomposition extremes  ->  {path.name}")
        print(tab_b.to_string(index=False))

    # ── Table C ──────────────────────────────────────────────────────────────
    tab_c = _table_l3plus_gap(wide)
    if not tab_c.empty:
        path = OUT_DIR / "tab_l3plus_gap_by_pipe.csv"
        tab_c.to_csv(path, index=False)
        print(f"\n[Tab C] L3->L3+ gap by pipe  ->  {path.name}")
        print(tab_c.to_string(index=False))

    # ── Table D ──────────────────────────────────────────────────────────────
    tab_d = _table_parameter_influence(wide)
    if not tab_d.empty:
        path = OUT_DIR / "tab_parameter_influence.csv"
        tab_d.to_csv(path, index=False)
        print(f"\n[Tab D] Parameter influence ranking  ->  {path.name}")
        print(tab_d.to_string(index=False))


if __name__ == "__main__":
    main()
