"""Gesamtlauf der Datenanalysen auf dem anonymisierten Datensatz DHN-A.

Aufruf aus der Repository-Wurzel:  ``python -m scripts.dhn_study.run_analyse``
Ergebnisse: ``results/dhn_study/datenanalyse/`` (CSV + ``zusammenfassung.md``, nicht versioniert).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import anker, auslegung, daten, wetter

T_AUSL = -14.0          # Auslegungs-Tagesmittel (≈ 10-Jahres-Kältetag der Referenzstation, siehe Kältewellen)
DP_GRENZE = 4.0         # Plan A: max. Differenzdruck Austritt Hauptanlage (Status offen)


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

    # 4) Heizkurve und Rücklauf der Hauptanlage gegen Außentemperatur
    x = pd.concat([ta_h.reindex(m.index), m.gas_CHP_T_supply, m.gas_CHP_T_return], axis=1, keys=["Ta", "VL", "RL"]).dropna()
    x["Klasse"] = np.floor(x.Ta / 2) * 2 + 1
    hk = x.groupby("Klasse").agg(n=("VL", "size"), VL=("VL", "median"), RL=("RL", "median"),
                                 RL_P90=("RL", lambda s: s.quantile(0.9)))
    hk["Vorgabe"] = np.clip(110 - hk.index, 90, 120)
    erg["heizkurve"] = hk[hk.index <= 13]
    erg["heizkurve"].to_csv(out_dir / "heizkurve_hauptanlage.csv")

    # 5) Verlustgesetz und erforderliche Δp der Hauptanlage bei Auslegung
    kd = daten.kunden_dp(m)
    mitte_min = kd[daten.MITTE_STATIONEN].min(axis=1)
    dp_chp = m.gas_CHP_p_supply - m.gas_CHP_p_return
    dT = m.gas_CHP_T_supply - m.gas_CHP_T_return
    fit = anker.fit_verlustgesetz(dp_chp, mitte_min, e["verbund"], dT)
    erg["verlustgesetz"] = fit
    sp = erg["spitzenfaktor"]["2025 gesamt"]["median"]
    kalt = x[x.Ta < -5]
    dT_ausl = {"RL Median Kälte": 120.0 - kalt.RL.median(), "RL P90 Kälte": 120.0 - kalt.RL.quantile(0.9)}
    erg["dT_ausl"] = dT_ausl
    aus = erg["auslegung"]
    v = aus[(aus.Reihe == "2025 Verbund") & (aus.Temperatur == "Ta")]
    rows = []
    for _, r in v.iterrows():
        for q in ("P50", "P90"):
            P = r[f"{q} bei {T_AUSL:g} °C [MW]"] * sp
            for lab, dTd in dT_ausl.items():
                rows.append({"Lastmodell": f"{r.Modell} {q}", "P Stunde [MW]": P, "Spreizung": f"{lab} ({dTd:.1f} K)",
                             "erf. Δp (1,0 bar) [bar]": anker.erforderliche_dp(fit, P, dTd, 1.0),
                             "erf. Δp (1,2 bar) [bar]": anker.erforderliche_dp(fit, P, dTd, 1.2),
                             "Ausbaureserve bis 4,0 bar": anker.ausbaureserve(fit, P, dTd, DP_GRENZE, 1.0)})
    erg["erforderliche_dp"] = pd.DataFrame(rows)
    erg["erforderliche_dp"].to_csv(out_dir / "erforderliche_dp_hauptanlage.csv", index=False)
    hoch = e["verbund"] >= e["verbund"].quantile(0.9)
    erg["dp_chp_2025"] = {"Hochlast-P95": float(dp_chp[hoch].quantile(0.95)), "max": float(dp_chp.max())}

    # 6) Netzhebel (Differenzenregression)
    reg = pd.DataFrame({"boiler_plant_1 [100 kg/s]": m.boiler_plant_1_flow / 3.6 / 100, "gas_CHP-Δp [bar]": dp_chp,
                        "waste_incineration-Δp [bar]": m.waste_incineration_p_supply - m.waste_incineration_p_return,
                        "Last [10 MW]": e["verbund"] / 10,
                        "pump_station_1-Gewinn [bar]": m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump})
    ziele = {k: kd[k] for k in ["V06", "V12", "V03", "V10", "V24", "V23", "V22", "V15", "HX_West"] if k in kd}
    erg["netzhebel"] = anker.netzhebel(ziele, reg)
    erg["netzhebel"].to_csv(out_dir / "netzhebel.csv", index=False)

    # 7) Temperatur-Tracer (Anteil Ost-Wasser, Winter)
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
    f = erg["verlustgesetz"]
    teile = ["# Datenanalyse DHN-A – Zusammenfassung (automatisch erzeugt)", "",
             f"Identische Signale: {erg['duplikate']}", f"GT-Quellen: {erg['gt_quellen']}; Imputationsmodell R² = {erg['gt_modell']['r2']:.2f}", "",
             "## Einheitentest", _md(erg["einheiten"].round(3)), "", "## Kältewellen (Referenzstation)", _md(erg["kaeltewellen"].round(1), index=False), "",
             f"Ausrichtung Lastgang 2020 (Korrelation): {erg['ausrichtung_2020']}", "", "## Auslegungslast", _md(erg["auslegung"].round(1), index=False), "",
             f"Spitzenfaktoren: {erg['spitzenfaktor']}", "", "## Heizkurve Hauptanlage", _md(erg["heizkurve"].round(1)), "",
             f"Auslegungsspreizung aus gemessenem Rücklauf: {erg['dT_ausl']}", "",
             f"## Verlustgesetz: a = {f['a']:.3f}, b = {f['b']:.4f} (R² {f['r2']:.2f}, n {f['n']}, F_max {f['F_max']:.2f}, Residuum P90 {f['residuum_p90']:.2f} bar)",
             _md(erg["erforderliche_dp"].round(2), index=False), f"Δp Hauptanlage 2025: {erg['dp_chp_2025']}", "",
             "## Netzhebel", _md(erg["netzhebel"].round(3), index=False), "", "## Tracer", _md(erg["tracer"].round(2))]
    (out_dir / "zusammenfassung.md").write_text("\n".join(teile), encoding="utf-8")


if __name__ == "__main__":
    main()
