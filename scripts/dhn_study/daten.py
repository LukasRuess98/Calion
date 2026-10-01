"""Anonymisierten Datensatz DHN-A laden, Signale prüfen und die Erzeugung korrigiert berechnen.

Datensatz: ``data/dhn_a/`` (siehe ``data/dhn_a/README.md``). Verbraucher heißen V01…V24, Erzeuger nach Typ.

Korrekturen gegenüber dem Studien-Notebook:
* ``gas_turbine_heat`` ist im gelieferten Export eine Kopie von ``boiler_plant_2_secondary_heat`` und wird
  verworfen. GT-Wärme = GT-Durchfluss · Δh (gemessen), Stillstand (T_VL < 60 °C) = 0, Rest imputiert über
  Δp und ΔT der GT (Regressionsmodell aus den gemessenen Stunden) und gekennzeichnet.
* Durchflüsse an Kundenstationen und Hauptleitungen sind t/h (Einheitentest), nicht m³/h.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MESSDATEN = "measurements_2025_hourly.parquet"
LASTGAENGE = "generation_profiles_2020_2022_hourly.csv"
TEMP_STUNDE = "ambient_temperature_hourly.parquet"
TEMP_TAG = "ambient_temperature_daily.csv"


def repo_root(start: Path | None = None) -> Path:
    """Repository-Wurzel (Ordner mit ``calion/`` und ``configs/``)."""
    start = Path(start or __file__).resolve()
    for p in [start, *start.parents]:
        if (p / "calion").is_dir() and (p / "configs").is_dir():
            return p
    raise FileNotFoundError("Repository-Wurzel nicht gefunden")


def daten_dir() -> Path:
    return repo_root() / "data" / "dhn_a"


# ---------------------------------------------------------------- Stoffwerte Wasser
def rho_w(T):
    """Dichte [kg/m³] nach Kell (1975), T in °C."""
    T = np.asarray(T, float)
    return (999.83952 + 16.945176 * T - 7.9870401e-3 * T**2 - 46.170461e-6 * T**3
            + 105.56302e-9 * T**4 - 280.54253e-12 * T**5) / (1 + 16.879850e-3 * T)


def cp_w(T):
    """Spezifische Wärmekapazität [kJ/(kg K)], gesättigtes Wasser, lineare Interpolation."""
    return np.interp(np.asarray(T, float), [0, 20, 40, 60, 80, 100, 120, 140, 160],
                     [4.217, 4.182, 4.179, 4.185, 4.197, 4.216, 4.245, 4.285, 4.339])


def dh(t_vl, t_rl):
    """Enthalpiedifferenz [kJ/kg] zwischen Vor- und Rücklauf."""
    t_vl, t_rl = np.asarray(t_vl, float), np.asarray(t_rl, float)
    return cp_w(0.5 * (t_vl + t_rl)) * (t_vl - t_rl)


# ---------------------------------------------------------------- Laden
def lade_messdaten(pfad: Path | None = None) -> pd.DataFrame:
    return pd.read_parquet(pfad or daten_dir() / MESSDATEN).sort_index()


def lade_verbraucher(pfad: Path | None = None) -> pd.DataFrame:
    return pd.read_csv(pfad or daten_dir() / "consumers.csv").set_index("id")


def lade_lastgaenge(pfad: Path | None = None) -> dict[int, pd.Series]:
    """Stündliche Erzeugungslastgänge 2020–2022 [MW], je Jahr ab dem 01.01. fortlaufend (2020 inkl. 29.02.)."""
    df = pd.read_csv(pfad or daten_dir() / LASTGAENGE)
    return {jahr: pd.Series(df[f"generation_MW_{jahr}"].to_numpy(float),
                            index=pd.date_range(f"{jahr}-01-01", periods=len(df), freq="h"), name=f"P_{jahr}")
            for jahr in (2020, 2021, 2022)}


def lade_aussentemperatur() -> tuple[pd.Series, pd.Series]:
    """(stündlich ab 2019, Tagesmittel ab 1955) in naiver Ortszeit [°C]."""
    h = pd.read_parquet(daten_dir() / TEMP_STUNDE)["T_ambient"]
    d = pd.read_csv(daten_dir() / TEMP_TAG, index_col=0, parse_dates=True)["T_ambient_daily_mean"]
    return h, d


# ---------------------------------------------------------------- Signalprüfungen
def identische_signale(df: pd.DataFrame, min_n: int = 500, anteil: float = 0.99, tol: float = 1e-9) -> list[tuple[str, str, int]]:
    """Paare von Spalten, die in ≥ ``anteil`` der gemeinsamen Stunden identisch sind (Export-/Zuordnungsfehler)."""
    num = df.select_dtypes("number")
    cols = list(num.columns)
    vals = num.to_numpy(float)
    paare = []
    for i, a in enumerate(cols):
        for j in range(i + 1, len(cols)):
            m = np.isfinite(vals[:, i]) & np.isfinite(vals[:, j])
            n = int(m.sum())
            if n >= min_n and (np.abs(vals[m, i] - vals[m, j]) < tol).mean() >= anteil:
                paare.append((a, cols[j], n))
    return paare


def haeufigster_wert(s: pd.Series) -> tuple[float, float]:
    """Häufigster Wert und sein Anteil (Hinweis auf Hängewerte)."""
    s = s.dropna()
    if s.empty:
        return np.nan, 0.0
    vc = s.value_counts()
    return float(vc.index[0]), float(vc.iloc[0] / len(s))


def einheitentest(q_mw: pd.Series, v: pd.Series, t_vl: pd.Series, t_rl: pd.Series,
                  q_min: float = 0.2, v_min: float = 2.0, dt_min: float = 8.0) -> dict[str, float]:
    """Median von Q_gemessen / Q_berechnet für drei Einheitenhypothesen des Durchflusses.

    1,00 bedeutet passende Einheit: ``t/h`` (Masse), ``m3/h@RL`` bzw. ``m3/h@VL`` (Volumen am Messort).
    """
    x = pd.concat([q_mw, v, t_vl, t_rl], axis=1, keys=["q", "v", "tv", "tr"]).dropna()
    x = x[(x.q > q_min) & (x.v > v_min) & (x.tv - x.tr > dt_min)]
    h = dh(x.tv, x.tr) / 1e3                                       # MJ/kg → MW je kg/s
    return {"n": float(len(x)),
            "t/h": float((x.q / (x.v / 3.6 * h)).median()),
            "m3/h@RL": float((x.q / (x.v * rho_w(x.tr) / 3600 * h)).median()),
            "m3/h@VL": float((x.q / (x.v * rho_w(x.tv) / 3600 * h)).median())}


# ---------------------------------------------------------------- Erzeugung
def gt_imputationsmodell(m: pd.DataFrame) -> dict:
    """Lineares Modell GT-Wärme ~ a + b·(p_VL − p_RL) + c·(T_VL − T_RL), angepasst auf die gemessenen Stunden."""
    q = m["gas_turbine_flow"] / 3.6 * dh(m["gas_turbine_T_supply"], m["gas_turbine_T_return"]) / 1e3
    x = pd.concat([q, m["gas_turbine_p_supply"] - m["gas_turbine_p_return"], m["gas_turbine_T_supply"] - m["gas_turbine_T_return"]],
                  axis=1, keys=["q", "dp", "dT"]).dropna()
    x = x[x.q > 0.5]
    A = np.c_[np.ones(len(x)), x.dp, x.dT]
    c = np.linalg.lstsq(A, x.q, rcond=None)[0]
    r2 = 1 - ((x.q - A @ c) ** 2).sum() / ((x.q - x.q.mean()) ** 2).sum()
    return {"koeff": c, "r2": float(r2), "n": len(x)}


def erzeugung(m: pd.DataFrame, t_stillstand: float = 60.0, hx_spitze: float = 40.0) -> pd.DataFrame:
    """Korrigierte Wärmeeinspeisung je Erzeuger [MW] und Summen.

    Spalten: gas_CHP, waste_incineration, biomass_CHP, gas_turbine, gt_quelle, boiler_plant_1, hx_west (Abgabe an das
    Sekundärnetz über WÜ), boilers_west, verbund (Einspeisung in das Verbundnetz), gesamt (+ Kessel Sekundärnetz).
    """
    gt_mess = m["gas_turbine_flow"] / 3.6 * dh(m["gas_turbine_T_supply"], m["gas_turbine_T_return"]) / 1e3
    model = gt_imputationsmodell(m)
    c = model["koeff"]
    gt_imp = (c[0] + c[1] * (m["gas_turbine_p_supply"] - m["gas_turbine_p_return"])
              + c[2] * (m["gas_turbine_T_supply"] - m["gas_turbine_T_return"])).clip(lower=0)
    still = m["gas_turbine_T_supply"] < t_stillstand
    gt = gt_mess.where(gt_mess.notna(), np.where(still, 0.0, gt_imp))
    quelle = np.where(gt_mess.notna(), "gemessen", np.where(still, "stillstand", np.where(gt_imp.notna(), "imputiert", "fehlend")))
    hw1 = m["boiler_plant_1_flow"] / 3.6 * dh(m["boiler_plant_1_T_supply"], m["boiler_plant_1_T_return"]) / 1e3
    hx = m["boiler_plant_2_hx_heat"].mask(m["boiler_plant_2_hx_heat"] > hx_spitze)
    kessel = (m["boiler_plant_2_secondary_heat"] - hx).clip(lower=0)
    out = pd.DataFrame({"gas_CHP": m["gas_CHP_heat"], "waste_incineration": m["waste_incineration_heat"],
                        "biomass_CHP": m["biomass_CHP_heat"], "gas_turbine": gt, "gt_quelle": quelle,
                        "boiler_plant_1": hw1, "hx_west": hx, "boilers_west": kessel}, index=m.index)
    out["verbund"] = out[["gas_CHP", "waste_incineration", "biomass_CHP", "gas_turbine"]].sum(axis=1, min_count=4) + out["boiler_plant_1"].fillna(0.0)
    out["gesamt"] = out["verbund"] + out["boilers_west"].fillna(0.0)
    out.attrs["gt_modell"] = model
    return out


def kunden_dp(m: pd.DataFrame) -> pd.DataFrame:
    """Kunden-Differenzdrücke [bar] je Verbraucher V..: ``_dp``-Signal, sonst ``_p_supply − _p_return``.

    Zusätzlich ``HX_West`` (Eintritt Wärmeübertrager zum Sekundärnetz).
    """
    out = {}
    ids = sorted({c.split("_")[0] for c in m.columns if c.startswith("V") and c[1:3].isdigit()})
    for v in ids:
        if f"{v}_dp" in m:
            out[v] = m[f"{v}_dp"]
        elif f"{v}_p_supply" in m and f"{v}_p_return" in m:
            out[v] = m[f"{v}_p_supply"] - m[f"{v}_p_return"]
    if "boiler_plant_2_hx_dp" in m:
        out["HX_West"] = m["boiler_plant_2_hx_dp"]
    df = pd.DataFrame(out)
    return df.where(df > 0.05)


def stationen(region_enthaelt: tuple[str, ...]) -> list[str]:
    """Verbraucher-IDs, deren Region einen der Begriffe enthält (aus ``consumers.csv``)."""
    v = lade_verbraucher()
    return [i for i, r in v.region.items() if any(t in r for t in region_enthaelt)]


# Referenzstationen der Auswertung (Regionen laut consumers.csv)
MITTE_STATIONEN = ["V03", "V10", "V12", "V23", "V24"]     # City, Mitte-L4, L1 – Stationen mit Δp-Messung
SUED_KRITISCH = "V06"                                   # kritischste Verbundstation (Süd)
SPEICHERSTANDORT = "V22"                                # Großkunde, Speicherstandort S
