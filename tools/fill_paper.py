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


def auto_fill_values() -> dict[str, str]:
    """Build key→value mapping from available run artefacts."""
    values: dict[str, str] = {}
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
    args = parser.parse_args()

    if args.scan:
        generate_template()
    elif args.fill:
        sys.exit(fill_paper())
    elif args.auto:
        sys.exit(fill_paper(auto=True))


if __name__ == "__main__":
    main()
