# Input data schema

The model reads one data folder (`paths.data_dir` in the configuration; default of the study: the non-public data set
`data/dhn_a`, here: `data/synthetic`). All hourly files use **naive local time** (Europe/Berlin) with the conventions of the
measurement export: the missing spring DST hour does not exist (2025-03-30 02:00), the October double hour is merged into
one value, i.e. 8 759 hours for 2025. The study year is 2025 (`meta.year`).

## Files in the data folder

| file | content | resolution / units |
|---|---|---|
| `measurements_2025_hourly.parquet` | measured operating data of the network (index `time_local`, 169 columns, see below; only 35 are used) | 1 h; see unit conventions |
| `ambient_temperature_hourly.parquet` | column `T_ambient` [°C], index naive local time; must cover the study period | 1 h |
| `ambient_temperature_daily.csv` | columns `date`, `T_ambient_daily_mean` [°C] | 1 d |
| `plants.yaml` | pump data of the existing plants: `m_max_t_h`, `pumps.installed` (e.g. `"2x550 t/h"` or `"3x300 m3/h"`), `pumps.head_m`, `dp_internal_bar`, `shutdown_bar.{p_return_below, p_supply_above}` for `gas_CHP`, `waste_incineration`, `gas_turbine`, `biomass_CHP`, `boiler_plant_1` | – |
| `sectors.csv` | sub-areas with connected load: `sub_area, section, region, network_volume_m3, customers, connected_MW, note`. `sub_area` must start with a key of `netzmodell.SEKTOR_KNOTEN` (assigns the load node); `section` starting with `W` = secondary network (excluded) | MW |
| `consumers.csv` | stations `id, region, note` (V01–V24) | – |

Outside the data folder (paths in the configuration):

| key | file | columns |
|---|---|---|
| `paths.prices_dir` | `raw_<year>.json` | `unix_seconds` (UTC, hourly or 15 min), `price` [EUR/MWh] — format of the energy-charts.info API (DE-LU day-ahead); 15-min values are averaged to hours |
| `paths.partner_a_csv` | partner-A waste heat, one year (mapped to the study year with `inputs.partner_a.calendar_shift_days`) | `time` (naive local, hourly), `Q_avail_MW` (available waste heat), `T_warm_C` (source temperature of the merged stream), `T_intake_C` |
| `paths.grid_co2_csv` | grid emission factor (secondary metric only) | `time`, `ef_grid_t_MWh` [t/MWh] |

Without `partner_a_csv` (and without the local configuration of the study), partner A has zero availability.

## Measurement columns

Naming `<object>_<quantity>`. Objects: `V01`…`V24` (stations), `gas_CHP` (main plant, pressure holder; paper: GCHP),
`waste_incineration` (WI), `gas_turbine` (GT), `biomass_CHP` (BCHP), `boiler_plant_1` (GB), `boiler_plant_2` (west
transfer: `_hx_` heat exchanger, `_secondary_` secondary network), `pump_station_1`, `pump_station_2` (PS1, PS2).
Quantities: `p_supply`, `p_return` [bar g], `dp` [bar], `T_supply`, `T_return` [°C], `flow` [t/h] (biomass CHP: m³/h in
the supply line), `heat` [MW]; `gas_CHP_flow_line_1..4` signed trunk flows [t/h], `gas_CHP_flow_total_out` their positive sum.

**Columns used by the model (35):**

| use | columns |
|---|---|
| demand = Σ feed-in, today's dispatch | `gas_CHP_heat`, `waste_incineration_heat`, `biomass_CHP_heat`, `boiler_plant_1_flow` + `_T_supply` + `_T_return`, `gas_turbine_flow` + `_T_supply` + `_T_return` + `_p_supply` + `_p_return` (GT heat = flow·Δh, gaps imputed from Δp and ΔT) |
| network temperatures | `gas_CHP_T_supply`, `gas_CHP_T_return` |
| west transfer | `boiler_plant_2_hx_heat`, `boiler_plant_2_hx_flow`, `boiler_plant_2_secondary_heat` |
| hydraulic anchor (measured Δp, flows) | `gas_CHP_p_supply`, `gas_CHP_p_return`, `gas_CHP_flow_total_out`, `waste_incineration_p_supply`, `waste_incineration_p_return`, `waste_incineration_T_supply`, `waste_incineration_T_return`, `gas_turbine_dp`, `biomass_CHP_dp`, `biomass_CHP_flow`, `biomass_CHP_T_supply`, `biomass_CHP_p_return`, `boiler_plant_1_dp`, `boiler_plant_1_p_return` |
| large customer at site S | `V22_flow` |
| pump stations | `pump_station_1_dp_supply_after_pump`, `pump_station_1_dp_supply_before_pump`, `pump_station_2_dp_supply_after_pump`, `pump_station_2_dp_supply_before_pump` |

The remaining 134 columns are part of the export schema (and of the synthetic example) but not read by the model; they
may be missing (NaN). The full list is `synthetic_data.SCHEMA_COLUMNS`.

## Equivalent network

`scripts/dhn_study/netzmodell.py`: nodes (`KNOTEN`), edges (`KANTEN`: id, from, to, DN, length), load nodes of the
sub-areas (`SEKTOR_KNOTEN`), station → node (`STATIONEN`), load groups (`LASTGRUPPEN`), pump stations (`PUMPEN`).
In this publication DN and length are placeholders; the calculations use the calibrated resistances in
`scripts/dhn_study/kalibrierung/<variant>/kalibrierung_kanten.csv` (`K [bar/(kg/s)²]` per edge, supply + return).
For an own network, enter its topology and geometry and calibrate with `netzmodell.kalibriere` (needs measured
pressures and flows) or set K from the pipe data (`netzmodell.k_prior`).
