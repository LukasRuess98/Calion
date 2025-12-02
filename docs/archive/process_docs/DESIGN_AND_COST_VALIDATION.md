# Validierung: Design-Übertragung und Kosten-Aggregation

**Status:** ⚠️ KRITISCHER FEHLER IN MPC GEFUNDEN
**Datum:** 2025-11-19
**Geprüfte Komponenten:** Design-Datenübertragung, Zielfunktion, Kosten-Aggregation

---

## 🎯 Überprüfungsziele

1. ✅ Werden die richtigen Design-Daten von PF zu RH/MPC übertragen?
2. ⚠️ Gehen in die Zielfunktion die richtigen Daten ein (keine doppelten Kosten)?
3. ⚠️ Wird CAPEX/OPEX korrekt behandelt bei PF→RH?

---

## ✅ 1. Design-Datenübertragung (KORREKT)

### 1.1 Design-Extraktion aus PF

**Funktion:** `_extract_design_data()` (rolling_horizon.py:908-929)

**Extrahierte Daten:**
```python
DesignData(
    heat_pumps: {
        "hp_id": {
            "capacity_mw": float,        # Thermische Kapazität MW
            "build_binary": float,       # Build-Entscheidung (0/1)
        }
    },
    storage: {
        "name": str,
        "capacity_mwh": float,           # Speicherkapazität MWh
        "power_mw": float,               # Ladeleistung MW
        "build_binary": float,           # Build-Entscheidung (0/1)
    }
)
```

**Quelle:** PF result → `summary` dictionary
- Heat Pumps: `summary["heat_pump_{id}"]["Thermal_capacity_MW"]`, `["Build_binary"]`
- Storage: `summary["storage_{name}"]["Capacity_MWh"]`, `["Power_limit_MW"]`, `["Build_binary"]`

**Bewertung:** ✅ **KORREKT**
- Alle relevanten Kapazitäten werden extrahiert
- Build-Entscheidungen werden korrekt übernommen
- Fallback auf "Build" wenn "Build_binary" nicht vorhanden

---

### 1.2 Design-Fixierung in RH/MPC

**Funktion:** `_apply_design_fix()` (rolling_horizon.py:1034-1071)

**Anwendung auf Heat Pumps:**
```python
# Für jede Heat Pump:
hp_cfg["investment"]["enabled"] = False                    # Keine neue Investition
hp_cfg["investment"]["capacity_min_mw"] = capacity         # Min = Max
hp_cfg["investment"]["capacity_max_mw"] = capacity         # = PF-Design
hp_cfg["max_th_mw"] = capacity                             # Thermische Kapazität
hp_cfg["min_th_mw"] = capacity                             # Fixiert
hp_cfg["enabled"] = False if build_binary < 0.5 else True  # Deaktivieren falls nicht gebaut
```

**Anwendung auf Storage:**
```python
storage_cfg["enabled"] = build_binary >= 0.5               # Nur aktiv wenn gebaut
storage_cfg["max_energy_mwh"] = capacity_mwh               # Energiekapazität
storage_cfg["max_power_mw"] = power_mw                     # Leistung
storage_cfg["investment"]["enabled"] = False               # Keine neue Investition
storage_cfg["investment"]["energy_capacity_min_mwh"] = capacity_mwh  # Min = Max
storage_cfg["investment"]["energy_capacity_max_mwh"] = capacity_mwh
storage_cfg["investment"]["power_capacity_min_mw"] = power_mw
storage_cfg["investment"]["power_capacity_max_mw"] = power_mw
```

**Bewertung:** ✅ **KORREKT**
- Investment wird deaktiviert (`enabled = False`)
- Kapazitäten werden auf PF-Werte fixiert (min = max)
- Build-Entscheidungen werden respektiert
- Nicht gebaute Komponenten werden deaktiviert

---

## ⚠️ 2. Kosten-Aggregation (FEHLER IN MPC!)

### 2.1 Investment vs. Operational Costs

**Definition der Investment-Kosten:**
```python
_INVESTMENT_KEYS = {
    "objective.Capex_cost_EUR",                    # Investitionskosten (amortisiert)
    "objective.Activation_cost_EUR",               # Aktivierungskosten
    "objective.Tie_breaker_cost_EUR",              # Tie-breaker Kosten
    "objective.Storage_installation_cost_EUR",     # Speicher-Installationskosten
}
```

**Operational Costs:** Alle anderen `objective.*` Kosten:
- `objective.Grid_energy_cost_EUR` - Strombezugskosten
- `objective.Grid_sell_revenue_EUR` - Stromverkaufserlöse
- `objective.Fuel_cost_EUR` - Brennstoffkosten
- `objective.Demand_charge_cost_EUR` - Leistungspreise
- etc.

---

### 2.2 Kosten-Aggregationsplan

**Funktion:** `_load_cost_plan()` (rolling_horizon.py:955-977)

**Logik:**
```python
# Standardverhalten:
if fix_design:
    include_investment = False      # Bei fixiertem Design: KEINE CAPEX in RH
else:
    include_investment = True       # Bei freiem Design: CAPEX in RH

# Zusätzliche Kontrolle:
amortise_once = True                # CAPEX nur einmal zählen (nicht in jedem Fenster!)
```

**Konfigurierbar über:**
```yaml
costs:
  include_investment_in_rh: false/true        # Override für include_investment
  amortise_investment_once_in_rh: true        # CAPEX nur 1x (Standard: true)
  include_tie_breaker_in_rh: false/true
  include_installation_in_rh: false/true
  include_activation_in_rh: false/true
```

**Bewertung:** ✅ **LOGIK KORREKT**
- Bei `PF→RH` (fix_design=true): CAPEX wird NICHT in RH gezählt (kommt von PF!)
- Bei `RH-only` (fix_design=false): CAPEX wird nur 1x gezählt (nicht in jedem Fenster)
- Konfigurierbar für Sonderfälle

---

### 2.3 Kosten-Akkumulation in RH

**Funktion:** `_accumulate_costs()` (rolling_horizon.py:787-825)

**Ablauf:**
```python
for key, value in window_costs.items():
    # 1. Überspringe spezielle Keys
    if key in _SKIP_KEYS:  # "objective.OBJ_value_EUR", "objective.Objective_residual_EUR"
        continue

    # 2. Investment Costs
    if key in _INVESTMENT_KEYS:
        # Prüfe ob Investment in diesem Fenster inkludiert werden soll
        if not cost_plan.investment_active(window_idx):
            continue

        # Prüfe ob bereits gezählt (amortise_once)
        if cost_plan.amortise_once and key in once_costs:
            continue

        # Addiere VOLLE Kosten (NICHT skaliert!)
        target[key] += value
        once_costs.add(key)
        continue

    # 3. Operational Costs
    scaled_value = value
    if key.startswith("objective."):
        scaled_value *= commit_fraction    # Skaliere mit committiertem Anteil!

    target[key] += scaled_value
```

**Beispiel:**
```
Fenster-Länge: 168h
Commit-Länge: 24h
commit_fraction = 24/168 = 0.143

Fenster-Kosten:
- objective.Capex_cost_EUR = 10000 EUR       → Hinzugefügt: 10000 EUR (1x, nicht skaliert)
- objective.Grid_energy_cost_EUR = 5000 EUR  → Hinzugefügt: 5000 * 0.143 = 715 EUR
```

**Bewertung:** ✅ **KORREKT**
- CAPEX: Volle Kosten, nur einmal
- OPEX: Skaliert mit commit_fraction (verhindert Doppelzählung bei Overlap)
- `investment_active()` verhindert CAPEX in späteren Fenstern (wenn amortise_once=True)

---

### 2.4 Kosten-Akkumulation in MPC

**Funktion:** `run_mpc()` (mpc.py:182-189)

**Aktueller Code:**
```python
for cost_key, cost_val in window_result.costs.items():
    # Investment costs: amortize once
    if cost_key in cost_plan.once_keys and cost_key not in once_costs:
        aggregated_costs[cost_key] = aggregated_costs.get(cost_key, 0.0) + cost_val
        once_costs.add(cost_key)
    # Operational costs: scale by commit fraction
    elif cost_key not in cost_plan.once_keys:
        aggregated_costs[cost_key] = aggregated_costs.get(cost_key, 0.0) + cost_val * commit_fraction
```

**❌ FEHLER:** `cost_plan.once_keys` existiert nicht!

`_CostAggregationPlan` hat folgende Attribute:
```python
@dataclass
class _CostAggregationPlan:
    include_investment: bool
    amortise_once: bool
    include_tie_breaker: bool
    include_installation: bool
    include_activation: bool

    def investment_active(self, window_idx: int) -> bool:
        ...
```

**KEIN Attribut `once_keys`!**

**Konsequenz:**
- ❌ MPC wirft `AttributeError: '_CostAggregationPlan' object has no attribute 'once_keys'`
- ❌ MPC-Läufe werden **FEHLSCHLAGEN**
- ❌ Keine korrekten Benchmark-Ergebnisse möglich

**Bewertung:** ❌ **KRITISCHER FEHLER - MUSS BEHOBEN WERDEN**

---

## 🔧 3. Erforderliche Korrekturen

### 3.1 MPC Kosten-Aggregation korrigieren

**Option A: Verwende _accumulate_costs() wie RH**

**Aktueller MPC-Code (FALSCH):**
```python
# Zeile 182-189 in mpc.py
for cost_key, cost_val in window_result.costs.items():
    if cost_key in cost_plan.once_keys and cost_key not in once_costs:  # ← FEHLER!
        aggregated_costs[cost_key] = aggregated_costs.get(cost_key, 0.0) + cost_val
        once_costs.add(cost_key)
    elif cost_key not in cost_plan.once_keys:  # ← FEHLER!
        aggregated_costs[cost_key] = aggregated_costs.get(cost_key, 0.0) + cost_val * commit_fraction
```

**Korrektur (Verwende RH-Funktion):**
```python
# Importiere _accumulate_costs
from energis.run.rolling_horizon import (
    ...
    _accumulate_costs,  # ← Hinzufügen!
)

# Ersetze manuellen Loop (Zeile 179-189) durch:
_accumulate_costs(
    aggregated_costs,
    window_result.costs,
    cost_plan,
    commit_fraction,
    window_idx,
    once_costs,
)
```

**Vorteile:**
- ✅ Identisches Verhalten wie RH
- ✅ Nutzt bewährte, getestete Logik
- ✅ Berücksichtigt `investment_active()` korrekt
- ✅ Berücksichtigt alle Investment-Keys (_INVESTMENT_KEYS)
- ✅ Kürzer und wartbarer

---

### 3.2 Zusätzliche Verbesserungen

**A) Konsistente Nutzung von _extend_series()**

RH verwendet:
```python
_extend_series(aggregated_series, window_result.series, commit_len)
```

MPC macht es manuell:
```python
for i, idx in enumerate(committed_indices):
    for key, values in window_result.series.items():
        if i < len(values):
            aggregated_series.setdefault(key, []).append(values[i])
```

**Empfehlung:** Importiere und nutze `_extend_series()` für Konsistenz.

**B) Konsistente Nutzung von _next_soc()**

RH verwendet:
```python
soc_next = _next_soc(window_result.series, commit_len, soc_next)
```

MPC macht es manuell:
```python
if base_storage_enabled and "TES_E" in window_result.series:
    soc_values = window_result.series["TES_E"]
    if commit_steps > 0 and commit_steps <= len(soc_values):
        soc_next = soc_values[commit_steps - 1]
```

**Empfehlung:** Importiere und nutze `_next_soc()` für Konsistenz.

---

## 📊 4. Zusammenfassung der Validierung

| Komponente | Status | Bewertung |
|------------|--------|-----------|
| **Design-Extraktion** | ✅ KORREKT | Alle Kapazitäten werden korrekt extrahiert |
| **Design-Fixierung** | ✅ KORREKT | Investment deaktiviert, Kapazitäten fixiert |
| **RH Kosten-Logik** | ✅ KORREKT | CAPEX 1x, OPEX skaliert, konfigurierbar |
| **RH Kosten-Akkumulation** | ✅ KORREKT | `_accumulate_costs()` funktioniert korrekt |
| **MPC Kosten-Akkumulation** | ❌ **FEHLER** | `cost_plan.once_keys` existiert nicht! |
| **MPC Series-Aggregation** | ⚠️ MANUELL | Funktioniert, aber sollte `_extend_series()` nutzen |
| **MPC SOC-Propagation** | ⚠️ MANUELL | Funktioniert, aber sollte `_next_soc()` nutzen |

---

## 🎯 5. Auswirkungen auf Szenarien

### 5.1 Betroffene Methoden

**❌ BETROFFEN (können nicht laufen):**
- Methode 4: RH-Forecast-Persistence
- Methode 5: RH-Forecast-Noisy
- Methode 6: PF→RH-Forecast-Persistence
- Methode 7: PF→RH-Forecast-Noisy

**✅ NICHT BETROFFEN:**
- Methode 1: PF (nutzt kein MPC)
- Methode 2: RH-Perfect (nutzt `_accumulate_costs()` korrekt)
- Methode 3: PF→RH-Perfect (nutzt `_accumulate_costs()` korrekt)

### 5.2 Kritikalität

**KRITISCH:** ⚠️⚠️⚠️
- 4 von 7 Methoden können nicht laufen
- Benchmark-Suite ist nicht funktionsfähig
- Alle MPC/Forecast-basierten Experimente betroffen

---

## ✅ 6. Validierungsergebnis: Design-Datenfluss

### 6.1 PF → Design → RH/MPC Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PF-Optimierung                                           │
│    - Löst gesamtes Jahr mit perfekten Daten                │
│    - Bestimmt optimale Kapazitäten                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. _extract_design_data()                                   │
│    ✅ Extrahiert aus PF result.summary:                     │
│       - heat_pumps[id].capacity_mw                          │
│       - heat_pumps[id].build_binary                         │
│       - storage.capacity_mwh                                │
│       - storage.power_mw                                    │
│       - storage.build_binary                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. WorkflowContext.design = DesignData(...)                │
│    ✅ Speichert Design-Daten in Context                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. RH/MPC Step mit fix_design=true                         │
│    - Prüft: context.plan.fix_design AND context.design     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. _apply_design_fix(window_cfg, context.design)           │
│    ✅ Fixiert Design in jeder Window-Konfiguration:         │
│       - investment.enabled = False                          │
│       - capacity_min = capacity_max = PF-Kapazität          │
│       - max_th_mw = min_th_mw = PF-Kapazität                │
│       - enabled = False falls build_binary < 0.5            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Optimierung mit fixiertem Design                        │
│    ✅ Solver kann nur Operation optimieren                  │
│    ✅ Kapazitäten sind fixiert (min=max)                    │
│    ✅ Investment-Variablen deaktiviert                      │
└─────────────────────────────────────────────────────────────┘
```

**Bewertung:** ✅ **VOLLSTÄNDIG KORREKT**

---

### 6.2 Kosten-Datenfluss bei PF→RH

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PF-Optimierung                                           │
│    Kosten:                                                  │
│      - CAPEX: 50000 EUR (Wärmepumpe + Speicher)           │
│      - OPEX: 100000 EUR (Strom, Gas, etc.)                │
│      - Total: 150000 EUR                                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. WorkflowResult.pf_result.costs                          │
│    ✅ PF-Kosten werden gespeichert                          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. RH Step mit fix_design=true                             │
│    - _load_cost_plan(cfg, fix_design=True)                 │
│      → include_investment = False (DEFAULT!)               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. RH Rolling Horizon Loop (52 Fenster @ 1 Woche)          │
│                                                             │
│    Fenster 1:                                               │
│      - Optimierung mit fixiertem Design                     │
│      - Window Kosten:                                       │
│          objective.Capex_cost_EUR = 0  (deaktiviert!)      │
│          objective.Grid_energy_cost_EUR = 2000             │
│      - _accumulate_costs():                                 │
│          if key in _INVESTMENT_KEYS:                        │
│              if not cost_plan.investment_active(0):         │
│                  continue  ← ÜBERSPRINGT CAPEX!            │
│          aggregated += 2000 * (24/168) = 286 EUR          │
│                                                             │
│    Fenster 2-52: Analog, KEIN CAPEX                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. WorkflowResult.rh_result.costs                          │
│    ✅ Nur OPEX: ~95000 EUR                                  │
│    ✅ KEIN CAPEX (wird nicht doppelt gezählt!)             │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Finale Kosten-Berechnung                                │
│    Total = PF.CAPEX + RH.OPEX                               │
│          = 50000 + 95000                                    │
│          = 145000 EUR                                       │
│                                                             │
│    ✅ CAPEX nur 1x gezählt (von PF)                         │
│    ✅ OPEX von RH (realistischer Betrieb)                   │
│    ✅ Keine Doppelzählung!                                  │
└─────────────────────────────────────────────────────────────┘
```

**Bewertung:** ✅ **VOLLSTÄNDIG KORREKT** (für RH, NICHT für MPC!)

---

## 🚨 7. Handlungsempfehlungen

### Priorität 1: KRITISCH - SOFORT BEHEBEN

**Fix MPC Kosten-Aggregation:**
```python
# In energis/run/mpc.py, Zeile 64-76:
from energis.run.rolling_horizon import (
    RollingHorizonResult,
    WindowResult,
    _hours_to_steps,
    _initial_soc,
    _storage_enabled,
    _apply_terminal_policy,
    _set_initial_soc,
    _apply_design_fix,
    _solve_scenario,
    _load_cost_plan,
    _extract_design_data,
    _accumulate_costs,    # ← HINZUFÜGEN
    _extend_series,       # ← HINZUFÜGEN (optional)
    _next_soc,            # ← HINZUFÜGEN (optional)
)

# Zeile 179-189: ERSETZEN durch:
_accumulate_costs(
    aggregated_costs,
    window_result.costs,
    cost_plan,
    commit_fraction,
    window_idx,
    once_costs,
)
```

### Priorität 2: Code-Qualität

**Konsistenz mit RH:**
- Nutze `_extend_series()` für Series-Aggregation
- Nutze `_next_soc()` für SOC-Propagation

### Priorität 3: Testing

**Nach Fix:**
1. Teste MPC_ONLY mit Persistence-Forecast
2. Teste PF_THEN_MPC mit Noisy-Forecast
3. Verifiziere Kosten-Aggregation (CAPEX nur 1x!)
4. Vergleiche RH vs. MPC Kosten-Struktur

---

## 📋 Checkliste

- [x] Design-Extraktion überprüft → ✅ KORREKT
- [x] Design-Fixierung überprüft → ✅ KORREKT
- [x] RH Kosten-Logik überprüft → ✅ KORREKT
- [x] MPC Kosten-Logik überprüft → ❌ **FEHLER GEFUNDEN**
- [ ] MPC Kosten-Logik korrigiert → **AUSSTEHEND**
- [ ] Tests durchgeführt → **AUSSTEHEND**
- [ ] Benchmark-Suite funktionsfähig → **AUSSTEHEND**

---

## 📝 Fazit

**Design-Übertragung:** ✅ **PERFEKT IMPLEMENTIERT**
- Alle Kapazitäten werden korrekt extrahiert und fixiert
- Build-Entscheidungen werden respektiert
- Investment wird sauber deaktiviert

**RH Kosten-Aggregation:** ✅ **PERFEKT IMPLEMENTIERT**
- CAPEX wird nur 1x gezählt (nicht in jedem Fenster)
- OPEX wird mit commit_fraction skaliert (verhindert Overlap-Doppelzählung)
- Bei PF→RH wird CAPEX korrekt ausgeschlossen (include_investment=False)

**MPC Kosten-Aggregation:** ❌ **KRITISCHER FEHLER**
- Code verweist auf nicht-existierendes Attribut `cost_plan.once_keys`
- Runtime-Fehler bei allen MPC-basierten Methoden
- Muss dringend behoben werden vor Benchmark-Läufen

**Gesamtbewertung:** ⚠️ **DESIGN KORREKT, KOSTEN-BUG MUSS BEHOBEN WERDEN**
