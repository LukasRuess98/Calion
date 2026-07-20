import pandas as pd
import os

acron = "data/Stadtbach/11_Messwerte_Acron"

consumer_stations = [
    "Am_Mittleren_Moos", "August-Wessels-Str", "Beethovenpark", "Don_Bosco",
    "Fraunhofer", "Fuggerstr", "Grasiger_Weg", "Hans-Boeckler-Str",
    "Hoher_Weg", "Hooverstr", "Hunoldsgraben", "Josefinum",
    "Klinikum", "Kreissparkasse", "KUKA", "Kurt-Schumacher-Str",
    "Lechhauser_Str", "Lise-Meitner-Str", "MAN", "Schlettererstr",
    "Siegfried-Aufhaeuser-Str", "SIGMA_Technopark", "Theodor-Heuss-Platz", "UNI",
]

print("Consumer stations with Waermeleistung data:")
for station in consumer_stations:
    d = os.path.join(acron, station)
    if not os.path.isdir(d):
        print(f"  {station:<35} DIR MISSING!")
        continue
    # Non-temp xlsx files
    files = [f for f in os.listdir(d) if f.endswith(".xlsx") and not f.startswith("~")]
    wl_files = [f for f in files if "Waermeleistung" in f]
    df_files = [f for f in files if "Durchfluss" in f]
    tv_files = [f for f in files if "Temp_VL" in f]
    tr_files = [f for f in files if "Temp_RL" in f]

    if wl_files:
        fp = os.path.join(d, wl_files[0])
        df = pd.read_excel(fp, skiprows=2, header=0, engine="openpyxl")
        wert = pd.to_numeric(df["Wert"], errors="coerce")
        print(f"  {station:<35} WL={wl_files[0]:<50} mean={wert.mean():.2f} max={wert.max():.2f} MW")
    elif df_files and tv_files and tr_files:
        print(f"  {station:<35} NO WL, has Durchfluss+TV+TR -> computable")
    else:
        avail = "+".join([("DF" if df_files else ""), ("TV" if tv_files else ""), ("TR" if tr_files else "")]).strip("+")
        print(f"  {station:<35} NO WL, avail={avail if avail else 'none'}")
