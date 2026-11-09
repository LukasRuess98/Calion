"""v12 B9: a decomposition block uses the SAME measured SB temperatures as the full year (sliced by timestamp),
not the heating-curve fallback that a length mismatch used to trigger."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import numpy as np

from scripts.paper_2 import scenario_runner as sr


def test_full_year_unchanged_and_month_sliced():
    vl_y, rl_y = sr._load_measured_sb_temperatures()
    assert len(vl_y) == 8760
    t0 = datetime(2025, 3, 1)
    tab = SimpleNamespace(index=[t0 + timedelta(hours=h) for h in range(31 * 24)])
    vl_m, rl_m = sr._load_measured_sb_temperatures(tab)
    i0 = (t0 - datetime(2025, 1, 1)).days * 24
    assert len(vl_m) == 744
    assert np.array_equal(vl_m, vl_y[i0:i0 + 744]) and np.array_equal(rl_m, rl_y[i0:i0 + 744])
