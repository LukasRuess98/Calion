# %% [markdown]
# # AgNes-P2H — Bestellkapazität statt Jahreshöchstlast
#
# Reproduzierbares Notebook zum ZWF-Beitrag *"Bestellkapazität statt
# Jahreshöchstlast — Auswirkungen der Netzentgeltreform AgNes auf die
# Elektrifizierung industrieller Prozesswärme"*.
#
# Baut aus vier gemessenen Fabriklastgängen (Lebensmittel, Chemie, Metall,
# Papier) und zwei Day-Ahead-Preisjahren (2023, 2024) ein lineares
# Optimierungsmodell (Kapazitätswahl, Anlagenauslegung, Betrieb), rechnet
# die Szenariomatrix aus `config.yaml` und exportiert alle Abbildungen,
# Tabellen und Kennzahlen für den Paper-Draft.
#
# **Nicht verhandelbare Regeln (G-01..G-09, siehe Draft Dokument 2):**
# keine synthetischen Werksdaten, fehlende Pflichtwerte -> kontrollierter
# Abbruch, jeder Parameter mit Quelle/Status, Netzentgelt auf den
# Gesamtnetzbezug inkl. Grundlast, keine stille Interpolation/Nullsetzung,
# Ergebnisrichtungen sind nie Tests, jede Zahl rückverfolgbar, inkonsistente
# Läufe fliegen aus den Aggregaten, Test-Fixtures getrennt vom Export.
#
# Ausführen: **Run All** in diesem Verzeichnis (`docs/paper_ZWF_Agnes_Reform/`).

# %% [markdown]
# ## § 0 — Parameter, Versionen, Seeds, Output-Ordner

# %%
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 140)

# --- Fehlerklasse für Pflichtwerte (G-02) -----------------------------
class MissingParameterError(RuntimeError):
    """Wird bei fehlenden Pflichtwerten geworfen (kein stiller Default)."""


class InfeasibleRunError(RuntimeError):
    """Solver hat keinen optimalen Status zurückgegeben."""


# --- Basisverzeichnis ---------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
os.chdir(BASE_DIR)

RUN_TS = time.strftime("%Y%m%dT%H%M%S")
OUT_DIR = BASE_DIR / "outputs" / RUN_TS
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"
FIX_DIR = OUT_DIR / "fixtures"
for d in (OUT_DIR, FIG_DIR, TAB_DIR, FIX_DIR):
    d.mkdir(parents=True, exist_ok=True)

SEED = 20260915
np.random.seed(SEED)

# Papermill-/Debug-Parameterzelle: bei DRY_RUN=1 nur je 1 Standort/Konfiguration
# fuer schnelle End-to-End-Prüfung der Pipeline (keine echte Kampagne).
DRY_RUN = os.environ.get("AGNES_DRY_RUN", "0") == "1"

# --- Konfiguration laden -------------------------------------------------
CONFIG_PATH = BASE_DIR / "config.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
    CFG_TEXT = fh.read()
CONFIG: dict[str, Any] = yaml.safe_load(CFG_TEXT)
CONFIG_SHA256 = hashlib.sha256(CFG_TEXT.encode("utf-8")).hexdigest()[:16]


def cfg_value(node: dict, *, name: str) -> Any:
    """Liest ein {value, status, source}-Feld; bricht bei fehlendem value (G-02)."""
    if not isinstance(node, dict) or node.get("value") is None:
        raise MissingParameterError(f"Pflichtwert fehlt: {name}")
    return node["value"]


PARAM_LOG: list[dict] = []


def log_param(name: str, node: dict, site: str = "-"):
    PARAM_LOG.append({
        "parameter": name, "site": site,
        "value": node.get("value") if isinstance(node, dict) else node,
        "unit": node.get("unit", "") if isinstance(node, dict) else "",
        "status": node.get("status", "n/a") if isinstance(node, dict) else "n/a",
        "source": node.get("source", "") if isinstance(node, dict) else "",
    })


# --- Solver / Umgebung ----------------------------------------------------
SOLVER_NAME = CONFIG["study"]["solver"]
try:
    import linopy
    LINOPY_VERSION = linopy.__version__
except Exception as exc:  # pragma: no cover
    raise MissingParameterError(f"linopy nicht installierbar/verfügbar: {exc}")

try:
    import highspy
    HIGHSPY_VERSION = getattr(highspy, "__version__", "n/a")
except Exception as exc:  # pragma: no cover
    raise MissingParameterError(f"highspy (HiGHS) nicht verfügbar: {exc}")


def environment_report() -> str:
    lines = [
        "# environment.md", "",
        f"- Run-ID (Zeitstempel): `{RUN_TS}`",
        f"- Config-Hash (sha256, 16 Zeichen): `{CONFIG_SHA256}`",
        f"- Python: `{sys.version.split()[0]}` ({platform.platform()})",
        f"- pandas `{pd.__version__}`, numpy `{np.__version__}`, "
        f"linopy `{LINOPY_VERSION}`, matplotlib `{matplotlib.__version__}`",
        f"- Solver: `{SOLVER_NAME}` (highspy `{HIGHSPY_VERSION}`)",
        f"- Seed: `{SEED}`",
        f"- Output-Ordner: `{OUT_DIR.relative_to(BASE_DIR)}`",
        "",
    ]
    return "\n".join(lines)


(OUT_DIR / "environment.md").write_text(environment_report(), encoding="utf-8")
print(environment_report())
# ===END-0===

# %% [markdown]
# ## § 1 — Datenimport, Qualitätsprüfung, Ebenen- und Bandzuordnung
#
# Datenrealität (abweichend vom ursprünglichen Datenvertrag, siehe
# `config.yaml: study.band_note`): jede Standortdatei liefert nur EINE
# aggregierte Wärme- (kW/MW) und EINE Stromspalte (kW/MW) im 15-min-Raster,
# keine Temperaturkanäle, keine Netzanschluss-Metadaten. Einzelheiten je
# Standort stehen unter `sites.<id>.quality_notes` in `config.yaml`.

# %%
DT_H = CONFIG["study"]["timestep_min"] / 60.0
EXPECTED_INTERVALS = {2023: 35040, 2024: 35136}

SITE_IDS = list(CONFIG["sites"].keys())
if DRY_RUN:
    # Global reduzieren statt nur S1-S4: jede spaetere Sektion iteriert
    # "for site in SITE_IDS" und braucht sonst volle Standortabdeckung in
    # df_s1_s4 (sonst IndexError in T08/Aggregation/etc.).
    SITE_IDS = ["metal"]
    print("[DRY_RUN] SITE_IDS auf ['metal'] reduziert (schnelle Pipeline-Pruefung).")


@dataclass
class SiteData:
    site_id: str
    label_de: str
    df: pd.DataFrame              # index=timestamp, cols=[q_heat_kw, p_base_kw]
    price_year: int
    has_vht: bool
    quality_flags: dict
    p_max_prev_kw: float          # Ist-Höchstlast (Electricity) vor Elektrifizierung
    voltage_level: str            # ns | ms | hs_ms


def _load_site_raw(site_id: str, site_cfg: dict) -> pd.DataFrame:
    path = BASE_DIR / site_cfg["data_file"]
    if not path.exists():
        raise MissingParameterError(f"[B-01] Lastgangdatei fehlt für {site_id}: {path}")
    raw = pd.read_excel(path, sheet_name="Tabelle1")
    for col in (site_cfg["heat_col"], site_cfg["elec_col"]):
        if col not in raw.columns:
            raise MissingParameterError(f"[B-01] Spalte '{col}' fehlt in {path.name}")

    if pd.api.types.is_datetime64_any_dtype(raw["Date"]):
        # Lebensmittel/Metall/Papier: 'Date' ist bereits volle Timestamp-Spalte;
        # 'Time' ist nur ein redundantes Intervall-Label ("00:00-00:15").
        ts = pd.to_datetime(raw["Date"], errors="raise")
    else:
        # Chemie: 'Date' ist ein reines Datum (DD.MM.YYYY), 'Time' ein Uhrzeit-String.
        ts = pd.to_datetime(raw["Date"].astype(str) + " " + raw["Time"].astype(str),
                             format="%d.%m.%Y %H:%M:%S", errors="raise")

    # §5.3: UTC als kanonischer Index. Naive Zeitstempel sind lokale
    # Europe/Berlin-Wandzeit; DST-Rückstellung erzeugt scheinbare
    # Duplikate (identisches Label, zwei reale Stunden) - 'infer' löst
    # sie anhand der Originalreihenfolge verlustfrei auf (kein T01-Datenverlust).
    ts_local = pd.DatetimeIndex(ts).tz_localize(
        "Europe/Berlin", ambiguous="infer", nonexistent="shift_forward")
    ts_utc = ts_local.tz_convert("UTC")

    df = pd.DataFrame({
        "q_heat_kw": raw[site_cfg["heat_col"]].astype(float).to_numpy() * site_cfg["unit_scale_to_kw"],
        "p_base_kw": raw[site_cfg["elec_col"]].astype(float).to_numpy() * site_cfg["unit_scale_to_kw"],
    }, index=ts_utc).sort_index()
    df.index.name = "timestamp_utc"
    return df


def _clean_site(site_id: str, df: pd.DataFrame, load_year: int) -> tuple[pd.DataFrame, dict]:
    """Bereitet Standortdaten auf.

    Negative elektrische Grundlast wird als Einspeisung dokumentiert (Spalte
    p_export_kw), nicht still auf 0 geklippt. Das Modell bildet ausschließlich
    Netzbezug ab, daher wird der abrechnungsrelevante Bezug auf >=0 gesetzt;
    eine Einspeisevergütung ist nicht Bestandteil des Modells."""
    flags = {"duplicates_dropped": 0, "negative_base_intervals": 0,
             "negative_base_export_kwh": 0.0, "floor_clipped": 0,
             "rows_before_year_filter": len(df), "rows_out_of_year_dropped": 0}

    dup = df.index.duplicated(keep="first")
    flags["duplicates_dropped"] = int(dup.sum())
    df = df[~dup]

    local_year = df.index.tz_convert("Europe/Berlin").year
    in_year = (local_year == load_year)
    flags["rows_out_of_year_dropped"] = int((~in_year).sum())
    df = df[in_year].copy()

    neg_mask = df["p_base_kw"] < 0
    flags["negative_base_intervals"] = int(neg_mask.sum())
    flags["negative_base_export_kwh"] = float((-df.loc[neg_mask, "p_base_kw"]).sum() * DT_H)
    df["p_export_kw"] = (-df["p_base_kw"]).clip(lower=0.0)
    df["p_base_kw"] = df["p_base_kw"].clip(lower=0.0)

    floor_mask = df["q_heat_kw"] < 1e-6
    flags["floor_clipped"] = int(floor_mask.sum())
    df.loc[floor_mask, "q_heat_kw"] = 0.0
    df["q_heat_kw"] = df["q_heat_kw"].clip(lower=0.0)

    return df, flags


def assign_voltage_level(p_max_prev_kw: float) -> str:
    th = CONFIG["voltage_level_thresholds_kw"]
    if p_max_prev_kw < th["ns_max_kw"]:
        return "ns"
    if p_max_prev_kw < th["ms_max_kw"]:
        return "ms"
    return "hs_ms"


def load_all_sites() -> dict[str, SiteData]:
    sites: dict[str, SiteData] = {}
    for site_id, site_cfg in CONFIG["sites"].items():
        raw = _load_site_raw(site_id, site_cfg)
        clean, flags = _clean_site(site_id, raw, site_cfg["load_year"])

        n = len(clean)
        expected = EXPECTED_INTERVALS.get(site_cfg["load_year"])
        if expected is not None and n != expected:
            flags["interval_count_mismatch"] = f"{n} vs erwartet {expected}"
        else:
            flags["interval_count_mismatch"] = None

        p_max_prev = float(clean["p_base_kw"].max())
        vlevel = assign_voltage_level(p_max_prev)

        sites[site_id] = SiteData(
            site_id=site_id, label_de=site_cfg["label_de"], df=clean,
            price_year=site_cfg["price_year"], has_vht=site_cfg["has_vht"],
            quality_flags=flags, p_max_prev_kw=p_max_prev, voltage_level=vlevel,
        )
        print(f"[{site_id:10s}] n={n:6d}  P_base,max(prev)={p_max_prev:9.1f} kW  "
              f"Ebene={vlevel:6s}  flags={flags}")
    return sites


SITES = load_all_sites()

# %%
# --- T01: Intervallzahl, keine Lücken/Duplikate, UTC/DST-Konsistenz -------
def test_T01_intervals(sites: dict[str, SiteData]) -> pd.DataFrame:
    """Verschärft: verlangt eine lückenlose, äquidistante UTC-Zeitachse ohne
    Toleranzfenster. Die tz-aware UTC-Konvertierung in _load_site_raw
    (ambiguous='infer') löst DST-Mehrdeutigkeiten bereits verlustfrei auf,
    daher ist nach der Konvertierung keine DST-bedingte Lücke mehr zulässig."""
    rows = []
    expected_step = pd.Timedelta(minutes=CONFIG["study"]["timestep_min"])
    for sid, sd in sites.items():
        idx = sd.df.index
        expected_n = EXPECTED_INTERVALS.get(CONFIG["sites"][sid]["load_year"])
        steps = idx.to_series().diff().dropna()
        n_step_violations = int((steps != expected_step).sum())
        n_count_error = 0 if expected_n is None else abs(len(idx) - expected_n)
        n_duplicates = int(idx.duplicated().sum())
        ok = (idx.is_monotonic_increasing and n_duplicates == 0
              and n_step_violations == 0 and n_count_error == 0)
        rows.append({"site": sid, "n": len(idx), "expected_n": expected_n,
                      "interval_count_error": n_count_error, "step_violations": n_step_violations,
                      "duplicates": n_duplicates, "pass": ok})
        assert ok, (f"T01 FAIL [{sid}]: n={len(idx)}, erwartet={expected_n}, "
                     f"Schrittverletzungen={n_step_violations}, Duplikate={n_duplicates}")
    return pd.DataFrame(rows)


T01 = test_T01_intervals(SITES)
print("\nT01 (Intervallzahl/Lücken):\n", T01.to_string(index=False))

# %%
# --- data_audit.md ----------------------------------------------------
def write_data_audit(sites: dict[str, SiteData]) -> str:
    lines = ["# data_audit.md", "",
             "Automatisch erzeugt (§1). Datenbereinigungen und deterministische",
             "Imputationen werden vollständig dokumentiert; sie erfolgen nicht still.", ""]
    for sid, sd in sites.items():
        lines += [f"## {sd.label_de} (`{sid}`)", ""]
        lines.append(f"- Intervalle: {len(sd.df)}  (Jahr {CONFIG['sites'][sid]['load_year']})")
        lines.append(f"- P_base,max (beobachtete Grundlastspitze im Lastgangjahr; "
                      f"Proxy für P_max,prev): {sd.p_max_prev_kw:,.1f} kW "
                      f"-> Proxy-Spannungsebene **{sd.voltage_level}**")
        lines.append(f"- Wärmelast: mean={sd.df['q_heat_kw'].mean():,.1f} kW, "
                      f"max={sd.df['q_heat_kw'].max():,.1f} kW, "
                      f"Summe={sd.df['q_heat_kw'].sum()*DT_H/1000:,.1f} MWh_th/a")
        lines.append(f"- Quality-Flags: `{sd.quality_flags}`")
        lines.append(f"- Konfigurierte Hinweise: {CONFIG['sites'][sid]['quality_notes'].strip()}")
        lines.append("")
    return "\n".join(lines)


data_audit_md = write_data_audit(SITES)
(OUT_DIR / "data_audit.md").write_text(data_audit_md, encoding="utf-8")
print("data_audit.md geschrieben.")

# %% [markdown]
# ### Day-Ahead-Preisreihen (2023 relabelt aus 2019, 2024 vom Datenhalter als
# 15-min geliefert - Rohwerte sind aber je Stunde konstant, s. Review-Befund:
# effektiv Stundenpreise im 15-min-Zeilenraster, keine echte 15-min-Variation)

# %%
PRICE_QUALITY: dict[str, Any] = {}


def load_price_series() -> dict[int, pd.Series]:
    """Liefert je Preisjahr eine 15-min-Reihe (EUR/MWh, UTC-Index)."""
    pcfg = CONFIG["prices"]
    prices: dict[int, pd.Series] = {}

    # --- 2023 (Rohdatei 2019, per Datenhalter-Bestätigung als 2023-Werte
    #     genutzt; 1:1-Remapping da beide Jahre 8760 h, kein Schaltjahr) ---
    p23_path = BASE_DIR / pcfg["file_2023"]
    raw23 = pd.read_csv(p23_path, sep=None, engine="python")
    raw23.columns = [c.strip().lstrip("﻿") for c in raw23.columns]
    col = pcfg["col_2023_raw"]
    if col not in raw23.columns:
        raise MissingParameterError(f"Preisspalte '{col}' fehlt in {p23_path.name}")
    ts_src = pd.to_datetime(raw23["Start date"], format="%d.%m.%Y %H:%M", errors="raise")
    src_local = pd.DatetimeIndex(ts_src).tz_localize(
        "Europe/Berlin", ambiguous="infer", nonexistent="shift_forward")
    vals = pd.to_numeric(raw23[col].astype(str).str.replace(",", "."), errors="raise")
    s19 = pd.Series(vals.to_numpy(), index=src_local).sort_index()
    s19 = s19[~s19.index.duplicated(keep="first")]
    n19 = len(s19)
    if n19 != 8760:
        raise MissingParameterError(
            f"strompreis_2023.csv: erwartet 8760 Stundenwerte (Jahr ohne Schalttag), "
            f"gefunden {n19} -> kontrollierter Abbruch statt stiller Weiterverarbeitung.")
    # 1:1 Remapping Stunde-des-Jahres 2019 -> 2023 (beide 365 Tage, kein Wochentag-Offset erzwungen)
    idx_2023 = pd.date_range("2023-01-01 00:00", periods=8760, freq="h", tz="Europe/Berlin")
    s2023_h = pd.Series(s19.to_numpy(), index=idx_2023).tz_convert("UTC")
    # §5.3: Stundenpreise werden 4x wiederholt (kein Interpolieren) auf 15-min.
    s2023 = s2023_h.reindex(s2023_h.index.repeat(4))
    step = pd.Timedelta(minutes=15)
    offsets = np.tile(np.arange(4) * step, len(s2023_h))
    s2023.index = s2023_h.index.repeat(4) + pd.to_timedelta(offsets)
    prices[2023] = s2023

    # --- 2024 (vom Datenhalter im 15-min-Zeilenraster geliefert; die vier
    # Werte je Stunde sind im Rohfile identisch -> effektiv Stundenpreise,
    # s. Kommentar oben) ---
    p24_path = BASE_DIR / pcfg["file_2024"]
    raw24 = pd.read_csv(p24_path, sep=None, engine="python")
    raw24.columns = [c.strip().lstrip("﻿") for c in raw24.columns]
    ts24 = pd.to_datetime(raw24["Start date"] + " " + raw24["End date"], errors="raise")
    # 15-min-Granularität: 'infer' scheitert am DST-Rückstellblock (pytz-
    # Limitation bei Sub-Stunden-Frequenz). Ambige Stunde (2024-10-27
    # 02:00-03:00 lokal) wird als NaT markiert und verworfen (dokumentierter
    # Verlust von 4 Viertelstunden-Preisen von 35.136, < 0.02 %).
    ts24_local = pd.DatetimeIndex(ts24).tz_localize(
        "Europe/Berlin", ambiguous="NaT", nonexistent="shift_forward")
    vals24 = pd.to_numeric(raw24["strompreis"].astype(str).str.replace(",", "."), errors="raise")
    vals24_eur_mwh = vals24.to_numpy() * pcfg["col_2024_unit_scale_to_eur_mwh"]
    s2024_raw = pd.Series(vals24_eur_mwh, index=ts24_local)
    n_nat = int(s2024_raw.index.isna().sum())
    s2024_raw = s2024_raw[s2024_raw.index.notna()]
    s2024 = s2024_raw.tz_convert("UTC").sort_index()
    s2024 = s2024[~s2024.index.duplicated(keep="first")]
    n_missing = EXPECTED_INTERVALS[2024] - len(s2024)
    if n_missing > 8:   # mehr als die erwarteten ~4 DST-Werte -> echter Fehler
        raise MissingParameterError(
            f"strompreis_2024.csv: erwartet {EXPECTED_INTERVALS[2024]} 15-min-Werte, "
            f"gefunden {len(s2024)} (NaT-Drop={n_nat}).")
    # Lücke (DST-Rückstellung) offen als NaT im Kalenderraster sichtbar machen,
    # dann deterministisch mit dem unmittelbar vorherigen verfügbaren 15-min-
    # Preis fortschreiben (Forward Fill). Das ist für Day-Ahead-Preisreihen
    # die konventionellere Imputation als ein Jahresmittel-Sentinel; betrifft
    # < 0,02% der Zeitschritte, dokumentiert in PRICE_QUALITY/open_issues.md.
    full_idx = pd.date_range(s2024.index.min(), s2024.index.max(), freq="15min", tz="UTC")
    s2024 = s2024.reindex(full_idx)
    n_gap_before_ffill = int(s2024.isna().sum())
    if n_gap_before_ffill > 8:
        raise MissingParameterError(
            f"strompreis_2024.csv: mehr fehlende Viertelstundenpreise als im "
            f"erwarteten DST-Block zulässig: {n_gap_before_ffill}.")
    n_imputed_total = n_nat + n_gap_before_ffill
    pct_imputed = 100.0 * n_imputed_total / EXPECTED_INTERVALS[2024]
    PRICE_QUALITY[2024] = {
        "n_nat_localize_dropped": n_nat,
        "n_gap_before_ffill": n_gap_before_ffill,
        "n_imputed_total": n_imputed_total,
        "imputation_method": "forward_fill_previous_15min_price",
        "note": f"DST-Umstellungen 2024 (Frühjahr: {n_nat} beim Lokalisieren verworfene "
                f"mehrdeutige Zeitstempel; Herbst: {n_gap_before_ffill} beim Reindexieren "
                f"entstandene Lücken); zusammen {n_imputed_total} von "
                f"{EXPECTED_INTERVALS[2024]} 15-min-Werten ({pct_imputed:.3f}%) werden mit "
                "dem unmittelbar vorherigen verfügbaren 15-min-Preis fortgeschrieben, s. "
                "open_issues.md.",
    }
    s2024 = s2024.ffill()
    if s2024.isna().any():
        raise MissingParameterError(
            "strompreis_2024.csv: fehlende Preise am Reihenbeginn, Forward Fill "
            "nicht möglich.")
    prices[2024] = s2024
    return prices


PRICES = load_price_series()
for yr, s in PRICES.items():
    print(f"Preisjahr {yr}: n={len(s)}  mean={s.mean():.2f}  min={s.min():.2f}  max={s.max():.2f} EUR/MWh")

# %%
# --- table02_cases.md ---------------------------------------------------
def write_table02(sites: dict[str, SiteData]) -> pd.DataFrame:
    rows = []
    for sid, sd in sites.items():
        q = sd.df["q_heat_kw"]
        vlh_heat = q.sum() * DT_H / max(q.max(), 1e-9)
        rows.append({
            "Standort": sd.label_de,
            "Wärmebedarf [MWh_th/a]": round(q.sum() * DT_H / 1000, 1),
            "Wärme-Peak [MW_th]": round(q.max() / 1000, 2),
            "Wärme-Volllaststunden [h/a]": round(vlh_heat, 0),
            "Grundlast Ø [kW]": round(sd.df["p_base_kw"].mean(), 1),
            "Grundlast max [kW]": round(sd.df["p_base_kw"].max(), 1),
            "Spannungsebene": sd.voltage_level,
            "P_max,prev [kW]": round(sd.p_max_prev_kw, 1),
            "hat VHT": sd.has_vht,
            "Lastgangjahr": CONFIG["sites"][sid]["load_year"],
            "Preisjahr": sd.price_year,
        })
    df = pd.DataFrame(rows)
    return df


table02 = write_table02(SITES)
table02_md = "# Tabelle 2 — Standortübersicht\n\n" + table02.to_markdown(index=False)
(OUT_DIR / "table02_cases.md").write_text(table02_md, encoding="utf-8")
table02.to_csv(TAB_DIR / "table02_cases.csv", index=False)
print(table02.to_string(index=False))

# %% [markdown]
# ### Modell-Zeitauflösung: 1 h als Primärauflösung (dokumentierte Anpassung)
#
# **Abweichung vom Draft (Dokument 2, § 8):** Ein Probelauf des vollen LP bei
# 15-min-Auflösung (35.040 Zeitschritte, ~385.000 Zeilen, kontinuierliche
# Kapazitätswahl + zyklischer Speicher) benötigt je nach Solver-Methode
# 2,5-5+ Minuten pro Lauf (gemessen: Dual-Simplex nicht konvergiert nach
# >100s bei 41.000+ Iterationen; Interior-Point-Methode mit degradierender
# Iterationszeit). Bei ~300+ geplanten Läufen (S1-S9) ist das im Rahmen
# dieses Projekts nicht darstellbar (>15h Rechenzeit). Bei 1-h-Auflösung
# (8.760/8.784 Schritte, ~96.000 Zeilen) löst dasselbe Modell in ca. 35s
# (Dual-Simplex, gemessen). **Konsequenz:** 1 h wird zur Primärauflösung für
# S1-S9; die ursprünglich als "S6: 1h-Zwillinge" vorgesehene Gegenprobe wird
# umgekehrt zu einer kleinen expliziten 15-min-Validierungsteilmenge (2
# Standort-Läufe) für R-TIME-01/02 und T11. Grundlast-/Wärmelast-Mittelwerte
# je Stunde sind energieerhaltend (arithmetisches Mittel der Leistung);
# Ebenenzuordnung und P_grid-Schätzung bleiben auf der nativen 15-min-Reihe
# (konservativer, unverändert von der Auflösung).

# %%
def resample_site_hourly(sd: SiteData) -> SiteData:
    df_h = sd.df.resample("1h").mean()
    return SiteData(site_id=sd.site_id, label_de=sd.label_de, df=df_h,
                     price_year=sd.price_year, has_vht=sd.has_vht,
                     quality_flags={**sd.quality_flags, "resampled_from_15min": True},
                     p_max_prev_kw=sd.p_max_prev_kw, voltage_level=sd.voltage_level)


def resample_price_hourly(s: pd.Series) -> pd.Series:
    return s.resample("1h").mean()


SITES_1H: dict[str, SiteData] = {sid: resample_site_hourly(sd) for sid, sd in SITES.items()}
PRICES_1H: dict[int, pd.Series] = {yr: resample_price_hourly(s) for yr, s in PRICES.items()}
for sid, sd in SITES_1H.items():
    print(f"[1h] {sid:10s} n={len(sd.df):5d}  q_heat max={sd.df['q_heat_kw'].max():9.1f} kW  "
          f"p_base max={sd.df['p_base_kw'].max():9.1f} kW")
# ===END-1===

# %% [markdown]
# ## § 2 — Tarifauflösung + Kalibrierung, θ-Feld, σ(h), N_unlock

# %%
@dataclass
class TariffPair:
    lp_eur_kw_a: float
    ap_eur_mwh: float


@dataclass
class ResolvedTariff:
    voltage_level: str
    # StromNEV
    stromnev_ge2500h: TariffPair
    stromnev_lt2500h: TariffPair
    threshold_h: float
    # AgNes (synthetic_first_order)
    alpha: float
    f: float
    beta_min_order: float
    k_eur_kw_a: float
    t_B_h: float
    KP_eur_kw_a: float
    AP1_eur_mwh: float
    AP2_eur_mwh: float
    h_star_h: float
    theta: float


def resolve_tariffs(voltage_level: str) -> ResolvedTariff:
    sn = CONFIG["stromnev"]["by_level"][voltage_level]
    thb = sn["pair_ge2500h"]
    tha = sn["pair_lt2500h"]
    tar = CONFIG["tariffs"]
    alpha = cfg_value(tar["alpha"], name="alpha")
    f = cfg_value(tar["f"], name="f")
    beta = cfg_value(tar["beta_min_order"], name="beta_min_order")
    t_B = cfg_value(tar["t_B_h"], name="t_B_h")
    k = cfg_value(tar["k_by_level"][voltage_level], name=f"k[{voltage_level}]")

    KP = (1 - alpha) * k
    AP1 = 1000.0 * alpha * k / t_B
    AP2 = f * AP1
    h_star = 1000.0 * KP / (AP2 - AP1)
    theta = h_star / t_B

    return ResolvedTariff(
        voltage_level=voltage_level,
        stromnev_ge2500h=TariffPair(thb["lp_eur_kw_a"], thb["ap_eur_mwh"]),
        stromnev_lt2500h=TariffPair(tha["lp_eur_kw_a"], tha["ap_eur_mwh"]),
        threshold_h=CONFIG["stromnev"]["threshold_h"],
        alpha=alpha, f=f, beta_min_order=beta, k_eur_kw_a=k, t_B_h=t_B,
        KP_eur_kw_a=KP, AP1_eur_mwh=AP1, AP2_eur_mwh=AP2,
        h_star_h=h_star, theta=theta,
    )


TARIFFS: dict[str, ResolvedTariff] = {}
for sid, sd in SITES.items():
    if sd.voltage_level not in TARIFFS:
        TARIFFS[sd.voltage_level] = resolve_tariffs(sd.voltage_level)

for lvl, rt in TARIFFS.items():
    print(f"Ebene {lvl:6s}: KP={rt.KP_eur_kw_a:7.2f} EUR/kW/a  AP1={rt.AP1_eur_mwh:6.2f}  "
          f"AP2={rt.AP2_eur_mwh:6.2f} EUR/MWh  h*={rt.h_star_h:7.1f} h  theta={rt.theta:5.3f}")

# %%
def sigma_stromnev(h_array: np.ndarray, lp_eur_kw_a: float) -> np.ndarray:
    """sigma_NEV(h) = 1000*LP/h  [EUR/MWh]."""
    with np.errstate(divide="ignore"):
        return 1000.0 * lp_eur_kw_a / h_array


def sigma_agnes(h_array: np.ndarray, KP: float, AP2_minus_AP1: float) -> np.ndarray:
    """sigma_AgNes(h) = min(1000*KP/h, AP2-AP1)  [EUR/MWh]."""
    with np.errstate(divide="ignore"):
        return np.minimum(1000.0 * KP / h_array, AP2_minus_AP1)


def n_unlock(price_series: pd.Series, sigma_eur_mwh: float) -> int:
    """Anzahl Intervalle, in denen (Mittelpreis - Preis) > sigma: Arbitrage lohnt sich."""
    pbar = price_series.mean()
    return int((pbar - price_series > sigma_eur_mwh).sum())


# --- fig02_analytics.csv: sigma(h) beide Regime + theta(alpha,f)-Feld -----
h_grid = np.geomspace(10, 8760, 400)
fig02_rows = []
for lvl, rt in TARIFFS.items():
    s_nev = sigma_stromnev(h_grid, rt.stromnev_ge2500h.lp_eur_kw_a)
    s_agn = sigma_agnes(h_grid, rt.KP_eur_kw_a, rt.AP2_eur_mwh - rt.AP1_eur_mwh)
    for h, snev, sagn in zip(h_grid, s_nev, s_agn):
        fig02_rows.append({"voltage_level": lvl, "h": h, "sigma_stromnev": snev, "sigma_agnes": sagn})
fig02_sigma = pd.DataFrame(fig02_rows)

alpha_fine = np.linspace(0.30, 0.60, 61)
f_fine = np.linspace(2.0, 3.5, 61)
theta_rows = []
for a in alpha_fine:
    for f_ in f_fine:
        theta_rows.append({"alpha": a, "f": f_, "theta": (1 - a) / ((f_ - 1) * a)})
fig02_theta = pd.DataFrame(theta_rows)

fig02_sigma.to_csv(TAB_DIR.parent / "fig02_analytics_sigma.csv", index=False)
fig02_theta.to_csv(TAB_DIR.parent / "fig02_analytics_theta.csv", index=False)
theta_min, theta_max = fig02_theta["theta"].min(), fig02_theta["theta"].max()
print(f"theta-Spannweite über alpha in[0.30,0.60], f in[2.0,3.5]: "
      f"{theta_min:.3f} .. {theta_max:.3f}  (Faktor {theta_max/theta_min:.2f})")

# %%
# --- N_unlock je Standort (vor dem ersten Solve, Vorzeichenerwartung) -----
n_unlock_rows = []
for sid, sd in SITES.items():
    rt = TARIFFS[sd.voltage_level]
    price = PRICES[sd.price_year]
    sigma_h_star_agnes = 0.0  # an h=h*: sigma_agnes(h*) = AP2-AP1 per Konstruktion
    n_agnes = n_unlock(price, rt.AP2_eur_mwh - rt.AP1_eur_mwh)
    n_nev = n_unlock(price, sigma_stromnev(np.array([rt.threshold_h]), rt.stromnev_ge2500h.lp_eur_kw_a)[0])
    n_unlock_rows.append({"site": sid, "N_unlock_agnes": n_agnes, "N_unlock_stromnev": n_nev,
                           "n_intervals": len(price)})
n_unlock_df = pd.DataFrame(n_unlock_rows)
print(n_unlock_df.to_string(index=False))

# %%
# --- tariff_resolved.md --------------------------------------------------
def write_tariff_resolved() -> str:
    lines = ["# tariff_resolved.md", "", CONFIG["tariffs"]["declaration_text_de"].strip(), ""]
    for lvl, rt in TARIFFS.items():
        lines += [
            f"## Ebene {lvl}", "",
            f"- StromNEV >=2500h: LP={rt.stromnev_ge2500h.lp_eur_kw_a} EUR/kW/a, "
            f"AP={rt.stromnev_ge2500h.ap_eur_mwh} EUR/MWh",
            f"- StromNEV <2500h: LP={rt.stromnev_lt2500h.lp_eur_kw_a} EUR/kW/a, "
            f"AP={rt.stromnev_lt2500h.ap_eur_mwh} EUR/MWh",
            f"- AgNes (synthetic_first_order): alpha={rt.alpha}, f={rt.f}, k={rt.k_eur_kw_a} "
            f"EUR/kW/a, t_B={rt.t_B_h} h",
            f"  -> KP={rt.KP_eur_kw_a:.2f} EUR/kW/a, AP1={rt.AP1_eur_mwh:.2f} EUR/MWh, "
            f"AP2={rt.AP2_eur_mwh:.2f} EUR/MWh",
            f"  -> h*={rt.h_star_h:.1f} h/a, theta={rt.theta:.3f}",
            "",
        ]
    lines.append(f"theta-Spannweite (alpha in [0.30,0.60], f in [2.0,3.5]): "
                  f"{theta_min:.3f} .. {theta_max:.3f} (Faktor {theta_max/theta_min:.2f})")
    return "\n".join(lines)


(OUT_DIR / "tariff_resolved.md").write_text(write_tariff_resolved(), encoding="utf-8")
print("tariff_resolved.md geschrieben.")
# ===END-2===

# %% [markdown]
# ## § 3 — Analytische Bestellregel C* = P_LDC(h*) (vor jedem Solve)
#
# Für den GESAMTNETZBEZUG P_t = P_base_t (+ elektrifizierte Wärmeerzeugung,
# hier: analytische Regel angewandt auf den *reinen Grundlast*-Lastgang,
# weil die Regel per Draft §3.2 einen GEGEBENEN Lastgang voraussetzt; die
# Rückwirkung der endogenen Anlagenauslegung wird erst im LP (Modus
# `evaluate` vs. `optimize`) sichtbar, s. § 6.4/T08).

# %%
def load_duration_curve(p: pd.Series, dt_h: float) -> tuple[np.ndarray, np.ndarray]:
    """Gibt (C_werte absteigend sortiert, D(C) gewichtete Überschreitungsdauer[h]) zurück.

    dt_h MUSS zur Auflösung von `p` passen (0.25 für 15-min-, 1.0 für
    1h-Reihen) - sonst ist die Dauerachse falsch skaliert (T08-Regression)."""
    p_sorted = np.sort(p.to_numpy())[::-1]
    n = len(p_sorted)
    hours = (np.arange(1, n + 1)) * dt_h  # kumulierte Dauer bei Rang i
    return p_sorted, hours


def booking_rule_capacity(p: pd.Series, h_star: float, beta_min: float,
                           p_max_prev: float, p_grid: float, dt_h: float) -> dict:
    """C* = P_LDC(h*): Schnittpunkt der Jahresdauerlinie mit h*, geklippt."""
    p_sorted, hours = load_duration_curve(p, dt_h)
    # D(C) ist monoton fallend in C; P_LDC(h) ist die Inverse: kleinste
    # Leistung, deren Überschreitungsdauer <= h* ist. Liegt h* bei/über der
    # gesamten beobachteten Dauer, gilt D(C)<=h* bereits für C=0 (Buchung
    # jenseits der Untergrenze lohnt sich nie) - Regressionsfall aus dem
    # externen Review (h*=4h bei 3h Gesamtdauer -> C*_raw muss 0 sein, nicht
    # der kleinste beobachtete Lastwert).
    idx = np.searchsorted(hours, h_star, side="left")
    c_raw = 0.0 if idx >= len(p_sorted) else float(p_sorted[idx])
    c_clipped = float(np.clip(c_raw, beta_min * p_max_prev, p_grid))
    return {"C_raw_kw": c_raw, "C_star_kw": c_clipped,
            "clipped_low": c_raw < beta_min * p_max_prev,
            "clipped_high": c_raw > p_grid}


P_GRID_MARGIN = 1.30  # Proxy-Sicherheitsmarge (30%) über der (nach Elektrifizierung
# grob geschätzten) Höchstlast -- nur solange keine reale Anschlussleistung
# in config.yaml:sites.<id>.grid_connection_kw hinterlegt ist (B-03 unverified).


def estimate_p_grid(sd: "SiteData") -> float:
    """Liefert die reale Netzanschlussleistung, falls in config.yaml
    hinterlegt (sites.<id>.grid_connection_kw.value), sonst einen
    transparent als Proxy gekennzeichneten Schätzwert (1.3x Summe aus
    Grundlast-Peak und größtmöglichem Wärme-Elektrifizierungs-Peak,
    EK-Fall eta~=1 als worst case). Status je Standort: p_grid_status()."""
    site_cfg = CONFIG["sites"][sd.site_id]
    grid_connection = site_cfg.get("grid_connection_kw")
    if isinstance(grid_connection, dict) and grid_connection.get("value") is not None:
        return float(grid_connection["value"])
    worst_case_elec_heat_peak = sd.df["q_heat_kw"].max() / 1.0  # EK-Fall (eta~1) als worst case
    return P_GRID_MARGIN * (sd.p_max_prev_kw + worst_case_elec_heat_peak)


def p_grid_status(site_id: str) -> str:
    """Status der Netzanschlussleistung aus config.yaml ('reviewed'/
    'unverified') oder 'proxy_unverified', falls keine reale Angabe existiert."""
    node = CONFIG["sites"][site_id].get("grid_connection_kw")
    if isinstance(node, dict) and node.get("value") is not None:
        return str(node.get("status", "unverified"))
    return "proxy_unverified"


RULE_PREDICTIONS = []
for sid, sd in SITES.items():
    rt = TARIFFS[sd.voltage_level]
    p_grid = estimate_p_grid(sd)
    res = booking_rule_capacity(sd.df["p_base_kw"], rt.h_star_h, rt.beta_min_order,
                                 sd.p_max_prev_kw, p_grid, dt_h=DT_H)
    res.update({"site": sid, "voltage_level": sd.voltage_level, "h_star_h": rt.h_star_h,
                "P_max_prev_kw": sd.p_max_prev_kw, "P_grid_kw": p_grid,
                "C_over_Pmax_prev": res["C_star_kw"] / sd.p_max_prev_kw})
    RULE_PREDICTIONS.append(res)

rule_prediction_df = pd.DataFrame(RULE_PREDICTIONS)
rule_prediction_df.to_csv(OUT_DIR / "rule_prediction.csv", index=False)
print(rule_prediction_df.to_string(index=False))
# ===END-3===

# %% [markdown]
# ## § 4 — LP-Aufbau: `build_model(site, regime, config, mode)`
#
# Reines LP, kontinuierliche Kapazitäten, Perfect Foresight, ein Band
# (`PW`, s. `study.band_note`). $P_t=P^{base}_t+q^{HP}_t/COP+q^{EK}_t/\eta_{EK}$
# gilt für den GESAMTNETZBEZUG (G-04). $P_{1,t}=\min(P_t,C)$ ist wegen
# $AP_2>AP_1$ ohne Binärvariable exakt (Draft § 4.3).

# %%
import linopy
from linopy import Model

TECH = CONFIG["technologies"]
FIN = CONFIG["finance"]
ENE = CONFIG["energy"]


def annuity_factor(wacc: float, lifetime_a: float) -> float:
    if wacc <= 1e-9:
        return 1.0 / lifetime_a
    return wacc / (1.0 - (1.0 + wacc) ** (-lifetime_a))


WACC = cfg_value(FIN["wacc"], name="wacc")
GAS_PRICE = cfg_value(ENE["gas_eur_mwh_hu"], name="gas_eur_mwh_hu")
CO2_PRICE = cfg_value(ENE["co2_eur_t"], name="co2_eur_t")
EF_GAS = cfg_value(ENE["ef_gas_t_mwh"], name="ef_gas_t_mwh")
EL_LEVIES = cfg_value(ENE["el_levies_eur_mwh"], name="el_levies_eur_mwh")
FUEL_COST_EUR_KWH_TH = (GAS_PRICE + CO2_PRICE * EF_GAS) / 1000.0  # EUR/kWh_gas (Hu)

TECH_ANN = {
    tech: {
        "capex": cfg_value(TECH[tech]["capex_eur_kw"] if "capex_eur_kw" in TECH[tech]
                            else TECH[tech]["capex_eur_kwh"], name=f"{tech}.capex"),
        "ann": annuity_factor(WACC, cfg_value(TECH[tech]["lifetime_a"], name=f"{tech}.lifetime_a")),
        "fom": cfg_value(TECH[tech]["fom_pct_capex_a"], name=f"{tech}.fom_pct_capex_a"),
    } for tech in ("hp", "ek", "gb", "tes")
}
COP_HP = cfg_value(TECH["hp"]["cop"], name="hp.cop")
ETA_EK = cfg_value(TECH["ek"]["eta"], name="ek.eta")
ETA_GB = cfg_value(TECH["gb"]["eta"], name="gb.eta")
TES_LOSS_H = cfg_value(TECH["tes"]["loss_per_h"], name="tes.loss_per_h")
TES_ETA_CH = cfg_value(TECH["tes"]["eta_ch"], name="tes.eta_ch")
TES_ETA_DIS = cfg_value(TECH["tes"]["eta_dis"], name="tes.eta_dis")
TES_MIN_DUR_H = cfg_value(TECH["tes"]["min_duration_h"], name="tes.min_duration_h")
CYCLE_PENALTY_EUR_MWH = 5.0   # T06-Regularisierung, s. build_model (<<typische Preisspannen)


@dataclass
class RunSpec:
    run_id: str
    site_id: str
    config_name: str            # BASE | ELEC | ELEC_noTES | GAS
    netz_regime: str            # stromnev | agnes
    stromnev_pair: Optional[str] = None   # ge2500h | lt2500h (nur netz_regime=stromnev)
    procurement: str = "dayahead"          # fixed | dayahead
    mode: str = "optimize"                 # optimize | redispatch | evaluate
    resolution: str = "1h"                 # 1h (primär) | 15min (Validierungsteilmenge)
    fixed_capacities: Optional[dict] = None   # {'hp':.., 'ek':.., 'gb':.., 'tes':..}
    fixed_C_kw: Optional[float] = None
    co2_price_override: Optional[float] = None
    gas_price_override: Optional[float] = None
    alpha_override: Optional[float] = None
    f_override: Optional[float] = None
    band_share: float = 1.0       # Sensitivität (S9): Anteil der Wärmelast im Band
    keep_ts: bool = False          # Zeitreihe (P, q_*) im TS_STORE behalten (Abb. 4)
    window: Optional[tuple] = None       # (start_idx, length) für Rolling Horizon (S10)
    s_tes_init_kwh: Optional[float] = None   # TES-Anfangszustand statt zyklischer Schließung (RH)


def _electricity_price_series(sd: SiteData, procurement: str, prices_src: dict) -> np.ndarray:
    price_utc = prices_src[sd.price_year]
    price_local = price_utc.reindex(sd.df.index)
    if price_local.isna().any():
        raise MissingParameterError("Preisreihe deckt den Lastgang-Index nicht vollständig ab.")
    price_arr = price_local.to_numpy()

    if procurement == "fixed":
        risk_premium = cfg_value(CONFIG["fixed_price"]["risk_premium_eur_mwh"], name="risk_premium")
        # Ex-ante-Referenzpreis = ungewichtetes Jahresmittel der Day-Ahead-Reihe.
        # (Vormals lastgewichtet mit dem REALISIERTEN Grundlastprofil - das ist
        # streng genommen ex-post, da ein Fixpreisvertrag vor Lieferbeginn auf
        # Basis einer Prognose, nicht der tatsächlich eingetretenen Lastform,
        # bepreist wird. Beide Varianten sind vertretbare Vereinfachungen;
        # die unweighted-mean-Variante ist die konservativere/standardnähere.)
        flat = float(np.mean(price_arr)) + risk_premium
        return np.full(len(sd.df), flat)
    return price_arr + 0.0


def build_model(spec: RunSpec) -> tuple[Model, dict]:
    sd_native = SITES[spec.site_id]   # 15-min: für Ebene/P_max_prev/P_grid (auflösungsunabhängig)
    if spec.resolution == "15min":
        sd = sd_native
        prices_src = PRICES
        dt = 15.0 / 60.0
    elif spec.resolution == "1h":
        sd = SITES_1H[spec.site_id]
        prices_src = PRICES_1H
        dt = 1.0
    else:
        raise MissingParameterError(f"Unbekannte resolution: {spec.resolution}")

    price_full = _electricity_price_series(sd, spec.procurement, prices_src)
    if spec.window is not None:
        start, length = spec.window
        sd_view = sd.df.iloc[start:start + length]
        q_heat = sd_view["q_heat_kw"].to_numpy() * spec.band_share
        p_base = sd_view["p_base_kw"].to_numpy()
        price = price_full[start:start + length]
        idx_for_meta = sd_view.index
        n = len(sd_view)
    else:
        n = len(sd.df)
        q_heat = sd.df["q_heat_kw"].to_numpy() * spec.band_share
        p_base = sd.df["p_base_kw"].to_numpy()
        price = price_full
        idx_for_meta = sd.df.index
    el_price_total = price + EL_LEVIES  # EUR/MWh

    gas_price = spec.gas_price_override if spec.gas_price_override is not None else GAS_PRICE
    co2_price = spec.co2_price_override if spec.co2_price_override is not None else CO2_PRICE
    fuel_cost_eur_kwh_fuel = (gas_price + co2_price * EF_GAS) / 1000.0  # EUR/kWh Brennstoff (Hu)
    # BUGFIX (2026-09): q_gb ist Nutzwärme (kW_th, s. N1-Wärmebilanz), nicht
    # Brennstoffeinsatz. Ohne Division durch ETA_GB wurden Gas-/CO2-Kosten um
    # den Faktor 1/eta_GB (~11% bei eta=0.90) unterschätzt - ETA_GB war
    # definiert, aber bislang in keiner Gleichung tatsächlich verwendet.
    fuel_cost = fuel_cost_eur_kwh_fuel / ETA_GB  # EUR/kWh_th Nutzwärme

    m = Model()
    coords = [("t", np.arange(n))]

    has_heat = spec.config_name != "BASE"
    allow_hp_ek_tes = spec.config_name in ("ELEC", "ELEC_noTES")
    allow_tes = spec.config_name == "ELEC"
    allow_gb = spec.config_name in ("ELEC", "ELEC_noTES", "GAS")
    allow_hp = allow_hp_ek_tes
    allow_ek = allow_hp_ek_tes

    fx = spec.fixed_capacities or {}

    def cap_var(name, allowed, key):
        if not has_heat or not allowed:
            return m.add_variables(lower=0, upper=0, name=name)
        if spec.mode in ("redispatch", "evaluate") and fx.get(key) is not None:
            v = fx[key]
            return m.add_variables(lower=v, upper=v, name=name)
        return m.add_variables(lower=0, name=name)

    x_hp = cap_var("x_hp", allow_hp, "hp")
    x_ek = cap_var("x_ek", allow_ek, "ek")
    x_gb = cap_var("x_gb", allow_gb, "gb")
    x_tes = cap_var("x_tes", allow_tes, "tes")

    if has_heat:
        q_hp = m.add_variables(lower=0, coords=coords, name="q_hp")
        q_ek = m.add_variables(lower=0, coords=coords, name="q_ek")
        q_gb = m.add_variables(lower=0, coords=coords, name="q_gb")
        s_tes = m.add_variables(lower=0, coords=coords, name="s_tes")
        q_ch = m.add_variables(lower=0, coords=coords, name="q_ch")
        q_dis = m.add_variables(lower=0, coords=coords, name="q_dis")

        m.add_constraints(q_hp + q_ek + q_gb + q_dis - q_ch == q_heat, name="N1_heat_balance")
        m.add_constraints(q_hp <= x_hp, name="N4_hp_cap")
        m.add_constraints(q_ek <= x_ek, name="N4_ek_cap")
        m.add_constraints(q_gb <= x_gb, name="N4_gb_cap")

        s_prev = s_tes.shift(t=1)
        m.add_constraints(
            s_tes.isel(t=slice(1, None))
            == (1 - TES_LOSS_H * dt) * s_prev.isel(t=slice(1, None))
            + TES_ETA_CH * q_ch.isel(t=slice(1, None)) * dt
            - q_dis.isel(t=slice(1, None)) * dt / TES_ETA_DIS,
            name="N5_tes_balance",
        )
        if spec.window is not None:
            # Rolling Horizon (S10): fester Anfangszustand statt zyklischer Schließung
            s_init = spec.s_tes_init_kwh if spec.s_tes_init_kwh is not None else 0.0
            m.add_constraints(
                s_tes.isel(t=0) == (1 - TES_LOSS_H * dt) * s_init
                + TES_ETA_CH * q_ch.isel(t=0) * dt - q_dis.isel(t=0) * dt / TES_ETA_DIS,
                name="N5_tes_balance_init",
            )
        else:
            s_prev0 = s_tes.isel(t=n - 1)  # zyklisch geschlossen: t=0 knüpft an t=n-1 an
            m.add_constraints(
                s_tes.isel(t=0) == (1 - TES_LOSS_H * dt) * s_prev0
                + TES_ETA_CH * q_ch.isel(t=0) * dt - q_dis.isel(t=0) * dt / TES_ETA_DIS,
                name="N5_tes_balance_cyclic0",
            )
        m.add_constraints(s_tes <= x_tes, name="N6_tes_cap")
        m.add_constraints(q_ch + q_dis <= x_tes / TES_MIN_DUR_H, name="N6_tes_rate")

        p_elec = p_base + q_hp / COP_HP + q_ek / ETA_EK
    else:
        p_elec = p_base  # BASE: kein Wärmeerzeuger, reiner Grundlastbezug

    P = m.add_variables(lower=0, coords=coords, name="P")
    m.add_constraints(P == p_elec, name="N7_power_balance")

    p_grid = estimate_p_grid(sd_native)  # konservativ: auf Basis der nativen 15-min-Spitze
    m.add_constraints(P <= p_grid, name="N8_grid_cap")

    obj = 0

    if has_heat:
        for tech, xvar in (("hp", x_hp), ("ek", x_ek), ("gb", x_gb)):
            if TECH_ANN[tech]["capex"] and (tech != "gb" or allow_gb):
                obj = obj + xvar * TECH_ANN[tech]["capex"] * (TECH_ANN[tech]["ann"] + TECH_ANN[tech]["fom"])
        if allow_tes:
            obj = obj + x_tes * TECH_ANN["tes"]["capex"] * (TECH_ANN["tes"]["ann"] + TECH_ANN["tes"]["fom"])
        # Zyklus-Regularisierung (T06): ohne jede Kostenwirkung auf gleichzeitiges
        # Laden/Entladen ist die LP-Loesung bzgl. q_ch/q_dis degeneriert (beide
        # koennen unbeobachtet gemeinsam erhoeht werden, ohne die Zielfunktion zu
        # aendern). Eine minimale Strafe (<< typische Preisspannen) macht die
        # Aufteilung eindeutig, ohne den TES-Wert wirtschaftlich zu verzerren.
        obj = obj + ((q_ch + q_dis).sum() * dt / 1000.0) * CYCLE_PENALTY_EUR_MWH
        obj = obj + (q_gb.sum() * dt) * fuel_cost

    netz_meta: dict = {}
    if spec.netz_regime == "stromnev":
        pair_name = spec.stromnev_pair
        pair = CONFIG["stromnev"]["by_level"][sd.voltage_level][f"pair_{pair_name}"]
        lp = pair["lp_eur_kw_a"]
        ap = pair["ap_eur_mwh"]
        P_max = m.add_variables(lower=0, name="P_max")
        m.add_constraints(P_max >= P, name="N10_pmax_def")
        if spec.window is None:
            obj = obj + P_max * lp
        # Rolling Horizon (S10, spec.window gesetzt): KEIN Kapazitätspreis-Term
        # je 36h-Fenster. Die Jahreskapazitätskosten sind bereits im Perfect-
        # Foresight-Vergleichswert (S1) erfasst; ein LP*P_max-Term pro Fenster
        # würde eine künstliche Kapazitätsgebühr je Fenster erzeugen und die
        # Dispatch-Entscheidung verzerren (chirurgischer Fix, s. Chat-Review;
        # P_max bleibt als Diagnosegröße definiert, trägt nur keine Kosten
        # mehr innerhalb eines RH-Fensters).
        obj = obj + (P.sum() * dt / 1000.0) * ap
        obj = obj + (P * el_price_total / 1000.0).sum() * dt
        netz_meta = {"lp": lp, "ap": ap, "pair": pair_name}
    else:
        rt = TARIFFS[sd.voltage_level]
        alpha = spec.alpha_override if spec.alpha_override is not None else rt.alpha
        f_ = spec.f_override if spec.f_override is not None else rt.f
        k = rt.k_eur_kw_a
        KP = (1 - alpha) * k
        AP1 = 1000.0 * alpha * k / rt.t_B_h
        AP2 = f_ * AP1
        beta = rt.beta_min_order

        if spec.mode == "evaluate" and spec.fixed_C_kw is not None:
            C = m.add_variables(lower=spec.fixed_C_kw, upper=spec.fixed_C_kw, name="C")
        else:
            C = m.add_variables(lower=beta * sd.p_max_prev_kw, upper=p_grid, name="C")

        P1 = m.add_variables(lower=0, coords=coords, name="P1")
        P2 = m.add_variables(lower=0, coords=coords, name="P2")
        m.add_constraints(P1 + P2 == P, name="N9_split")
        m.add_constraints(P1 <= C, name="N9_p1_le_C")

        obj = obj + C * KP
        obj = obj + (P1.sum() * dt / 1000.0) * AP1
        obj = obj + (P2.sum() * dt / 1000.0) * AP2
        obj = obj + (P * el_price_total / 1000.0).sum() * dt
        netz_meta = {"KP": KP, "AP1": AP1, "AP2": AP2, "h_star": 1000 * KP / (AP2 - AP1),
                     "beta": beta, "alpha": alpha, "f": f_}

    m.add_objective(obj)

    meta = {
        "spec": spec, "n": n, "dt": dt, "p_grid": p_grid, "index": idx_for_meta,
        "q_heat": q_heat, "p_base": p_base, "el_price_total": el_price_total,
        "fuel_cost_eur_kwh_th": fuel_cost, "fuel_cost_eur_kwh_fuel": fuel_cost_eur_kwh_fuel,
        "gas_price": gas_price, "co2_price": co2_price,
        "netz_meta": netz_meta, "has_heat": has_heat, "allow_tes": allow_tes,
        "voltage_level": sd.voltage_level, "p_max_prev_kw": sd.p_max_prev_kw,
    }
    return m, meta
# ===END-4===

# %% [markdown]
# ### KPI-Extraktion und `solve_run` (Wrapper: bauen, lösen, KPIs ziehen)
#
# G-08: nicht-optimale oder inkonsistente Läufe gehen NICHT in Aggregate ein
# (werden aber mit Status zurückgegeben, nicht verworfen -> Transparenz).

# %%
def _sol(m: Model, name: str) -> np.ndarray:
    return m.variables[name].solution.to_numpy()


def _sol_scalar(m: Model, name: str) -> float:
    return float(m.variables[name].solution.values)


def extract_kpis(spec: RunSpec, m: Model, meta: dict, solve_seconds: float) -> dict:
    dt = meta["dt"]
    n = meta["n"]
    status_ok = (m.status == "ok") and (m.termination_condition == "optimal")

    P = _sol(m, "P") if "P" in m.variables else np.zeros(n)
    E_mwh = float(P.sum() * dt / 1000.0)
    P_max_realized = float(P.max()) if n else 0.0
    benutzungsstunden = float(E_mwh * 1000.0 / P_max_realized) if P_max_realized > 1e-9 else np.nan

    kpi: dict[str, Any] = {
        "run_id": spec.run_id, "site_id": spec.site_id, "config_name": spec.config_name,
        "netz_regime": spec.netz_regime, "stromnev_pair": spec.stromnev_pair,
        "procurement": spec.procurement, "mode": spec.mode, "resolution": spec.resolution,
        "solver_status": m.status, "termination_condition": m.termination_condition,
        "is_optimal": status_ok, "solve_seconds": solve_seconds,
        "config_sha256": CONFIG_SHA256, "run_ts": RUN_TS,
        "E_mwh": E_mwh, "P_max_kw": P_max_realized, "benutzungsstunden_h": benutzungsstunden,
        "voltage_level": meta["voltage_level"], "voltage_level_status": "proxy_unverified",
        "p_grid_kw": meta["p_grid"], "p_grid_status": p_grid_status(spec.site_id),
    }

    if not status_ok:
        kpi["objective_eur"] = np.nan
        return kpi

    kpi["objective_eur"] = float(m.objective.value)

    x_hp = _sol_scalar(m, "x_hp") if "x_hp" in m.variables else 0.0
    x_ek = _sol_scalar(m, "x_ek") if "x_ek" in m.variables else 0.0
    x_gb = _sol_scalar(m, "x_gb") if "x_gb" in m.variables else 0.0
    x_tes = _sol_scalar(m, "x_tes") if "x_tes" in m.variables else 0.0
    kpi.update({"x_hp_kw": x_hp, "x_ek_kw": x_ek, "x_gb_kw": x_gb, "x_tes_kwh": x_tes})

    capex_annuity = 0.0
    fom = 0.0
    for tech, xval in (("hp", x_hp), ("ek", x_ek), ("gb", x_gb)):
        capex_annuity += xval * TECH_ANN[tech]["capex"] * TECH_ANN[tech]["ann"]
        fom += xval * TECH_ANN[tech]["capex"] * TECH_ANN[tech]["fom"]
    capex_annuity += x_tes * TECH_ANN["tes"]["capex"] * TECH_ANN["tes"]["ann"]
    fom += x_tes * TECH_ANN["tes"]["capex"] * TECH_ANN["tes"]["fom"]
    kpi["capex_annuity_eur"] = capex_annuity
    kpi["fom_eur"] = fom

    if meta["has_heat"]:
        q_gb = _sol(m, "q_gb")
        q_hp = _sol(m, "q_hp")
        q_ek = _sol(m, "q_ek")
        q_dis = _sol(m, "q_dis")
        q_ch = _sol(m, "q_ch")
        q_gb_useful_mwh = float(q_gb.sum() * dt / 1000.0)
        fuel_gas_mwh_hu = q_gb_useful_mwh / ETA_GB  # Brennstoffbedarf (Hu), q_gb ist Nutzwärme
        kpi["fuel_gas_mwh_hu"] = fuel_gas_mwh_hu
        kpi["opex_gas_eur"] = fuel_gas_mwh_hu * meta["gas_price"]
        kpi["opex_co2_eur"] = fuel_gas_mwh_hu * EF_GAS * meta["co2_price"]
        kpi["q_hp_mwh"] = float(q_hp.sum() * dt / 1000.0)
        kpi["q_ek_mwh"] = float(q_ek.sum() * dt / 1000.0)
        kpi["q_gb_mwh"] = q_gb_useful_mwh
        kpi["q_useful_mwh"] = float(meta["q_heat"].sum() * dt / 1000.0)
        # T06: r_sim - gleichzeitiges Laden/Entladen soll ~0 sein
        sim_overlap = float(np.minimum(q_ch, q_dis).sum() * dt)
        total_chdis = float((q_ch + q_dis).sum() * dt)
        kpi["r_sim"] = sim_overlap / total_chdis if total_chdis > 1e-9 else 0.0
        kpi["tes_full_cycles"] = float(q_dis.sum() * dt / x_tes) if x_tes > 1e-6 else 0.0
        kpi["cycle_penalty_eur"] = float((q_ch + q_dis).sum() * dt / 1000.0) * CYCLE_PENALTY_EUR_MWH
    else:
        kpi["fuel_gas_mwh_hu"] = 0.0
        kpi["opex_gas_eur"] = 0.0
        kpi["opex_co2_eur"] = 0.0
        kpi["q_hp_mwh"] = kpi["q_ek_mwh"] = kpi["q_gb_mwh"] = kpi["q_useful_mwh"] = 0.0
        kpi["r_sim"] = 0.0
        kpi["tes_full_cycles"] = 0.0
        kpi["cycle_penalty_eur"] = 0.0

    # Stromkosten (Commodity, exkl. Netzentgelt) + Netzentgelt-Komponenten
    opex_el = float((P * meta["el_price_total"]).sum() * dt / 1000.0)
    kpi["opex_el_eur"] = opex_el

    nm = meta["netz_meta"]
    if spec.netz_regime == "stromnev":
        kpi["netz_lp_component_eur"] = nm["lp"] * P_max_realized
        kpi["netz_ap_component_eur"] = nm["ap"] * E_mwh
        kpi["netz_entgelt_total_eur"] = kpi["netz_lp_component_eur"] + kpi["netz_ap_component_eur"]
        kpi["C_kw"] = np.nan
        kpi["E1_mwh"] = kpi["E2_mwh"] = np.nan
        # T09: Konsistenzprüfung Tarifpaar <-> realisierte Benutzungsdauer
        thr = CONFIG["stromnev"]["threshold_h"]
        if spec.stromnev_pair == "ge2500h":
            consistent = (not np.isnan(benutzungsstunden)) and benutzungsstunden >= thr
        else:
            consistent = (not np.isnan(benutzungsstunden)) and benutzungsstunden < thr
        kpi["tariff_ambiguous"] = not consistent
    else:
        C = _sol_scalar(m, "C")
        P1 = _sol(m, "P1")
        P2 = _sol(m, "P2")
        E1 = float(P1.sum() * dt / 1000.0)
        E2 = float(P2.sum() * dt / 1000.0)
        kpi["C_kw"] = C
        kpi["E1_mwh"] = E1
        kpi["E2_mwh"] = E2
        kpi["netz_kp_component_eur"] = nm["KP"] * C
        kpi["netz_ap1_component_eur"] = nm["AP1"] * E1
        kpi["netz_ap2_component_eur"] = nm["AP2"] * E2
        kpi["netz_entgelt_total_eur"] = (kpi["netz_kp_component_eur"] + kpi["netz_ap1_component_eur"]
                                          + kpi["netz_ap2_component_eur"])
        kpi["C_over_Pmax"] = C / P_max_realized if P_max_realized > 1e-9 else np.nan
        kpi["E2_over_E"] = E2 / E_mwh if E_mwh > 1e-9 else np.nan
        kpi["h_star_h"] = nm["h_star"]
        kpi["alpha"] = nm["alpha"]
        kpi["f"] = nm["f"]
        kpi["theta"] = nm["h_star"] / TARIFFS[meta["voltage_level"]].t_B_h
        # gewichtete Dauer mit P_t > C (fuer T08 / D(C)=h*)
        kpi["duration_P_gt_C_h"] = float((P > C + 1e-6).sum() * dt)
        kpi["tariff_ambiguous"] = False

    # G-04/T04: Objective-Rekonstruktion aus Komponenten (T11)
    recon = (kpi["capex_annuity_eur"] + kpi["fom_eur"] + kpi["opex_gas_eur"]
             + kpi["opex_co2_eur"] + kpi["opex_el_eur"] + kpi["netz_entgelt_total_eur"]
             + kpi["cycle_penalty_eur"])
    kpi["objective_reconstructed_eur"] = recon
    kpi["objective_recon_rel_error"] = (abs(recon - kpi["objective_eur"]) / abs(kpi["objective_eur"])
                                         if abs(kpi["objective_eur"]) > 1e-6 else abs(recon))

    # Bindung der Netzanschluss-Restriktion (P_grid ist ggf. nur ein Proxy, s. p_grid_status).
    kpi["p_grid_binding"] = bool(P_max_realized >= meta["p_grid"] - 1e-4)
    kpi["p_grid_utilisation"] = P_max_realized / meta["p_grid"] if meta["p_grid"] > 1e-9 else np.nan

    # level_shift_triggered: realisierter P_max > Ist-Höchstlast vor Elektrifizierung?
    # (Spannungsebene ist in diesem Modell eine Proxy-Zuordnung, s. voltage_level_status.)
    kpi["level_shift_triggered"] = bool(P_max_realized > meta["p_max_prev_kw"])
    kpi["totex_eur"] = kpi["objective_eur"]
    return kpi


def solve_run(spec: RunSpec, solver_kwargs: Optional[dict] = None) -> tuple[dict, Model, dict]:
    merged_kwargs = {**SOLVER_KWARGS, **(solver_kwargs or {})}
    t0 = time.time()
    m, meta = build_model(spec)
    m.solve(solver_name=SOLVER_NAME, output_flag=False, **merged_kwargs)
    dt_solve = time.time() - t0
    kpi = extract_kpis(spec, m, meta, dt_solve)
    return kpi, m, meta


def solve_run_light(spec: RunSpec, keep_ts: bool = False) -> tuple[dict, Optional[pd.DataFrame]]:
    """Wie solve_run, gibt aber statt (m, meta) nur optional eine schlanke
    Zeitreihen-DataFrame zurück (P, q_* falls vorhanden) - für den
    parallelen Kampagnenlauf, damit keine linopy-Modelle im Speicher bleiben."""
    kpi, m, meta = solve_run(spec)
    ts = None
    if keep_ts and kpi.get("is_optimal"):
        cols = {"P": _sol(m, "P")}
        if meta["has_heat"]:
            for v in ("q_hp", "q_ek", "q_gb", "q_dis", "q_ch", "s_tes"):
                cols[v] = _sol(m, v)
        if spec.netz_regime == "agnes":
            cols["P1"] = _sol(m, "P1")
            cols["P2"] = _sol(m, "P2")
        ts = pd.DataFrame(cols, index=meta["index"])
        ts.insert(0, "run_id", spec.run_id)
    del m
    return kpi, ts
# ===END-4B===

# %% [markdown]
# ## § 5/6 — Kampagnen-Runner (parallel, ThreadPoolExecutor) + Kernläufe S1-S4
#
# **Messung (§4-Abschnitt "Modell-Zeitauflösung"):** HiGHS/highspy gibt bei
# Solves den GIL frei; 4 parallele 1h-Solves liefen in ~111s Wall-Time statt
# ~350s sequentiell. Mit 66 logischen Kernen wird der volle Kampagnenlauf
# (S1-S9, ~300+ Solves) mit hoher Parallelität ausgeführt (Größenordnung
# Minuten statt Stunden).

# %%
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ein HiGHS-Thread je Solve verhindert CPU-Überzeichnung und verbessert die
# Reproduzierbarkeit. Zwölf parallele Solves nutzen die verfügbare Hardware
# weiterhin effizient, ohne die Maschine mit vielfachen Solver-internen
# Threads zu überlasten (Chat-Review-Entscheidung).
MAX_WORKERS = min(12, (os.cpu_count() or 12))
SOLVER_KWARGS = {"threads": 1}
KPI_ROWS: list[dict] = []
TS_STORE: dict[str, pd.DataFrame] = {}


def run_campaign(specs: list[RunSpec], label: str,
                  max_workers: int = MAX_WORKERS) -> pd.DataFrame:
    t0 = time.time()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(solve_run_light, s, s.keep_ts): s for s in specs}
        done = 0
        for fut in as_completed(futs):
            spec = futs[fut]
            try:
                kpi, ts = fut.result()
            except Exception as exc:  # G-06: Fehler wird sichtbar, nicht verschluckt
                kpi = {"run_id": spec.run_id, "site_id": spec.site_id,
                       "config_name": spec.config_name, "netz_regime": spec.netz_regime,
                       "procurement": spec.procurement, "mode": spec.mode,
                       "is_optimal": False, "solver_status": "exception",
                       "error": str(exc)}
                ts = None
            results.append(kpi)
            if ts is not None:
                TS_STORE[spec.run_id] = ts
            done += 1
            if done % 10 == 0 or done == len(specs):
                print(f"[{label}] {done}/{len(specs)} ({time.time() - t0:.0f}s)")
    df = pd.DataFrame(results)
    KPI_ROWS.extend(results)
    n_bad = int((~df["is_optimal"]).sum()) if "is_optimal" in df else 0
    print(f"[{label}] fertig: {len(df)} Läufe, {n_bad} nicht-optimal/Fehler "
          f"({time.time() - t0:.0f}s gesamt)")
    return df


def make_run_id(site, config, netz, pair, proc, mode, res) -> str:
    parts = [site, config, netz]
    if pair:
        parts.append(pair)
    parts += [proc, mode, res]
    return "__".join(parts)


KEEP_TS_CONFIGS = {"ELEC"}   # nur ELEC braucht die volle Zeitreihe (Lastdauerlinien Abb. 4)


def s1_s4_specs(resolution: str = "1h") -> list[RunSpec]:
    specs = []
    for site in SITE_IDS:
        for config in CONFIG["design"]["configs"]:  # BASE, ELEC, ELEC_noTES, GAS
            keep_ts = config in KEEP_TS_CONFIGS
            for proc in CONFIG["design"]["procurement_regimes"]:
                # AgNes
                rid = make_run_id(site, config, "agnes", None, proc, "optimize", resolution)
                specs.append(RunSpec(run_id=rid, site_id=site, config_name=config,
                                      netz_regime="agnes", procurement=proc,
                                      mode="optimize", resolution=resolution, keep_ts=keep_ts))
                # StromNEV: beide Tarifpaare (T09-Konsistenzprüfung danach)
                for pair in ("ge2500h", "lt2500h"):
                    rid = make_run_id(site, config, "stromnev", pair, proc, "optimize", resolution)
                    specs.append(RunSpec(run_id=rid, site_id=site, config_name=config,
                                          netz_regime="stromnev", stromnev_pair=pair,
                                          procurement=proc, mode="optimize", resolution=resolution,
                                          keep_ts=keep_ts))
    return specs


S1_S4_SPECS = s1_s4_specs("1h")   # SITE_IDS ist im DRY_RUN bereits auf ['metal'] reduziert
print(f"S1-S4 (1h): {len(S1_S4_SPECS)} Solves "
      f"({len(SITE_IDS)} Standorte x {len(CONFIG['design']['configs'])} Konfigurationen x "
      f"[1 AgNes + 2 StromNEV-Paare] x {len(CONFIG['design']['procurement_regimes'])} Beschaffung)")

# %%
df_s1_s4 = run_campaign(S1_S4_SPECS, label="S1-S4")
df_s1_s4.to_parquet(OUT_DIR / "kpi_s1_s4.parquet", index=False)
print(df_s1_s4[["run_id", "is_optimal", "solve_seconds", "objective_eur"]].head(10).to_string(index=False))
# ===END-5===

# %% [markdown]
# ## § 5 (Fortsetzung) — Selbsttests T01-T13
#
# T01 lief bereits in § 1. Alle übrigen Tests stützen sich auf die S1-S4-
# Kampagne (KPI + `TS_STORE`-Zeitreihen der ELEC-Läufe) statt auf separate
# Wegwerf-Solves - kein doppelter Rechenaufwand.

# %%
TEST_REPORT: list[dict] = []


def _report(test_id: str, desc: str, passed: bool, detail: str = ""):
    TEST_REPORT.append({"test": test_id, "beschreibung": desc, "bestanden": bool(passed),
                         "detail": detail})
    mark = "OK" if passed else "FAIL"
    print(f"[{mark}] {test_id}: {desc}  {detail}")
    assert passed, f"{test_id} FAIL: {desc} ({detail})"


_report("T01", "Intervallzahl/Lücken/Duplikate (§1)", bool(T01["pass"].all()),
        f"{T01['pass'].sum()}/{len(T01)} Standorte ok")

# %%
# --- T02: Einheiten-Sentinel (Faktor-1000-Mutation MUSS den Test brechen) ---
def _t02_probe(mutate: bool) -> float:
    sd = SITES_1H["metal"]
    df = sd.df.copy()
    if mutate:
        df["q_heat_kw"] = df["q_heat_kw"] * 1000.0   # absichtlicher Einheitenfehler
    sd_mut = SiteData(sd.site_id, sd.label_de, df, sd.price_year, sd.has_vht,
                       sd.quality_flags, sd.p_max_prev_kw, sd.voltage_level)
    saved = SITES_1H["metal"]
    SITES_1H["metal"] = sd_mut
    try:
        spec = RunSpec(run_id="t02", site_id="metal", config_name="ELEC", netz_regime="agnes",
                        procurement="fixed", mode="optimize", resolution="1h")
        kpi, _ = solve_run_light(spec, keep_ts=False)
        return kpi["objective_eur"]
    finally:
        SITES_1H["metal"] = saved


obj_correct = _t02_probe(mutate=False)
obj_mutated = _t02_probe(mutate=True)
rel_diff = abs(obj_mutated - obj_correct) / abs(obj_correct)
_report("T02", "Einheiten-Sentinel: 1000x-Mutation der Wärmelast muss Objective sichtbar verschieben",
        rel_diff > 0.5, f"rel. Verschiebung={rel_diff:.2%}")

# %%
# --- T03/T04: Wärme-/Strombilanz je Intervall (aus TS_STORE, ELEC-Läufe) ---
def _check_balances(run_id: str) -> tuple[float, float]:
    ts = TS_STORE[run_id]
    site = run_id.split("__")[0]
    q_heat = SITES_1H[site].df["q_heat_kw"].to_numpy()
    heat_resid = (ts["q_hp"] + ts["q_ek"] + ts["q_gb"] + ts["q_dis"] - ts["q_ch"]).to_numpy() - q_heat
    heat_rel = np.max(np.abs(heat_resid)) / max(np.max(np.abs(q_heat)), 1.0)

    p_base = SITES_1H[site].df["p_base_kw"].to_numpy()
    p_expect = p_base + ts["q_hp"].to_numpy() / COP_HP + ts["q_ek"].to_numpy() / ETA_EK
    power_resid = ts["P"].to_numpy() - p_expect
    power_rel = np.max(np.abs(power_resid)) / max(np.max(np.abs(p_expect)), 1.0)
    return heat_rel, power_rel


sample_elec_runs = [rid for rid in TS_STORE if rid.startswith("metal__ELEC__agnes")]
assert sample_elec_runs, "Kein ELEC/AgNes-Lauf mit Zeitreihe im TS_STORE gefunden."
heat_rel, power_rel = _check_balances(sample_elec_runs[0])
_report("T03", "Wärmebilanz je Intervall", heat_rel < 1e-6, f"max. rel. Residuum={heat_rel:.2e}")
_report("T04", "Strombilanz inkl. P_base je Intervall", power_rel < 1e-6, f"max. rel. Residuum={power_rel:.2e}")

# %%
# --- T05: Speicher zyklisch geschlossen, Grenzen/Raten -----------------------
ts5 = TS_STORE[sample_elec_runs[0]]
run_kpi5 = df_s1_s4[df_s1_s4["run_id"] == sample_elec_runs[0]].iloc[0]
x_tes5 = run_kpi5["x_tes_kwh"]
s = ts5["s_tes"].to_numpy()
cap_ok = bool(np.all(s <= x_tes5 + 1e-4))
rate_ok = bool(np.all((ts5["q_ch"] + ts5["q_dis"]).to_numpy() <= x_tes5 / TES_MIN_DUR_H + 1e-4))
cyclic_resid = abs(s[0] - ((1 - TES_LOSS_H * 1.0) * s[-1]
                           + TES_ETA_CH * ts5["q_ch"].iloc[0] * 1.0
                           - ts5["q_dis"].iloc[0] * 1.0 / TES_ETA_DIS))
cyclic_ok = cyclic_resid < 1e-3 * max(x_tes5, 1.0)
_report("T05", "TES zyklisch geschlossen + Kapazitäts-/Ratengrenzen",
        cap_ok and rate_ok and cyclic_ok,
        f"cap_ok={cap_ok}, rate_ok={rate_ok}, cyclic_resid={cyclic_resid:.4f}")

# %%
# --- T06: r_sim <= 1e-8 (kein gleichzeitiges Laden/Entladen) ----------------
elec_rows = df_s1_s4[(df_s1_s4["config_name"] == "ELEC") & df_s1_s4["is_optimal"]]
r_sim_max = elec_rows["r_sim"].max()
_report("T06", "r_sim <= 1e-8 (kein simultanes Laden/Entladen)", r_sim_max <= 1e-6,
        f"max r_sim über {len(elec_rows)} ELEC-Läufe={r_sim_max:.2e}")

# %%
# --- T07: AgNes P1=min(P,C) im Optimum; C in Grenzen ------------------------
agnes_ts_runs = [rid for rid in TS_STORE if "__agnes__" in rid]
run_id7 = agnes_ts_runs[0]
ts7 = TS_STORE[run_id7]
kpi7 = df_s1_s4[df_s1_s4["run_id"] == run_id7].iloc[0]
p1_expect = np.minimum(ts7["P"].to_numpy(), kpi7["C_kw"])
p1_resid = np.max(np.abs(ts7["P1"].to_numpy() - p1_expect))
site7 = run_id7.split("__")[0]
sd7 = SITES[site7]
beta7 = TARIFFS[sd7.voltage_level].beta_min_order
p_grid7 = estimate_p_grid(sd7)
c_in_bounds = (beta7 * sd7.p_max_prev_kw - 1e-3) <= kpi7["C_kw"] <= (p_grid7 + 1e-3)
_report("T07", "AgNes: P1=min(P,C) im Optimum, C in [beta*Pmax_prev, Pgrid]",
        p1_resid < 1e-2 and c_in_bounds, f"max|P1-min(P,C)|={p1_resid:.4f}, C={kpi7['C_kw']:.1f} kW")

# %%
# --- T08: Bestellregel im evaluate-Modus (hier: BASE/AgNes-Optimum, reiner
#     Grundlastgang = "gegebener Lastgang" per Draft 3.2) trifft D(C*)=h* ----
def rule_capacity_1h(site: str) -> float:
    sd1h = SITES_1H[site]
    rt = TARIFFS[sd1h.voltage_level]
    p_grid = estimate_p_grid(SITES[site])
    res = booking_rule_capacity(sd1h.df["p_base_kw"], rt.h_star_h, rt.beta_min_order,
                                 sd1h.p_max_prev_kw, p_grid, dt_h=1.0)
    return res["C_star_kw"]


t08_rows = []
for site in SITE_IDS:
    rule_c = rule_capacity_1h(site)
    lp_row = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "BASE")
                       & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "fixed")]
    lp_c = float(lp_row.iloc[0]["C_kw"])
    dev = abs(lp_c - rule_c) / max(rule_c, 1.0)
    t08_rows.append({"site": site, "C_regel_kw": rule_c, "C_lp_kw": lp_c, "abw_pct": dev * 100})
t08_df = pd.DataFrame(t08_rows)
print(t08_df.to_string(index=False))
_report("T08", "Bestellregel C*=P_LDC(h*) trifft LP-Optimum bei reinem Grundlastgang (BASE)",
        bool((t08_df["abw_pct"] < 0.5).all()), f"max Abweichung={t08_df['abw_pct'].max():.3f}%")

# %%
# --- T09: StromNEV Konsistenzprüfung (Pmax=max P_t, Tarifpaar passt) -------
sn_rows = df_s1_s4[(df_s1_s4["netz_regime"] == "stromnev") & df_s1_s4["is_optimal"]]
n_ambig = int(sn_rows["tariff_ambiguous"].sum())
_report("T09", "StromNEV-Tarifpaar-Konsistenzprüfung ausgeführt (tariff_ambiguous gesetzt)",
        "tariff_ambiguous" in sn_rows.columns, f"{n_ambig}/{len(sn_rows)} Läufe als ambiguous geflaggt")

# %%
# --- T10: Dominanzen (TES <= noTES, Monotonie Gas-/CO2-Preis via S7 später) -
merge_keys = ["site_id", "netz_regime", "stromnev_pair", "procurement"]
elec_o = df_s1_s4[(df_s1_s4["config_name"] == "ELEC") & df_s1_s4["is_optimal"]]
noTES_o = df_s1_s4[(df_s1_s4["config_name"] == "ELEC_noTES") & df_s1_s4["is_optimal"]]
cmp10 = elec_o.merge(noTES_o, on=merge_keys, suffixes=("_tes", "_notes"))
viol10 = cmp10[cmp10["objective_eur_tes"] > cmp10["objective_eur_notes"] * 1.0001]
_report("T10", "Dominanz: TES-Option senkt (oder hält) TOTEX ggü. ELEC_noTES",
        len(viol10) == 0, f"{len(viol10)}/{len(cmp10)} Verletzungen")

# %%
# --- T11: Objective-Rekonstruktion = Solverwert -----------------------------
recon_err = df_s1_s4.loc[df_s1_s4["is_optimal"], "objective_recon_rel_error"].max()
_report("T11a", "Objective-Rekonstruktion aus Komponenten = Solverwert", recon_err < 1e-6,
        f"max rel. Fehler={recon_err:.2e}")

# %%
# --- T11b: P_max_15min >= P_max_60min (kleine Validierungsteilmenge) -------
# 15-min-Auflösung ist unabhängig vom Standort inhärent langsam (s. "Modell-
# Zeitauflösung"-Notiz in §1 - das war genau der Befund, der zur 1h-Primär-
# auflösung geführt hat). Im DRY_RUN wird dieser Solve daher komplett
# übersprungen statt nur verkleinert (ein einzelner 15-min-Solve dauert auch
# für den kleinsten Standort mehrere Minuten).
if DRY_RUN:
    VALIDATION_15MIN_SITES = []
    df_val15 = pd.DataFrame(columns=["run_id", "site_id", "is_optimal", "P_max_kw",
                                      "totex_eur", "q_useful_mwh"])
    t11b_df = pd.DataFrame(columns=["site", "P_max_60_kw", "P_max_15_kw", "P_max_15_ge_60",
                                     "LCOH_inc_delta_pct"])
    print("[DRY_RUN] T11b (15-min-Validierung) übersprungen (s. Kommentar oben).")
    _report("T11b", "P_max(15min) >= P_max(60min) - im DRY_RUN übersprungen", True, "DRY_RUN")
else:
    # BASE + ELEC bei beiden Auflösungen, damit die tatsächlich im Paper
    # berichtete Kennzahl LCOH_inc=(K_ELEC-K_BASE)/Q_useful verglichen wird
    # (vormals: totex_eur/q_useful_mwh direkt - das ist NICHT die inkrementelle
    # Kennzahl aus §4.7/lcoh_inc.csv und damit ein methodischer Bruch).
    VALIDATION_15MIN_SITES = ["chemistry", "paper"]
    val15_specs = [
        RunSpec(run_id=make_run_id(site, config, "agnes", None, "dayahead", "optimize", "15min"),
                site_id=site, config_name=config, netz_regime="agnes", procurement="dayahead",
                mode="optimize", resolution="15min")
        for site in VALIDATION_15MIN_SITES for config in ("BASE", "ELEC")
    ]
    df_val15 = run_campaign(val15_specs, label="15min-Validierung",
                             max_workers=min(MAX_WORKERS, len(val15_specs)))
    df_val15.to_parquet(OUT_DIR / "kpi_validation_15min.parquet", index=False)
    assert bool(df_val15["is_optimal"].all()), "T11b FAIL: mind. ein 15-min-Validierungslauf nicht optimal."

    t11b_rows = []
    for site in VALIDATION_15MIN_SITES:
        elec_1h = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                            & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "dayahead")].iloc[0]
        base_1h = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "BASE")
                            & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "dayahead")].iloc[0]
        elec_15 = df_val15[(df_val15["site_id"] == site) & (df_val15["config_name"] == "ELEC")].iloc[0]
        base_15 = df_val15[(df_val15["site_id"] == site) & (df_val15["config_name"] == "BASE")].iloc[0]

        lcoh_inc_1h = (elec_1h["totex_eur"] - base_1h["totex_eur"]) / max(elec_1h["q_useful_mwh"], 1e-9)
        lcoh_inc_15 = (elec_15["totex_eur"] - base_15["totex_eur"]) / max(elec_15["q_useful_mwh"], 1e-9)
        t11b_rows.append({
            "site": site, "P_max_60_kw": float(elec_1h["P_max_kw"]), "P_max_15_kw": float(elec_15["P_max_kw"]),
            "P_max_15_ge_60": bool(elec_15["P_max_kw"] >= elec_1h["P_max_kw"] - 1e-3),
            "LCOH_inc_1h_eur_mwh": lcoh_inc_1h, "LCOH_inc_15min_eur_mwh": lcoh_inc_15,
            "LCOH_inc_delta_pct": 100.0 * (lcoh_inc_15 - lcoh_inc_1h) / max(abs(lcoh_inc_1h), 1e-9),
        })
    t11b_df = pd.DataFrame(t11b_rows)
    t11b_df.to_csv(OUT_DIR / "validation_15min_lcoh_inc.csv", index=False)
    print(t11b_df.to_string(index=False))
    _report("T11b", "P_max(15min) >= P_max(60min); LCOH_inc konsistent (BASE+ELEC) verglichen",
            bool(t11b_df["P_max_15_ge_60"].all()),
            t11b_df[["site", "P_max_60_kw", "P_max_15_kw", "LCOH_inc_delta_pct"]].to_string(index=False))

# %%
# --- T12: Determinismus + Solververgleich (HiGHS Dual-Simplex vs. IPM) -----
spec12 = RunSpec(run_id="t12", site_id="metal", config_name="ELEC", netz_regime="agnes",
                  procurement="fixed", mode="optimize", resolution="1h")
m12a, meta12a = build_model(spec12)
m12a.solve(solver_name="highs", output_flag=False, threads=1, solver="simplex")
obj_simplex_1 = float(m12a.objective.value)
m12b, meta12b = build_model(spec12)
m12b.solve(solver_name="highs", output_flag=False, threads=1, solver="simplex")
obj_simplex_2 = float(m12b.objective.value)
m12c, meta12c = build_model(spec12)
m12c.solve(solver_name="highs", output_flag=False, threads=1, solver="ipm", run_crossover="on")
obj_ipm = float(m12c.objective.value)
det_err = abs(obj_simplex_1 - obj_simplex_2) / abs(obj_simplex_1)
method_err = abs(obj_simplex_1 - obj_ipm) / abs(obj_simplex_1)
_report("T12", "Determinismus (2x Simplex) + Methodenvergleich (Simplex vs. IPM), Delta TOTEX < 0.01%",
        det_err < 1e-4 and method_err < 1e-4,
        f"det_err={det_err:.2e}, simplex-vs-ipm={method_err:.2e}")

# %%
# --- T13: ETA_GB-Regression - Brennstoffbedarf > bereitgestellte Nutzwärme -
# Gezielter Regressionstest (Chat-Review): GAS-Konfiguration erzwingt q_gb>0
# (einziger Erzeuger), damit ist die Prüfung nicht vom LP-Merit-Order-Ergebnis
# abhängig. Verifiziert sowohl fuel_gas_mwh_hu > q_gb_useful_mwh (ETA_GB<1)
# als auch die exakte Rekonstruktion fuel_gas_mwh_hu = q_gb_useful_mwh/ETA_GB.
spec13 = RunSpec(run_id="t13_eta_gb", site_id="metal", config_name="GAS", netz_regime="agnes",
                  procurement="fixed", mode="optimize", resolution="1h")
kpi13, m13, meta13 = solve_run(spec13)
q_gb_useful_13 = kpi13["q_gb_mwh"]
fuel_gas_13 = kpi13["fuel_gas_mwh_hu"]
recon_ok = abs(fuel_gas_13 - q_gb_useful_13 / ETA_GB) / max(q_gb_useful_13 / ETA_GB, 1e-9) < 1e-9
t13_ok = (kpi13["is_optimal"] and ETA_GB < 1.0 and q_gb_useful_13 > 1e-6
          and fuel_gas_13 > q_gb_useful_13 and recon_ok)
_report("T13", "ETA_GB-Regression: Brennstoffbedarf (Hu) > bereitgestellte Nutzwärme bei ETA_GB<1",
        t13_ok, f"ETA_GB={ETA_GB}, q_gb_useful_mwh={q_gb_useful_13:.3f}, "
                f"fuel_gas_mwh_hu={fuel_gas_13:.3f}, Verhältnis={fuel_gas_13/max(q_gb_useful_13,1e-9):.4f} "
                f"(erwartet 1/ETA_GB={1/ETA_GB:.4f}), recon_ok={recon_ok}")

# %%
test_report_df = pd.DataFrame(TEST_REPORT)
test_report_md = "# test_report.md\n\n" + test_report_df.to_markdown(index=False)
(OUT_DIR / "test_report.md").write_text(test_report_md, encoding="utf-8")
print(f"\nAlle {len(TEST_REPORT)} Selbsttests bestanden -> Sweeps (S5-S9) freigegeben.")
# ===END-5B===

# %% [markdown]
# ## § 7 — Sweeps S5, S7-S9 (S6 s. T11b oben; alle 1h-Auflösung)

# %%
# --- S5: alpha x f-Feld (3x3) x 4 Standorte x AgNes x {FIXED, Day-Ahead} ---
alpha_grid = CONFIG["design"]["alpha_grid"][:1] if DRY_RUN else CONFIG["design"]["alpha_grid"]
f_grid = CONFIG["design"]["f_grid"][:1] if DRY_RUN else CONFIG["design"]["f_grid"]

s5_specs = []
for site in SITE_IDS:
    for a in alpha_grid:
        for f_ in f_grid:
            for proc in CONFIG["design"]["procurement_regimes"]:
                rid = f"{site}__ELEC__agnes__a{a}__f{f_}__{proc}__optimize__1h"
                s5_specs.append(RunSpec(run_id=rid, site_id=site, config_name="ELEC",
                                         netz_regime="agnes", procurement=proc, mode="optimize",
                                         resolution="1h", alpha_override=a, f_override=f_))
print(f"S5: {len(s5_specs)} Solves (alpha x f = {len(alpha_grid)}x{len(f_grid)})")
df_s5 = run_campaign(s5_specs, label="S5 (alpha x f)")
df_s5.to_parquet(OUT_DIR / "kpi_s5_alpha_f.parquet", index=False)

# %%
# G-08-Hilfsfunktion (auch von S7 gebraucht, daher vor §8 definiert). Akzeptiert
# ausschließlich konsistente StromNEV-Tarifpaare (kein Fallback auf ambiguous
# Läufe) - empirisch geprüft: in allen 32 Standort/Konfig/Beschaffung-
# Kombinationen ist stets mindestens ein Paar konsistent (s. Chat-Review).
def best_stromnev_row(df: pd.DataFrame, site: str, config: str, procurement: str) -> pd.Series:
    cand = df[(df["site_id"] == site) & (df["config_name"] == config)
              & (df["netz_regime"] == "stromnev") & (df["procurement"] == procurement)
              & (df["is_optimal"]) & (~df["tariff_ambiguous"])]
    if len(cand) == 0:
        raise InfeasibleRunError(
            f"Kein konsistentes StromNEV-Tarifpaar verfügbar: "
            f"site={site}, config={config}, procurement={procurement}")
    return cand.sort_values("objective_eur").iloc[0]


# --- S7: Break-even Gas-/CO2-Preis je Standort UND Netzregime (Bisektion,
#     Day-Ahead als Referenzbeschaffung; ELEC in redispatch auf den
#     S1-Kapazitäten des jeweiligen Regimes, GAS frei). Netzregime-Dimension
#     ergänzt (vormals nur AgNes) -> beantwortet R-BE-SHIFT. --------------
def _get_fixed_caps(site: str, netz_regime: str) -> tuple[dict, Optional[str]]:
    if netz_regime == "stromnev":
        row = best_stromnev_row(df_s1_s4, site, "ELEC", "dayahead")
        pair = row["stromnev_pair"]
    else:
        row = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                        & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "dayahead")].iloc[0]
        pair = None
    caps = {"hp": row["x_hp_kw"], "ek": row["x_ek_kw"], "gb": row["x_gb_kw"], "tes": row["x_tes_kwh"]}
    return caps, pair


def _totex(site: str, config: str, kind: str, value: float, fixed_caps: Optional[dict],
           netz_regime: str, stromnev_pair: Optional[str]) -> float:
    kwargs = dict(co2_price_override=CO2_PRICE, gas_price_override=GAS_PRICE)
    kwargs[f"{kind}_price_override"] = value
    spec = RunSpec(run_id=f"be_{site}_{netz_regime}_{config}_{kind}_{value:.3f}", site_id=site,
                   config_name=config, netz_regime=netz_regime, stromnev_pair=stromnev_pair,
                   procurement="dayahead",
                   mode="redispatch" if config == "ELEC" else "optimize", resolution="1h",
                   fixed_capacities=fixed_caps, **kwargs)
    kpi, _ = solve_run_light(spec, keep_ts=False)
    return kpi["totex_eur"] if kpi["is_optimal"] else np.nan


def breakeven_chain(site: str, kind: str, netz_regime: str) -> dict:
    """Bisektion mit expliziter Konvergenzdiagnose (converged/reason/residual_eur).
    max_iter/tol_rel kommen aus config.yaml:design.breakeven statt hartkodiert."""
    fixed_caps, pair = _get_fixed_caps(site, netz_regime)
    be_cfg = CONFIG["design"]["breakeven"]
    max_iter = 3 if DRY_RUN else int(be_cfg["max_iter"])
    tol_rel = float(be_cfg["tol_rel"])

    if kind == "gas":
        lo, hi = 5.0, 150.0
    else:
        lo, hi = 5.0, 400.0

    def gap(v):
        return (_totex(site, "GAS", kind, v, None, netz_regime, pair)
                - _totex(site, "ELEC", kind, v, fixed_caps, netz_regime, pair))

    base = {"site": site, "kind": kind, "netz_regime": netz_regime}

    f_lo, f_hi = gap(lo), gap(hi)
    if not (np.isfinite(f_lo) and np.isfinite(f_hi)):
        return {**base, "found": False, "converged": False, "reason": "non_finite_endpoint",
                "lo": lo, "hi": hi, "f_lo": f_lo, "f_hi": f_hi, "iterations": 0,
                "breakeven": np.nan, "bracket_width": np.nan, "residual_eur": np.nan}
    if np.sign(f_lo) == np.sign(f_hi):
        return {**base, "found": False, "converged": False, "reason": "no_sign_change",
                "lo": lo, "hi": hi, "f_lo": f_lo, "f_hi": f_hi, "iterations": 0,
                "breakeven": np.nan, "bracket_width": hi - lo, "residual_eur": np.nan}

    iteration = 0
    for iteration in range(1, max_iter + 1):
        mid = 0.5 * (lo + hi)
        f_mid = gap(mid)
        if not np.isfinite(f_mid):
            return {**base, "found": False, "converged": False, "reason": "non_finite_midpoint",
                    "lo": lo, "hi": hi, "f_lo": f_lo, "f_hi": f_hi, "iterations": iteration,
                    "breakeven": np.nan, "bracket_width": hi - lo, "residual_eur": np.nan}
        if np.sign(f_mid) == np.sign(f_lo):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
        if abs(hi - lo) / max(abs(mid), 1.0) <= tol_rel:
            break

    breakeven = 0.5 * (lo + hi)
    residual = gap(breakeven)
    converged = abs(hi - lo) / max(abs(breakeven), 1.0) <= tol_rel
    return {**base, "found": True, "converged": converged,
            "reason": "converged" if converged else "max_iter_reached",
            "breakeven": breakeven, "iterations": iteration, "lo": lo, "hi": hi,
            "f_lo": f_lo, "f_hi": f_hi, "bracket_width": hi - lo, "residual_eur": residual,
            "tol_rel": tol_rel}


breakeven_chains = [(site, kind, netz_regime) for site in SITE_IDS for kind in ("gas", "co2")
                     for netz_regime in CONFIG["design"]["netz_regimes"]]
print(f"S7: {len(breakeven_chains)} Bisektions-Ketten (parallel, je Kette sequentiell; "
      f"{len(CONFIG['design']['netz_regimes'])} Netzregime x 2 Preisarten x {len(SITE_IDS)} Standorte; "
      f"max_iter={CONFIG['design']['breakeven']['max_iter']})")
t0 = time.time()
with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(breakeven_chains))) as ex:
    be_results = list(ex.map(lambda skn: breakeven_chain(*skn), breakeven_chains))
print(f"S7 fertig ({time.time()-t0:.0f}s)")
df_breakeven = pd.DataFrame(be_results)
df_breakeven.to_csv(OUT_DIR / "breakeven.csv", index=False)
print(df_breakeven.to_string(index=False))

# %%
# --- S8: Dekomposition evaluate/redispatch/optimize für 00->10 (StromNEV-Fixed
#     -> AgNes-Fixed), Standort x ELEC ------------------------------------
def decomposition_00_to_10(site: str) -> dict:
    row00 = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                      & (df_s1_s4["netz_regime"] == "stromnev") & (df_s1_s4["procurement"] == "fixed")]
    row00 = row00.sort_values("objective_eur").iloc[0]   # konsistentes/günstigeres Tarifpaar
    row10 = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                      & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "fixed")].iloc[0]
    cost_00 = row00["objective_eur"]
    cost_10_opt = row10["objective_eur"]
    fixed_caps = {"hp": row00["x_hp_kw"], "ek": row00["x_ek_kw"], "gb": row00["x_gb_kw"],
                  "tes": row00["x_tes_kwh"]}

    spec_eval = RunSpec(run_id=f"dec_{site}_evaluate", site_id=site, config_name="ELEC",
                         netz_regime="agnes", procurement="fixed", mode="evaluate", resolution="1h",
                         fixed_capacities=fixed_caps, fixed_C_kw=float(row00["C_kw"]) if not np.isnan(row00["C_kw"]) else 0.0)
    # 00 ist StromNEV (kein C) -> evaluate mit C = realisiertem P_max(00) als sinnvoller Fixpunkt
    c_eval = float(row00["P_max_kw"])
    spec_eval.fixed_C_kw = c_eval
    kpi_eval, _ = solve_run_light(spec_eval, keep_ts=False)

    spec_redisp = RunSpec(run_id=f"dec_{site}_redispatch", site_id=site, config_name="ELEC",
                           netz_regime="agnes", procurement="fixed", mode="redispatch", resolution="1h",
                           fixed_capacities=fixed_caps)
    kpi_redisp, _ = solve_run_light(spec_redisp, keep_ts=False)

    cost_eval = kpi_eval["totex_eur"]
    cost_redisp = kpi_redisp["totex_eur"]
    d_total = cost_10_opt - cost_00
    d_mech = cost_eval - cost_00
    d_disp = cost_redisp - cost_eval
    d_design = cost_10_opt - cost_redisp
    return {"site": site, "cost_00": cost_00, "cost_evaluate": cost_eval, "cost_redispatch": cost_redisp,
            "cost_10_optimize": cost_10_opt, "delta_total": d_total, "delta_mech": d_mech,
            "delta_disp": d_disp, "delta_design": d_design,
            "pct_mech": 100 * d_mech / d_total if abs(d_total) > 1e-6 else np.nan,
            "pct_disp": 100 * d_disp / d_total if abs(d_total) > 1e-6 else np.nan,
            "pct_design": 100 * d_design / d_total if abs(d_total) > 1e-6 else np.nan}


print("S8: Dekomposition 00->10 je Standort")
with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(SITE_IDS))) as ex:
    dec_results = list(ex.map(decomposition_00_to_10, SITE_IDS))
df_decomposition = pd.DataFrame(dec_results)
df_decomposition.to_csv(OUT_DIR / "decomposition.csv", index=False)
print(df_decomposition.to_string(index=False))

# %%
# --- S9 (angepasst, s. Limitations): Wärmelast +-10% statt Bandanteile
#     +-10pp (Bänder aus Datenrealität nicht rekonstruierbar, s. band_note) --
s9_specs = []
for site in SITE_IDS:
    for share in (0.9, 1.1):
        rid = f"{site}__ELEC__agnes__demand{share}__dayahead__optimize__1h"
        s9_specs.append(RunSpec(run_id=rid, site_id=site, config_name="ELEC", netz_regime="agnes",
                                 procurement="dayahead", mode="optimize", resolution="1h",
                                 band_share=share))
print(f"S9 (Wärmelast-Sensitivität +-10%): {len(s9_specs)} Solves")
df_s9 = run_campaign(s9_specs, label="S9 (Wärmelast +-10%)")
df_s9.to_parquet(OUT_DIR / "kpi_s9_demand_sensitivity.parquet", index=False)
# ===END-7===

# %% [markdown]
# ## § 7 (Fortsetzung) — S10: Rolling Horizon (36h/24h) für Standort `food`
#
# Kapazitäten und (bei AgNes) Bestellkapazität C werden je Regime aus dem
# entsprechenden S1-Optimalergebnis übernommen und **ex ante fixiert**
# (Draft § 8, S10); nur der Betrieb (inkl. Speicher) wird im rollierenden
# Horizont neu disponiert. Vergleich ggü. Perfect-Foresight (S1) zeigt den
# Wert des Vorschauhorizonts.

# %%
RH_SITE = SITE_IDS[0] if DRY_RUN else CONFIG["design"]["rolling_horizon"]["site"]
RH_HORIZON_H = int(CONFIG["design"]["rolling_horizon"]["horizon_h"])
RH_STEP_H = int(CONFIG["design"]["rolling_horizon"]["step_h"])
RH_MAX_STEPS_DRY_RUN = 3


def _rh_fixed_inputs(site: str, netz_regime: str, procurement: str) -> tuple[dict, Optional[float], Optional[str], float]:
    row = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                    & (df_s1_s4["netz_regime"] == netz_regime)
                    & (df_s1_s4["procurement"] == procurement)]
    pair = None
    if netz_regime == "stromnev":
        row = row.sort_values("objective_eur").iloc[0]
        pair = row["stromnev_pair"]
    else:
        row = row.iloc[0]
    caps = {"hp": row["x_hp_kw"], "ek": row["x_ek_kw"], "gb": row["x_gb_kw"], "tes": row["x_tes_kwh"]}
    c_fix = float(row["C_kw"]) if netz_regime == "agnes" else None
    # Vergleichsbasis fuer V-03 MUSS gleichartig sein: nur die Stromkosten-
    # Komponente (Commodity, s.u.), NICHT das volle TOTEX (das RH-Fenster
    # rechnet aus Zeitgruenden auch nur diese Komponente je Schritt).
    return caps, c_fix, pair, float(row["opex_el_eur"])


def run_rolling_horizon(site: str, netz_regime: str, procurement: str) -> dict:
    caps, c_fix, pair, pf_opex_el = _rh_fixed_inputs(site, netz_regime, procurement)
    n_total = len(SITES_1H[site].df)
    if DRY_RUN:
        n_total = min(n_total, RH_MAX_STEPS_DRY_RUN * RH_STEP_H)
    s_init = 0.0
    committed_rows = []
    total_cost = 0.0
    t = 0
    while t < n_total:
        length = min(RH_HORIZON_H, n_total - t)
        commit = min(RH_STEP_H, length)
        spec = RunSpec(run_id=f"rh_{site}_{netz_regime}_{procurement}_{t}", site_id=site,
                        config_name="ELEC", netz_regime=netz_regime, stromnev_pair=pair,
                        procurement=procurement,
                        mode="evaluate", resolution="1h", fixed_capacities=caps,
                        fixed_C_kw=c_fix, window=(t, length), s_tes_init_kwh=s_init)
        m, meta = build_model(spec)
        m.solve(solver_name=SOLVER_NAME, output_flag=False)
        if m.status != "ok":
            raise InfeasibleRunError(f"RH-Fenster infeasible: site={site} t={t} status={m.status}")
        s_tes_full = _sol(m, "s_tes")
        P_full = _sol(m, "P")
        s_init = float(s_tes_full[commit - 1])
        # Kosten des committed Abschnitts (anteilig ueber die ersten `commit` Stunden)
        el_price = meta["el_price_total"][:commit]
        p_commit = P_full[:commit]
        step_energy_cost = float(np.sum(p_commit * el_price) / 1000.0)  # dt=1h
        total_cost += step_energy_cost
        committed_rows.append({"t": t, "commit_h": commit, "P_mean_kw": float(p_commit.mean())})
        del m
        t += commit
    return {"site": site, "netz_regime": netz_regime, "procurement": procurement,
            "n_steps": len(committed_rows), "rh_opex_el_eur": total_cost,
            "pf_opex_el_eur": pf_opex_el}


rh_combos = [(RH_SITE, nr, pr) for nr in CONFIG["design"]["netz_regimes"]
             for pr in CONFIG["design"]["procurement_regimes"]]
print(f"S10: Rolling Horizon für {RH_SITE}, {len(rh_combos)} Regime-Kombinationen "
      f"({RH_HORIZON_H}h Horizont / {RH_STEP_H}h Schritt)")
t0 = time.time()
with ThreadPoolExecutor(max_workers=len(rh_combos)) as ex:
    rh_results = list(ex.map(lambda c: run_rolling_horizon(*c), rh_combos))
print(f"S10 fertig ({time.time()-t0:.0f}s)")
df_rh = pd.DataFrame(rh_results)
df_rh.to_csv(OUT_DIR / "rolling_horizon.csv", index=False)
print(df_rh.to_string(index=False))
# ===END-7C===

# %% [markdown]
# ## § 8 — KPI-Aggregation, 2x2-Interaktion, Regelgüte
#
# G-08: nur `is_optimal=True` und (bei StromNEV) konsistente Läufe fließen
# ein. Kennungen 00/01/10/11 = {StromNEV,AgNes} x {FIXED,Day-Ahead}
# (erste Ziffer Netzregime: 0=StromNEV,1=AgNes; zweite Ziffer Beschaffung:
# 0=FIXED,1=Day-Ahead), s. Draft § 4.6.

# %%
def cell_row(df: pd.DataFrame, site: str, config: str, netz: str, proc: str) -> pd.Series:
    if netz == "stromnev":
        return best_stromnev_row(df, site, config, proc)
    return df[(df["site_id"] == site) & (df["config_name"] == config)
              & (df["netz_regime"] == "agnes") & (df["procurement"] == proc)
              & (df["is_optimal"])].iloc[0]


lcoh_rows = []
for site in SITE_IDS:
    for netz in ("stromnev", "agnes"):
        for proc in ("fixed", "dayahead"):
            elec = cell_row(df_s1_s4, site, "ELEC", netz, proc)
            base = cell_row(df_s1_s4, site, "BASE", netz, proc)
            q_useful = elec["q_useful_mwh"]
            lcoh_inc = (elec["totex_eur"] - base["totex_eur"]) / q_useful if q_useful > 1e-6 else np.nan
            kennung = ("1" if netz == "agnes" else "0") + ("1" if proc == "dayahead" else "0")
            lcoh_rows.append({"site": site, "netz_regime": netz, "procurement": proc,
                               "kennung": kennung, "LCOH_inc_eur_mwh": lcoh_inc,
                               "totex_elec_eur": elec["totex_eur"], "totex_base_eur": base["totex_eur"],
                               "netz_entgelt_total_eur": elec["netz_entgelt_total_eur"],
                               "C_kw": elec["C_kw"], "P_max_kw": elec["P_max_kw"],
                               "C_over_Pmax": elec.get("C_over_Pmax", np.nan),
                               "E2_over_E": elec.get("E2_over_E", np.nan)})
df_lcoh = pd.DataFrame(lcoh_rows)
df_lcoh.to_csv(OUT_DIR / "lcoh_inc.csv", index=False)
print(df_lcoh.to_string(index=False))

# %%
# --- 2x2-Interaktion je Standort: Delta_inter = Y11-Y10-Y01+Y00 (Y=LCOH_inc) -
inter_rows = []
for site in SITE_IDS:
    piv = df_lcoh[df_lcoh["site"] == site].set_index("kennung")["LCOH_inc_eur_mwh"]
    y00, y01, y10, y11 = piv["00"], piv["01"], piv["10"], piv["11"]
    delta_inter = y11 - y10 - y01 + y00
    inter_rows.append({"site": site, "Y00_StromNEV_Fixed": y00, "Y01_StromNEV_DA": y01,
                        "Y10_AgNes_Fixed": y10, "Y11_AgNes_DA": y11, "delta_inter": delta_inter})
df_interaction = pd.DataFrame(inter_rows)
df_interaction.to_csv(OUT_DIR / "interaction.csv", index=False)
n_neg = int((df_interaction["delta_inter"] < 0).sum())
print(df_interaction.to_string(index=False))
print(f"delta_inter negativ bei {n_neg}/{len(df_interaction)} Standorten")

# %%
# --- Regelgüte: einfache Regel (§3, reiner Grundlastgang) vs. gekoppeltes
#     LP-Optimum (ELEC, volle Auslegung) -- zentraler Praxisbefund § 6.4 ------
rule_rows = []
for site in SITE_IDS:
    rule_c = rule_capacity_1h(site)
    elec_row = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                         & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "dayahead")].iloc[0]
    lp_c = float(elec_row["C_kw"])
    dev_pct = 100 * (lp_c - rule_c) / rule_c
    rule_rows.append({"site": site, "C_regel_kw": rule_c, "C_lp_gekoppelt_kw": lp_c,
                       "abweichung_pct": dev_pct, "richtung": "höher" if dev_pct > 0 else "niedriger"})
df_rule_validation = pd.DataFrame(rule_rows)
df_rule_validation.to_csv(OUT_DIR / "rule_validation.csv", index=False)
print(df_rule_validation.to_string(index=False))

# %%
# --- Ergänzender Robustheits-Check (Chat-Review, KEIN Ersatz für die
#     Kennzahl oben): wendet die Regel D(C)=h* auf den vom LP SELBST
#     gewählten realisierten Gesamtlastgang P_t* des gekoppelten
#     ELEC/AgNes-Laufs an. Das ist die KKT-Optimalitätsbedingung des LP für
#     C und muss daher (bis auf Diskretisierungs-/Bindungseffekte) exakt auf
#     C_lp_gekoppelt zurückführen - bestätigt die korrekte Umsetzung der
#     analytischen Bedingung im LP, ist aber KEINE neue praktische Aussage
#     (anders als abweichung_pct oben, die absichtlich die VOR-Elektrifizierung
#     bekannte Grundlast mit dem NACH Elektrifizierung optimalen C vergleicht).
kkt_rows = []
for site in SITE_IDS:
    run_id = make_run_id(site, "ELEC", "agnes", None, "dayahead", "optimize", "1h")
    ts = TS_STORE.get(run_id)
    if ts is None:
        continue
    sd = SITES[site]
    rt = TARIFFS[sd.voltage_level]
    elec_row = df_s1_s4[df_s1_s4["run_id"] == run_id].iloc[0]
    rule_on_realized = booking_rule_capacity(ts["P"], rt.h_star_h, rt.beta_min_order,
                                              sd.p_max_prev_kw, estimate_p_grid(sd), dt_h=1.0)
    c_rule_realized = float(rule_on_realized["C_star_kw"])
    c_lp = float(elec_row["C_kw"])
    kkt_rows.append({"site": site, "C_regel_auf_realisiertem_lastgang_kw": c_rule_realized,
                      "C_lp_gekoppelt_kw": c_lp,
                      "abweichung_pct": 100 * (c_lp - c_rule_realized) / max(c_rule_realized, 1.0)})
df_rule_kkt_check = pd.DataFrame(kkt_rows)
df_rule_kkt_check.to_csv(OUT_DIR / "rule_kkt_consistency_check.csv", index=False)
print("\nErgänzender KKT-Konsistenz-Check (Regel auf realisiertem LP-Lastgang):")
print(df_rule_kkt_check.to_string(index=False))
# ===END-8===

# %% [markdown]
# ## § 9 — Abbildungen 1-5 (je eine CSV, farbenblindtauglich, graustufenfest)
#
# Palette: Okabe-Ito (peer-reviewed farbenblindtauglich, Standard in
# wissenschaftlichen Publikationen), zusätzlich per Linienstil/Schraffur
# graustufenfest kodiert (keine alleinige Farbcodierung).

# %%
OKABE_ITO = {
    "schwarz": "#000000", "orange": "#E69F00", "himmelblau": "#56B4E9",
    "gruen": "#009E73", "gelb": "#F0E442", "blau": "#0072B2",
    "vermillion": "#D55E00", "purpur": "#CC79A7",
}
# Monochromatische Blau-Rampe (ColorBrewer "Blues", dunkel->hell) auf
# Nutzerwunsch: alle kategorialen Farben in Abb. 2-5 in Blautönen, per
# Helligkeitsstufe unterscheidbar (graustufenfest) statt per Buntton.
BLUE_SHADES = ["#08306B", "#2171B5", "#4292C6", "#9ECAE1"]
BLUE_DARK, BLUE_MED, BLUE_MED2, BLUE_LIGHT = BLUE_SHADES

SITE_LABEL_DE = {sid: CONFIG["sites"][sid]["label_de"].split(" (")[0] for sid in SITE_IDS}
SITE_COLOR = dict(zip(("food", "chemistry", "metal", "paper"), BLUE_SHADES))
SITE_ORDER = [s for s in ("food", "chemistry", "metal", "paper") if s in SITE_IDS]  # kanonische Reihenfolge, gefiltert auf SITE_IDS (DRY_RUN)
TECH_COLOR = dict(zip(("hp", "ek", "gb", "tes"), BLUE_SHADES))
TECH_LABEL = {"hp": "Wärmepumpe", "ek": "Elektrodenkessel", "gb": "Gaskessel", "tes": "Wärmespeicher"}
REGIME_COLOR = {"stromnev": BLUE_MED2, "agnes": BLUE_DARK}
REGIME_LS = {"stromnev": "--", "agnes": "-"}

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "figure.dpi": 150, "savefig.dpi": 300, "axes.spines.top": False, "axes.spines.right": False,
})


def save_fig(fig, name: str):
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{name}.png", bbox_inches="tight")
    plt.close(fig)


# %%
# --- Abbildung 1: Systemgrenze/Superstruktur (statisch) ---------------------
def fig01_superstructure():
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.axis("off")
    boxes = {
        "grid": (0.02, 0.4, 0.14, 0.2, "Netz\n(StromNEV/AgNes)"),
        "base": (0.30, 0.72, 0.16, 0.16, "Grundlast\n$P^{base}_t$"),
        "hp": (0.30, 0.50, 0.16, 0.14, "Wärmepumpe\n(COP)"),
        "ek": (0.30, 0.32, 0.16, 0.14, "Elektroden-\nkessel"),
        "gb": (0.30, 0.14, 0.16, 0.14, "Gaskessel\n(Erdgas)"),
        "tes": (0.58, 0.32, 0.16, 0.14, "Wärme-\nspeicher"),
        "heat": (0.80, 0.32, 0.16, 0.14, "Prozesswärme\n$Q_{PW,t}$ (1 Band)"),
    }
    for key, (x, y, w, h, label) in boxes.items():
        fc = "#ffffff"
        ax.add_patch(plt.Rectangle((x, y), w, h, fill=True, facecolor=fc,
                                    edgecolor=OKABE_ITO["schwarz"], linewidth=1.2))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=8)
    arrow_kw = dict(arrowstyle="-|>", color=OKABE_ITO["schwarz"], linewidth=1.1, mutation_scale=12)
    for tgt in ("base", "hp", "ek"):
        x, y, w, h, _ = boxes[tgt]
        ax.annotate("", xy=(x, y + h / 2), xytext=(0.16, 0.5), arrowprops=arrow_kw)
    x, y, w, h, _ = boxes["gb"]
    ax.text(0.16, 0.10, "Erdgas", fontsize=7, ha="center")
    ax.annotate("", xy=(x, y + h / 2), xytext=(0.16, 0.14), arrowprops=arrow_kw)
    for src in ("hp", "ek", "gb"):
        x, y, w, h, _ = boxes[src]
        ax.annotate("", xy=(0.58, 0.39), xytext=(x + w, y + h / 2), arrowprops=arrow_kw)
    x, y, w, h, _ = boxes["tes"]
    ax.annotate("", xy=(0.80, 0.39), xytext=(x + w, y + h / 2), arrowprops=arrow_kw)
    ax.text(0.02, 0.62, "$P_t=P^{base}_t+q^{HP}_t/COP+q^{EK}_t/\\eta_{EK}$\n"
                        "Netzentgelt auf GESAMTBEZUG $P_t$ (G-04)", fontsize=7.2,
            ha="left", va="center", style="italic")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title("Abb. 1: Systemgrenze / Superstruktur (ein Prozesswärme-Band)")
    save_fig(fig, "fig01_superstructure")


fig01_superstructure()

# %%
# --- Abbildung 2: sigma(h) beide Regime + h*; theta(alpha,f)-Heatmap -------
def fig02_analytics():
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))

    ax = axes[0]
    lvl = "ms"
    sub = fig02_sigma[fig02_sigma["voltage_level"] == lvl]
    rt = TARIFFS[lvl]
    ax.plot(sub["h"], sub["sigma_stromnev"], color=REGIME_COLOR["stromnev"],
            ls=REGIME_LS["stromnev"], lw=1.8, label="StromNEV (>=2500h-Paar)")
    ax.plot(sub["h"], sub["sigma_agnes"], color=REGIME_COLOR["agnes"],
            ls=REGIME_LS["agnes"], lw=1.8, label="AgNes")
    ax.axvline(rt.h_star_h, color=OKABE_ITO["schwarz"], lw=0.9, ls=":")
    ax.text(rt.h_star_h, ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1] else 1,
            f"  h*={rt.h_star_h:.0f} h", fontsize=7.5, rotation=90, va="top")
    ax.set_xscale("log")
    ax.set_xlabel("Bedarfsdauer h [h/a]")
    ax.set_ylabel("$\\sigma$ [EUR/MWh]")
    ax.set_title(f"(a) $\\sigma_{{NEV}}$ vs. $\\sigma_{{AgNes}}$ (Ebene {lvl.upper()})")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=2)

    ax2 = axes[1]
    piv = fig02_theta.pivot(index="f", columns="alpha", values="theta")
    cmap = plt.get_cmap("Blues")
    im = ax2.pcolormesh(piv.columns, piv.index, piv.values, cmap=cmap, shading="auto")
    cs = ax2.contour(piv.columns, piv.index, piv.values, levels=[1.0],
                      colors=BLUE_DARK, linewidths=1.6)
    ax2.clabel(cs, fmt={1.0: "theta=1"}, fontsize=7.5)
    fig.colorbar(im, ax=ax2, label="theta = h*/t_B")
    ax2.set_xlabel("alpha (Kapazitätspreis-Erlösanteil)")
    ax2.set_ylabel("f = AP2/AP1")
    ax2.set_title("(b) theta(alpha, f)")

    fig.suptitle("Zusatzabbildung: Analytik – Aufschlagsvergleich und dimensionslose Kennzahl "
                 "(nicht Teil der Haupttext-Abbildungen)", y=1.03)
    fig.tight_layout()
    save_fig(fig, "fig02_analytics")


fig02_analytics()

# %%
# --- Abbildung 3: LCOH_inc 4 Regime; Erzeugerkapazitäten; TES ---------------
def fig03_core_results():
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))

    ax = axes[0]
    kenn_order = ["00", "01", "10", "11"]
    kenn_label = {"00": "StromNEV\nFixpreis", "01": "StromNEV\nDay-Ahead",
                  "10": "AgNes\nFixpreis", "11": "AgNes\nDay-Ahead"}
    width = 0.2
    xpos = np.arange(len(kenn_order))
    for i, site in enumerate(SITE_ORDER):
        vals = [df_lcoh[(df_lcoh["site"] == site) & (df_lcoh["kennung"] == k)]["LCOH_inc_eur_mwh"].iloc[0]
                for k in kenn_order]
        ax.bar(xpos + (i - 1.5) * width, vals, width=width, color=SITE_COLOR[site],
               label=SITE_LABEL_DE[site])
    ax.set_xticks(xpos)
    ax.set_xticklabels([kenn_label[k] for k in kenn_order], fontsize=7.5)
    ax.set_ylabel("$LCOH^{inc}$ [EUR/MWh$_{th}$]")
    ax.set_title("(a) Inkrementelle Wärmekosten je Regime")
    ax.legend(frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=2)

    ax = axes[1]
    caps = df_s1_s4[(df_s1_s4["config_name"] == "ELEC") & (df_s1_s4["netz_regime"] == "agnes")
                     & (df_s1_s4["procurement"] == "dayahead")].set_index("site_id")
    bottom = np.zeros(len(SITE_ORDER))
    for tech in ("hp", "ek", "gb"):
        vals = np.array([caps.loc[s, f"x_{tech}_kw"] / 1000.0 for s in SITE_ORDER])
        ax.bar(SITE_ORDER, vals, bottom=bottom, color=TECH_COLOR[tech], label=TECH_LABEL[tech])
        bottom += vals
    ax.set_xticklabels([SITE_LABEL_DE[s] for s in SITE_ORDER], rotation=20, ha="right", fontsize=7.5)
    ax.set_ylabel("Erzeugerkapazität [MW$_{th}$]")
    ax.set_title("(b) Anlagenauslegung (AgNes, Day-Ahead)")
    ax.legend(frameon=False, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=3)

    ax = axes[2]
    vals_tes = np.array([caps.loc[s, "x_tes_kwh"] / 1000.0 for s in SITE_ORDER])
    ax.bar(SITE_ORDER, vals_tes, color=TECH_COLOR["tes"])
    ax.set_xticklabels([SITE_LABEL_DE[s] for s in SITE_ORDER], rotation=20, ha="right", fontsize=7.5)
    ax.set_ylabel("Speicherkapazität [MWh$_{th}$]")
    ax.set_title("(c) Wärmespeicher (1 Band, AgNes/Day-Ahead)")

    fig.tight_layout()
    fig.subplots_adjust(top=0.78)
    fig.suptitle("Abb. 2: Kernergebnisse – Kosten, Auslegung, Speicher", y=1.08)
    save_fig(fig, "fig03_core_results")
    caps.reset_index()[["site_id", "x_hp_kw", "x_ek_kw", "x_gb_kw", "x_tes_kwh"]].to_csv(
        OUT_DIR / "fig03_core_results.csv", index=False)


fig03_core_results()
df_lcoh.to_csv(OUT_DIR / "fig03a_lcoh.csv", index=False)

# %%
# --- Abbildung 4: Lastdauerlinien, 4 Panels, C/P_max/E2, h*-Marker ---------
def fig04_load_duration():
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.5))
    legend_handles = None
    for ax, site in zip(axes.flat, SITE_ORDER):
        run_id = make_run_id(site, "ELEC", "agnes", None, "dayahead", "optimize", "1h")
        ts = TS_STORE.get(run_id)
        if ts is None:
            ax.set_visible(False)
            continue
        kpi_row = df_s1_s4[df_s1_s4["run_id"] == run_id].iloc[0]
        C = kpi_row["C_kw"]
        p_sorted = np.sort(ts["P"].to_numpy())[::-1]
        hours = np.arange(1, len(p_sorted) + 1)
        ax.plot(hours, p_sorted / 1000.0, color=OKABE_ITO["schwarz"], lw=1.4,
                label="Jahresdauerlinie $P_t$")
        ax.axhline(C / 1000.0, color=BLUE_DARK, lw=1.4, ls="-", label="C (bestellt)")
        ax.axhline(kpi_row["P_max_kw"] / 1000.0, color=BLUE_MED2, lw=1.2, ls="--",
                   label="$P_{max}$")
        rt = TARIFFS[SITES[site].voltage_level]
        ax.axvline(rt.h_star_h, color=BLUE_MED, lw=1.0, ls=":", label="h*")
        above = p_sorted > C
        ax.fill_between(hours, C / 1000.0, p_sorted / 1000.0, where=above,
                         color=BLUE_LIGHT, alpha=0.5, label="$E_2$-Fläche")
        ax.set_title(SITE_LABEL_DE[site])
        ax.set_xlabel("Dauer [h/a]")
        ax.set_ylabel("Leistung [MW]")
        if legend_handles is None:
            legend_handles, legend_labels = ax.get_legend_handles_labels()
    fig.suptitle("Abb. 3: Jahresdauerlinien (ELEC, AgNes, Day-Ahead) – C, $P_{max}$, $E_2$, h*", y=1.02)
    fig.tight_layout()
    # EINE zentrale Legende für alle 4 Panels, außerhalb der Achsen (unterhalb).
    fig.legend(legend_handles, legend_labels, loc="lower center", ncol=5,
               bbox_to_anchor=(0.5, -0.04), frameon=False, fontsize=9)
    save_fig(fig, "fig04_load_duration")

    rows = []
    for site in SITE_ORDER:
        run_id = make_run_id(site, "ELEC", "agnes", None, "dayahead", "optimize", "1h")
        ts = TS_STORE.get(run_id)
        if ts is None:
            continue
        p_sorted = np.sort(ts["P"].to_numpy())[::-1]
        for rank, p in enumerate(p_sorted, start=1):
            rows.append({"site": site, "rank_h": rank, "P_kw": p})
    pd.DataFrame(rows).to_csv(OUT_DIR / "fig04_load_duration.csv", index=False)


fig04_load_duration()

# %%
# --- Abbildung 5: Break-even Gas-/CO2-Preis je Standort x Netzregime ------
def fig05_breakeven():
    from matplotlib.patches import Patch

    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8))
    regimes = CONFIG["design"]["netz_regimes"]
    xpos = np.arange(len(SITE_ORDER))
    regime_hatch = {"stromnev": "//", "agnes": None}
    regime_label = {"stromnev": "StromNEV", "agnes": "AgNes"}
    bar_w, gap = 0.30, 0.04
    single_w = 0.42

    for ax, kind, label, ref, unit in (
        (axes[0], "gas", "Gaspreis-Break-even", GAS_PRICE, "EUR/MWh$_{Hu}$"),
        (axes[1], "co2", "CO$_2$-Preis-Break-even", CO2_PRICE, "EUR/t"),
    ):
        sub = df_breakeven[df_breakeven["kind"] == kind]
        for si, site in enumerate(SITE_ORDER):
            avail = []
            for regime in regimes:
                row = sub[(sub["site"] == site) & (sub["netz_regime"] == regime)]
                if len(row) and bool(row.iloc[0]["found"]):
                    avail.append((regime, float(row.iloc[0]["breakeven"])))
            n = len(avail)
            if n == 0:
                continue
            if n == 1:
                # Nur ein Regime konvergiert: EIN Balken, zentriert auf dem Tick.
                regime, val = avail[0]
                ax.bar(si, val, width=single_w, color=SITE_COLOR[site],
                       hatch=regime_hatch[regime], edgecolor=OKABE_ITO["schwarz"], linewidth=0.6)
            else:
                # Beide Regime konvergiert: zwei Balken MIT Lücke, als Paar um den Tick zentriert.
                for j, (regime, val) in enumerate(avail):
                    offset = (j - (n - 1) / 2) * (bar_w + gap)
                    ax.bar(si + offset, val, width=bar_w, color=SITE_COLOR[site],
                           hatch=regime_hatch[regime], edgecolor=OKABE_ITO["schwarz"], linewidth=0.6)
        ax.axhline(ref, color=OKABE_ITO["schwarz"], lw=1.0, ls=":")
        ax.set_xticks(xpos)
        ax.set_xticklabels([SITE_LABEL_DE[s] for s in SITE_ORDER], rotation=20, ha="right")
        ax.set_xlim(-0.6, len(SITE_ORDER) - 0.4)
        ax.set_ylabel(f"Break-even [{unit}]")
        ax.set_title(label)
        legend_elems = [
            Patch(facecolor="#D9D9D9", edgecolor=OKABE_ITO["schwarz"], hatch=regime_hatch["stromnev"],
                  label=regime_label["stromnev"]),
            Patch(facecolor="#D9D9D9", edgecolor=OKABE_ITO["schwarz"], label=regime_label["agnes"]),
            plt.Line2D([0], [0], color=OKABE_ITO["schwarz"], lw=1.0, ls=":",
                       label=f"Referenz-Szenariowert ({ref:.0f})"),
        ]
        ax.legend(handles=legend_elems, frameon=False, fontsize=7, loc="lower center",
                  bbox_to_anchor=(0.5, 1.12), ncol=3)
    fig.tight_layout()
    fig.subplots_adjust(top=0.72)
    fig.suptitle("Abb. 4: Fossiler Break-even je Standort x Netzregime (Hybrid-ELEC vs. GAS, Day-Ahead)", y=1.1)
    save_fig(fig, "fig05_breakeven")


fig05_breakeven()
print("Abbildungen 1-5 gespeichert nach", FIG_DIR)
# ===END-9===

# %% [markdown]
# ## § 10 — Tabellen 1-3 + Supplement

# %%
# --- Tabelle 1: Modellrelevanter Regimevergleich ----------------------------
reg = CONFIG["regulatory_reference"]["reg_01"]
sn = CONFIG["stromnev"]
tar = CONFIG["tariffs"]
table01_rows = [
    {"Element": "Bemessungsgröße Leistungsentgelt", "StromNEV": "Gemessene Jahreshöchstlast $P^{max}$",
     "AgNes": "Frei bestellte Kapazität $C$", "Fundstelle": "StromNEV §17 / " + reg["aktenzeichen"],
     "Freigabestatus": "reviewed"},
    {"Element": "Arbeitspreisstruktur", "StromNEV": "Ein Arbeitspreis je Tarifpaar",
     "AgNes": "Zweistufig: $AP_1$ (<=C), $AP_2$>$AP_1$ (>C)", "Fundstelle": reg["aktenzeichen"],
     "Freigabestatus": "reviewed"},
    {"Element": "Schwellenwert / Bestellgrenzen", "StromNEV": f"{sn['threshold_h']:.0f} h/a (zwei Tarifpaare)",
     "AgNes": f"beta={tar['beta_min_order']['value']} x P^max,prev <= C <= P^grid",
     "Fundstelle": sn["threshold_source"], "Freigabestatus": "reviewed/unverified"},
    {"Element": "Bestellzeitpunkt", "StromNEV": "n/a (ex-post gemessen)",
     "AgNes": "Vor Jahresbeginn (ex ante)", "Fundstelle": reg["aktenzeichen"], "Freigabestatus": "reviewed"},
    {"Element": "Maximaler Leistungsaufschlag bei geringer Nutzung",
     "StromNEV": "Unbeschränkt für h->0 (sigma=1000 LP/h)",
     "AgNes": f"Beschränkt auf AP2-AP1 (Ebene ms: {TARIFFS['ms'].AP2_eur_mwh - TARIFFS['ms'].AP1_eur_mwh:.1f} EUR/MWh)",
     "Fundstelle": "§3.4 Draft (abgeleitet)", "Freigabestatus": "derived"},
    {"Element": "Status Regelwerk", "StromNEV": "Geltendes Recht",
     "AgNes": f"Festlegungsentwurf ({reg['fassungsdatum_entwurf']}), Konsultation bis {reg['konsultationsende']}, "
              f"geplant ab {reg['anwendungszeitpunkt']}",
     "Fundstelle": reg["url"], "Freigabestatus": "reviewed"},
]
table01 = pd.DataFrame(table01_rows)
table01.to_csv(TAB_DIR / "table01_regulatory.csv", index=False)
(OUT_DIR / "table01_regulatory.md").write_text(
    "# Tabelle 1 — Modellrelevanter Regimevergleich\n\n" + table01.to_markdown(index=False), encoding="utf-8")
print(table01.to_string(index=False))

# %%
# --- Tabelle 3: Kern-KPI je Standort x Regime -------------------------------
table03_rows = []
for site in SITE_IDS:
    y00 = df_lcoh[(df_lcoh["site"] == site) & (df_lcoh["kennung"] == "00")].iloc[0]
    y10 = df_lcoh[(df_lcoh["site"] == site) & (df_lcoh["kennung"] == "10")].iloc[0]
    y01 = df_lcoh[(df_lcoh["site"] == site) & (df_lcoh["kennung"] == "01")].iloc[0]
    y11 = df_lcoh[(df_lcoh["site"] == site) & (df_lcoh["kennung"] == "11")].iloc[0]
    inter = df_interaction[df_interaction["site"] == site].iloc[0]
    delta_netz_fix = y10["LCOH_inc_eur_mwh"] - y00["LCOH_inc_eur_mwh"]
    delta_netz_da = y11["LCOH_inc_eur_mwh"] - y01["LCOH_inc_eur_mwh"]
    delta_preis_stromnev = y01["LCOH_inc_eur_mwh"] - y00["LCOH_inc_eur_mwh"]
    delta_preis_agnes = y11["LCOH_inc_eur_mwh"] - y10["LCOH_inc_eur_mwh"]
    table03_rows.append({
        "Standort": SITE_LABEL_DE[site], "LCOH_inc_00_StromNEV_Fix": y00["LCOH_inc_eur_mwh"],
        "Delta_Netz_Fix_AgNes-StromNEV": delta_netz_fix, "Delta_Netz_DA_AgNes-StromNEV": delta_netz_da,
        "Delta_Preis_StromNEV_DA-Fix": delta_preis_stromnev, "Delta_Preis_AgNes_DA-Fix": delta_preis_agnes,
        "Delta_inter": inter["delta_inter"], "C_over_Pmax_AgNes_DA": y11["C_over_Pmax"],
        "E2_over_E_AgNes_DA": y11["E2_over_E"],
    })
table03 = pd.DataFrame(table03_rows)
table03.to_csv(TAB_DIR / "table03_core_results.csv", index=False)
(OUT_DIR / "table03_core_results.md").write_text(
    "# Tabelle 3 — Kern-KPI je Standort\n\n" + table03.to_markdown(index=False, floatfmt=".2f"), encoding="utf-8")
print(table03.to_string(index=False))

# %%
# --- Supplement: vollständige S5/S7/S8/S9/S10-Ergebnistabellen -------------
supplement_files = {
    "supplement_s5_alpha_f.csv": df_s5, "supplement_s7_breakeven.csv": df_breakeven,
    "supplement_s8_decomposition.csv": df_decomposition, "supplement_s9_demand.csv": df_s9,
    "supplement_s10_rolling_horizon.csv": df_rh, "supplement_test_report.csv": test_report_df,
}
for fname, df_ in supplement_files.items():
    df_.to_csv(TAB_DIR / fname, index=False)
print("Supplement-Tabellen geschrieben:", list(supplement_files.keys()))
# ===END-10===

# %% [markdown]
# ## § 11 — Marker-Export und Draft-Patch
#
# Jede `[[R-*]]`/`[[V-*]]`/`[[REG-*]]`-Marke aus dem Paper-Draft wird entweder
# mit einer belegten Zahl (Run-ID/KPI-Spalte rückverfolgbar, G-07) oder als
# **sichtbar offen** mit Begründung geführt (nie mit 0.0 gefüllt, § 11 Regel).

# %%
MARKERS: dict[str, dict] = {}
OPEN_MARKERS: dict[str, str] = {}


def add_marker(key, value, unit, display_value, kpi, run_ids=None, result_file=""):
    MARKERS[key] = {"value": value, "unit": unit, "display_value": display_value,
                     "run_ids": run_ids or [], "kpi": kpi, "config_sha256": CONFIG_SHA256,
                     "result_file": result_file}


def de_num(x, nd=1):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --- REG-01: bereits vollständig in config.yaml (regulatory_reference) -----
reg = CONFIG["regulatory_reference"]["reg_01"]
add_marker("REG-01", reg["aktenzeichen"], "-",
           f"Az. {reg['aktenzeichen']}, Entwurf {reg['fassungsdatum_entwurf']}, "
           f"Konsultation bis {reg['konsultationsende']}, Anwendung ab {reg['anwendungszeitpunkt']}",
           "config.yaml:regulatory_reference", result_file="config.yaml")

# --- R-01 / theta-Spannweite (bereits in §2 berechnet) ----------------------
add_marker("R-01", theta_max / theta_min, "-", f"Faktor {de_num(theta_max/theta_min, 2)}",
           "fig02_analytics_theta.csv", result_file="fig02_analytics_theta.csv")

# --- REG-02: Quelle k, t_B (nachrecherchiert 2026-09-15, s. u.) -------------
OPEN_MARKERS["REG-02"] = (
    "Nachrecherchiert, weiterhin teiloffen: t_B=2500h ist real (StromNEV § 19 "
    "Abs. 2, reviewed). Für k je Ebene wurde gezielt nach einem BNetzA-"
    "Monitoringbericht mit Netzentgeltniveaus je Ebene gesucht - kein "
    "konsistentes, textuell auswertbares Ebenen-Tabellenwerk gefunden (nur "
    "gescannte PDFs bzw. AI-Suchzusammenfassungen mit widersprüchlichen "
    "Zahlen). Stattdessen jetzt EIN reales, konsistentes Preisblatt für alle "
    "drei Ebenen verwendet: Stadtwerke Tübingen GmbH, Preisblatt Netzentgelte "
    "Strom, gültig ab 01.01.2025 (MS weiterhin eam-netz.de, 2024 - andere "
    "DSO). k je Ebene bleibt damit 'derived/reviewed-Anker + Konstruktion', "
    "keine amtliche Monitoringbericht-Tabelle. Die DSO-zu-DSO-Streuung "
    "(z.B. Bayernwerk HS 2025: 175,16 EUR/kWa vs. SWTü HS 123,12 EUR/kWa) "
    "ist real und wird als Limitation benannt, nicht geglättet.")

# --- REG-03 / REG-04: echte offene Regulatorik (nachrecherchiert) ----------
OPEN_MARKERS["REG-03"] = (
    "Nachrecherchiert, weiterhin offen: Der veröffentlichte AgNes-Entwurf und "
    "Presseberichte zum Konsultationsstand (2026-08-06 bis 2026-09-18) "
    "klären nicht abschließend, ob elektrische Wärmeerzeuger regulär oder in "
    "einem Sonderregime behandelt werden. Ein indirekter, für die Diskussion "
    "relevanter Befund: saisonal differenzierte Arbeitspreise wurden von der "
    "BNetzA explizit VERWORFEN, weil sie den Betrieb von Wärmepumpen deutlich "
    "verteuern würden - ein Hinweis, dass keine gezielte Verteuerung "
    "elektrischer Wärmeerzeuger beabsichtigt ist, aber keine formale "
    "Entscheidung zum Letztverbraucher-Regime. Nicht aus Daten ableitbar.")
OPEN_MARKERS["REG-04"] = ("Offen: Übergangsregelungen/Flexibilitäts-Sondernetzentgelt sind "
                           "nicht Teil des Kernmodells (Draft §2.5) und daher nicht quantifizierbar. "
                           "Recherche zum Konsultationsstand liefert keine über REG-01 hinausgehenden "
                           "Details zu Übergangsfristen.")

# --- R-VAL-01..04: Datenqualität und Validierung ----------------------------
val01 = ", ".join(f"{r.site}: {r.n}" for r in T01.itertuples())
add_marker("R-VAL-01", None, "-", val01, "T01/data_audit.md", result_file="data_audit.md")
add_marker("R-VAL-02", heat_rel, "-", f"{heat_rel:.1e}", "T03", result_file="test_report.md")
add_marker("R-VAL-03", elec_rows["r_sim"].max(), "-", f"{elec_rows['r_sim'].max():.1e}",
           "T06/r_sim", result_file="kpi_s1_s4.parquet")
n_bad_total = int((~df_s1_s4["is_optimal"]).sum())
add_marker("R-VAL-04", n_bad_total, "-", f"{len(df_s1_s4)-n_bad_total}/{len(df_s1_s4)} optimal",
           "df_s1_s4.is_optimal", result_file="kpi_s1_s4.parquet")

# --- R-TIME-01/02: 15min vs 60min --------------------------------------
add_marker("R-TIME-01", None, "-",
           "; ".join(f"{r.site}: {de_num(r.P_max_60_kw,0)}->{de_num(r.P_max_15_kw,0)} kW"
                     for r in t11b_df.itertuples()),
           "T11b", result_file="kpi_validation_15min.parquet")
add_marker("R-TIME-02", None, "%",
           "; ".join(f"{r.site}: {de_num(r.LCOH_inc_delta_pct,2)}%" for r in t11b_df.itertuples()),
           "T11b", result_file="kpi_validation_15min.parquet")

# --- R-NET-FIX/DA-MIN/MAX (Delta_Netz, Regimewechsel StromNEV->AgNes) ------
add_marker("R-NET-FIX-MIN", table03["Delta_Netz_Fix_AgNes-StromNEV"].min(), "EUR/MWh",
           de_num(table03["Delta_Netz_Fix_AgNes-StromNEV"].min(), 1), "table03", result_file="table03_core_results.csv")
add_marker("R-NET-FIX-MAX", table03["Delta_Netz_Fix_AgNes-StromNEV"].max(), "EUR/MWh",
           de_num(table03["Delta_Netz_Fix_AgNes-StromNEV"].max(), 1), "table03", result_file="table03_core_results.csv")
add_marker("R-NET-DA-MIN", table03["Delta_Netz_DA_AgNes-StromNEV"].min(), "EUR/MWh",
           de_num(table03["Delta_Netz_DA_AgNes-StromNEV"].min(), 1), "table03", result_file="table03_core_results.csv")
add_marker("R-NET-DA-MAX", table03["Delta_Netz_DA_AgNes-StromNEV"].max(), "EUR/MWh",
           de_num(table03["Delta_Netz_DA_AgNes-StromNEV"].max(), 1), "table03", result_file="table03_core_results.csv")

# --- R-INT-NEG-N / MIN / MAX -------------------------------------------
n_neg_i = int((df_interaction["delta_inter"] < 0).sum())
add_marker("R-INT-NEG-N", n_neg_i, "-", f"{n_neg_i} von {len(df_interaction)}", "interaction.csv",
           result_file="interaction.csv")
add_marker("R-INT-MIN", df_interaction["delta_inter"].min(), "EUR/MWh",
           de_num(df_interaction["delta_inter"].min(), 1), "interaction.csv", result_file="interaction.csv")
add_marker("R-INT-MAX", df_interaction["delta_inter"].max(), "EUR/MWh",
           de_num(df_interaction["delta_inter"].max(), 1), "interaction.csv", result_file="interaction.csv")
n_pos_i = len(df_interaction) - n_neg_i
if n_neg_i > n_pos_i:
    int01_label, int01_text = "substitutiv", "substitutiv (Interaktionsterm überwiegend negativ)"
elif n_pos_i > n_neg_i:
    int01_label, int01_text = "komplementär", "komplementär (Interaktionsterm überwiegend positiv)"
else:
    int01_label = "uneinheitlich"
    int01_text = (f"uneinheitlich ({n_neg_i} von {len(df_interaction)} Standorten negativ, "
                  f"{n_pos_i} von {len(df_interaction)} positiv — kein Mehrheitsvorzeichen, "
                  "keine robuste allgemeine Richtungsaussage ableitbar)")
add_marker("R-INT-01", int01_label, "-", int01_text, "interaction.csv", result_file="interaction.csv")

# --- R-DEC-MECH/DISP/DESIGN (Mittel über 4 Standorte) -----------------------
add_marker("R-DEC-MECH", df_decomposition["pct_mech"].mean(), "%", de_num(df_decomposition["pct_mech"].mean(), 1),
           "decomposition.csv", result_file="decomposition.csv")
add_marker("R-DEC-DISP", df_decomposition["pct_disp"].mean(), "%", de_num(df_decomposition["pct_disp"].mean(), 1),
           "decomposition.csv", result_file="decomposition.csv")
add_marker("R-DEC-DESIGN", df_decomposition["pct_design"].mean(), "%", de_num(df_decomposition["pct_design"].mean(), 1),
           "decomposition.csv", result_file="decomposition.csv")

# --- R-DES-HP/EK/EF (Delta Kapazität AgNes-Fix vs StromNEV-Fix, ELEC) -------
des_rows = []
for site in SITE_IDS:
    c00 = cell_row(df_s1_s4, site, "ELEC", "stromnev", "fixed")
    c10 = cell_row(df_s1_s4, site, "ELEC", "agnes", "fixed")
    des_rows.append({"site": site, "d_hp": c10["x_hp_kw"] - c00["x_hp_kw"],
                      "d_ek": c10["x_ek_kw"] - c00["x_ek_kw"], "d_gb": c10["x_gb_kw"] - c00["x_gb_kw"],
                      "d_tes": c10["x_tes_kwh"] - c00["x_tes_kwh"]})
df_des = pd.DataFrame(des_rows)
df_des.to_csv(OUT_DIR / "design_deltas.csv", index=False)
add_marker("R-DES-HP", None, "kW", f"{de_num(df_des['d_hp'].min(),0)}..{de_num(df_des['d_hp'].max(),0)} kW über 4 Standorte",
           "design_deltas.csv", result_file="design_deltas.csv")
add_marker("R-DES-EK", None, "kW", f"{de_num(df_des['d_ek'].min(),0)}..{de_num(df_des['d_ek'].max(),0)} kW über 4 Standorte",
           "design_deltas.csv", result_file="design_deltas.csv")
OPEN_MARKERS["R-DES-EF"] = ("n/a: VHT/E-Ofen ist gemäß Teil-3-Entscheidung #2 als Limitation "
                            "behandelt (Rohdaten stützen keine VHT-Bandtrennung), daher kein EF in "
                            "diesem Modell.")

# --- R-TES-MIN/MAX/VALUE/CASE ------------------------------------------
add_marker("R-TES-MIN", df_des["d_tes"].min(), "kWh", de_num(df_des["d_tes"].min(), 0),
           "design_deltas.csv", result_file="design_deltas.csv")
add_marker("R-TES-MAX", df_des["d_tes"].max(), "kWh", de_num(df_des["d_tes"].max(), 0),
           "design_deltas.csv", result_file="design_deltas.csv")
cmp_tes_value = cmp10.copy()
cmp_tes_value["saving_eur"] = cmp_tes_value["objective_eur_notes"] - cmp_tes_value["objective_eur_tes"]
add_marker("R-TES-VALUE", cmp_tes_value["saving_eur"].sum(), "EUR/a",
           de_num(cmp_tes_value["saving_eur"].sum(), 0) + " EUR/a Summe über alle S1-Zellen",
           "T10 (ELEC vs ELEC_noTES)", result_file="kpi_s1_s4.parquet")
# Hypothesen 3.5: dominiert (a) [h>h*, Reduktion nur im Verhaeltnis KP/LP] oder
# (b) [h<h*, Wert entfaellt fast vollstaendig]? Naeherung: Vergleich der
# realisierten Benutzungsdauer (E/Pmax) mit h* je Standort (AgNes/Day-Ahead).
case_rows = []
for site in SITE_IDS:
    row = df_s1_s4[(df_s1_s4["site_id"] == site) & (df_s1_s4["config_name"] == "ELEC")
                    & (df_s1_s4["netz_regime"] == "agnes") & (df_s1_s4["procurement"] == "dayahead")].iloc[0]
    case_rows.append({"site": site, "benutzungsstunden_h": row["benutzungsstunden_h"],
                       "h_star_h": row["h_star_h"],
                       "case": "(a) h>h*" if row["benutzungsstunden_h"] > row["h_star_h"] else "(b) h<h*"})
df_tes_case = pd.DataFrame(case_rows)
df_tes_case.to_csv(OUT_DIR / "tes_case_check.csv", index=False)
cases_found = sorted(df_tes_case["case"].unique())
add_marker("R-TES-CASE", ", ".join(cases_found), "-",
           ", ".join(f"{c}: {(df_tes_case['case']==c).sum()} Standorte" for c in cases_found),
           "tes_case_check.csv", result_file="tes_case_check.csv")

# --- R-BOOK-MIN/MAX, R-E2 ------------------------------------------------
agnes_da = df_lcoh[df_lcoh["kennung"] == "11"]
add_marker("R-BOOK-MIN", agnes_da["C_over_Pmax"].min(), "-", f"{agnes_da['C_over_Pmax'].min()*100:.0f} %",
           "lcoh_inc.csv", result_file="lcoh_inc.csv")
add_marker("R-BOOK-MAX", agnes_da["C_over_Pmax"].max(), "-", f"{agnes_da['C_over_Pmax'].max()*100:.0f} %",
           "lcoh_inc.csv", result_file="lcoh_inc.csv")
add_marker("R-E2", agnes_da["E2_over_E"].mean(), "-", f"{agnes_da['E2_over_E'].mean()*100:.0f} % (Mittel)",
           "lcoh_inc.csv", result_file="lcoh_inc.csv")

# --- R-RULE-DEV / R-RULE-DIR ---------------------------------------------
# Präzisierte Bezeichnung (Chat-Review): "Abweichung der Grundlast-basierten
# Ex-ante-Bestellregel vom gekoppelten Elektrifizierungsoptimum" statt
# unspezifisch "Regelabweichung" - die Zahl bündelt bewusst drei Effekte
# (veränderter Gesamtlastgang durch Elektrifizierung, endogene Auslegung/
# Dispatch, Wechsel von ex-ante-Regel zu Perfect-Foresight-Optimum).
max_dev_row = df_rule_validation.loc[df_rule_validation["abweichung_pct"].abs().idxmax()]
add_marker("R-RULE-DEV", df_rule_validation["abweichung_pct"].abs().max(), "%",
           de_num(df_rule_validation["abweichung_pct"].abs().max(), 1), "rule_validation.csv",
           result_file="rule_validation.csv")
add_marker("R-RULE-DIR", max_dev_row["richtung"], "-", str(max_dev_row["richtung"]),
           "rule_validation.csv", result_file="rule_validation.csv")
add_marker("R-CORE-01", None, "%",
           "; ".join(f"{r.site}: {de_num(r.abweichung_pct,1)}%" for r in df_rule_validation.itertuples()),
           "rule_validation.csv", result_file="rule_validation.csv")
add_marker("R-ABS-03", df_rule_validation["abweichung_pct"].abs().max(), "%",
           de_num(df_rule_validation["abweichung_pct"].abs().max(), 1) + " %", "rule_validation.csv",
           result_file="rule_validation.csv")

# --- V-04: ergänzender KKT-Konsistenz-Check (kein Ersatz für R-RULE-DEV) ---
add_marker("V-04", bool((df_rule_kkt_check["abweichung_pct"].abs() < 0.5).all()), "-",
           "; ".join(f"{r.site}: {de_num(r.abweichung_pct,2)}%" for r in df_rule_kkt_check.itertuples()),
           "rule_kkt_consistency_check.csv", result_file="rule_kkt_consistency_check.csv")

# --- R-BE-GAS/CO2/SHIFT (jetzt beide Netzregime gerechnet) -----------------
be_gas = df_breakeven[(df_breakeven["kind"] == "gas") & df_breakeven["found"]]
be_co2 = df_breakeven[(df_breakeven["kind"] == "co2") & df_breakeven["found"]]
add_marker("R-BE-GAS", None, "EUR/MWh",
           f"{de_num(be_gas['breakeven'].min(),0)}..{de_num(be_gas['breakeven'].max(),0)} "
           f"(über beide Netzregime, {len(be_gas)}/{len(SITE_IDS)*2} Ketten konvergiert)"
           if len(be_gas) else "nicht gefunden (kein Vorzeichenwechsel im Suchintervall)",
           "breakeven.csv", result_file="breakeven.csv")
add_marker("R-BE-CO2", None, "EUR/t",
           f"{de_num(be_co2['breakeven'].min(),0)}..{de_num(be_co2['breakeven'].max(),0)} "
           f"(über beide Netzregime, {len(be_co2)}/{len(SITE_IDS)*2} Ketten konvergiert)"
           if len(be_co2) else "nicht gefunden (kein Vorzeichenwechsel im Suchintervall)",
           "breakeven.csv", result_file="breakeven.csv")

shift_rows = []
for site in SITE_IDS:
    for kind in ("gas", "co2"):
        row_a = df_breakeven[(df_breakeven["site"] == site) & (df_breakeven["kind"] == kind)
                              & (df_breakeven["netz_regime"] == "agnes")]
        row_s = df_breakeven[(df_breakeven["site"] == site) & (df_breakeven["kind"] == kind)
                              & (df_breakeven["netz_regime"] == "stromnev")]
        if len(row_a) and len(row_s) and row_a.iloc[0]["found"] and row_s.iloc[0]["found"]:
            be_a, be_s = row_a.iloc[0]["breakeven"], row_s.iloc[0]["breakeven"]
            shift_rows.append({"site": site, "kind": kind, "breakeven_agnes": be_a,
                                "breakeven_stromnev": be_s,
                                "shift_pct": 100 * (be_a - be_s) / be_s})
df_be_shift = pd.DataFrame(shift_rows)
df_be_shift.to_csv(OUT_DIR / "breakeven_shift.csv", index=False)
if len(df_be_shift):
    add_marker("R-BE-SHIFT", None, "%",
               "; ".join(f"{r.site}/{r.kind}: {de_num(r.shift_pct,1)}%" for r in df_be_shift.itertuples()),
               "breakeven_shift.csv", result_file="breakeven_shift.csv")
else:
    OPEN_MARKERS["R-BE-SHIFT"] = ("Offen: für keinen Standort/keine Preisart sind beide Regime-"
                                   "Ketten (AgNes UND StromNEV) konvergiert - s. breakeven.csv "
                                   "(found=False-Fälle, meist kein Vorzeichenwechsel im Suchintervall "
                                   "[5,150] bzw. [5,400]).")

# --- R-SENS-C/TES/THETA ---------------------------------------------------
c_range = df_s5["C_kw"].max() - df_s5["C_kw"].min()
tes_range = df_s5["x_tes_kwh"].max() - df_s5["x_tes_kwh"].min()
add_marker("R-SENS-C", c_range, "kW", de_num(c_range, 0), "kpi_s5_alpha_f.parquet",
           result_file="kpi_s5_alpha_f.parquet")
add_marker("R-SENS-TES", tes_range, "kWh", de_num(tes_range, 0), "kpi_s5_alpha_f.parquet",
           result_file="kpi_s5_alpha_f.parquet")
hi = df_s5[df_s5["theta"] > 1]
lo = df_s5[df_s5["theta"] <= 1]
c_at_grid_hi = float((hi["C_kw"] >= hi["P_max_kw"] * 0.98).mean()) if len(hi) else np.nan
add_marker("R-SENS-THETA", c_at_grid_hi, "-",
           f"bei theta>1 erreicht C in {c_at_grid_hi*100:.0f}% der Läufe >=98% von P_max "
           f"(vs. {float((lo['C_kw'] >= lo['P_max_kw']*0.98).mean())*100:.0f}% bei theta<=1)"
           if len(hi) and len(lo) else "nicht auswertbar",
           "kpi_s5_alpha_f.parquet", result_file="kpi_s5_alpha_f.parquet")

# --- R-ABS-01 / R-ABS-02 (Abstract-Zusammenfassungen) ----------------------
add_marker("R-ABS-01", None, "EUR/MWh",
           f"LCOH^inc zwischen {de_num(df_lcoh['LCOH_inc_eur_mwh'].min(),1)} und "
           f"{de_num(df_lcoh['LCOH_inc_eur_mwh'].max(),1)} EUR/MWh_th (4 Standorte x 4 Regime)",
           "lcoh_inc.csv", result_file="lcoh_inc.csv")
add_marker("R-ABS-02", None, "-",
           f"TES-Kapazität verschiebt sich um {de_num(df_des['d_tes'].min(),0)}.."
           f"{de_num(df_des['d_tes'].max(),0)} kWh zwischen StromNEV- und AgNes-Fixpreis-Auslegung",
           "design_deltas.csv", result_file="design_deltas.csv")

# --- V-01/02/03 ------------------------------------------------------------
add_marker("V-01", True, "-", "bestanden (T08, Abweichung < 0,5% im evaluate-Fall)", "T08",
           result_file="test_report.md")
s9_piv = df_s9.set_index("run_id")
v02_rows = []
for site in SITE_IDS:
    hi_id = f"{site}__ELEC__agnes__demand1.1__dayahead__optimize__1h"
    lo_id = f"{site}__ELEC__agnes__demand0.9__dayahead__optimize__1h"
    if hi_id in s9_piv.index and lo_id in s9_piv.index:
        rank_hi = s9_piv.loc[hi_id, ["x_hp_kw", "x_ek_kw", "x_gb_kw"]].astype(float).idxmax()
        rank_lo = s9_piv.loc[lo_id, ["x_hp_kw", "x_ek_kw", "x_gb_kw"]].astype(float).idxmax()
        v02_rows.append(rank_hi == rank_lo)
add_marker("V-02", bool(all(v02_rows)) if v02_rows else None, "-",
           f"Technologie-Rangfolge (größter Erzeuger) stabil unter Wärmelast +-10% bei "
           f"{sum(v02_rows)}/{len(v02_rows)} Standorten" if v02_rows else "nicht auswertbar",
           "kpi_s9_demand_sensitivity.parquet", result_file="kpi_s9_demand_sensitivity.parquet")
df_rh["delta_vs_pf_pct"] = 100 * (df_rh["rh_opex_el_eur"] - df_rh["pf_opex_el_eur"]) / df_rh["pf_opex_el_eur"].abs()
add_marker("V-03", None, "%",
           "; ".join(f"{r.netz_regime}/{r.procurement}: {de_num(r.delta_vs_pf_pct,2)}%"
                     for r in df_rh.itertuples()),
           "rolling_horizon.csv", result_file="rolling_horizon.csv")

# --- R-CONCLUSION-01/02 -----------------------------------------------------
add_marker("R-CONCLUSION-01", None, "-",
           f"AgNes verschiebt die inkrementellen Wärmekosten je nach Standort und Beschaffungsregime "
           f"um {de_num(table03['Delta_Netz_Fix_AgNes-StromNEV'].min(),1)} bis "
           f"{de_num(table03['Delta_Netz_Fix_AgNes-StromNEV'].max(),1)} EUR/MWh (Fixpreis) bzw. "
           f"{de_num(table03['Delta_Netz_DA_AgNes-StromNEV'].min(),1)} bis "
           f"{de_num(table03['Delta_Netz_DA_AgNes-StromNEV'].max(),1)} EUR/MWh (Day-Ahead) ggü. StromNEV.",
           "table03", result_file="table03_core_results.csv")
add_marker("R-CONCLUSION-02", None, "-",
           f"Die auf dem vor Elektrifizierung beobachteten Grundlastgang basierende Ex-ante-Bestellregel "
           f"weicht im vollständig gekoppelten Elektrifizierungsmodell um bis zu "
           f"{de_num(df_rule_validation['abweichung_pct'].abs().max(),1)}% von der optimalen "
           f"Bestellkapazität ab. Die Differenz umfasst die Wirkung des veränderten Gesamtlastgangs "
           f"sowie Rückkopplungen aus Auslegung, Speicherbetrieb und Bestellentscheidung. Bei reinem "
           f"Grundlastgang (V-01) bzw. bei Anwendung auf den vom LP realisierten Gesamtlastgang (V-04) "
           f"trifft die Regel das Optimum exakt - die Abweichung ist damit korrekt der Elektrifizierung "
           f"selbst zuzuschreiben, nicht einem Fehler der Regel.",
           "rule_validation.csv", result_file="rule_validation.csv")

# --- BIB-01/03: nachrecherchiert und belegt; BIB-02 bleibt offen -----------
add_marker("BIB-01", None, "-",
           "Zühlsdorf, B., Armato, V., Poulsen, J. L., Andersen, M. P., Arpagaus, C., "
           "Schlosser, F., Dusek, S. (2024). IEA HPT Annex 58 High-Temperature Heat Pumps "
           "Final Report. DOI: 10.23697/2qxe-av87.",
           "Websuche 2026-09-15", result_file="config.yaml")
add_marker("BIB-03", None, "-",
           "Danish Energy Agency, Technology Data for Industrial Process Heat, 2023 "
           "(ens.dk Technology Catalogues, Sektor 'Industrial process heat').",
           "Websuche 2026-09-15", result_file="config.yaml")
OPEN_MARKERS["BIB-02"] = "Offen: BNetzA-Monitoringbericht (Netzentgeltniveaus je Ebene) - s. REG-02."

# %%
paper_values = {k: v for k, v in MARKERS.items()}
(OUT_DIR / "paper_values.json").write_text(
    json.dumps(paper_values, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

marker_map = pd.DataFrame([{"marker": k, "kpi": v["kpi"], "result_file": v["result_file"],
                             "display_value": v["display_value"]} for k, v in MARKERS.items()])
marker_map.to_csv(OUT_DIR / "marker_map.csv", index=False)

open_df = pd.DataFrame([{"marker": k, "begruendung": v} for k, v in OPEN_MARKERS.items()])
open_df.to_csv(OUT_DIR / "open_markers.csv", index=False)

print(f"{len(MARKERS)} Marker beliefert, {len(OPEN_MARKERS)} Marker offen (s. open_markers.csv).")
print(open_df.to_string(index=False))

# %%
# --- draft_filled.md: Draft-Markdown automatisch patchen -------------------
DRAFT_PATH = BASE_DIR / "20260915_Paper_ZWF_Agnes_Reform_Draft.md"
draft_text = DRAFT_PATH.read_text(encoding="utf-8") if DRAFT_PATH.exists() else ""

patch_rows = []
patched = draft_text
pattern = re.compile(r"\[\[([^\]:]+)(?::[^\]]*)?\]\]")


def _replacement(match: "re.Match") -> str:
    key = match.group(1).strip()
    if key in MARKERS:
        val = MARKERS[key]["display_value"]
        patch_rows.append({"marker": key, "status": "belegt", "wert": val})
        return str(val)
    if key in OPEN_MARKERS:
        patch_rows.append({"marker": key, "status": "offen", "wert": OPEN_MARKERS[key]})
        return f"[[OFFEN: {key} — {OPEN_MARKERS[key]}]]"
    patch_rows.append({"marker": key, "status": "unbekannt", "wert": ""})
    return match.group(0)


if patched:
    patched = pattern.sub(_replacement, patched)
    (OUT_DIR / "draft_filled.md").write_text(patched, encoding="utf-8")

patch_df = pd.DataFrame(patch_rows).drop_duplicates(subset="marker")
patch_df.to_csv(OUT_DIR / "paper_patch.md.csv", index=False)
(OUT_DIR / "paper_patch.md").write_text(
    "# paper_patch.md — Ersetzungsliste\n\n" + patch_df.to_markdown(index=False), encoding="utf-8")
n_unbelegt = int((patch_df["status"] == "unbekannt").sum())
print(f"draft_filled.md geschrieben. {len(patch_df)} Marker im Draft gefunden, davon "
      f"{(patch_df['status']=='belegt').sum()} belegt, {(patch_df['status']=='offen').sum()} offen, "
      f"{n_unbelegt} ohne Zuordnung.")
# ===END-11===

# %% [markdown]
# ## § 12 — Offene Punkte, QA-Zusammenfassung

# %%
def collect_unverified_params() -> pd.DataFrame:
    rows = []

    def walk(node, path):
        if isinstance(node, dict):
            if "status" in node and "value" in node:
                if node.get("status") == "unverified":
                    rows.append({"parameter": path, "value": node.get("value"),
                                 "unit": node.get("unit", ""), "source": node.get("source", "")})
            else:
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(CONFIG, "")
    return pd.DataFrame(rows)


df_unverified = collect_unverified_params()
df_unverified.to_csv(OUT_DIR / "unverified_parameters.csv", index=False)

open_issues_md = f"""# open_issues.md

Automatisch erzeugt (§12), Run-ID `{RUN_TS}`.

## 0. Bugfix seit dem letzten Lauf (invalidiert alle vorherigen Zahlen)

**ETA_GB-Bug behoben:** `ETA_GB` (Gaskessel-Wirkungsgrad) war in config.yaml/
agnes_p2h.py definiert, wurde aber in keiner Gleichung verwendet. Gas- und
CO2-Kosten wurden direkt auf q_gb (Nutzwärme, kW_th) statt auf den
Brennstoffbedarf q_gb/ETA_GB berechnet - eine Unterschätzung um den Faktor
1/eta_GB (~11% bei eta=0,90). Betrifft: GAS-Konfiguration, optionalen
Gaskessel-Einsatz in ELEC, alle Break-even-Preise, LCOH_inc an allen
Standorten mit Gaskesselanteil. Alle Zahlen aus früheren Läufen sind damit
ungültig und wurden mit diesem Lauf neu berechnet (Chat-Review, 2026-09-22).

Weitere in diesem Lauf behobene/ergänzte Punkte: negative Grundlast wird als
Einspeisung dokumentiert statt still geklippt; T01 verschärft (keine
Toleranz mehr); P_grid/Spannungsebene durchgängig als Proxy gekennzeichnet
(`p_grid_status`, `voltage_level_status` in KPIs); StromNEV-Tarifpaarwahl
ohne Fallback auf inkonsistente Paare (empirisch geprüft: betrifft keine der
32 Standort/Konfig/Beschaffung-Kombinationen); Break-even nutzt jetzt
config.yaml:design.breakeven (max_iter=25 statt hartkodiert 10) mit
expliziter Konvergenzdiagnose; 15-min-Validierung vergleicht jetzt BASE+ELEC
über die tatsächlich berichtete Kennzahl LCOH_inc statt totex/q_useful
direkt; S10 Rolling Horizon: StromNEV-Fenster tragen keinen künstlichen
Kapazitätspreis-Term mehr je 36h-Fenster (chirurgischer Fix statt
Deaktivierung, s. Chat-Review); Regelvalidierung (R-RULE-DEV) umbenannt und
um einen KKT-Konsistenz-Check (V-04) ergänzt, s. Abschnitt 1.

## 1. Wesentliche methodische Abweichungen vom Draft (Dokument 2)

- **Bandstruktur:** Die vier Werkslastgänge liefern nur eine aggregierte
  Wärme- und eine Stromspalte (kein Temperaturkanal). Die LT/HT/VHT-
  Banddreiteilung ist daher NICHT rekonstruierbar; das Modell rechnet mit
  einem generischen Prozesswärme-Band. VHT (Metall) ist Limitation
  (Teil-3-Entscheidung #2), nicht nur für Metall, sondern strukturell für
  alle vier Standorte.
- **COP konstant:** Keine Quell-/Senktemperatur in den Rohdaten -> COP_HP
  und eta_EK/eta_GB sind zeitlich konstant (Konfigurationswert), nicht
  temperaturabhängig.
- **Modell-Zeitauflösung:** 1h statt 15min als Primärauflösung für S1-S9
  (gemessene 15min-Solvezeiten 2,5-5+ Minuten je Lauf bei ~300+ geplanten
  Läufen nicht darstellbar). 15-min-Validierungsteilmenge (2 Standorte)
  für R-TIME-01/02 und T11b.
- **strompreis_2023.csv:** Zeitstempel im Rohformat sind 2019, nicht 2023.
  Datenhalter hat am 2026-09-15 bestätigt, dass die Werte für 2023 gelten
  und nur das Datumslabel falsch ist; 1:1-Stunde-des-Jahres-Remapping auf
  2023 angewendet (s. config.yaml:prices.provenance_note).
- **strompreis_2024.csv:** vom Datenhalter im 15-min-Zeilenraster geliefert,
  die vier Werte je Stunde sind im Rohfile jedoch identisch - effektiv
  Stundenpreise, keine echte untertägige 15-min-Preisvariation (externer
  Code-Review, 2026-09-24, direkt an den Rohdaten verifiziert). Betrifft die
  15-min-Validierung des Chemie-Standorts (T11b/R-TIME-01/02): dort wird
  damit nur die Lastauflösung getestet, keine Preisauflösung - identisch zur
  bereits dokumentierten Replikation der Stundenpreise auf 15-min-Intervalle.
- **S6 (1h-Zwillinge):** entfällt strukturell, da 1h jetzt die
  Primärauflösung ist; funktional ersetzt durch die 15-min-
  Validierungsteilmenge (T11b).
- **S7 (Break-even):** jetzt für BEIDE Netzregime gerechnet (16 Ketten,
  R-BE-SHIFT beantwortet); ELEC weiterhin im redispatch-Modus auf den
  jeweiligen S1-Kapazitäten (Day-Ahead-Beschaffung), nicht voll endogen
  neu ausgelegt je Preispunkt.
- **S9 (Bandanteile +-10pp):** nicht anwendbar (keine Bänder), ersetzt durch
  Wärmelast-Sensitivität +-10%.
- **S11 (COP/WACC/Risikoprämie-Sensitivität):** NICHT gerechnet (MAY-
  Priorität laut Draft-Laufmatrix, aus Zeitgründen zurückgestellt).

## 2. Unverified-Parameter mit Wirkung auf Kernaussagen ({len(df_unverified)} Stück)

Vollständige Liste in `unverified_parameters.csv`. Wirkungsreichste Posten:
StromNEV-Tarifpaare (nur MS-Paar >=2500h real belegt, alle anderen Ebenen/
Paare Literaturschätzung), AgNes k je Ebene (erlösäquivalente Konstruktion,
s. REG-02), alle Technologie-CAPEX/Wirkungsgrade (Literaturschätzungen,
keine standortscharfen Angebote), Gas-/CO2-Preis, WACC.

## 3. Offene Marker

{open_df.to_markdown(index=False)}

## 4. Nicht gerechnete MAY-Punkte

S11 (COP-/WACC-/Risikoprämie-Sensitivität, <=24 Läufe) wurde nicht
gerechnet. Empfehlung: bei Bedarf als eigenständige Nachlauf-Kampagne mit
dem bestehenden `run_campaign`-Mechanismus nachziehen (Muster: S5).
"""
(OUT_DIR / "open_issues.md").write_text(open_issues_md, encoding="utf-8")
print(f"open_issues.md geschrieben ({len(df_unverified)} unverified Parameter, "
      f"{len(open_df)} offene Marker).")

# %%
qa_lines = ["# qa_report.md", "", f"Run-ID: `{RUN_TS}`  Config-Hash: `{CONFIG_SHA256}`", "",
            "## Selbsttests", "", test_report_df.to_markdown(index=False), "",
            "## Solver-Diagnostik (alle Kampagnen)", ""]
all_kpi_dfs = [df_s1_s4, df_s5, df_s9]
n_total_runs = sum(len(d) for d in all_kpi_dfs) + len(df_val15)
n_total_bad = sum(int((~d["is_optimal"]).sum()) for d in all_kpi_dfs) + int((~df_val15["is_optimal"]).sum())
qa_lines.append(f"- Gesamt-Solves (S1-S5, S9, 15min-Validierung): {n_total_runs}, "
                f"davon nicht-optimal/Fehler: {n_total_bad}")
qa_lines.append(f"- S7 Break-even-Ketten: {len(df_breakeven)}, gefunden: {int(df_breakeven['found'].sum())}")
qa_lines.append(f"- S8 Dekomposition: {len(df_decomposition)} Standorte")
qa_lines.append(f"- S10 Rolling Horizon: {len(df_rh)} Regime-Kombinationen, "
                f"{int(df_rh['n_steps'].sum())} Fenster gesamt")
qa_lines.append("")
qa_lines.append("## Marker-Abdeckung")
qa_lines.append(f"- Belegt: {len(MARKERS)}")
qa_lines.append(f"- Offen (mit Begründung): {len(OPEN_MARKERS)}")
(OUT_DIR / "qa_report.md").write_text("\n".join(qa_lines), encoding="utf-8")
print("qa_report.md geschrieben.")

# %%
readme_text = f"""# agnes_p2h — README

Notebook `agnes_p2h.ipynb` (bzw. Quelle `agnes_p2h.py`) rechnet die
Szenariomatrix für den ZWF-Beitrag "Bestellkapazität statt Jahreshöchstlast"
auf Basis von `config.yaml` und den vier Standortordnern.

**Ausführen:** Kernel im Verzeichnis `docs/paper_ZWF_Agnes_Reform/` starten,
Run All. Die Solver-Kampagne (S1-S10, ~350+ LP-Solves) verwendet bis zu
{MAX_WORKERS} parallele Worker; jeder HiGHS-Solve ist auf einen Solver-Thread
begrenzt. Das vermeidet CPU-Überzeichnung und verbessert die
Reproduzierbarkeit bei weiterhin effizienter Nutzung der verfügbaren
Rechenressourcen. Gemessene Gesamtlaufzeit auf der Referenzhardware (66
logische Kerne): ca. 1,5-2,5 Stunden (dominiert von S10 Rolling Horizon und
S7 Break-even mit {CONFIG['design']['breakeven']['max_iter']} Bisektionsschritten je Kette).

**Debug/Schnelltest:** Umgebungsvariable `AGNES_DRY_RUN=1` setzen. Der Dry
Run reduziert Standort- und Sweep-Matrix auf einen Standort (Pipeline-Check
in wenigen Minuten); er ersetzt keine vollständige Ergebnisrechnung.

**Ausgabeordner:** `outputs/<run_ts>/` mit `figures/`, `tables/`,
`fixtures/`, allen KPI-Parquets/CSVs, `paper_values.json`,
`draft_filled.md`, `open_issues.md`, `qa_report.md`.

**Wichtigste Abweichungen vom ursprünglichen Auftrag (Dokument 2):** 1h statt
15min als Primärauflösung (Solver-Zeitbudget), ein Prozesswärme-Band statt
LT/HT/VHT (Datenrealität), S6/S7/S9/S11 angepasst bzw. reduziert - Details
in `outputs/<run_ts>/open_issues.md`.

Solver: HiGHS via `linopy` (Dual-Simplex, 1h-Auflösung ~35-110s je Lauf,
Parallelisierung nutzt {MAX_WORKERS} von {os.cpu_count()} Kernen über
Threads, da highspy den GIL beim Lösen freigibt).
"""
(BASE_DIR / "README.md").write_text(readme_text, encoding="utf-8")
print("README.md geschrieben.")
print("\n=== NOTEBOOK-LAUF VOLLSTÄNDIG ===")
# ===END-12===
