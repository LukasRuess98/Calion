"""v12 B1: system balance check R(t) -> validation.json status.

Dump-based (existing runs, skipped if the output dirs are absent on this machine):
  SB-PIN0 (v9)          -> ok            (R in [+0.04, +0.25] MW: junction dT step, v12-M2)
  SB-C1 = SB-REF (v10)  -> balance_fail  (v11-M1 phantom heat, R down to -23.7 MW)
  MM-PIN0 (v9)          -> balance_fail  (v12-M1: primary j_9 own demand unserved; solved BEFORE B2b.
                                          The v12 C0 re-run of MM-PIN0 must be ok -- checked in C0.)
Model-based: the 2-node cut solved with the fixed code -> ok, and identical to the independent residual.
"""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from calion.run import balance_check as bc
from tests.v12 import twonode_helper as h

OUT = Path(__file__).resolve().parents[2] / "output"


def _need(run):
    d = OUT / run
    if not (d / "full_solution_dump.json").exists():
        pytest.skip(f"{d} not available")
    return d


def test_classify_thresholds():
    assert bc.classify(np.full(10, 0.1), 1000.0)["status"] == "ok"
    assert bc.classify(np.r_[np.full(9, 0.0), -0.06], 1000.0)["status"] == "balance_fail"   # phantom hour
    assert bc.classify(np.r_[np.full(9, 0.0), 0.6], 1000.0)["status"] == "balance_fail"     # |R| > 0.5 MW
    assert bc.classify(np.full(10, 0.3), 1000.0)["status"] == "balance_fail"                # 3 MWh > 0.2 %


def test_dump_sb_pin0_ok():
    r = bc.balance_from_dump(_need("v9/SB-S0-HK0-PIN0"))
    assert r["status"] == "ok", r["reasons"]
    assert r["R_min_MW"] > 0 and abs(r["R_sum_MWh"] - 1030.7) < 1.0


def test_dump_sb_c1_balance_fail():
    r = bc.balance_from_dump(_need("v10/SB-REF-HK0"))
    assert r["status"] == "balance_fail"
    assert r["R_min_MW"] < -20 and r["hours_R_below_min"] == 4900


def test_dump_mm_pin0_pre_b2b_balance_fail():
    r = bc.balance_from_dump(_need("v9/MM-S0-HK0-PIN0"))
    assert r["status"] == "balance_fail" and r["hours_R_below_min"] > 1000


def test_merge_into_validation_sets_status(tmp_path):
    (tmp_path / "validation.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    bc.merge_into_validation(tmp_path, bc.classify(np.r_[np.zeros(5), -1.0], 100.0))
    assert json.loads((tmp_path / "validation.json").read_text())["status"] == "balance_fail"


def test_model_based_twonode_ok_and_consistent():
    model, _ = h.build(h.make_cfg(primary_demand=True, bidirectional=True))
    assert h.solve(model) == "optimal"
    r = bc.balance_from_model(model)
    assert r is not None and r["status"] == "ok", r["reasons"]
    ref = h.residual(model)["R"]
    assert np.allclose(np.array(r["R_MW"]), ref, atol=1e-6)
