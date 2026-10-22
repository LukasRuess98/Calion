"""B3 (Bau-Entscheidungen) + B4 (Konvergenz/Provenienz) Tabellen.
Read-only: liest nur bestehende output/-Dateien, kein Solve, keine Code-Aenderung.
Quelle fuer Build-Zustaende: geometry.csv / cost_breakdown.json (NICHT design_helpers-Logzeilen, bekannter Bug).
Gap/Solve-Zeit/Solution-count: aus dem Gurobi-Log (massgeblich bei Widerspruch zu meta.json).
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # repo root
OUT_B3 = ROOT / "docs/paper_2/agent_reports/tables/B3_bau_entscheidungen.csv"
OUT_B4 = ROOT / "docs/paper_2/agent_reports/tables/B4_konvergenz_provenienz.csv"

TES_NODE_MAP = {"S1": "j_hkw", "S2": "j_man", "S3": "j_man", None: "-", "null": "-"}

# AC1/AC2-style env recipe keys we scan for in chain.output (if present)
ENV_KEYS = [
    "CALION_TES_C0_SCALE", "CALION_TES_POWER_CAPEX", "CALION_TES_HMAX", "CALION_TES_RHD",
    "CALION_TES_P2E_HOURS", "CALION_TES_POWER_MAX", "CALION_WARMSTART_FROM",
    "CALION_WARMSTART_DUMP", "CALION_SEED_FILL_ZERO", "CALION_MIPFOCUS", "CALION_TIMELIMIT",
    "CALION_MIPGAP", "CALION_NO_SOLFILES",
]

RUN_DIRS = []
for pat in ["output/v7_final/*", "output/_z3/*/paper2_runs/*", "output/_z3b/*/paper2_runs/*",
            "output/_parallel_aa3/*/paper2_runs/*", "output/_s2/*/paper2_runs/*"]:
    RUN_DIRS.extend(sorted((ROOT / "").glob(pat)))

RUN_GROUP_OF = {
    "v7_final": "v7_final", "_z3": "Z3", "_z3b": "Z3b", "_parallel_aa3": "AA3", "_s2": "Stage2",
}


def run_group_for(path: Path) -> str:
    parts = path.parts
    for key, label in RUN_GROUP_OF.items():
        if key in parts:
            return label
    return "unknown"


def load_json(p: Path):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def load_geometry(p: Path):
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else None


def max_col(csv_path: Path, col: str):
    if not csv_path.exists():
        return None
    try:
        with open(csv_path, encoding="utf-8") as f:
            r = csv.DictReader(f)
            if col not in (r.fieldnames or []):
                return None
            best = 0.0
            for row in r:
                try:
                    v = float(row[col])
                    if v > best:
                        best = v
                except (ValueError, TypeError):
                    pass
            return best
    except Exception:
        return None


def find_chain_output(run_dir: Path):
    # Stage-2 style: .../<job>/chain.output two levels up from paper2_runs/<scen>
    cand = run_dir.parent.parent / "chain.output"
    if cand.exists():
        return cand
    return None


SHARED_GLOBAL_LOGDIR = (ROOT / "output" / "logs").resolve()


def find_gurobi_log(run_dir: Path, scen_id: str):
    # try sibling logs/ dir (Stage2/AA3 convention) two levels up FIRST (job-isolated,
    # trustworthy). Only fall back to the global output/logs/ dir (shared across MANY
    # unrelated campaigns over the whole project history -- confirmed contaminated even
    # taking the LAST "Best objective" occurrence, since later unrelated runs using the
    # same scenario_id keep appending to it) as a last resort, flagged separately.
    for base in [run_dir.parent.parent, run_dir.parent]:
        cand = base / "logs" / f"gurobi_{scen_id}.log"
        if cand.exists() and cand.resolve() != SHARED_GLOBAL_LOGDIR / cand.name:
            return cand, False
    cand = SHARED_GLOBAL_LOGDIR / f"gurobi_{scen_id}.log"
    if cand.exists():
        return cand, True
    return None, False


def parse_gurobi_log(log_path: Path):
    if log_path is None or not log_path.exists():
        return {}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    out = {}
    for key, pat in [
        ("threads", r"Set parameter Threads to value (\d+)"),
        ("mipfocus", r"Set parameter MIPFocus to value (\d+)"),
        ("mipgap_param", r"Set parameter MIPGap to value ([\d.]+)"),
        ("timelimit_param", r"Set parameter TimeLimit to value ([\d.]+)"),
        ("cuts", r"Set parameter Cuts to value (\d+)"),
        ("nodefilestart", r"Set parameter NodefileStart to value ([\d.]+)"),
    ]:
        # Same cumulative-log trap as "Best objective" below -- take the LAST occurrence,
        # which belongs to the final/current solve session, not an old stale one.
        matches = re.findall(pat, text)
        out[key] = matches[-1] if matches else None
    sol_counts = re.findall(r"Solution count (\d+):", text)
    out["solution_count_log"] = sol_counts[-1] if sol_counts else None
    # KNOWN TRAP (Stage-1-Befund C2/verify_solver_params.py): manche Logfiles unter
    # output/logs/ sind KUMULATIV -- enthalten viele aufeinanderfolgende Solve-Sessions
    # dieses scenario_id ueber die ganze Projekthistorie. Nur der LETZTE "Best objective"-
    # Treffer ist der des tatsaechlich aktuellen/finalen Laufs -- re.findall + [-1], NIE
    # re.search (das greift den ERSTEN, oft veralteten Treffer).
    best_all = re.findall(r"Best objective ([\d.e+-]+), best bound ([\d.e+-]+), gap ([\d.]+)%", text)
    if best_all and best_all[-1][0] != "-":
        out["ub_log"] = float(best_all[-1][0])
        out["lb_log"] = float(best_all[-1][1])
        out["gap_log_pct"] = float(best_all[-1][2])
        out["cumulative_log_n_sessions"] = len(best_all)
    else:
        out["ub_log"] = out["lb_log"] = out["gap_log_pct"] = None
        out["cumulative_log_n_sessions"] = len(best_all)
    out["time_limit_reached"] = "Time limit reached" in text
    out["optimal_found"] = "Optimal solution found" in text
    mip_start_all = re.findall(r"Loaded user MIP start with objective ([\d.e+-]+)", text)
    out["mip_start_obj"] = float(mip_start_all[-1]) if mip_start_all else None
    return out


def parse_env_recipe(chain_output: Path):
    if chain_output is None or not chain_output.exists():
        return {}
    text = chain_output.read_text(encoding="utf-8", errors="replace")
    found = {}
    for k in ENV_KEYS:
        # look for log lines that echo the env var name with a value, or just note presence
        m = re.search(rf"{k}[=:]\s*([^\s,)\]]+)", text)
        if m:
            found[k] = m.group(1)
    return found


b3_rows = []
b4_rows = []

for run_dir in RUN_DIRS:
    scen_id = run_dir.name
    geom_path = run_dir / "geometry.csv"
    meta_path = run_dir / "meta.json"
    cost_path = run_dir / "cost_breakdown.json"
    smeta_path = run_dir / "scenario_meta.json"
    dispatch_path = run_dir / "dispatch_per_asset.csv"

    if not meta_path.exists():
        continue  # not a real solved run dir

    meta = load_json(meta_path) or {}
    geom = load_geometry(geom_path)
    cost = load_json(cost_path)
    smeta = load_json(smeta_path)
    group = run_group_for(run_dir)
    network = "MM" if scen_id.startswith("MM") else ("SB" if scen_id.startswith("SB") else "?")

    notes = []
    if "_INVALID" in str(run_dir) or "resolve\\" in str(run_dir).replace("/", "\\") and "resolve2" not in str(run_dir) and "sb_s2_resolve" in str(run_dir) and "sb_s2_resolve2" not in str(run_dir):
        pass

    # --- B3 ---
    build_tes = hp_mw = ek_mw = tes_e = tes_v = tes_cap = None
    tes_node = "-"
    tes_capex_annuity = None
    if geom is not None:
        build_tes = geom.get("build")
        tes_e = geom.get("E_TES_max_MWh")
        tes_v = geom.get("V_TES_m3")
        tes_cap = geom.get("cap_power_MW")
    if smeta is not None:
        tes_node_code = smeta.get("tes_node")
        tes_node = TES_NODE_MAP.get(tes_node_code, tes_node_code or "-")
    hp_mw = max_col(dispatch_path, "hp_sb_MW")
    if hp_mw is None:
        hp_mw = max_col(dispatch_path, "hp_mm_MW")
    if cost is not None:
        tes_capex_annuity = cost.get("real_costs_EUR", {}).get("Capex_cost_EUR", {}).get("value")
        obj_eur = cost.get("objective_total_EUR")
    else:
        obj_eur = meta.get("obj_eur") or meta.get("objective")
    if hp_mw is None:
        notes.append("HP-Kapazitaet: fehlt (keine dispatch_per_asset.csv oder Spalte nicht gefunden)")
    notes.append("EK-Kapazitaet: fehlt (kein eindeutiges Export-Feld identifiziert, siehe A2d)")
    notes.append("TES/HP-CAPEX-Annuitaet NICHT separierbar aus Capex_cost_EUR (enthaelt auch Rohr/EK)")

    b3_rows.append({
        "scenario_id": scen_id, "run_group": group, "source_path": str(run_dir.relative_to(ROOT)),
        "build_HP": 1 if (hp_mw or 0) > 0.01 else ("" if hp_mw is None else 0),
        "HP_capacity_MW": round(hp_mw, 4) if hp_mw is not None else "",
        "HP_node": "j_man (vermutet, fix, siehe Stadtbach_topo.yaml Kommentar)" if network == "SB" else "",
        "build_EK": "", "EK_capacity_MW": "", "EK_node": "",
        "build_TES": build_tes if build_tes is not None else "",
        "TES_E_max_MWh": tes_e or "", "TES_V_m3": tes_v or "", "TES_cap_power_MW": tes_cap or "",
        "TES_node": tes_node,
        "TES_capex_annuity_EUR_per_yr": "fehlt: nicht separierbar von HP/EK/Rohr" if tes_capex_annuity is None else round(tes_capex_annuity, 2),
        "HPEK_capex_annuity_EUR_per_yr": "fehlt: nicht separierbar",
        "obj_eur": round(obj_eur, 2) if obj_eur else "",
        "notes": "; ".join(notes),
    })

    # --- B4 ---
    log_path, log_is_shared = find_gurobi_log(run_dir, scen_id)
    log_data = parse_gurobi_log(log_path)
    chain_out = find_chain_output(run_dir)
    env_recipe = parse_env_recipe(chain_out)

    meta_gap = meta.get("mip_gap")
    meta_gap_pct = round(meta_gap * 100, 4) if isinstance(meta_gap, (int, float)) else None
    log_gap_pct = log_data.get("gap_log_pct")
    meta_vs_log = ""
    if log_is_shared:
        # Shared, multi-campaign logfile (output/logs/) -- confirmed unreliable even with
        # "take last occurrence" (later unrelated runs reusing the same scenario_id keep
        # appending). meta.json is authoritative here instead (cross-checked against the
        # reference table in the task, matches exactly for all 5 spot-check rows).
        log_gap_pct = None
        log_data["ub_log"] = None
        log_data["lb_log"] = None
        meta_vs_log = ("NICHT PRUEFBAR: gurobi_%s.log ist ein GEMEINSAMES Mehrfach-Kampagnen-Logfile "
                       "(output/logs/, %s Sessions, auch von spaeteren/unverwandten Laeufen mit "
                       "demselben scenario_id kontaminiert) -- meta.json verwendet, nicht das Log"
                       % (scen_id, log_data.get("cumulative_log_n_sessions")))
    elif meta_gap_pct is not None and log_gap_pct is not None:
        if abs(meta_gap_pct - log_gap_pct) > 0.01:
            meta_vs_log = f"ABWEICHUNG: meta.json={meta_gap_pct}% vs. Log={log_gap_pct}% -> Log gilt"
        else:
            meta_vs_log = "uebereinstimmend"
    elif log_gap_pct is None and log_path is None:
        meta_vs_log = "fehlt: kein Gurobi-Log gefunden, meta.json ungeprueft verwendet"

    solcount_meta = meta.get("solution_count")
    solcount_log = None if log_is_shared else log_data.get("solution_count_log")
    solcount_note = ""
    if log_is_shared:
        solcount_note = "nicht pruefbar (gemeinsames Logfile, siehe meta_vs_log)"
    elif solcount_log is not None and str(solcount_meta) != str(solcount_log):
        solcount_note = f"meta.json solution_count={solcount_meta} WEICHT ab von Log={solcount_log} (Defekt 15) -> Log gilt"

    git_sha = meta.get("git_sha", "")
    git_reliable = "ja"
    # heuristic: Stage-2/AA3-late runs during the shared-worktree AC-block period are unreliable
    if group in ("Stage2",) or "c0x1.3" in scen_id.lower() or "c0x1.5" in scen_id.lower() or "c0x2.0" in str(run_dir).lower():
        git_reliable = "NEIN (geteiltes Arbeitsverzeichnis, siehe A2/A3 git_sha-Befund)"

    b4_rows.append({
        "scenario_id": scen_id, "run_group": group, "network": network,
        "source_path": str(run_dir.relative_to(ROOT)),
        "UB_obj_eur": log_data.get("ub_log") if log_data.get("ub_log") is not None else (meta.get("obj_eur") or meta.get("objective")),
        "LB_bound": log_data.get("lb_log") if log_data.get("lb_log") is not None else "fehlt: kein Log",
        "LB_source": "belegt (Log)" if log_data.get("lb_log") is not None else "fehlt",
        "mip_gap_pct_log": log_gap_pct if log_gap_pct is not None else "fehlt: kein Log",
        "mip_gap_pct_meta": meta_gap_pct,
        "meta_vs_log": meta_vs_log,
        "status": meta.get("status") or meta.get("solver_status") or ("maxTimeLimit" if log_data.get("time_limit_reached") else ("optimal" if log_data.get("optimal_found") else "")),
        "solve_time_s": meta.get("solve_s") or meta.get("solve_time_s") or "",
        "solution_count_log": solcount_log or "fehlt: kein Log",
        "solution_count_meta": solcount_meta,
        "solcount_note": solcount_note,
        "threads": log_data.get("threads") or "",
        "mipfocus": log_data.get("mipfocus") or "",
        "cuts": log_data.get("cuts") or "",
        "mipgap_param": log_data.get("mipgap_param") or "",
        "timelimit_param": log_data.get("timelimit_param") or "",
        "mip_start_obj": log_data.get("mip_start_obj") or "",
        "warmstart_source": env_recipe.get("CALION_WARMSTART_FROM") or env_recipe.get("CALION_WARMSTART_DUMP") or "unbekannt",
        "seed_fill_zero": env_recipe.get("CALION_SEED_FILL_ZERO") or "",
        "c0_scale": env_recipe.get("CALION_TES_C0_SCALE") or "",
        "env_recipe_other": ";".join(f"{k}={v}" for k, v in env_recipe.items() if k not in ("CALION_WARMSTART_FROM", "CALION_WARMSTART_DUMP", "CALION_SEED_FILL_ZERO", "CALION_TES_C0_SCALE")) or "fehlt: kein chain.output gefunden/geparst",
        "git_sha": git_sha,
        "git_sha_verlaesslich": git_reliable,
        "wall_clock_timestamp": meta.get("wall_clock", ""),
        "log_is_cumulative": f"JA ({log_data.get('cumulative_log_n_sessions')} Sessions im selben Logfile, letzter Treffer verwendet)" if (log_data.get("cumulative_log_n_sessions") or 0) > 1 else "nein",
        "notes": "FAILED Versuch, superseded by *_resolve2" if "sb_s2_resolve" == scen_id.lower().replace("-", "_") or (scen_id == "SB-S2-HK0" and "sb_s2_resolve" in str(run_dir) and "resolve2" not in str(run_dir)) else "",
    })

OUT_B3.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_B3, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(b3_rows[0].keys()))
    w.writeheader()
    for r in b3_rows:
        w.writerow(r)

with open(OUT_B4, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(b4_rows[0].keys()))
    w.writeheader()
    for r in b4_rows:
        w.writerow(r)

print(f"B3: {len(b3_rows)} rows -> {OUT_B3}")
print(f"B4: {len(b4_rows)} rows -> {OUT_B4}")
