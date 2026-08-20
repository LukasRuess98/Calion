# Data requests to acquire (Paper 1 revision)

The current dataset `data/Import_Data_Memmingen_epronet.xlsx` (43,288 rows × 417 cols)
is confirmed to be **entirely substation/delivery-side**: 27 zones × 15 channels
(demand, flow rate, flow/return temp, temp diff, power, total energy, total volume,
+ per-channel quality flags) plus datetime, price, grid CO2, and weather
(outdoor_temp, humidity, solar, wind). `Waermebedarf_MWth` = Σ V_x_demand = total
**delivered** heat. There is **no plant-side heat-generation channel**.

## Request 1 — plant heat generation, for T0P1c (measurement-calibrated loss)

**What:** the annual heat **generated / fed into the network** at the Memmingen plant
(Heizwerk / Energiezentrale) for 2025 — i.e. the plant-side heat-meter total
(Wärmeeinspeisung ins Netz).

- **Minimum useful:** one number — total MWh generated in 2025.
  Then measured network loss = generation − Σ V_x delivered (≈ 9,776 MWh), and
  `T0P1c` constant adder = that loss / 8760.
- **Better:** the hourly (or 15-min) plant heat-output time series, enabling a
  measurement-based *profile* (not just a constant).

**Why it matters (not just completeness):** `T0P1a/b` are oracle-calibrated to the
*model's* loss (1,329.8 MWh ≈ 13.6% of delivered). Reviewer 2.4 questioned the loss
calibration (the ×1.33 / ×4.7 multipliers). `T0P1c` is the independent reality check:
if measured loss ≈ 1,330 MWh, a/b/c agree and the decomposition stands as-is; if it
differs materially, `loss_main` (currently 96% of the gap) shifts and must be restated.
So this figure both completes the R2.2 control and directly supports the R2.4 response.

**Status:** T0P1a and T0P1b built, run, and decomposed. T0P1c blocked on this figure.

## (Nice-to-have, not blocking) Request 2 — any plant fuel/CO2 metering for 2025

If available, measured plant fuel input by carrier would let the validated bias
numbers rest on measured generation cost too. Not required for the current results.
