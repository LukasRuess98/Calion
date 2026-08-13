"""
§8 Placeholder Filler for Paper_draft_v2.tex

Step 1: Scan paper, list every \\placeholder{KEY}, generate _placeholders_template.json
Step 2: Read _placeholders.json (key→value), replace in paper, write Paper_filled.tex

Usage:
    python tools/fill_paper.py --scan          # Step 1: generate template
    python tools/fill_paper.py --fill          # Step 2: fill from _placeholders.json
    python tools/fill_paper.py --auto          # Step 2: auto-fill from run artefacts first
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER_SRC = ROOT / "docs" / "paper_1" / "Paper_draft_v2.tex"
OUT_BASE = ROOT / "output" / "paper_runs"
PLACEHOLDER_TEMPLATE = OUT_BASE / "_placeholders_template.json"
PLACEHOLDER_VALUES = OUT_BASE / "_placeholders.json"
PAPER_OUT = ROOT / "docs" / "paper_1" / "Paper_filled.tex"

PLACEHOLDER_RE = re.compile(r"\\placeholder\{([^}]+)\}")
RESULT_RE = re.compile(r"\\result\{([^}]+)\}")


# ---------------------------------------------------------------------------
# Step 1: Scan
# ---------------------------------------------------------------------------

def scan_placeholders(tex_path: Path) -> dict[str, str]:
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    keys = {}
    for m in PLACEHOLDER_RE.finditer(text):
        raw_key = m.group(1).strip()
        stable_id = _make_id(raw_key)
        keys[stable_id] = raw_key  # stable_id → original description
    return keys


def _make_id(description: str) -> str:
    """Convert a natural-language placeholder description to a stable snake_case ID."""
    s = description.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s[:60]


def generate_template(tex_path: Path = PAPER_SRC) -> dict:
    if not tex_path.exists():
        print(f"[ERR] Paper source not found: {tex_path}")
        sys.exit(1)

    found = scan_placeholders(tex_path)
    template = {k: f"FILL_{k.upper()}" for k in found}

    PLACEHOLDER_TEMPLATE.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[SCAN] Found {len(template)} placeholders.")
    print(f"[OUT]  {PLACEHOLDER_TEMPLATE}")
    print("Edit _placeholders_template.json, rename to _placeholders.json, then run --fill.")
    return template


# ---------------------------------------------------------------------------
# Auto-fill: populate values from run artefacts
# ---------------------------------------------------------------------------

def _load_economics() -> dict[str, dict]:
    eco = {}
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        p = OUT_BASE / rid / "economics.csv"
        if p.exists():
            try:
                import pandas as pd
                df = pd.read_csv(p)
                if not df.empty:
                    eco[rid] = df.iloc[0].to_dict()
            except Exception:
                pass
    return eco


def _safe(val, default: str = "N/A") -> str:
    try:
        v = float(val)
        if not math.isfinite(v):
            return default
        if v == int(v):
            return f"{int(v):,}".replace(",", r"\,")
        return f"{v:.2f}"
    except (TypeError, ValueError):
        return default


def _load_v2_analysis() -> dict[str, str]:
    """Emit the \\result{} keys used by paper_v15_skeleton.tex from the HARDENED
    v2 analysis CSVs (single source of truth). All solves <=0.1% gap (2026-08-11)."""
    import pandas as pd
    A = ROOT / "results" / "v2" / "analysis"
    v: dict[str, str] = {}

    # --- exact decomposition (decomposition_live.csv) ---
    dp = A / "decomposition_live.csv"
    if dp.exists():
        d = pd.read_csv(dp).set_index("term")["pct_of_total"]
        e = pd.read_csv(dp).set_index("term")["eur"]
        # total_pct = total gap as % of L1 economic cost (the number quoted in prose)
        if "cost_L1" in e.index and "total" in e.index:
            v["total_pct"] = f"{100 * e['total'] / e['cost_L1']:.1f}"
        for term, key in [("loss_main", "loss_pct"), ("topo_main", "topo_pct"),
                          ("interaction", "interaction_pct")]:
            if term in d.index:
                v[key] = f"{d[term]:.1f}"

    # --- regret (regret_decomp.csv), CP = copperplate vs L1 ---
    rp = A / "regret_decomp.csv"
    if rp.exists():
        r = pd.read_csv(rp).set_index("level")
        if "CP" in r.index:
            v["cp_bias_pct"] = f"{r.loc['CP', 'bias_pct']:+.1f}"
            v["cp_regret_pct"] = f"{r.loc['CP', 'regret_pct']:+.1f}"
        if "CP+L" in r.index:
            v["cpl_bias_pct"] = f"{r.loc['CP+L', 'bias_pct']:+.2f}"
            v["cpl_regret_pct"] = f"{r.loc['CP+L', 'regret_pct']:+.2f}"

    # --- synthetic factorial (synth_factorial_decomposition.csv) ---
    sp = A / "synth_factorial_decomposition.csv"
    if sp.exists():
        s = pd.read_csv(sp)
        v["synth_loss_median"] = f"{s['loss_pct_of_total'].median():.1f}"
        v["synth_topo_median"] = f"{s['topo_pct_of_total'].median():.1f}"
        v["synth_topo_absmax"] = f"{s['topo_pct_of_total'].abs().max():.2f}"
        v["synth_burden_min"] = f"{s['total_pct'].min():.1f}"
        v["synth_burden_max"] = f"{s['total_pct'].max():.1f}"

    # --- frozen-adder drift (frozen_adder_drift.csv) ---
    fp = A / "frozen_adder_drift.csv"
    if fp.exists():
        f = pd.read_csv(fp)
        best = f.sort_values("mean_abs_drift_pts").iloc[0]
        v["drift_best_mean_pts"] = f"{best['mean_abs_drift_pts']:.1f}"
        v["drift_best_max_pts"] = f"{best['max_abs_drift_pts']:.1f}"

    # --- supply-temperature flexibility (tsup_sensitivity.csv), Pillar-2 robustness ---
    tp = A / "tsup_sensitivity.csv"
    if tp.exists():
        t = pd.read_csv(tp)
        feas = t[t["velocity_viol_steps"] == 0]
        base = t.iloc[0]
        opt = feas.loc[feas["tsup_cost_eur"].idxmin()] if len(feas) else base
        save = base["tsup_cost_eur"] - opt["tsup_cost_eur"]
        v["tsup_opt_offset_k"] = f"{opt['offset_K']:.1f}"
        v["tsup_saving_eur"] = f"{save:,.0f}".replace(",", r"\,")
        v["tsup_saving_pct_op"] = f"{100 * save / ECON_L1:.1f}"   # % of L1 operating cost
        v["tsup_pump_base_mwh"] = f"{base['pump_mwh']:.1f}"
        v["tsup_pump_opt_mwh"] = f"{opt['pump_mwh']:.1f}"
        binds = t[t["velocity_viol_steps"] > 0]["offset_K"]
        if len(binds):
            v["tsup_velocity_bind_k"] = f"{binds.min():.1f}"

    # --- fidelity design rule (fidelity_rule.csv): b = lambda/(1+lambda) ---
    frp = A / "fidelity_rule.csv"
    if frp.exists():
        import numpy as np
        fr = pd.read_csv(frp).dropna(subset=["b_pred_pct", "b_meas_pct"])
        err = fr["b_pred_pct"] - fr["b_meas_pct"]
        ss = ((fr["b_meas_pct"] - fr["b_meas_pct"].mean()) ** 2).sum()
        r2 = 1 - (err ** 2).sum() / ss if ss else float("nan")
        x = (fr["lambda"] / (1 + fr["lambda"])).to_numpy()
        Amat = np.column_stack([x, np.ones(len(x))])
        (a, c), *_ = np.linalg.lstsq(Amat, fr["b_meas_pct"].to_numpy(), rcond=None)
        fit = Amat @ np.array([a, c])
        r2c = 1 - ((fr["b_meas_pct"] - fit) ** 2).sum() / ss if ss else float("nan")
        v["rule_r2"] = f"{r2:.2f}"
        v["rule_r2_cal"] = f"{r2c:.2f}"
        v["rule_mae_pts"] = f"{err.abs().mean():.1f}"
        v["rule_lambda_min"] = f"{fr['lambda'].min():.2f}"
        v["rule_lambda_max"] = f"{fr['lambda'].max():.1f}"
        v["rule_n"] = f"{len(fr)}"
        m = fr[fr.net == "Memmingen"]
        if len(m):
            v["rule_lambda_mem"] = f"{m['lambda'].iloc[0]:.2f}"
            v["rule_b_pred_mem"] = f"{m['b_pred_pct'].iloc[0]:.0f}"
            v["rule_b_meas_mem"] = f"{m['b_meas_pct'].iloc[0]:.0f}"

    # --- solved temperature-linearisation error (linearisation_solved.csv, R2.3) ---
    lsp = A / "linearisation_solved.csv"
    if lsp.exists():
        ls = pd.read_csv(lsp).set_index("window")
        if "winter" in ls.index:
            v["linsolved_winter_pct"] = f"{ls.loc['winter', 'lin_error_incumbent_pct']:+.2f}"
        if "autumn" in ls.index:
            v["linsolved_autumn_pct"] = f"{ls.loc['autumn', 'lin_error_incumbent_pct']:+.2f}"
        v["linsolved_absmax_pct"] = f"{ls[['lin_error_incumbent_pct','lin_error_bound_pct']].abs().max().max():.2f}"
        v["linsolved_gap_pct"] = f"{ls['native_qcp_gap_pct'].abs().max():.2f}"
    return v


ECON_L1 = 136142.42   # L1 (T2P1_defU) economic operating cost, hardened lineage


def auto_fill_values() -> dict[str, str]:
    """Build key→value mapping from available run artefacts."""
    values: dict[str, str] = {}
    try:
        values.update(_load_v2_analysis())
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] v2-analysis fill skipped: {exc}")
    eco = _load_economics()

    # Cost totals per level
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        if rid in eco:
            r = eco[rid]
            rid_key = rid.lower().replace("+", "plus")
            values[f"total_{rid_key}"] = _safe(r.get("cost_total_eur"))
            values[f"fuel_{rid_key}"] = _safe(r.get("cost_fuel_eur"))
            values[f"elec_{rid_key}"] = _safe(r.get("cost_energy_buy_eur"))
            values[f"co2eur_{rid_key}"] = _safe(r.get("cost_co2_eur"))
            values[f"co2t_{rid_key}"] = _safe(r.get("co2_total_t"))
            values[f"lcoh_{rid_key}"] = _safe(r.get("lcoh_eur_per_MWh_th"))
            values[f"share_hp_{rid_key}"] = _safe(r.get("share_HP_pct"))
            values[f"pump_{rid_key}"] = _safe(r.get("cost_pump_eur"))

    # Cost gaps — signed and absolute
    if "L1" in eco and "L3" in eco:
        c1 = float(eco["L1"].get("cost_total_eur", 0))
        c3 = float(eco["L3"].get("cost_total_eur", 1))
        if c3 > 0:
            values["gap_l1_l3_pct"] = f"{(c3 - c1) / c3 * 100:.1f}"
            values["gap_l1_l3_abs_eur"] = _safe(c3 - c1)
    if "L2" in eco and "L3" in eco:
        c2 = float(eco["L2"].get("cost_total_eur", 0))
        c3 = float(eco["L3"].get("cost_total_eur", 1))
        if c3 > 0:
            values["gap_l2_l3_pct"] = f"{(c3 - c2) / c3 * 100:.1f}"
    if "L3" in eco and "L3plus" in eco:
        c3 = float(eco["L3"].get("cost_total_eur", 1))
        c3p = float(eco["L3plus"].get("cost_total_eur", 0))
        if c3 > 0:
            values["gap_l3_l3plus_pct"] = f"{(c3p - c3) / c3 * 100:.2f}"
    if "L3plus" in eco and "L3NL" in eco:
        c3p = float(eco["L3plus"].get("cost_total_eur", 1))
        c3nl = float(eco["L3NL"].get("cost_total_eur", 0))
        if c3p > 0:
            values["gap_l3plus_l3nl_pct"] = f"{(c3nl - c3p) / c3p * 100:.2f}"

    # CO2 gaps
    if "L1" in eco and "L3" in eco:
        em1 = float(eco["L1"].get("co2_total_t", 0))
        em3 = float(eco["L3"].get("co2_total_t", 1))
        if em3 > 0:
            values["gap_l1_l3_co2_pct"] = f"{(em3 - em1) / em3 * 100:.1f}"
    if "L2" in eco and "L3" in eco:
        em2 = float(eco["L2"].get("co2_total_t", 0))
        em3 = float(eco["L3"].get("co2_total_t", 1))
        if em3 > 0:
            values["gap_l2_l3_co2_pct"] = f"{(em3 - em2) / em3 * 100:.1f}"

    # Pipe losses per level (MWh/year)
    for rid in ["L1", "L2", "L3", "L3plus"]:
        pipes_p = OUT_BASE / rid / "pipes.csv"
        if pipes_p.exists():
            try:
                import pandas as pd
                df_p = pd.read_csv(pipes_p)
                rid_key = rid.lower().replace("+", "plus")
                if "annual_loss_MWh" in df_p.columns:
                    total_loss = df_p["annual_loss_MWh"].sum()
                    values[f"loss_{rid_key}_mwh"] = f"{total_loss:,.0f}".replace(",", r"\,")
            except Exception:
                pass

    # Linearization error from level_consistency.json
    consist_path = OUT_BASE / "level_consistency.json"
    if consist_path.exists():
        try:
            import json as _json
            consist = _json.loads(consist_path.read_text(encoding="utf-8"))
            lin_err = consist.get("linearization_error", {})
            if lin_err:
                err_pct = lin_err.get("signed_error_pct")
                abs_err = lin_err.get("abs_error_pct")
                if err_pct is not None:
                    values["linearization_error_pct"] = f"{err_pct:+.3f}"
                    values["linearization_error_abs_pct"] = f"{abs(err_pct):.2f}"
        except Exception:
            pass

    # Solve times and model size stats from meta
    for rid in ["L1", "L2", "L3", "L3plus", "L3NL"]:
        meta_path = OUT_BASE / rid / "meta.json"
        if meta_path.exists():
            try:
                m = json.loads(meta_path.read_text())
                rid_key = rid.lower().replace("+", "plus")
                values[f"solve_time_{rid_key}"] = _safe(m.get("solve_time_s"))
                values[f"mip_gap_{rid_key}"] = _safe(
                    (m.get("mip_gap") or 0) * 100
                )
                # Variable/constraint counts (populated after stat-capture re-run)
                def _fmt_count(v):
                    if v is None:
                        return None
                    try:
                        n = int(v)
                        return f"{n:,}".replace(",", r"\,")
                    except (TypeError, ValueError):
                        return None
                for stat_key in ["num_vars", "num_bin", "num_constr", "num_quad_constr"]:
                    val = _fmt_count(m.get(stat_key))
                    if val is not None:
                        values[f"{stat_key}_{rid_key}"] = val
            except Exception:
                pass

    return values


# ---------------------------------------------------------------------------
# Step 2: Fill
# ---------------------------------------------------------------------------

def fill_paper(
    tex_path: Path = PAPER_SRC,
    values_path: Path = PLACEHOLDER_VALUES,
    out_path: Path = PAPER_OUT,
    auto: bool = False,
) -> int:
    if not tex_path.exists():
        print(f"[ERR] Paper source not found: {tex_path}")
        return 1

    text = tex_path.read_text(encoding="utf-8", errors="replace")

    # Build values dict
    values: dict[str, str] = {}

    if auto:
        auto_vals = auto_fill_values()
        values.update(auto_vals)
        print(f"[AUTO] Auto-filled {len(auto_vals)} values from run artefacts.")

    if values_path.exists():
        manual = json.loads(values_path.read_text(encoding="utf-8"))
        values.update(manual)
        print(f"[LOAD] Loaded {len(manual)} manual values from {values_path.name}.")
    elif not auto:
        print(f"[WARN] {values_path} not found. Run --scan first, then fill the template.")

    # Replace \placeholder{KEY} with \textcolor{black}{VALUE}
    not_found: list[str] = []
    replaced = 0

    def _replace(m: re.Match) -> str:
        nonlocal replaced
        raw_key = m.group(1).strip()
        stable_id = _make_id(raw_key)
        if stable_id in values:
            replaced += 1
            return r"\textcolor{black}{" + str(values[stable_id]) + "}"
        # Also try raw_key directly
        if raw_key in values:
            replaced += 1
            return r"\textcolor{black}{" + str(values[raw_key]) + "}"
        not_found.append(raw_key)
        return m.group(0)  # leave unchanged

    filled = PLACEHOLDER_RE.sub(_replace, text)

    # Also replace \result{KEY}
    def _replace_result(m: re.Match) -> str:
        nonlocal replaced
        raw_key = m.group(1).strip()
        stable_id = _make_id(raw_key)
        val = values.get(stable_id) or values.get(raw_key)
        if val is not None:
            replaced += 1
            return r"\textbf{" + str(val) + "}"
        return m.group(0)

    filled = RESULT_RE.sub(_replace_result, filled)

    out_path.write_text(filled, encoding="utf-8")
    print(f"[FILL] Replaced {replaced} placeholders.")
    if not_found:
        print(f"[WARN] {len(not_found)} placeholders remain unfilled:")
        for k in sorted(set(not_found))[:20]:
            print(f"  \\placeholder{{{k}}}")
        if len(not_found) > 20:
            print(f"  ... and {len(not_found) - 20} more")
    else:
        print("[OK] All placeholders filled.")
    print(f"[OUT] {out_path}")

    remaining = len(PLACEHOLDER_RE.findall(filled))
    print(f"[CHECK P1] Remaining \\placeholder{{}} in output: {remaining}")
    return 0 if remaining == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true", help="Step 1: scan and generate template")
    group.add_argument("--fill", action="store_true", help="Step 2: fill from _placeholders.json")
    group.add_argument("--auto", action="store_true", help="Step 2: auto-fill from run artefacts + manual overrides")
    parser.add_argument("--src", type=Path, default=PAPER_SRC, help="source .tex (default Paper_draft_v2.tex)")
    parser.add_argument("--out", type=Path, default=None, help="output .tex (default <src>_filled.tex)")
    args = parser.parse_args()

    out = args.out or args.src.with_name(args.src.stem + "_filled.tex")
    if args.scan:
        generate_template(args.src)
    elif args.fill:
        sys.exit(fill_paper(tex_path=args.src, out_path=out))
    elif args.auto:
        sys.exit(fill_paper(tex_path=args.src, out_path=out, auto=True))


if __name__ == "__main__":
    main()
