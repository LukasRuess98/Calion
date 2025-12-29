# Config-Struktur Analyse & Verbesserungsvorschläge

## 📊 IST-ZUSTAND

### Aktuelle Ordnerstruktur
```
configs/
├── base.yaml                    (40 Zeilen)   - Solver, Grid, Costs defaults
├── tech_catalog.yaml            (75 Zeilen)   - Fuel/Tech parameters
├── stadtbach.yaml              (245 Zeilen)   - MONOLITH: Alles in einer Datei
├── networks/
│   └── brownfield.yaml         (236 Zeilen)   - Network topology
├── scenarios/
│   ├── one_week.yaml           (78 Zeilen)    - Test scenario
│   ├── high_hp_year.yaml       (79 Zeilen)    - High HP scenario
│   └── full_year.yaml          (92 Zeilen)    - Full year scenario
└── systems/
    ├── baseline.yaml           (129 Zeilen)   - Baseline system config
    └── high_hp.yaml            (122 Zeilen)   - High HP system config
```

### ❌ PROBLEME

#### 1. **Massive Redundanz**
- WRG column mapping wird in JEDER Datei dupliziert:
  - `stadtbach.yaml`: Zeilen 35-42
  - `scenarios/one_week.yaml`: Zeilen 39-46
  - `scenarios/full_year.yaml`: Zeilen 39-46
- Solver settings werden mehrfach definiert
- Grid limits werden dupliziert
- **Problem**: Änderungen müssen an 4+ Stellen gemacht werden

#### 2. **Inkonsistente Verwendung**
- `stadtbach.yaml` ist ein **Monolith** (245 Zeilen, alles drin)
- `scenarios/` und `systems/` werden **NIE benutzt**
- User muss raten: "Welche Datei soll ich editieren?"
- **Problem**: Verwirrung über "intended" vs. "actual" Struktur

#### 3. **Falsche Granularität**
- `baseline.yaml` hat veraltete column names:
  ```yaml
  wrg_capacity_column: WRG1_Q_cap  # FALSCH! Existiert nicht
  ```
- **Problem**: Configs in `systems/` sind veraltet und kaputt

#### 4. **Fehlende Trennung von Concerns**
Aktuell vermischt in `stadtbach.yaml`:
- Site-spezifische Daten (Excel file, columns) - ÄNDERN SICH NIE
- Scenario-Parameter (Zeitraum, workflow) - ÄNDERN SICH OFT
- System-Konfiguration (Generators, HP, Storage) - ÄNDERN SICH MANCHMAL
- Tech-Parameter (Effizienzen, COPs) - ÄNDERN SICH SELTEN

#### 5. **Kein Import-Mechanismus**
- YAML hat kein `include:` oder `extends:`
- Code unterstützt Merging, aber User muss wissen:
  ```bash
  python -m energis.run configs/base.yaml configs/tech_catalog.yaml configs/stadtbach.yaml
  ```
- **Problem**: Nicht offensichtlich, nicht dokumentiert

---

## ✅ LÖSUNGSANSÄTZE

### Option 1: **Modular mit explizitem Merging** (EMPFOHLEN)

#### Vorteile
- ✅ Maximale Flexibilität
- ✅ DRY (Don't Repeat Yourself)
- ✅ Klare Trennung von Concerns
- ✅ Nutzt bereits vorhandenes Merging
- ✅ Einfach testbar

#### Neue Struktur
```
configs/
├── 00_base/
│   ├── solver.yaml              # Solver defaults (Gurobi settings)
│   ├── costs.yaml               # Cost parameters (CO2, dump, grid)
│   └── grid.yaml                # Grid limits and fees
│
├── 01_tech/
│   ├── fuels.yaml               # Fuel prices and emissions
│   ├── generators.yaml          # Generator efficiencies
│   ├── heat_pumps.yaml          # HP defaults (COP, investment)
│   └── storage.yaml             # Storage defaults (investment)
│
├── 02_site/
│   └── stadtbach/
│       ├── data_source.yaml     # Excel file + column mapping (READ-ONLY)
│       └── assets.yaml          # Installed assets (HKW, GTOST, etc.)
│
├── 03_systems/
│   ├── baseline.yaml            # Baseline: Current assets only
│   ├── with_storage.yaml        # + Thermal storage
│   ├── with_hp.yaml             # + Heat pumps
│   └── full.yaml                # All technologies
│
├── 04_scenarios/
│   ├── test_1week.yaml          # Quick test (1 week)
│   ├── summer_2023.yaml         # Summer analysis
│   ├── winter_2023.yaml         # Winter peak analysis
│   └── full_2023.yaml           # Full year optimization
│
├── 05_networks/
│   └── brownfield.yaml          # Network topology (unchanged)
│
└── presets/                      # Pre-composed configs
    ├── quick_test.yaml          # For development
    ├── baseline_full_year.yaml  # Production run
    └── hp_optimization.yaml     # HP investment study
```

#### Verwendung

**Minimale Ausführung:**
```bash
# All defaults + specific scenario
python -m energis.run \
  configs/00_base/solver.yaml \
  configs/00_base/costs.yaml \
  configs/01_tech/fuels.yaml \
  configs/02_site/stadtbach/data_source.yaml \
  configs/03_systems/baseline.yaml \
  configs/04_scenarios/test_1week.yaml
```

**Mit Preset (einfacher):**
```bash
python -m energis.run configs/presets/quick_test.yaml
```

Wobei `quick_test.yaml` enthält:
```yaml
# Quick test preset - composes multiple configs
_includes:
  - ../00_base/solver.yaml
  - ../00_base/costs.yaml
  - ../01_tech/fuels.yaml
  - ../02_site/stadtbach/data_source.yaml
  - ../03_systems/baseline.yaml
  - ../04_scenarios/test_1week.yaml

# Override specific settings for quick testing
run:
  solver_options:
    TimeLimit: 300  # Faster for testing
```

**ABER**: Requires implementing `_includes:` support!

---

### Option 2: **Flat mit Naming Convention** (EINFACHER)

#### Vorteile
- ✅ Keine Code-Änderungen nötig
- ✅ Funktioniert mit aktuellem Merging
- ✅ Einfach zu verstehen

#### Struktur
```
configs/
├── 00_defaults.yaml             # Solver, grid, costs
├── 01_tech.yaml                 # Fuels, generators, HP, storage
├── 02_stadtbach_data.yaml       # Site data (Excel + columns)
├── 03_stadtbach_assets.yaml     # Installed assets
├── 10_scenario_test.yaml        # Quick test scenario
├── 11_scenario_summer.yaml      # Summer scenario
├── 12_scenario_winter.yaml      # Winter scenario
├── 20_system_baseline.yaml      # System configs
├── 21_system_with_hp.yaml
├── 22_system_with_storage.yaml
└── networks/
    └── brownfield.yaml
```

#### Verwendung
```bash
# Order matters: later files override earlier
python -m energis.run \
  configs/00_defaults.yaml \
  configs/01_tech.yaml \
  configs/02_stadtbach_data.yaml \
  configs/03_stadtbach_assets.yaml \
  configs/20_system_baseline.yaml \
  configs/10_scenario_test.yaml
```

---

### Option 3: **Environment-basiert** (FÜR PRODUKTION)

#### Vorteile
- ✅ Klare Trennung dev/staging/prod
- ✅ Standard-Pattern aus DevOps
- ✅ Einfache CI/CD Integration

#### Struktur
```
configs/
├── common/
│   ├── tech.yaml
│   └── site.yaml
├── environments/
│   ├── dev.yaml              # Fast solver, short horizon
│   ├── staging.yaml          # Medium solver, 1 month
│   └── production.yaml       # Full solver, full year
└── scenarios/
    ├── baseline.yaml
    ├── hp_study.yaml
    └── storage_study.yaml
```

#### Verwendung
```bash
# Development
python -m energis.run \
  configs/common/tech.yaml \
  configs/environments/dev.yaml \
  configs/scenarios/baseline.yaml

# Production
python -m energis.run \
  configs/common/tech.yaml \
  configs/environments/production.yaml \
  configs/scenarios/hp_study.yaml
```

---

## 🎯 KONKRETE EMPFEHLUNG

### Phase 1: **Immediate Cleanup** (1 Tag)

1. **Konsolidiere site-spezifische Daten**
   ```bash
   configs/
   ├── site_stadtbach.yaml     # Excel file + column mappings (SINGLE SOURCE OF TRUTH)
   ├── tech_defaults.yaml      # Merge base.yaml + tech_catalog.yaml
   └── stadtbach_full.yaml     # Current monolith (DEPRECATED)
   ```

2. **Fix column mappings überall**
   - Eine zentrale Datei: `site_stadtbach.yaml`
   - Mit korrektem WRG1 mapping: `"WRG1_ T °C"`

3. **README.md schreiben**
   ```markdown
   # Quick Start

   ## Simple (single file):
   python -m energis.run configs/stadtbach_full.yaml

   ## Modular (recommended):
   python -m energis.run \
     configs/tech_defaults.yaml \
     configs/site_stadtbach.yaml \
     configs/scenarios/test_1week.yaml
   ```

### Phase 2: **Modular Refactoring** (2-3 Tage)

1. Implementiere **Option 1** (Modular)
2. Erstelle Presets für häufige Use-Cases
3. Migriere bestehende Workflows
4. Deprecate `stadtbach.yaml`

### Phase 3: **Advanced Features** (Optional)

1. **Config Inheritance** mit `_extends:`
   ```yaml
   # configs/scenarios/summer_2023.yaml
   _extends: base_scenario.yaml
   scenario:
     horizon:
       start: "2023-06-01"
       end: "2023-08-31"
   ```

2. **Config Validation Schema**
   - JSON Schema für jede Config-Ebene
   - Frühe Fehlererkennung
   - IDE Autocomplete

3. **Config Templates** mit Variables
   ```yaml
   # Use ${{ env.YEAR }} in configs
   scenario:
     horizon:
       start: "${{ env.YEAR }}-01-01"
   ```

---

## 📋 MIGRATION CHECKLIST

### Sofort (heute):
- [ ] Erstelle `configs/site_stadtbach.yaml` mit korrekten column mappings
- [ ] Teste: `python -m energis.run configs/tech_catalog.yaml configs/site_stadtbach.yaml configs/scenarios/one_week.yaml`
- [ ] Update `scenarios/*.yaml` um column mappings zu entfernen (inherit from site)

### Diese Woche:
- [ ] Entscheide: Option 1 (modular) oder Option 2 (flat)?
- [ ] Erstelle neue Ordnerstruktur
- [ ] Migriere bestehende Configs
- [ ] Schreibe Tests für Config-Merging
- [ ] Update Dokumentation

### Nächster Sprint:
- [ ] Deprecate `stadtbach.yaml` (add warning)
- [ ] Implementiere Config Inheritance (optional)
- [ ] Add CI checks für Config-Validierung

---

## 🔍 BEISPIEL: Vorher/Nachher

### VORHER (stadtbach.yaml - 245 Zeilen)
```yaml
# Alles in einer Datei
scenario: {...}
site: {...}
run: {...}
grid: {...}
fuels: {...}
generators: {...}
system:
  heat_pumps: [...] # 80 Zeilen
  storage: {...}
  generators: {...}
thermal_network: {...}
```

### NACHHER (Modular - 6 kleine Dateien)

**Ausführung:**
```bash
python -m energis.run configs/presets/stadtbach_rh_2023.yaml
```

**configs/presets/stadtbach_rh_2023.yaml (15 Zeilen):**
```yaml
_merge:
  - ../tech_defaults.yaml
  - ../site_stadtbach.yaml
  - ../systems/full.yaml
  - ../scenarios/rh_2023_q1.yaml

# Override nur was sich ändert
scenario:
  fix_design: true
  horizon:
    enforce: true
```

**Vorteile:**
- Änderung von Solver settings: Nur `tech_defaults.yaml` editieren
- Neues Szenario: Nur neue Datei in `scenarios/`
- Test mit anderen WRG columns: Nur `site_stadtbach.yaml`
- **Kein Copy-Paste, keine Redundanz**

---

## 📌 FAZIT

### Was ist das Problem?
- ❌ Redundanz durch Copy-Paste (WRG columns 4x dupliziert)
- ❌ Verwirrung über welche Datei zu editieren
- ❌ Monolith `stadtbach.yaml` schwer wartbar
- ❌ `scenarios/` und `systems/` existieren aber werden ignoriert

### Was sollte gemacht werden?
1. **Kurzfristig**: Konsolidiere site data → `site_stadtbach.yaml`
2. **Mittelfristig**: Migriere zu **Option 1** (Modular mit Presets)
3. **Langfristig**: Add Config Inheritance + Validation

### Warum ist das besser?
- ✅ **DRY**: Änderungen nur an EINER Stelle
- ✅ **Klarheit**: Jede Datei hat einen klaren Zweck
- ✅ **Flexibilität**: Mix & Match für verschiedene Szenarien
- ✅ **Testbarkeit**: Kleine Configs einfach zu testen
- ✅ **Wartbarkeit**: Neue Szenarien in 10 Zeilen statt 245
