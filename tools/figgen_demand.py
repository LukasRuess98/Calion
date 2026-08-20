"""Normalised total heat demand (cleaned consumption) for the Memmingen network.
Sums the 27 consumer demand columns from the cleaned import workbook, normalises to peak,
and plots the annual profile. Caches the summed series so re-runs are fast.
Output: results/v2/figures/F_demand.{png,pdf}
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.paper.mpl_export import AE_DOUBLE_COLUMN_IN, apply_ae_style, save_figure_bundle
apply_ae_style(matplotlib)
matplotlib.rcParams.update({"font.family": "serif",
                            "font.serif": ["STIXGeneral", "STIX Two Text", "Times New Roman"],
                            "mathtext.fontset": "stix"})
BLUE_D, BLUE_M = "#08306B", "#2171B5"

cache = ROOT / "results" / "v2" / "analysis" / "total_demand.csv"
if cache.exists():
    tot = pd.read_csv(cache, parse_dates=["t"]).set_index("t")["demand_MW"]
else:
    import openpyxl
    xl = ROOT / "data" / "Import_Data_Memmingen_epronet_cleaned.xlsx"
    wb = openpyxl.load_workbook(xl, read_only=True, data_only=True)
    ws = wb["Data"]
    it = ws.iter_rows(values_only=True)
    header = list(next(it))
    di = header.index("Datum")
    dem_i = [i for i, h in enumerate(header) if isinstance(h, str) and h.endswith("_demand_MWth")]
    times, totals = [], []
    for r in it:
        if r[di] is None:
            continue
        times.append(r[di]); totals.append(sum((r[i] or 0.0) for i in dem_i))
    wb.close()
    tot = pd.Series(totals, index=pd.to_datetime(times), name="demand_MW")
    tot.index.name = "t"
    tot.to_csv(cache)
    print(f"cached {len(dem_i)} demand columns, {len(tot)} rows -> {cache.name}")

daily = tot.resample("D").mean().loc["2025"]   # the calendar year the model dispatches
norm = daily / daily.max()

fig, ax = plt.subplots(figsize=(AE_DOUBLE_COLUMN_IN, 2.5))
ax.fill_between(norm.index, 0, norm.values, color=BLUE_M, alpha=0.18, lw=0)
ax.plot(norm.index, norm.values, color=BLUE_D, lw=0.9)
ax.set_ylabel("Normalised total\nheat demand (--)")
ax.set_xlabel("2025")
ax.set_ylim(0, 1.02)
ax.margins(x=0.01)
peak_mw = daily.max()
ax.text(0.015, 0.93, f"peak daily mean $=$ {peak_mw:.1f} MW",
        transform=ax.transAxes, fontsize=6.6, va="top", color="#33475b")
fig.tight_layout()
save_figure_bundle(fig, ROOT / "results/v2/figures/F_demand", formats=("png", "pdf"), raster_dpi=600)
print("wrote F_demand; peak daily mean %.2f MW, annual mean %.2f MW" % (daily.max(), daily.mean()))
