# 🪟 Windows Setup Guide

Schnelle Anleitung für die Integration der neuen Features unter Windows.

## ⚡ Quick Start

### 1. Package installieren
```cmd
# Im Projekt-Root (wo setup.py ist):
pip install -e .
```

### 2. Dependencies prüfen
```cmd
# Excel-Support:
pip install openpyxl

# Alle anderen Dependencies sollten bereits vorhanden sein
pip list | findstr "pyomo pandas numpy yaml"
```

### 3. Excel-Template erstellen
```cmd
python scripts\create_thermal_network_template.py -o test_network.xlsx
```

### 4. Excel Parser testen
```cmd
# NICHT direkt Python-Code in CMD eingeben!
# Stattdessen unser Test-Script verwenden:
python test_excel_parser.py
```

## 🔧 Häufige Probleme

### Problem 1: "ModuleNotFoundError: No module named 'energis'"

**Lösung:**
```cmd
# Package installieren:
pip install -e .

# Prüfen:
python -c "import energis; print(energis.__version__)"
```

### Problem 2: Multi-Line Commands funktionieren nicht

**Windows CMD unterstützt KEINE `\` Continuation!**

❌ **FALSCH (funktioniert nicht):**
```cmd
python -c "from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser; \
           parser = ThermalNetworkExcelParser('test.xlsx'); \
           parser.save_yaml('output.yaml')"
```

✅ **RICHTIG (verwende Script):**
```cmd
# Erstelle ein Python-Script (z.B. convert.py):
python test_excel_parser.py
```

Oder verwende PowerShell:
```powershell
python -c "from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser; parser = ThermalNetworkExcelParser('test.xlsx'); parser.save_yaml('output.yaml')"
```

### Problem 3: Examples starten nicht

**Fehler:**
```
ModuleNotFoundError: No module named 'energis'
```

**Lösung:**
```cmd
# 1. Package installieren
pip install -e .

# 2. Examples ausführen
python examples\runner_integration_test.py
python examples\stratified_storage_integration.py
```

## 📋 Test-Workflow

### Schritt 1: Package Setup
```cmd
cd C:\Users\LKR\Documents\GitHub\Energy_Framwork\Planing-Framework-for-Heat
pip install -e .
pip install openpyxl
```

### Schritt 2: Template erstellen
```cmd
python scripts\create_thermal_network_template.py -o mein_netzwerk.xlsx
```

### Schritt 3: Excel ausfüllen
- Öffne `mein_netzwerk.xlsx` in Excel
- Fülle die 6 Sheets aus (siehe `Anleitung` Sheet)
- Speichern

### Schritt 4: Validieren & Konvertieren
```cmd
# Verwende das Test-Script:
python test_excel_parser.py

# Oder erstelle eigenes Script:
# convert_my_network.py
```

### Schritt 5: Simulation starten
```cmd
python -m energis.run.rolling_horizon ^
    configs\base.yaml ^
    configs\scenarios\mein_netzwerk.scenario.yaml
```

## 🎯 Empfohlener Workflow

### Option A: Interaktives Python
```cmd
# Python starten
python

# Im Python-Interpreter:
>>> from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser
>>> parser = ThermalNetworkExcelParser('test_network.xlsx')
>>> summary = parser.get_summary()
>>> print(summary)
>>> errors = parser.validate()
>>> print(f"Errors: {len(errors)}")
>>> if not errors:
...     parser.save_yaml('output.yaml')
>>> exit()
```

### Option B: PowerShell (besser als CMD)
```powershell
# PowerShell unterstützt bessere Multi-Line:
python -c @"
from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser
parser = ThermalNetworkExcelParser('test_network.xlsx')
errors = parser.validate()
if not errors:
    parser.save_yaml('output.yaml')
    print('Success!')
else:
    for error in errors:
        print(f'ERROR: {error}')
"@
```

### Option C: Python-Script (EMPFOHLEN!)
```cmd
# Erstelle convert.py:
notepad convert.py

# Füge ein:
from energis.utils.thermal_network_excel_parser import ThermalNetworkExcelParser

parser = ThermalNetworkExcelParser('test_network.xlsx')
errors = parser.validate()

if not errors:
    parser.save_yaml('output.yaml')
    print('✓ YAML created successfully!')
else:
    print(f'❌ {len(errors)} validation errors:')
    for error in errors:
        print(f'  - {error}')

# Dann ausführen:
python convert.py
```

## 📚 Dokumentation

Alle Guides sind verfügbar:
- `docs\excel_import_feature.md` - Excel-Import Guide
- `docs\brownfield_quickstart_guide.md` - Brownfield-Guide
- `INTEGRATION_SUMMARY.md` - Vollständige Übersicht
- `QUICK_REFERENCE.md` - Schnellreferenz

## 🆘 Support

Bei Problemen:
1. Prüfe ob `pip install -e .` ausgeführt wurde
2. Prüfe ob alle Dependencies installiert sind
3. Verwende `test_excel_parser.py` statt direkte Commands
4. Siehe `INTEGRATION_SUMMARY.md` für Details

## ✅ Installations-Checkliste

- [ ] Package installiert: `pip install -e .`
- [ ] openpyxl installiert: `pip install openpyxl`
- [ ] Import funktioniert: `python -c "import energis"`
- [ ] Template erstellt: `python scripts\create_thermal_network_template.py -o test.xlsx`
- [ ] Parser getestet: `python test_excel_parser.py`
- [ ] Examples funktionieren: `python examples\runner_integration_test.py`

Wenn alle ✅ sind, bist du ready! 🚀
