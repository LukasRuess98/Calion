"""
Tables 1–4 — extract all paper tables from run outputs.

Usage:
    python scripts/paper/extract_tables.py \
        --l1-dir outputs/paper/L1 \
        --l2-dir outputs/paper/L2 \
        --l3-dir outputs/paper/L3 \
        --outdir outputs/paper/tables/

Produces (all CSV, semicolon-delimited):
    table1_cost_breakdown.csv
    table2_operational_kpis.csv
    table3_network_characteristics.csv
    table4_solver_statistics.csv  (partial — solver stats logged separately)
"""
import argparse
import json
from pathlib import Path

import pandas as pd

DT_H = 1.0
DEMAND_COL = "waermebedarf_MWth"


# -- Helpers ------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    print(f"  Warning: {path} not found — returning empty dict")
    return {}


def _load_ts(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, sep=";", decimal=",",
                           index_col=0, parse_dates=True)
    print(f"  Warning: {path} not found — returning empty DataFrame")
    return pd.DataFrame()


def _get(d: dict, *keys, default=0.0):
    """Drill into nested dict; try top-level and 'objective' sub-dict."""
    for k in keys:
        if k in d:
            v = d[k]
            return float(v) if isinstance(v, (int, float)) else v
        obj = d.get("objective", d.get("PF", d.get("pf", {})))
        if isinstance(obj, dict) and k in obj:
            v = obj[k]
            return float(v) if isinstance(v, (int, float)) else v
    return default


# -- Table 1: Cost breakdown ---------------------------------------------------

COST_KEYS = [
    ("Grid_energy_cost_EUR",   "Grid electricity [EUR]"),
    ("Fuel_cost_EUR",          "Gas fuel [EUR]"),
    ("CO2_cost_EUR",           "CO2 cost [EUR]"),
    ("Demand_charge_cost_EUR", "Demand charge [EUR]"),
    ("Dump_cost_EUR",          "Heat dump [EUR]"),
    ("Capex_cost_EUR",         "CAPEX [EUR]"),
    ("OBJ_value_EUR",          "Total cost [EUR]"),
]


def build_table1(costs: list[dict]) -> pd.DataFrame:
    rows = []
    for json_key, label in COST_KEYS:
        vals = [_get(c, json_key) for c in costs]
        base = vals[0]
        row = {"Cost component": label,
               "L1 [EUR]":  f"{vals[0]:,.0f}",
               "L2 [EUR]":  f"{vals[1]:,.0f}",
               "L3 [EUR]":  f"{vals[2]:,.0f}",
               "dL2-L1 [%]": f"{(vals[1]-base)/base*100:+.1f}" if base else "—",
               "dL3-L1 [%]": f"{(vals[2]-base)/base*100:+.1f}" if base else "—"}
        rows.append(row)
    return pd.DataFrame(rows)


# -- Table 2: Operational KPIs -------------------------------------------------

def build_table2(ts_list: list[pd.DataFrame], costs: list[dict]) -> pd.DataFrame:
    rows = []

    def _safe_col(df, col):
        return df[col].fillna(0) if col in df.columns else pd.Series([0.0])

    for tag, df, cost in zip(["L1", "L2", "L3"], ts_list, costs):
        demand_gwh   = _safe_col(df, DEMAND_COL).sum() * DT_H / 1e3
        hp_heat_gwh  = _safe_col(df, "hp_main_Q_th_MW").sum() * DT_H / 1e3
        boiler_gwh   = _safe_col(df, "BOILER_MAIN_Q_th_MW").sum() * DT_H / 1e3
        tes_dis_gwh  = _safe_col(df, "TES_discharge_MW").sum() * DT_H / 1e3
        p_buy_gwh    = _safe_col(df, "P_buy_MW").sum() * DT_H / 1e3
        p_sell_gwh   = _safe_col(df, "P_sell_MW").sum() * DT_H / 1e3
        dump_gwh     = _safe_col(df, "Q_dump_MWth").sum() * DT_H / 1e3
        co2_total_t  = _safe_col(df, "Total_CO2_emissions_t_per_step").sum()

        hp_on_h      = (_safe_col(df, "hp_main_on") > 0.5).sum()
        hp_cap_mw    = _get(cost, "Thermal_capacity_MW", default=100.0)
        fl_hours     = hp_heat_gwh * 1e3 / hp_cap_mw if hp_cap_mw > 0 else 0
        boiler_util  = boiler_gwh / (200.0 * demand_gwh / 1e3) * 100 if demand_gwh > 0 else 0

        avg_cop      = df["hp_main_COP"].replace(0, float("nan")).mean() if "hp_main_COP" in df.columns else 0
        soc_max      = _safe_col(df, "TES_SOC_MWh").max()
        soc_avg      = _safe_col(df, "TES_SOC_MWh").mean()

        rows.append({
            "Metric": "Level",
            "Value": tag,
        })

        entries = [
            ("Annual heat demand [GWh]",        f"{demand_gwh:.1f}"),
            ("HP heat output [GWh]",             f"{hp_heat_gwh:.1f}"),
            ("Boiler heat output [GWh]",         f"{boiler_gwh:.1f}"),
            ("Storage discharge [GWh]",          f"{tes_dis_gwh:.1f}"),
            ("HP full-load hours [h]",           f"{fl_hours:.0f}"),
            ("HP average COP [-]",               f"{avg_cop:.2f}" if avg_cop > 0 else "—"),
            ("Storage max SOC [MWh]",            f"{soc_max:.1f}"),
            ("Storage avg SOC [MWh]",            f"{soc_avg:.1f}"),
            ("Grid import [GWh]",                f"{p_buy_gwh:.1f}"),
            ("Grid export [GWh]",                f"{p_sell_gwh:.1f}"),
            ("Heat dump [GWh]",                  f"{dump_gwh:.2f}"),
            ("Total CO2 emissions [t]",          f"{co2_total_t:,.0f}"),
        ]
        for metric, val in entries:
            rows.append({"Metric": metric, f"L1" if tag == "L1" else tag: val})

    # Pivot: metric as rows, levels as columns
    pivot = {}
    level_keys = ["L1", "L2", "L3"]
    # Re-build cleanly
    metric_vals: dict[str, dict] = {}
    for tag, df, cost in zip(["L1", "L2", "L3"], ts_list, costs):
        def _s(col): return df[col].fillna(0) if col in df.columns else pd.Series([0.0])
        demand_gwh  = _s(DEMAND_COL).sum() * DT_H / 1e3
        hp_gwh      = _s("hp_main_Q_th_MW").sum() * DT_H / 1e3
        boil_gwh    = _s("BOILER_MAIN_Q_th_MW").sum() * DT_H / 1e3
        tes_dis     = _s("TES_discharge_MW").sum() * DT_H / 1e3
        p_buy       = _s("P_buy_MW").sum() * DT_H / 1e3
        p_sell      = _s("P_sell_MW").sum() * DT_H / 1e3
        dump        = _s("Q_dump_MWth").sum() * DT_H / 1e3
        co2         = _s("Total_CO2_emissions_t_per_step").sum()
        hp_cap      = 100.0
        fl          = hp_gwh * 1e3 / hp_cap
        avg_cop     = df["hp_main_COP"].replace(0, float("nan")).mean() if "hp_main_COP" in df.columns else float("nan")
        soc_max     = _s("TES_SOC_MWh").max()
        soc_avg     = _s("TES_SOC_MWh").mean()

        metric_vals[tag] = {
            "Annual heat demand [GWh]":   f"{demand_gwh:.1f}",
            "HP heat output [GWh]":       f"{hp_gwh:.1f}",
            "Boiler heat output [GWh]":   f"{boil_gwh:.1f}",
            "Storage discharge [GWh]":    f"{tes_dis:.1f}",
            "HP full-load hours [h]":     f"{fl:.0f}",
            "HP average COP [-]":         f"{avg_cop:.2f}" if avg_cop == avg_cop else "—",
            "Storage max SOC [MWh]":      f"{soc_max:.1f}",
            "Storage avg SOC [MWh]":      f"{soc_avg:.1f}",
            "Grid import [GWh]":          f"{p_buy:.1f}",
            "Grid export [GWh]":          f"{p_sell:.1f}",
            "Heat dump [GWh]":            f"{dump:.3f}",
            "Total CO2 emissions [t]":    f"{co2:,.0f}",
        }

    metrics = list(metric_vals["L1"].keys())
    table_rows = []
    for m in metrics:
        table_rows.append({
            "Metric": m,
            "L1": metric_vals["L1"][m],
            "L2": metric_vals["L2"][m],
            "L3": metric_vals["L3"][m],
        })
    return pd.DataFrame(table_rows)


# -- Table 3: Network characteristics -----------------------------------------

NETWORK_STATIC = {
    "L1": {"Nodes": 1,  "Consumer nodes": 0,  "Junction nodes": 0,
           "Pipes": 0,  "Total pipe length [m]": 0,
           "Min pipe diameter [mm]": "—", "Max pipe diameter [mm]": "—"},
    "L2": {"Nodes": 5,  "Consumer nodes": 3,  "Junction nodes": 1,
           "Pipes": 4,  "Total pipe length [m]": 6300,
           "Min pipe diameter [mm]": 350, "Max pipe diameter [mm]": 500},
    "L3": {"Nodes": 29, "Consumer nodes": 23, "Junction nodes": 5,
           "Pipes": 28, "Total pipe length [m]": 14250,
           "Min pipe diameter [mm]": 150, "Max pipe diameter [mm]": 600},
}


def build_table3(l2_pipes_dir: Path, l3_pipes_dir: Path) -> pd.DataFrame:
    rows = []
    for k in list(NETWORK_STATIC["L1"].keys()):
        rows.append({"Property": k,
                     "L1": NETWORK_STATIC["L1"][k],
                     "L2": NETWORK_STATIC["L2"][k],
                     "L3": NETWORK_STATIC["L3"][k]})

    # Add computed pipe losses from network_summary.json
    import json as _json
    for tag, pipes_dir in [("L2", l2_pipes_dir), ("L3", l3_pipes_dir)]:
        summary_path = pipes_dir / "network_summary.json"
        total_loss_gwh = None
        if summary_path.exists():
            with open(summary_path, encoding="utf-8") as f:
                ns = _json.load(f)
            total_loss_mwh = sum(
                float(p.get("total_heat_loss_mwh", 0))
                for p in ns.get("pipes", {}).values()
            )
            total_loss_gwh = total_loss_mwh / 1e3
        val = f"{total_loss_gwh:.3f}" if total_loss_gwh is not None else "n/a"
        rows.append({"Property": f"Annual total pipe loss [GWh] ({tag})",
                     "L1": "—",
                     "L2": val if tag == "L2" else "—",
                     "L3": val if tag == "L3" else "—"})

    return pd.DataFrame(rows)


# -- Main ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract paper tables")
    parser.add_argument("--l1-dir", required=True)
    parser.add_argument("--l2-dir", required=True)
    parser.add_argument("--l3-dir", required=True)
    parser.add_argument("--outdir", default="outputs/paper/tables")
    args = parser.parse_args()

    dirs = {tag: Path(d) for tag, d in
            [("L1", args.l1_dir), ("L2", args.l2_dir), ("L3", args.l3_dir)]}
    Path(args.outdir).mkdir(parents=True, exist_ok=True)

    # Load data
    costs = [_load_json(dirs[t] / "costs.json") for t in ["L1", "L2", "L3"]]
    ts    = [_load_ts(dirs[t] / "pf_timeseries.csv") for t in ["L1", "L2", "L3"]]

    # Table 1
    t1 = build_table1(costs)
    p1 = Path(args.outdir) / "table1_cost_breakdown.csv"
    t1.to_csv(p1, index=False, sep=";")
    print(f"\n-- Table 1: Cost breakdown -> {p1}")
    print(t1.to_string(index=False))

    # Table 2
    t2 = build_table2(ts, costs)
    p2 = Path(args.outdir) / "table2_operational_kpis.csv"
    t2.to_csv(p2, index=False, sep=";")
    print(f"\n-- Table 2: Operational KPIs -> {p2}")
    print(t2.to_string(index=False))

    # Table 3
    t3 = build_table3(dirs["L2"] / "thermal_network",
                      dirs["L3"] / "thermal_network")
    p3 = Path(args.outdir) / "table3_network_characteristics.csv"
    t3.to_csv(p3, index=False, sep=";")
    print(f"\n-- Table 3: Network characteristics -> {p3}")
    print(t3.to_string(index=False))

    print("\nAll tables written.")


if __name__ == "__main__":
    main()
