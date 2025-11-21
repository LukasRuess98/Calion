"""
Diagnose-Script um die Excel-Struktur zu verstehen
"""
import pandas as pd
import sys
from pathlib import Path

# Excel-Pfad von Kommandozeile
if len(sys.argv) < 2:
    print("Usage: python debug_excel_structure.py <path_to_scenario_xlsx>")
    sys.exit(1)

excel_path = sys.argv[1]
print(f"Untersuche: {excel_path}\n")
print("="*70)

# Test 1: Ohne Header-Parameter (default header=0)
print("\n1️⃣  TEST: header=0 (default), index_col=0")
print("-"*70)
try:
    df1 = pd.read_excel(excel_path, sheet_name='Timeseries', header=0, index_col=0)
    print(f"Shape: {df1.shape}")
    print(f"Index (erste 5): {list(df1.index[:5])}")
    print(f"Spalten (erste 5): {list(df1.columns[:5])}")
    print(f"Index-Typ: {type(df1.index[0]) if len(df1.index) > 0 else 'leer'}")
except Exception as e:
    print(f"FEHLER: {e}")

# Test 2: header=1, index_col=0
print("\n2️⃣  TEST: header=1, index_col=0")
print("-"*70)
try:
    df2 = pd.read_excel(excel_path, sheet_name='Timeseries', header=1, index_col=0)
    print(f"Shape: {df2.shape}")
    print(f"Index (erste 5): {list(df2.index[:5])}")
    print(f"Spalten (erste 5): {list(df2.columns[:5])}")
    print(f"Index-Typ: {type(df2.index[0]) if len(df2.index) > 0 else 'leer'}")
except Exception as e:
    print(f"FEHLER: {e}")

# Test 3: header=None (liest alles als Daten, keine Header)
print("\n3️⃣  TEST: header=None (raw data)")
print("-"*70)
try:
    df3 = pd.read_excel(excel_path, sheet_name='Timeseries', header=None)
    print(f"Shape: {df3.shape}")
    print(f"\nErste 10 Zeilen:")
    print(df3.head(10).to_string())
except Exception as e:
    print(f"FEHLER: {e}")

# Test 4: skiprows=[0], index_col=0
print("\n4️⃣  TEST: skiprows=[0] (überspringt erste Zeile), index_col=0")
print("-"*70)
try:
    df4 = pd.read_excel(excel_path, sheet_name='Timeseries', skiprows=[0], index_col=0)
    print(f"Shape: {df4.shape}")
    print(f"Index (erste 5): {list(df4.index[:5])}")
    print(f"Spalten (erste 5): {list(df4.columns[:5])}")
    print(f"Index-Typ: {type(df4.index[0]) if len(df4.index) > 0 else 'leer'}")
except Exception as e:
    print(f"FEHLER: {e}")

print("\n" + "="*70)
print("Diagnose abgeschlossen!")
