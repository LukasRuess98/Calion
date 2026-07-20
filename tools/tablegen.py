r"""
§7 LaTeX Table Generator

Reads CSVs from output/paper_runs/ and writes booktabs LaTeX snippets
to output/paper_runs/tables/*.tex.

Usage:
    python tools/tablegen.py              # generate all tables
    python tools/tablegen.py --table tab_cost_topology

Format: booktabs (\toprule/\midrule/\bottomrule), siunitx for numbers.
Each .tex file is a standalone \begin{tabular}...\end{tabular} snippet
for \input{} in the paper.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "output" / "paper_runs"
TABLES = RUNS / "tables"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _num(val, decimals: int = 0, unit: str = "") -> str:
    """Format a number with siunitx-friendly notation."""
    try:
        v = float(val)
        if not math.isfinite(v):
            return r"\text{N/A}"
        if decimals == 0:
            formatted = f"{v:,.0f}".replace(",", r"\,")
        else:
            formatted = f"{v:,.{decimals}f}".replace(",", r"\,")
        return formatted
    except (TypeError, ValueError):
        return str(val) if val is not None else r"\text{N/A}"


def _pct(val) -> str:
    return _num(val, decimals=1) + r"\,\%"


def _eur(val, keur: bool = False) -> str:
    if keur:
        try:
            return _num(float(val) / 1000, decimals=1) + r"\,k\euro{}"
        except Exception:
            pass
    return _num(val, decimals=0) + r"\,\euro{}"


def _mwh(val) -> str:
    return _num(val, decimals=1) + r"\,MWh"


def _table(header_rows: list[str], data_rows: list[str], caption: str = "", label: str = "",
           col_spec: str = "") -> str:
    lines = []
    if not col_spec:
        col_spec = "l" + "r" * max(0, len(header_rows[0].split("&")) - 1)
    lines.append(r"\begin{tabular}{" + col_spec + "}")
    lines.append(r"\toprule")
    for h in header_rows:
        lines.append(h + r" \\")
    lines.append(r"\midrule")
    for i, row in enumerate(data_rows):
        lines.append(row + r" \\")
        if i < len(data_rows) - 1 and row.startswith(r"\midrule"):
            pass  # already has midrule
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def _load_economics() -> pd.DataFrame | None:
    """Load all economics.csv files into one DataFrame indexed by run_id."""
    dfs = []
    for run_id in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        p = RUNS / run_id / "economics.csv"
        if p.exists():
            df = pd.read_csv(p)
            df["run_id"] = run_id
            dfs.append(df)
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True).set_index("run_id")


# ---------------------------------------------------------------------------
# Individual table generators
# ---------------------------------------------------------------------------

def tab_cost_topology() -> str:
    """Annual operational cost and CO₂ — L1 vs L2 vs L3."""
    eco = _load_economics()
    header = [
        r"Level & Fuel [\euro/a] & Elec.\ [\euro/a] & CO$_2$ [\euro/a]"
        r" & Total [\euro/a] & Total CO$_2$ [t/a] & $\Delta$~CO$_2$"
    ]
    rows = []
    base_co2 = None
    for rid in ["L1", "L2", "L3"]:
        if eco is not None and rid in eco.index:
            r = eco.loc[rid]
            co2 = r.get("co2_total_t", 0)
            if base_co2 is None:
                base_co2 = co2
            delta = f"{co2 - base_co2:+,.0f}".replace(",", r"\,") + r"\,t" if base_co2 is not None else "—"
            rows.append(
                f"{rid} & {_eur(r.get('cost_fuel_eur',0))} & {_eur(r.get('cost_energy_buy_eur',0))}"
                f" & {_eur(r.get('cost_co2_eur',0))} & {_eur(r.get('cost_total_eur',0))}"
                f" & {_num(co2, 0)} & {delta}"
            )
        else:
            rows.append(f"{rid} & \\placeholder{{fuel_{rid}}} & \\placeholder{{elec_{rid}}}"
                        f" & \\placeholder{{co2eur_{rid}}} & \\placeholder{{total_{rid}}}"
                        f" & \\placeholder{{co2t_{rid}}} & —")
    return _table(header, rows, col_spec="lrrrrrr")


def tab_cost_extended() -> str:
    """Annual cost — L3 vs L3+ vs L3NL."""
    eco = _load_economics()
    header = [
        r"Level & Total [\euro/a] & Pump [\euro/a] & CO$_2$ [\euro/a]"
        r" & Total CO$_2$ [t/a] & $\Delta$~CO$_2$ vs.\ L3"
    ]
    rows = []
    base_co2 = None
    if eco is not None and "L3" in eco.index:
        base_co2 = float(eco.loc["L3", "co2_total_t"])

    for rid in ["L3", "L3plus", "L3NL"]:
        if eco is not None and rid in eco.index:
            r = eco.loc[rid]
            co2 = float(r.get("co2_total_t", 0))
            delta = f"{co2 - base_co2:+,.0f}".replace(",", r"\,") + r"\,t" if base_co2 is not None else "—"
            rows.append(
                f"{rid} & {_eur(r.get('cost_total_eur',0))} & {_eur(r.get('cost_pump_eur',0))}"
                f" & {_eur(r.get('cost_co2_eur',0))} & {_num(co2, 0)} & {delta}"
            )
        else:
            rows.append(f"{rid} & \\placeholder{{total_{rid}}} & \\placeholder{{pump_{rid}}}"
                        f" & \\placeholder{{co2eur_{rid}}} & \\placeholder{{co2t_{rid}}} & —")
    return _table(header, rows, col_spec="lrrrrr")


def tab_validation() -> str:
    """Validation against measured data — placeholder until data provided."""
    header = [r"Metric & Measured & Model & MAPE [\%] & Target [\%] & Pass?"]
    metrics = [
        "Gas consumption [MWh]", "Electricity purchase [MWh]",
        "CHP operating hours [h]", "HP operating hours [h]", "Peak import [MW]",
    ]
    rows = [
        f"{m} & \\placeholder{{meas}} & \\placeholder{{model}} & \\placeholder{{mape}}"
        f" & \\placeholder{{target}} & \\placeholder{{pass}}"
        for m in metrics
    ]
    return _table(header, rows, col_spec="lrrrrr")


def tab_computation() -> str:
    """Computational metrics per level."""
    eco = _load_economics()
    header = [r"Level & Solver & Vars & Bin. vars & Constraints & Solve time [s] & MIP gap [\%]"]
    rows = []
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        meta_path = RUNS / rid / "meta.json"
        if meta_path.exists():
            import json
            m = json.loads(meta_path.read_text())
            solver = "Gurobi" if m.get("gurobi_version") else "HiGHS"
            rows.append(
                f"{rid} & {solver} & {m.get('num_vars','—')} & {m.get('num_bin','—')}"
                f" & {m.get('num_constr','—')} & {_num(m.get('solve_time_s',0), 1)}"
                f" & {_num((m.get('mip_gap') or 0)*100, 3)}"
            )
        else:
            rows.append(f"{rid} & \\placeholder{{solver}} & — & — & — & \\placeholder{{time}} & —")
    return _table(header, rows, col_spec="lrrrrrrr")


def tab_network_params() -> str:
    """Network parameters summary."""
    header = [r"Parameter & L1 & L2 & L3 / L3$^+$ / L3$^\mathrm{NL}$"]
    params = [
        ("Nodes", "1", "8", "15"),
        ("Pipes", "0", "7", "14"),
        ("Total pipe length [m]", "—", "1{,}240", "3{,}255"),
        ("Peak demand [MW]", "76", "76", "76"),
        ("Storage [MWh / MW]", "1000 / 50", "1000 / 50", "1000 / 50"),
        (r"Roughness $\varepsilon$ [mm]", "—", "0.5", "0.5"),
        (r"$\eta_\mathrm{pump}$ [--]", "—", "0.75", "0.75"),
        (r"CO$_2$ price [\euro/t]", "1000", "1000", "1000"),
    ]
    rows = [f"{p[0]} & {p[1]} & {p[2]} & {p[3]}" for p in params]
    return _table(header, rows, col_spec="lrrr")


def tab_transport_delays() -> str:
    """Transport delays per pipe segment."""
    header = [r"Pipe & Length [m] & DN & $v_\mathrm{avg}$ [m/s] & $\tau$ [min] & $k_p$ steps"]
    rows = []
    pipes_path = RUNS / "L3plus" / "pipes.csv"
    if not pipes_path.exists():
        pipes_path = RUNS / "L3" / "pipes.csv"
    if pipes_path.exists():
        df = pd.read_csv(pipes_path)
        for _, r in df.iterrows():
            v = r.get("peak_velocity_m_s", 0) or 1.0
            tau = (r.get("length_m", 0) / (v * 60)) if v > 0 else 0
            rows.append(
                f"{r.get('pipe_id','?')} & {_num(r.get('length_m',0), 0)}"
                f" & {_num(r.get('diameter_mm',0), 0)}"
                f" & {_num(v, 2)}"
                f" & {_num(tau, 1)}"
                f" & {int(r.get('k_p_steps', 3))}"
            )
    else:
        rows = [r"— & — & — & — & — & —"]
    return _table(header, rows, col_spec="lrrrrrr")


def tab_storage() -> str:
    """Storage KPIs per level."""
    header = [r"Level & Charge [MWh] & Discharge [MWh] & Avg SOC [MWh] & Min SOC [MWh] & Max SOC [MWh]"]
    rows = []
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        p = RUNS / rid / "meta.json"
        if (RUNS / rid / "dispatch_hourly.csv").exists():
            df = pd.read_csv(RUNS / rid / "dispatch_hourly.csv")
            charge = df.get("Q_storage_charge_MW", pd.Series([0])).sum()
            discharge = df.get("Q_storage_discharge_MW", pd.Series([0])).sum()
            soc = df.get("SOC_MWh", pd.Series([0]))
            rows.append(
                f"{rid} & {_num(charge, 1)} & {_num(discharge, 1)}"
                f" & {_num(soc.mean(), 1)} & {_num(soc.min(), 1)} & {_num(soc.max(), 1)}"
            )
        else:
            rows.append(f"{rid} & \\placeholder{{charge}} & \\placeholder{{discharge}}"
                        f" & \\placeholder{{soc_avg}} & \\placeholder{{soc_min}} & \\placeholder{{soc_max}}")
    return _table(header, rows, col_spec="lrrrrr")


def tab_gap_stability() -> str:
    """Sensitivity: cost gap stability across scenarios."""
    header = [
        r"Scenario & $\Delta$cost L1--L3 [\%] & $\Delta$cost L3--L3$^+$ [\%]"
        r" & $\Delta$cost L3$^+$--L3$^\mathrm{NL}$ [\%]"
    ]
    sens_path = RUNS / "sensitivity" / "summary.csv"
    if sens_path.exists():
        df = pd.read_csv(sens_path)
        rows = []
        for _, r in df.iterrows():
            rows.append(
                f"{r.get('scenario','?')} & \\placeholder{{gap_L1_L3}}"
                f" & \\placeholder{{gap_L3_L3plus}}"
                f" & \\placeholder{{gap_L3plus_L3NL}}"
            )
    else:
        scenarios = ["baseline", "gas\\_high", "elec\\_low", "co2\\_high", "cold", "warm", "cop\\_low"]
        rows = [
            f"{s} & \\placeholder{{gap_L1_L3}} & \\placeholder{{gap_L3_L3plus}} & \\placeholder{{gap_L3plus_L3NL}}"
            for s in scenarios
        ]
    return _table(header, rows, col_spec="lrrr")


def tab_effect_hierarchy() -> str:
    """Effect hierarchy: topology vs physics vs linearization."""
    header = [r"Effect & $\Delta$cost [\euro/a] & $\Delta$cost [\%] & Driver"]
    rows = [
        r"Topology (L1$\to$L2) & \placeholder{dC_topo} & \placeholder{pct_topo} & Network losses",
        r"Granularity (L2$\to$L3) & \placeholder{dC_gran} & \placeholder{pct_gran} & Demand heterogeneity",
        r"Physics: losses (L3 basic$\to$L3$^+$) & \placeholder{dC_loss} & \placeholder{pct_loss} & Heat loss",
        r"Physics: pressure (L3$\to$L3$^+$) & \placeholder{dC_pump} & \placeholder{pct_pump} & Pump energy",
        r"Linearization (L3$^+\to$L3$^\mathrm{NL}$) & \placeholder{dC_lin} & \placeholder{pct_lin} & PWL error",
    ]
    return _table(header, rows, col_spec="lrrl")


def tab_linearization() -> str:
    """PWL linearization diagnostics per pipe."""
    header = [r"Pipe & $K$ BP & $\Delta p$ max err [Pa] & $\Delta p$ RMSE [Pa] & $\varphi$ max err & Taylor res. [K]"]
    diag_path = RUNS / "L3plus" / "linearization_diagnostics.csv"
    if diag_path.exists():
        df = pd.read_csv(diag_path)
        rows = [
            f"{r.get('pipe_id','?')} & {r.get('K_breakpoints','?')}"
            f" & {_num(r.get('dp_PWL_max_err_Pa',0), 0)}"
            f" & {_num(r.get('dp_PWL_RMSE_Pa',0), 0)}"
            f" & {_num(r.get('phi_PWL_max_err',0), 4)}"
            f" & {_num(r.get('taylor_residual_K',0), 4)}"
            for _, r in df.iterrows()
        ]
    else:
        rows = [r"— & — & — & — & — & —  \quad (run L3$^+$ first)"]
    return _table(header, rows, col_spec="lrrrrr")


def tab_pwl_breakdown() -> str:
    """Per-pipe PWL error breakdown (new table)."""
    return tab_linearization()  # same content


# ---------------------------------------------------------------------------
# Registry and dispatch
# ---------------------------------------------------------------------------

TABLES_MAP = {
    "tab_validation":       tab_validation,
    "tab_cost_topology":    tab_cost_topology,
    "tab_cost_extended":    tab_cost_extended,
    "tab_linearization":    tab_linearization,
    "tab_storage":          tab_storage,
    "tab_computation":      tab_computation,
    "tab_effect_hierarchy": tab_effect_hierarchy,
    "tab_gap_stability":    tab_gap_stability,
    "tab_transport_delays": tab_transport_delays,
    "tab_network_params":   tab_network_params,
    "tab_pwl_breakdown":    tab_pwl_breakdown,
}


def generate_all(subset: list[str] | None = None) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    targets = subset if subset else list(TABLES_MAP.keys())
    for name in targets:
        fn = TABLES_MAP.get(name)
        if fn is None:
            print(f"[SKIP] Unknown table: {name}")
            continue
        try:
            content = fn()
            out = TABLES / f"{name}.tex"
            out.write_text(content + "\n", encoding="utf-8")
            print(f"[OK] {name}.tex")
        except Exception as e:
            print(f"[ERR] {name}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", nargs="*", help="Specific table(s) to generate")
    args = parser.parse_args()
    generate_all(args.table)


if __name__ == "__main__":
    main()
