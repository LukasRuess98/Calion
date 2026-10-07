"""Strukturell unabhängige Gegenrechnung des Ersatznetzes mit pandapipes (Plan 2.7).

pandapipes rechnet das Netz als **geschlossenen Kreis**:
* Vor- und Rücklauf sind getrennte Rohrnetze, je mit eigener Temperatur (120 °C bzw. 60 °C) und damit eigener Dichte,
  Viskosität und Reibungszahl. Die Kreisströme im Vor- und Rücklauf werden getrennt gelöst; das Ersatznetz nimmt sie
  dagegen als Spiegelbild an.
* Die KWK ist eine Umwälzpumpe mit Druckhaltung (Rücklaufdruck fest, Förderhöhe = KWK-Δp).
* Ost-Erzeuger und HW1 sind massenstromgeführt (Quelle im Vorlauf, Senke im Rücklauf), die Verbraucher und die Übergabe
  West umgekehrt. PS1 und PS2 sind Pumpen mit flacher Kennlinie (Förderhöhe = gemessener Gewinn).
* Jede Kante wird zu zwei Rohren mit Plan-Durchmesser. Ihre Länge ist so gewählt, dass Vor- plus Rücklauf beim
  Bezugsdurchfluss (Median der Hochlaststunden) den kalibrierten Widerstand K treffen. Der KWK-interne Verlust ist ein
  Formverlust (ζ).

Zwei Reibungsansätze:
* ``nikuradse``: Reibungszahl unabhängig vom Durchfluss, also wie das Ersatznetz quadratisch. Diese Rechnung prüft
  Löser, Massenbilanz, Pumpen und die Annahme gespiegelter Rücklaufströme (Kriterium Plan 2.7: ≤ 0,05 bar).
* ``swamee-jain``: Reibungszahl hängt von der Reynoldszahl ab (explizite Näherung der Colebrook-Gleichung, Abweichung
  1–2 %; die Colebrook-Iteration von pandapipes konvergiert in diesem vermaschten Netz nicht zuverlässig). Diese Rechnung
  zeigt, wie stark die quadratische Annahme die Extrapolation auf den Auslegungsfall beeinflusst.

Aufruf (benötigt ``pip install pandapipes``):  ``python -m scripts.dhn_study.gegenrechnung_pandapipes``
Kalibrierung: die des letzten Laufs von ``python -m scripts.dhn_study.run_netzmodell``, sonst die veröffentlichte
Referenzkalibrierung (``scripts/dhn_study/kalibrierung/``).
Ergebnisse: ``results/dhn_study/netzmodell/pandapipes_*.csv`` und ``pandapipes_zusammenfassung.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import daten
from . import netzmodell as nm

T_VL_K, T_RL_K = 393.15, 333.15
P_RUHE_BAR = 6.0                 # Druckhaltung (Rücklauf am KWK); für die Δp ohne Belang
K_MM = 0.1                       # Rauigkeit
D_KWK_MM = 700.0                 # Ersatzdurchmesser des KWK-internen Formverlusts
PUMPEN_KANTEN = ("L4c", "W1")    # PS1, PS2: Gewinn am Kantenanfang


def _pp():
    try:
        import pandapipes
    except ImportError as err:  # pragma: no cover - optionale Abhängigkeit
        raise ImportError("Die Gegenrechnung benötigt pandapipes: pip install pandapipes") from err
    return pandapipes


def reibungszahl(re: np.ndarray, d_m: float, k_mm: float, modell: str) -> np.ndarray:
    """Darcy-Reibungszahl wie in pandapipes: Nikuradse (+ 64/Re) bzw. Swamee-Jain."""
    re = np.maximum(np.asarray(re, dtype=float), 1.0)
    k = k_mm / 1000
    if modell == "nikuradse":
        return 64 / re + 1 / (-2 * np.log10(k / (3.71 * d_m))) ** 2
    return 0.25 / np.log10(k / (3.7 * d_m) + 5.74 / re**0.9) ** 2


@dataclass
class PPNetz:
    net: object
    j_vl: dict
    j_rl: dict
    rohr_vl: dict
    rohr_rl: dict
    pumpe: dict
    mengen: dict                 # (Tabelle, Index) je Knoten: Einspeisung/Entnahme im Vor- und Rücklauf
    modell: str


def baue_netz(nz: nm.Netz, K: np.ndarray, m_ref: np.ndarray, modell: str = "swamee-jain", k_mm: float = K_MM) -> PPNetz:
    """pandapipes-Netz (geschlossener Kreis) mit Rohren, deren Vor- plus Rücklaufverlust beim Bezugsdurchfluss
    ``m_ref`` [kg/s] je Kante dem kalibrierten Widerstand ``K`` entspricht."""
    pp = _pp()
    net = pp.create_empty_network(fluid="water")
    fl = pp.get_fluid(net)
    rho = dict(zip(("VL", "RL"), fl.get_density(np.array([T_VL_K, T_RL_K])), strict=True))
    eta = dict(zip(("VL", "RL"), fl.get_viscosity(np.array([T_VL_K, T_RL_K])), strict=True))
    j_vl = {n: pp.create_junction(net, 10.0, T_VL_K, name=f"{n}_VL") for n in nz.knoten}
    j_rl = {n: pp.create_junction(net, P_RUHE_BAR, T_RL_K, name=f"{n}_RL") for n in nz.knoten}
    pp.create_circ_pump_const_pressure(net, j_rl[nz.wurzel], j_vl[nz.wurzel], p_flow_bar=P_RUHE_BAR + 3.0, plift_bar=3.0,
                                       t_flow_k=T_VL_K)
    rohr_vl, rohr_rl, pumpe = {}, {}, {}
    for j, (kid, a, b, dn, _laenge) in enumerate(nz.kanten):
        d = (dn or D_KWK_MM) / 1000
        A = np.pi * d**2 / 4
        start = j_vl[a]
        if kid in PUMPEN_KANTEN:
            druck = pp.create_junction(net, 10.0, T_VL_K, name=f"{kid}_Druckseite")
            pp.create_pump_from_parameters(net, j_vl[a], druck, f"flach_{kid}", pressure_list=[0.01, 0.01, 0.01],
                                           flowrate_list=[0.0, 1000.0, 5000.0], reg_polynomial_degree=1)
            pumpe[kid] = net.pump.index[-1]
            start = druck
        if dn is None:
            # Formverlust: Δp = ζ·ṁ²/(2ρA²) je Seite
            zeta = 2 * A**2 * K[j] * 1e5 / (1 / rho["VL"] + 1 / rho["RL"])
            kw = {"length_km": 1e-3, "k_mm": 1e-6, "loss_coefficient": zeta}
        else:
            m = max(abs(float(m_ref[j])), 1.0)
            lam = {s: float(reibungszahl(m * d / (eta[s] * A), d, k_mm, modell)) for s in ("VL", "RL")}
            laenge = K[j] * 1e5 * 2 * d * A**2 / (lam["VL"] / rho["VL"] + lam["RL"] / rho["RL"])
            kw = {"length_km": max(laenge, 1e-3) / 1000, "k_mm": k_mm}
        rohr_vl[kid] = pp.create_pipe_from_parameters(net, start, j_vl[b], inner_diameter_mm=d * 1000, name=f"{kid}_VL", **kw)
        rohr_rl[kid] = pp.create_pipe_from_parameters(net, j_rl[b], j_rl[a], inner_diameter_mm=d * 1000, name=f"{kid}_RL", **kw)
    mengen = {n: (pp.create_source(net, j_vl[n], 0.0), pp.create_sink(net, j_vl[n], 0.0),
                  pp.create_source(net, j_rl[n], 0.0), pp.create_sink(net, j_rl[n], 0.0))
              for n in nz.knoten if n != nz.wurzel}
    return PPNetz(net, j_vl, j_rl, rohr_vl, rohr_rl, pumpe, mengen, modell)


def rechne(nz: nm.Netz, ppn: PPNetz, b: np.ndarray, gewinn: np.ndarray, dp_kwk: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Eine Stunde: Δp (VL − RL) je Knoten [bar], Kantenströme Vorlauf und Rücklauf [kg/s] (Richtung wie im Ersatznetz).
    Gewinne ≤ 0,01 bar (Bypass) werden auf 0,01 bar Förderhöhe gesetzt; die Differenz zum Sollgewinn wird danach exakt
    korrigiert (beide Pumpenkanten liegen außerhalb von Maschen). Konvergiert die Rechnung nicht, ist das Ergebnis NaN."""
    pp = _pp()
    from pandapipes.std_types.std_type_class import PumpStdType

    net = ppn.net
    for n, (q_vl, s_vl, q_rl, s_rl) in ppn.mengen.items():
        v = float(b[nz.idx[n]])
        net.source.at[q_vl, "mdot_kg_per_s"] = max(v, 0.0)
        net.sink.at[s_vl, "mdot_kg_per_s"] = max(-v, 0.0)
        net.source.at[q_rl, "mdot_kg_per_s"] = max(-v, 0.0)
        net.sink.at[s_rl, "mdot_kg_per_s"] = max(v, 0.0)
    net.circ_pump_pressure["plift_bar"] = dp_kwk
    net.circ_pump_pressure["p_flow_bar"] = P_RUHE_BAR + dp_kwk
    for kid, pid in ppn.pumpe.items():
        hub = max(float(gewinn[nz.kanten_ids.index(kid)]), 0.01)
        name = f"flach_{kid}_{hub:.3f}"
        if name not in net.std_types["pump"]:
            pp.create_pump_std_type(net, name, PumpStdType(name, [0.0, hub]))
        net.pump.loc[pid, "std_type"] = name
    try:
        pp.pipeflow(net, mode="hydraulics", friction_model=ppn.modell, max_iter_hyd=100, tol_p=1e-7, tol_m=1e-7)
    except Exception:  # nicht konvergiert: einmal mit lockerer Toleranz, sonst NaN
        try:
            pp.pipeflow(net, mode="hydraulics", friction_model=ppn.modell, max_iter_hyd=300, tol_p=1e-5, tol_m=1e-5)
        except Exception:
            nan = np.full(len(nz.kanten), np.nan)
            return np.full(len(nz.knoten), np.nan), nan, nan
    # Korrektur auf den Sollgewinn: tatsächlich wirksame Förderhöhe (bei Rückströmung umgeht pandapipes die Pumpe)
    korrektur = np.zeros(len(nz.knoten))
    for kid, pid in ppn.pumpe.items():
        j = nz.kanten_ids.index(kid)
        korrektur += (float(gewinn[j]) - float(net.res_pump.deltap_bar[pid])) * np.clip(nz.P[:, j], 0, None)
    p = net.res_junction.p_bar
    dp = np.array([p[ppn.j_vl[n]] - p[ppn.j_rl[n]] for n in nz.knoten]) + korrektur
    m_vl = np.array([net.res_pipe.mdot_from_kg_per_s[ppn.rohr_vl[k]] for k in nz.kanten_ids])
    m_rl = np.array([net.res_pipe.mdot_from_kg_per_s[ppn.rohr_rl[k]] for k in nz.kanten_ids])
    return dp, m_vl, m_rl


def main() -> dict:
    from .run_netzmodell import (
        SPEICHER_MW,
        aufteilung,
        auslegung_eingaben,
        kalibrierung_ordner,
        lade_kalibrierung,
    )

    out = daten.repo_root() / "results" / "dhn_study" / "netzmodell"
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    kal = lade_kalibrierung(kalibrierung_ordner(out), nz)
    K, gw, gl, vs = kal["K"], kal["gewichte"], kal["grundlast"], kal["versatz"].to_dict()
    hold, _ = aufteilung(f, ta)
    b_all = f.b(nz, gw, gl)
    m_mod = nz.loese(b_all, K, f.gewinn)
    dp_mod = nz.dp_knoten(m_mod, K, f.dp_kwk, f.gewinn)
    last = e["verbund"].reindex(f.index).to_numpy()
    hoch = hold & (last >= np.nanquantile(last[hold], 0.9))
    m_ref = np.median(np.abs(m_mod[hoch]), axis=0)

    # 1) Holdout-Stunden: alle Hochlaststunden und eine Stichprobe über alle Lasten. Nur Stunden, in denen die KWK
    # fördert (≥ 10 kg/s): Eine Umwälzpumpe kann ihre Richtung nicht umkehren.
    rng = np.random.default_rng(1)
    kwk_an = m_mod[:, 0] >= 10.0
    rest = np.flatnonzero(hold & ~hoch & kwk_an)
    stunden = np.sort(np.concatenate([np.flatnonzero(hoch & kwk_an), rng.choice(rest, size=min(300, len(rest)), replace=False)]))
    erg = {}
    zeilen = []
    for modell in ("nikuradse", "swamee-jain"):
        ppn = baue_netz(nz, K, m_ref, modell)
        for i in stunden:
            dp, m_vl, m_rl = rechne(nz, ppn, b_all[i], f.gewinn[i], float(f.dp_kwk[i]))
            zeilen.append({"Reibung": modell, "Stunde": f.index[i], "Hochlast": bool(hoch[i]), "Last [MW]": last[i],
                           "KWK-Fluss [kg/s]": m_mod[i, 0],
                           **{f"dDp {n}": dp[k] - dp_mod[i, k] for k, n in enumerate(nz.knoten)},
                           "max |dDp| [bar]": float(np.max(np.abs(dp - dp_mod[i]))),
                           "max |dm| VL [kg/s]": float(np.max(np.abs(m_vl - m_mod[i]))),
                           "max |dm| RL [kg/s]": float(np.max(np.abs(m_rl - m_mod[i]))),
                           "max |VL − RL| [kg/s]": float(np.max(np.abs(m_vl - m_rl)))})
    v = pd.DataFrame(zeilen)
    v.to_csv(out / "pandapipes_vergleich_stunden.csv", index=False)
    kw = pd.cut(v["KWK-Fluss [kg/s]"], [-1, 180, 240, 1000], labels=["< 180 kg/s", "180–240 kg/s", "> 240 kg/s"])
    knoten_z = [f"dDp {nm.STATIONEN[s]}" for s in ("V03", "V06", "V22", "V15")]
    erg["vergleich"] = v.groupby(["Reibung", kw], observed=True).agg(
        Stunden=("Stunde", "size"), nicht_konvergiert=("max |dDp| [bar]", lambda x: int(x.isna().sum())),
        max_dDp=("max |dDp| [bar]", "max"), P95_dDp=("max |dDp| [bar]", lambda x: x.quantile(0.95)),
        **{f"Mittel {k[4:]}": (k, "mean") for k in knoten_z},
        max_dm_VL=("max |dm| VL [kg/s]", "max"), max_VL_RL=("max |VL − RL| [kg/s]", "max"))
    erg["vergleich"].to_csv(out / "pandapipes_vergleich.csv")

    # 2) Auslegungsfall mit denselben Randbedingungen wie run_netzmodell (Ost nach Plan A und wie 2025)
    ae = auslegung_eingaben(m, e, ta, nz)
    dh, gewinn, mindest, hw1_mw, hw1_m = ae["dh"], ae["gewinn"][0], ae["mindest"], ae["hw1_mw"], ae["hw1_m"]
    netze = {"Ersatznetz": None, **{f"pandapipes {mo}": baue_netz(nz, K, m_ref, mo) for mo in ("nikuradse", "swamee-jain")}}

    def erf(ppn, P, west, ost_v, speicher=None):
        b = nm.auslegungs_einspeisung(nz, P, dh, ost_v, hw1_mw, hw1_m, west, speicher, gw, gl)[0]
        if ppn is None:
            dp = nz.dp_knoten(nz.loese(b[None], K, gewinn[None]), K, np.array([4.0]), gewinn[None])[0]
        else:
            dp, *_ = rechne(nz, ppn, b, gewinn, 4.0)
            if not np.isfinite(dp).all():
                raise RuntimeError(f"pandapipes konvergiert im Auslegungsfall nicht (P = {P:.1f} MW, {ppn.modell})")
        need = {z: mindest[z] - (dp[nz.idx[nm.STATIONEN[z]]] - 4.0) - vs.get(z, 0.0) for z in mindest}
        return max(need.values()), max(need, key=need.get)

    def reserve(ppn, P, west, ost_v, grenze=4.0):
        lo, hi = 0.8, 1.4
        for _ in range(25):
            mid = 0.5 * (lo + hi)
            (lo, hi) = (mid, hi) if erf(ppn, P * mid, west, ost_v)[0] < grenze else (lo, mid)
        return lo - 1.0

    zeilen = []
    for var, ost_v in ae["ost"].items():
        for fall, (P, west) in ae["faelle"].items():
            for name, ppn in netze.items():
                req, bind = erf(ppn, P, west, ost_v)
                zeilen.append({"Ost": var, "Fall": fall, "Rechnung": name, "erf. KWK-Δp [bar]": req, "maßgebend": bind,
                               "Reserve bis 4,0 bar": reserve(ppn, P, west, ost_v),
                               "Entlastung Speicher S [bar]": req - erf(ppn, P, west, ost_v, {"S": SPEICHER_MW})[0],
                               "Entlastung Speicher Südende [bar]": req - erf(ppn, P, west, ost_v, {"SUED_E": SPEICHER_MW})[0]})
    erg["auslegung"] = pd.DataFrame(zeilen).set_index(["Ost", "Fall", "Rechnung"])
    erg["auslegung"].to_csv(out / "pandapipes_auslegung.csv")
    from .run_analyse import _md
    text = ["# pandapipes-Gegenrechnung (automatisch erzeugt)", "",
            f"Stunden: {len(stunden)} (Holdout; davon {int(hoch[stunden].sum())} Hochlast); Bezugsdurchfluss = Median "
            f"der Hochlaststunden; Rauigkeit {K_MM} mm.", "",
            "## Abweichung pandapipes − Ersatznetz (Δp in bar, Ströme in kg/s)", _md(erg["vergleich"].round(3)), "",
            "## Auslegungsfall", _md(erg["auslegung"].round(3))]
    (out / "pandapipes_zusammenfassung.md").write_text("\n".join(text), encoding="utf-8")
    return erg


if __name__ == "__main__":
    main()
