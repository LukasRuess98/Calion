"""v12 B7: runs_v12.csv row from a finished v12 run (Teil E columns); skipped if output/v12 is absent."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "output" / "v12" / "SB-S0-HK0-PIN0"
TEIL_E = ["scenario_id", "network", "HK", "WP_MW", "TES_MWh", "TES_m3", "TES_site", "status", "UB_EUR", "LB_EUR",
          "width_EUR", "runtime_s", "R_min_MW", "R_absmax_MW", "R_sum_MWh", "residual_EUR", "HP_Qth_MWh",
          "HP_Qel_MWh", "HP_SCOP", "HP_full_load_h", "TES_cycles", "TES_direct_share", "TES_dT_K", "CHP_el_MWh",
          "CHP_th_MWh", "boiler_th_MWh", "dump_MWh", "grid_import_peak_MW"]


def test_row_has_teil_e_columns_and_consistent_interval():
    if not (RUN / "meta.json").exists():
        pytest.skip("v12 C0 SB run not available")
    from scripts.paper_2.v12.runs_log import row
    r = row(RUN)
    assert all(c in r for c in TEIL_E)
    assert r["LB_EUR"] <= r["UB_EUR"] and r["width_EUR"] == pytest.approx(r["UB_EUR"] - r["LB_EUR"])
    assert r["balance_status"] == "ok" and r["WP_MW"] == 0.0 and r["TES_site"] == "none"
    assert any(k.startswith("cost_") for k in r)
