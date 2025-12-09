# Integration Guide - Stadtbach & Phase 4 Thermal Network

## 🎯 Überblick

Dieses Dokument erklärt:
1. Wie du das aktuelle Stadtbach-System nutzt
2. Wie das Modell intern funktioniert
3. Wie Phase 4 (Thermal Network) später integriert wird

---

## 📂 Aktuelle Struktur

```
configs/
├── base.yaml                              # Globale Defaults (Solver, Kosten, Grid)
├── systems/
│   ├── stadtbach.system.yaml              # Original Stadtbach (einfach)
│   └── stadtbach_extended.system.yaml     # Extended mit Kommentaren
└── scenarios/
    ├── rolling_horizon_only.scenario.yaml # Standard-Workflow
    ├── test_1week.scenario.yaml           # Quick Test
    └── mpc_perfect_noise.scenario.yaml    # MPC-Workflow
```

---

## 🚀 Stadtbach ausführen

### **Schnellstart (1 Woche Test)**

```bash
python -m energis.run \
    configs/base.yaml \
    configs/systems/stadtbach.system.yaml \
    configs/scenarios/test_1week.scenario.yaml
```

**Was passiert:**
1. Lädt alle 3 YAML-Dateien
2. Merged sie zusammen (base + system + scenario)
3. Erstellt Pyomo-Modell mit allen Komponenten
4. Optimiert mit Gurobi
5. Exportiert Ergebnisse nach `results/`

### **Volles Jahr optimieren**

```bash
python -m energis.run \
    configs/base.yaml \
    configs/systems/stadtbach.system.yaml \
    configs/scenarios/rolling_horizon_only.scenario.yaml
```

### **Mit Extended Version (stratified storage)**

```bash
python -m energis.run \
    configs/base.yaml \
    configs/systems/stadtbach_extended.system.yaml \
    configs/scenarios/test_1week.scenario.yaml
```

---

## 🔧 Wie das Modell intern funktioniert

### **1. Config-Laden & Merging**

```python
# energis/run/rolling_horizon.py
def run_workflow(config_paths):
    # Lädt alle YAMLs
    config = merge_configs(config_paths)

    # Jetzt hat config alles:
    # - config['run']         # von base.yaml
    # - config['costs']       # von base.yaml
    # - config['system']      # von stadtbach.system.yaml
    # - config['scenario']    # von scenario.yaml
```

### **2. System Builder erstellt Pyomo-Modell**

```python
# energis/models/system_builder.py (vereinfacht)

def build_system(model, config, timeseries):
    """Erstellt alle Komponenten basierend auf Config."""

    # 1. Heat Pumps erstellen
    for hp_cfg in config['system']['heat_pumps']:
        hp = HeatPumpBlock(
            name=hp_cfg['id'],
            cop_series=cop_series,  # Aus Zeitreihen berechnet
            capacity_min_mw=...,
            capacity_max_mw=...,
            investable=True
        )
        hp.attach(model, time_set, config, buses)

    # 2. Storage erstellen
    storage_type = config['system']['storage'].get('type', 'simple')
    if storage_type == 'stratified':
        storage = StratifiedStorageBlock(...)
    else:
        storage = StorageBlock(...)
    storage.attach(model, time_set, config, buses)

    # 3. Generators/Kessel erstellen
    for gen_id, gen_cfg in config['system']['generators'].items():
        gen = ThermalGeneratorBlock(
            name=gen_id,
            capacity_mw=gen_cfg['cap_th_mw'],
            fuel=gen_cfg.get('fuel', 'gas')
        )
        gen.attach(model, time_set, config, buses)

    # 4. Bus-Bilanzen erstellen
    # Alle Komponenten haben sich am Bus registriert
    # Jetzt: Summe(Inputs) = Summe(Outputs) + Demand
    create_bus_balances(model, buses)
```

### **3. Komponenten-Architektur**

Alle Komponenten implementieren das **Component Protocol**:

```python
class Component(Protocol):
    def attach(self, model, time_set, config, buses):
        """Fügt Variablen und Constraints zum Modell hinzu."""

    def get_results(self, model, time_set):
        """Extrahiert Ergebnisse nach Optimierung."""

    def validate_config(self, config):
        """Validiert Konfiguration."""
```

**Beispiel: Heat Pump Block**

```python
# energis/models/blocks/heat_pump.py

@register_component("heat_pump", category="converter")
class HeatPumpBlock(BaseComponent):
    def attach(self, model, time_set, config, buses):
        # Erstelle Variablen
        Q_th_out = pyo.Var(time_set, domain=NonNegativeReals)  # Wärme raus
        P_el_in = pyo.Expression(...)  # Strom rein (Q_th / COP)

        # Erstelle Constraints
        # Capacity constraint: Q_th <= capacity * on_off
        # Min load constraint: Q_th >= min_load * capacity * on_off

        # Registriere am Bus
        buses['heat'].add_output(Q_th_out)
        buses['electricity'].add_input(P_el_in)

        return {'Q_th_out': Q_th_out, 'P_el_in': P_el_in}
```

---

## 🔌 Integration - Wo ist was?

### **Module-Übersicht**

```
energis/
├── run/
│   ├── rolling_horizon.py      # Hauptworkflow, lädt Configs, ruft Solver
│   └── __main__.py             # CLI-Entry: python -m energis.run
│
├── models/
│   ├── system_builder.py       # ⭐ HIER wird alles zusammengebaut
│   ├── registry.py             # Component Registry (Plugin-System)
│   └── blocks/                 # Alle Komponenten-Implementierungen
│       ├── heat_pump.py        # HeatPumpBlock
│       ├── storage.py          # StorageBlock (simple)
│       ├── stratified_storage.py  # StratifiedStorageBlock
│       ├── thermal_gen.py      # ThermalGeneratorBlock (Kessel)
│       └── p2h.py              # P2HBlock (Power-to-Heat)
│
├── io/
│   ├── network_designer.py         # Dashboard (optional, zu komplex)
│   └── network_templates.py        # Templates (optional)
│
└── utils/
    ├── timeseries.py           # Zeitreihen-Handling
    └── config_utils.py         # Config-Merging
```

### **Wo wird die YAML verarbeitet?**

**system_builder.py Zeilen 300-700:**

```python
# Zeile ~400: Heat Pumps
if 'heat_pumps' in syscfg:
    for hp_cfg in syscfg['heat_pumps']:
        # Erstelle HeatPumpBlock mit Config

# Zeile ~480: Storage
if syscfg.get('storage', {}).get('enabled'):
    storage_type = syscfg['storage'].get('type', 'simple')
    if storage_type == 'stratified':
        block = StratifiedStorageBlock(...)
    else:
        block = StorageBlock(...)

# Zeile ~660: Generators
for gen_id, gen_cfg in syscfg.get('generators', {}).items():
    if gen_cfg.get('enabled', True):
        block = ThermalGeneratorBlock(...)
```

---

## 🛣️ Phase 4: Thermal Network Integration (Roadmap)

### **Status: NICHT implementiert** (nur Planung existiert)

**Warum nicht?**
- Komplex: Hydraulische Modellierung, Pipe-Flows, Druck-Verluste
- Risiko: 6-8 Wochen Entwicklung
- Prototyping nötig

### **Was existiert bereits:**

1. **Dokumentation**: `docs/thermal_network_integration.md`
2. **Datenstrukturen**: Ideen in YAML-Kommentaren
3. **Component Protocol**: Bereits modular, neue Komponenten einfach

### **Wie würde Phase 4 integriert?**

#### **Schritt 1: Neue Komponenten erstellen**

```python
# energis/models/blocks/pipe.py

@register_component("pipe", category="network")
class PipeBlock(BaseComponent):
    """Rohr mit Wärmeverlusten und Druckverlust."""

    def __init__(self, name, length_m, diameter_mm, ...):
        self.length_m = length_m
        self.diameter_mm = diameter_mm

    def attach(self, model, time_set, config, buses):
        # Variablen: mass_flow, T_supply, T_return, pressure_drop
        # Constraints: Wärmeverlust = f(length, insulation, T_diff)
        #              Druckverlust = f(mass_flow, diameter, length)
```

```python
# energis/models/blocks/node.py

@register_component("node", category="network")
class NodeBlock(BaseComponent):
    """Netzknoten mit Druck und Temperatur."""

    def attach(self, model, time_set, config, buses):
        # Variablen: pressure, temperature, mass_balance
        # Constraints: Summe(inflows) = Summe(outflows)
```

#### **Schritt 2: YAML erweitern**

```yaml
# stadtbach_with_network.system.yaml

system:
  # ... heat_pumps, storage, generators wie bisher ...

  # NEU: Thermal Network
  thermal_network:
    enabled: true

    nodes:
      - id: N1_HKW
        type: producer
        components: [hkw, HP1, HP2]  # Welche Komponenten sind hier?
        x: 0
        y: 0
        pressure_bar: 10.0

      - id: N2_Storage
        type: storage
        components: [TES]
        x: 500
        y: 0
        pressure_bar: 9.5

      - id: N3_Consumer
        type: consumer
        x: 1000
        y: 0
        pressure_bar: 9.0

    pipes:
      - id: P1_Supply
        from: N1_HKW
        to: N2_Storage
        length_m: 500
        diameter_mm: 300
        insulation_mm: 50
        U_value: 0.15  # W/(m·K)

      - id: P2_Supply
        from: N2_Storage
        to: N3_Consumer
        length_m: 500
        diameter_mm: 250
        insulation_mm: 50

      - id: P2_Return
        from: N3_Consumer
        to: N2_Storage
        length_m: 500
        diameter_mm: 250
        insulation_mm: 50
```

#### **Schritt 3: System Builder erweitern**

```python
# In system_builder.py (NEU hinzufügen)

def build_thermal_network(model, config, time_set, buses):
    """Erstellt Thermal Network mit Pipes und Nodes."""

    network_cfg = config['system'].get('thermal_network', {})
    if not network_cfg.get('enabled', False):
        return  # Kein Netzwerk

    # 1. Nodes erstellen
    nodes = {}
    for node_cfg in network_cfg['nodes']:
        node = NodeBlock(name=node_cfg['id'], ...)
        node.attach(model, time_set, config, buses)
        nodes[node_cfg['id']] = node

    # 2. Pipes erstellen
    for pipe_cfg in network_cfg['pipes']:
        pipe = PipeBlock(
            name=pipe_cfg['id'],
            from_node=nodes[pipe_cfg['from']],
            to_node=nodes[pipe_cfg['to']],
            length_m=pipe_cfg['length_m'],
            diameter_mm=pipe_cfg['diameter_mm']
        )
        pipe.attach(model, time_set, config, buses)
```

#### **Schritt 4: Testing & Validation**

```bash
# Test mit kleinem Netzwerk
python -m energis.run \
    configs/base.yaml \
    configs/systems/stadtbach_with_network.system.yaml \
    configs/scenarios/test_1week.scenario.yaml
```

---

## 📊 Vergleich: Mit vs. Ohne Thermal Network

### **Ohne Thermal Network (AKTUELL)**

```
Komponenten:
  HP1 ──┐
  HP2 ──┼──> [Heat Bus] ──> Storage ──> [Heat Bus] ──> Demand
  HKW ──┤
  etc. ─┘

Annahmen:
  - Kein Wärmeverlust in Rohren
  - Kein Druckverlust
  - Unendlich schnelle Wärmeübertragung
  - Perfekte Mischung

Vorteile:
  ✅ Schnelle Optimierung
  ✅ Einfache Struktur
  ✅ Gut für Investitions-Studien

Nachteile:
  ❌ Keine räumliche Information
  ❌ Keine Netzwerk-Kosten
  ❌ Keine Hydraulik
```

### **Mit Thermal Network (PHASE 4)**

```
Komponenten:
  HP1 ──> N1 ──[Pipe P1]──> N2 ──[Pipe P2]──> N3 ──> Consumer
               (500m, DN300)     (500m, DN250)
  HKW ──> N1

  Storage @ N2

Modelliert:
  ✅ Wärmeverluste in Rohren (length × U-value × ΔT)
  ✅ Druckverluste (Darcy-Weisbach)
  ✅ Vorlauf-/Rücklauf-Temperaturen
  ✅ Netzwerk-Topologie
  ✅ Rohrdimensionierung

Komplexität:
  ⚠️ Mehr Variablen (+50%)
  ⚠️ Mehr Constraints (+100%)
  ⚠️ Nichtlinear (→ Linearisierung nötig)
  ⚠️ Längere Solver-Zeit

Anwendung:
  → Detaillierte Netzwerk-Planung
  → Rohr-Dimensionierung
  → Druck-/Temperatur-Analyse
```

---

## 🎯 Empfehlung: Schrittweise Vorgehen

### **Phase 1: Jetzt (Ohne Netzwerk)**

```bash
# 1. Stadtbach mit aktueller Config testen
python -m energis.run \
    configs/base.yaml \
    configs/systems/stadtbach.system.yaml \
    configs/scenarios/test_1week.scenario.yaml

# 2. Stratified Storage testen
# → stadtbach_extended.yaml bearbeiten: type: stratified

# 3. Investment-Optimierung
# → Verschiedene Kapazitäts-Bounds testen
```

**Fokus:**
- ✅ Investitions-Entscheidungen (welche Kapazitäten?)
- ✅ Betriebsoptimierung (wann welche Anlage?)
- ✅ Storage-Strategie
- ✅ Kosten-Analyse

### **Phase 2: Später (Mit Netzwerk)**

```bash
# Erst wenn Investment-Entscheidungen getroffen sind:
# 1. Netzwerk-Topologie definieren
# 2. Rohr-Parameter hinzufügen
# 3. Hydraulik-Modell implementieren
# 4. Re-optimieren mit Netzwerk-Kosten
```

**Fokus:**
- ✅ Rohr-Dimensionierung
- ✅ Druck-Verluste
- ✅ Wärme-Verluste
- ✅ Netzwerk-Kosten

---

## 📝 Nächste Schritte für dich

1. **Teste Stadtbach:**
   ```bash
   python -m energis.run configs/base.yaml configs/systems/stadtbach.system.yaml configs/scenarios/test_1week.scenario.yaml
   ```

2. **Schau dir Ergebnisse an:**
   ```bash
   ls results/  # Excel-Dateien mit Ergebnissen
   ```

3. **Passe Config an:**
   - Öffne `stadtbach_extended.system.yaml`
   - Ändere Kapazitäten, Investment-Bounds
   - Ändere `type: stratified` für besseres Storage-Modell

4. **Wenn du Netzwerk brauchst:**
   - Wir erstellen `stadtbach_with_network.system.yaml`
   - Implementieren Pipe/Node Blocks
   - Integrieren in system_builder.py

---

## 📞 Support

**Fragen? Probleme?**
- Config-Struktur unklar? → Siehe `configs/systems/baseline.system.yaml` als Referenz
- Fehler beim Ausführen? → Check `check_system.py` zuerst
- Phase 4 brauchst du wirklich? → Lass uns darüber reden, ob es nötig ist

**Dokumentation:**
- `docs/thermal_network_integration.md` - Detaillierte Phase 4 Planung
- `docs/STRATIFIED_STORAGE.md` - Storage-Modelle
- `TEST_PLAN.md` - Testing-Strategie
