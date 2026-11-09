"""v12 B4: every objective term reported individually; residual vs pyo.value(model.obj) <= 1 EUR.

Cause of the v10 C2 residual (82,204.43 EUR): the TES cycling cost (cycling_cost_eur_per_mwh = 2 EUR/MWh x
(Qc + Qd) = 2 x 41,102.2 MWh) was added to the FUEL bucket of the objective but never reported as a cost line.
Test: 48 h run of the C1 design (TES cycles) -> Storage_cycling_cost_EUR = 2 x throughput, residual <= 1 EUR.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_c2_v10_residual_is_exactly_the_cycling_cost():
    run = ROOT / "output" / "v10" / "SB-S1-HK0"
    if not (run / "full_solution_dump.json").exists():
        pytest.skip("v10 C2 not available")
    v = json.loads((run / "full_solution_dump.json").read_text())["vars"]
    thr = sum(v["tes_sb_Qc"].values()) + sum(v["tes_sb_Qd"].values())
    res = json.loads((run / "cost_breakdown.json").read_text())["residual_EUR"]
    assert res == pytest.approx(2.0 * thr, abs=1e-3)


def test_residual_closed_with_cycling_line(tmp_path):
    d = {"run_id": "B4TEST", "hp_mw": 8.0, "ek_mw": 0.0, "tes_mwh": 146.0, "tes_site": "source"}
    (tmp_path / "d.yaml").write_text(yaml.safe_dump(d), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CALION_OUT_BASE=str(tmp_path / "runs"),
               CALION_FIXED_DESIGN=str(tmp_path / "d.yaml"), CALION_HORIZON_START="2025-01-08 00:00",
               CALION_HORIZON_END="2025-01-09 23:00", CALION_MIPGAP="0.0001")
    env.pop("CALION_RUN_TAG", None)
    r = subprocess.run([sys.executable, "-m", "scripts.paper_2.scenario_runner", "-s", "SB-S3-HK0", "-g", "8"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800)
    out = tmp_path / "runs" / "B4TEST"
    assert (out / "cost_breakdown.json").exists(), r.stdout[-3000:]
    cb = json.loads((out / "cost_breakdown.json").read_text())
    v = json.loads((out / "full_solution_dump.json").read_text())["vars"]
    thr = sum(v["tes_sb_Qc"].values()) + sum(v["tes_sb_Qd"].values())
    assert thr > 0
    assert cb["model_aux_terms_EUR"]["Storage_cycling_cost_EUR"]["value"] == pytest.approx(2.0 * thr, rel=1e-6)
    assert abs(cb["residual_EUR"]) <= 1.0, cb["residual_EUR"]
    vj = json.loads((out / "validation.json").read_text())
    assert vj["objective_residual"]["pass"] is True
