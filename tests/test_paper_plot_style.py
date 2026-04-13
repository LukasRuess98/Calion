import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "paper"))


def test_ecm_dimensions():
    import ecm_style
    assert abs(ecm_style.SINGLE_COL_W - 3.54) < 0.01
    assert abs(ecm_style.DOUBLE_COL_W - 7.48) < 0.01


def test_ecm_font_sizes():
    import ecm_style
    assert ecm_style.FONT_TICK == 8
    assert ecm_style.FONT_AXIS_LABEL == 9
    assert ecm_style.FONT_TITLE == 10


def test_apply_ecm_style_sets_rcparams():
    import matplotlib as mpl
    import ecm_style
    ecm_style.apply_ecm_style()
    assert mpl.rcParams["xtick.labelsize"] == ecm_style.FONT_TICK
    assert mpl.rcParams["font.size"] == ecm_style.FONT_AXIS_LABEL


def test_color_constants_defined():
    import ecm_style
    for attr in ("C_BOILER", "C_HP", "C_TES_DIS", "C_TES_CHG",
                 "C_DEMAND", "C_DUMP", "C_L1", "C_L2", "C_L3"):
        val = getattr(ecm_style, attr)
        assert val.startswith("#"), f"{attr} should be a hex color string"


# ── Smoke-test helpers ────────────────────────────────────────────────────────
import csv
import json
import importlib
import numpy as np
import matplotlib
matplotlib.use("Agg")


def _write_dispatch_csv(path, n=168):
    """Minimal pf_timeseries.csv for smoke testing."""
    rows = [
        {
            "timestamp": i,
            "waermebedarf_MWth":    50 + 10 * np.sin(i / 24 * 3.14),
            "BOILER_MAIN_Q_th_MW":  30.0,
            "hp_main_Q_th_MW":      15.0,
            "TES_discharge_MW":      5.0,
            "TES_charge_MW":         3.0,
            "Q_dump_MWth":           0.0,
        }
        for i in range(n)
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def test_dispatch_comparison_smoke(tmp_path):
    import plot_dispatch_comparison as pdc
    importlib.reload(pdc)

    for tag in ("l1", "l2", "l3"):
        _write_dispatch_csv(tmp_path / f"{tag}.csv")

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.csv"),
                "--l2", str(tmp_path / "l2.csv"),
                "--l3", str(tmp_path / "l3.csv"),
                "--outdir", str(tmp_path)]
    pdc.main()

    assert (tmp_path / "fig2_dispatch_comparison.pdf").exists()
    assert (tmp_path / "fig2_dispatch_comparison.png").exists()


def _write_costs_json(path, grid=9_400_000, co2=4_200_000, total=14_770_000,
                      demand_mwh=50_000.0):
    data = {"PF": {
        "Grid_energy_cost_EUR":   grid,
        "Fuel_cost_EUR":          0.0,
        "CO2_cost_EUR":           co2,
        "Demand_charge_cost_EUR": 0.0,
        "Dump_cost_EUR":          0.0,
        "Capex_cost_EUR":         0.0,
        "OBJ_value_EUR":          total,
        "total_demand_MWh":       demand_mwh,
    }}
    Path(path).write_text(json.dumps(data))


def test_cost_comparison_smoke(tmp_path):
    import plot_cost_comparison as pcc
    importlib.reload(pcc)

    _write_costs_json(tmp_path / "l1.json", total=14_770_000)
    _write_costs_json(tmp_path / "l2.json", total=14_810_000)
    _write_costs_json(tmp_path / "l3.json", total=14_850_000)

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.json"),
                "--l2", str(tmp_path / "l2.json"),
                "--l3", str(tmp_path / "l3.json"),
                "--outdir", str(tmp_path)]
    pcc.main()

    assert (tmp_path / "fig3_cost_comparison.pdf").exists()
    assert (tmp_path / "fig3_cost_comparison.png").exists()


def _write_network_summary(path, n_pipes=5, base_loss=300.0):
    pipes = {
        f"pipe_{i:02d}": {"total_heat_loss_mwh": base_loss - i * (base_loss / (n_pipes + 1)),
                           "length_m": 500 + i * 100}
        for i in range(n_pipes)
    }
    Path(path).write_text(json.dumps({"pipes": pipes}))


def test_pipe_losses_smoke(tmp_path):
    import plot_pipe_losses as ppl
    importlib.reload(ppl)

    _write_network_summary(tmp_path / "l2_summary.json", n_pipes=4,  base_loss=400)
    _write_network_summary(tmp_path / "l3_summary.json", n_pipes=15, base_loss=200)
    _write_dispatch_csv(tmp_path / "l1_demand.csv", n=8760)

    sys.argv = ["prog",
                "--l2-summary", str(tmp_path / "l2_summary.json"),
                "--l3-summary", str(tmp_path / "l3_summary.json"),
                "--l1-demand",  str(tmp_path / "l1_demand.csv"),
                "--outdir", str(tmp_path)]
    ppl.main()

    assert (tmp_path / "fig4_pipe_losses.pdf").exists()
    assert (tmp_path / "fig4_pipe_losses.png").exists()


def _write_soc_csv(path, n=8760):
    rows = [
        {
            "timestamp":          i,
            "TES_SOC_MWh":        230 + 20 * np.sin(i / 24 * 3.14),
            "TES_charge_MW":      max(0.0, 5 * np.sin(i / 12 * 3.14)),
            "TES_discharge_MW":   max(0.0, -5 * np.sin(i / 12 * 3.14)),
        }
        for i in range(n)
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def test_storage_comparison_smoke(tmp_path):
    import plot_storage_comparison as psc
    importlib.reload(psc)

    for tag in ("l1", "l2", "l3"):
        _write_soc_csv(tmp_path / f"{tag}.csv")

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.csv"),
                "--l2", str(tmp_path / "l2.csv"),
                "--l3", str(tmp_path / "l3.csv"),
                "--outdir", str(tmp_path)]
    psc.main()

    assert (tmp_path / "fig8_storage_soc.pdf").exists()
    assert (tmp_path / "fig8_storage_soc.png").exists()


def test_co2_comparison_smoke(tmp_path):
    for name, gas_t, grid_t, total in [
        ("l1.json", 820.0, 380.0, 14_770_000),
        ("l2.json", 825.0, 382.0, 14_810_000),
        ("l3.json", 830.0, 385.0, 14_850_000),
    ]:
        data = {"PF": {
            "CO2_gas_tonnes":  gas_t,
            "CO2_grid_tonnes": grid_t,
            "OBJ_value_EUR":   total,
            "total_demand_MWh": 50_000.0,
        }}
        (tmp_path / name).write_text(json.dumps(data))

    import plot_co2_comparison as pco2
    importlib.reload(pco2)

    sys.argv = ["prog",
                "--l1", str(tmp_path / "l1.json"),
                "--l2", str(tmp_path / "l2.json"),
                "--l3", str(tmp_path / "l3.json"),
                "--outdir", str(tmp_path)]
    pco2.main()

    assert (tmp_path / "figX_co2_comparison.pdf").exists()
    assert (tmp_path / "figX_co2_comparison.png").exists()
