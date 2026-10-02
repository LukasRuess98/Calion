"""Mehrfachstart der Kalibrierung: Ist das Optimum eindeutig?

Die Kalibrierung (``netzmodell.kalibriere``) ist ein nichtlineares Ausgleichsproblem mit 55 Parametern. Aus verschiedenen
Startwerten kann sie in verschiedenen lokalen Optima enden. Dieses Skript rechnet die Kalibrierung aus mehreren Starts:
* ``A``: Start bei der veröffentlichten Referenzkalibrierung (prüft, ob sie ein stationärer Punkt ist);
* ``B``: Start bei den Prior-Werten (alle Multiplikatoren 1, Gewichte 1, Grundlast und Versatz 0);
* ``C``, ``D``, ``E``: zufällige Starts (log-Multiplikatoren ~ N(0; 0,7), log-Gewichte ~ N(0; 0,2), Grundlast ~ N(0; 20 kg/s)).

Je Start werden die Parameter und die Kosten (Daten- und Prior-Anteil) gespeichert. Kalibrierungen, deren Kosten
höchstens ``TOLERANZ`` über dem besten Wert liegen, gelten als gleich gute **Kalibriervarianten**; Auslegung und
Unsicherheitsläufe werden mit allen gerechnet.

Aufruf: ``python -m scripts.dhn_study.mehrfachstart [A B C D E]`` (je Start ≈ 5–15 min). Ergebnisse:
``results/dhn_study/netzmodell/kalibrierungen/<Start>/`` und ``kalibrierungen/uebersicht.csv``. Die veröffentlichten
Varianten liegen unter ``scripts/dhn_study/kalibrierung/``.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from . import daten
from . import netzmodell as nm
from .run_netzmodell import (
    KALIBRIERUNG_REPO,
    KANTEN_SIGMA,
    PAAR_GEWICHT,
    kalibrier_eingaben,
    kalibrier_problem,
    lade_kalibrierung,
    speichere_kalibrierung,
)

STARTS = {"A": "Referenzkalibrierung", "B": "Prior-Werte", "C": "Zufall 1", "D": "Zufall 2", "E": "Zufall 3"}
TOLERANZ = 0.05            # relative Kostendifferenz, bis zu der eine Kalibrierung als gleich gut gilt


def startwert(name: str, nz: nm.Netz) -> dict | None:
    """Startwert der Kalibrierung für einen Start (``None`` = Prior-Werte)."""
    if name == "A":
        return lade_kalibrierung(KALIBRIERUNG_REPO / "A", nz)
    if name == "B":
        return None
    rng = np.random.default_rng({"C": 1, "D": 2, "E": 3}[name])
    return {"multiplikator": pd.Series(np.exp(rng.normal(0.0, 0.7, len(nz.kanten))), index=nz.kanten_ids),
            "gewichte": {g: float(np.exp(rng.normal(0.0, 0.2))) for g in nm.LASTGRUPPEN},
            "grundlast": {g: float(rng.normal(0.0, 20.0)) for g in nm.GRUNDLAST_GRUPPEN},
            "versatz": pd.Series(0.0, index=list(nm.STATIONEN))}


def kosten(pr: dict, kal: dict, n_prior: int) -> dict:
    """Kosten ½·Σr² der Kalibrierung, getrennt nach Daten- und Prior-Anteil."""
    r = pr["res"](pr["x_aus"](kal))
    return {"Kosten": 0.5 * float(np.sum(r**2)), "Kosten Daten": 0.5 * float(np.sum(r[:-n_prior] ** 2)),
            "Kosten Prior": 0.5 * float(np.sum(r[-n_prior:] ** 2))}


def uebersicht(ordner) -> pd.DataFrame:
    """Kosten aller vorhandenen Kalibrierungen in ``ordner`` (Unterordner je Start) und ob sie gleich gut sind."""
    zeilen = {p.name: pd.read_csv(p / "kosten.csv", index_col=0).iloc[:, 0] for p in sorted(ordner.iterdir())
              if (p / "kosten.csv").exists()}
    u = pd.DataFrame(zeilen).T
    for c in ("Kosten", "Kosten Daten", "Kosten Prior"):
        u[c] = pd.to_numeric(u[c])
    u["relativ zum besten"] = u["Kosten"] / u["Kosten"].min() - 1
    u["gleich gut"] = u["relativ zum besten"] <= TOLERANZ
    return u


def main(namen: list[str]) -> pd.DataFrame:
    out = daten.repo_root() / "results" / "dhn_study" / "netzmodell" / "kalibrierungen"
    out.mkdir(parents=True, exist_ok=True)
    m = daten.lade_messdaten()
    e = daten.erzeugung(m)
    ta = daten.lade_aussentemperatur()[0].reindex(m.index)
    nz = nm.netz()
    f = nm.randbedingungen(m, e, nz)
    ein = kalibrier_eingaben(m, e, ta, f)
    pr = kalibrier_problem(nz, ein)
    n_prior = len(pr["namen"])
    for name in namen:
        kal = nm.kalibriere(nz, ein["ft"], gewichtung=ein["gewichtung"], paar_gewicht=PAAR_GEWICHT, hebel=ein["hebel"],
                            kanten_sigma=KANTEN_SIGMA, start=startwert(name, nz))
        ziel = out / name
        ziel.mkdir(exist_ok=True)
        speichere_kalibrierung(kal, nz, ziel)
        pd.Series({"Start": STARTS[name], **kosten(pr, kal, n_prior), "konvergiert": kal["erfolg"]}).to_csv(ziel / "kosten.csv")
    u = uebersicht(out)
    u.to_csv(out / "uebersicht.csv")
    return u


if __name__ == "__main__":
    main(sys.argv[1:] or list(STARTS))
