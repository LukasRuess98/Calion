"""Paper 2 LaTeX table generator.

Reads scenarios_kpis.csv and sensitivity.csv from output/paper2_runs/
and generates booktabs LaTeX table snippets in output/paper2_runs/tables/.

Tables:
  tab_p2_scenarios_kpi.tex — Main KPI table (20 scenarios × economic KPIs)
  tab_p2_sizing.tex        — Component sizing (Q_WP, Q_EK, V_TES, h_TES, E_TES)
  tab_p2_sensitivity.tex   — Tornado sensitivity (±% TAC per parameter)

Usage:
  python tools/tablegen_p2.py
  Or called from run_paper2_full.py phase 5.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _r(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fval(v, fmt=".0f", na="—") -> str:
    try:
        return format(float(v), fmt)
    except (TypeError, ValueError):
        return na


def _tex_escape(s: str) -> str:
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def write_scenarios_kpi_table(out_base: Path, table_dir: Path) -> Path:
    """Table 1: 20-scenario KPI comparison (economic + environmental)."""
    rows = _r(out_base / "scenarios_kpis.csv")
    if not rows:
        return table_dir / "tab_p2_scenarios_kpi.tex"

    lines = [
        r"\begin{tabular}{llrrrrr}",
        r"  \toprule",
        r"  Scenario & Network & TAC & LCOH & CAPEX & CO\textsubscript{2} & \% cost red. \\",
        r"  & & [k\euro/a] & [\euro/MWh] & [k\euro/a] & [t/a] & [\%] \\",
        r"  \midrule",
    ]

    prev_network = None
    for r in rows:
        network = r.get("network", "")
        if prev_network and network != prev_network:
            lines.append(r"  \midrule")
        prev_network = network

        scen_id = _tex_escape(r.get("scenario_id", ""))
        net = "MM" if "memmingen" in network else "SB"
        bc_flag = r" (BC)" if r.get("baseline") in ("True", True, "true") else ""
        tac = _fval(float(r.get("TAC_eur_per_a") or 0) / 1000, ".0f")
        lcoh = _fval(r.get("LCOH_eur_per_MWh"), ".1f")
        capex_raw = r.get("CAPEX_annual_eur_per_a")
        capex = _fval(float(capex_raw) / 1000, ".0f") if capex_raw else "—"
        co2 = _fval(r.get("co2_t_per_a"), ".0f")
        cost_red = _fval(r.get("cost_reduction_pct"), ".1f")
        lines.append(
            f"  {scen_id}{bc_flag} & {net} & {tac} & {lcoh} & {capex} & {co2} & {cost_red} \\\\"
        )

    lines += [
        r"  \bottomrule",
        r"\end{tabular}",
    ]
    path = table_dir / "tab_p2_scenarios_kpi.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_sizing_table(out_base: Path, table_dir: Path) -> Path:
    """Table 2: Optimal component sizing per optimization scenario."""
    rows = _r(out_base / "scenarios_kpis.csv")
    opt_rows = [r for r in rows if r.get("baseline") not in ("True", True, "true")]

    lines = [
        r"\begin{tabular}{lrrrrr}",
        r"  \toprule",
        r"  Scenario & $\dot{Q}_\mathrm{WP}$ & $\dot{Q}_\mathrm{EK}$ & $V_\mathrm{TES}$ & $h_\mathrm{TES}$ & $E_\mathrm{TES}$ \\",
        r"  & [MW] & [MW] & [m\textsuperscript{3}] & [m] & [MWh] \\",
        r"  \midrule",
    ]
    for r in opt_rows:
        scen = _tex_escape(r.get("scenario_id", ""))
        q_wp = _fval(r.get("Q_WP_opt_MW"), ".1f")
        q_ek = _fval(r.get("Q_EK_opt_MW"), ".1f")
        v = _fval(r.get("V_TES_m3"), ".0f")
        h = _fval(r.get("h_TES_m"), ".1f")
        e = _fval(r.get("E_TES_MWh"), ".0f")
        lines.append(f"  {scen} & {q_wp} & {q_ek} & {v} & {h} & {e} \\\\")

    lines += [r"  \bottomrule", r"\end{tabular}"]
    path = table_dir / "tab_p2_sizing.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_sensitivity_table(out_base: Path, table_dir: Path) -> Path:
    """Table 3: Sensitivity tornado (parameter × ΔCost%)."""
    rows = _r(out_base / "sensitivity.csv")
    if not rows:
        path = table_dir / "tab_p2_sensitivity.tex"
        path.write_text(
            r"\begin{tabular}{l}\toprule No sensitivity data yet\\\bottomrule\end{tabular}",
            encoding="utf-8",
        )
        return path

    params_seen = {}
    for r in rows:
        param = r.get("param", "")
        delta = _try_float(r.get("delta_pct"))
        if param not in params_seen:
            params_seen[param] = []
        if delta is not None:
            params_seen[param].append((r.get("variant", ""), delta))

    param_labels = {
        "c_el": r"Electricity price $c_\mathrm{el}$",
        "c_co2": r"CO\textsubscript{2} price $c_\mathrm{CO_2}$",
        "alpha_wp": r"WP CAPEX $\alpha_\mathrm{WP}$",
        "Q_AW_max": r"Waste heat availability",
        "delta_max": r"DSM potential $\delta_\mathrm{max}$",
        "discount_rate": r"Discount rate $i$",
    }

    lines = [
        r"\begin{tabular}{lrr}",
        r"  \toprule",
        r"  Parameter & $\Delta\text{TAC}_\text{low}$ [\%] & $\Delta\text{TAC}_\text{high}$ [\%] \\",
        r"  \midrule",
    ]
    for param, variants in params_seen.items():
        label = param_labels.get(param, _tex_escape(param))
        deltas = [d for _, d in variants]
        low = _fval(min(deltas) if deltas else None, "+.1f")
        high = _fval(max(deltas) if deltas else None, "+.1f")
        lines.append(f"  {label} & {low} & {high} \\\\")

    lines += [r"  \bottomrule", r"\end{tabular}"]
    path = table_dir / "tab_p2_sensitivity.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _try_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def generate_all_tables(out_base: Path, table_dir: Path) -> None:
    """Generate all Paper 2 LaTeX tables."""
    table_dir.mkdir(parents=True, exist_ok=True)
    p1 = write_scenarios_kpi_table(out_base, table_dir)
    p2 = write_sizing_table(out_base, table_dir)
    p3 = write_sensitivity_table(out_base, table_dir)
    print(f"Tables written:\n  {p1}\n  {p2}\n  {p3}")


if __name__ == "__main__":
    out_base = _ROOT / "output" / "paper2_runs"
    table_dir = out_base / "tables"
    generate_all_tables(out_base, table_dir)
