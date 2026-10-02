"""Hydraulisches Ersatznetz DHN-A (Verbund, Sektionsebene) mit Kalibrierung an den Messwerten 2025.

Modellstruktur (Plan, Phase 2):
* **ein Druckhalter:** Die KWK ist Bilanzknoten (Slack); ihre Δp ist Randbedingung (Messwert bzw. gesuchte Größe).
* **Massenbilanz je Erzeuger:** Ost-Erzeuger, HW1 und die Übergabe zum Westnetz speisen gemessene Massenströme ein
  bzw. aus; ihre Δp ist Modellergebnis (damit ist die Ost-Kopplung Validierungsziel, nicht Eingabe).
* **Vor- und Rücklauf gekoppelt:** Jeder Verbraucher entnimmt im Vorlauf so viel, wie er in den Rücklauf zurückgibt.
  Die Rücklaufströme sind deshalb das Spiegelbild der Vorlaufströme; ein Kantenwiderstand K beschreibt den Δp-Verlust
  von Vor- plus Rücklauf: Δp_nach = Δp_von − K·ṁ·|ṁ| + Pumpengewinn. Geländehöhen kürzen sich in der Δp heraus.
* **Vermaschung:** Kreisströme werden mit dem Newton-Verfahren auf den Maschenströmen gelöst (stundenweise vektorisiert).

Die Topologie stammt aus den Betreiberplänen (anonymisiert, ohne Geografie); Längen und Durchmesser sind Schätzwerte
und dienen nur als Startwert. Die Widerstände werden kalibriert (``kalibriere``), Lastverteilung aus ``sectors.csv``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from . import daten, hydraulik

# Knoten: id -> Region (für die Darstellung)
KNOTEN = {
    "KWK": "Erzeuger", "SS": "Erzeuger", "K1": "L1", "S": "Ost-L5", "L5M": "Ost-L5", "K2": "Ost-L5", "L5O": "Ost-L5", "MVA": "Erzeuger",
    "GT": "Erzeuger", "BIO": "Erzeuger", "L6": "Ost-L6", "K3": "Mitte-L3", "L7": "Ost-L7", "K4": "Mitte-L3", "L1G": "L1",
    "SEC2": "City/Mitte-L2", "SEC3": "Mitte-L3", "SEC4": "Mitte-L4", "PS1": "Süd", "SUED_N": "Süd", "HW1": "Erzeuger",
    "SUED_S": "Süd", "SUED_E": "Süd", "PS2": "L1", "HW2": "West-WÜ",
}
# Kanten: id, von, nach, DN [mm], Länge [m] (Schätzwerte, nur Startwert der Kalibrierung). "KWKi" ist der anlageninterne
# Verlust der KWK zwischen Messstelle (Pumpe) und Sammelschiene; Startwert aus Plan A (1,1 bar bei 2 350 t/h).
KANTEN = [
    ("KWKi", "KWK", "SS", None, None), ("L1a", "SS", "K1", 400, 854), ("L5a", "K1", "S", 400, 394), ("L5b", "S", "L5M", 400, 2285),
    ("L5c", "L5M", "K2", 400, 258), ("L5d", "K2", "L5O", 400, 1800), ("L5e", "L5O", "MVA", 350, 870),
    ("L5f", "L5O", "GT", 350, 60), ("L5g", "L5O", "BIO", 250, 60), ("L6a", "K2", "L6", 350, 1500),
    ("L6b", "L6", "K3", 350, 1500), ("L6c", "K2", "GT", 350, 3000), ("L7a", "K4", "L7", 250, 2500),
    ("L7b", "L7", "GT", 250, 3500), ("L2", "SS", "SEC2", 350, 600), ("L3", "SS", "SEC3", 350, 800),
    ("L4a", "SS", "SEC4", 400, 1200), ("L4b", "SEC4", "PS1", 400, 3270), ("L4c", "PS1", "SUED_N", 400, 610),
    ("L4d", "SUED_N", "HW1", 350, 900), ("L4e", "HW1", "SUED_S", 350, 800), ("L4f", "SUED_S", "SUED_E", 250, 1500),
    ("L1b", "K1", "L1G", 350, 1400), ("L1c", "L1G", "PS2", 350, 1400), ("W1", "PS2", "HW2", 350, 960),
    ("M12", "L1G", "SEC2", 350, 700), ("M23", "SEC2", "SEC3", 200, 600), ("M24", "SEC2", "SEC4", 200, 800),
    ("M34", "SEC3", "SEC4", 250, 700), ("K63", "K3", "SEC3", 350, 300), ("K73", "K4", "SEC3", 250, 600),
]
# Teilgebiete (sectors.csv) -> Lastknoten
SEKTOR_KNOTEN = {"L1-": "L1G", "L5-W": "S", "L5-M": "L5M", "L5-O": "L5O", "M2-": "SEC2", "City-": "SEC2", "M3-": "SEC3",
                 "L6-": "L6", "L7-": "L7", "L4-": "SEC4", "M4-": "SEC4", "Sued-01": "SUED_N", "Sued-02": "SUED_N",
                 "Sued-03": "SUED_N", "Sued-08": "SUED_N", "Sued-10": "SUED_N", "Sued-04": "SUED_S", "Sued-07": "SUED_S",
                 "Sued-05": "SUED_E", "Sued-06": "SUED_E", "Sued-09": "SUED_E"}
# Messstationen (Δp) -> Knoten
STATIONEN = {"V22": "S", "V11": "L5M", "V08": "K2", "V18": "L5O", "V07": "L7", "V15": "K3", "V19": "SEC3", "V03": "SEC2",
             "V10": "SEC2", "V24": "SEC2", "V12": "SEC4", "V23": "L1G", "V06": "SUED_E"}
# gemessener Großkunde (ein Kunde = ganzes Teilgebiet L5-W): Entnahme direkt aus dem Durchfluss (t/h)
GROSSKUNDE = ("V22", "S")
# Lastgruppen mit kalibrierbarem Gewicht (die Anschlussanteile innerhalb einer Gruppe bleiben fest)
LASTGRUPPEN = {"SEC2": ["SEC2"], "SEC3": ["SEC3"], "SEC4": ["SEC4"], "Süd": ["SUED_N", "SUED_S", "SUED_E"],
               "Ost": ["L5M", "L5O", "L6", "L7"], "L1": ["L1G"]}
PUMPEN = {"L4c": "pump_station_1", "W1": "pump_station_2"}     # Pumpengewinn am Kantenanfang
STAMMLEITUNGEN = {"L1a": 1, "L2": 2, "L3": 3, "L4a": 4}          # gas_CHP_flow_line_k
MITTE_ZIELE = ["V03", "V10", "V12", "V23", "V24"]


K_KWK_INTERN = 1.1 / (2350 / 3.6) ** 2     # Plan A: Δp intern 1,1 bar bei 2 350 t/h


def k_prior(dn_mm: float | None, laenge_m: float | None, f: float = 0.018, rho: float = 960.0) -> float:
    """Darcy-Widerstand von Vor- plus Rücklauf [bar/(kg/s)²]: 2 · 8 f L / (π² ρ D⁵) / 1e5 (ohne DN: KWK-intern)."""
    if dn_mm is None:
        return K_KWK_INTERN
    d = dn_mm / 1000
    return 2 * 8 * f * laenge_m / (np.pi**2 * rho * d**5) / 1e5


@dataclass
class Netz:
    knoten: list[str]
    kanten: list[tuple]
    wurzel: str = "KWK"
    idx: dict = field(init=False)
    A: np.ndarray = field(init=False)
    C: np.ndarray = field(init=False)
    P: np.ndarray = field(init=False)
    M0: np.ndarray = field(init=False)
    k0: np.ndarray = field(init=False)

    def __post_init__(self):
        self.idx = {n: i for i, n in enumerate(self.knoten)}
        self.kanten_ids = [k[0] for k in self.kanten]
        N, E = len(self.knoten), len(self.kanten)
        self.A = np.zeros((N, E))
        for j, (_, a, b, *_r) in enumerate(self.kanten):
            self.A[self.idx[a], j] -= 1.0
            self.A[self.idx[b], j] += 1.0
        self.k0 = np.array([k_prior(k[3], k[4]) for k in self.kanten])
        # Spannbaum per Breitensuche ab der Wurzel; P[n] = vorzeichenbehaftete Kanten des Baumpfads Wurzel -> n
        nachbarn = {n: [] for n in self.knoten}
        for j, (_, a, b, *_r) in enumerate(self.kanten):
            nachbarn[a].append((j, b, +1.0))
            nachbarn[b].append((j, a, -1.0))
        self.P = np.zeros((N, E))
        baum, besucht, schlange = [], {self.wurzel}, [self.wurzel]
        while schlange:
            n = schlange.pop(0)
            for j, m, s in nachbarn[n]:
                if m not in besucht:
                    besucht.add(m)
                    baum.append(j)
                    self.P[self.idx[m]] = self.P[self.idx[n]]
                    self.P[self.idx[m], j] = s
                    schlange.append(m)
        if len(besucht) != N:
            raise ValueError("Netz nicht zusammenhängend")
        sehnen = [j for j in range(E) if j not in baum]
        C = []
        for j in sehnen:
            _, a, b, *_r = self.kanten[j]
            z = self.P[self.idx[a]] - self.P[self.idx[b]]
            z[j] += 1.0
            C.append(z)
        self.C = np.array(C)
        # Baumströme aus Einspeisungen: A_T m_T = -b (ohne Wurzelzeile)
        nr = [i for i in range(N) if self.knoten[i] != self.wurzel]
        AT = self.A[np.ix_(nr, baum)]
        inv = np.linalg.inv(AT)
        self.M0 = np.zeros((E, N))
        self.M0[np.ix_(baum, nr)] = -inv
        self._nr = nr

    def loese(self, b: np.ndarray, K: np.ndarray, gewinn: np.ndarray | None = None, iter_max: int = 50,
              tol: float = 1e-7, m_lin: np.ndarray | None = None) -> np.ndarray:
        """Kantenströme [kg/s] (B×E) für Einspeisungen b (B×N, + = Einspeisung; Summe über Nicht-Wurzelknoten beliebig,
        die Wurzel gleicht aus). Pumpengewinne auf Kanten innerhalb von Maschen werden berücksichtigt. ``K`` je Kante (E)
        oder je Fall und Kante (B×E); ``m_lin``: Verlustgesetz oberhalb dieses Durchflusses linear (``verlust``)."""
        b = np.atleast_2d(b)
        B = b.shape[0]
        g = np.zeros((B, np.shape(K)[-1])) if gewinn is None else np.atleast_2d(gewinn)
        m0 = b @ self.M0.T
        nl = self.C.shape[0]
        q = np.zeros((B, nl))
        for _ in range(iter_max):
            m = m0 + q @ self.C
            h, d = verlust(m, K, m_lin)
            f = (h - g) @ self.C.T
            if np.max(np.abs(f)) < tol:
                break
            J = np.einsum("le,be,ke->blk", self.C, d + 1e-9, self.C)
            q = q - np.linalg.solve(J, f[..., None])[..., 0]
        return m0 + q @ self.C

    def dp_knoten(self, m: np.ndarray, K: np.ndarray, dp_wurzel: np.ndarray, gewinn: np.ndarray | None = None,
                  m_lin: np.ndarray | None = None) -> np.ndarray:
        """Δp (VL − RL) [bar] je Knoten (B×N) bei Wurzel-Δp ``dp_wurzel`` (B,)."""
        g = 0.0 if gewinn is None else gewinn
        return np.asarray(dp_wurzel)[:, None] - (verlust(m, K, m_lin)[0] - g) @ self.P.T


def verlust(m: np.ndarray, K: np.ndarray, m_lin: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Kantenverlust [bar] und Ableitung nach ṁ. Quadratisch K·ṁ·|ṁ|; mit ``m_lin`` (je Kante) oberhalb von m_lin
    linear fortgesetzt (stetig differenzierbar): K·sign(ṁ)·(2·m_lin·|ṁ| − m_lin²). Die lineare Fortsetzung bildet die
    Strukturvariante „Hebel wachsen oberhalb des Messbereichs nicht mehr“ ab."""
    a = np.abs(m)
    if m_lin is None:
        return K * m * a, 2 * K * a
    über = a > m_lin
    h = np.where(über, K * np.sign(m) * (2 * m_lin * a - m_lin**2), K * m * a)
    d = np.where(über, 2 * K * m_lin, 2 * K * a)
    return h, d


def netz() -> Netz:
    return Netz(list(KNOTEN), KANTEN)


QUELLEN = ["KWK", "MVA", "GT", "BIO", "HW1"]      # Quellmarkierung für die Mischungsrechnung (Temperatur-Tracer)


def quellanteile(nz: Netz, m: np.ndarray, b: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Anteil jeder Quelle (``QUELLEN``) am Vorlaufwasser je Knoten (B×N×Q): vollständige Mischung am Knoten,
    Aufwind entlang der Kantenströme ``m`` (B×E). Quellen sind die KWK (Wurzel) und die Erzeugerknoten mit Einspeisung
    b > 0. Knoten ohne Zufluss erhalten KWK-Wasser."""
    m, b = np.atleast_2d(m), np.atleast_2d(b)
    B, N = b.shape
    von = np.zeros((len(nz.kanten), N))
    nach = np.zeros_like(von)
    for j, (_, a, z, *_r) in enumerate(nz.kanten):
        von[j, nz.idx[a]] = 1.0
        nach[j, nz.idx[z]] = 1.0
    zufluss = np.maximum(nz.A[None, :, :] * m[:, None, :], 0.0)                   # B×N×E: Zufluss in n über e
    oben = np.where((m > 0)[..., None], von[None], nach[None])                    # B×E×N: Knoten stromauf von e
    ein = np.zeros((B, N, len(QUELLEN)))
    for q, kn in enumerate(QUELLEN[1:], start=1):
        ein[:, nz.idx[kn], q] = np.maximum(b[:, nz.idx[kn]], 0.0)
    w = nz.idx[nz.wurzel]
    Q = zufluss.sum(axis=2) + ein.sum(axis=2) + eps
    M = -np.einsum("bne,bek->bnk", zufluss, oben)
    M[:, np.arange(N), np.arange(N)] += Q
    rhs = ein.copy()
    rhs[:, :, 0] += eps                                                           # stehendes Wasser = KWK
    M[:, w, :] = 0.0
    M[:, w, w] = 1.0
    rhs[:, w, :] = 0.0
    rhs[:, w, 0] = 1.0
    return np.linalg.solve(M, rhs)


def lastanteile(gewichte: dict[str, float] | None = None) -> pd.Series:
    """Lastanteil je Knoten (Verbund): Anschlussleistung aus ``sectors.csv``, optional je Lastgruppe gewichtet und auf
    Summe 1 normiert."""
    s = daten.lade_sektoren()
    s = s[~s.section.str.startswith("W")]
    knoten = [next(v for k, v in SEKTOR_KNOTEN.items() if sa.startswith(k)) for sa in s.index]
    a = s.connected_MW.groupby(knoten).sum()
    for g, w in (gewichte or {}).items():
        a[LASTGRUPPEN[g]] *= w
    return a / a.sum()


def verteilung(nz: Netz, rest: np.ndarray, gk_gemessen: np.ndarray, gewichte: dict[str, float] | None = None,
               grundlast: dict[str, float] | None = None) -> np.ndarray:
    """Verbraucher-Massenstrom je Knoten (B×N): rest·Anteil + Grundlastverschiebung je Lastgruppe."""
    a = lastanteile(gewichte)
    gk = nz.idx[GROSSKUNDE[1]]
    w = np.zeros((len(rest), len(nz.knoten)))
    for kn, v in a.items():
        w[:, nz.idx[kn]] = v
    w[gk_gemessen, gk] = 0.0
    w /= w.sum(axis=1, keepdims=True)
    v = rest[:, None] * w
    if grundlast:
        basis = lastanteile()
        summe = 0.0
        for g, c in grundlast.items():
            kn = LASTGRUPPEN[g]
            v[:, [nz.idx[k] for k in kn]] += c * (basis[kn] / basis[kn].sum()).to_numpy()
            summe += c
        v[:, nz.idx["SEC2"]] -= summe
    return v


@dataclass
class Fall:
    """Stundenweise Randbedingungen und Messwerte für das Ersatznetz.

    Einspeisungen b = b_fix − rest·Lastanteil: ``b_fix`` enthält Erzeuger, Übergabe West und den gemessenen Großkunden,
    ``rest`` die übrigen Verbraucher-Massenströme, die nach Lastanteil verteilt werden.
    """
    b_fix: np.ndarray             # B×N [kg/s]
    rest: np.ndarray              # B [kg/s]
    gk_gemessen: np.ndarray       # B (bool): Großkunde gemessen -> sein Knoten erhält keinen Restanteil
    gewinn: np.ndarray            # Pumpengewinne B×E [bar]
    dp_kwk: np.ndarray            # B
    ziele: pd.DataFrame           # Messwerte: Δp je Station/Erzeuger [bar], Stammleitungsflüsse [kg/s]
    index: pd.DatetimeIndex

    def b(self, nz: Netz, gewichte: dict[str, float] | None = None, grundlast: dict[str, float] | None = None) -> np.ndarray:
        """Einspeisungen B×N. ``grundlast`` [kg/s] je Lastgruppe verschiebt Last zwischen den Gruppen (Summe 0; Rest geht
        an SEC2): Gruppen mit viel Grundlast haben bei geringer Gesamtlast einen höheren Anteil."""
        return self.b_fix - verteilung(nz, self.rest, self.gk_gemessen, gewichte, grundlast)

    def teil(self, sel) -> Fall:
        return Fall(self.b_fix[sel], self.rest[sel], self.gk_gemessen[sel], self.gewinn[sel], self.dp_kwk[sel],
                    self.ziele.iloc[sel], self.index[sel])


def randbedingungen(m: pd.DataFrame, e: pd.DataFrame, nz: Netz) -> Fall:
    """Einspeisungen aus Messwerten: Ost-Erzeuger, HW1, Übergabe West; Verbraucher = Rest nach Lastanteil, der gemessene
    Großkunde an seinem Knoten. Die KWK-Einspeisung (Summe der Stammleitungsflüsse) bestimmt den Rest, die Aufteilung
    auf die Stammleitungen ist Modellergebnis."""
    ms = hydraulik.massenstroeme(m, e)
    kwk = m[[f"gas_CHP_flow_line_{k}" for k in range(1, 5)]].sum(axis=1, min_count=4) / 3.6
    hx = m.boiler_plant_2_hx_flow / 3.6
    ein = pd.DataFrame({"MVA": ms.MVA, "GT": ms.GT.fillna(0.0), "BIO": ms.Bio, "HW1": ms.HW1, "HW2": -hx}, index=m.index)
    verbraucher = (kwk + ein.sum(axis=1, min_count=5)).to_numpy()
    b = np.zeros((len(m), len(nz.knoten)))
    for k, s in ein.items():
        b[:, nz.idx[k]] += s.to_numpy()
    gk, gk_knoten = GROSSKUNDE
    g = (m[f"{gk}_flow"] / 3.6).to_numpy()
    gemessen = np.isfinite(g)
    b[gemessen, nz.idx[gk_knoten]] -= g[gemessen]
    rest = np.where(gemessen, verbraucher - np.nan_to_num(g), verbraucher)
    E = len(nz.kanten)
    gew = np.zeros((len(m), E))
    for kid, ps in PUMPEN.items():
        gew[:, nz.kanten_ids.index(kid)] = (m[f"{ps}_dp_supply_after_pump"] - m[f"{ps}_dp_supply_before_pump"]).fillna(0).to_numpy()
    kd = daten.kunden_dp(m)
    ziele = pd.DataFrame({st: kd[st] for st in STATIONEN if st in kd}, index=m.index)
    ziele["MVA"] = m.waste_incineration_p_supply - m.waste_incineration_p_return
    ziele["GT"] = m.gas_turbine_dp.where(e["gas_turbine"] > 2)
    ziele["BIO"] = m.biomass_CHP_dp
    ziele["HW1"] = m.boiler_plant_1_dp.where(ms.HW1 > 5)
    ziele["PS1"] = m.pump_station_1_dp_supply_before_pump
    ziele["PS2"] = m.pump_station_2_dp_supply_before_pump
    ziele["HW2"] = m.boiler_plant_2_hx_dp
    for kid, k in STAMMLEITUNGEN.items():
        ziele[f"Fluss {kid}"] = m[f"gas_CHP_flow_line_{k}"] / 3.6
    dp_kwk = (m.gas_CHP_p_supply - m.gas_CHP_p_return).to_numpy()
    ok = np.isfinite(b).all(axis=1) & np.isfinite(rest) & np.isfinite(dp_kwk)
    return Fall(b[ok], rest[ok], gemessen[ok], gew[ok], dp_kwk[ok], ziele[ok], m.index[ok])


ZIEL_KNOTEN = {**STATIONEN, "MVA": "MVA", "GT": "GT", "BIO": "BIO", "HW1": "HW1", "PS1": "PS1", "PS2": "PS2", "HW2": "HW2"}
FLUSS_SKALA = 15.0      # kg/s, die im Kalibrierziel 0,1 bar entsprechen


def simuliere(nz: Netz, fall: Fall, K: np.ndarray, versatz: dict | None = None,
              gewichte: dict[str, float] | None = None, grundlast: dict[str, float] | None = None) -> pd.DataFrame:
    """Modellwerte zu den Messzielen: Δp an Stationen/Erzeugern (+ Stationsversatz) und Stammleitungsflüsse."""
    m = nz.loese(fall.b(nz, gewichte, grundlast), K, fall.gewinn)
    dp = nz.dp_knoten(m, K, fall.dp_kwk, fall.gewinn)
    # Pumpstationen: Saugseite = Knoten (Gewinn liegt am Anfang der abgehenden Kante)
    out = {z: dp[:, nz.idx[kn]] + (versatz or {}).get(z, 0.0) for z, kn in ZIEL_KNOTEN.items()}
    for kid in STAMMLEITUNGEN:
        out[f"Fluss {kid}"] = m[:, nz.kanten_ids.index(kid)]
    return pd.DataFrame(out, index=fall.index)


GRUNDLAST_GRUPPEN = ["SEC3", "SEC4", "Süd", "Ost", "L1"]      # SEC2 gleicht aus
HEBEL_ZIELE = ["V06", "V03", "V12", "V23", "V22", "V15", "MVA", "PS1"]
HEBEL_REGRESSOREN = ["KWK-Fluss", "KWK-Δp", "Verbraucher", "HW1", "PS1-Gewinn"]


def hebel_regressoren(m: pd.DataFrame, e: pd.DataFrame, index: pd.DatetimeIndex, mit_west: bool = False) -> pd.DataFrame:
    """Massenstromkonsistente Regressoren der Hebelregression: KWK-Eigendurchfluss, KWK-Δp, Verbraucherdurchfluss,
    HW1-Durchfluss (je 100 kg/s) und PS1-Gewinn. Bei festem KWK-Durchfluss und Verbrauch beschreibt der HW1-Koeffizient
    den Ersatz von Ost- durch Süd-Einspeisung; der KWK-Koeffizient (negativ) den Ersatz von KWK- durch Ost-Wasser.
    ``mit_west``: zusätzlich der Übergabestrom zum Westnetz. Dann ist der KWK-Koeffizient reiner Ost-Ersatz (ohne den
    Anteil, in dem eine geänderte West-Entnahme den KWK-Durchfluss verschiebt)."""
    ms = hydraulik.massenstroeme(m, e)
    kwk = m[[f"gas_CHP_flow_line_{k}" for k in range(1, 5)]].sum(axis=1, min_count=4) / 3.6
    verbr = kwk + ms.MVA + ms.GT.fillna(0.0) + ms.Bio + ms.HW1 - m.boiler_plant_2_hx_flow / 3.6
    r = pd.DataFrame({"KWK-Fluss": kwk / 100, "KWK-Δp": m.gas_CHP_p_supply - m.gas_CHP_p_return,
                      "Verbraucher": verbr / 100, "HW1": ms.HW1 / 100,
                      "PS1-Gewinn": m.pump_station_1_p_supply_after_pump - m.pump_station_1_p_supply_before_pump})
    if mit_west:
        r["West"] = m.boiler_plant_2_hx_flow / 360
    return r.reindex(index)


def _hebel_koeff(Y: np.ndarray, dX: np.ndarray, zeilen: np.ndarray) -> np.ndarray:
    """Regression stündlicher Differenzen ΔY = c0 + ΔX·b je Spalte von Y (nur Zeilen ``zeilen`` je Spalte)."""
    dY = np.diff(Y, axis=0)
    out = np.zeros((Y.shape[1], dX.shape[1]))
    A = np.c_[np.ones(len(dX)), dX]
    for j in range(Y.shape[1]):
        z = zeilen[:, j]
        out[j] = np.linalg.lstsq(A[z], dY[z, j], rcond=None)[0][1:]
    return out


def hebel_vergleich(fall: Fall, reg: pd.DataFrame, sim: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Gleiche Differenzenregression auf Messung und Modell (gleiche Stunden): Koeffizienten Messung, Modell, Standardfehler."""
    dX = np.diff(reg.to_numpy(), axis=0)
    Ym = fall.ziele[HEBEL_ZIELE].to_numpy()
    dYm = np.diff(Ym, axis=0)
    folge = np.diff(fall.index.to_numpy()) == np.timedelta64(1, "h")
    zeilen = folge[:, None] & np.isfinite(dYm) & (np.abs(dYm) < 1.0) & np.isfinite(dX).all(axis=1)[:, None]
    km = _hebel_koeff(Ym, np.nan_to_num(dX), zeilen)
    ks = _hebel_koeff(sim[HEBEL_ZIELE].to_numpy(), np.nan_to_num(dX), zeilen)
    se = np.zeros_like(km)
    A = np.c_[np.ones(len(dX)), np.nan_to_num(dX)]
    for j in range(len(HEBEL_ZIELE)):
        z = zeilen[:, j]
        r = dYm[z, j] - A[z] @ np.r_[0.0, km[j]] - np.mean(dYm[z, j] - A[z] @ np.r_[0.0, km[j]])
        se[j] = np.sqrt(np.diag(np.linalg.inv(A[z].T @ A[z]))[1:] * r.var())
    f = lambda a: pd.DataFrame(a, index=HEBEL_ZIELE, columns=list(reg.columns))  # noqa: E731
    return f(km), f(ks), f(se)


def hebel_vergleich_fest(fall: Fall, reg: pd.DataFrame, sim: pd.DataFrame, fest: str = "KWK-Δp") -> tuple[pd.DataFrame, ...]:
    """Wie ``hebel_vergleich``, aber mit dem Koeffizienten von ``fest`` auf 1 gesetzt: Ziel minus Regressor wird auf die
    übrigen Regressoren regressiert (Gegenprobe gegen eine durch die Regelung verzerrte KWK-Δp)."""
    from dataclasses import replace

    u = reg[fest].to_numpy()[:, None]
    f2 = replace(fall, ziele=fall.ziele.assign(**{z: fall.ziele[z] - u[:, 0] for z in HEBEL_ZIELE}))
    s2 = sim.assign(**{z: sim[z] - u[:, 0] for z in HEBEL_ZIELE})
    return hebel_vergleich(f2, reg.drop(columns=fest), s2)


def kalibrier_problem(nz: Netz, fall: Fall, prior_sigma: float = 1.0, versatz_sigma: float = 0.3, gewicht_sigma: float = 0.3,
                      grundlast_sigma: float = 40.0, gewichtung: np.ndarray | None = None, paar_gewicht: float = 0.0,
                      hebel: dict | None = None, kanten_sigma: dict[str, float] | None = None) -> dict:
    """Residuenfunktion der Kalibrierung (gewichtete kleinste Quadrate über alle Stunden des Falls). Parameter mit Prior:
    * Widerstandsmultiplikator je Kante (log, N(0, ``prior_sigma``)),
    * Lastgewicht je Lastgruppe (log, N(0, ``gewicht_sigma``)),
    * Grundlastverschiebung je Lastgruppe (kg/s, N(0, ``grundlast_sigma``); SEC2 gleicht aus),
    * Versatz je Station (bar, N(0, ``versatz_sigma``)): örtliche Verluste zwischen Sektionsknoten und Messstelle.
    ``gewichtung`` (je Stunde) kann z. B. Heizperiodenstunden stärker gewichten.
    ``paar_gewicht`` > 0: Der Fall besteht aus aufeinanderfolgenden Stundenpaaren (Zeile 2k, 2k+1); zusätzlich werden die
    stündlichen **Änderungen** angepasst (Skala 0,05 bar bzw. 5 kg/s). Das bindet die Reaktion auf Einspeiseänderungen
    (natürliche Experimente) und trennt Verluste, die nur vom Gesamtdurchfluss abhängen, von solchen einzelner Leitungen.
    ``hebel``: {"fall": zusammenhängender Fall, "reg": Regressoren (``hebel_regressoren``), "gewicht": float}. Die gemessenen
    Hebel (Differenzenregression) werden mit denselben Regressionen auf der Modellreihe verglichen; Skala = max(SE, 0,03).
    ``kanten_sigma``: abweichender Prior je Kante (z. B. eng um den Planwert).
    Rückgabe: {"res": Residuen(x), "zerlege": x -> (K, Gewichte, Grundlast, Versatz), "x_aus": Kalibrierung -> x, "namen"}.
    """
    stationen = [s for s in STATIONEN if s in fall.ziele]
    gruppen = list(LASTGRUPPEN)
    E, G, H = len(nz.kanten), len(gruppen), len(GRUNDLAST_GRUPPEN)
    if paar_gewicht > 0:
        t = fall.index
        gerade = np.arange(0, len(t) - 1, 2)
        paare = gerade[(t[gerade + 1] - t[gerade]) == pd.Timedelta(hours=1)]
    spalten = list(fall.ziele.columns)
    W = np.array([1 / 0.1 if not c.startswith("Fluss") else 1 / FLUSS_SKALA for c in spalten])
    Yv = fall.ziele.to_numpy()
    maske = np.isfinite(Yv)
    gw = np.ones(len(Yv)) if gewichtung is None else np.asarray(gewichtung, float)
    norm = np.sqrt((maske * gw[:, None]).sum() / Yv.shape[1])

    def zerlege(x):
        return (nz.k0 * np.exp(x[:E]), dict(zip(gruppen, np.exp(x[E:E + G]), strict=True)),
                dict(zip(GRUNDLAST_GRUPPEN, x[E + G:E + G + H], strict=True)),
                dict(zip(stationen, x[E + G + H:], strict=True)))

    Wd = np.array([1 / 0.05 if not c.startswith("Fluss") else 1 / 5.0 for c in spalten])
    if hebel:
        hf, hreg = hebel["fall"], hebel["reg"]
        km0, _, se0 = hebel_vergleich(hf, hreg, hf.ziele)
        hskala = np.maximum(se0.to_numpy(), 0.03)
        dXh = np.nan_to_num(np.diff(hreg.to_numpy(), axis=0))
        Ymh = hf.ziele[HEBEL_ZIELE].to_numpy()
        dYmh = np.diff(Ymh, axis=0)
        folge = np.diff(hf.index.to_numpy()) == np.timedelta64(1, "h")
        hzeilen = folge[:, None] & np.isfinite(dYmh) & (np.abs(dYmh) < 1.0) & np.isfinite(np.diff(hreg.to_numpy(), axis=0)).all(axis=1)[:, None]
        hkm = km0.to_numpy()

    sig_k = np.array([(kanten_sigma or {}).get(k, prior_sigma) for k in nz.kanten_ids])

    def res(x):
        K, gew, gl, vs = zerlege(x)
        sim = simuliere(nz, fall, K, vs, gew, gl)[spalten].to_numpy()
        r = np.where(maske, (sim - Yv) * W * np.sqrt(gw)[:, None], 0.0).ravel() / norm
        teile = [r]
        if paar_gewicht > 0:
            dsim, dy = sim[paare + 1] - sim[paare], Yv[paare + 1] - Yv[paare]
            md = np.isfinite(dy)
            rd = np.where(md, (dsim - dy) * Wd, 0.0).ravel() / np.sqrt(md.sum() / Yv.shape[1])
            teile.append(np.sqrt(paar_gewicht) * rd)
        if hebel:
            simh = simuliere(nz, hf, K, vs, gew, gl)[HEBEL_ZIELE].to_numpy()
            ks = _hebel_koeff(simh, dXh, hzeilen)
            teile.append(np.sqrt(hebel.get("gewicht", 1.0)) * ((ks - hkm) / hskala).ravel())
        return np.concatenate([*teile, x[:E] / sig_k, x[E:E + G] / gewicht_sigma, x[E + G:E + G + H] / grundlast_sigma,
                               x[E + G + H:] / versatz_sigma])

    def x_aus(kal: dict) -> np.ndarray:
        x = np.zeros(E + G + H + len(stationen))
        x[:E] = np.log(np.clip(kal["multiplikator"].reindex(nz.kanten_ids).to_numpy(float), 1e-3, None))
        x[E:E + G] = np.log([kal["gewichte"].get(g, 1.0) for g in gruppen])
        x[E + G:E + G + H] = [kal["grundlast"].get(g, 0.0) for g in GRUNDLAST_GRUPPEN]
        x[E + G + H:] = [float(kal["versatz"].get(st, 0.0)) for st in stationen]
        return x

    namen = ([f"log Multiplikator {k}" for k in nz.kanten_ids] + [f"log Gewicht {g}" for g in gruppen]
             + [f"Grundlast {g} [kg/s]" for g in GRUNDLAST_GRUPPEN] + [f"Versatz {st} [bar]" for st in stationen])
    return {"res": res, "zerlege": zerlege, "x_aus": x_aus, "namen": namen}


def kalibriere(nz: Netz, fall: Fall, prior_sigma: float = 1.0, versatz_sigma: float = 0.3, gewicht_sigma: float = 0.3,
               grundlast_sigma: float = 40.0, gewichtung: np.ndarray | None = None, max_nfev: int = 300,
               paar_gewicht: float = 0.0, hebel: dict | None = None, kanten_sigma: dict[str, float] | None = None,
               start: dict | None = None) -> dict:
    """Kalibrierung (``kalibrier_problem``) mit ``least_squares``; ``start``: früheres Ergebnis als Startwert (Kanten mit
    eigenem Prior in ``kanten_sigma`` starten am Planwert)."""
    pr = kalibrier_problem(nz, fall, prior_sigma, versatz_sigma, gewicht_sigma, grundlast_sigma, gewichtung, paar_gewicht,
                           hebel, kanten_sigma)
    E = len(nz.kanten)
    x0 = np.zeros(len(pr["namen"]))
    if start:
        x0 = pr["x_aus"](start)
        for i, k in enumerate(nz.kanten_ids):
            if k in (kanten_sigma or {}):
                x0[i] = 0.0
    lsq = least_squares(pr["res"], x0, method="trf", x_scale="jac", max_nfev=max_nfev)
    K, gew, gl, vs = pr["zerlege"](lsq.x)
    return {"K": K, "multiplikator": pd.Series(np.exp(lsq.x[:E]), index=nz.kanten_ids), "gewichte": gew, "grundlast": gl,
            "versatz": pd.Series(vs), "kosten": float(lsq.cost), "erfolg": bool(lsq.success)}


def laplace_kovarianz(problem: dict, x: np.ndarray, schritt: np.ndarray | None = None) -> np.ndarray:
    """Kovarianz der Parameter in Laplace-Näherung, (JᵀJ)⁻¹ mit der Jacobi-Matrix der Residuen (zentrale Differenzen).
    Die Residuen der Kalibrierung sind so skaliert, dass jede Messreihe wie eine Beobachtung mit 0,1 bar Fehler
    (Pegel) bzw. ihrem Standardfehler (Hebel) zählt; die Kovarianz beschreibt damit die Parameterunsicherheit bei
    systematischem Modellfehler dieser Größe."""
    h = np.full(len(x), 1e-3) if schritt is None else np.asarray(schritt, float)
    J = np.empty((len(problem["res"](x)), len(x)))
    for i in range(len(x)):
        e = np.zeros(len(x))
        e[i] = h[i]
        J[:, i] = (problem["res"](x + e) - problem["res"](x - e)) / (2 * h[i])
    return np.linalg.inv(J.T @ J)


def guete(sim: pd.DataFrame, ziele: pd.DataFrame, maske: np.ndarray | None = None) -> pd.DataFrame:
    """RMSE, Bias und Korrelation je Messziel."""
    rows = []
    for c in ziele.columns:
        y, s = ziele[c].to_numpy(), sim[c].to_numpy()
        ok = np.isfinite(y) & (maske if maske is not None else True)
        if ok.sum() < 20:
            continue
        e = s[ok] - y[ok]
        rows.append({"Ziel": c, "n": int(ok.sum()), "Bias": float(e.mean()), "RMSE": float(np.sqrt((e**2).mean())),
                     "r": float(np.corrcoef(s[ok], y[ok])[0, 1]) if np.std(y[ok]) > 0 else np.nan})
    return pd.DataFrame(rows).set_index("Ziel")


def hebel_modell(nz: Netz, fall: Fall, K: np.ndarray, knoten_ein: str, gewichte: dict | None = None,
                 grundlast: dict | None = None, dm: float = 10.0) -> pd.Series:
    """Modell-Einspeisehebel: Δp-Änderung je Knoten bei +dm kg/s Einspeisung am Knoten anstelle von KWK-Wasser
    (KWK-Δp fest), je 100 kg/s, gemittelt über die Stunden des Falls."""
    b1 = fall.b(nz, gewichte, grundlast)
    m1 = nz.loese(b1, K, fall.gewinn)
    d1 = nz.dp_knoten(m1, K, fall.dp_kwk, fall.gewinn)
    b2 = b1.copy()
    b2[:, nz.idx[knoten_ein]] += dm
    m2 = nz.loese(b2, K, fall.gewinn)
    d2 = nz.dp_knoten(m2, K, fall.dp_kwk, fall.gewinn)
    return pd.Series((d2 - d1).mean(axis=0) * 100 / dm, index=nz.knoten)


def erforderliche_kwk_dp(nz: Netz, K: np.ndarray, b: np.ndarray, gewinn: np.ndarray, mindest: dict[str, float],
                         versatz: dict | None = None) -> tuple[np.ndarray, pd.DataFrame]:
    """Kleinste KWK-Δp, bei der alle Zielstationen ihren Mindest-Δp halten (Δp ist linear in der Wurzel-Δp)."""
    m = nz.loese(b, K, gewinn)
    d0 = nz.dp_knoten(m, K, np.zeros(b.shape[0]), gewinn)
    need = pd.DataFrame({z: mindest[z] - d0[:, nz.idx[ZIEL_KNOTEN[z]]] - (versatz or {}).get(z, 0.0) for z in mindest})
    return need.max(axis=1).to_numpy(), need


def entlastung_aus_hebeln(need: pd.Series, hebel: dict[str, float], dm: float) -> float:
    """Senkung der erforderlichen KWK-Δp durch eine Einspeisung von ``dm`` kg/s anstelle von KWK-Wasser, wenn sie jede
    Zielstation um ``hebel[z]`` bar je 100 kg/s anhebt. ``need``: KWK-Δp-Bedarf je Zielstation (maßgebend ist das Maximum)."""
    return float(need.max() - max(need[z] - hebel[z] * dm / 100 for z in need.index))


def auslegungs_einspeisung(nz: Netz, P_verbund_mw: float, dh_kj_kg: float, ost_mw: dict[str, float], hw1_mw: float,
                           hw1_max_kg_s: float, west_bezug_mw: float = 0.0, speicher: dict[str, float] | None = None,
                           gewichte: dict[str, float] | None = None, grundlast: dict[str, float] | None = None) -> np.ndarray:
    """Einspeisevektor (1×N) für einen Auslegungsfall: Lasten nach Anschlussanteil, Ost/HW1 fest, KWK als Ausgleich,
    optional Speicherentladung [MW] an Knoten (verdrängt KWK-Wasser)."""
    mf = 1e3 / dh_kj_kg
    b = np.zeros(len(nz.knoten))
    for k, p in ost_mw.items():
        b[nz.idx[k]] += p * mf
    b[nz.idx["HW1"]] += min(hw1_mw * mf, hw1_max_kg_s)
    b[nz.idx["HW2"]] -= west_bezug_mw * mf
    last = (P_verbund_mw - west_bezug_mw) * mf
    b -= verteilung(nz, np.array([last]), np.array([False]), gewichte, grundlast)[0]
    for kn, p in (speicher or {}).items():
        b[nz.idx[kn]] += p * mf
    return b[None, :]
