"""Unsicherheitsläufe zum Auslegungsfall (Plan, Phase 4): Ensemble über Parameter, Eingangsgrößen und Modellstruktur.

Quellen der Unsicherheit:
* **Kalibrierung:** alle gleich guten Kalibriervarianten aus dem Mehrfachstart (``mehrfachstart.py``,
  ``scripts/dhn_study/kalibrierung/``), je Variante gleich viele Läufe. Um jede Variante streuen die Parameter nach der
  Laplace-Näherung (``netzmodell.laplace_kovarianz``): log-Multiplikatoren, log-Lastgewichte, Grundlastverschiebungen
  und Stationsversätze als multivariate Normalverteilung.
* **Eingangsgrößen** des Auslegungsfalls:
  * Rücklauf ~ N(gemessener Median bei Kälte, 1 K);
  * Ost-Erzeugung zwischen Plan A und dem Kältebetrieb 2025 (gleichverteilt);
  * PS1-Gewinn zwischen P95 und P99 2025 (gleichverteilt);
  * Mindest-Δp am Regelpunkt V06 1,0–1,4 bar (Sollwert 1,2 bar ± 0,2; offene TAB-Frage).
* **Modellstruktur** (jeder Lauf in beiden Varianten):
  * „quadratisch“: Verluste wachsen auch oberhalb des Messbereichs mit ṁ²;
  * „linear oberhalb P95“: oberhalb des P95-Durchflusses je Kante (Heizperiode 2025) wachsen die Verluste linear, die
    Hebel also nicht mehr (Befund der Hebel je Durchflussband, ``Netzmodell.md`` Abschnitt 4.3).
  Zusätzlich für den Speicher S die datenverankerte Entlastung mit den gemessenen Hebeln (± Standardfehler).

Bewertung nach Plan 1.1: Eine Aussage gilt als gestützt, wenn sie in ≥ 90 % der Läufe **jeder** Kombination aus
Struktur- und Kalibriervariante gilt.

Aufruf: ``python -m scripts.dhn_study.unsicherheit`` (≈ 2–5 min; die Kovarianzen werden beim ersten Lauf berechnet und
gespeichert, ``--neu`` erzwingt die Neuberechnung). Voraussetzung: ``python -m scripts.dhn_study.run_netzmodell
--ohne-kalibrierung`` (gemessene Speicherhebel je Variante).
Ergebnisse: ``results/dhn_study/netzmodell/unsicherheit_*.csv`` und ``unsicherheit_zusammenfassung.md``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import daten
from . import netzmodell as nm
from .run_analyse import T_VL_AUSL, _md
from .run_netzmodell import (
    KALIBRIERUNG_REPO,
    SPEICHER_MW,
    auslegung_eingaben,
    kalibrier_eingaben,
    kalibrier_problem,
    kalibriervarianten,
    lade_kalibrierung,
)

N_JE_VARIANTE = 200       # Läufe je Kalibriervariante, Strukturvariante und Lastfall
SEED = 7
SIGMA_RUECKLAUF_K = 1.0
V06_MINDEST = (1.0, 1.4)
KNIE_QUANTIL = 0.95
VARIANTEN = ("quadratisch", "linear oberhalb P95")


def ziehe_parameter(x: np.ndarray, kov: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """n Parametervektoren aus N(x, kov); die Kovarianz wird bei Bedarf auf positive Eigenwerte gestutzt."""
    kov = 0.5 * (kov + kov.T)
    w, v = np.linalg.eigh(kov)
    L = v * np.sqrt(np.clip(w, 0.0, None))
    return x + rng.standard_normal((n, len(x))) @ L.T


class Ensemble:
    """Auslegungsfall für viele Läufe zugleich (Einspeisungen, Widerstände und Grenzen je Lauf)."""

    def __init__(self, nz: nm.Netz, pr: dict, xs: np.ndarray, ae: dict, t_rl: np.ndarray, lam_ost: np.ndarray,
                 ps1: np.ndarray, v06: np.ndarray):
        """``xs``: Parametervektoren (n×P); je Lauf Rücklauf [°C], Anteil „Ost wie 2025“ (0 = Plan A), PS1-Gewinn [bar]
        und Mindest-Δp an V06 [bar]."""
        self.nz = nz
        n = len(xs)
        teile = [pr["zerlege"](x) for x in xs]
        self.K = np.array([t[0] for t in teile])
        self.versatz = [t[3] for t in teile]
        self.t_rl, self.lam_ost, self.ps1, self.v06 = (np.broadcast_to(np.asarray(v, float), (n,)).copy()
                                                       for v in (t_rl, lam_ost, ps1, v06))
        self.mf = 1e3 / np.array([float(daten.dh(T_VL_AUSL, t)) for t in self.t_rl])
        a, b = ae["ost"]["Ost Plan A"], ae["ost"]["Ost wie 2025"]
        ost = {k: (1 - self.lam_ost) * a[k] + self.lam_ost * b[k] for k in a}
        N = len(nz.knoten)
        self.inj = np.zeros((n, N))
        for k, p in ost.items():
            self.inj[:, nz.idx[k]] += p * self.mf
        self.inj[:, nz.idx["HW1"]] += np.minimum(ae["hw1_mw"] * self.mf, ae["hw1_m"])
        self.W = np.zeros((n, N))
        self.shift = np.zeros((n, N))
        for i, t in enumerate(teile):
            v1 = nm.verteilung(nz, np.array([1.0]), np.array([False]), t[1], t[2])[0]
            v0 = nm.verteilung(nz, np.array([0.0]), np.array([False]), t[1], t[2])[0]
            self.W[i], self.shift[i] = v1 - v0, v0
        self.G = np.repeat(ae["gewinn"], n, axis=0)
        self.G[:, nz.kanten_ids.index("L4c")] = self.ps1
        self.ziele = list(ae["mindest"])
        self.mindest = np.array([[self.v06[i] if z == "V06" else ae["mindest"][z] for z in self.ziele] for i in range(n)])
        self.vs = np.array([[float(v.get(z, 0.0)) for z in self.ziele] for v in self.versatz])
        self.knoten = [nz.idx[nm.STATIONEN[z]] for z in self.ziele]

    def einspeisung(self, P: np.ndarray, west: float, speicher: str | None = None) -> np.ndarray:
        b = self.inj - ((P - west) * self.mf)[:, None] * self.W - self.shift
        b[:, self.nz.idx["HW2"]] -= west * self.mf
        if speicher:
            b[:, self.nz.idx[speicher]] += SPEICHER_MW * self.mf
        return b

    def bedarf(self, P: np.ndarray, west: float, speicher: str | None = None, m_lin=None) -> np.ndarray:
        """KWK-Δp-Bedarf je Lauf und Zielstation (n×Z): Mindest-Δp − Δp bei KWK-Δp 0 − Stationsversatz."""
        b = self.einspeisung(P, west, speicher)
        m = self.nz.loese(b, self.K, self.G, m_lin=m_lin)
        d0 = self.nz.dp_knoten(m, self.K, np.zeros(len(b)), self.G, m_lin=m_lin)
        return self.mindest - d0[:, self.knoten] - self.vs

    def reserve(self, P: float, west: float, grenze, speicher=None, m_lin=None, hebel=None) -> np.ndarray:
        """Lastzuwachs (Faktor − 1) je Lauf, bis der Bedarf die Grenze erreicht (Bisektion). ``hebel`` (n×Z, bar je
        100 kg/s): Speicher S über gemessene Hebel statt im Modell."""
        n = len(self.K)
        lo, hi = np.full(n, 0.5), np.full(n, 2.5)
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            need = self.bedarf(P * mid, west, speicher, m_lin)
            if hebel is not None:
                need = need - hebel * (SPEICHER_MW * self.mf)[:, None] / 100
            ok = need.max(axis=1) < grenze
            lo, hi = np.where(ok, mid, lo), np.where(ok, hi, mid)
        return lo - 1.0


def main(n_je: int = N_JE_VARIANTE, neu_kovarianz: bool = False) -> dict:
    out = daten.repo_root() / "results" / "dhn_study" / "netzmodell"
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    ein = kalibrier_eingaben(m, e, ta, f)
    pr = kalibrier_problem(nz, ein)
    namen, referenz = kalibriervarianten()
    E, G, H = len(nz.kanten), len(nm.LASTGRUPPEN), len(nm.GRUNDLAST_GRUPPEN)
    rng = np.random.default_rng(SEED)
    x_hat, xs, var_kal, par = {}, [], [], {}
    for v in namen:
        x_hat[v] = pr["x_aus"](lade_kalibrierung(KALIBRIERUNG_REPO / v, nz))
        datei = out / f"kalibrierung_kovarianz_{v}.csv"
        if neu_kovarianz or not datei.exists():
            schritt = np.full(len(x_hat[v]), 1e-3)
            schritt[E + G:E + G + H] = 0.05
            pd.DataFrame(nm.laplace_kovarianz(pr, x_hat[v], schritt), index=pr["namen"], columns=pr["namen"]).to_csv(datei)
        kov = pd.read_csv(datei, index_col=0).loc[pr["namen"], pr["namen"]].to_numpy()
        par[v] = pd.DataFrame({"Schätzwert": x_hat[v], "Standardabweichung": np.sqrt(np.diag(kov))}, index=pr["namen"])
        xs.append(ziehe_parameter(x_hat[v], kov, n_je, rng))
        var_kal += [v] * n_je
    xs, var_kal = np.vstack(xs), np.array(var_kal)
    n = len(xs)
    erg = {"parameter": pd.concat(par, axis=1), "varianten": namen, "referenz": referenz}
    erg["parameter"].to_csv(out / "unsicherheit_parameter.csv")

    ae = auslegung_eingaben(m, e, ta, nz)
    ens = Ensemble(nz, pr, xs, ae, t_rl=ae["T_RL"] + SIGMA_RUECKLAUF_K * rng.standard_normal(n),
                   lam_ost=rng.uniform(0.0, 1.0, n), ps1=rng.uniform(ae["ps1_quantile"]["P95"], ae["ps1_quantile"]["P99"], n),
                   v06=rng.uniform(*V06_MINDEST, n))
    # Beiträge zur Streuung der erforderlichen KWK-Δp (quadratische Variante): nur Parameter (inkl. Kalibriervarianten),
    # nur Eingangsgrößen (Referenzkalibrierung), alles
    x_ref = np.repeat(x_hat[referenz][None], n, axis=0)
    teil_ens = {"nur Parameter": Ensemble(nz, pr, xs, ae, ae["T_RL"], 0.5, ae["ps1_quantile"]["P99"], ae["mindest"]["V06"]),
                "nur Eingangsgrößen": Ensemble(nz, pr, x_ref, ae, ens.t_rl, ens.lam_ost, ens.ps1, ens.v06),
                "alles": ens}
    beitrag = {}
    for fall, (P, west) in ae["faelle"].items():
        for name, en in teil_ens.items():
            r = en.bedarf(np.full(n, P), west).max(axis=1)
            beitrag[(fall, name)] = {"P5": np.quantile(r, 0.05), "P50": np.median(r), "P95": np.quantile(r, 0.95)}
    erg["beitrag"] = pd.DataFrame(beitrag).T
    erg["beitrag"]["Breite P5–P95"] = erg["beitrag"]["P95"] - erg["beitrag"]["P5"]
    erg["beitrag"].to_csv(out / "unsicherheit_beitraege.csv")
    # Welche Parameter treiben die Streuung? Rangkorrelation mit der erf. KWK-Δp (P90, nur Parameter, Referenzvariante)
    P90, west90 = ae["faelle"]["P90"]
    r90 = teil_ens["nur Parameter"].bedarf(np.full(n, P90), west90).max(axis=1)
    ref = var_kal == referenz
    rho = pd.DataFrame(xs[ref], columns=pr["namen"]).corrwith(pd.Series(r90[ref]), method="spearman")
    erg["parameter_einfluss"] = rho.reindex(rho.abs().sort_values(ascending=False).index[:8]).to_frame("Rangkorrelation (P90)")
    # Kontrolle: ohne Streuung reproduziert das Ensemble den deterministischen Auslegungsfall (Referenz, Ost nach Plan A)
    det = Ensemble(nz, pr, x_hat[referenz][None], ae, ae["T_RL"], 0.0, ae["ps1_quantile"]["P99"], ae["mindest"]["V06"])
    erg["kontrolle"] = {fall: float(det.bedarf(np.array([P]), west).max()) for fall, (P, west) in ae["faelle"].items()}

    # Knie der Strukturvariante je Kalibriervariante: P95 des Durchflusses je Kante in der Heizperiode 2025
    knie = {}
    for v in namen:
        K_v, gw_v, gl_v, _ = pr["zerlege"](x_hat[v])
        knie[v] = np.quantile(np.abs(nz.loese(f.b(nz, gw_v, gl_v), K_v, f.gewinn)[ein["heiz"]]), KNIE_QUANTIL, axis=0)
    m_lin = np.array([knie[v] for v in var_kal])
    erg["knie"] = pd.DataFrame(knie, index=nz.kanten_ids)

    # Gemessene Hebel des Speichers S je Kalibriervariante (Standardfehler; Mitte-Stationen am selben Knoten gekoppelt)
    gruppe = {z: nm.STATIONEN[z] for z in ens.ziele}
    zufall = {g: rng.standard_normal(n) for g in sorted(set(gruppe.values()))}
    hm = {v: pd.read_csv(out / f"hebel_speicher_s_gemessen_{v}.csv", index_col=0).reindex(ens.ziele) for v in namen}
    hebel = np.column_stack([np.array([hm[v].loc[z, "Hebel [bar je 100 kg/s]"] for v in var_kal])
                             + np.array([hm[v].loc[z, "SE"] for v in var_kal]) * zufall[gruppe[z]] for z in ens.ziele])

    zeilen = []
    for var in VARIANTEN:
        ml = None if var == "quadratisch" else m_lin
        for fall, (P, west) in ae["faelle"].items():
            Pv = np.full(n, P)
            need = ens.bedarf(Pv, west, m_lin=ml)
            req = need.max(axis=1)
            dm = SPEICHER_MW * ens.mf
            req_s = ens.bedarf(Pv, west, "S", ml).max(axis=1)
            req_sued = ens.bedarf(Pv, west, "SUED_E", ml).max(axis=1)
            req_s_mess = (need - hebel * dm[:, None] / 100).max(axis=1)
            r4 = ens.reserve(P, west, 4.0, m_lin=ml)
            zeilen.append(pd.DataFrame({
                "Variante": var, "Fall": fall, "Kalibrierung": var_kal, "Lauf": np.arange(n), "Rücklauf [°C]": ens.t_rl, "Anteil Ost wie 2025": ens.lam_ost,
                "PS1-Gewinn [bar]": ens.ps1, "Mindest-Δp V06 [bar]": ens.v06,
                "erf. KWK-Δp [bar]": req, "maßgebend": np.array(ens.ziele)[need.argmax(axis=1)],
                "Reserve bis 4,0 bar": r4, "Reserve bis Pumpe": ens.reserve(P, west, ae["pumpe"], m_lin=ml),
                "Entlastung S, Modell [bar]": req - req_s, "Entlastung S, gemessene Hebel [bar]": req - req_s_mess,
                "Entlastung Südende, Modell [bar]": req - req_sued,
                "Reservegewinn S, Modell [Pp]": 100 * (ens.reserve(P, west, 4.0, "S", ml) - r4),
                "Reservegewinn S, gemessene Hebel [Pp]": 100 * (ens.reserve(P, west, 4.0, m_lin=ml, hebel=hebel) - r4),
                "Reservegewinn Südende, Modell [Pp]": 100 * (ens.reserve(P, west, 4.0, "SUED_E", ml) - r4)}))
    lf = pd.concat(zeilen, ignore_index=True)
    lf.to_csv(out / "unsicherheit_laeufe.csv", index=False)
    erg["laeufe"] = lf

    groessen = ["erf. KWK-Δp [bar]", "Reserve bis 4,0 bar", "Reserve bis Pumpe", "Entlastung S, Modell [bar]",
                "Entlastung S, gemessene Hebel [bar]", "Entlastung Südende, Modell [bar]", "Reservegewinn S, Modell [Pp]",
                "Reservegewinn S, gemessene Hebel [Pp]", "Reservegewinn Südende, Modell [Pp]"]
    q = lf.groupby(["Fall", "Variante"])[groessen].quantile([0.05, 0.5, 0.95]).unstack()
    q.columns = [f"{g} {'P5' if p == 0.05 else 'P50' if p == 0.5 else 'P95'}" for g, p in q.columns]
    erg["quantile"] = q
    q.to_csv(out / "unsicherheit_quantile.csv")
    qk = lf.groupby(["Fall", "Variante", "Kalibrierung"])[groessen].median()
    erg["median_je_kalibrierung"] = qk
    qk.to_csv(out / "unsicherheit_median_je_kalibrierung.csv")
    eingaben = ["Rücklauf [°C]", "Anteil Ost wie 2025", "PS1-Gewinn [bar]", "Mindest-Δp V06 [bar]"]
    erg["rang"] = pd.DataFrame({(fall, var): g[eingaben].corrwith(g["erf. KWK-Δp [bar]"], method="spearman")
                                for (fall, var), g in lf.groupby(["Fall", "Variante"])})
    erg["massgebend"] = lf.groupby(["Fall", "Variante"]).maßgebend.value_counts(normalize=True).unstack().fillna(0.0)
    erg["massgebend_je_kalibrierung"] = (lf.groupby(["Fall", "Kalibrierung"]).maßgebend.value_counts(normalize=True)
                                         .unstack().fillna(0.0))

    aussagen = {
        "F1: P50 erf. KWK-Δp ≤ 4,0 bar": ("P50", lf["erf. KWK-Δp [bar]"] <= 4.0),
        "F1: P90 erf. KWK-Δp ≤ 4,0 bar": ("P90", lf["erf. KWK-Δp [bar]"] <= 4.0),
        "F1: P90 erf. KWK-Δp ≤ Pumpengrenze": ("P90", lf["erf. KWK-Δp [bar]"] <= ae["pumpe"]),
        "F2: P90 Reserve bis Pumpengrenze ≥ 5 %": ("P90", lf["Reserve bis Pumpe"] >= 0.05),
        "F1: Mitte maßgebend (P50)": ("P50", lf["maßgebend"] != "V06"),
        "F3: Speicher S entlastet ≥ 0,2 bar (Modell)": ("P90", lf["Entlastung S, Modell [bar]"] >= 0.2),
        "F3: Speicher S entlastet ≥ 0,2 bar (gemessene Hebel)": ("P90", lf["Entlastung S, gemessene Hebel [bar]"] >= 0.2),
        "F3: Speicher S entlastet ≥ 0,15 bar (Modell und gemessene Hebel)": (
            "P90", (lf["Entlastung S, Modell [bar]"] >= 0.15) & (lf["Entlastung S, gemessene Hebel [bar]"] >= 0.15)),
        "F3: Speicher S bringt < 10 Pp Reserve (Modell)": ("P90", lf["Reservegewinn S, Modell [Pp]"] < 10),
        "F3: Südende bringt mehr Reserve als S (Modell)": ("P90", lf["Reservegewinn Südende, Modell [Pp]"]
                                                           > lf["Reservegewinn S, Modell [Pp]"]),
    }
    a = []
    for text, (fall, wahr) in aussagen.items():
        sel = lf.Fall == fall
        anteil = wahr[sel].groupby(lf.Variante[sel]).mean()
        je = wahr[sel].groupby([lf.Variante[sel], lf.Kalibrierung[sel]]).mean()
        a.append({"Aussage": text, **{f"Anteil {v}": anteil[v] for v in VARIANTEN},
                  "kleinster Anteil je Kalibrier- und Strukturvariante": je.min(),
                  "Bewertung": ("gestützt" if (je >= 0.9).all() else "widerlegt" if (je <= 0.1).all()
                                else "offen (< 90 % oder variantenabhängig)")})
    erg["aussagen"] = pd.DataFrame(a).set_index("Aussage")
    erg["aussagen"].to_csv(out / "unsicherheit_aussagen.csv")

    # Prüfung der Parameterunsicherheit: Streuung der Stationsvorhersage im Hochlast-Holdout gegen den tatsächlichen Fehler
    hold = ein["hold"]
    last = e["verbund"].reindex(f.index).to_numpy()
    hoch = hold & (last >= np.nanquantile(last[hold], 0.9))
    fh = f.teil(hoch)
    stationen = ["V03", "V10", "V12", "V23", "V24", "V06", "V22", "V15", "MVA"]
    def sim_lauf(x):
        K, gw, gl, vs = pr["zerlege"](x)
        return nm.simuliere(nz, fh, K, vs, gw, gl)[stationen].to_numpy()

    sims = np.array([sim_lauf(x) for x in xs[ref][:100]])
    K_hat, gw_hat, gl_hat, vs_hat = pr["zerlege"](x_hat[referenz])
    sim_hat = nm.simuliere(nz, fh, K_hat, vs_hat, gw_hat, gl_hat)[stationen]
    fehler = sim_hat - fh.ziele[stationen]
    erg["parameterstreuung"] = pd.DataFrame({"Streuung aus Parametern [bar]": np.nanmean(sims.std(axis=0), axis=0),
                                             "RMSE Holdout Hochlast [bar]": np.sqrt((fehler**2).mean())}, index=stationen)
    erg["parameterstreuung"].to_csv(out / "unsicherheit_parameterstreuung.csv")
    _bericht(erg, n_je, out)
    return erg


def _bericht(erg: dict, n_je: int, out) -> None:
    p = erg["parameter"].copy()
    for v in erg["varianten"]:
        log = p.index.str.startswith("log")
        p.loc[log, (v, "Faktor (1 SD)")] = np.exp(p.loc[log, (v, "Standardabweichung")])
    p = p.sort_index(axis=1)
    text = ["# Unsicherheitsläufe zum Auslegungsfall (automatisch erzeugt)", "",
            f"Kalibriervarianten {erg['varianten']} (Referenz {erg['referenz']}), je {n_je} Läufe je Strukturvariante und "
            f"Lastfall; Parameter aus der Laplace-Näherung je Variante, Rücklauf ± {SIGMA_RUECKLAUF_K} K, Ost zwischen "
            f"Plan A und 2025, PS1 P95–P99, V06-Mindest-Δp {V06_MINDEST}.", "",
            f"Kontrolle ohne Streuung (Referenz, Ost nach Plan A, V06 1,2 bar): erf. KWK-Δp {erg['kontrolle']}", "",
            "## Aussagen (Anteil der Läufe, in denen die Aussage gilt)", _md(erg["aussagen"].round(3)), "",
            "## Quantile", _md(erg["quantile"].T.round(3)), "",
            "## Median je Kalibriervariante", _md(erg["median_je_kalibrierung"].T.round(3)), "",
            "## Maßgebende Station (Anteil)", _md(erg["massgebend"].round(3)), "",
            _md(erg["massgebend_je_kalibrierung"].round(3)), "",
            "## Beiträge zur Streuung der erf. KWK-Δp (quadratisch)", _md(erg["beitrag"].round(3)), "",
            "## Rangkorrelation Eingangsgröße – erf. KWK-Δp", _md(erg["rang"].round(2)), "",
            "## Einflussreichste Parameter (nur Parameterstreuung, P90, Referenzvariante)",
            _md(erg["parameter_einfluss"].round(2)), "",
            "## Parameterstreuung gegen Holdout-Fehler (Referenzvariante)", _md(erg["parameterstreuung"].round(3)), "",
            "## Parameter (Laplace-Näherung je Kalibriervariante)", _md(p.round(3)), "",
            "## Knie der Strukturvariante (P95 je Kante, Heizperiode)", _md(erg["knie"].round(1))]
    (out / "unsicherheit_zusammenfassung.md").write_text("\n".join(text), encoding="utf-8")


if __name__ == "__main__":
    import sys

    main(neu_kovarianz="--neu" in sys.argv)
