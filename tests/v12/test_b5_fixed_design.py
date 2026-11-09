"""v12 B5: CALION_FIXED_DESIGN=<yaml> -> operation-only MILP with HP MW, EK MW, TES energy/power and TES site fixed.

Validation cases (no solve) + two real 48 h runs on the full Stadtbach network through scenario_runner:
  source/S3 (C1 design: WP 8 MW + TES 146 MWh at j_man, hot charging; exercises B2 with reverse flow)
  hub/S1    (WP 8 MW at j_man + TES 146 MWh at j_hkw)
Checks: no investment binaries left free, sizes exactly as designed, CAPEX charged, Q_def = 0 (B6), balance ok (B1).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _design(tmp_path, **kw):
    d = {"run_id": "T", "hp_mw": 8.0, "ek_mw": 0.0, "tes_mwh": 146.0, "tes_site": "source"}
    d.update(kw)
    p = tmp_path / "d.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    return p


@pytest.mark.parametrize("kw,msg", [
    ({"tes_site": "elsewhere"}, "tes_site must be"),
    ({"tes_mwh": 0.0}, "inconsistent"),
    ({"hp_mw": 0.0}, "cannot charge"),
    ({"bogus": 1}, "unknown key"),
])
def test_design_validation(tmp_path, monkeypatch, kw, msg):
    from scripts.paper_2.scenario_runner import _load_fixed_design
    monkeypatch.setenv("CALION_FIXED_DESIGN", str(_design(tmp_path, **kw)))
    with pytest.raises(ValueError, match=msg):
        _load_fixed_design()


def _run(tmp_path, base, **kw):
    design = _design(tmp_path, run_id=f"B5TEST-{base}", **kw)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CALION_OUT_BASE=str(tmp_path / "runs"),
               CALION_FIXED_DESIGN=str(design), CALION_HORIZON_START="2025-01-08 00:00",
               CALION_HORIZON_END="2025-01-09 23:00", CALION_MIPGAP="0.0001")
    env.pop("CALION_RUN_TAG", None)
    r = subprocess.run([sys.executable, "-m", "scripts.paper_2.scenario_runner", "-s", base, "-g", "8"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800)
    out = tmp_path / "runs" / f"B5TEST-{base}"
    assert (out / "meta.json").exists(), r.stdout[-3000:] + r.stderr[-3000:]
    dump = json.loads((out / "full_solution_dump.json").read_text())["vars"]
    return out, dump


def _common_checks(out, dump):
    census = json.loads((out / "binary_census.json").read_text())["free_by_component"]
    assert not any(k.endswith(("_build", "_size_sel")) for k in census), census
    assert dump["hp_sb_cap_mw"]["None"] == pytest.approx(8.0)
    assert dump["tes_sb_build"]["None"] == pytest.approx(1.0)
    assert sum(dump["hp_sb_Q_def"].values()) == pytest.approx(0.0, abs=1e-6)
    assert json.loads((out / "validation.json").read_text())["status"] == "ok"
    cb = json.loads((out / "cost_breakdown.json").read_text())
    assert cb["real_costs_EUR"]["Capex_cost_EUR"]["value"] > 0


def test_source_design_c1_48h(tmp_path):
    out, dump = _run(tmp_path, "SB-S3-HK0")
    _common_checks(out, dump)
    assert sum(1 for x in dump["HKW_TO_MAN_m_dot"].values() if x < -1e-6) > 0, "needs reverse-flow hours"
    assert sum(dump["tes_sb_Qc"].values()) > 0


def test_hub_design_48h(tmp_path):
    out, dump = _run(tmp_path, "SB-S1-HK0", tes_site="hub")
    _common_checks(out, dump)
