"""v12 B9 building blocks (Weg B), 48 h C1 design on the full Stadtbach network:
  CALION_SOC_MODE=handoff (E0 fixed, end free), =free with boundary values (aux line = l_s*E0 - l_e*E_end),
  CALION_PEAK_CAP_MW (P_buy <= cap), CALION_DEMAND_CHARGE_OFF (no demand charge in the objective).
Every run: balance ok, objective residual <= 1 EUR."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path, tag, **env_extra):
    d = {"run_id": f"B9-{tag}", "hp_mw": 8.0, "ek_mw": 0.0, "tes_mwh": 146.0, "tes_site": "source"}
    (tmp_path / "d.yaml").write_text(yaml.safe_dump(d), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CALION_OUT_BASE=str(tmp_path / "runs"),
               CALION_FIXED_DESIGN=str(tmp_path / "d.yaml"), CALION_HORIZON_START="2025-01-08 00:00",
               CALION_HORIZON_END="2025-01-09 23:00", CALION_MIPGAP="0.0001", **env_extra)
    env.pop("CALION_RUN_TAG", None)
    r = subprocess.run([sys.executable, "-m", "scripts.paper_2.scenario_runner", "-s", "SB-S3-HK0", "-g", "8"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800)
    out = tmp_path / "runs" / f"B9-{tag}"
    assert (out / "meta.json").exists(), r.stdout[-3000:] + r.stderr[-2000:]
    v = json.loads((out / "full_solution_dump.json").read_text())["vars"]
    cb = json.loads((out / "cost_breakdown.json").read_text())
    vj = json.loads((out / "validation.json").read_text())
    assert vj["system_balance"]["status"] == "ok"
    assert abs(cb["residual_EUR"]) <= 1.0, cb["residual_EUR"]
    return v, cb


def _e_end(v):
    e = v["tes_sb_E"]
    return e[str(max(int(k) for k in e))]


def test_handoff_fixes_start_and_frees_end(tmp_path):
    v, _ = _run(tmp_path, "handoff", CALION_SOC_MODE="handoff", CALION_SOC_START_MWH="100")
    assert v["tes_sb_E0"]["None"] == pytest.approx(100.0)


def test_free_with_boundary_values(tmp_path):
    v, cb = _run(tmp_path, "free", CALION_SOC_MODE="free", CALION_SOC_START_VALUE="40", CALION_SOC_END_VALUE="35")
    e0, ee = v["tes_sb_E0"]["None"], _e_end(v)
    line = cb["model_aux_terms_EUR"]["SOC_boundary_value_EUR"]["value"]
    assert line == pytest.approx(40 * e0 - 35 * ee, abs=1e-3)


def test_peak_cap_and_demand_charge_off(tmp_path):
    v, cb = _run(tmp_path, "peak", CALION_PEAK_CAP_MW="0.5", CALION_DEMAND_CHARGE_OFF="1")
    assert max(v["P_buy"].values()) <= 0.5 + 1e-6
    assert cb["real_costs_EUR"]["Demand_charge_cost_EUR"]["value"] == pytest.approx(0.0, abs=1e-6)
