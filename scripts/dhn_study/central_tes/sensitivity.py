"""Sensitivity sets (spec 7.4 and author additions); each set writes results/central_tes/sensitivities/<set>/.

Priority A: A1 TES energy × power (E + H), A2 link DN (E + H), A3 temperature handling (class model vs single-state
strategies, E + H), A4 partner-B premium (E), A5 partner-B electricity-cost regime (E), A6 HP→EB cascade (E).
Priority B (approved 2026-10-09): B2 price year, B4 V06 limit; B1 and B3 are part of PR.
Author additions: PR prosumer drivers (HP size, source temperature, EB size, HP grid fee, B1 availability, B3 η_C),
PS partner-A calendar shift, PG gas price downwards, BL partner-B electricity cost over the literature range, AT atmospheric tank, P prices / waste-heat fee / model variants, X south expansion,
X4 expansion with KWK ≤ 4 bar, XR south-trunk reinforcement. A2x: exploratory, not part of the reported results.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config as C
from .run import Study, _dump

REF_VARIANT = ["A"]


def cases(cfg: dict, sid: str) -> list[tuple[str, dict, list[str], bool]]:
    """(case name, overrides, scenarios, mode_h)."""
    tes = cfg["tes"]
    if sid == "A1":
        out = [("V0", {"tes.enabled": False}, ["F111"], True)]
        for v in (2500, 5000, 10000, 20000):
            for q in (10, 20, 40, 80):
                if (v, q) in ((2500, 10), (20000, 10)):
                    continue
                out.append((f"V{v}_Q{q}", {"tes.volume_m3": v, "tes.Q_ch_max_MW": q, "tes.Q_dis_max_MW": q}, ["F111"], True))
        return out
    if sid == "A2":
        return [(f"DN{d}", {"link.DN": d}, ["F110", "F111"], True) for d in (300, 350, 400, 450, 500)]
    if sid == "A3":       # temperature strategy (H6): reference = temperature classes (factorial); spec single-state model
        return [(f"single_{st}", {"tes.model": "single", "tes.T_set_strategy": st}, ["F001", "F111"], True)
                for st in ("fixed", "monthly", "daily")]
    if sid == "A4":
        out = [("ref_F101", {}, ["F101"], False)]
        out += [(f"pi{p}", {"electrode_boiler.premium_eur_MWh": p}, ["F111", "F011", "F010"], False) for p in (0, 10, 20, 30, 40, 60)]
        return out
    if sid == "A5":
        out = [("ref_F101", {}, ["F101"], False)]
        for c in ("low", "high"):
            for d in ("none", "full"):
                out.append((f"{c}_{d}", {"electrode_boiler.c_el_var_case": c, "electrode_boiler.demand_charge": d},
                            ["F111", "F110", "F010"], False))
        return out
    if sid == "A6":       # cascade (H6) with the class model (the strategy cross of the spec applies to the single model)
        out = [("casc_off", {"heat_pump.cascade.enabled": False}, ["F111"], False)]
        for tm in (70, 80, 90, 100):
            out.append((f"Tmid{tm}", {"heat_pump.cascade.T_mid_C": tm}, ["F111"], False))
        return out
    if sid == "X":        # network expansion in the south: +10/20/30 % demand, new peak boiler capacity is a decision
        out = []
        for L in (10, 20, 30):
            base = {"inputs.expansion": {"share": L / 100, "region": "south"}, "new_boiler.enabled": True}
            out.append((f"L{L}", base, ["F000", "F110", "F111"], True))
            if L <= 20:
                out.append((f"L{L}_tes_south", {**base, "tes.node": "station:V06"}, ["F001", "F111"], True))
        return out
    if sid == "X4":       # expansion with the KWK 4.0 bar experience value as hard limit (operator practice)
        out = []
        for L in (0, 20):
            base = {"inputs.expansion": {"share": L / 100, "region": "south"}, "new_boiler.enabled": True,
                    "hydraulics.kwk_experience_value_hard": True}
            out.append((f"L{L}_kwk4", base, ["F000", "F110", "F111"], True))

        return out
    if sid == "PR":       # prosumer sensitivities: HP size, source temperature, EB size, B1 availability, B3 Carnot fraction
        fa, fb = ["F100", "F101", "F110", "F111"], ["F010", "F011", "F110", "F111"]
        out = [(f"hp{q:g}", {"heat_pump.Q_max_MW": q}, fa, False) for q in (2.5, 10.0, 15.0)]
        out += [(f"Tsrc+{d}", {"inputs.partner_a.T_source_offset_K": float(d)}, fa, False) for d in (10, 20)]
        out += [(f"eb{p:g}", {"electrode_boiler.P_max_MW": p}, fb, False) for p in (5.0, 20.0)]
        out += [(f"B1_scale{sc:g}", {"inputs.partner_a.scale": sc}, fa, False) for sc in (0.5, 0.75, 1.25)]
        out += [(f"B3_etaC{e:g}", {"heat_pump.eta_carnot": e}, fa, False) for e in (0.4, 0.6)]
        out += [(f"hp_cel{c:g}", {"heat_pump.c_el_var_eur_MWh": c}, fa, False) for c in (55.0, 76.0)]   # grid fee range (lit.)
        return out
    if sid == "AT":       # atmospheric tank alternative (≤ 95 °C classes, no pressure vessel) — economics comparison
        return [(f"atm_V{v}_Q{q}", {"tes.volume_m3": v, "tes.Q_ch_max_MW": q, "tes.Q_dis_max_MW": q, "tes.classes_C": [90.0, 95.0]},
                 ["F111"], False) for v, q in ((10000, 40), (20000, 40), (50000, 80))]
    if sid == "PS":       # partner-A data mapping: 2023 profile shifted by ± 1 week against the 2025 calendar
        return [(f"shift{d:+d}d", {"inputs.partner_a.calendar_shift_days": 728 + d}, ["F100", "F101", "F111"], False)
                for d in (-7, 7)]
    if sid == "B2":       # price year (2025 demand and temperatures; weather–price correlation lost)
        return [(f"prices{y}", {"inputs.prices.year": y}, ["F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111"], False)
                for y in (2023, 2024)]
    if sid == "PG":       # gas price downwards (spot level 2025 ≈ 37 EUR/MWh; reference 48), all eight scenarios
        return [(f"gas{g:g}", {"fuels.gas.price": g}, ["F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111"], False)
                for g in (37.0, 42.0)]
    if sid == "BL":       # partner-B electricity cost over the literature range: levy floor 11.4 + network charge
        # 23.6 / 42.8 / 61.8 EUR/MWh (BNetzA monitoring 2025, industrial 24 GWh case) → 35 / 54 / 73; no demand charge
        return [(f"cel{c:g}", {"electrode_boiler.c_el_var_eur_MWh.high": c}, ["F010", "F011", "F110", "F111"], False)
                for c in (35.0, 54.0, 73.0)]
    if sid == "B4":       # hydraulic limit at the south end (V06) ± 0.2 bar
        return [(f"V06_{v:g}", {"hydraulics.control.setpoints": {"V06": v, "Mitte": 1.0}}, ["F000", "F111"], True) for v in (1.0, 1.4)]
    if sid == "XR":       # south expansion with reinforcement of the south trunk (parallel pipe) instead of / with the boiler
        out = []
        for L in (20, 30):
            base = {"inputs.expansion": {"share": L / 100, "region": "south"}, "new_boiler.enabled": True}
            out.append((f"L{L}_R1", {**base, "hydraulics.reinforce": {"edges": ["L4b"], "K_factor": 0.25}}, ["F111"], True))
            out.append((f"L{L}_R2", {**base, "hydraulics.reinforce": {"edges": ["L4a", "L4b", "L4c"], "K_factor": 0.25}}, ["F111"], True))
        return out
    if sid == "P":        # price and cost assumptions (existing configuration values; waste-heat fee)
        return [("gas58.6_co2_100", {"fuels.gas.price": 58.6, "co2_price_eur_t": 100.0}, ["F000", "F001", "F110", "F111"], False),
                *[(f"piA{p}", {"heat_pump.pi_source_eur_MWh": p}, ["F100", "F101", "F111"], False) for p in (0, 10, 20)],
                ("tes_single_fixed", {"tes.model": "single", "tes.T_set_strategy": "fixed"}, ["F001", "F101", "F011", "F111"], False),
                ("eb_kwk_9.9", {"plants.existing_eb_at_kwk.enabled": True}, ["F000", "F111"], False)]
    if sid == "A2x":      # exploratory: where does the link bind? daily strategy (network charging) and 80 MW TES power
        return [(f"DN{d}_daily_Q80", {"link.DN": d, "tes.T_set_strategy": "daily", "tes.Q_ch_max_MW": 80, "tes.Q_dis_max_MW": 80},
                 ["F111"], True) for d in (300, 400, 500)]
    raise ValueError(sid)


def _load_done(d: Path, code: str, mode_h: bool) -> dict | None:
    """Resume: results of a finished scenario (E, and H on calibration A if requested)."""
    pe, ph = d / f"{code}-E" / "annual_metrics.json", d / f"{code}-H" / "A" / "annual_metrics.json"
    if not pe.exists() or (mode_h and not ph.exists()):
        return None
    r = {"E": json.loads(pe.read_text())}
    if mode_h:
        r["H"] = {"A": json.loads(ph.read_text())}
    return r


def run(cfg: dict, sid: str, out: Path, only: list[str] | None = None, no_h: bool = False):
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    for name, ov, scen, mode_h in cases(cfg, sid):
        if only and name not in only:
            continue
        mode_h = mode_h and not no_h
        c = C.merge(cfg, ov)
        st = Study(c, out / name, REF_VARIANT, out / "run.log")
        st.log(f"{sid}/{name}: {ov}")
        for code in scen:
            r = _load_done(out / name, code, mode_h)
            if r is None:
                r = st.run(code, mode_h)
                import gc
                gc.collect()
            e = r["E"]["metrics"]
            row = {"case": name, "scenario": code, **{k: json.dumps(v) for k, v in ov.items()}, "C_E": e["cost_total_EUR"],
                   "viol_E": r["E"]["hydraulics"]["A"]["violating_hours"],
                   "attr_E": r["E"]["hydraulics"]["A"]["attributable_to_central_h"],
                   "U_A": e["partner_A"]["U"], "B_heat_GWh": e["partner_B"]["heat_GWh"], "TES_dis_GWh": e["TES"]["discharge_GWh"],
                   "TES_EFC": e["TES"]["equivalent_full_cycles"], "tau_h": e["dimensionless"]["tau_h"],
                   "kappa_link": e["dimensionless"]["kappa_link"], "psi_central": e["dimensionless"]["psi_central"],
                   "cascade_share": e["partner_A"]["cascade_share"], "A_chain_eff": e["partner_A"]["chain_efficiency"],
                   "B_price_weighted": e["partner_B"]["price_weighted_EUR_MWh"],
                   "masked_dis_h": e["TES"]["hours_discharge_masked"], "masked_ch_grid_h": e["TES"]["hours_charge_from_grid_masked"]}
            row |= {"C_new_MW_E": e.get("new_boiler", {}).get("capacity_MW", 0.0),
                    "NEW_heat_GWh_E": e.get("new_boiler", {}).get("heat_GWh", 0.0),
                    "dpKWK_p95_E": r["E"]["hydraulics"]["A"]["dp_KWK_required"]["p95"],
                    "soft_KWK_h_E": r["E"]["hydraulics"]["A"]["soft_hours"]["KWK"],
                    "TES_ext_GWh": e["TES"].get("external_net_GWh", 0.0)}
            if mode_h:
                h = r["H"]["A"]
                row |= {"C_new_MW_H": h["metrics"].get("new_boiler", {}).get("capacity_MW", 0.0),
                        "NEW_heat_GWh_H": h["metrics"].get("new_boiler", {}).get("heat_GWh", 0.0),
                        "dpKWK_p95_H": h["hydraulics"]["dp_KWK_required"]["p95"]}
                row |= {"C_H": h["metrics"]["cost_total_EUR"], "dC_hyd": h["dC_hyd_EUR"], "conv_H": h["info"]["converged"],
                        "iter_H": h["info"]["iterations"]}
            summary.append(row)
            pd.DataFrame(summary).to_csv(out / "summary.csv", index=False)
    _dump({"sid": sid, "cases": [c[0] for c in cases(cfg, sid)]}, out / "cases.json")
    return pd.DataFrame(summary)
