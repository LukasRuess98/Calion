# Vergleich aller verfügbaren Run-Methoden

## Übersicht

Dieses Dokument beschreibt alle verfügbaren Optimierungsmethoden für die Energiesystemplanung und deren fundamentale Unterschiede.

## 🎯 Fundamentale Konzepte

### 1. **Design vs. Operation**
- **Design**: Langfristige Investitionsentscheidungen (Kapazitäten von Wärmepumpe, Speicher, etc.)
- **Operation**: Kurzfristige Betriebsentscheidungen (Wann wird Wärme erzeugt? Wann wird Speicher geladen?)

### 2. **Vorausschau-Horizont**
- **Perfekt (Full Year)**: Kennt alle zukünftigen Werte (Preise, Nachfrage) im Voraus
- **Begrenzt (Rolling)**: Schaut nur begrenzt in die Zukunft (z.B. 168h = 1 Woche)

### 3. **Forecast-Qualität**
- **Perfekt**: Nutzt echte zukünftige Daten (unrealistisch, nur für Benchmark)
- **Forecast**: Nutzt Vorhersagen mit unvermeidbaren Fehlern (realistisch)

---

## 📊 Verfügbare Methoden im Detail

### 1️⃣ Perfect Forecast (PF)

**Szenario:** `perfect_forecast_full_year.scenario.yaml`

```yaml
run_mode: PF_ONLY
workflow: [PF]
fix_design: false
```

**Charakteristik:**
- ✅ **Optimales Design** (kennt gesamtes Jahr)
- ✅ **Optimale Operation** (kennt gesamtes Jahr)
- ❌ **Unrealistisch** (perfekte Voraussicht)
- 🎯 **Verwendung**: Theoretisches Optimum, untere Kostengrenze

**Mathematisch:**
```
min_x,u  ∑_{t=0}^{T} cost(x, u_t, demand_t, price_t)
s.t.     constraints(x, u, demand, price)

wobei demand, price = ECHTE Werte für gesamtes Jahr
```

**Vorteile:**
- Beste mögliche Lösung (Benchmark)
- Zeigt theoretische Kosteneinsparungen

**Nachteile:**
- Unrealistisch
- Nicht umsetzbar in Praxis

---

### 2️⃣ Rolling Horizon - Perfect Foresight (RH)

**Szenario:** `rolling_horizon_only.scenario.yaml` ✨ NEU

```yaml
run_mode: RH_ONLY
workflow: [RH]
fix_design: false
rolling_horizon:
  heat_horizon_hours: 168.0  # 1 Woche Vorausschau
  step_hours: 24.0           # Alle 24h neu planen
```

**Charakteristik:**
- ⚠️ **Myopisches Design** (nur 168h Vorausschau)
- ⚠️ **Myopische Operation** (nur 168h Vorausschau)
- ❌ **Unrealistisch** (nutzt perfekte Zukunftsdaten im Fenster!)
- 🎯 **Verwendung**: Verstehen des Effekts begrenzter Vorausschau

**Ablauf:**
```
t = 0
while t < T:
    # Optimiere Fenster [t : t+168h] mit ECHTEN Zukunftsdaten
    solve window(demand[t:t+168h], price[t:t+168h])
    # Führe nur erste 24h aus
    commit solution[0:24h]
    # Springe zum nächsten Zeitpunkt
    t += 24h
```

**⚠️ WICHTIG:** Diese Methode nutzt **noch perfekte Zukunftsdaten** im 168h-Fenster, nur der Horizont ist begrenzt!

**Vorteile:**
- Zeigt Effekt begrenzter Vorausschau isoliert
- Schnellere Berechnung als PF (kleinere Fenster)

**Nachteile:**
- Immer noch unrealistisch (perfekte Daten)
- Schlechteres Design als PF (myopisch)
- Höhere Kosten als PF

---

### 3️⃣ PF → RH (Perfect Design + Myopic Operation)

**Szenario:** `pf_then_rh.workflow.scenario.yaml`

```yaml
run_mode: PF_THEN_RH
workflow: [PF, RH]
fix_design: true  # RH nutzt PF-Design!
rolling_horizon:
  heat_horizon_hours: 168.0
  step_hours: 24.0
```

**Charakteristik:**
- ✅ **Optimales Design** (von PF mit perfekter Jahresvorausschau)
- ⚠️ **Myopische Operation** (RH mit 168h Vorausschau)
- ❌ **Halb-unrealistisch** (Design: unrealistisch, Operation: begrenzt)
- 🎯 **Verwendung**: Trennung von Design- und Operationsoptimierung

**Ablauf:**
```
# Phase 1: Design-Optimierung
x* = solve_PF(full_year_data)  # Optimale Kapazitäten

# Phase 2: Operations-Optimierung mit fixiertem Design
t = 0
while t < T:
    solve window(demand[t:t+168h], price[t:t+168h], fixed_design=x*)
    commit solution[0:24h]
    t += 24h
```

**Vorteile:**
- Trennt langfristige (Design) von kurzfristigen (Operation) Entscheidungen
- Optimales Design trotz myopischer Operation
- Niedriger als RH_ONLY (besseres Design)

**Nachteile:**
- Design-Phase unrealistisch (perfekte Jahresvorausschau)
- Operations-Phase nutzt noch perfekte Daten im Fenster

---

### 4️⃣ Rolling Horizon with Forecast - Persistence (RH-Forecast-Persistence)

**Szenario:** `rh_forecast_persistence.scenario.yaml` ✨ NEU

```yaml
run_mode: MPC_ONLY
workflow: [MPC]
fix_design: false
mpc:
  forecast_method: "persistence"
  forecast_horizon_hours: 168.0
  update_frequency_hours: 24.0
```

**Charakteristik:**
- ⚠️ **Myopisches Design** mit Forecast
- ✅ **Realistische Operation** mit Forecast-Updates
- ✅ **Realistisch** (nutzt naive Vorhersage)
- 🎯 **Verwendung**: Baseline für realistische Methoden

**Forecast-Methode: Persistence**
```python
# "Morgen wird wie heute"
forecast[t+1:t+168h] = historical[t-24h:t]  # Wiederhole letzten Tag
```

**Ablauf:**
```
t = 0
while t < T:
    # Generiere Vorhersage (naiv: Wiederholung)
    forecast = generate_persistence_forecast(historical[0:t], horizon=168h)

    # Optimiere mit Vorhersage
    solve window(forecast_demand, forecast_price)

    # Führe nur erste 24h aus (mit ECHTEN Werten!)
    commit solution[0:24h]

    # Springe zum nächsten Zeitpunkt
    t += 24h
```

**Vorteile:**
- ✅ Vollständig realistisch
- ✅ Einfache Vorhersage (keine Modelle nötig)
- ✅ Zeigt Wert von besseren Forecasts

**Nachteile:**
- Schlechte Forecast-Qualität
- Höhere Kosten als Methoden mit perfekter Vorausschau
- Suboptimales Design (myopisch mit schlechtem Forecast)

---

### 5️⃣ Rolling Horizon with Forecast - Noisy (RH-Forecast-Noisy)

**Szenario:** `rh_forecast_noisy.scenario.yaml` ✨ NEU

```yaml
run_mode: MPC_ONLY
workflow: [MPC]
fix_design: false
mpc:
  forecast_method: "perfect_noise"
  forecast_horizon_hours: 168.0
  update_frequency_hours: 24.0
  noise_std_dev: 0.10  # 10% Standardabweichung
  random_seed: 42
```

**Charakteristik:**
- ⚠️ **Myopisches Design** mit verrauschtem Forecast
- ✅ **Realistische Operation** mit Forecast-Updates
- ✅ **Realistisch** (simuliert reale Forecast-Fehler)
- 🎯 **Verwendung**: Realistischer als Persistence, zeigt Forecast-Qualitätseffekt

**Forecast-Methode: Perfect + Noise**
```python
# Perfekt + kontrolliertes Rauschen
forecast_demand = demand[t:t+168h] + N(0, σ * mean(demand))
forecast_price = price[t:t+168h] * LogNormal(0, σ)
```

**Ablauf:**
```
t = 0
while t < T:
    # Generiere verrauschte Vorhersage
    forecast = perfect_data[t:t+168h] + noise(σ=10%)

    # Optimiere mit verrauschtem Forecast
    solve window(forecast_demand, forecast_price)

    # Führe nur erste 24h aus (mit ECHTEN Werten!)
    commit solution[0:24h]

    t += 24h
```

**Vorteile:**
- ✅ Realistisch (simuliert echte Forecast-Fehler)
- ✅ Kontrollierbare Forecast-Qualität (σ-Parameter)
- ✅ Reproduzierbar (random seed)
- ✅ Besser als Persistence

**Nachteile:**
- Immer noch Forecast-Fehler
- Höhere Kosten als perfekte Methoden
- Suboptimales Design (myopisch)

---

### 6️⃣ PF → RH-Forecast-Persistence

**Szenario:** `pf_then_rh_forecast.scenario.yaml` ✨ NEU

```yaml
run_mode: PF_THEN_MPC
workflow: [PF, MPC]
fix_design: true
mpc:
  forecast_method: "persistence"
  forecast_horizon_hours: 168.0
  update_frequency_hours: 24.0
```

**Charakteristik:**
- ✅ **Optimales Design** (PF mit perfekter Jahresvorausschau)
- ✅ **Realistische Operation** (RH mit Forecast-Updates)
- ⚠️ **Halb-realistisch** (Design unrealistisch, Operation realistisch)
- 🎯 **Verwendung**: Best-Case Design + realistische Operation

**Ablauf:**
```
# Phase 1: Design-Optimierung (unrealistisch aber optimal)
x* = solve_PF(full_year_data)  # Optimale Kapazitäten

# Phase 2: Operations-Optimierung mit Forecast (realistisch)
t = 0
while t < T:
    forecast = generate_persistence_forecast(historical[0:t], 168h)
    solve window(forecast, fixed_design=x*)
    commit solution[0:24h]
    t += 24h
```

**Vorteile:**
- ✅ Optimales Design (niedrigste CAPEX)
- ✅ Realistische Operation
- ✅ Zeigt: "Was wäre wenn Design perfekt, aber Betrieb realistisch?"

**Nachteile:**
- Design-Phase unrealistisch
- Höhere OPEX als bei perfekter Vorausschau
- Design kann suboptimal sein für Forecast-basierte Operation

---

### 7️⃣ PF → RH-Forecast-Noisy

**Szenario:** `pf_then_mpc.scenario.yaml` (bereits vorhanden, mit noise)

```yaml
run_mode: PF_THEN_MPC
workflow: [PF, MPC]
fix_design: true
mpc:
  forecast_method: "perfect_noise"
  forecast_horizon_hours: 168.0
  update_frequency_hours: 24.0
  noise_std_dev: 0.10
```

**Charakteristik:**
- ✅ **Optimales Design** (PF)
- ✅ **Realistische Operation** (RH mit besserem Forecast als Persistence)
- ⚠️ **Halb-realistisch**
- 🎯 **Verwendung**: Effekt von Forecast-Qualität bei optimalem Design

---

## 📊 Vergleichstabelle

| Methode | Design | Operation | Forecast im Fenster | Horizont | Realistisch | Kosten (relativ) |
|---------|--------|-----------|---------------------|----------|-------------|------------------|
| **1. PF** | Optimal | Optimal | ✅ Perfekt | Ganzes Jahr | ❌ Nein | 100% (niedrigste) |
| **2. RH (perfect)** | Myopisch | Myopisch | ✅ Perfekt | 168h | ❌ Nein | ~105-115% |
| **3. PF→RH (perfect)** | Optimal | Myopisch | ✅ Perfekt | 168h | ⚠️ Halb | ~102-110% |
| **4. RH-Forecast-Pers** | Myopisch | Myopisch | ❌ Persistence | 168h | ✅ Ja | ~115-130% |
| **5. RH-Forecast-Noisy** | Myopisch | Myopisch | ⚠️ Noisy (10%) | 168h | ✅ Ja | ~110-120% |
| **6. PF→RH-Forecast-Pers** | Optimal | Myopisch | ❌ Persistence | 168h | ⚠️ Halb | ~107-118% |
| **7. PF→RH-Forecast-Noisy** | Optimal | Myopisch | ⚠️ Noisy (10%) | 168h | ⚠️ Halb | ~105-115% |

**Kostenranking (niedrigste → höchste):**
```
PF < PF→RH-Noisy < PF→RH-Perfect < PF→RH-Pers < RH-Noisy < RH-Perfect < RH-Pers
```

---

## 🔬 Wissenschaftliche Fragestellungen

### Forschungsfrage 1: Wert perfekter Information
**Vergleich:** PF vs. RH-Forecast-Pers
- Wie viel kostet uns begrenzte Vorausschau + Forecast-Fehler?

### Forschungsfrage 2: Wert von Forecast-Updates
**Vergleich:** RH-Perfect vs. RH-Forecast-Noisy
- Wie viel kostet uns Forecast-Unsicherheit alleine?

### Forschungsfrage 3: Trennung Design/Operation
**Vergleich:** RH-Forecast vs. PF→RH-Forecast
- Wie wichtig ist gutes Design vs. gute Operation?

### Forschungsfrage 4: Forecast-Qualität
**Vergleich:** RH-Forecast-Pers vs. RH-Forecast-Noisy
- Wie viel Wert hat bessere Forecast-Qualität?

### Forschungsfrage 5: Rolling Horizon Effekt
**Vergleich:** PF vs. RH-Perfect
- Wie viel kostet uns nur die begrenzte Vorausschau (ohne Forecast-Fehler)?

---

## 🎯 Empfohlene Benchmark-Sets

### Set A: Alle Methoden (umfassend)
```python
methods = [
    "PF",
    "RH_PERFECT",
    "PF_THEN_RH_PERFECT",
    "RH_FORECAST_PERSISTENCE",
    "RH_FORECAST_NOISY",
    "PF_THEN_RH_FORECAST_PERSISTENCE",
    "PF_THEN_RH_FORECAST_NOISY"
]
```

### Set B: Nur realistische Methoden
```python
methods = [
    "PF",  # Benchmark
    "RH_FORECAST_PERSISTENCE",
    "RH_FORECAST_NOISY",
    "PF_THEN_RH_FORECAST_PERSISTENCE",
    "PF_THEN_RH_FORECAST_NOISY"
]
```

### Set C: Minimal (für Quick-Tests)
```python
methods = [
    "PF",  # Theoretisches Optimum
    "PF_THEN_RH_FORECAST_NOISY"  # Realistischer Best-Case
]
```

---

## 📝 Naming Konvention

**Technisch (im Code):**
- `PF_ONLY`, `RH_ONLY`, `MPC_ONLY`, `PF_THEN_RH`, `PF_THEN_MPC`

**Konzeptionell (in Paper/Dokumentation):**
- Perfect Forecast (PF)
- Rolling Horizon with Perfect Foresight (RH-Perfect)
- Rolling Horizon with Forecast (RH-Forecast / MPC)
- PF → RH (two-stage optimization)

**Klarstellung:**
- **MPC = Rolling Horizon mit Forecast-Updates**
- Der einzige Unterschied zwischen RH und MPC ist ob echte Zukunftsdaten oder Forecasts genutzt werden!

---

## 🚀 Verwendungsbeispiele

### Beispiel 1: Schneller Test
```bash
# Nur PF und beste realistische Methode
python scripts/run_forecast_benchmark.py \
    --mode quick \
    --methods PF PF_THEN_RH_FORECAST_NOISY
```

### Beispiel 2: Vollständiger Vergleich
```bash
# Alle 7 Methoden
python scripts/run_forecast_benchmark.py \
    --mode standard \
    --methods PF RH_PERFECT PF_THEN_RH_PERFECT \
             RH_FORECAST_PERSISTENCE RH_FORECAST_NOISY \
             PF_THEN_RH_FORECAST_PERSISTENCE PF_THEN_RH_FORECAST_NOISY
```

### Beispiel 3: Nur realistische Methoden
```bash
python scripts/run_forecast_benchmark.py \
    --mode standard \
    --methods PF RH_FORECAST_PERSISTENCE RH_FORECAST_NOISY \
             PF_THEN_RH_FORECAST_PERSISTENCE PF_THEN_RH_FORECAST_NOISY
```

---

## ⚠️ Wichtige Hinweise

### 1. Perfekte Daten im Rolling Horizon
**Aktueller Stand:** Die Methoden `RH_PERFECT` und `PF_THEN_RH_PERFECT` nutzen im 168h-Fenster **echte zukünftige Daten**, nicht Forecasts!

```python
# RH-Perfect (aktuell):
window_table = slice_table(full_data, range(t, t+168h))  # ECHTE Zukunft!

# RH-Forecast/MPC:
window_table = forecast_generator.generate(historical, t, 168h)  # Vorhersage!
```

### 2. Design-Fixierung
- `fix_design: true` → RH nutzt PF-Design, optimiert nur Operation
- `fix_design: false` → RH optimiert Design + Operation gemeinsam (myopisch)

### 3. Forecast-Methoden
- **Persistence**: Einfachste Baseline, schlecht aber realistisch
- **Perfect + Noise**: Simuliert realistische Forecast-Fehler kontrolliert
- **Zukünftig**: ML-basierte Forecasts, Analog-Methoden, etc.

### 4. Kosten-Dekomposition
```python
Total Cost = CAPEX (amortisiert) + OPEX

CAPEX = Investition * Zinsfaktor / Lebensdauer
OPEX = Strom + Gas + Wartung + ...
```

Bei `PF_THEN_RH`: CAPEX stammt von PF, OPEX von RH!

---

## 📚 Literatur-Einordnung

**Perfect Forecast:**
- Benchmark in vielen Papers (Gabrielli et al., Marquant et al.)
- Zeigt theoretisches Optimum

**Rolling Horizon (Perfect):**
- Kaum verwendet (da unrealistisch)
- Kann Horizont-Effekt isolieren

**Model Predictive Control (MPC):**
- Standard in Control Theory (Bemporad, Morari)
- Energy Systems: Oldewurtel et al., Ma et al.
- Nutzt Forecasts + Updates

**Two-Stage (PF → RH):**
- Trennung Design/Operation: Morvaj et al., Dorfner et al.
- "What-if" Szenario: Optimales Design mit realistischer Operation

---

## ✅ Zusammenfassung

Wir haben nun **7 verschiedene Methoden** für systematische Vergleiche:

1. ✅ **PF** - Theoretisches Optimum
2. ✅ **RH-Perfect** - Effekt begrenzter Vorausschau (unrealistisch)
3. ✅ **PF→RH-Perfect** - Two-Stage mit perfekter Operation (unrealistisch)
4. ✅ **RH-Forecast-Pers** - Vollständig realistisch, naive Baseline
5. ✅ **RH-Forecast-Noisy** - Vollständig realistisch, bessere Forecasts
6. ✅ **PF→RH-Forecast-Pers** - Optimales Design + realistische Operation (naive)
7. ✅ **PF→RH-Forecast-Noisy** - Optimales Design + realistische Operation (besser)

**Für Applied Energy Paper:** Methoden 1, 4, 5, 6, 7 sind am relevantesten!
