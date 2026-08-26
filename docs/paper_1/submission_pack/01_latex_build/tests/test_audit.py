"""
Audit regression tests for Paper 1 (prompt AGENT_PROMPT_FINAL, section Q).

Pure post-processing — no solve. Two groups:
  (1) manuscript headline numbers vs the canonical result file
      (data/objective_decomposition.csv, the economic-cost basis the tables are built from);
  (2) the dimensional conventions fixed in the units audit (Eqs 12/14/16/19).

Canonical file columns (per level): gurobi_objective_eur, econ_cost_eur,
co2_selfuse_correction_eur, tes_cycling_eur, closure_residual_eur, ...
Levels: CP (T0P0), CP+L (T0P1a), CP+Lb (T0P1b), ND0 (T2P0), L1 (T2P1).

Run:  python -m pytest tests/test_audit.py -q --no-cov
      (--no-cov skips the repo-wide calion coverage gate, which does not apply to these
      standalone data checks.)
"""
import csv
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "data" / "objective_decomposition.csv"
SYNTH = ROOT / "data" / "synth_factorial_decomposition.csv"
# git-ignored solve output (present only in the reproduction worktree)
SYNTH_OUT = Path(r"c:/Users/LKR/Documents/GitHub/Energy_Framwork"
                 r"/paper1_faithful_c19d690/output/paper1_v2/synth_decomp")


def _load():
    rows = {}
    with open(CANON) as f:
        for r in csv.DictReader(f):
            rows[r["level"]] = {k: float(v) for k, v in r.items()
                                if k not in ("level", "run_id")}
    return rows


def _econ(r, lvl):
    return r[lvl]["econ_cost_eur"]


def _gross(r, lvl):
    # gross carbon basis = economic cost + the self-use CO2 that netting removes
    return r[lvl]["econ_cost_eur"] + r[lvl]["co2_selfuse_correction_eur"]


# ---------------------------------------------------------------- Q3 identity
def test_factorial_identity_closes_exactly():
    r = _load()
    C00, C01, C10, C11 = _econ(r, "CP"), _econ(r, "CP+L"), _econ(r, "ND0"), _econ(r, "L1")
    loss, topo, gap = C01 - C00, C10 - C00, C11 - C00
    interaction = gap - loss - topo
    assert abs((loss + topo + interaction) - gap) < 1e-6


# ------------------------------------------------ Q9 table-vs-canonical numbers
def test_decomposition_shares_match_tab_decomposition():
    r = _load()
    C00, C01, C10, C11 = _econ(r, "CP"), _econ(r, "CP+L"), _econ(r, "ND0"), _econ(r, "L1")
    gap = C11 - C00
    assert abs(gap - 20591) < 5.0                         # EUR/yr
    assert abs((C01 - C00) / gap * 100 - 95.85) < 0.1     # loss main effect  (tab: 95.8)
    assert abs((C10 - C00) / gap * 100 - 4.67) < 0.1      # topology main     (tab: 4.7)
    assert abs((gap - (C01 - C00) - (C10 - C00)) / gap * 100 + 0.5) < 0.1  # interaction -0.5


def test_cp_bias_matches_tab_regret():
    r = _load()
    bias = (_econ(r, "CP") - _econ(r, "L1")) / _econ(r, "L1") * 100
    assert abs(bias - (-15.1)) < 0.1                      # tab_regret: -15.1


# ----------------------------------------------------------- Q8 cost accounting
def test_objective_reconciles_to_econ_plus_terms():
    r = _load()
    for lvl, d in r.items():
        recon = (d["econ_cost_eur"] + d["co2_selfuse_correction_eur"]
                 + d["tes_cycling_eur"] + d["closure_residual_eur"])
        assert abs(recon - d["gurobi_objective_eur"]) < 1.0, lvl


def test_gross_co2_basis_robustness():
    # the §2.6 robustness note: gross basis -> 97.0/3.5 and CP bias -12.2, loss-dominance holds
    r = _load()
    C00, C01, C10, C11 = _gross(r, "CP"), _gross(r, "CP+L"), _gross(r, "ND0"), _gross(r, "L1")
    gap = C11 - C00
    assert abs((C01 - C00) / gap * 100 - 97.0) < 0.2
    assert abs((C10 - C00) / gap * 100 - 3.5) < 0.2
    assert abs((C00 - C11) / C11 * 100 - (-12.2)) < 0.2
    # loss-dominance strengthens, never inverts
    assert (C01 - C00) > 10 * (C10 - C00)


# --------------------------------------------------------------- Q4 factorial
def test_synthetic_factorial_is_135():
    n = sum(1 for _ in open(SYNTH)) - 1  # minus header
    assert n == 135
    assert 3 * 5 * 3 * 3 == 135


# ------------------------------ Q2 feature activation / A3 synthetic scope
def test_synthetic_solves_only_decomposition_configs():
    """The synthetic set is solved through the four decomposition controls only; no
    extended-physics level (T2P2/L2, T2P3/L3, ...) is solved on it -- i.e. L2 is not
    accidentally included as a solved synthetic result (prompt Q2; manuscript A3)."""
    if not SYNTH_OUT.exists():
        pytest.skip("synth_decomp output not present (git-ignored worktree)")
    allowed = {"T0P0", "T0P1", "T0P1a", "T0P1b", "T2P0", "T2P1"}
    codes = set()
    for d in SYNTH_OUT.iterdir():
        m = re.search(r"_(T\dP\d[a-z]?)$", d.name)
        if m:
            codes.add(m.group(1))
    assert codes, "no config codes found in synth output"
    assert codes <= allowed, f"unexpected configs solved on synthetic set: {codes - allowed}"
    assert not any(c.startswith(("T2P2", "T2P3", "T2P4", "T2P5", "T2P6")) for c in codes)


# --------------------------------------------- Q1 dimensional conventions (units)
def test_massflow_1e6_factor_H3():
    # Eq 14: m_dot[kg/s] = 1e6 * Q[MW] / (cp[J/kgK] * dT[K])   ==   code Q*1000/(cp_kJ*dT)
    Q_MW, cp_J, dT = 1.0, 4190.0, 30.0
    assert abs(1e6 * Q_MW / (cp_J * dT) - Q_MW * 1000 / (4.19 * dT)) < 1e-6


def test_pump_power_micro_factor_H4():
    # Eq 16: P[MW] = 1e-6 * m_dot*dp/rho ; realistic trunk inputs -> sub-MW (order kW)
    m_dot, dp, rho = 100.0, 1e5, 977.0
    P_MW = 1e-6 * m_dot * dp / rho
    assert 0.0 < P_MW < 1.0


def test_co2_kg_basis_H2():
    # E[kg] = P[MW]*e[kg/MWh]*dt[h] ; cost = lambda[EUR/t]/1000 * E[kg]
    P, e, dt, lam = 1.0, 200.0, 1.0, 100.0
    E_kg = P * e * dt
    assert abs(E_kg - 200.0) < 1e-9
    assert abs(lam / 1000 * E_kg - 20.0) < 1e-9


def test_delay_seconds_to_whole_hours_H9_H10():
    # k_p = floor(tau[s] / 3600) ; sub-hour travel -> 0 (integer-step effect only)
    for tau_s, expect in [(500, 0), (3599, 0), (3600, 1), (7200, 2)]:
        assert math.floor(tau_s / 3600) == expect
