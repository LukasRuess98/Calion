"""v12 B2/B2b: system heat balance closes in every hour of a 2-node cut of the real Stadtbach config.

B2  -- bidirectional feeder into a secondary node with generation (j_man): reverse AND forward hours, R(t) = 0.
       Before the fix the secondary end booked Q_consumer (>= 0) as inflow in reverse hours (v11-M1 phantom heat).
B2b -- the primary producer's own local demand must be in its nodal balance (v12-M1, MM j_9 was served for free).
Builds with the production path (workflow inputs + solver.build_model) and solves with Gurobi (48 h, seconds).
"""
import numpy as np
import pytest

from tests.v12 import twonode_helper as h

TOL = 1e-6  # MW


def _run(**kw):
    model, _ = h.build(h.make_cfg(**kw))
    term = h.solve(model)
    assert term == "optimal", term
    return h.residual(model)


def test_b2_bidirectional_secondary_node_closes_both_directions():
    r = _run(primary_demand=False, bidirectional=True)
    assert (r["mdot"] < -1e-6).sum() > 0, "test needs reverse-flow hours (j_man -> j_hkw)"
    assert (r["mdot"] > 1e-6).sum() > 0, "test needs forward-flow hours (j_hkw -> j_man)"
    assert np.abs(r["R"]).max() < TOL, f"system residual max |R| = {np.abs(r['R']).max():.4f} MW"


def test_b2_and_b2b_combined():
    r = _run(primary_demand=True, bidirectional=True)
    assert (r["mdot"] < -1e-6).sum() > 0 and (r["mdot"] > 1e-6).sum() > 0
    assert np.abs(r["R"]).max() < TOL, f"system residual max |R| = {np.abs(r['R']).max():.4f} MW"
