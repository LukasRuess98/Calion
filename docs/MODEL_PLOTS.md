# Pyomo Model Visualization Plots

Zusätzlich zu den Export-Dateien (Excel, Markdown, JSON) werden jetzt automatisch **6 professionelle Visualisierungen** erstellt, die dir helfen, das Modell vor der Optimierung zu verstehen.

## 📊 Übersicht der Plots

### 1. Model Structure Overview (Modellgröße)
**Datei:** `pyomo_model_before_solve_01_overview.png`

![Model Overview](https://via.placeholder.com/800x400/2ecc71/FFFFFF?text=Model+Structure+Overview)

**Zeigt:**
- Anzahl Sets, Parameter, Variablen, Constraints, Objectives
- Logarithmische Skala für bessere Vergleichbarkeit
- Farbkodiert für schnelle Orientierung

**Nutzen:**
- Schneller Überblick über Modellgröße
- Identifikation dominanter Komponenten
- Vergleich verschiedener Modellversionen

---

### 2. Variable Types Distribution (Variablentypen)
**Datei:** `pyomo_model_before_solve_02_variable_types.png`

![Variable Types](https://via.placeholder.com/800x400/3498db/FFFFFF?text=Variable+Types+Distribution)

**Zeigt:**
- Verteilung der Variablentypen (NonNegativeReals, Binary, etc.)
- Prozentuale Anteile
- Absolute Anzahlen

**Nutzen:**
- Verstehen der Modellstruktur (kontinuierlich vs. diskret)
- Einschätzung der Lösungskomplexität
- Identifikation von MILP vs. LP Problemen

---

### 3. Constraint Sizes (Top 20)
**Datei:** `pyomo_model_before_solve_03_constraint_sizes.png`

![Constraint Sizes](https://via.placeholder.com/800x400/e74c3c/FFFFFF?text=Constraint+Sizes)

**Zeigt:**
- Die 20 größten Constraint-Gruppen
- Anzahl der einzelnen Constraints pro Typ
- Logarithmische Skala für große Bereiche

**Nutzen:**
- Identifikation dominanter Constraints
- Verstehen der Modellkomplexität
- Erkennen von Skalierungsproblemen

---

### 4. Parameter Time Series (Zeitreihen)
**Datei:** `pyomo_model_before_solve_04_parameter_timeseries.png`

![Parameter Timeseries](https://via.placeholder.com/800x600/2ecc71/FFFFFF?text=Parameter+Time+Series)

**Zeigt:**
- Zeitreihen wichtiger Parameter (Strompreis, Wärmebedarf, CO2)
- Mittelwert (rote gestrichelte Linie)
- Verlauf über den Planungshorizont

**Nutzen:**
- Plausibilitätsprüfung der Eingangsdaten
- Erkennen von Anomalien oder Ausreißern
- Verstehen der zeitlichen Dynamik

**Erkannte Parameter:**
- `strompreis`, `price` → Strompreise
- `waermebedarf`, `demand` → Wärmebedarfe
- `co2` → CO2-Intensität
- `temperatur`, `temp` → Temperaturen

---

### 5. Variable Bounds Overview (Variablengrenzen)
**Datei:** `pyomo_model_before_solve_05_variable_bounds.png`

![Variable Bounds](https://via.placeholder.com/800x400/f39c12/FFFFFF?text=Variable+Bounds)

**Zeigt:**
- **Links:** Bounds der Top 15 Variablen (Bereichsdarstellung)
- **Rechts:** Anteil bounded vs. unbounded Variablen

**Nutzen:**
- Überprüfung realistischer Grenzen
- Identifikation potentiell unbeschränkter Variablen
- Erkennen von zu engen oder zu weiten Bounds

---

### 6. Model Complexity Matrix (Komplexitätsmatrix)
**Datei:** `pyomo_model_before_solve_06_complexity_matrix.png`

![Complexity Matrix](https://via.placeholder.com/800x600/9b59b6/FFFFFF?text=Model+Complexity+Matrix)

**Zeigt:**
- Heatmap der Modellkomplexität
- Anzahl indexierter vs. skalarer Komponenten
- Gesamtgröße der einzelnen Komponentengruppen

**Nutzen:**
- Gesamtüberblick über Modellstruktur
- Identifikation von Indexierungs-Mustern
- Verstehen der Dimensionalität

---

## 🎨 Visualisierungs-Features

### Professionelles Design
- ✅ Hochauflösend (300 DPI) für Präsentationen
- ✅ Farbkodiert für schnelle Orientierung
- ✅ Beschriftete Achsen und Werte
- ✅ Logarithmische Skalen wo sinnvoll
- ✅ Legende und Annotationen

### Automatische Anpassung
- ✅ Dynamische Skalierung basierend auf Daten
- ✅ Intelligente Auswahl relevanter Parameter
- ✅ Fehlertoleranz bei fehlenden Daten

### Export-Format
- **Format:** PNG (kompatibel mit allen Tools)
- **Auflösung:** 300 DPI (publication-ready)
- **Größe:** ~100-500 KB pro Plot

---

## 📂 Dateistruktur

Nach einem Optimierungslauf:

```
exports/YYYYMMDD_HHMMSS_<scenario_tag>/
├── model_structure/
│   ├── pyomo_model_before_solve.xlsx
│   ├── pyomo_model_before_solve.md
│   ├── pyomo_model_before_solve.json
│   ├── pyomo_model_before_solve_01_overview.png          ← NEU!
│   ├── pyomo_model_before_solve_02_variable_types.png    ← NEU!
│   ├── pyomo_model_before_solve_03_constraint_sizes.png  ← NEU!
│   ├── pyomo_model_before_solve_04_parameter_timeseries.png ← NEU!
│   ├── pyomo_model_before_solve_05_variable_bounds.png   ← NEU!
│   └── pyomo_model_before_solve_06_complexity_matrix.png ← NEU!
└── ...
```

---

## 💡 Anwendungsbeispiele

### 1. Vor der Optimierung: Schnellcheck

**Workflow:**
1. Öffne `*_01_overview.png` → Modellgröße plausibel?
2. Öffne `*_04_parameter_timeseries.png` → Eingangsdaten korrekt?
3. Öffne `*_05_variable_bounds.png` → Bounds realistisch?

**Zeitaufwand:** ~2 Minuten
**Nutzen:** Verhindert stundenlange Fehloptimierungen!

---

### 2. Debugging: Solver findet keine Lösung

**Workflow:**
1. Öffne `*_03_constraint_sizes.png` → Welche Constraints dominieren?
2. Öffne `*_02_variable_types.png` → Zu viele Binary-Variablen?
3. Öffne `*_05_variable_bounds.png` → Widersprüchliche Bounds?

**Zeitaufwand:** ~5 Minuten
**Nutzen:** Schnellere Fehleridentifikation

---

### 3. Dokumentation: Modell präsentieren

**Workflow:**
1. Kopiere alle 6 Plots in Präsentation
2. Nutze `*_01_overview.png` für Gesamtübersicht
3. Nutze `*_04_parameter_timeseries.png` für Input-Daten
4. Nutze `*_06_complexity_matrix.png` für technische Details

**Zeitaufwand:** ~10 Minuten
**Nutzen:** Professionelle, überzeugende Präsentation

---

### 4. Modellvergleich: Szenarien A vs. B

**Workflow:**
```bash
# Visuelle Vergleiche
compare scenario_A/*_01_overview.png scenario_B/*_01_overview.png
compare scenario_A/*_02_variable_types.png scenario_B/*_02_variable_types.png
```

**Zeitaufwand:** ~5 Minuten
**Nutzen:** Sofortiges Verständnis der Unterschiede

---

## 🔧 Technische Details

### Abhängigkeiten
- `matplotlib` - Plotting-Library
- `numpy` - Numerische Operationen

Wenn nicht installiert:
```bash
pip install matplotlib numpy
```

Falls fehlend, werden Plots übersprungen (ohne Fehler).

### Performance
- **Generierung:** ~2-5 Sekunden für alle 6 Plots
- **Speicher:** ~50 MB während Plot-Erstellung
- **Overhead:** Minimal, da nur vor Solver-Ausführung

### Anpassung

Plots können konfiguriert werden in `energis/io/model_inspector.py`:

```python
# Anzahl angezeigter Constraints ändern
constraints = inspection.get("constraints", [])[:20]  # Hier ändern

# Auflösung ändern
plt.savefig(path, dpi=300)  # Hier ändern (150, 300, 600)

# Farben anpassen
colors = ['#2ecc71', '#3498db', ...]  # Hier ändern
```

---

## 🎯 Best Practices

### ✅ DO's
- Schaue dir die Plots **vor** der Optimierung an
- Nutze sie für **Code-Reviews** und **Validierung**
- Archiviere sie für **Dokumentation** und **Reproduzierbarkeit**
- Vergleiche sie zwischen **verschiedenen Szenarien**

### ❌ DON'Ts
- Verlasse dich nicht **ausschließlich** auf Plots (prüfe auch Excel/JSON)
- Ignoriere **Warnungen** bei der Plot-Erstellung nicht
- Ändere **Modell-Code** basierend nur auf Plots (erst verstehen!)

---

## 📚 Weitere Informationen

- **Vollständige Dokumentation:** [`docs/MODEL_EXPORT.md`](docs/MODEL_EXPORT.md)
- **Code:** [`energis/io/model_inspector.py`](energis/io/model_inspector.py)
- **Beispiele:** Siehe `exports/` nach jedem Run

---

## 🆘 Fehlerbehebung

**Problem:** Plots werden nicht erstellt
```
[PLOT] Warning: Could not create overview plot: ...
```

**Lösung 1:** Matplotlib installieren
```bash
pip install matplotlib numpy
```

**Lösung 2:** Prüfe Log-Meldungen für spezifische Fehler

---

**Problem:** Plots sind leer oder unvollständig

**Lösung:** Prüfe, ob Modell vollständig initialisiert ist
```python
# Modell muss gebaut sein
model = build_model(table, cfg, dt_h=1.0)

# Dann Export
export_model_structure(model, output_dir)
```

---

**Problem:** Schriftarten/Style-Warnungen

**Lösung:** Ignorieren (funktionale Plots werden trotzdem erstellt)
```
Warning: seaborn-v0_8-darkgrid not found
```
Dies hat keinen Einfluss auf die Funktionalität.

---

## 💬 Feedback

Welche zusätzlichen Visualisierungen wären hilfreich? Öffne ein Issue auf GitHub!

Mögliche zukünftige Plots:
- 📊 Sparsity Pattern der Constraint-Matrix
- 🔄 Dependency Graph zwischen Constraints
- 📈 COP-Zeitreihen für Wärmepumpen
- 🌡️ Temperatur-Profile
- ⚡ Lastprofile visualisiert

---

🎉 **Viel Erfolg mit den neuen Visualisierungen!**
