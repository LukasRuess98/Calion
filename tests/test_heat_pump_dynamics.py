"""Tests for heat pump min uptime / min downtime constraints."""
import pytest

try:
    import pyomo.environ as pyo
    HAVE_PYOMO = True
except ImportError:
    HAVE_PYOMO = False

pytestmark = pytest.mark.skipif(not HAVE_PYOMO, reason="Pyomo not installed")


def _make_hp(min_uptime_h: float = 0, min_downtime_h: float = 0):
    from calion.models.blocks.heat_pump import HeatPumpBlock
    return HeatPumpBlock(
        name='HP_TEST',
        min_load=0.2,
        cop_series=[3.5],
        capacity_min_mw=0.0,
        capacity_max_mw=5.0,
        capacity_init_mw=5.0,
        investable=False,
        min_uptime_h=min_uptime_h,
        min_downtime_h=min_downtime_h,
    )


def test_no_dynamics_when_zero():
    """When min_uptime=0, min_downtime=0: no u/v variables added."""
    hp = _make_hp(0, 0)
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    hp.attach(m, m.t, cfg={}, buses={})
    assert not hasattr(m, 'HP_TEST_u'), "No startup variable expected"
    assert not hasattr(m, 'HP_TEST_v'), "No shutdown variable expected"


def test_startup_shutdown_variables_created():
    """When min_uptime > 0: u and v binary variables are created."""
    hp = _make_hp(min_uptime_h=2, min_downtime_h=1)
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 6)
    hp.attach(m, m.t, cfg={}, buses={})
    assert hasattr(m, 'HP_TEST_u'), "Startup variable u must exist"
    assert hasattr(m, 'HP_TEST_v'), "Shutdown variable v must exist"


def test_state_transition_constraint():
    """y[t] - y[t-1] == u[t] - v[t] for t > 1."""
    hp = _make_hp(min_uptime_h=2, min_downtime_h=1)
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 4)
    hp.attach(m, m.t, cfg={}, buses={})
    assert hasattr(m, 'HP_TEST_state_transition'), "State transition constraint must exist"


def test_min_uptime_constraint_exists():
    """min_uptime constraint must be added when min_uptime_h > 0."""
    hp = _make_hp(min_uptime_h=3, min_downtime_h=0)
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 6)
    hp.attach(m, m.t, cfg={}, buses={})
    assert hasattr(m, 'HP_TEST_min_uptime'), "Min uptime constraint must exist"


def test_min_downtime_constraint_exists():
    """min_downtime constraint must be added when min_downtime_h > 0."""
    hp = _make_hp(min_uptime_h=0, min_downtime_h=2)
    m = pyo.ConcreteModel()
    m.t = pyo.RangeSet(1, 6)
    hp.attach(m, m.t, cfg={}, buses={})
    assert hasattr(m, 'HP_TEST_min_downtime'), "Min downtime constraint must exist"
