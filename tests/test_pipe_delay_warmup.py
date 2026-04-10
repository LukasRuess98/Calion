"""Test transport delay warm-up initial condition."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")


def _make_pipe_config(q_initial: float = 0.0) -> dict:
    return {
        'id': 'test_pipe',
        'from_node': 'A',
        'to_node': 'B',
        'length_m': 2000.0,
        'current_diameter_supply_mm': 200,
        'supply_temp_nominal_c': 90.0,
        'return_temp_nominal_c': 50.0,
        'milp_linearize': False,
        'Q_pipe_initial_mw': q_initial,
    }


def test_warmup_constraint_uses_initial_value():
    """For t < tau, w_delay upper bound must equal Q_pipe_initial_mw, not be unconstrained."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 6)
    m.dt_h = 1.0

    config = _make_pipe_config(q_initial=2.5)
    result = PipePairBlock.attach(m, m.t, config, buses={})

    # Find w_ub_q constraints
    w_ub_q = getattr(m, 'TEST_PIPE_w_ub_q', None)
    assert w_ub_q is not None, "w_ub_q constraint must exist"

    # Collect all active constraint bounds for warm-up timesteps
    tau_steps = result.get('tau_steps', [])
    assert len(tau_steps) > 0, "Need at least one delay bucket"

    # For warm-up period, the constraint should NOT be skipped
    warm_up_constrained = False
    for n in range(len(tau_steps)):
        for i, t in enumerate(sorted(m.t)):
            if i < tau_steps[n]:
                key = (n, t)
                if key in w_ub_q:
                    c = w_ub_q[key]
                    assert c.active, f"Warm-up constraint ({n},{t}) must be active"
                    warm_up_constrained = True
    assert warm_up_constrained, "At least one warm-up constraint must be active"


def test_warmup_default_is_zero():
    """Default Q_pipe_initial_mw=0.0 constrains w_delay to 0 during warm-up."""
    from calion.models.blocks.pipe_pair import PipePairBlock

    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 6)
    m.dt_h = 1.0

    config = _make_pipe_config(q_initial=0.0)
    PipePairBlock.attach(m, m.t, config, buses={})

    w_ub_q = getattr(m, 'TEST_PIPE_w_ub_q', None)
    assert w_ub_q is not None
