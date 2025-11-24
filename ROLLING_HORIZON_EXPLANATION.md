# Rolling Horizon - Detaillierte Erklärung

## Überblick

Das Framework implementiert verschiedene Optimierungsszenarien für die Wärmeplanung. Der Rolling Horizon funktioniert ähnlich wie **Model Predictive Control (MPC)**: Das Optimierungsfenster wird schrittweise verschoben, und nur ein Teil der Lösung wird tatsächlich "committed" (übernommen).

## Rolling Horizon Mechanismus

### Funktionsweise (wie MPC)

Der Rolling Horizon läuft **NICHT** über die komplette Zeitreihe auf einmal, sondern:

1. **Fenster-basierte Optimierung**:
   - Ein Optimierungsfenster (z.B. 168h = 1 Woche) wird über die Zeitreihe geschoben
   - Für jedes Fenster wird eine vollständige Optimierung durchgeführt

2. **Schrittweise Verschiebung**:
   - Nach jedem Fenster wird nur ein Teil der Lösung übernommen (committed)
   - Das Fenster wird dann um diesen Schritt vorwärts bewegt
   - Der Prozess wiederholt sich bis zum Ende der Zeitreihe

3. **Commit-Logik** (Zeile 695 in `rolling_horizon.py`):
   ```python
   commit_len = min(step_steps - overlap_steps, len(window_table))
   ```
   - `step_steps`: Schrittweite (z.B. 24h)
   - `overlap_steps`: Überlappung zwischen Fenstern (Standard: 0h)
   - **Committed werden**: Die ersten `step_steps - overlap_steps` Zeitschritte

4. **Fenster-Verschiebung** (Zeile 729):
   ```python
   start += max(step_steps - overlap_steps, 1)
   ```

### Parameter

| Parameter | Beschreibung | Typischer Wert | Config-Key |
|-----------|-------------|----------------|------------|
| `horizon_hours` | Länge des Optimierungsfensters | 168h (1 Woche) | `rolling_horizon.heat_horizon_hours` |
| `step_hours` | Um wie viel wird das Fenster verschoben | 24h (1 Tag) | `rolling_horizon.step_hours` |
| `overlap_hours` | Überlappung zwischen Fenstern | 0h (keine) | `rolling_horizon.overlap_hours` |
| `terminal_policy` | Storage-Endbedingung | "free" | `rolling_horizon.terminal_policy` |

### Beispiel

Bei `horizon_hours=168h`, `step_hours=24h`, `overlap_hours=0h`:

```
Fenster 1: [0h   ---------- 168h]  → Commit: 0-24h
Fenster 2:       [24h  ---------- 192h]  → Commit: 24-48h
Fenster 3:             [48h  ---------- 216h]  → Commit: 48-72h
...
```

## State-of-Charge (SOC) Management

Zwischen den Rolling Horizon Fenstern wird der **Speicher-Ladezustand** (State-of-Charge) übergeben:

1. **Am Ende jedes Fensters** (Zeile 715):
   ```python
   soc_next = _next_soc(window_result.series, commit_len, soc_next)
   ```
   - Extrahiert den SOC am Ende des committed Bereichs

2. **Am Anfang des nächsten Fensters** (Zeile 679-680):
   ```python
   if soc_next is not None and base_storage_enabled:
       _set_initial_soc(window_cfg, soc_next)
   ```
   - Setzt den Anfangs-SOC für das nächste Fenster

Dies sorgt für **zeitliche Konsistenz** zwischen den Fenstern.

## Szenarien im Detail

### 1. PF_ONLY (Perfect Forecast)

**Datei**: `configs/scenarios/perfect_forecast_full_year.scenario.yaml`

**Workflow**: `[PF]`

**Beschreibung**: Einmalige Optimierung über die **gesamte Zeitreihe** (typisch: 8760h = 1 Jahr)

**Eigenschaften**:
- ✅ Globales Optimum (beste Lösung)
- ✅ Design-Optimierung (Investitionen in HP und Speicher)
- ❌ Nicht realistisch (perfekte Zukunftskenntnis über 1 Jahr)
- ❌ Hohe Rechenzeit bei langen Zeitreihen

**Kosten**:
- Alle Kosten aktiv:
  - CAPEX (Investitionen)
  - OPEX (Betrieb, Strom, Brennstoff)
  - Demand Charges
  - CO2-Kosten
  - Tie-Breaker & Activation-Kosten

**Übergabe**:
- Design (Wärmepumpen-Kapazitäten, Speicher-Größe) für nachfolgende RH-Läufe

---

### 2. RH_ONLY (Rolling Horizon mit perfekter Vorausschau)

**Datei**: `configs/scenarios/rolling_horizon_only.scenario.yaml`

**Workflow**: `[RH]`

**Beschreibung**: Rolling Horizon mit **perfektem Vorwissen** innerhalb des Fensters

**Eigenschaften**:
- ✅ Myopische Design-Optimierung (Design wird in jedem Fenster neu optimiert)
- ✅ Realistischere Simulation als PF_ONLY
- ⚠️ Suboptimal gegenüber PF (kein globales Optimum)
- ⚠️ Noch immer unrealistisch (perfekte 168h-Vorausschau)

**Parameter**:
- `horizon_hours`: 168h (1 Woche Optimierung)
- `step_hours`: 24h (täglich neues Fenster)
- `fix_design`: `false` (Design wird optimiert)

**Kosten im RH**:

Die Kosten werden **nicht** einfach summiert - das würde zu Doppelzählungen führen!

Stattdessen (Zeile 787-826 in `rolling_horizon.py`, `_accumulate_costs`):

| Kostenart | Behandlung | Grund |
|-----------|-----------|-------|
| **Investitionskosten** (CAPEX) | Nur **einmal** im ersten Fenster | Einmalige Investition |
| **Aktivierungskosten** | Nur **einmal** im ersten Fenster | Einmalige Aktivierung |
| **Tie-Breaker** | Nur **einmal** im ersten Fenster | Einmalige Entscheidung |
| **Storage Installation** | Nur **einmal** im ersten Fenster | Einmalige Installation |
| **Betriebskosten** (OPEX) | **Skaliert** mit `commit_fraction` | Nur committed Teil zählt |
| **Energiekosten** | **Skaliert** mit `commit_fraction` | Nur committed Teil zählt |
| **Demand Charges** | **Skaliert** mit `commit_fraction` | Nur committed Teil zählt |

**Commit-Fraction** (Zeile 705):
```python
commit_fraction = float(commit_len / len(window_table))
```
- Bei 24h committed von 168h Fenster: `commit_fraction = 24/168 = 0.143`

**Übergabe zwischen Fenstern**:
- SOC (Speicher-Ladezustand)
- Design (falls im ersten Fenster optimiert und nicht fixiert)

---

### 3. PF_THEN_RH (Perfect Forecast → Rolling Horizon)

**Datei**: `configs/scenarios/pf_then_rh.workflow.scenario.yaml`

**Workflow**: `[PF, RH]`

**Beschreibung**: Zweistufiger Ansatz - **Realistischste Simulation**

**Ablauf**:

1. **Schritt 1 - PF**:
   - Optimierung über das gesamte Jahr
   - Bestimmt **Design** (HP-Kapazitäten, Speicher-Größe)

2. **Schritt 2 - RH**:
   - Rolling Horizon mit **fixiertem Design** aus Schritt 1
   - Simuliert realistische Betriebsplanung mit perfekter Kurzzeit-Vorausschau

**Eigenschaften**:
- ✅ Realistischste Simulation (Investition → Betrieb getrennt)
- ✅ Design aus PF wird fixiert (`fix_design: true`)
- ✅ RH simuliert Betriebsphase mit Planungshorizont

**Parameter**:
- `fix_design`: `true` (Design aus PF wird übernommen)
- RH-Parameter wie bei RH_ONLY

**Kosten im RH-Teil**:
- **Keine** Investitionskosten (Design ist fixiert)
- Nur Betriebskosten:
  - Energiekosten
  - Brennstoffkosten
  - Demand Charges
  - CO2-Kosten

**Design-Fixierung** (Zeile 1034-1071 in `rolling_horizon.py`, `_apply_design_fix`):
```python
# Für jede Wärmepumpe:
hp_cfg["max_th_mw"] = capacity_from_pf
hp_cfg["min_th_mw"] = capacity_from_pf
invest_cfg["enabled"] = False  # Investment deaktiviert

# Für Speicher:
storage_cfg["max_energy_mwh"] = capacity_from_pf
invest_cfg["enabled"] = False
```

**Übergabe PF → RH**:
- **Design-Daten** (via JSON oder intern):
  - Heat Pump Kapazitäten (MW thermal)
  - Heat Pump Build-Binary (gebaut: ja/nein)
  - Storage Kapazität (MWh)
  - Storage Power (MW)

---

### 4. MPC_ONLY / RH_FORECAST (MPC mit Prognosen)

**Dateien**:
- `configs/scenarios/mpc_persistence.scenario.yaml`
- `configs/scenarios/rh_forecast_persistence.scenario.yaml`

**Workflow**: `[MPC]`

**Beschreibung**: Rolling Horizon mit **realistischen Prognosen** statt perfekter Vorausschau

**Eigenschaften**:
- ✅ **Realistischste Variante** (nutzt Forecasts wie in der Praxis)
- ✅ Simuliert Prognosefehler
- ⚠️ Suboptimal (wegen Prognosefehlern)

**MPC-Ablauf** (siehe `mpc.py`):

```python
while current_index < n:
    # 1. Neue Prognose generieren
    forecast_table = forecast_gen.generate_forecast(
        historical_data=historical_data,
        current_index=current_index,
        horizon_hours=168.0,
        dt_h=dt_h,
    )

    # 2. Optimierung mit Prognose
    window_result = optimize(forecast_table, ...)

    # 3. Nur ersten Teil committen (z.B. 24h)
    commit_steps = update_frequency_hours

    # 4. Fenster verschieben
    current_index += commit_steps
```

**Unterschied zu RH_ONLY**:
- RH_ONLY: Nutzt **echte historische Daten** im Fenster (perfekt)
- MPC: Nutzt **Prognosen** im Fenster (realistisch)

**Prognose-Methoden**:

1. **Persistence** (`forecast_method: "persistence"`):
   - "Morgen = Heute"
   - Einfachste Methode
   - Gut für stationäre Daten

2. **Perfect with Noise** (`forecast_method: "perfect_noise"`):
   - Echte Daten + Rauschen
   - Für Sensitivitätsanalysen

**Parameter**:
- `forecast_horizon_hours`: 168h (Prognose-Horizont)
- `update_frequency_hours`: 24h (wie oft neue Prognose)
- `forecast_method`: "persistence" oder "perfect_noise"

**Kosten**:
- Wie bei RH_ONLY
- Investitionskosten optional (abhängig von `fix_design`)

---

## Szenario-Vergleich

| Szenario | Workflow | Design-Optimierung | Vorwissen | Rechenzeit | Realismus | Qualität |
|----------|----------|-------------------|-----------|------------|-----------|----------|
| **PF_ONLY** | [PF] | ✅ Global | Perfekt (Jahr) | Hoch | Niedrig | Optimal |
| **RH_ONLY** | [RH] | ✅ Myopisch | Perfekt (Woche) | Mittel | Mittel | Suboptimal |
| **PF_THEN_RH** | [PF, RH] | ✅ PF, dann fix | PF: Jahr<br>RH: Woche | Hoch | **Hoch** | Gut |
| **MPC** | [MPC] | ✅/❌ Optional | Prognose (Woche) | Mittel | **Sehr Hoch** | Suboptimal |

## Kosten-Aggregation im Rolling Horizon

### Problem: Doppelzählung

Würde man die Kosten einfach summieren:
```
Total = Sum(Fenster_1_Kosten + Fenster_2_Kosten + ...)
```

**Problem**: Überlappende Bereiche würden mehrfach gezählt!

### Lösung: Commit-Fraction Skalierung

**Code** (Zeile 787-826 in `rolling_horizon.py`):

```python
def _accumulate_costs(target, window_costs, plan, commit_fraction, window_idx, once_costs):
    for key, value in window_costs.items():
        if key in INVESTMENT_KEYS:  # CAPEX, Activation, etc.
            if plan.amortise_once and window_idx > 0:
                continue  # Nur im ersten Fenster
            target[key] = value
        else:
            # Betriebskosten: Skalieren mit committed Anteil
            if key.startswith("objective."):
                scaled_value = value * commit_fraction
            target[key] += scaled_value
```

### Beispiel-Rechnung

**Szenario**: 168h Fenster, 24h committed

```
Fenster 1:
- Window total energy cost: 10000 EUR (für 168h optimiert)
- Commit fraction: 24/168 = 0.143
- Aggregated: 10000 * 0.143 = 1430 EUR ✅

Fenster 2:
- Window total energy cost: 12000 EUR
- Commit fraction: 24/168 = 0.143
- Aggregated: 12000 * 0.143 = 1716 EUR ✅

Total energy cost: 1430 + 1716 + ... = Realistisch ✅
```

### Kostenarten im Detail

**Investitionskosten** (`_CostAggregationPlan`, Zeile 136-151):

```python
include_investment: bool          # Investition aktiv?
amortise_once: bool = True        # Nur einmal zählen?
include_tie_breaker: bool         # Tie-Breaker aktiv?
include_installation: bool        # Installation aktiv?
include_activation: bool          # Aktivierung aktiv?
```

**Standard-Verhalten**:
- Bei `fix_design=True`: **Keine** Investitionskosten in RH
- Bei `fix_design=False`: Investitionskosten **nur im ersten Fenster**

**Config-Override** (in `base.yaml` oder `costs` Section):
```yaml
costs:
  include_investment_in_rh: false  # Überschreibt Standard
  amortise_investment_once_in_rh: true  # Standard
  include_tie_breaker_in_rh: true
  include_installation_in_rh: true
  include_activation_in_rh: true
```

## Terminal Policy für Speicher

Der `terminal_policy` definiert, was am **Ende eines Rolling Horizon Fensters** mit dem Speicher passiert:

| Policy | Bedeutung | Use Case |
|--------|-----------|----------|
| `"free"` | Keine Endbedingung | Standard, flexibel |
| `"empty"` | Speicher muss leer sein | Konservativ |
| `"full"` | Speicher muss voll sein | Optimistisch |
| `"maintain"` | SOC = Anfangs-SOC | Zyklisch |

**Standard**: `"free"` (keine Einschränkung)

**Implementation** (Zeile 1020-1031 in `rolling_horizon.py`):
```python
def _apply_terminal_policy(cfg, policy):
    storage["terminal"]["policy"] = policy
```

## Praktische Hinweise

### 1. Welches Szenario wählen?

**Für Design-Entscheidungen**:
- ➡️ **PF_ONLY**: Initiale Dimensionierung

**Für realistische Simulation**:
- ➡️ **PF_THEN_RH**: Trennung Design/Betrieb
- ➡️ **MPC**: Mit Prognose-Unsicherheit

**Für Sensitivitätsanalyse**:
- ➡️ **RH_ONLY**: Verschiedene Horizonte testen

### 2. Parameter-Tuning

**Horizon Hours** (Fenster-Länge):
- 168h (1 Woche): Standard, gute Balance
- 336h (2 Wochen): Bessere Vorausschau, höhere Rechenzeit
- 72h (3 Tage): Schneller, myopischer

**Step Hours** (Commit-Länge):
- 24h (1 Tag): Standard für tägliche Planung
- 8h: Feinere Granularität
- 48h: Schneller, weniger Fenster

**Overlap**:
- 0h: Standard, keine Überlappung
- >0h: Glatterer Übergang, aber mehr Fenster

### 3. Rechenzeit-Optimierung

**Schnellere Optimierung**:
```yaml
run:
  solver_options:
    MIPGap: 0.02        # 2% statt 0.01%
    TimeLimit: 1800     # 30min statt 1h
    MIPFocus: 1         # Fokus auf Feasibility
```

**Kürzerer Zeitraum testen**:
```yaml
scenario:
  horizon:
    type: "date_range"
    start: "2023-01-01"
    end: "2023-02-01"  # Nur 1 Monat statt Jahr
```

## Code-Referenzen

| Funktion | Datei | Zeile | Beschreibung |
|----------|-------|-------|--------------|
| `_run_rolling_horizon` | `rolling_horizon.py` | 634-747 | Hauptschleife |
| `_accumulate_costs` | `rolling_horizon.py` | 787-826 | Kosten-Aggregation |
| `_apply_design_fix` | `rolling_horizon.py` | 1034-1071 | Design fixieren |
| `run_mpc` | `mpc.py` | 22-212 | MPC mit Prognosen |
| `_apply_terminal_policy` | `rolling_horizon.py` | 1020-1031 | Terminal Policy |
| `_next_soc` | `rolling_horizon.py` | 861-866 | SOC-Übergabe |

## Zusammenfassung

**Rolling Horizon = MPC-ähnlich**:
- ✅ Fenster wird schrittweise verschoben
- ✅ Nur Teil der Lösung wird committed
- ✅ SOC wird zwischen Fenstern übergeben
- ✅ Kosten werden korrekt skaliert (keine Doppelzählung)

**Nicht wie naive Batch-Verarbeitung**:
- ❌ Nicht einfach "komplette Länge berechnen und ausgeben"
- ❌ Nicht einfach Kosten aufsummieren

**Szenarien-Hierarchie**:
1. **PF_ONLY**: Benchmark, optimales Design
2. **PF_THEN_RH**: Realistische Simulation mit optimalem Design
3. **MPC**: Realistischste Simulation mit Prognosen
4. **RH_ONLY**: Myopische Alternative (ohne PF-Phase)
