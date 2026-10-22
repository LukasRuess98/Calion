"""AE2 (2026-10-22): bottom-up tank-connection cost [EUR/MW_th] for a chosen power, with range.

Positions and sources (all read from the primary documents, not from web summaries):
 (a) connection line  : DEA/Energinet Technology Data for Energy Transport v8 (Dec 2025), sheet
                        "3.1 DH transmission", note D: cost per trench metre of a pipe pair
                        P = 330 * C^-0.571 [EUR/MW/m], C = capacity in MW (this is per metre, correct
                        scope for a line; it includes trench/civil work, hence conservative for a short
                        in-plant connection). Length 50-100 m at the producer site.
 (b)+(c) pumps, valves/fittings, pressure holding, instrumentation & control:
                        KWW Technikkatalog Waermeplanung 2026 (v1.1, Excel), table 39 "Pumpstationen"
                        (source KEA-BW Technikkatalog BW v1.1, sheet 4.1), > 1 MW: 82 - 123 EUR/kW_th
                        installed, of which 25 % EQUIPMENT ("Anlagenkosten": pumps, fittings, measurement)
                        and 75 % installation (civil works, building, grid connection). A tank connection
                        on the producer site needs the equipment, not the network-station civil works ->
                        equipment share 20.5 - 30.8 EUR/kW_th.  The catalogue does NOT split pumps vs.
                        fittings vs. control, so no separate percentage surcharge can be sourced.
 NOT included: heat exchanger (the tank is connected directly, DEA Energy Storage ch. 141) -- if a
 hydraulic decoupling were needed it would be a separate, priced position.
 Reference anchors (not part of the bottom-up): 70 EUR/kW = DEA Heating Installations ch. 203 p. 44,
 a house-connection substation at 320 kW (UPPER anchor, not scaled to 110 MW); 280 kEUR/MW = DEA
 transmission pump + HX station incl. civil works (stress test, outside the scope).

usage: python scripts/paper_2/connection_cost_bottom_up.py [P_MW ...]
"""
import sys

LINE_LEN_M = (50.0, 100.0)
PUMP_STATION_EUR_PER_KW = (82.0, 123.0)       # KWW 2026 table 39, > 1 MW, installed
EQUIPMENT_SHARE = 0.25                         # same table: "davon Anlagenkosten"


def line_eur_per_mw(p_mw: float, length_m: float) -> float:
    return 330.0 * p_mw ** -0.571 * length_m


def bottom_up(p_mw: float) -> dict:
    a_lo, a_hi = (line_eur_per_mw(p_mw, L) for L in LINE_LEN_M)
    bc_lo, bc_hi = (c * 1000.0 * EQUIPMENT_SHARE for c in PUMP_STATION_EUR_PER_KW)
    return {
        "P_MW": p_mw,
        "line_eur_per_mw": (a_lo, a_hi),
        "pumps_fittings_control_eur_per_mw": (bc_lo, bc_hi),
        "total_eur_per_mw": (a_lo + bc_lo, a_hi + bc_hi),
        "total_eur_per_mw_mid": 0.5 * (a_lo + bc_lo + a_hi + bc_hi),
        "total_capex_meur": (p_mw * (a_lo + bc_lo) / 1e6, p_mw * (a_hi + bc_hi) / 1e6),
    }


if __name__ == "__main__":
    powers = [float(a) for a in sys.argv[1:]] or [10.0, 25.0, 51.8]
    for p in powers:
        r = bottom_up(p)
        print(f"P = {p:5.1f} MW  line {r['line_eur_per_mw'][0]:7,.0f}-{r['line_eur_per_mw'][1]:7,.0f}  "
              f"pumps/fittings/control {r['pumps_fittings_control_eur_per_mw'][0]:7,.0f}-"
              f"{r['pumps_fittings_control_eur_per_mw'][1]:7,.0f}  => {r['total_eur_per_mw'][0]:7,.0f}-"
              f"{r['total_eur_per_mw'][1]:7,.0f} EUR/MW (mid {r['total_eur_per_mw_mid']:,.0f}); "
              f"CAPEX {r['total_capex_meur'][0]:.2f}-{r['total_capex_meur'][1]:.2f} MEUR")
