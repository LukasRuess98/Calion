"""Gesamtlauf der Datenanalysen auf dem anonymisierten Datensatz DHN-A.

Aufruf aus der Repository-Wurzel:  ``python -m scripts.dhn_study.run_analyse``
Ergebnisse: ``results/dhn_study/datenanalyse/`` (CSV + ``zusammenfassung.md``, nicht versioniert).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import anker, auslegung, daten, hydraulik, wetter

T_AUSL = -14.0          # Auslegungs-Tagesmittel (≈ 10-Jahres-Kältetag der Referenzstation, siehe Kältewellen)
DP_GRENZE = 4.0         # Plan A: max. Differenzdruck Austritt Hauptanlage (Status offen, siehe Grenzband)
T_VL_AUSL = 120.0       # Vorlauf bei Auslegung (Heizkurve 110 − Ta, begrenzt auf 120 °C)


def main() -> dict:
    out_dir = daten.repo_root() / "results" / "dhn_study" / "datenanalyse"
    out_dir.mkdir(parents=True, exist_ok=True)
    m = daten.lade_messdaten()
    erg = {}

    # 1) Signalprüfungen
    erg["duplikate"] = daten.identische_signale(m)
    einh = {st: daten.einheitentest(m[f"{st}_heat"], m[f"{st}_flow"], m[f"{st}_T_supply"], m[f"{st}_T_return"])
            for st in ("V07", "V22", "V14", "V05", "boiler_plant_2_hx", "biomass_CHP")}
    erg["einheiten"] = pd.DataFrame(einh).T
    erg["einheiten"].to_csv(out_dir / "einheitentest.csv")

    # 2) Erzeugung (korrigiert) und Wetter
    e = daten.erzeugung(m)
    erg["gt_modell"] = e.attrs["gt_modell"]
    erg["gt_quellen"] = e.gt_quelle.value_counts(normalize=True).round(3).to_dict()
    ta_h, ta_d = daten.lade_aussentemperatur()
    erg["kaeltewellen"] = wetter.kaeltewellen(ta_d)
    erg["kaeltewellen"].to_csv(out_dir / "kaeltewellen.csv", index=False)

    # 3) Auslegungslast
    lg = daten.lade_lastgaenge()
    erg["ausrichtung_2020"] = auslegung.pruefe_ausrichtung(lg[2020].to_numpy(), 2020, ta_d)
    reihen = {"Lastgang 2020–2022": pd.concat(lg.values()), "2025 gesamt": e["gesamt"], "2025 Verbund": e["verbund"]}
    erg["auslegung"] = auslegung.auslegungsband(reihen, ta_d, T_AUSL, wetter.ta_eff(ta_d))
    erg["auslegung"].to_csv(out_dir / "auslegungslast.csv", index=False)
    erg["spitzenfaktor"] = {k: auslegung.spitzenfaktor(s, ta_d) for k, s in (("Lastgang 2020–2022", pd.concat(lg.values())), ("2025 gesamt", e["gesamt"]))}
    ung = []
    for name, s_h in (("Lastgang 2020–2022", pd.concat(lg.values())), ("2025 Verbund", e["verbund"]), ("2025 gesamt", e["gesamt"])):
        pt = s_h.resample("D").mean()
        f0 = auslegung.fit_last_temperatur(pt, ta_d, **auslegung.MODELLE["linear unbegrenzt (Fit ≥ 0 °C)"])
        ung.append(auslegung.ungedeckte_last(pt, ta_d, f0).assign(Reihe=name).reset_index(names="Ta-Klasse"))
    erg["ungedeckt"] = pd.concat(ung, ignore_index=True)[["Reihe", "Ta-Klasse", "Tage", "Erwartet_MW", "Differenz_MW", "Differenz [%]"]]
    erg["ungedeckt"].to_csv(out_dir / "ungedeckte_last_kaeltetage.csv", index=False)

    # 4) Heizkurve und Rücklauf der Hauptanlage gegen Außentemperatur
    x = pd.concat([ta_h.reindex(m.index), m.gas_CHP_T_supply, m.gas_CHP_T_return], axis=1, keys=["Ta", "VL", "RL"]).dropna()
    x["Klasse"] = np.floor(x.Ta / 2) * 2 + 1
    hk = x.groupby("Klasse").agg(n=("VL", "size"), VL=("VL", "median"), RL=("RL", "median"),
                                 RL_P90=("RL", lambda s: s.quantile(0.9)))
    hk["Vorgabe"] = np.clip(110 - hk.index, 90, 120)
    erg["heizkurve"] = hk[hk.index <= 13]
    erg["heizkurve"].to_csv(out_dir / "heizkurve_hauptanlage.csv")

    # 5) Hydraulische Begrenzung bei Kälte: aktive Grenzen, Ost-Kopplung, Schlechtpunktregelung Süd, Versorgung kalter Werktage
    kd = daten.kunden_dp(m)
    mitte_min = kd[daten.MITTE_STATIONEN].min(axis=1)
    sued_min = kd[daten.SUED_SCHLECHTPUNKTE].min(axis=1)
    dp_chp = m.gas_CHP_p_supply - m.gas_CHP_p_return
    dT = m.gas_CHP_T_supply - m.gas_CHP_T_return
    ps1 = m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump
    ms = hydraulik.massenstroeme(m, e)
    gt_an = e["gas_turbine"] > 2.0
    dp_ost = pd.concat([m.waste_incineration_p_supply - m.waste_incineration_p_return, m.gas_turbine_dp.where(gt_an),
                        m.biomass_CHP_dp], axis=1).max(axis=1)
    ta = ta_h.reindex(m.index)
    erg["grenzen"] = hydraulik.aktive_grenzen(pd.DataFrame({"dp_ost": dp_ost, "dp_kwk": dp_chp, "dp_sued": sued_min,
                                                            "dp_mitte": mitte_min, "gt_an": gt_an}), ta)
    erg["grenzen"].to_csv(out_dir / "aktive_grenzen.csv")
    erg["ost_kopplung"] = hydraulik.fit_ost_kopplung(m.waste_incineration_p_supply - m.waste_incineration_p_return, dp_chp, ms.Ost, ms.KWK)
    erg["ost_kopplung_diff"] = anker.netzhebel({"MVA-Δp": m.waste_incineration_p_supply - m.waste_incineration_p_return},
                                               pd.DataFrame({"KWK-Δp [bar]": dp_chp, "ṁ_Ost [100 kg/s]": ms.Ost / 100,
                                                             "ṁ_KWK [100 kg/s]": ms.KWK / 100, "ṁ_HW1 [100 kg/s]": ms.HW1 / 100}))
    F = e["verbund"] / dT
    erg["regelgesetz_sued"] = hydraulik.fit_regelgesetz_sued(dp_chp, F, ms.HW1, ps1, maske=ta < 8)
    # Abweichung kalter Werktage vom unbegrenzten Bedarf je Station und Versorgungsweg (2025)
    ab = []
    for name, s_h in {**{st: m[f"{st}_heat"] for st in ("V05", "V14", "V07", "V22", "V13")}, "Verbund": e["verbund"],
                      "gesamt": e["gesamt"], "WÜ Verbund → West": e["hx_west"], "Kessel West (HW2)": e["boilers_west"]}.items():
        pt = s_h.resample("D").mean().where(s_h.resample("D").count() >= 20)
        f0 = auslegung.fit_last_temperatur(pt, ta_d, t_min=0.0, ferien=True)
        u = auslegung.ungedeckte_last(pt, ta_d, f0, klassen=(-20, -2))
        ab.append({"Reihe": name, **u.iloc[0].to_dict()} if len(u) else {"Reihe": name})
    erg["abweichung_kalt"] = pd.DataFrame(ab)
    erg["abweichung_kalt"].to_csv(out_dir / "abweichung_kalte_werktage_2025.csv", index=False)

    # 6) Grenzband der KWK-Δp und Machbarkeit des Auslegungspunkts
    anl = daten.lade_anlagen()["plants"]
    kwk = anl["gas_CHP"]
    erg["kwk_band"] = {"Planwert (Plan A)": kwk["dp_max_outlet_bar"], "gemessen max. 2025": float(dp_chp.max()),
                       "aus Pumpenförderhöhe": hydraulik.dp_aus_pumpe(kwk["pumps"]["head_m"], T_VL_AUSL, kwk["dp_internal_bar"])}
    fit = anker.fit_verlustgesetz(dp_chp, mitte_min, e["verbund"], dT)
    erg["verlustgesetz"] = fit
    sp = erg["spitzenfaktor"]["2025 gesamt"]["median"]
    kalt = x[x.Ta < -5]
    dT_ausl = {"RL Median Kälte": T_VL_AUSL - kalt.RL.median(), "RL P90 Kälte": T_VL_AUSL - kalt.RL.quantile(0.9)}
    erg["dT_ausl"] = dT_ausl
    ost_mw = sum(anl[k]["P_max_MW"]["design_minus14C"] for k in ("waste_incineration", "gas_turbine", "biomass_CHP"))
    hw1_mw, hw1_m = anl["boiler_plant_1"]["P_max_MW"]["design_minus14C"], anl["boiler_plant_1"]["m_max_t_h"] / 3.6
    ps1_voll = float(ps1.quantile(0.99))
    fo, fs = erg["ost_kopplung"], erg["regelgesetz_sued"]
    aus = erg["auslegung"]
    v = aus[(aus.Reihe == "2025 Verbund") & (aus.Temperatur == "Ta")]
    band = erg["kwk_band"]

    def fall(P, dTd, ost=ost_mw):
        t_rl = T_VL_AUSL - dTd
        m_ost = float(hydraulik.massenstrom(ost, T_VL_AUSL, t_rl))
        m_hw1 = min(hw1_m, float(hydraulik.massenstrom(hw1_mw, T_VL_AUSL, t_rl)))
        m_kwk = float(hydraulik.massenstrom(P - ost - hw1_mw, T_VL_AUSL, t_rl))
        dp_m = anker.erforderliche_dp(fit, P, dTd, 1.0)
        dp_s = hydraulik.erforderliche_dp_sued(fs, P, dTd, m_hw1, ps1_voll)
        g_ost = hydraulik.kwk_grenze_ost(fo, m_ost, m_kwk)
        res = {k: hydraulik.ausbaureserve(fit, fs, P, dTd, g, m_hw1, ps1_voll)["gesamt"]
               for k, g in (("4,0 bar", band["Planwert (Plan A)"]), ("Pumpe", band["aus Pumpenförderhöhe"]))}
        return {"P Stunde [MW]": P, "ΔT [K]": dTd, "P_KWK [MW]": P - ost - hw1_mw,
                "Erzeugungsreserve [MW]": kwk["P_max_MW"]["design_minus14C"] + ost + hw1_mw - P,
                "erf. KWK-Δp Mitte [bar]": dp_m, "erf. KWK-Δp Süd [bar]": dp_s, "erf. KWK-Δp [bar]": max(dp_m, dp_s),
                "KWK-Grenze aus Ost [bar]": g_ost, "Reserve bis 4,0 bar": res["4,0 bar"], "Reserve bis Pumpe": res["Pumpe"],
                "Extrapolation F (Süd)": (P / dTd) / fs["F_p99"]}

    dT0 = dT_ausl["RL Median Kälte"]
    rows = []
    for _, r in v.iterrows():
        for q in ("P50", "P90"):
            rows.append({"Lastmodell": f"{r.Modell} {q}", **fall(r[f"{q} bei {T_AUSL:g} °C [MW]"] * sp, dT0)})
    erg["erforderliche_dp"] = pd.DataFrame(rows)
    erg["erforderliche_dp"].to_csv(out_dir / "erforderliche_dp_hauptanlage.csv", index=False)
    P_ref = v[v.Modell.str.startswith("linear unbegrenzt")][f"P50 bei {T_AUSL:g} °C [MW]"].iloc[0] * sp
    erg["sensitivitaet_rl"] = pd.DataFrame([{"Rücklauf": lab, **fall(P_ref, dTd)} for lab, dTd in
                                            (("gemessen Median (Ta < −5 °C)", dT0), ("gemessen P90", dT_ausl["RL P90 Kälte"]),
                                             ("Median + 5 K", dT0 - 5.0), ("Median − 5 K", dT0 + 5.0))])
    # Ost-Grenze im heutigen Kältebetrieb (Ta < −2 °C, GT in Betrieb): Medianwerte der Massenströme
    kalt_gt = (ta < -2) & gt_an
    t_ost_vl = m.waste_incineration_T_supply[kalt_gt].median()
    m_o, m_k = float(ms.Ost[kalt_gt].median()), float(ms.KWK[kalt_gt].median())
    m_o_120 = m_o * float(daten.dh(t_ost_vl, m.waste_incineration_T_return[kalt_gt].median()) / daten.dh(T_VL_AUSL, m.waste_incineration_T_return[kalt_gt].median()))
    dp_mva = m.waste_incineration_p_supply - m.waste_incineration_p_return
    mva = anl["waste_incineration"]
    erg["mva_band"] = {"Planwert (Plan A)": mva["dp_max_outlet_bar"], "P99 2025": float(dp_mva.quantile(0.99)), "max. 2025": float(dp_mva.max()),
                       "Stunden > Planwert": int((dp_mva > mva["dp_max_outlet_bar"]).sum()),
                       "aus Pumpenförderhöhe (RL-Pumpe)": hydraulik.dp_aus_pumpe(mva["pumps"]["head_m"], float(m.waste_incineration_T_return[kalt_gt].median()), mva["dp_internal_bar"])}
    erg["ost_grenze_2025"] = {"Stunden": int(kalt_gt.sum()), "Ost-VL [°C]": float(t_ost_vl), "ṁ_Ost [kg/s]": m_o, "ṁ_KWK [kg/s]": m_k,
                              "ṁ_Ost bei Ost-VL 120 °C [kg/s]": m_o_120, "KWK-Δp gemessen (Median)": float(dp_chp[kalt_gt].median())}
    for lab, g in (("MVA 7,5 bar", erg["mva_band"]["Planwert (Plan A)"]), ("MVA P99 2025", erg["mva_band"]["P99 2025"])):
        erg["ost_grenze_2025"][f"KWK-Grenze ({lab}) [bar]"] = hydraulik.kwk_grenze_ost(fo, m_o, m_k, g)
        erg["ost_grenze_2025"][f"KWK-Grenze ({lab}, Ost-VL 120 °C) [bar]"] = hydraulik.kwk_grenze_ost(fo, m_o_120, m_k, g)
    # Thermische Spitze am Auslegungstag gegen die Verbund-Erzeugungsleistung (Plan A, −14 °C; KWK auch im Umleitbetrieb)
    prof = auslegung.tagesprofile(pd.concat(lg.values()), ta_d)
    leistung = {"Plan A (−14 °C)": kwk["P_max_MW"]["design_minus14C"] + ost_mw + hw1_mw,
                "KWK im Umleitbetrieb": kwk["P_max_MW"]["diversion_mode"] + ost_mw + hw1_mw}
    erg["spitze"] = pd.DataFrame([{"Lastmodell": f"{r.Modell} {q}", "Tagesmittel [MW]": r[f"{q} bei {T_AUSL:g} °C [MW]"],
                                   "Erzeugung": lab, "Leistung [MW]": L,
                                   **auslegung.ueberschuss(prof, r[f"{q} bei {T_AUSL:g} °C [MW]"], L)}
                                  for _, r in v.iterrows() for q in ("P50", "P90") for lab, L in leistung.items()])
    erg["spitze"].to_csv(out_dir / "spitze_auslegungstag.csv", index=False)
    erg["auslegung_annahmen"] = {"Ost-Einspeisung [MW]": ost_mw, "HW1 [MW]": hw1_mw, "HW1 [kg/s]": hw1_m,
                                 "PS1-Gewinn (P99 2025) [bar]": ps1_voll, "Spitzenfaktor": sp, "Verbund-Erzeugung [MW]": leistung}
    hoch = e["verbund"] >= e["verbund"].quantile(0.9)
    erg["dp_chp_2025"] = {"Hochlast-P95": float(dp_chp[hoch].quantile(0.95)), "max": float(dp_chp.max()),
                          "Stunden > 4,0 bar": int((dp_chp > 4.0).sum())}

    # 7) Netzhebel (Differenzenregression)
    reg = pd.DataFrame({"boiler_plant_1 [100 kg/s]": m.boiler_plant_1_flow / 3.6 / 100, "gas_CHP-Δp [bar]": dp_chp,
                        "waste_incineration-Δp [bar]": m.waste_incineration_p_supply - m.waste_incineration_p_return,
                        "Last [10 MW]": e["verbund"] / 10,
                        "pump_station_1-Gewinn [bar]": m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump})
    ziele = {k: kd[k] for k in ["V06", "V12", "V03", "V10", "V24", "V23", "V22", "V15", "HX_West"] if k in kd}
    erg["netzhebel"] = anker.netzhebel(ziele, reg)
    erg["netzhebel"].to_csv(out_dir / "netzhebel.csv", index=False)

    # 8) Temperatur-Tracer (Anteil Ost-Wasser, Winter)
    t_ost = m[["waste_incineration_T_supply", "biomass_CHP_T_supply"]].mean(axis=1)
    winter = pd.Series(m.index.month.isin([1, 2, 11, 12]), index=m.index)
    erg["tracer"] = pd.DataFrame({st: anker.tracer_anteil(m[col], m.gas_CHP_T_supply, t_ost, maske=winter) for st, col in {
        "V22": "V22_T_supply", "V11": "V11_T_supply", "V15 (Hausanschluss)": "V15_house_T_supply", "V23": "V23_T_supply",
        "V17": "V17_T_supply", "V12": "V12_T_supply", "V24": "V24_T_supply", "V05": "V05_T_supply"}.items()}).T
    erg["tracer"].to_csv(out_dir / "tracer_ostanteil.csv")

    _bericht(erg, out_dir)
    return erg


def _md(df: pd.DataFrame, index: bool = True) -> str:
    """Markdown-Tabelle ohne Zusatzabhängigkeit (tabulate)."""
    df = df.reset_index() if index else df
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + "---|" * len(df.columns)
    zeilen = ["| " + " | ".join(f"{v:.3g}" if isinstance(v, float) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *zeilen])


def _bericht(erg: dict, out_dir) -> None:
    f, fo, fs = erg["verlustgesetz"], erg["ost_kopplung"], erg["regelgesetz_sued"]
    teile = ["# Datenanalyse DHN-A – Zusammenfassung (automatisch erzeugt)", "",
             f"Identische Signale: {erg['duplikate']}", f"GT-Quellen: {erg['gt_quellen']}; Imputationsmodell R² = {erg['gt_modell']['r2']:.2f}", "",
             "## Einheitentest", _md(erg["einheiten"].round(3)), "", "## Kältewellen (Referenzstation)", _md(erg["kaeltewellen"].round(1), index=False), "",
             f"Ausrichtung Lastgang 2020 (Korrelation): {erg['ausrichtung_2020']}", "", "## Auslegungslast", _md(erg["auslegung"].round(1), index=False), "",
             "## Ungedeckte Last an kalten Werktagen (gegen Fit ≥ 0 °C)", _md(erg["ungedeckt"].round(1), index=False), "",
             f"Spitzenfaktoren: {erg['spitzenfaktor']}", "", "## Heizkurve Hauptanlage", _md(erg["heizkurve"].round(1)), "",
             f"Auslegungsspreizung aus gemessenem Rücklauf: {erg['dT_ausl']}", "",
             "## Hydraulische Begrenzung: aktive Grenzen je Außentemperatur", _md(erg["grenzen"].round(2)), "",
             f"Ost-Kopplung (Niveau): Δp_MVA − Δp_KWK = {fo['c']:.2f} + {fo['d']:.3f}·(ṁ_Ost/100)² − {fo['f']:.3f}·(ṁ_KWK/100)² "
             f"(R² {fo['r2']:.2f}, Rest P90 {fo['residuum_p90']:.2f} bar, n {fo['n']}, ṁ_Ost P99 {fo['m_ost_p99']:.0f} kg/s, ṁ_KWK P99 {fo['m_kwk_p99']:.0f} kg/s)",
             "", "Ost-Kopplung (Differenzen):", _md(erg["ost_kopplung_diff"].round(3), index=False), "",
             f"Regelgesetz Süd: Δp_KWK = {fs['a']:.2f} + {fs['b']:.3f}·F² − {fs['g']:.2f}·ṁ_HW1/100 − {fs['h']:.2f}·Δp_PS1 "
             f"(R² {fs['r2']:.2f}, Rest P90 {fs['residuum_p90']:.2f} bar, n {fs['n']}, F P99 {fs['F_p99']:.2f})", "",
             "## Kalte Werktage 2025 (Ta < −2 °C) gegen unbegrenzten Bedarf", _md(erg["abweichung_kalt"].round(2), index=False), "",
             f"## Grenzband KWK-Δp: {erg['kwk_band']}", "",
             f"## Verlustgesetz Mitte: a = {f['a']:.3f}, b = {f['b']:.4f} (R² {f['r2']:.2f}, n {f['n']}, F_max {f['F_max']:.2f}, Residuum P90 {f['residuum_p90']:.2f} bar)",
             f"Annahmen Auslegung: {erg['auslegung_annahmen']}", "",
             _md(erg["erforderliche_dp"].round(2), index=False), "", "Sensitivität Rücklauf (linear unbegrenzt P50):",
             _md(erg["sensitivitaet_rl"].round(2), index=False), "", f"Ost-Grenze im Kältebetrieb 2025: {erg['ost_grenze_2025']}", "", f"MVA-Δp-Band: {erg['mva_band']}", "",
             f"Δp Hauptanlage 2025: {erg['dp_chp_2025']}", "",
             "## Thermische Spitze am Auslegungstag (Profile Lastgang 2020–2022, Werktage < −2 °C)", _md(erg["spitze"].round(1), index=False), "",
             "## Netzhebel", _md(erg["netzhebel"].round(3), index=False), "", "## Tracer", _md(erg["tracer"].round(2))]
    (out_dir / "zusammenfassung.md").write_text("\n".join(teile), encoding="utf-8")


if __name__ == "__main__":
    main()
