"""Außentemperatur aus dem DWD Climate Data Center (Stundenwerte einer Referenzstation).

Der anonymisierte Datensatz ``data/dhn_a/`` enthält die Temperatur bereits; dieses Modul dient der Aktualisierung.
Zeitbezug laut DWD-Metadaten: bis 30.11.1996 MEZ, ab 01.12.1996 UTC. Die Werte werden in
naive Ortszeit (Europe/Berlin, mit Sommerzeit) umgerechnet, passend zu den Zeitstempeln des Leitsystems.
"""

from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from .daten import repo_root

DWD_BASIS = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature"
UTC_AB = pd.Timestamp("1996-12-01")


def cache_dir() -> Path:
    p = repo_root() / "data" / "dwd"
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_produkt(text: str, utc_ab: pd.Timestamp = UTC_AB) -> pd.Series:
    """DWD-Produktdatei (``produkt_tu_stunde_*.txt``) → Lufttemperatur [°C] in naiver Ortszeit."""
    df = pd.read_csv(io.StringIO(text), sep=";", skipinitialspace=True)
    t = pd.to_datetime(df["MESS_DATUM"].astype(str), format="%Y%m%d%H")
    ta = pd.Series(df["TT_TU"].to_numpy(float), index=t).where(lambda s: s > -999)
    ta = ta[~ta.index.duplicated()].sort_index()
    mez = ta.index < utc_ab
    utc_index = ta.index.where(~mez, ta.index - pd.Timedelta(hours=1))   # MEZ = UTC+1
    lokal = pd.DatetimeIndex(utc_index).tz_localize("UTC").tz_convert("Europe/Berlin").tz_localize(None)
    out = pd.Series(ta.to_numpy(), index=lokal, name="Ta")
    return out[~out.index.duplicated()].sort_index()


def _zip_namen(unterordner: str, station: str) -> list[str]:
    html = urllib.request.urlopen(f"{DWD_BASIS}/{unterordner}/", timeout=60).read().decode("latin1")
    return sorted(set(re.findall(rf"stundenwerte_TU_{station}[^\"]*\.zip", html)))


def lade_dwd(station: str, download: bool = True) -> pd.Series:
    """Historische + aktuelle Stundenwerte, zwischengespeichert in ``data/dwd/``."""
    cd = cache_dir()
    if download:
        for sub in ("historical", "recent"):
            for name in _zip_namen(sub, station):
                ziel = cd / name
                if sub == "recent" or not ziel.exists():
                    urllib.request.urlretrieve(f"{DWD_BASIS}/{sub}/{name}", ziel)
    teile = []
    for z in sorted(cd.glob(f"stundenwerte_TU_{station}_*.zip")):
        with zipfile.ZipFile(z) as zf:
            prod = [n for n in zf.namelist() if n.startswith("produkt_tu_stunde")]
            teile.append(parse_produkt(zf.read(prod[0]).decode("latin1")))
    if not teile:
        raise FileNotFoundError(f"keine DWD-Dateien in {cd}")
    ta = pd.concat(teile)
    return ta[~ta.index.duplicated(keep="last")].sort_index()


def kaeltewellen(t_tag: pd.Series, von: int = 1991, bis: int = 2025, dauer=(1, 2, 3, 5)) -> pd.DataFrame:
    """Statistik der tiefsten n-Tage-Mittel je Jahr (Minimum, 10-%-Quantil, Median der Jahresminima)."""
    t = t_tag[str(von):str(bis)]
    rows = []
    for n in dauer:
        jm = t.rolling(n).mean().groupby(t.index.year).min()
        rows.append({"Dauer [d]": n, "Minimum [°C]": jm.min(), "Jahr": int(jm.idxmin()),
                     "P10 Jahresminima [°C]": jm.quantile(0.1), "Median Jahresminima [°C]": jm.median(),
                     "Jahre < −10 °C": int((jm < -10).sum())})
    return pd.DataFrame(rows)


def ta_eff(t_tag: pd.Series, gewichte=(0.5, 0.3, 0.2)) -> pd.Series:
    """Gewichtetes Mittel aus Tag, Vortag und Vorvortag (Gebäudeträgheit)."""
    return sum(w * t_tag.shift(i) for i, w in enumerate(gewichte))


def tagesmittel(s: pd.Series) -> pd.Series:
    return s.resample("D").mean()

