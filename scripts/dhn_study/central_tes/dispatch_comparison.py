"""Kraftwerkseinsatz 2025: gemessener Betrieb (IST) gegen MILP F000 (Mode E, Mode H) und eine wärmegeführte Regel.

Fahrpläne (alle ohne Speicher und ohne Partner A/B):
* ``IST``: gemessene Wärme der Bestandsanlagen (``Q_meas_*``), aufgebaut wie ``Hydro._sched_measured``: fehlende Werte
  = 0, die KWK schließt die Bilanz zur Last ``D`` (sie ist auch im Netzmodell die Ausgleichsanlage).
* ``MILP_E`` / ``MILP_H``: Szenario F000 der Studie, perfekte Voraussicht, Mode H mit Kalibrierung A.
* Fairness-Treppe: ``MILP_E_MVA_IST`` (MVA fährt wie gemessen statt bis Monats-P95) → ``MILP_H_MVA_IST_KWKGRENZE``
  (zusätzlich KWK-Δp-Modellbedarf ≤ 4,0 bar − gemessene Betriebsreserve, harte Grenze in Mode H) → ``MILP_UC`` (zusätzlich
  Mindestlasten = P5 der IST-Last und Anfahrkosten als Binärvariablen für KWK, GT, HW1; Mode-H-Iteration gegen dieselbe
  KWK-Grenze; HW1 darf takten, wenn die Restlast unter seiner Mindestlast liegt; Notkühlung mit Strafe nur, wenn sonst
  unzulässig). ``MILP_UC_PROZENT``: Mindestlasten 30/50/10 % der Kapazität.
* ``REGEL``: feste Merit-Order ohne Strompreissignal (BIO must-run → MVA → KWK → GT → HW1) in denselben Grenzen
  wie MILP_E_MVA_IST.
* Nur in ``meta.json``: MILP mit gesperrten MVA-Ausfallstunden, MILP mit MVA ≤ gemessen, KWK-Grenze 4,0 bar ohne Reserve.

Alle Fahrpläne werden mit derselben Kostenfunktion bewertet wie im MILP (``milp.plant_costs``: Brennstoff, CO2,
Energiesteuer, MVA-Übernahmepreis, Biomasse, Stromgutschrift zum Day-Ahead-Preis). Anfahrkosten werden für alle
Fahrpläne gleich, aber getrennt bewertet; Pumpenstrom ist nicht Teil des MILP und wird nur berichtet.

    python -m scripts.dhn_study.central_tes.dispatch_comparison [--uc-sets ist prozent] [--skip-uc] [--uc-wiederverwenden]

Ergebnisse: ``results/central_tes/dispatch_comparison/`` (gitignored), Bericht ``reports/central_tes/dispatch_comparison.md``.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from .. import daten
from . import config as C
from . import cop, coupling, inputs, milp
from .hydraulics import Hydro
from .milp import EXISTING, PLANTS

ON_MW = 1.0                                                   # Betrieb: Wärme > 1 MW
MERIT_ORDER = ["BIO", "MVA", "KWK", "GT", "HW1"]
CHP = ["KWK", "GT", "BIO"]
UC_PLANTS = ["KWK", "GT", "HW1"]
MINLAST_ANTEIL_VORSCHLAG = {"KWK": 0.30, "GT": 0.50, "HW1": 0.10}  # Vorschlag der Aufgabe (Variante "prozent")
ANFAHRKOSTEN_EUR = {"KWK": 5000.0, "GT": 2000.0, "HW1": 200.0}    # Annahme je Start
NOTKUEHLUNG_EUR_MWH = 10000.0                                     # Strafe für Überschusswärme (nur MILP_UC)
TAKTEN = ("HW1",)          # Kessel: Stundenmittel unter Mindestlast zulässig, wenn die Restlast selbst darunter liegt
KWK_ERFAHRUNGSWERT_BAR = 4.0
PREISKLASSEN = [(-np.inf, 0.0, "< 0"), (0.0, 50.0, "0–50"), (50.0, 100.0, "50–100"), (100.0, 150.0, "100–150"),
                (150.0, np.inf, "> 150")]
FAHRPLAENE = ["IST", "REGEL", "MILP_E", "MILP_H", "MILP_E_MVA_IST", "MILP_H_MVA_IST_KWKGRENZE", "MILP_UC", "MILP_UC_PROZENT"]


# --------------------------------------------------------------------------------------------------- Fahrpläne
def ist_fahrplan(hy: Hydro) -> pd.DataFrame:
    """Gemessener Einsatz wie ``Hydro._sched_measured`` (KWK schließt die Bilanz)."""
    return hy._sched_measured().astype(float)


def mva_ausfall(x: pd.DataFrame) -> pd.Series:
    """Stunden, in denen die MVA gemessen keine Wärme lieferte: < 1 MW, oder Messlücke bei kaltem Vorlauf (≤ 90 °C)."""
    m = daten.lade_messdaten().reindex(x.index)
    q = x["Q_meas_MVA"]
    warm = m["waste_incineration_T_supply"] > 90.0
    return ((q.fillna(0.0) < ON_MW) & ~(q.isna() & warm)).rename("mva_ausfall")


def mit_grenzen(x: pd.DataFrame, cfg: dict, sperre_mva: pd.Series | None = None, mva: str | None = None) -> pd.DataFrame:
    """Eingangsdaten mit vorab berechneten Anlagengrenzen (``lo_*``/``hi_*``, von ``milp.plant_bounds`` genutzt).
    ``sperre_mva``: MVA-Obergrenze 0 in diesen Stunden. ``mva``: ``"max_ist"`` = Obergrenze gemessene Wärme der Stunde
    (statt Monats-P95); ``"fest"`` = MVA fährt wie gemessen (abfallgeführte Abnahme), höchstens bis zur Last nach BIO."""
    if mva in ("max_ist", "fest"):
        lo, hi = milp.plant_bounds(x, C.merge(cfg, {"plants": {"MVA": {"availability": None}}}))
        q = x["Q_meas_MVA"].fillna(0.0).clip(lower=0.0)
        if mva == "fest":
            hi["MVA"] = q
            lo["MVA"] = np.minimum(q, np.maximum(x["D"] - lo["BIO"], 0.0))
        else:
            hi["MVA"] = np.minimum(hi["MVA"], q)
    else:
        lo, hi = milp.plant_bounds(x, cfg)
    if sperre_mva is not None:
        hi.loc[sperre_mva.to_numpy(), "MVA"] = 0.0
    xb = x.copy()
    for g in PLANTS:
        xb[f"lo_{g}"], xb[f"hi_{g}"] = lo[g], hi[g]
    return xb


def milp_f000(x: pd.DataFrame, s: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict, pyo.ConcreteModel]:
    m = milp.build(x, s, cfg, milp.Flags(False, False, False))
    info = milp.solve(m, cfg)
    return milp.extract(m, x, s, cfg), info, m


def milp_uc(x: pd.DataFrame, s: pd.DataFrame, cfg: dict, minlast: dict, anfahr: dict, u0: dict,
            cuts: list | None = None) -> tuple[pd.DataFrame, dict]:
    """F000 mit Mindestlast (Q ≥ P_min·u) und Anfahrkosten (st ≥ u_t − u_{t−1}) für ``UC_PLANTS``; ``cuts``: hydraulische
    Schnitte aus einem Mode-H-Lauf (gleiches Format wie ``milp.build``). Für die Kessel in ``TAKTEN`` gilt die Mindestlast
    nicht in Stunden, in denen die Restlast nach den Muss-Anlagen (D − Σ Untergrenzen der übrigen Anlagen) kleiner als die
    Mindestlast ist: ein Kessel kann innerhalb der Stunde takten, das Stundenmittel liegt dann unter der Mindestlast."""
    m = milp.build(x, s, cfg, milp.Flags(False, False, False), cuts=cuts)
    lo, hi = milp.plant_bounds(x, cfg)
    T = len(x)
    rest = (x["D"] - sum(lo[g] for g in PLANTS if g not in minlast)).to_numpy()
    takt = {g: (rest < minlast[g]) if g in TAKTEN else np.zeros(T, bool) for g in minlast}
    m.UC = pyo.Set(initialize=list(minlast))
    m.u = pyo.Var(m.UC, m.H, domain=pyo.Binary)
    m.st = pyo.Var(m.UC, m.H, bounds=(0.0, 1.0))
    hia = {g: hi[g].to_numpy() for g in minlast}
    m.uc_hi = pyo.Constraint(m.UC, m.H, rule=lambda _m, g, t: _m.Q[g, t] <= float(hia[g][t]) * _m.u[g, t])
    m.uc_lo = pyo.Constraint(m.UC, m.H, rule=lambda _m, g, t: pyo.Constraint.Skip if takt[g][t]
                             else _m.Q[g, t] >= float(minlast[g]) * _m.u[g, t])
    m.uc_st = pyo.Constraint(m.UC, m.H, rule=lambda _m, g, t: _m.st[g, t] >= _m.u[g, t] - (_m.u[g, t - 1] if t > 0 else float(u0[g])))
    # Notkühlung: Überschusswärme, falls der Restbedarf nach BIO/MVA unter allen Mindestlasten liegt (sonst unzulässig)
    m.dump = pyo.Var(m.H, bounds=(0.0, None))
    D = x["D"].to_numpy()
    m.bal.deactivate()
    m.bal_uc = pyo.Constraint(m.H, rule=lambda _m, t: sum(_m.Q[g, t] for g in PLANTS) + _m.Qc[t] + _m.Qtx[t] + _m.Qek[t]
                              - _m.dump[t] == float(D[t]))
    expr = (m.obj.expr + sum(float(anfahr[g]) * m.st[g, t] for g in minlast for t in range(T))
            + NOTKUEHLUNG_EUR_MWH * cfg["meta"]["dt_h"] * sum(m.dump[t] for t in range(T)))
    m.del_component(m.obj)
    m.obj = pyo.Objective(expr=expr, sense=pyo.minimize)
    info = milp.solve(m, cfg)
    sched = milp.extract(m, x, s, cfg)
    sched["Q_dump"] = np.array([pyo.value(m.dump[t]) for t in range(T)])
    info["notkuehlung_MWh"] = float(sched["Q_dump"].sum() * cfg["meta"]["dt_h"])
    info["notkuehlung_h"] = int((sched["Q_dump"] > 1e-6).sum())
    info["takten_h"] = {g: int(v.sum()) for g, v in takt.items() if g in TAKTEN}
    sched["C_start"] = 0.0
    for g in minlast:
        sched[f"start_{g}"] = np.array([pyo.value(m.st[g, t]) for t in range(T)])
        sched["C_start"] += anfahr[g] * sched[f"start_{g}"]
    return sched, info


def milp_uc_h(x: pd.DataFrame, s: pd.DataFrame, cfg: dict, cfg_h: dict, hy: Hydro, minlast: dict, anfahr: dict,
              u0: dict, cuts: list, log=print) -> tuple[pd.DataFrame, dict]:
    """``milp_uc`` mit Mode-H-Iteration (Schnitte wie ``coupling.mode_h``) gegen die Grenzen von ``cfg_h``/``hy``."""
    cuts = list(cuts)
    eps = float(cfg_h["hydraulics"].get("cut_margin_bar", 0.02))
    verl = []
    for k in range(int(cfg_h["hydraulics"]["k_max"]) + 1):
        sched, info = milp_uc(x, s, cfg, minlast, anfahr, u0, cuts)
        ev = coupling.validate(hy, sched, cfg_h, x)
        verl.append(int(ev["violation"].sum()))
        log(f"    UC-H it {k}: {verl[-1]} h verletzt, obj {info['objective']:.0f}, gap {info['gap']:.1e}, {info['runtime_s']:.0f} s")
        if verl[-1] == 0:
            break
        new = coupling.make_cuts(hy, sched, ev, eps, False)
        if not new:
            break
        cuts += new
    info.update({"iterationen": k, "verletzungen_je_iteration": verl, "schnitte": len(cuts), "konvergiert": verl[-1] == 0})
    return sched, info


def schnitte(cuts_df: pd.DataFrame) -> list[dict]:
    """Schnittliste für ``milp.build`` aus der Schnitttabelle von ``coupling.mode_h``."""
    if cuts_df is None or cuts_df.empty:
        return []
    acols = [c for c in cuts_df if c.startswith("a_")]
    return [{"t": int(r["t"]), "rhs": float(r["rhs"]), "a": {c[2:]: float(r[c]) for c in acols}} for _, r in cuts_df.iterrows()]


def regel(x: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Wärmegeführte Merit-Order ohne Preissignal in den Grenzen von ``milp.plant_bounds`` und der Ost-Parallelgrenze."""
    lo, hi = milp.plant_bounds(x, cfg)
    em = cfg["plants"].get("east_parallel_max_kg_s")
    ost_cap = (em * x["dh"] / 1e3).to_numpy() if em else np.full(len(x), np.inf)
    rest = x["D"].to_numpy().copy()
    q, ost = {}, np.zeros(len(x))
    for g in MERIT_ORDER:
        cap = hi[g].to_numpy()
        if g in ("MVA", "GT", "BIO"):
            cap = np.minimum(cap, np.maximum(ost_cap - ost, 0.0))
        q[g] = np.clip(rest, lo[g].to_numpy(), np.maximum(cap, lo[g].to_numpy()))
        rest = rest - q[g]
        if g in ("MVA", "GT", "BIO"):
            ost = ost + q[g]
    out = pd.DataFrame({f"Q_{g}": q[g] for g in EXISTING}, index=x.index)
    out["Q_NEW"] = out["Q_central"] = out["Q_tes_ext"] = 0.0
    out.attrs["ungedeckt_MW"] = rest
    return out


# --------------------------------------------------------------------------------------------------- Bewertung
def kosten(sched: pd.DataFrame, x: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Stündliche Kosten je Anlage und Komponente [EUR]; ``gesamt`` = Σ milp.plant_costs·Q (dieselbe Funktion wie im
    MILP), die Komponenten (Brennstoff, CO2, Energiesteuer, Stromgutschrift) sind deren Aufteilung."""
    pc = milp.plant_costs(x, cfg)
    dt = cfg["meta"]["dt_h"]
    out = pd.DataFrame(index=x.index)
    for g in EXISTING:
        p = cfg["plants"][g]
        fu = cfg["fuels"][p["fuel"]]
        q = sched[f"Q_{g}"].to_numpy(dtype=float) * dt                  # gemessene Werte liegen teils als float32 vor
        out[f"{g}_brennstoff"] = fu["price"] / p["eta_th"] * q
        out[f"{g}_co2"] = fu["ef"] / 1e3 * cfg["co2_price_eur_t"] / p["eta_th"] * q
        out[f"{g}_steuer"] = p.get("energy_tax_eur_MWh", 0.0) / p["eta_th"] * q
        cr = p.get("eta_el", 0.0) / p["eta_th"] * x["price"].to_numpy() if cfg.get("chp_power_credit") == "day_ahead" else 0.0
        out[f"{g}_stromerloes"] = -cr * q
        out[f"{g}_gesamt"] = pc[g].to_numpy() * q
        komp = out[[f"{g}_brennstoff", f"{g}_co2", f"{g}_steuer", f"{g}_stromerloes"]].sum(axis=1)
        assert np.allclose(komp, out[f"{g}_gesamt"], atol=1e-6), f"Kostenaufteilung {g} weicht ab"
    out["gesamt"] = out[[f"{g}_gesamt" for g in EXISTING]].sum(axis=1)
    # Anfahrkosten getrennt und für jeden Fahrplan gleich bewertet (UC: Startvariablen des Modells, sonst Q > ON_MW)
    if "C_start" in sched:
        out["anfahrkosten"] = sched["C_start"].to_numpy()
    else:
        out["anfahrkosten"] = sum(ANFAHRKOSTEN_EUR[g] * starts(sched[f"Q_{g}"]).to_numpy() for g in UC_PLANTS)
    if "Q_dump" in sched:            # nur ausgewiesen: Modellstrafe der Notkühlung (MILP_UC), keine echte Kostenart;
        out["notkuehlung_strafe"] = NOTKUEHLUNG_EUR_MWH * sched["Q_dump"].to_numpy() * dt   # Brennstoff der Überschusswärme ist enthalten
    return out


def strom(sched: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """KWK-Strom je Anlage [MW_el] = Wärme · η_el/η_th (wie im Modell)."""
    return pd.DataFrame({g: sched[f"Q_{g}"] * cfg["plants"][g].get("eta_el", 0.0) / cfg["plants"][g]["eta_th"] for g in CHP})


def co2_t(sched: pd.DataFrame, cfg: dict) -> float:
    return float(sum((sched[f"Q_{g}"] / cfg["plants"][g]["eta_th"] * cfg["fuels"][cfg["plants"][g]["fuel"]]["ef"] / 1e3).sum()
                     for g in EXISTING) * cfg["meta"]["dt_h"])


def starts(q: pd.Series) -> pd.Series:
    """Anfahrten (aus → ein, ein = Q > ON_MW); die erste Stunde zählt nicht (Anfangszustand = erste Stunde)."""
    on = q > ON_MW
    return (on & ~on.shift(1, fill_value=bool(on.iloc[0]))).astype(float)


def fahrweise(q: pd.Series, minlast: float | None) -> dict:
    on = q > ON_MW
    out = {"anfahrten": int(starts(q).sum()), "rampen_GWh": float(q.diff().abs().sum() / 1e3)}
    if minlast is not None:
        out["h_unter_mindestlast"] = int((on & (q < minlast - 1e-6)).sum())
    return out


def hydraulik(hy: Hydro, sched: pd.DataFrame) -> pd.DataFrame:
    return hy.evaluate(coupling._sched_cols(sched))


def kennzahlen(name: str, sched: pd.DataFrame, k: pd.DataFrame, ev: pd.DataFrame, x: pd.DataFrame, cfg: dict,
               minlast: dict, minlast_prozent: dict, ref_kosten: tuple[float, float] | None) -> dict:
    dt = cfg["meta"]["dt_h"]
    z = {"Fahrplan": name, "Kosten gesamt [M€/a]": k["gesamt"].sum() / 1e6}
    for komp, lbl in (("brennstoff", "Brennstoff"), ("co2", "CO2"), ("steuer", "Energiesteuer"), ("stromerloes", "Stromerlös")):
        z[f"Kosten {lbl} [M€/a]"] = sum(k[f"{g}_{komp}"].sum() for g in EXISTING) / 1e6
    for g in EXISTING:
        z[f"Kosten {g} [M€/a]"] = k[f"{g}_gesamt"].sum() / 1e6
    z["Anfahrkosten bewertet [M€/a]"] = k["anfahrkosten"].sum() / 1e6
    z["Kosten inkl. Anfahrkosten [M€/a]"] = (k["gesamt"].sum() + k["anfahrkosten"].sum()) / 1e6
    if "notkuehlung_strafe" in k:
        z["Notkühlung [MWh/a]"] = k["notkuehlung_strafe"].sum() / NOTKUEHLUNG_EUR_MWH
        z["Notkühlung [h]"] = int((k["notkuehlung_strafe"] > 1e-6).sum())
        z["Notkühlung Modellstrafe (nicht in den Kosten) [M€/a]"] = k["notkuehlung_strafe"].sum() / 1e6
    if ref_kosten is not None:
        z["Differenz zu IST [M€/a]"] = z["Kosten gesamt [M€/a]"] - ref_kosten[0] / 1e6
        z["Differenz zu IST [%]"] = 100 * (k["gesamt"].sum() / ref_kosten[0] - 1)
        z["Differenz zu IST inkl. Anfahrkosten [M€/a]"] = z["Kosten inkl. Anfahrkosten [M€/a]"] - ref_kosten[1] / 1e6
    tot = sum(sched[f"Q_{g}"].sum() for g in EXISTING) * dt
    for g in EXISTING:
        q = sched[f"Q_{g}"]
        e = q.sum() * dt
        z[f"Wärme {g} [GWh/a]"] = e / 1e3
        z[f"Anteil {g} [%]"] = 100 * e / tot
        z[f"Vollbenutzungsstunden {g} [h]"] = e / cfg["plants"][g]["cap_MW"]
        z[f"Betriebsstunden {g} [h]"] = int((q > ON_MW).sum())
    el = strom(sched, cfg)
    neg = x["price"] < 0
    for g in CHP:
        e = el[g].sum() * dt
        z[f"Strom {g} [GWh/a]"] = e / 1e3
        z[f"Erzielter Strompreis {g} [€/MWh]"] = float((el[g] * x["price"]).sum() / el[g].sum()) if e > 0 else np.nan
        z[f"Strom {g} bei negativem Preis [GWh/a]"] = el[g][neg].sum() * dt / 1e3
        z[f"Stunden {g} in Betrieb bei negativem Preis [h]"] = int(((sched[f"Q_{g}"] > ON_MW) & neg).sum())
    z["CO2 Brennstoff [kt/a]"] = co2_t(sched, cfg) / 1e3
    for g in UC_PLANTS:
        fw = fahrweise(sched[f"Q_{g}"], minlast.get(g))
        z[f"Anfahrten {g} [-]"] = fw["anfahrten"]
        z[f"Rampen Σ|ΔQ| {g} [GWh/a]"] = fw["rampen_GWh"]
        z[f"Stunden unter Mindestlast {g} (IST-P5 {minlast[g]:.1f} MW) [h]"] = fw["h_unter_mindestlast"]
        z[f"Stunden unter Mindestlast {g} ({100 * MINLAST_ANTEIL_VORSCHLAG[g]:.0f} % = {minlast_prozent[g]:.1f} MW) [h]"] = \
            fahrweise(sched[f"Q_{g}"], minlast_prozent[g])["h_unter_mindestlast"]
    z["KWK-Δp erforderlich Mittel [bar]"] = float(ev["dp_KWK"].mean())
    z["KWK-Δp erforderlich P95 [bar]"] = float(ev["dp_KWK"].quantile(0.95))
    z["KWK-Δp erforderlich Max [bar]"] = float(ev["dp_KWK"].max())
    z["Stunden KWK-Δp > 4,0 bar [h]"] = int(ev["soft_KWK"].sum())
    z["Stunden mit hydraulischer Grenzverletzung [h]"] = int(ev["violation"].sum())
    z["Pumpenstrom (nicht in den Kosten) [MWh/a]"] = float(sum(ev[c].sum() for c in ev if c.startswith("P_pump_")) * dt)
    return z


# --------------------------------------------------------------------------------------------------- Prüfungen IST
def bilanzpruefung(ist: pd.DataFrame, x: pd.DataFrame) -> dict:
    roh = daten.erzeugung(daten.lade_messdaten())
    roh = pd.DataFrame({g: roh[c] for g, c in inputs.PLANT_COLS.items()}).reindex(x.index)
    summe = ist[[f"Q_{g}" for g in EXISTING]].sum(axis=1)
    abw = summe - x["D"]
    kwk_resid = ist["Q_KWK"] - x["Q_meas_KWK"]
    return {"Stunden": len(x), "Last modelliert ergänzt (D_imputed) [h]": int(x["D_imputed"].sum()),
            "Interpolierte Werte je Anlage (Lücken ≤ 6 h)": {g: int(roh[g].isna().sum() - x[f"Q_meas_{g}"].isna().sum())
                                                            for g in ("KWK", "MVA", "GT")},
            "Verbleibende Lücken (= 0 gesetzt, KWK schließt die Bilanz) [h]": {g: int(x[f"Q_meas_{g}"].isna().sum())
                                                                            for g in ("KWK", "MVA", "GT")},
            "davon MVA in MVA-Ausfallstunden [h]": int((x["Q_meas_MVA"].isna() & mva_ausfall(x)).sum()),
            "HW1 fehlend → 0 gesetzt [h]": int(roh["HW1"].isna().sum()),
            "BIO fehlend → Median gesetzt [h]": int(roh["BIO"].isna().sum()),
            "Summe IST − Last: Stunden mit |Abw.| > 0,01 MW": int((abw.abs() > 0.01).sum()),
            "Summe IST − Last: max |Abw.| [MW]": float(abw.abs().max()),
            "Summe IST − Last: Jahressumme [GWh]": float(abw.sum() / 1e3),
            "KWK als Ausgleich weicht von gemessener KWK ab: Stunden": int((kwk_resid.abs() > 0.01).sum()),
            "KWK als Ausgleich − gemessen: Jahressumme [GWh]": float(kwk_resid.sum() / 1e3)}


def grenzpruefung(ist: pd.DataFrame, x: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    lo, hi = milp.plant_bounds(x, cfg)
    rows = []
    for g in EXISTING:
        q = ist[f"Q_{g}"]
        p = cfg["plants"][g]
        mm = cfg["plants"]["m_max_kg_s"].get(g)
        m_cap = mm * x["dh"] / 1e3 if mm else pd.Series(np.inf, index=x.index)
        r = {"Anlage": g, "über Nennkapazität [h]": int((q > p["cap_MW"] + 1e-6).sum()),
             "über Massenstromgrenze m_max [h]": int((q > m_cap + 1e-6).sum()),
             "über Modell-Obergrenze gesamt [h]": int((q > hi[g] + 1e-6).sum()),
             "max. Überschreitung Obergrenze [MW]": float(max((q - hi[g]).max(), 0.0)),
             "unter Modell-Untergrenze (must-run) [h]": int((q < lo[g] - 1e-6).sum())}
        if p.get("availability") == "monthly_p95_measured":
            r["über Monats-P95-Verfügbarkeit [h]"] = int((q > hi[g] + 1e-6).sum())
        rows.append(r)
    em = cfg["plants"].get("east_parallel_max_kg_s")
    ost = ist[["Q_MVA", "Q_GT", "Q_BIO"]].sum(axis=1)
    rows.append({"Anlage": "MVA+GT+BIO", "über Ost-Parallelgrenze [h]": int((ost > em * x["dh"] / 1e3 + 1e-6).sum())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------------- Zerlegung
def zerlegung(sa: pd.DataFrame, sb: pd.DataFrame, ka: pd.DataFrame, kb: pd.DataFrame) -> pd.DataFrame:
    """Mengen-/Zeitpunkteffekt je Anlage (A → B) auf die Betriebskosten (ohne Anfahrkosten). Mengeneffekt = mittlere
    Grenzkosten in A × Mengenänderung, relativ zur KWK (Ausgleichsanlage); Zeitpunkteffekt = Menge in B × Änderung der
    mengengewichteten Grenzkosten. Exakt additiv."""
    ea = {g: sa[f"Q_{g}"].sum() for g in EXISTING}
    eb = {g: sb[f"Q_{g}"].sum() for g in EXISTING}
    ca = {g: ka[f"{g}_gesamt"].sum() for g in EXISTING}
    cb = {g: kb[f"{g}_gesamt"].sum() for g in EXISTING}
    cbar = {g: ca[g] / ea[g] if ea[g] > 1e-9 else (cb[g] / eb[g] if eb[g] > 1e-9 else 0.0) for g in EXISTING}
    menge = {g: (cbar[g] - cbar["KWK"]) * (eb[g] - ea[g]) for g in EXISTING if g != "KWK"}
    bilanz = cbar["KWK"] * sum(eb[g] - ea[g] for g in EXISTING)
    zeit = {g: cb[g] - ca[g] - cbar[g] * (eb[g] - ea[g]) for g in EXISTING}
    schritte = [("a) HW1 statt KWK (Menge)", menge["HW1"]),
                ("b) GT statt KWK (Menge)", menge["GT"]),
                ("b) Strompreis-Verlagerung KWK (Zeitpunkt)", zeit["KWK"]),
                ("b) Strompreis-Verlagerung GT (Zeitpunkt)", zeit["GT"]),
                ("c) MVA/BIO-Auslastung (Menge + Zeitpunkt)", menge["MVA"] + menge["BIO"] + zeit["MVA"] + zeit["BIO"]),
                ("d) Rest (HW1-Zeitpunkt, Bilanzabweichung)", zeit["HW1"] + bilanz)]
    df = pd.DataFrame(schritte, columns=["Schritt", "Wert [M€/a]"])
    df["Wert [M€/a]"] /= 1e6
    assert abs(df["Wert [M€/a]"].sum() * 1e6 - (kb["gesamt"].sum() - ka["gesamt"].sum())) < 1.0
    return df


def differenzen(ka: pd.DataFrame, kb: pd.DataFrame, x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = kb["gesamt"] - ka["gesamt"]
    g = d.groupby(np.asarray(x.index.month)).sum() / 1e3
    monat = pd.DataFrame({"Monat": g.index.astype(int), "Differenz [k€]": g.to_numpy()})
    p = x["price"]
    rows = []
    for a, b, lbl in PREISKLASSEN:
        sel = (p >= a) & (p < b) if np.isfinite(a) else (p < b)
        rows.append({"Preisklasse [€/MWh]": lbl, "Stunden": int(sel.sum()), "Differenz [k€]": float(d[sel].sum() / 1e3)})
    return monat, pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------------- Wochen
def wochen(x: pd.DataFrame) -> dict[str, pd.Timestamp]:
    """Montag 00:00 der drei Darstellungswochen (Kriterien im Bericht)."""
    idx = x.index
    mo = idx[(idx.dayofweek == 0) & (idx.hour == 0)]
    voll = [t for t in mo if (t + pd.Timedelta(hours=167)) in idx and len(x.loc[t:t + pd.Timedelta(hours=167)]) >= 166]
    jf = x.loc[x.index.month.isin([1, 2]), "D"]
    tmax = jf.idxmax()
    kalt = max(t for t in voll if t <= tmax)
    def spreizung(t):
        p = x.loc[t:t + pd.Timedelta(hours=167), "price"]
        return p.max() - p.min()
    ue = [t for t in voll if t.month in (4, 10) and (t + pd.Timedelta(hours=167)).month == t.month]
    uebergang = max(ue, key=spreizung)
    so = [t for t in voll if t.month in (6, 7, 8) and (t + pd.Timedelta(hours=167)).month in (6, 7, 8)]
    mittel = {t: x.loc[t:t + pd.Timedelta(hours=167), "D"].mean() for t in so}
    med = float(np.median(list(mittel.values())))
    sommer = min(so, key=lambda t: abs(mittel[t] - med))
    return {"Kältewoche": kalt, "Übergangswoche": uebergang, "Sommerwoche": sommer}


# --------------------------------------------------------------------------------------------------- Abbildungen
FARBE = {"BIO": "#7CC4B1", "MVA": "#179C7D", "KWK": "#005B7F", "GT": "#39C1CD", "HW1": "#F58220"}
TINTE, GEDAEMPFT, GITTER = "#1E2328", "#7C858B", "#E4E7E9"
# Fahrplanvergleich: IST neutral grau (Referenz), übrige Fahrpläne in fester Reihenfolge (validierte Palette)
BALKEN = {"IST": "#7C858B", "MILP_H": "#2a78d6", "MILP_H_MVA_IST_KWKGRENZE": "#1baf7a", "MILP_UC": "#4a3aa7", "REGEL": "#eb6834"}
NAME = {"IST": "IST (gemessen)", "REGEL": "Regel (Merit-Order)", "MILP_E": "MILP Mode E", "MILP_H": "MILP Mode H (Studie)",
        "MILP_E_MVA_IST": "MILP, MVA wie gemessen", "MILP_H_MVA_IST_KWKGRENZE": "MILP, MVA wie gemessen + KWK-Δp-Grenze",
        "MILP_UC": "MILP + Mindestlasten/Anfahrkosten", "MILP_UC_PROZENT": "MILP + Mindestlasten 30/50/10 %"}


def _stil(ax):
    ax.grid(axis="y", color=GITTER, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=TINTE, labelsize=8)


def abbildungen(out: Path, x: pd.DataFrame, plaene: dict, wo: dict, wf: pd.DataFrame, kz: pd.DataFrame):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    for name, t0 in wo.items():
        sl = slice(t0, t0 + pd.Timedelta(hours=167))
        fig, axs = plt.subplots(3, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [3, 3, 1.4]})
        for ax, fp in zip(axs[:2], ("IST", "MILP_H"), strict=True):
            s = plaene[fp].loc[sl]
            ax.stackplot(s.index, *[s[f"Q_{g}"].clip(lower=0) for g in MERIT_ORDER], colors=[FARBE[g] for g in MERIT_ORDER],
                         labels=MERIT_ORDER, step="post", linewidth=0)
            ax.plot(x.loc[sl].index, x.loc[sl, "D"], color=TINTE, linewidth=0.8, drawstyle="steps-post", label="Last")
            ax.set_ylabel("Wärme [MW]", fontsize=8)
            ax.set_title(f"{NAME[fp]} – {name} ab {t0:%d.%m.%Y}", fontsize=9, loc="left")
            _stil(ax)
        axs[0].legend(ncol=6, fontsize=7.5, frameon=False, loc="lower right", bbox_to_anchor=(1.0, 1.0))
        axs[2].plot(x.loc[sl].index, x.loc[sl, "price"], color=TINTE, linewidth=0.9, drawstyle="steps-post")
        axs[2].axhline(0, color=GEDAEMPFT, linewidth=0.6)
        axs[2].set_ylabel("Day-Ahead\n[€/MWh]", fontsize=8)
        _stil(axs[2])
        fig.tight_layout()
        fig.savefig(out / f"woche_{name.lower().replace('ä', 'ae').replace('ü', 'ue')}.png", dpi=130)
        plt.close(fig)
    # Wasserfall IST -> MILP_H
    w = wf[wf["Vergleich"] == "IST → MILP_H"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    cum = 0.0
    for i, v in enumerate(w["Wert [M€/a]"]):
        ax.bar(i, abs(v), bottom=min(cum, cum + v), color="#C94C2E" if v > 0 else "#179C7D", width=0.6)
        ax.text(i, cum + v + (0.04 if v >= 0 else -0.04), f"{v:+.2f}", ha="center", va="bottom" if v >= 0 else "top",
                fontsize=7.5, color=TINTE)
        cum += v
    ax.bar(len(w), cum, color=TINTE, width=0.6)
    ax.text(len(w), cum - 0.04, f"{cum:+.2f}", ha="center", va="top", fontsize=7.5, color=TINTE)
    ax.set_ylim(min(cum, 0) * 1.12, max(0.0, cum) + 0.15)
    ax.set_xticks(range(len(w) + 1))
    ax.set_xticklabels([s.split(" (")[0] for s in w["Schritt"]] + ["Summe"], rotation=20, ha="right", fontsize=7.5)
    ax.axhline(0, color=GEDAEMPFT, linewidth=0.6)
    ax.set_ylabel("Kostenänderung IST → MILP Mode H [M€/a]", fontsize=8)
    _stil(ax)
    fig.tight_layout()
    fig.savefig(out / "wasserfall.png", dpi=130)
    plt.close(fig)
    # Wärme je Anlage
    fig, ax = plt.subplots(figsize=(9, 4))
    fps = [f for f in BALKEN if f in plaene]
    wbar = 0.8 / len(fps)
    for j, fp in enumerate(fps):
        r = kz.set_index("Fahrplan").loc[fp]
        ax.bar(np.arange(len(EXISTING)) + (j - (len(fps) - 1) / 2) * wbar, [r[f"Wärme {g} [GWh/a]"] for g in EXISTING],
               width=wbar * 0.92, label=NAME[fp], color=BALKEN[fp])
    ax.set_xticks(range(len(EXISTING)))
    ax.set_xticklabels(EXISTING)
    ax.set_ylabel("Wärme [GWh/a]", fontsize=8)
    ax.legend(fontsize=7.5, frameon=False, ncol=2)
    _stil(ax)
    fig.tight_layout()
    fig.savefig(out / "waerme_je_anlage.png", dpi=130)
    plt.close(fig)
    # Dauerlinien HW1 und KWK
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, g in zip(axs, ("HW1", "KWK"), strict=True):
        for fp in ("IST", "MILP_H", "MILP_UC", "REGEL"):
            if fp in plaene:
                ax.plot(np.arange(len(x)), np.sort(plaene[fp][f"Q_{g}"].to_numpy())[::-1], color=BALKEN[fp], linewidth=1.4,
                        label=NAME[fp])
        ax.set_title(f"Jahresdauerlinie {g}", fontsize=9, loc="left")
        ax.set_xlabel("Stunden", fontsize=8)
        ax.set_ylabel("Wärme [MW]", fontsize=8)
        _stil(ax)
    axs[0].legend(fontsize=7.5, frameon=False)
    fig.tight_layout()
    fig.savefig(out / "dauerlinie_hw1_kwk.png", dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------------------------------- Ablauf
def main(argv=None) -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--uc-sets", nargs="*", default=["ist"], help="Mindestlast-Varianten für MILP_UC: ist (P5 IST) | prozent")
    ap.add_argument("--uc-time-limit", type=float, default=3600.0)
    ap.add_argument("--uc-gap", type=float, default=0.002)
    ap.add_argument("--skip-uc", action="store_true")
    ap.add_argument("--uc-wiederverwenden", action="store_true",
                    help="gespeicherte UC-Fahrpläne (fahrplan_MILP_UC*.parquet, uc_info.json) neu bewerten statt lösen")
    a = ap.parse_args(argv)
    t_start = time.time()
    cfg = C.load(a.config)
    out = C.root() / cfg["paths"]["results"] / "dispatch_comparison"
    out.mkdir(parents=True, exist_ok=True)
    log = lambda s: print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)  # noqa: E731
    x = inputs.build(cfg)
    s = cop.series(x, cfg)
    hy = Hydro(cfg, x, cfg["hydraulics"]["reference_variant"])
    ausfall = mva_ausfall(x)

    plaene, infos = {}, {}
    plaene["IST"] = ist_fahrplan(hy)
    sched_e, info_e, _ = milp_f000(x, s, cfg)
    plaene["MILP_E"], infos["MILP_E"] = sched_e, info_e
    log(f"MILP_E: {info_e['objective']:.0f} EUR ({info_e['status']}, {info_e['runtime_s']:.0f} s)")
    sh, ih, _evh, it_h, _cuts = coupling.mode_h(cfg, x, s, milp.Flags(False, False, False), hy, sched_e, info_e, log=log)
    plaene["MILP_H"], infos["MILP_H"] = sh, ih
    log(f"MILP_H: {ih['objective']:.0f} EUR, ΔC_hyd {ih['objective'] - info_e['objective']:.0f} EUR, konvergiert {ih['converged']}")
    m_mess = daten.lade_messdaten().reindex(x.index)
    dp_mess = m_mess["gas_CHP_p_supply"] - m_mess["gas_CHP_p_return"]
    ev_ist = hydraulik(hy, plaene["IST"])
    ok = np.isfinite(dp_mess.to_numpy())
    reserve = float(np.mean(dp_mess.to_numpy()[ok] - ev_ist["dp_KWK"].to_numpy()[ok]))   # Betriebsreserve über dem Modell-Mindestbedarf
    kwk_grenze = KWK_ERFAHRUNGSWERT_BAR - reserve
    info_extra = {}
    # Information: nur die MVA-Ausfallstunden gesperrt; MVA höchstens wie gemessen
    for key, xv in (("MILP_E_MVA_AUSFALL", mit_grenzen(x, cfg, ausfall)), ("MILP_E_MVA_MAX_IST", mit_grenzen(x, cfg, mva="max_ist"))):
        sv, iv, _ = milp_f000(xv, s, cfg)
        info_extra[key] = {"kosten_EUR": iv["objective"], "MVA_GWh": float(sv["Q_MVA"].sum() / 1e3)}
        log(f"{key}: {iv['objective']:.0f} EUR")
    # Fairness 1: MVA fährt wie gemessen (abfallgeführt, nicht frei bis Monats-P95 abrufbar)
    xb = mit_grenzen(x, cfg, mva="fest")
    sm, im, _ = milp_f000(xb, s, cfg)
    plaene["MILP_E_MVA_IST"], infos["MILP_E_MVA_IST"] = sm, im
    log(f"MILP_E_MVA_IST: {im['objective']:.0f} EUR")
    # Fairness 2: KWK-Δp-Modellbedarf ≤ 4,0 bar − Betriebsreserve (harte Grenze, Mode H); Information: 4,0 bar ohne Reserve
    hys, cfgs = {}, {}
    for key, grenze in (("MILP_H_MVA_IST_KWK4BAR_OHNE_RESERVE", KWK_ERFAHRUNGSWERT_BAR), ("MILP_H_MVA_IST_KWKGRENZE", kwk_grenze)):
        cfg4 = C.merge(cfg, {"hydraulics": {"kwk_experience_value_hard": True, "soft_limits_bar": {"KWK": float(grenze)}}})
        hys[key], cfgs[key] = Hydro(cfg4, x, cfg["hydraulics"]["reference_variant"]), cfg4
        s4, i4, _ev4, it4, cuts4 = coupling.mode_h(cfg4, xb, s, milp.Flags(False, False, False), hys[key], sm, im, log=log)
        log(f"{key}: {i4['objective']:.0f} EUR, konvergiert {i4['converged']}, {i4['n_cuts']} Schnitte")
        info_extra[key] = {"grenze_bar": float(grenze), "kosten_EUR": i4["objective"], "iterationen": int(i4["iterations"]),
                           "schnitte": int(i4["n_cuts"]), "konvergiert": bool(i4["converged"]),
                           "verletzungen_je_iteration": it4["violations"].tolist()}
    plaene["MILP_H_MVA_IST_KWKGRENZE"], infos["MILP_H_MVA_IST_KWKGRENZE"] = s4, i4
    hy4, cfg4 = hys["MILP_H_MVA_IST_KWKGRENZE"], cfgs["MILP_H_MVA_IST_KWKGRENZE"]
    plaene["REGEL"] = regel(xb, cfg)
    ungedeckt = plaene["REGEL"].attrs["ungedeckt_MW"]
    log(f"REGEL: ungedeckt {np.sum(ungedeckt):.1f} MWh in {int((ungedeckt > 1e-6).sum())} h")

    # Mindestlasten: P5 der IST-Last in Betriebsstunden (> 1 MW) und Vorschlag in % der Kapazität
    minlast = {g: float(np.round(plaene["IST"][f"Q_{g}"][plaene["IST"][f"Q_{g}"] > ON_MW].quantile(0.05), 1)) for g in UC_PLANTS}
    minlast_p = {g: MINLAST_ANTEIL_VORSCHLAG[g] * cfg["plants"][g]["cap_MW"] for g in UC_PLANTS}
    u0 = {g: bool(plaene["IST"][f"Q_{g}"].iloc[0] > ON_MW) for g in UC_PLANTS}
    uc_infos = {}
    if a.uc_wiederverwenden:
        uc_infos = json.loads((out / "uc_info.json").read_text(encoding="utf-8"))
        for key, iu in uc_infos.items():
            plaene[key], infos[key] = pd.read_parquet(out / f"fahrplan_{key}.parquet"), iu
            log(f"{key}: aus Datei, {iu['objective']:.0f} EUR, gap {iu['gap']:.2e}")
    elif not a.skip_uc:
        # Fairness 3: Mindestlasten + Anfahrkosten, mit MVA wie gemessen und den KWK-Grenz-Schnitten aus Fairness 2
        cfg_uc = C.merge(cfg, {"solver": {"mip_rel_gap": a.uc_gap, "time_limit_s": a.uc_time_limit}})
        for var in a.uc_sets:
            ml = minlast if var == "ist" else minlast_p
            t = time.time()
            su, iu = milp_uc_h(xb, s, cfg_uc, cfg4, hy4, ml, ANFAHRKOSTEN_EUR, u0, schnitte(cuts4), log=log)
            key = "MILP_UC" if var == "ist" else "MILP_UC_PROZENT"
            ev_uc4 = hy4.evaluate(coupling._sched_cols(su))
            plaene[key], infos[key] = su, iu
            uc_infos[key] = {"mindestlast_MW": ml, **iu, "dauer_s": time.time() - t,
                             "verletzungen_mit_kwk_grenze_h": int(ev_uc4["violation"].sum())}
            d = su.copy()
            d.attrs = {}
            d.to_parquet(out / f"fahrplan_{key}.parquet")                  # sofort sichern (lange Läufe)
            (out / "uc_info.json").write_text(json.dumps(uc_infos, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
            log(f"{key}: {iu['objective']:.0f} EUR, gap {iu['gap']:.2e}, {iu['status']}, {iu['runtime_s']:.0f} s, "
                f"Notkühlung {iu['notkuehlung_MWh']:.0f} MWh, KWK-Grenzprüfung: {int(ev_uc4['violation'].sum())} h verletzt")

    # Bewertung
    ks = {fp: kosten(sc, x, cfg) for fp, sc in plaene.items()}
    evs = {fp: hydraulik(hy, sc) for fp, sc in plaene.items()}
    ref = ks["IST"]["gesamt"].sum()
    ref_a = ref + ks["IST"]["anfahrkosten"].sum()
    kz_rows = [kennzahlen(fp, plaene[fp], ks[fp], evs[fp], x, cfg, minlast, minlast_p, None if fp == "IST" else (ref, ref_a))
               for fp in plaene]
    kz = pd.DataFrame(kz_rows)
    kz[f"Stunden KWK-Δp > Modellgrenze {kwk_grenze:.2f} bar (4,0 bar − Betriebsreserve) [h]"] = [
        int((evs[fp]["dp_KWK"] > kwk_grenze + 0.01).sum()) for fp in plaene]
    kz_ist = kz["Fahrplan"] == "IST"
    kz.loc[kz_ist, "KWK-Δp gemessen Mittel [bar]"] = float(dp_mess.mean())
    kz.loc[kz_ist, "KWK-Δp gemessen P95 [bar]"] = float(dp_mess.quantile(0.95))
    kz.loc[kz_ist, "KWK-Δp gemessen Max [bar]"] = float(dp_mess.max())
    kz.loc[kz_ist, "Stunden KWK-Δp gemessen > 4,0 bar [h]"] = int((dp_mess > 4.0).sum())
    for fp, inf in infos.items():
        sel = kz["Fahrplan"] == fp
        kz.loc[sel, "MILP-Zielfunktion [M€/a]"] = inf["objective"] / 1e6
        kz.loc[sel, "MILP-Gap [-]"] = inf["gap"]
    # MILP-Zielfunktion = eigene Bewertung (gleiche Kostenfunktion)
    for fp in ("MILP_E", "MILP_H", "MILP_E_MVA_IST", "MILP_H_MVA_IST_KWKGRENZE"):
        assert abs(ks[fp]["gesamt"].sum() - infos[fp]["objective"]) < 1.0, f"Bewertung {fp} ≠ MILP-Zielfunktion"
    for fp in uc_infos:                     # UC: Zielfunktion = Betrieb + Anfahrkosten + Notkühlungsstrafe
        k = ks[fp]
        c = k["gesamt"].sum() + k["anfahrkosten"].sum() + k["notkuehlung_strafe"].sum()
        assert abs(c - infos[fp]["objective"]) < 1e-6 * infos[fp]["objective"], f"Bewertung {fp} ≠ MILP-Zielfunktion"
    kz_long = kz.set_index("Fahrplan").T
    kz_long.index.name = "Kennzahl"
    kz_long.to_csv(out / "kennzahlen.csv", encoding="utf-8")

    # Zerlegung und Differenzen
    vergleiche = [("IST", "MILP_H"), ("IST", "MILP_E"), ("IST", "MILP_E_MVA_IST"), ("IST", "MILP_H_MVA_IST_KWKGRENZE"),
                  ("IST", "REGEL"), ("REGEL", "MILP_E_MVA_IST")]
    vergleiche += [("IST", k) for k in plaene if k.startswith("MILP_UC")]
    wf, mon, pk = [], [], []
    for a_, b_ in vergleiche:
        lbl = f"{a_} → {b_}"
        z = zerlegung(plaene[a_], plaene[b_], ks[a_], ks[b_]).assign(Vergleich=lbl)
        wf.append(z)
        mo, pr = differenzen(ks[a_], ks[b_], x)
        mon.append(mo.assign(Vergleich=lbl))
        pk.append(pr.assign(Vergleich=lbl))
    wf = pd.concat(wf)[["Vergleich", "Schritt", "Wert [M€/a]"]]
    wf.to_csv(out / "wasserfall.csv", index=False, encoding="utf-8")
    mon = pd.concat(mon).pivot(index="Monat", columns="Vergleich", values="Differenz [k€]").reset_index()
    mon.to_csv(out / "differenz_monat.csv", index=False, encoding="utf-8")
    pk = pd.concat(pk)
    pk_w = pk.pivot(index="Preisklasse [€/MWh]", columns="Vergleich", values="Differenz [k€]")
    pk_w.insert(0, "Stunden", pk.drop_duplicates("Preisklasse [€/MWh]").set_index("Preisklasse [€/MWh]")["Stunden"])
    pk_w = pk_w.reindex([p[2] for p in PREISKLASSEN]).reset_index()
    pk_w.to_csv(out / "differenz_preisklasse.csv", index=False, encoding="utf-8")

    # Fairness-Treppe
    treppe = [("IST", "IST (gemessen)"), ("MILP_H", "MILP F000 Mode H (Studie)"),
              ("MILP_E_MVA_IST", "+ MVA fest wie gemessen"),
              ("MILP_H_MVA_IST_KWKGRENZE", "+ KWK-Δp ≤ 4,0 bar inkl. Betriebsreserve (Mode H)"),
              ("MILP_UC", "+ Mindestlasten (P5 IST) und Anfahrkosten"),
              ("MILP_UC_PROZENT", "alternativ: Mindestlasten 30/50/10 % und Anfahrkosten")]
    tr, vor = [], None
    vorteil0 = ref - ks["MILP_H"]["gesamt"].sum()
    for key, lbl in treppe:
        if key not in ks:
            continue
        c = ks[key]["gesamt"].sum()
        ca = c + ks[key]["anfahrkosten"].sum()
        if key == "MILP_UC_PROZENT":                        # Alternative zur UC-Stufe, nicht deren Nachfolger
            vor = ks["MILP_H_MVA_IST_KWKGRENZE"]["gesamt"].sum()
        tr.append({"Stufe": lbl, "Fahrplan": key, "Kosten [M€/a]": c / 1e6, "Differenz zu IST [M€/a]": (c - ref) / 1e6,
                   "Änderung zur Vorstufe [M€/a]": (c - vor) / 1e6 if vor is not None else np.nan,
                   "Verbleibender Vorteil gegenüber IST [% des Studien-MILP]": 100 * (ref - c) / vorteil0 if key != "IST" else np.nan,
                   "Anfahrkosten bewertet [M€/a]": ks[key]["anfahrkosten"].sum() / 1e6,
                   "Kosten inkl. Anfahrkosten [M€/a]": ca / 1e6, "Differenz zu IST inkl. Anfahrkosten [M€/a]": (ca - ref_a) / 1e6})
        vor = c
    pd.DataFrame(tr).to_csv(out / "fairness.csv", index=False, encoding="utf-8")

    # Folien-Daten
    wo = wochen(x)
    rows = []
    for name, t0 in wo.items():
        sl = slice(t0, t0 + pd.Timedelta(hours=167))
        d = pd.DataFrame({"Woche": name, "Zeit": x.loc[sl].index, "Last [MW]": x.loc[sl, "D"].to_numpy(),
                          "Day-Ahead-Preis [€/MWh]": x.loc[sl, "price"].to_numpy()})
        for fp in [f for f in ("IST", "MILP_H", "MILP_UC") if f in plaene]:
            for g in MERIT_ORDER:
                d[f"{fp} {g} [MW]"] = plaene[fp].loc[sl, f"Q_{g}"].to_numpy()
        rows.append(d)
    pd.concat(rows).to_csv(out / "wochen.csv", index=False, encoding="utf-8")
    dl = pd.DataFrame({"Rang [h]": np.arange(1, len(x) + 1)})
    for g in EXISTING:
        for fp in plaene:
            dl[f"{fp} {g} [MW]"] = np.sort(plaene[fp][f"Q_{g}"].to_numpy())[::-1]
    dl.to_csv(out / "dauerlinien.csv", index=False, encoding="utf-8")
    dp = pd.DataFrame({"Zeit": x.index, "IST gemessen [bar]": dp_mess.to_numpy()})
    for fp in plaene:
        dp[f"{'IST modelliert' if fp == 'IST' else fp} [bar]"] = evs[fp]["dp_KWK"].to_numpy()
    dp.to_csv(out / "dp_kwk.csv", index=False, encoding="utf-8")

    # Prüfungen IST und Zusatzinformationen
    bil = bilanzpruefung(plaene["IST"], x)
    gr = grenzpruefung(plaene["IST"], x, cfg)
    gr.to_csv(out / "ist_grenzpruefung.csv", index=False, encoding="utf-8")
    res = evs["IST"]["dp_KWK"].to_numpy()[ok] - dp_mess.to_numpy()[ok]
    meta = {"bilanzpruefung": bil, "mva_ausfallstunden": int(ausfall.sum()),
            "mva_ausfall_je_monat": {int(k): int(v) for k, v in ausfall.groupby(x.index.month).sum().items() if v},
            "mva_milp_e_in_ausfallstunden_GWh": float(plaene["MILP_E"].loc[ausfall.to_numpy(), "Q_MVA"].sum() / 1e3),
            "regel_ungedeckt_MWh": float(np.sum(ungedeckt)), "regel_ungedeckt_h": int((ungedeckt > 1e-6).sum()),
            "mindestlast_ist_p5_MW": minlast, "mindestlast_vorschlag_MW": minlast_p, "anfahrkosten_EUR": ANFAHRKOSTEN_EUR,
            "uc": uc_infos, "solver": {k: {kk: v.get(kk) for kk in ("status", "objective", "bound", "gap", "runtime_s")} for k, v in infos.items()},
            "mode_h": {"iterationen": int(ih["iterations"]), "verletzungen_je_iteration": it_h["violations"].tolist(), "schnitte": int(ih["n_cuts"]), "konvergiert": bool(ih["converged"]),
                       "dC_hyd_EUR": float(ih["objective"] - info_e["objective"])},
            "varianten_information": info_extra, "kwk_betriebsreserve_bar": reserve, "kwk_grenze_modell_bar": kwk_grenze,
            "mva_milp_e_GWh_ueber_ist": float((plaene["MILP_E"]["Q_MVA"].sum() - plaene["IST"]["Q_MVA"].sum()) / 1e3),
            "kwk_dp_ist_modell_vs_messung": {"bias_bar": float(res.mean()), "rmse_bar": float(np.sqrt((res**2).mean())),
                                             "r": float(np.corrcoef(evs["IST"]["dp_KWK"].to_numpy()[ok], dp_mess.to_numpy()[ok])[0, 1])},
            "wochen": {k: str(v) for k, v in wo.items()},
            "strompreis": {"mittel": float(x["price"].mean()), "stunden_negativ": int((x["price"] < 0).sum())},
            "laufzeit_s": time.time() - t_start}
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    abbildungen(out / "png", x, plaene, wo, wf, kz)
    for fp, sc in plaene.items():
        d = sc[[c for c in sc if c in [f"Q_{g}" for g in EXISTING] or (fp in uc_infos)]].copy()
        d.attrs = {}
        d.to_parquet(out / f"fahrplan_{fp}.parquet")
    log(f"fertig in {time.time() - t_start:.0f} s -> {out}")
    return {"kennzahlen": kz, "wasserfall": wf, "monat": mon, "preisklasse": pk_w, "meta": meta, "grenzen": gr}


if __name__ == "__main__":
    main()
