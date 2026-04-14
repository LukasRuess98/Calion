"""
Validation — compare L3 model outputs against measured Stadtbach operational data.

Aggregates hourly L3 timeseries to monthly totals for four KPIs, then computes
MAPE, max monthly deviation, and systematic bias versus measured values.

Usage:
    python scripts/paper/validate_against_measured.py \
        --l3     outputs/paper/L3/pf_timeseries.csv \
        --measured data/stadtbach_measured_2023.csv \
        --outdir outputs/paper/validation/

Produces:
    validation_table.csv    — monthly comparison (12 rows × 4 variables)
    validation_summary.csv  — one row per variable: MAPE, max_dev_pct, bias_pct
    validation_results.tex  — LaTeX booktabs table fragment

Expected measured CSV format (comma-separated, 12 data rows):
    month,gas_consumption_MWh,electricity_purchase_MWh,hp_operating_hours,storage_cycles_count
    1,12500,8400,520,18
    2,...
    ...
    12,...
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DT_H = 1.0  # hourly time step [h]

# L3 column names
COL_BOILER   = "BOILER_MAIN_fuel_MW"
COL_P_BUY    = "P_buy_MW"
COL_HP_ON    = "hp_main_on"
COL_TES_CHG  = "TES_charge_MW"
COL_TES_DIS  = "TES_discharge_MW"

# Measured CSV columns
MEASURED_COLS = [
    "month",
    "gas_consumption_MWh",
    "electricity_purchase_MWh",
    "hp_operating_hours",
    "storage_cycles_count",
]

# Human-readable variable labels for output tables
VARIABLE_LABELS = {
    "gas_consumption_MWh":      "Gas consumption [MWh]",
    "electricity_purchase_MWh": "Electricity purchase [MWh]",
    "hp_operating_hours":       "HP operating hours [h]",
    "storage_cycles_count":     "Storage cycles [-]",
}

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------

MEASURED_FORMAT_HINT = """\
Expected file format  : CSV, comma-separated, 12 data rows (one per month Jan–Dec)
Expected columns      : {cols}

Example (first two rows):
  month,gas_consumption_MWh,electricity_purchase_MWh,hp_operating_hours,storage_cycles_count
  1,12500,8400,520,18
  2,11200,7600,480,16

Column descriptions:
  month                  — integer 1–12
  gas_consumption_MWh    — monthly gas energy consumed by the main boiler [MWh]
  electricity_purchase_MWh — monthly electricity purchased from the grid [MWh]
  hp_operating_hours     — number of hours the main heat pump was active per month
  storage_cycles_count   — number of charge-then-discharge cycles per month
""".format(cols=", ".join(MEASURED_COLS))


def _abort_missing_measured(path: Path) -> None:
    print(f"ERROR: Measured data file not found: {path}", file=sys.stderr)
    print("", file=sys.stderr)
    print(MEASURED_FORMAT_HINT, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_l3_timeseries(path: Path) -> pd.DataFrame:
    """Load the L3 hourly timeseries (semicolon-separated, comma decimal)."""
    if not path.exists():
        print(f"ERROR: L3 timeseries not found: {path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(path, sep=";", decimal=",", index_col=0, parse_dates=True)

    # Ensure required columns exist; fill missing ones with zero and warn.
    required = [COL_BOILER, COL_P_BUY, COL_HP_ON, COL_TES_CHG, COL_TES_DIS]
    for col in required:
        if col not in df.columns:
            print(f"  Warning: column '{col}' not found in L3 timeseries — treating as zero",
                  file=sys.stderr)
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df


def load_measured(path: Path) -> pd.DataFrame:
    """Load and validate the measured CSV."""
    if not path.exists():
        _abort_missing_measured(path)

    df = pd.read_csv(path)

    # Check required columns
    missing = [c for c in MEASURED_COLS if c not in df.columns]
    if missing:
        print(f"ERROR: Measured CSV is missing columns: {missing}", file=sys.stderr)
        print("", file=sys.stderr)
        print(MEASURED_FORMAT_HINT, file=sys.stderr)
        sys.exit(1)

    # Coerce numeric values
    for col in MEASURED_COLS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Expect exactly 12 rows
    if len(df) != 12:
        print(f"  Warning: measured CSV has {len(df)} rows; expected 12 (one per month).",
              file=sys.stderr)

    df = df.sort_values("month").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# L3 monthly aggregation
# ---------------------------------------------------------------------------

def _count_storage_cycles(chg: pd.Series, dis: pd.Series) -> int:
    """Count charge→discharge transitions within a month.

    A cycle is defined as a block of hours where TES_charge_MW > 0 is
    immediately followed (within the same month) by a block where
    TES_discharge_MW > 0.  Each such transition counts as one cycle.
    """
    in_charge = False
    cycles = 0
    for c, d in zip(chg, dis):
        if c > 0:
            in_charge = True
        elif d > 0 and in_charge:
            cycles += 1
            in_charge = False
    return cycles


def aggregate_l3_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate L3 hourly data to 12 monthly values for each KPI.

    Returns a DataFrame with columns:
        month, gas_consumption_MWh, electricity_purchase_MWh,
        hp_operating_hours, storage_cycles_count
    """
    # Derive month from the index (datetime) or from a 'month' column if present
    if hasattr(df.index, "month"):
        df = df.copy()
        df["_month"] = df.index.month
    else:
        # Fallback: assume rows are in order, assign month by row count
        print("  Warning: L3 timeseries index is not datetime; "
              "assigning months by row count (730 h each).", file=sys.stderr)
        month_labels = np.repeat(np.arange(1, 13), np.diff(
            np.round(np.linspace(0, len(df), 13)).astype(int)
        ))
        df = df.copy()
        df["_month"] = month_labels[: len(df)]

    rows = []
    for m in range(1, 13):
        mask = df["_month"] == m
        sub = df.loc[mask]

        gas_mwh   = float(sub[COL_BOILER].sum() * DT_H)
        elec_mwh  = float(sub[COL_P_BUY].sum() * DT_H)
        hp_hours  = float((sub[COL_HP_ON] > 0.5).sum())
        cycles    = _count_storage_cycles(sub[COL_TES_CHG], sub[COL_TES_DIS])

        rows.append({
            "month": m,
            "gas_consumption_MWh":      gas_mwh,
            "electricity_purchase_MWh": elec_mwh,
            "hp_operating_hours":       hp_hours,
            "storage_cycles_count":     float(cycles),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(measured: pd.Series, simulated: pd.Series) -> dict:
    """Compute MAPE, max monthly deviation, and bias for one variable.

    Parameters
    ----------
    measured, simulated:
        Aligned monthly series (length 12).

    Returns
    -------
    dict with keys: mape_pct, max_dev_pct, bias_pct
    """
    # Guard against zero measured values (avoid division by zero)
    valid = measured != 0
    if valid.sum() == 0:
        return {"mape_pct": float("nan"), "max_dev_pct": float("nan"), "bias_pct": float("nan")}

    err_pct = (simulated - measured) / measured * 100.0  # signed % error per month
    abs_err_pct = err_pct.abs()

    mape = float(abs_err_pct[valid].mean())
    max_dev = float(abs_err_pct[valid].max())
    bias = float(err_pct[valid].mean())  # positive = systematic over-estimation

    return {"mape_pct": mape, "max_dev_pct": max_dev, "bias_pct": bias}


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

def build_validation_table(measured: pd.DataFrame, simulated: pd.DataFrame) -> pd.DataFrame:
    """Build a long-format monthly comparison table.

    Columns: month, variable, measured, simulated, abs_dev_pct
    """
    variables = MEASURED_COLS[1:]  # skip 'month'
    rows = []
    for var in variables:
        for m in range(1, 13):
            meas_val = float(measured.loc[measured["month"] == m, var].iloc[0])
            sim_val  = float(simulated.loc[simulated["month"] == m, var].iloc[0])
            dev_pct  = abs(sim_val - meas_val) / meas_val * 100.0 if meas_val != 0 else float("nan")
            rows.append({
                "month":        m,
                "month_name":   MONTH_NAMES[m - 1],
                "variable":     var,
                "measured":     round(meas_val, 2),
                "simulated":    round(sim_val, 2),
                "abs_dev_pct":  round(dev_pct, 2),
            })
    return pd.DataFrame(rows)


def build_summary_table(measured: pd.DataFrame, simulated: pd.DataFrame) -> pd.DataFrame:
    """Build one-row-per-variable summary: MAPE, max_dev_pct, bias_pct."""
    variables = MEASURED_COLS[1:]
    rows = []
    for var in variables:
        m_vals = measured.set_index("month")[var]
        s_vals = simulated.set_index("month")[var]
        metrics = compute_metrics(m_vals, s_vals)

        annual_measured  = float(m_vals.sum())
        annual_simulated = float(s_vals.sum())
        annual_bias_pct  = (annual_simulated - annual_measured) / annual_measured * 100.0 \
                           if annual_measured != 0 else float("nan")

        rows.append({
            "variable":          var,
            "label":             VARIABLE_LABELS[var],
            "annual_measured":   round(annual_measured, 1),
            "annual_simulated":  round(annual_simulated, 1),
            "annual_bias_pct":   round(annual_bias_pct, 2),
            "mape_pct":          round(metrics["mape_pct"], 2),
            "max_dev_pct":       round(metrics["max_dev_pct"], 2),
            "bias_pct":          round(metrics["bias_pct"], 2),
        })
    return pd.DataFrame(rows)


def build_latex_table(summary: pd.DataFrame) -> str:
    """Render a booktabs-style LaTeX table fragment.

    Columns: Variable | Measured annual | L3 simulated annual | MAPE [%]
    """
    lines = [
        r"% Auto-generated by validate_against_measured.py — do not edit manually",
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Validation of L3 model against measured Stadtbach 2023 data.}",
        r"  \label{tab:validation}",
        r"  \begin{tabular}{lrrr}",
        r"    \toprule",
        r"    Variable & Measured (annual) & L3 simulated (annual) & MAPE [\%] \\",
        r"    \midrule",
    ]

    for _, row in summary.iterrows():
        label   = row["label"]
        meas    = row["annual_measured"]
        sim     = row["annual_simulated"]
        mape    = row["mape_pct"]

        # Format numbers: integers for MWh / hours / cycles, one decimal otherwise
        def _fmt(v):
            if abs(v) >= 100:
                return f"{v:,.0f}"
            return f"{v:.1f}"

        lines.append(
            f"    {label} & {_fmt(meas)} & {_fmt(sim)} & {mape:.1f} \\\\"
        )

    lines += [
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------

def print_report(summary: pd.DataFrame) -> None:
    """Print a compact validation report to stdout."""
    col_w = 28
    print()
    print("=" * 72)
    print("VALIDATION REPORT — L3 model vs. Stadtbach measured data 2023")
    print("=" * 72)
    header = (
        f"{'Variable':<{col_w}}  {'Meas. annual':>14}  {'Sim. annual':>13}"
        f"  {'MAPE':>7}  {'MaxDev':>8}  {'Bias':>7}"
    )
    print(header)
    print("-" * 72)
    for _, row in summary.iterrows():
        print(
            f"{row['label']:<{col_w}}  {row['annual_measured']:>14,.1f}  "
            f"{row['annual_simulated']:>13,.1f}  "
            f"{row['mape_pct']:>6.1f}%  "
            f"{row['max_dev_pct']:>7.1f}%  "
            f"{row['bias_pct']:>+6.1f}%"
        )
    print("-" * 72)
    print("  MAPE   = mean absolute percentage error across 12 months")
    print("  MaxDev = worst single month absolute deviation")
    print("  Bias   = mean signed error (+ = model over-estimates)")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate L3 model outputs against measured Stadtbach data."
    )
    parser.add_argument(
        "--l3",
        default="outputs/paper/L3/pf_timeseries.csv",
        help="Path to L3 hourly timeseries CSV (semicolon-sep, comma decimal). "
             "Default: outputs/paper/L3/pf_timeseries.csv",
    )
    parser.add_argument(
        "--measured",
        default="data/stadtbach_measured_2023.csv",
        help="Path to measured operational data CSV. "
             "Default: data/stadtbach_measured_2023.csv",
    )
    parser.add_argument(
        "--outdir",
        default="outputs/paper/validation",
        help="Directory for output files. Default: outputs/paper/validation/",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    l3_path       = Path(args.l3)
    measured_path = Path(args.measured)
    outdir        = Path(args.outdir)

    # -- Load data -------------------------------------------------------
    print(f"Loading L3 timeseries  : {l3_path}")
    l3_df = load_l3_timeseries(l3_path)
    print(f"  {len(l3_df)} rows loaded  ({l3_df.index.min()} — {l3_df.index.max()})")

    print(f"Loading measured data  : {measured_path}")
    measured_df = load_measured(measured_path)  # exits with code 1 if file absent
    print(f"  {len(measured_df)} monthly rows loaded")

    # -- Aggregate L3 to monthly -----------------------------------------
    print("Aggregating L3 timeseries to monthly totals...")
    simulated_df = aggregate_l3_monthly(l3_df)

    # -- Compute outputs -------------------------------------------------
    val_table = build_validation_table(measured_df, simulated_df)
    summary   = build_summary_table(measured_df, simulated_df)
    latex     = build_latex_table(summary)

    # -- Write outputs ---------------------------------------------------
    outdir.mkdir(parents=True, exist_ok=True)

    p_table   = outdir / "validation_table.csv"
    p_summary = outdir / "validation_summary.csv"
    p_latex   = outdir / "validation_results.tex"

    val_table.to_csv(p_table,   index=False, sep=";")
    summary.to_csv(p_summary,   index=False, sep=";")
    p_latex.write_text(latex, encoding="utf-8")

    print(f"\nOutputs written to {outdir}/")
    print(f"  {p_table.name}")
    print(f"  {p_summary.name}")
    print(f"  {p_latex.name}")

    # -- Console report --------------------------------------------------
    print_report(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
