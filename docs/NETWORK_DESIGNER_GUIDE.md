# Network Designer Guide

## 🗺️ Übersicht

Der **Thermal Network Designer** ist ein interaktives Dashboard mit Koordinatensystem zur visuellen Gestaltung thermischer Netzwerke. Er ermöglicht:

- ✅ **Drag-and-Drop** Komponenten-Platzierung
- ✅ **Visuelle Verbindungen** zwischen Komponenten
- ✅ **Live-Validierung** während der Konfiguration
- ✅ **Direkter YAML-Export** ohne Excel-Schritt
- ✅ **Simulation** direkt aus dem Dashboard
- ✅ **Ergebnis-Visualisierung** mit Energie-Flüssen

---

## 🚀 Quick Start

### Installation

```bash
# Plotly für interaktive Visualisierung
pip install plotly

# Panel für Dashboard
pip install panel

# Framework installieren
pip install -e .
```

### Dashboard starten

```bash
python start_network_designer.py
```

Öffnet Browser automatisch unter: **http://localhost:5006**

---

## 📋 Benutzeroberfläche

### Werkzeug-Palette

```
[👆 Auswählen] [🔥 Wärmepumpe] [⚡ Kessel] [🔋 Speicher] [🏠 Verbraucher] [─ Verbinden] [🗑️ Löschen]
```

#### Werkzeuge:

1. **👆 Auswählen** - Komponenten anklicken zum Bearbeiten
2. **🔥 Wärmepumpe** - Wärmepumpe platzieren
3. **⚡ Kessel** - Kessel platzieren
4. **🔋 Speicher** - Thermischer Speicher platzieren
5. **🏠 Verbraucher** - Verbraucher platzieren
6. **─ Verbinden** - Zwei Komponenten verbinden (2 Klicks)
7. **🗑️ Löschen** - Komponente löschen

### Koordinatensystem

```
┌─────────────────────────────────────────────────┐
│  Thermal Network Designer                       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Y (m)                                          │
│  800│                                           │
│     │    WP1 ●───────● Speicher                │
│  600│          │                                │
│     │          │                                │
│  400│    WP2 ●─┴───● Verbraucher1             │
│     │              │                            │
│  200│              ● Verbraucher2              │
│     │                                           │
│    0└─────────────────────────────────────────  │
│     0    200   400   600   800   1000    X (m) │
└─────────────────────────────────────────────────┘
```

### Eigenschaften-Panel

Rechts neben dem Canvas:

```
### 🔥 WP1

**Typ:** Wärmepumpe
**Position:** (150, 300)

Status:
○ Bestand  ● Investition

**Eigenschaften:**
Leistung (MW):    [10.0  ]
COP:              [3.5   ]

---

✅ **Validierung:** OK

---

[🗑️ Komponente löschen]
```

---

## 🎨 Workflow: Netzwerk erstellen

### Schritt 1: Komponenten platzieren

1. Werkzeug auswählen (z.B. **🔥 Wärmepumpe**)
2. Auf Canvas klicken → Komponente wird platziert
3. Wiederholen für alle Komponenten

**Tipp:** Koordinaten können später im Eigenschaften-Panel angepasst werden

### Schritt 2: Komponenten verbinden

1. **─ Verbinden** Werkzeug wählen
2. Erste Komponente anklicken
3. Zweite Komponente anklicken
4. Rohrleitung wird automatisch gezeichnet

**Tipp:** Verbindungen sind gerichtet (von → nach)

### Schritt 3: Eigenschaften konfigurieren

1. **👆 Auswählen** Werkzeug aktivieren
2. Komponente anklicken
3. Rechts im Panel bearbeiten:
   - **Status:** Bestand oder Investition
   - **Leistung:** Kapazität in MW
   - **COP/Wirkungsgrad:** Komponenten-Parameter

**Live-Validierung:** Fehler werden sofort angezeigt!

### Schritt 4: Validieren

- Automatische Validierung bei jeder Änderung
- Fehler werden rot im Canvas markiert
- Isolierte Komponenten werden erkannt

### Schritt 5: Exportieren oder Simulieren

**Option A: YAML exportieren**

```bash
[💾 YAML exportieren]
```

Erstellt: `exports/network_designer_export.yaml`

**Option B: Direkt simulieren**

```bash
[▶ Simulation starten]
```

- Validiert Netzwerk
- Erstellt temporäre Konfiguration
- Führt Optimierung aus
- Zeigt Ergebnisse an

---

## 📊 Ergebnis-Visualisierung

Nach erfolgreicher Simulation werden folgende Tabs angezeigt:

### 📊 Übersicht

- **KPI-Karten:** Gesamtkosten, Wärmebedarf, Spitzenlast
- **Kosten-Pie-Chart:** Verteilung nach Kategorien

### 🗺️ Netzwerk-Flows

- Energie-Flüsse als Pfeile im Netzwerk
- Pfeildicke = Flussstärke
- Time-Slider für Animation

### 📈 Zeitreihen

- **Wärmeerzeugung:** Gestapelt nach Komponenten
- **Wärmebedarf:** Nachfrage-Kurve
- **Speicher-SOC:** Füllstand über Zeit

### 💰 Kosten

- **Kosten-Tabelle:** Detaillierte Aufschlüsselung
- **CAPEX vs OPEX:** Investitions- vs. Betriebskosten
- **Komponenten-Kosten:** Breakdown nach Komponente

### 🔋 Komponenten-Auslastung

- **Auslastungsgrad:** % der Nennleistung
- **Volllaststunden:** Betriebsstunden pro Komponente

---

## 🔧 Beispiel-Workflow

### Beispiel: Brownfield-Ausbau

**Szenario:** Bestehendes Kessel-System wird mit Wärmepumpe und Speicher erweitert

#### Schritt-für-Schritt:

1. **Bestandskessel platzieren**
   - Werkzeug: **⚡ Kessel**
   - Position: (100, 300)
   - Status: **Bestand**
   - Leistung: 15 MW

2. **Neue Wärmepumpe platzieren**
   - Werkzeug: **🔥 Wärmepumpe**
   - Position: (100, 500)
   - Status: **Investition**
   - Leistung: wird optimiert

3. **Neuen Speicher platzieren**
   - Werkzeug: **🔋 Speicher**
   - Position: (400, 400)
   - Status: **Investition**
   - Kapazität: wird optimiert

4. **Verbraucher platzieren**
   - Werkzeug: **🏠 Verbraucher**
   - Position: (700, 400)

5. **Verbindungen erstellen**
   - Kessel → Speicher
   - Wärmepumpe → Speicher
   - Speicher → Verbraucher

6. **Simulation starten**
   ```
   [▶ Simulation starten]
   ```

7. **Ergebnisse analysieren**
   - Optimale WP-Größe
   - Optimale Speicher-Kapazität
   - Energie-Flüsse visualisiert
   - Kosten-Breakdown

---

## 💾 YAML-Export Format

```yaml
scenario:
  name: network_designer_scenario
  description: Created with Network Designer

  network:
    components:
      - id: HEA_a1b2c3d4
        type: heat_pump
        x: 100
        y: 500
        status: investment
        properties:
          cop: 3.5
          capacity_mw: 10.0

      - id: BOI_e5f6g7h8
        type: boiler
        x: 100
        y: 300
        status: existing
        properties:
          efficiency: 0.95
          capacity_mw: 15.0

      - id: STO_i9j0k1l2
        type: storage
        x: 400
        y: 400
        status: investment
        properties:
          capacity_mwh: 50.0
          efficiency: 0.98

    connections:
      - id: CONN_m3n4o5p6
        from: HEA_a1b2c3d4
        to: STO_i9j0k1l2
        type: pipe

      - id: CONN_q7r8s9t0
        from: BOI_e5f6g7h8
        to: STO_i9j0k1l2
        type: pipe

  system:
    heat_pumps:
      - id: HEA_a1b2c3d4
        existing: false
        cop: 3.5
        capacity_mw: 10.0

    boilers:
      - id: BOI_e5f6g7h8
        existing: true
        efficiency: 0.95
        capacity_mw: 15.0

    storage:
      - id: STO_i9j0k1l2
        existing: false
        capacity_mwh: 50.0
        efficiency: 0.98

    consumers:
      - id: CON_u1v2w3x4
        demand_mw: 25.0
```

---

## 🔌 Integration mit bestehendem Workflow

### Pyomo-Integration

Koordinaten werden in der YAML-Konfiguration gespeichert und können von Pyomo-Constraints genutzt werden:

```python
# In custom Pyomo constraints:
def distance_constraint(model, comp1, comp2):
    """Beispiel: Berücksichtige Distanzen für Wärmeverluste"""
    x1 = config['network']['components'][comp1]['x']
    y1 = config['network']['components'][comp1]['y']
    x2 = config['network']['components'][comp2]['x']
    y2 = config['network']['components'][comp2]['y']

    distance = ((x2-x1)**2 + (y2-y1)**2)**0.5

    # Wärmeverlust proportional zu Distanz
    heat_loss = distance * 0.01  # 1% pro 100m
    return model.heat_flow[comp1, comp2] * (1 - heat_loss)
```

### Runner-Integration

Das Dashboard ruft direkt `run_workflow()` auf:

```python
from energis.run.rolling_horizon import run_workflow

# Network Designer exportiert Config
config_path = 'temp_config.yaml'

# Runner führt Optimierung aus
result = run_workflow([config_path])

# Ergebnisse werden visualisiert
viewer.display_results(result)
```

---

## 🎯 Vorteile gegenüber Excel

| Feature | Excel-Workflow | Network Designer |
|---------|----------------|------------------|
| **Benutzerfreundlichkeit** | 6 Sheets ausfüllen | Visuelles Drag-and-Drop |
| **Validierung** | Nach Export | Live während Eingabe |
| **Fehlersuche** | Log durchsuchen | Rot markiert im Canvas |
| **Koordinaten** | Manuelle Eingabe | Visuell platzieren |
| **Verbindungen** | IDs tippen | Klick-and-Connect |
| **Export** | Excel → Parser → YAML | Direkt YAML |
| **Simulation** | Manueller Aufruf | 1-Klick im Dashboard |
| **Ergebnisse** | Separate Tools | Integrierte Visualisierung |
| **Zeitaufwand** | 30-60 min | 5-10 min |

---

## 🚀 Zukünftige Erweiterungen

### Phase 1 (Aktuell)
- ✅ Basis-Koordinatensystem
- ✅ Komponenten-Platzierung
- ✅ Live-Validierung
- ✅ YAML Export
- ✅ Runner-Integration
- ✅ Ergebnis-Visualisierung

### Phase 2 (Geplant)
- ⏳ Drag-to-Move (Komponenten verschieben)
- ⏳ Auto-Layout (automatische Anordnung)
- ⏳ Snap-to-Grid (Raster-Ausrichtung)
- ⏳ Template-Bibliothek (vordefinierte Netzwerke)
- ⏳ Import aus YAML (bestehende Configs laden)

### Phase 3 (Vision)
- ⏳ Animierte Energie-Flüsse
- ⏳ 3D-Visualisierung
- ⏳ GIS-Integration (echte Karten)
- ⏳ Multi-User Collaboration
- ⏳ Versionierung & History

---

## 📚 API-Referenz

### Komponenten-Typen

```python
COMPONENT_TYPES = {
    'heat_pump': 🔥 Wärmepumpe,
    'boiler': ⚡ Kessel,
    'storage': 🔋 Speicher,
    'consumer': 🏠 Verbraucher,
    'node': ⊕ Knoten (Verbindungspunkt),
}
```

### Status-Optionen

```python
STATUS = {
    'existing': Bestand (grün),
    'investment': Investition (blau),
    'pending': Nicht konfiguriert (gelb),
    'error': Fehler (rot),
}
```

### Programmatische Nutzung

```python
from energis.io.network_designer import create_network_designer

# Dashboard erstellen
designer = create_network_designer()

# Komponenten hinzufügen
designer.add_component(x=100, y=200, comp_type='heat_pump')
designer.add_component(x=300, y=200, comp_type='storage')

# Verbinden
comp1_id = designer.components[0].component_id
comp2_id = designer.components[1].component_id
designer.add_connection(comp1_id, comp2_id)

# Validieren
valid, errors = designer.validate_network()

# Exportieren
designer.export_to_yaml('my_network.yaml')

# Dashboard anzeigen
dashboard = designer.create_dashboard()
dashboard.show()
```

---

## ❓ Troubleshooting

### Problem: Canvas bleibt leer

**Lösung:**
```bash
# Prüfe Plotly-Installation
pip install --upgrade plotly

# Browser-Cache leeren
Strg + F5
```

### Problem: Komponenten nicht klickbar

**Lösung:**
- Werkzeug **👆 Auswählen** aktivieren
- Browser-Zoom auf 100% setzen

### Problem: Simulation schlägt fehl

**Lösung:**
1. Validierung prüfen (siehe Validation Panel)
2. Alle Komponenten konfiguriert?
3. Mindestens eine Verbindung vorhanden?
4. Zeitreihen-Daten verfügbar?

### Problem: Ergebnisse werden nicht angezeigt

**Lösung:**
- Prüfe Console-Output
- Results Viewer erfordert erfolgreiche Simulation
- Pandas und Plotly installiert?

---

## 📞 Support

- **GitHub Issues:** https://github.com/LukasRuess98/Planing-Framework-for-Heat/issues
- **Dokumentation:** `docs/`
- **Beispiele:** `examples/`

---

## 🎓 Weitere Ressourcen

- [SIMPLIFICATION_PROPOSAL.md](../SIMPLIFICATION_PROPOSAL.md) - Konzept-Dokumentation
- [FRAMEWORK_ARCHITECTURE_ANALYSIS.md](../FRAMEWORK_ARCHITECTURE_ANALYSIS.md) - Architektur-Übersicht
- [Excel Import Guide](./excel_import_feature.md) - Alternative: Excel-basierter Workflow

---

**Viel Erfolg beim Erstellen Ihrer thermischen Netzwerke! 🚀**
