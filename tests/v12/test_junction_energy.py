"""v12 junction energy fix (author decision 2026-11-09 on v12-M2): nodes without their own heat balance no longer
swallow the dT step between incoming and outgoing pipes; the supply loss is charged exactly once.
End-to-end through scenario_runner (48 h, full networks, measured/annual temperature basis):
  fixed  -> system residual R(t) = 0 in every hour (SB and MM)
  legacy (CALION_LEGACY_JUNCTION_ENERGY=1) -> R(t) > 0 (the old offset; positive control)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path, scen, **extra):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CALION_OUT_BASE=str(tmp_path / "runs"),
               CALION_HORIZON_START="2025-01-08 00:00", CALION_HORIZON_END="2025-01-09 23:00",
               CALION_MIPGAP="0.0001", **extra)
    env.pop("CALION_RUN_TAG", None)
    r = subprocess.run([sys.executable, "-m", "scripts.paper_2.scenario_runner", "-s", scen, "-g", "4"],
                       cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=1800)
    out = tmp_path / "runs" / scen
    assert (out / "validation.json").exists(), r.stdout[-3000:]
    R = json.loads((out / "system_balance_hourly.json").read_text())["R_MW"]
    return R, json.loads((out / "validation.json").read_text())


@pytest.mark.parametrize("scen", ["SB-S0-HK0-PIN0", "MM-S0-HK0-PIN0"])
def test_fixed_balance_closes(tmp_path, scen):
    R, v = _run(tmp_path, scen)
    assert max(abs(x) for x in R) < 1e-5, (min(R), max(R))
    assert v["system_balance"]["status"] == "ok"


@pytest.mark.parametrize("scen", ["SB-S0-HK0-PIN0", "MM-S0-HK0-PIN0"])
def test_legacy_shows_offset(tmp_path, scen):
    R, _ = _run(tmp_path, scen, CALION_LEGACY_JUNCTION_ENERGY="1")
    assert sum(R) > 0.5 and min(R) > -1e-6
