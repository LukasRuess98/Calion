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
