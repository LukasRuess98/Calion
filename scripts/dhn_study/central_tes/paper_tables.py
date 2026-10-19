"""Result tables for the paper (markdown), generated from the result files so that no number is typed by hand.

    python -m scripts.dhn_study.central_tes.paper_tables
Output: reports/central_tes/paper_tables.md (anonymised; values only).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config as C
from .metrics import annuity_factor

CODES = ["F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111"]
NAMES = {"F000": "reference", "F001": "TES", "F100": "A", "F010": "B", "F110": "A + B", "F101": "A + TES",
         "F011": "B + TES", "F111": "A + B + TES"}


def _j(p: Path) -> dict:
    return json.loads(p.read_text())


def k(x: float, d: int = 1) -> str:
    return f"{x / 1e3:,.{d}f}".replace(",", " ")


def n(x: float, d: int = 0) -> str:
    return f"{x:,.{d}f}".replace(",", " ")


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def t_inputs(cfg: dict) -> pd.DataFrame:
    p, hp, eb, tes, ec, nb = cfg["plants"], cfg["heat_pump"], cfg["electrode_boiler"], cfg["tes"], cfg["economics"], cfg["new_boiler"]
    from . import inputs
    x = inputs.build(cfg)
    qa = x["Q_A_avail"]
    tsrc = float((x["T_source"] * qa).sum() / qa.sum())
    rows = [
        ("Network", "demand (feed-in incl. losses) / peak", f"{x['D'].sum() / 1e3:.0f} GWh/a / {x['D'].max():.0f} MW (2025, measured)", "measurement"),
        ("Network", "supply temperature", f"measured 2025 (mean {x['T_VL'].mean():.1f}, P95 {x['T_VL'].quantile(0.95):.0f} °C)", "measurement"),
        ("Plants", "KWK / MVA / GT / Bio-KWK / HW1 capacity", " / ".join(n(p[g]["cap_MW"], 1) for g in ("KWK", "MVA", "GT", "BIO", "HW1")) + " MW", "operator plan A"),
        ("Prices", "gas / CO2 / biomass / MVA heat", f"{cfg['fuels']['gas']['price']} EUR/MWh / {cfg['co2_price_eur_t']} EUR/t / "
         f"{cfg['fuels']['biomass']['price']} / {cfg['fuels']['waste']['price']} EUR/MWh", "EEX 2025 means (gas, EUA); assumption"),
        ("Prices", "electricity", f"DE-LU day-ahead 2025 (hourly; mean {x['price'].mean():.1f} EUR/MWh, {int((x['price'] < 0).sum())} h < 0)", "SMARD / energy-charts"),
        ("Partner A", "waste heat (4 merged water streams)", (f"{qa.sum() / 1e3:.1f} GWh/a; source temperature (flow-weighted mix of the streams) {x['T_source'].mean():.1f} °C "
                                                         f"time mean, P95 {x['T_source'].quantile(0.95):.1f} °C (heat-weighted {tsrc:.1f} °C)"), "measurement 2023, mapped to 2025"),
        ("Partner A", "HP capacity / Carnot fraction / ΔT_app / COP_max", f"{hp['Q_max_MW']} MW / {hp['eta_carnot']} / {hp['dT_app_K']} K / {hp['cop_max']}", "assumption, literature"),
        ("Partner A", "HP grid fee + levies / waste-heat fee", f"{hp['c_el_var_eur_MWh']} / {hp['pi_source_eur_MWh']} EUR/MWh", "assumption (fee: sensitivity 0–20)"),
        ("Partner B", "EB power / efficiency / premium", f"{eb['P_max_MW']} MW / {eb['eta']} / {eb['premium_eur_MWh']} EUR/MWh", "author decision; A4 0–60"),
        ("Partner B", "variable electricity cost low / high (ref.)", f"{eb['c_el_var_eur_MWh']['low']} / {eb['c_el_var_eur_MWh']['high']} EUR/MWh", "levy floor + BNetzA network charge: lit. 35–73 (BL); A5"),
        ("TES", "volume / power / temperatures", f"{n(tes['volume_m3'])} m³ / {tes['Q_dis_max_MW']} MW / classes {int(tes['classes_C'][0])}–{int(tes['classes_C'][-1])} °C, T_low {tes['T_low_C']} °C", "literature size class; A1"),
        ("TES", "standing loss", f"{tes['loss_per_h'] * 100:.2f} %/h", "existing configuration"),
        ("Link", "DN / velocity limit", f"DN {cfg['link']['DN']} / {cfg['link']['v_max_m_s']} m/s", "operator valve table; A2"),
        ("Economics", "interest / lifetimes TES, HP, link", f"{ec['discount_rate'] * 100:.0f} % / {ec['lifetime_tes_a']}, {hp['lifetime_a']}, {ec['lifetime_link_a']} a", "assumption"),
        ("Economics", "TES specific cost low / ref / high", " / ".join(n(ec['tes_capex_eur_per_m3'][x]) for x in ("low", "ref", "high")) + " EUR/m³ + 0.1 M EUR", "DEA, AEE INTEC; assumption"),
        ("Economics", "HP / new peak boiler", f"{hp['capex_eur_per_MW'] / 1e6:.2f} / {nb['capex_eur_per_MW'] / 1e6:.2f} M EUR/MW", "DEA technology data (HP); assumption in the DEA range (boiler)"),
        ("Hydraulics", "control and limits", "KWK pressure holder; V06 ≥ 1.2 bar, city-centre stations ≥ 1.0 bar; pump curves; PN25; KWK 4 bar (soft / X4 hard)", "operator data, 2025 analysis"),
    ]
    return pd.DataFrame(rows, columns=["block", "parameter", "value", "source / status"])


def t_factorial(r: Path) -> pd.DataFrame:
    f = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
    c0 = f.at["F000", "C_E"]
    rows = []
    for c in CODES:
        rows.append({"scenario": f"{c} ({NAMES[c]})", "C_E [M EUR/a]": f"{f.at[c, 'C_E'] / 1e6:.3f}",
                     "v_E [k EUR/a]": "–" if c == "F000" else k(c0 - f.at[c, "C_E"]),
                     "violating h A / C / B": f"{f.at[c, 'viol_E_A']} / {f.at[c, 'viol_E_C']} / {f.at[c, 'viol_E_B']}",
                     "attributable h (A)": f.at[c, "attr_E_A"],
                     "ΔC_hyd A / C / B [EUR/a]": " / ".join("–" if pd.isna(f.at[c, f"dC_hyd_{v}"]) else f"{f.at[c, f'dC_hyd_{v}']:.0f}"
                                                            for v in "ACB")})
    return pd.DataFrame(rows)


def t_shapley(r: Path) -> pd.DataFrame:
    sh = _j(r / "scenario_runs" / "shapley.json")
    rows = []
    for key, lab in (("E", "Mode E"), ("H_A", "Mode H (A)")):
        s = sh[key]
        rows.append({"mode": lab, "φ TES": k(s["phi"]["TES"]), "φ A": k(s["phi"]["A"]), "φ B": k(s["phi"]["B"]),
                     "v(F111)": k(s["v_full"]), "TES interaction": k(s["tes_interaction"]),
                     "V_TES alone / +A / +B / +A+B": " / ".join(k(s["storage_value"][x]) for x in ("F001-F000", "F101-F100", "F011-F010", "F111-F110"))})
    return pd.DataFrame(rows)


def t_foresight(r: Path) -> pd.DataFrame:
    f = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
    rh = r / "rolling_horizon"
    c = {x: _j(rh / f"{x}" / "annual_metrics.json")["cost_total_EUR"] for x in
         ("F111-E_schedule_known_day_ahead", "F111-E_persistence", "F111-H_schedule_known_day_ahead", "F110-E_schedule_known_day_ahead",
          "F001-E_schedule_known_day_ahead", "F000-E_schedule_known_day_ahead")}
    pf_b, pf_h = f.at["F000", "C_E"] - f.at["F111", "C_E"], f.at["F000", "C_H_A"] - f.at["F111", "C_H_A"]
    pf_t = f.at["F110", "C_E"] - f.at["F111", "C_E"]
    pf_a = f.at["F000", "C_E"] - f.at["F001", "C_E"]
    rows = [
        ("A + B + TES vs. F000, Mode E, A schedule known", pf_b, c["F000-E_schedule_known_day_ahead"] - c["F111-E_schedule_known_day_ahead"]),
        ("A + B + TES vs. F000, Mode E, persistence", pf_b, c["F000-E_schedule_known_day_ahead"] - c["F111-E_persistence"]),
        ("A + B + TES vs. F000, Mode H (PF cuts), A schedule known", pf_h, f.at["F000", "C_H_A"] - c["F111-H_schedule_known_day_ahead"]),
        ("TES alone (F000 − F001), Mode E", pf_a, c["F000-E_schedule_known_day_ahead"] - c["F001-E_schedule_known_day_ahead"]),
        ("TES with A + B (F110 − F111), Mode E", pf_t, c["F110-E_schedule_known_day_ahead"] - c["F111-E_schedule_known_day_ahead"]),
    ]
    return pd.DataFrame([{"value": a, "PF [k EUR/a]": k(p), "RH [k EUR/a]": k(q), "RH / PF": f"{100 * q / p:.1f} %"} for a, p, q in rows])


FORESIGHT_LABELS = {
    "ref": "reference: 72 h window, 24 h commitment, demand noise σ 5 %, known prices + repeated last known day",
    "ref_w120": "reference, window 120 h", "ref_w168": "reference, window 168 h", "ref_w336": "reference, window 336 h",
    "ref_tv": "reference + terminal value (mean marginal heat cost of the following week)",
    "ref_w120_tv": "reference, window 120 h + terminal value",
    "ref_guide": "reference + PF storage level as soft end-of-window target (upper bound)",
    "ref_c1": "reference with hourly re-planning (commitment 1 h)",
    "ref_gap": "reference, MIP gap 10⁻⁵ per window",
    "pprice": "reference with perfect price forecast", "sigma0": "reference without demand noise",
    "pi": "perfect information (prices, demand, partner A), 72 h", "pi_w120": "perfect information, 120 h",
    "pi_w168": "perfect information, 168 h", "pi_w336": "perfect information, 336 h", "pi_w720": "perfect information, 720 h",
    "pi_tv": "perfect information, 72 h + terminal value", "pi_guide": "perfect information, 72 h + PF guide curve",
    "pi_gap": "perfect information, 72 h, MIP gap 10⁻⁵",
}


def t_foresight_decomp(r: Path) -> pd.DataFrame | None:
    p = r / "rolling_horizon" / "foresight" / "foresight_rh.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p).set_index("case")
    order = [c for c in FORESIGHT_LABELS if c in d.index]
    return pd.DataFrame([{"case": FORESIGHT_LABELS[c], "V_TES RH [k]": k(d.at[c, "V_TES_RH"]),
                          "RH / PF": f"{100 * d.at[c, 'share_of_PF']:.0f} %", "TES discharge [GWh]": f"{d.at[c, 'TES_dis_GWh']:.1f}"}
                         for c in order])


def t_size(r: Path, cfg: dict) -> pd.DataFrame:
    pf = pd.read_csv(r / "economics_tes_sizes.csv")
    rh = pd.read_csv(r / "rolling_horizon" / "tes_values_rh.csv")
    ec = cfg["economics"]
    af = annuity_factor(ec["discount_rate"], ec["lifetime_tes_a"])
    m = pf.merge(rh[["V_m3", "Q_MW", "V_TES_RH_EUR"]], on=["V_m3", "Q_MW"])
    a1 = pd.read_csv(r / "sensitivities" / "A1" / "summary.csv")
    a1["V_m3"] = a1["case"].str.extract(r"V(\d+)_").astype(float)
    a1["Q_MW"] = a1["case"].str.extract(r"_Q(\d+)").astype(float)
    m = m.merge(a1[[c for c in ("V_m3", "Q_MW", "attr_E", "dC_hyd", "TES_EFC") if c in a1]], on=["V_m3", "Q_MW"], how="left")
    rows = []
    for _, x in m.sort_values(["V_m3", "Q_MW"]).iterrows():
        be_rh = (x["V_TES_RH_EUR"] / af - ec["tes_capex_fixed_eur"]) / x["V_m3"]
        rows.append({"V [m³]": n(x["V_m3"]), "Q [MW]": n(x["Q_MW"]), "τ [h]": f"{x['tau_h']:.1f}",
                     "V_TES PF [k]": f"{x['value_kEUR_a']:.1f}", "V_TES RH [k]": k(x["V_TES_RH_EUR"]),
                     "RH/PF": f"{100 * x['V_TES_RH_EUR'] / 1e3 / x['value_kEUR_a']:.0f} %",
                     "break-even PF / RH [EUR/m³]": f"{n(x['break_even_EUR_per_m3'])} / {n(be_rh)}",
                     "EFC": f"{x['TES_EFC']:.0f}" if "TES_EFC" in x and pd.notna(x.get("TES_EFC")) else "–",
                     "attr. h (E)": int(x["attr_E"]) if pd.notna(x.get("attr_E")) else "–",
                     "ΔC_hyd [EUR/a]": f"{x['dC_hyd']:.0f}" if "dC_hyd" in x and pd.notna(x.get("dC_hyd")) else "–"})
    return pd.DataFrame(rows)


def _sum(r: Path, sid: str) -> pd.DataFrame | None:
    p = r / "sensitivities" / sid / "summary.csv"
    return pd.read_csv(p) if p.exists() else None


def t_sens(r: Path) -> str:
    f = pd.read_csv(r / "scenario_runs" / "factorial_summary.csv").set_index("scenario")
    c0, c110 = f.at["F000", "C_E"], f.at["F110", "C_E"]
    out = []
    a2 = _sum(r, "A2")
    if a2 is not None:
        g = a2.pivot(index="case", columns="scenario", values="C_E")
        gh = a2.pivot(index="case", columns="scenario", values="C_H") if "C_H" in a2 else None
        rows = []
        for case in sorted(g.index, key=lambda s: int(s[2:])):
            row = {"DN": case[2:], "V_TES (F110 − F111), E [k]": k(g.at[case, "F110"] - g.at[case, "F111"])}
            if gh is not None:
                row["V_TES, H [k]"] = k(gh.at[case, "F110"] - gh.at[case, "F111"])
            s = a2[(a2["case"] == case) & (a2["scenario"] == "F111")].iloc[0]
            row |= {"κ_link": f"{s['kappa_link']:.2f}", "attr. h (E)": int(s["attr_E"]),
                    "ΔC_hyd F111 [EUR/a]": f"{s['dC_hyd']:.0f}" if "dC_hyd" in s else "–"}
            rows.append(row)
        out.append("**A2 — connection DN** (F110/F111)\n\n" + md(pd.DataFrame(rows)))
    a3 = _sum(r, "A3")
    if a3 is not None:
        rows = [{"TES model / strategy": "temperature classes (reference)", "V_TES alone [k]": k(c0 - f.at["F001", "C_E"]),
                 "v(F111) [k]": k(c0 - f.at["F111", "C_E"]), "U_A F111": f"{100 * _j(r / 'scenario_runs' / 'F111-E' / 'annual_metrics.json')['metrics']['partner_A']['U']:.1f} %", "ΔC_hyd F111 [EUR/a]": f"{f.at['F111', 'dC_hyd_A']:.0f}"}]
        for case in ("single_fixed", "single_monthly", "single_daily"):
            g = a3[a3["case"] == case].set_index("scenario")
            if {"F001", "F111"} <= set(g.index):
                rows.append({"TES model / strategy": case.replace("_", " "), "V_TES alone [k]": k(c0 - g.at["F001", "C_E"]),
                             "v(F111) [k]": k(c0 - g.at["F111", "C_E"]), "U_A F111": f"{100 * g.at['F111', 'U_A']:.1f} %",
                             "ΔC_hyd F111 [EUR/a]": f"{g.at['F111', 'dC_hyd']:.0f}" if "dC_hyd" in g else "–"})
        e = r / "sensitivities" / "A3e" / "single_energy_only"
        if (e / "F001-E" / "annual_metrics.json").exists():
            c1 = _j(e / "F001-E" / "annual_metrics.json")["metrics"]["cost_total_EUR"]
            c3 = _j(e / "F111-E" / "annual_metrics.json")["metrics"]
            rows.append({"TES model / strategy": "single, energy only (no temperature limits, 120 °C capacity; A3e)",
                         "V_TES alone [k]": k(c0 - c1), "v(F111) [k]": k(c0 - c3["cost_total_EUR"]),
                         "U_A F111": f"{100 * c3['partner_A']['U']:.1f} %", "ΔC_hyd F111 [EUR/a]": "–"})
        out.append("**A3 — TES temperature handling**\n\n" + md(pd.DataFrame(rows)))
    a6 = _sum(r, "A6")
    if a6 is not None:
        rows = []
        for _, s in a6.iterrows():
            lab = "off" if s["case"] == "casc_off" else f"on, T_mid {s['case'][4:]} °C" + (" (reference)" if s["case"] == "Tmid80" else "")
            rows.append({"cascade": lab, "C_E F111 − reference [EUR/a]": f"{s['C_E'] - f.at['F111', 'C_E']:.0f}",
                         "cascade share of HP heat": f"{abs(100 * s['cascade_share']):.1f} %"})
        out.append("**A6 — HP → EB cascade** (F111, Mode E)\n\n" + md(pd.DataFrame(rows)))
    a4 = _sum(r, "A4")
    if a4 is not None:
        c101 = a4[a4["case"] == "ref_F101"]["C_E"].iloc[0]
        rows = []
        for case in [c for c in a4["case"].unique() if c.startswith("pi")]:
            g = a4[a4["case"] == case].set_index("scenario")
            p = float(case[2:])
            vb = c101 - g.at["F111", "C_E"]
            rows.append({"π [EUR/MWh]": n(p), "v_B = C(F101) − C(F111) [k]": k(vb), "EB heat F111 [GWh]": f"{g.at['F111', 'B_heat_GWh']:.2f}",
                         "premium revenue π·Q [k]": k(p * g.at["F111", "B_heat_GWh"] * 1e3)})
        out.append("**A4 — partner-B premium** (break-even premium per spec, C(F111) ≤ C(F101): above the scanned 60 EUR/MWh)\n\n"
                   + md(pd.DataFrame(rows)))
    a5 = _sum(r, "A5")
    if a5 is not None:
        rows = []
        c101 = a5[a5["case"] == "ref_F101"]["C_E"].iloc[0]
        for case in [c for c in a5["case"].unique() if c != "ref_F101"]:
            g = a5[a5["case"] == case].set_index("scenario")
            rows.append({"c_el,var / demand charge": case.replace("_", " / "), "v(F111) [k]": k(c0 - g.at["F111", "C_E"]),
                         "v_B = C(F101) − C(F111) [k]": k(c101 - g.at["F111", "C_E"]),
                         "EB heat F111 [GWh]": f"{g.at['F111', 'B_heat_GWh']:.2f}"})
        out.append("**A5 — partner-B electricity cost regime**\n\n" + md(pd.DataFrame(rows)))
    pp = _sum(r, "P")
    if pp is not None:
        rows = []
        for case in pp["case"].unique():
            g = pp[pp["case"] == case].set_index("scenario")
            ref = g.at["F000", "C_E"] if "F000" in g.index else c0
            rows.append({"case": case, **{f"C_E {s} [M]": f"{g.at[s, 'C_E'] / 1e6:.3f}" for s in g.index},
                         "v(F111) vs own F000 [k]": k(ref - g.at["F111", "C_E"]) if "F111" in g.index else "–"})
        out.append("**P — prices, waste-heat fee, model variants** (Mode E)\n\n" + md(pd.DataFrame(rows).fillna("–")))
    pr = _sum(r, "PR")
    if pr is not None:
        from .metrics import annuity_factor
        cfg = C.load()
        af = annuity_factor(cfg["economics"]["discount_rate"], cfg["heat_pump"]["lifetime_a"])
        rows = [{"case": "reference (HP 5 MW, 17 °C, fee 5, η_C 0.5, 38 EUR/MWh)", "value A alone [k]": k(c0 - f.at["F100", "C_E"]),
                 "value A with B+TES [k]": k(f.at["F011", "C_E"] - f.at["F111", "C_E"]), "U_A F111": f"{100 * _j(r / 'scenario_runs' / 'F111-E' / 'annual_metrics.json')['metrics']['partner_A']['U']:.1f} %",
                 "I_max HP [M EUR/MW]": f"{(c0 - f.at['F100', 'C_E']) / af / 5e6:.2f}"}]
        for case, g in pr.groupby("case", sort=False):
            g = g.set_index("scenario")
            if "F100" not in g.index:
                continue
            size = float(case[2:]) if case.startswith("hp") and not case.startswith("hp_") else 5.0
            rows.append({"case": case, "value A alone [k]": k(c0 - g.at["F100", "C_E"]),
                         "value A with B+TES [k]": k(f.at["F011", "C_E"] - g.at["F111", "C_E"]),
                         "U_A F111": f"{100 * g.at['F111', 'U_A']:.1f} %",
                         "I_max HP [M EUR/MW]": f"{(c0 - g.at['F100', 'C_E']) / af / size / 1e6:.2f}"})
        out.append("**PR — partner A** (HP investment justified by the value of A alone, 5 %, 20 a; DEA cost 0.95 M EUR/MW)\n\n" + md(pd.DataFrame(rows)))
        rows = []
        for case, g in pr.groupby("case", sort=False):
            g = g.set_index("scenario")
            if "F010" not in g.index:
                continue
            rows.append({"case": case, "value B alone [k]": k(c0 - g.at["F010", "C_E"]),
                         "value B with A+TES [k]": k(f.at["F101", "C_E"] - g.at["F111", "C_E"]), "EB heat F111 [GWh]": f"{g.at['F111', 'B_heat_GWh']:.2f}"})
        rows.insert(0, {"case": "reference (EB 10 MW)", "value B alone [k]": k(c0 - f.at["F010", "C_E"]),
                        "value B with A+TES [k]": k(f.at["F101", "C_E"] - f.at["F111", "C_E"]), "EB heat F111 [GWh]": f"{_j(r / 'scenario_runs' / 'F111-E' / 'annual_metrics.json')['metrics']['partner_B']['heat_GWh']:.2f}"})
        out.append("**PR — partner B (EB size)**\n\n" + md(pd.DataFrame(rows)))
    at = _sum(r, "AT")
    if at is not None:
        cfg = C.load()
        from .metrics import annuity_factor
        af = annuity_factor(cfg["economics"]["discount_rate"], cfg["economics"]["lifetime_tes_a"])
        rows = []
        atrh = r / "rolling_horizon" / "at_values_rh.csv"
        rh_v = pd.read_csv(atrh).set_index("case")["V_TES_RH_EUR"] if atrh.exists() else pd.Series(dtype=float)
        for _, x in at.iterrows():
            v = f.at["F110", "C_E"] - x["C_E"]
            vol = float(x["case"].split("_")[1][1:])
            fx = cfg["economics"]["tes_capex_fixed_eur"]
            row = {"case": x["case"], "V_TES vs F110, PF [k]": k(v), "TES discharge [GWh]": f"{x['TES_dis_GWh']:.2f}",
                   "break-even PF [EUR/m³]": n((v / af - fx) / vol), "DEA cost [EUR/m³]": n(3055.0 * vol ** -0.309) if vol <= 20000 else "≈ 250"}
            if x["case"] in rh_v.index:
                vr = rh_v[x["case"]]
                row |= {"V_TES, RH [k]": k(vr), "break-even RH [EUR/m³]": n((vr / af - fx) / vol)}
            rows.append(row)
        out.append("**AT — atmospheric tank (classes 90/95 °C)** (DEA cost curve 3055·V^−0.309, 20 000 m³ extrapolated; DEA 50 000 m³ case ≈ 250 EUR/m³)\n\n" + md(pd.DataFrame(rows)))
    ps = _sum(r, "PS")
    if ps is not None:
        rows = [{"partner-A calendar shift": "0 (reference)", "A alone [k]": k(c0 - f.at["F100", "C_E"]),
                 "A with TES [k]": k(f.at["F001", "C_E"] - f.at["F101", "C_E"]), "v(F111) [k]": k(c0 - f.at["F111", "C_E"])}]
        for case, g in ps.groupby("case", sort=False):
            g = g.set_index("scenario")["C_E"]
            rows.append({"partner-A calendar shift": case.replace("shift", "").replace("d", " d"), "A alone [k]": k(c0 - g["F100"]),
                         "A with TES [k]": k(f.at["F001", "C_E"] - g["F101"]), "v(F111) [k]": k(c0 - g["F111"])})
        out.append("**PS — partner-A data mapping** (2023 profile shifted against the 2025 calendar)\n\n" + md(pd.DataFrame(rows)))
    rob = r / "rolling_horizon" / "robustness_rh.csv"
    if rob.exists():
        d = pd.read_csv(rob)
        rows = [{"σ demand": f"{100 * x['sigma']:.0f} %", "seed": int(x["seed"]), "v(F111), RH [k]": k(x["v_F111"]),
                 "V_TES (F110 − F111), RH [k]": k(x["V_TES"]), "V_TES RH / PF": f"{100 * x['V_TES'] / (f.at['F110', 'C_E'] - f.at['F111', 'C_E']):.0f} %"}
                for _, x in d.iterrows()]
        out.append("**RH robustness** (forecast-noise seed and σ; partner-A schedule known; reference σ 5 %, seed 1234: "
                   "see T4)\n\n" + md(pd.DataFrame(rows)))
    b2 = _sum(r, "B2")
    if b2 is not None:
        from .metrics import shapley
        rows = []
        for case, g in b2.groupby("case"):
            c = g.set_index("scenario")["C_E"]
            if len(c) == 8:
                sh = shapley(c.to_dict())
                rows.append({"price year": case[-4:], "v(F111) [k]": k(sh["v_full"]), "φ TES [k]": k(sh["phi"]["TES"]),
                             "φ A [k]": k(sh["phi"]["A"]), "φ B [k]": k(sh["phi"]["B"]),
                             "A+B share": f"{100 * (sh['phi']['A'] + sh['phi']['B']) / sh['v_full']:.0f} %"})
        out.append("**B2 — price year** (2025 demand)\n\n" + md(pd.DataFrame(rows)))
    pg = _sum(r, "PG")
    if pg is not None:
        from .metrics import shapley
        ec = C.load()["economics"]
        af_t, fx_t = annuity_factor(ec["discount_rate"], ec["lifetime_tes_a"]), ec["tes_capex_fixed_eur"]
        ref = f["C_E"].to_dict()
        rows = []
        for case, cc in [("gas 48 (reference)", ref)] + [(f"gas {c[3:]}", g.set_index("scenario")["C_E"].to_dict())
                                                          for c, g in pg.groupby("case")]:
            if len(cc) >= 8:
                sh = shapley({k_: cc[k_] for k_ in ("F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111")})
                rows.append({"gas price [EUR/MWh]": case, "v(F111) [k]": k(sh["v_full"]), "φ TES [k]": k(sh["phi"]["TES"]),
                             "φ A [k]": k(sh["phi"]["A"]), "φ B [k]": k(sh["phi"]["B"]),
                             "A+B share": f"{100 * (sh['phi']['A'] + sh['phi']['B']) / sh['v_full']:.0f} %",
                             "V_TES (F110 − F111) [k]": k(cc["F110"] - cc["F111"]),
                             "break-even TES 5 000 m³ PF [EUR/m³]": n(((cc["F110"] - cc["F111"]) / af_t - fx_t) / 5000)})
        out.append("**PG — gas price downwards** (2025 spot level ≈ 37 EUR/MWh; upwards: set P)\n\n" + md(pd.DataFrame(rows)))
    bl = _sum(r, "BL")
    if bl is not None:
        from .metrics import shapley
        rows = []
        for case, cc in [("60 (reference)", f["C_E"].to_dict())] + [(c[3:], {**f["C_E"].to_dict(), **g.set_index("scenario")["C_E"].to_dict()})
                                                                     for c, g in bl.groupby("case")]:
            sh = shapley({k_: cc[k_] for k_ in ("F000", "F001", "F100", "F010", "F110", "F101", "F011", "F111")})
            rows.append({"c_el,var EB [EUR/MWh]": case, "B alone [k]": k(cc["F000"] - cc["F010"]), "φ B [k]": k(sh["phi"]["B"]),
                         "φ A [k]": k(sh["phi"]["A"]), "φ TES [k]": k(sh["phi"]["TES"]), "v(F111) [k]": k(sh["v_full"]),
                         "A+B share": f"{100 * (sh['phi']['A'] + sh['phi']['B']) / sh['v_full']:.0f} %"})
        out.append("**BL — partner-B electricity cost over the literature range** (levy floor 11.4 + network charge 23.6 / 42.8 / "
                   "61.8 EUR/MWh; no demand charge)\n\n" + md(pd.DataFrame(rows)))
    b4 = _sum(r, "B4")
    if b4 is not None:
        rows = [{"V06 limit [bar]": x["case"].split("_")[1], "scenario": x["scenario"], "violating h (E)": x["viol_E"],
                 "ΔC_hyd [EUR/a]": f"{x['dC_hyd']:.0f}", "KWK > 4 bar [h]": x["soft_KWK_h_E"]} for _, x in b4.iterrows()]
        out.append("**B4 — limit at the south end (V06)**\n\n" + md(pd.DataFrame(rows)))
    del c110
    return "\n\n".join(out)


HOSTING_LABELS = {"F000": "no TES", "F110": "partners A + B, no TES", "F001_S": "TES at S", "F111_S": "TES at S + A + B",
                  "F001_south": "TES in the south (V06)", "F111_south": "TES in the south + A + B",
                  "F001_south_V20000_Q80": "TES in the south, 20 000 m³ / 80 MW",
                  "F000_kwk4": "no TES, KWK ≤ 4 bar", "F001_S_kwk4": "TES at S, KWK ≤ 4 bar",
                  "F001_south_kwk4": "TES in the south, KWK ≤ 4 bar"}


def t_hosting(r: Path) -> str:
    p = r / "hosting" / "summary.csv"
    if not p.exists():
        return "(not run)"
    s = pd.read_csv(p)
    rows = [{"variant": HOSTING_LABELS.get(x["variant"], x["variant"]), "south growth": f"+{100 * x['share']:g} %",
             "unserved heat [MWh/a]": f"{x['unserved_H_MWh']:.1f}", "peak [MW]": f"{x['unserved_peak_H_MW']:.2f}",
             "hours": int(x["unserved_hours_H"]) if pd.notna(x.get("unserved_hours_H")) else "–",
             "redispatch cost ΔC_hyd [k]": k(x["dC_hyd_excl"]),
             "value vs no TES at equal heat [k]": k(x["value_vs_F000_H"]) if (not x["variant"].startswith("F000") and pd.notna(x["value_vs_F000_H"])) else "–",
             "remaining violation [bar]": f"{x['max_violation_H_bar']:.2f}"}
            for _, x in s.sort_values(["variant", "share"], key=lambda c: c.map(list(HOSTING_LABELS).index) if c.name == "variant" else c).iterrows()]
    hc = []
    for v, g in s.groupby("variant"):
        ok, bad = g[g["unserved_H_MWh"] < 0.01]["share"], g[g["unserved_H_MWh"] >= 0.01]["share"]
        if len(ok) and len(bad) and bad.min() > ok.max():
            hc.append(f"{HOSTING_LABELS.get(v, v)}: +{100 * ok.max():g} … +{100 * bad.min():g} %")
    return ("No new capacity; heat that the existing network cannot deliver to the new south customers within the hydraulic "
            "limits is unserved (Mode H, calibration A, perfect foresight). Hosting limit (last level without / first with "
            "unserved heat): " + "; ".join(hc) + "\n\n" + md(pd.DataFrame(rows)))


def t_expansion(r: Path) -> str:
    out = []
    xr = _sum(r, "XR")
    if xr is not None:
        cfg = C.load()
        from .metrics import annuity_factor
        af = annuity_factor(cfg["economics"]["discount_rate"], cfg["economics"]["lifetime_link_a"])
        x = pd.read_csv(r / "sensitivities" / "X" / "summary.csv")
        length = {e: L_ for e, *_r, L_ in __import__("scripts.dhn_study.netzmodell", fromlist=["KANTEN"]).KANTEN}
        rows = []
        for _, s_ in xr.iterrows():
            L = int(s_["case"][1:3])
            base = x[(x["case"] == f"L{L}") & (x["scenario"] == "F111")].iloc[0]
            edges = ["L4b"] if s_["case"].endswith("R1") else ["L4a", "L4b", "L4c"]
            pipe = sum(length[e] for e in edges) * cfg["economics"]["link_capex_eur_per_m"]
            rows.append({"level": f"+{L} %", "reinforcement": " + ".join(edges) + " (parallel pipe)",
                         "length [km]": f"{sum(length[e] for e in edges) / 1e3:.2f}", "C_H [M]": f"{s_['C_H'] / 1e6:.3f}",
                         "saving vs. boiler-only (incl. boiler capital) [k]": k(base["C_H"] - s_["C_H"]),
                         "pipe annuity [k]": k(pipe * af), "net [k]": k(base["C_H"] - s_["C_H"] - pipe * af),
                         "new boiler [MW] (without → with)": f"{base['C_new_MW_H']:.1f} → {abs(s_['C_new_MW_H']):.1f}",
                         "Mode H": "conv." if s_["conv_H"] else "not conv."})
        out.append("**XR — reinforcement of the south trunk** (F111; pipe 3 000 EUR/m, 40 a, 5 %)\n\n" + md(pd.DataFrame(rows)))
    for sid, title in (("X", "**X — south expansion** (Mode H on calibration A; TES at S)"),
                       ("X4", "**X4 — south expansion with KWK Δp ≤ 4 bar as hard limit**")):
        p = r / "sensitivities" / sid / "expansion_summary.csv"
        if not p.exists():
            continue
        s = pd.read_csv(p)
        s = s[~s["variant"].str.contains("south")]
        rows = [{"level": f"+{int(x['level'])} %", "scenario": x["variant"], "C_E [M]": f"{x['C_E'] / 1e6:.3f}",
                 "C_H [M]": f"{x['C_H'] / 1e6:.3f}", "ΔC_hyd [k]": k(x["dC_hyd"]), "new boiler [MW]": f"{abs(x['C_new_MW_H']):.1f}",
                 "its heat [GWh]": f"{abs(x['NEW_heat_GWh_H']):.1f}", "KWK Δp P95 H [bar]": f"{x['dpKWK_p95_H']:.2f}",
                 "Mode H": "conv." if x["conv_H"] else "not conv."} for _, x in s.iterrows()]
        out.append(title + "\n\n" + md(pd.DataFrame(rows)))
    return "\n\n".join(out)


def main():
    cfg = C.load()
    r = C.root() / cfg["paths"]["results"]
    parts = ["# Paper tables — central TES study (generated)",
             "Generated by `python -m scripts.dhn_study.central_tes.paper_tables` from `results/central_tes/`. "
             "k = kEUR/a, M = M EUR/a. Perfect foresight (PF) unless stated; RH = rolling horizon (72 h / 24 h). "
             "TES at site S (station of partner A, next to partner B).",
             "## T1 Inputs and assumptions\n\n" + md(t_inputs(cfg)),
             "## T2 Factorial (today's load)\n\n" + md(t_factorial(r)),
             "## T3 Shapley attribution\n\n" + md(t_shapley(r)),
             "## T4 Foresight\n\n" + md(t_foresight(r)),
             "## T4b Foresight decomposition (TES with A + B: F110 − F111; PF reference = 100 %)\n\n"
             + (md(t_foresight_decomp(r)) if t_foresight_decomp(r) is not None else "(not run)"),
             "## T5 TES size × power (A1): value and break-even investment\n\n" + md(t_size(r, cfg)),
             "## T6 Sensitivities\n\n" + t_sens(r),
             "## T7 South hosting capacity (no new capacity)\n\n" + t_hosting(r),
             "## T7b New capacity in the south — supplementary (not part of current planning: new boiler / pipe)\n\n" + t_expansion(r)]
    out = C.root() / "reports" / "central_tes" / "paper_tables.md"
    out.write_text("\n\n".join(parts) + "\n")
    print(out)


if __name__ == "__main__":
    main()
