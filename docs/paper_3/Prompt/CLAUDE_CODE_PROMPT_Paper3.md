# CLAUDE CODE — IMPLEMENTIERUNGSAUFTRAG
# Paper 3: CO₂-Bilanzierung in elektrifizierten Wärmenetzen
# CALION Framework | Lukas Ruess | Fraunhofer IPA / EEP Stuttgart
# ═══════════════════════════════════════════════════════════════════════════════

## KONTEXT & EINORDNUNG

Du arbeitest am CALION-Framework (Python/Pyomo/Gurobi) für die Optimierung
elektrifizierter Wärmenetze. Dieses Skript gehört zu Paper 3 einer kumulativen
Dissertation. Paper 1 und 2 sind bereits fertiggestellt und validiert.

**Wichtig:** Das bestehende CALION-Codebase ist deine Basis. Alle neuen Module
werden als eigenständige, importierbare Python-Dateien ergänzt — niemals
bestehende CALION-Kerndateien überschreiben.

---

## PROJEKTSTRUKTUR (Ziel)

```
paper3/
├── data/                          ← von smard_download.py erzeugt (bereits vorhanden)
│   ├── generation_15min_2025.parquet
│   ├── load_15min_2025.parquet
│   ├── prices_1h_2025.parquet
│   ├── ef_all_granularities_2025.parquet
│   ├── ef_g6_15min_2025.parquet
│   └── co2_summary_2025.csv
│
├── smard_download.py              ← BEREITS IMPLEMENTIERT (nicht anfassen)
│
├── calion_l1_paper3.py            ← ZU IMPLEMENTIEREN: CALION L1 Dispatch-Modell
├── run_simulations.py             ← ZU IMPLEMENTIEREN: Alle 18 Solver-Runs orchestrieren
├── co2_postprocessing.py          ← ZU IMPLEMENTIEREN: CO₂-Post-Processing Pipeline
├── figures.py                     ← ZU IMPLEMENTIEREN: Alle 12 Abbildungen
│
├── results/
│   ├── runs/                      ← Solver-Outputs je Run (Parquet)
│   ├── co2/                       ← CO₂-Bilanzen (Parquet + CSV)
│   └── figures/                   ← Abbildungen (PDF + PNG)
│
└── paper3_main.py                 ← ZU IMPLEMENTIEREN: Einstiegspunkt, alles in Sequenz
```

---

## DATENBASIS (bereits vorhanden)

```python
# Pfade zu den SMARD-Daten (von smard_download.py erzeugt):
DATA_DIR = Path("./data")

# Inhalte:
# ef_all_granularities_2025.parquet — Index: hourly DatetimeIndex (Europe/Berlin)
# Spalten:
#   ef_g1        [g CO2/kWh] — Jahreswert konstant 344.0
#   ef_g2        [g CO2/kWh] — Monatsmittel
#   ef_g3        [g CO2/kWh] — Wochenmittel
#   ef_g4        [g CO2/kWh] — Tagesmittel
#   ef_g5_m1     [g CO2/kWh] — Stündlich, attributional
#   ef_g5_m2     [g CO2/kWh] — Stündlich, MEFS (Merit-Order-Approx.)
#   ef_g6_m1     [g CO2/kWh] — Viertelstündlich → stündlich gemittelt (für Dispatch)
#   ee_share_1h  [0..1]      — EE-Anteil stündlich
#   residual_load_gw [GW]    — Residuallast stündlich

# prices_1h_2025.parquet:
#   da_price     [EUR/MWh]   — EPEX Spot Day-Ahead, stündlich
```

---

## AUFGABE 1: `calion_l1_paper3.py`

Implementiere das CALION L1 MILP-Dispatch-Modell (Kupferschiene) mit Pyomo/Gurobi.

### Modellparameter

```python
@dataclass
class NetworkParams:
    name: str                    # "memmingen" oder "stadtbach"
    q_demand_mwh: pd.Series      # Wärmebedarf stündlich [MWh/h], Index=DatetimeIndex
    t_outside_c: pd.Series       # Außentemperatur stündlich [°C]

@dataclass
class SystemParams:
    config: str                  # "S1", "S2", "S3"
    # Wärmepumpe
    hp_cap_mw: float             # Wärmeleistung nominal [MW_th]
    hp_cop_rated: float          # COP bei Normbedingungen
    hp_t_ref_c: float            # Referenzaußentemp. für COP [°C], default -7
    hp_cop_min: float            # Min. COP (Clipping), default 1.5
    # Elektrodenkessel (S3 only)
    eb_cap_mw: float             # Elektrische Leistung [MW_el], default 0.0
    eb_eta: float                # Wirkungsgrad, default 0.99
    # Thermischer Speicher (S2 only)
    tes_cap_mwh: float           # Speicherkapazität [MWh_th], default 0.0
    tes_loss_per_h: float        # Verlustrate [1/h], default 0.005
    tes_eta_charge: float        # Ladeeffizienz, default 0.95
    tes_eta_discharge: float     # Entladeeffizienz, default 0.95
    tes_soc_min: float           # Min. SOC [MWh_th], default 0.05 * tes_cap_mwh
    tes_soc_max: float           # Max. SOC [MWh_th], default 0.95 * tes_cap_mwh
    tes_soc_init: float          # Start-SOC [MWh_th], default 0.5 * tes_cap_mwh

@dataclass
class OperationParams:
    strategy: str                # "B1", "B2", "B3"
    prices_eur_mwh: pd.Series    # Strompreise stündlich [EUR/MWh]
    price_fixed: float           # Fixpreis für B1 [EUR/MWh], default 120.0
    rh_horizon_h: int            # Rolling-Horizon Fenstergröße [h], default 24
    rh_step_h: int               # Rollschritt [h], default 1
    mip_gap: float               # Solver MIPGap, default 0.001
    time_limit_s: int            # Solver Zeitlimit [s], default 3600
```

### COP-Modell

```python
def compute_cop(t_outside: float, cop_rated: float, t_ref: float = -7.0,
                cop_min: float = 1.5) -> float:
    """
    Lineares COP-Modell: COP steigt mit Außentemperatur.
    COP(T) = cop_rated + 0.08 * (T - t_ref)
    Geclippt auf [cop_min, cop_rated * 1.5]
    """
```

### MILP-Modell (Pyomo)

```python
def build_l1_model(
    net: NetworkParams,
    sys: SystemParams,
    ops: OperationParams,
    time_index: pd.DatetimeIndex,
) -> pyo.ConcreteModel:
    """
    Aufbau des L1 MILP-Modells für einen gegebenen Zeithorizont.

    Entscheidungsvariablen:
      p_hp_el[t]   ≥ 0  — Elektrische WP-Leistung [MW_el]
      p_eb_el[t]   ≥ 0  — Elektrische EK-Leistung [MW_el] (S3)
      q_tes_ch[t]  ≥ 0  — TES Ladeleistung [MW_th] (S2)
      q_tes_dch[t] ≥ 0  — TES Entladeleistung [MW_th] (S2)
      soc_tes[t]   ≥ 0  — TES Ladezustand [MWh_th] (S2)

    Constraints:
      [C1] Wärmebilanz:
           q_hp[t] + q_eb[t] + q_tes_dch[t] - q_tes_ch[t] == q_demand[t]
           mit q_hp[t] = p_hp_el[t] * COP[t]
               q_eb[t] = p_eb_el[t] * eta_eb

      [C2] Kapazitätsgrenzen:
           0 ≤ p_hp_el[t] ≤ hp_cap_mw / COP[t]
           0 ≤ p_eb_el[t] ≤ eb_cap_mw
           0 ≤ q_tes_ch[t] ≤ tes_cap_mwh * 0.5  (Laderampe)
           0 ≤ q_tes_dch[t] ≤ tes_cap_mwh * 0.5

      [C3] TES SOC-Dynamik:
           soc_tes[t] = soc_tes[t-1] * (1 - loss_per_h)
                        + q_tes_ch[t] * eta_ch
                        - q_tes_dch[t] / eta_dch
           soc_min ≤ soc_tes[t] ≤ soc_max

      [C4] SOC-Initialisierung und Periodizität:
           soc_tes[0] = soc_init  (für PF: soc_init = 0.5 * cap)
           soc_tes[T] ≥ soc_tes[0]  (kein "Entleer-Trick" am Jahresende)

    Zielfunktion (Kostenminimierung):
      min Σ_t [ (p_hp_el[t] + p_eb_el[t]) * price[t] ] * dt
      mit dt = 1 h
    """
```

### Solve-Funktion mit Rolling Horizon

```python
def solve_dispatch(
    net: NetworkParams,
    sys: SystemParams,
    ops: OperationParams,
    horizon: pd.DatetimeIndex,
) -> dict:
    """
    Löst den Dispatch-MILP.

    Für B1, B2: Einmaliger Solve über den gesamten Horizont.
    Für B3: Rolling-Horizon mit rh_horizon_h Fenster und rh_step_h Rollschritt.

    Returns dict mit:
      p_el_total_mw: pd.Series   — Gesamtstromverbrauch [MW_el], stündlich
      p_hp_el_mw:   pd.Series   — WP-Strombezug [MW_el]
      p_eb_el_mw:   pd.Series   — EK-Strombezug [MW_el]
      q_hp_mwh:     pd.Series   — WP-Wärmeproduktion [MWh/h]
      q_eb_mwh:     pd.Series   — EK-Wärmeproduktion [MWh/h]
      soc_tes_mwh:  pd.Series   — TES SOC [MWh] (None für S1)
      cost_eur:     float        — Jahresbetriebskosten [EUR]
      q_demand_mwh: pd.Series   — Übergebener Wärmebedarf (zur Kontrolle)
      solver_status: str         — "optimal" / "feasible" / "infeasible"
      solve_time_s:  float       — Solver-Zeit [s]
    """
```

---

## AUFGABE 2: `run_simulations.py`

Orchestriert alle 18 Solver-Runs. Liest Netz- und Systemparameter aus
Konfigurationsdateien, ruft `calion_l1_paper3.solve_dispatch()` auf,
speichert Ergebnisse.

### Run-Konfiguration

```python
# Netze
NETWORKS = {
    "memmingen": NetworkParams(
        name="memmingen",
        q_demand_mwh=...,   # Aus Messdaten laden (stündlich 2025, 8760h)
        t_outside_c=...,    # DWD-Station Memmingen 2025
    ),
    "stadtbach": NetworkParams(
        name="stadtbach",
        q_demand_mwh=...,   # Aus Paper-1-Modell (SLP-skaliert auf Jahressumme)
        t_outside_c=...,    # DWD-Station Stuttgart/Stadtbach 2025
    ),
}

# Systemkonfigurationen — Parameterwerte MÜSSEN angepasst werden!
# Die folgenden Werte sind PLATZHALTER — ersetze mit echten Netzwerten:
SYSTEMS = {
    "S1": SystemParams(config="S1", hp_cap_mw=12.0, hp_cop_rated=3.5,
                        eb_cap_mw=0.0, tes_cap_mwh=0.0, ...),
    "S2": SystemParams(config="S2", hp_cap_mw=12.0, hp_cop_rated=3.5,
                        tes_cap_mwh=50.0, ...),   # TES-Kapazität aus Paper 2!
    "S3": SystemParams(config="S3", hp_cap_mw=12.0, hp_cop_rated=3.5,
                        eb_cap_mw=5.0, ...),
}

# Betriebsstrategien
STRATEGIES = {
    "B1": OperationParams(strategy="B1", price_fixed=120.0, ...),
    "B2": OperationParams(strategy="B2", prices_eur_mwh=da_prices, ...),
    "B3": OperationParams(strategy="B3", prices_eur_mwh=da_prices,
                          rh_horizon_h=24, rh_step_h=1, ...),
}

# Run-Matrix (18 Runs)
RUN_MATRIX = [
    # (run_id, network, system, strategy)
    ("R01", "memmingen", "S1", "B1"),
    ("R02", "memmingen", "S2", "B1"),
    ("R03", "memmingen", "S3", "B1"),
    ("R04", "memmingen", "S1", "B2"),
    ("R05", "memmingen", "S2", "B2"),
    ("R06", "memmingen", "S3", "B2"),
    ("R07", "memmingen", "S1", "B3"),
    ("R08", "memmingen", "S2", "B3"),
    ("R09", "memmingen", "S3", "B3"),
    ("R10", "stadtbach", "S1", "B1"),
    ("R11", "stadtbach", "S2", "B1"),
    ("R12", "stadtbach", "S3", "B1"),
    ("R13", "stadtbach", "S1", "B2"),
    ("R14", "stadtbach", "S2", "B2"),
    ("R15", "stadtbach", "S3", "B2"),
    ("R16", "stadtbach", "S1", "B3"),
    ("R17", "stadtbach", "S2", "B3"),
    ("R18", "stadtbach", "S3", "B3"),
]
```

### Ausgabeformat je Run

```python
# Speichere je Run als Parquet: results/runs/{run_id}.parquet
# Spalten:
#   timestamp       — DatetimeIndex Europe/Berlin
#   p_el_total_mw   — Gesamtstrom [MW_el]
#   p_hp_el_mw      — WP-Strom [MW_el]
#   p_eb_el_mw      — EK-Strom [MW_el]
#   q_hp_mwh        — WP-Wärme [MWh/h]
#   q_eb_mwh        — EK-Wärme [MWh/h]
#   soc_tes_mwh     — TES SOC [MWh]
#   q_demand_mwh    — Wärmebedarf (Referenz)
#   da_price        — Strompreis [EUR/MWh]
#   ef_g5_m1        — Stündl. EF (attributional) [g/kWh]

# Speichere Metadaten als JSON: results/runs/{run_id}_meta.json
# {run_id, network, system, strategy, cost_eur, solve_time_s,
#  solver_status, q_demand_total_mwh, q_supply_total_mwh,
#  p_el_total_mwh_a, cop_annual_mean}
```

### Wichtige Hinweise für B3 (Rolling Horizon)

```python
# Rolling-Horizon Implementierung:
# - Fenster: 24h voraus (ein Handelstag)
# - Rollschritt: 1h
# - SOC-Initialisierung: Übernimm den tatsächlichen SOC aus dem letzten Schritt
#   (nicht den nominalen Startwert — das ist der entscheidende Unterschied zu PF)
# - Nur die erste Stunde je Fenster wird als "committed" übernommen
# - Letzter Zeithorizont: Randbehandlung falls < 24h verbleiben

# ACHTUNG: 8760 Solver-Calls für B3 — stelle sicher dass:
# 1. Das Modell warm gestartet wird (vorherige Lösung als Hint)
# 2. Der MIPGap für RH etwas lockerer sein darf (0.5% statt 0.1%)
# 3. Fortschritt wird geloggt (alle 168h = 1 Woche)
```

---

## AUFGABE 3: `co2_postprocessing.py`

Liest alle 18 Run-Outputs, multipliziert mit EF-Zeitreihen, berechnet KPIs.

### Kern-Funktion

```python
def compute_co2_all_runs(
    runs_dir: Path,
    ef_df: pd.DataFrame,           # aus ef_all_granularities_2025.parquet
    ef_g6_15min: pd.Series,        # 15-min EF für G6
) -> pd.DataFrame:
    """
    Berechnet CO2-Emissionen für alle 18 Runs × 5 EF-Varianten.

    EF-Varianten:
      G1:    ef_g1 (konstant)
      G2:    ef_g2 (monatlich)
      G3:    ef_g3 (wöchentlich)
      G4:    ef_g4 (täglich)
      G5_M1: ef_g5_m1 (stündlich, attributional)   ← Referenz
      G5_M2: ef_g5_m2 (stündlich, MEFS)
      G6_M1: ef_g6_m1 (stündl. Mittel aus 15-min)  ← separat gespeichert

    Formel:
      CO2[t/a] = Σ_t ( P_el[t] [MW] * EF[t] [g/kWh] * 1h ) / 1e6
      (1 MW * 1h = 1 MWh; 1 MWh * g/kWh = 1000 g = 0.001 kg → / 1e6 → t)

    Returns DataFrame mit Index = run_id, Spalten = [co2_g1, co2_g2, ...,
    co2_g5_m2, co2_g6_m1, ef_err_g1_pct, ef_err_g2_pct, ..., cost_eur,
    network, system, strategy, q_demand_mwh, cop_mean]
    """
```

### KPI-Berechnung

```python
def compute_kpis(co2_df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet alle Paper-3-KPIs aus der CO2-Bilanz-Tabelle.

    K1: co2_abs_g{x}     [t/a]  — absolute Emissionen je Granularität
    K2: co2_spez_g{x}    [kg/MWh_th] — normiert auf Wärmeproduktion
    K3: ef_err_g{x}_pct  [%]   — (CO2_Gx - CO2_G5_M1) / CO2_G5_M1 * 100
    K4: rh_pen_pct       [%]   — (CO2_B3 - CO2_B2) / CO2_B2 * 100
    K5: stor_ben_pct     [%]   — (CO2_S1 - CO2_S2) / CO2_S1 * 100
    K6: m1_m2_delta_pct  [%]   — (CO2_M2 - CO2_M1) / CO2_M1 * 100
    K7: cost_eur_a       [EUR/a]
    K8: co2_monthly      [t/Monat × 12] — als separater DataFrame
    """
```

---

## AUFGABE 4: `figures.py`

Erstelle alle 12 Abbildungen. Matplotlib/Seaborn. Einheitliches Farbschema.

### Farbschema (VERBINDLICH — nicht abweichen)

```python
COLORS = {
    # Systemkonfigurationen
    "S1": "#1F5C99",    # Blau
    "S2": "#C55A11",    # Orange
    "S3": "#375623",    # Grün
    # Strategien (Linientypen)
    "B1": "dashed",
    "B2": "solid",
    "B3": "dotted",
    # Netzwerke (Sättigung)
    "memmingen": 1.0,   # volle Sättigung
    "stadtbach":  0.6,  # 60% Sättigung (alpha)
    # Methoden (Marker)
    "M1": "o",          # Kreis
    "M2": "^",          # Dreieck
    # Granularitäten (für Achsenbeschriftung)
    "G1": "Jährl.\n(G1)",
    "G2": "Monatl.\n(G2)",
    "G3": "Wöchentl.\n(G3)",
    "G4": "Tägl.\n(G4)",
    "G5": "Stündl.\n(G5)",
    "G6": "15-min\n(G6)",
}
FIGSIZE_SINGLE = (8, 5)     # Einspaltig
FIGSIZE_DOUBLE = (14, 5)    # Zweispaltig (Memmingen | Stadtbach)
FONTSIZE = 10
DPI_SCREEN = 100
DPI_PRINT  = 300
```

### Abbildungen im Detail

```python
# F1 — Systemübersicht (konzeptionell, keine Daten)
# Erstelle mit matplotlib.patches ein Systemschema:
# [WP] → [Wärmenetz (L1=Kupfer)] → [Verbraucher]
# [EB] ↗
# [TES] ↕
# CO₂-Post-Processing-Kette unten: P_el(t) × EF_G1..G6(t) → CO₂-Bilanzen

# F2 — EF-Zeitreihe 2025
# 3 Linien: ef_g5_m1 (stündlich, Blau, alpha=0.4), ef_g2 (monatlich, Orange),
#           ef_g1 (konstant, Rot gestrichelt)
# x: Jan–Dez 2025, y: [g CO₂/kWh], dual-y für EE-share (rechts)

# F3 — EF-Heatmap
# x: Stunde des Tages (0–23), y: Monat (1–12)
# Farbe: mittlerer ef_g5_m1 [g/kWh], Colormap: RdYlGn_r (rot=hoch, grün=niedrig)
# Annotiere: PV-Mittagstief, Winter-Peaks

# F4 — Dispatch-Vergleich (Exemplarwoche)
# Wähle automatisch: kälteste Woche (Winter) + wärmste Woche (Sommer)
# 4 Subplots übereinander: Strompreis, EF, P_WP+P_EB, SOC_TES
# 3 Linien je Subplot: B1/B2/B3 (jeweils S2, Memmingen)

# F5 — Jahreskostenvergleich
# Grouped Bar: x={S1,S2,S3} × {B1,B2,B3}, y=Kosten [kEUR/a]
# Zwei Panels: Memmingen (links) | Stadtbach (rechts)
# Füge Prozentzahl-Annotation hinzu: Ersparnis B2 vs. B1

# F6 — CO₂-Divergenzkurve (KERNFIGUR — höchste Sorgfalt!)
# x: G1,G2,G3,G4,G5,G6 (diskret, gleichmäßig)
# y: CO₂ [t/a], links; rel. Fehler zu G5 [%], rechts (twin axis)
# Linien: S1 (Blau), S2 (Orange), S3 (Grün) — je Strategie ein Panel
# 3 Panels: B1 | B2 | B3
# Schraffierter Bereich: |G1 - G5| für jeden S
# Referenzlinie: G5 als gestrichelt grau
# Annotation: Fehlerprozent direkt am G1-Punkt

# F7 — Bilanzierungsfehler Boxplot
# x: G1,G2,G3,G4,G6 (relativ zu G5), y: ef_err [%]
# Boxplot über alle 18 Runs
# Horizontale Nulllinie, Farbkodierung: positiv=Überschätzung, negativ=Unterschätzung

# F8 — M1 vs. M2 Scatter
# x: co2_g5_m1 [t/a], y: co2_g5_m2 [t/a]
# 18 Punkte, Farbe=Systemkonf., Marker-Form=Strategie
# Diagonale y=x als gestrichelte Referenz
# Annotiere Ausreißer mit Run-ID

# F9 — Monatliche CO₂-Heatmap
# Zeilen: 18 Runs (sortiert: Memmingen oben, Stadtbach unten)
# Spalten: 12 Monate
# Farbe: CO₂ [t/Monat], normiert auf jeweiliges Jahresmaximum je Run
# y-tick labels: "{run_id}: {network}-{system}-{strategy}"

# F10 — RH vs. PF Lollipop
# x: 6 System×Netz-Kombinationen (S1/S2/S3 × Mmg/Stb)
# y: (CO₂_B3 - CO₂_B2) / CO₂_B2 * 100 [%] → RH-Penalität
# Getrennt für G5_M1 und G5_M2
# Nulllinie, positive Werte = RH schlechter als PF

# F11 — Netzvergleich (normiert)
# x: Systemkonf. S1/S2/S3, y: co2_spez [kg CO₂/MWh_th]
# Überlagere Memmingen (volle Farbe) und Stadtbach (transparent)
# Pro Strategie B1/B2/B3 je eine Gruppe
# Zeigt: Generalisierbarkeit der Kernaussage

# F12 — Policy-Implikationsdiagramm (konzeptionell)
# x: Granularität G1..G6 (diskret)
# y: mittlerer |Bilanzierungsfehler| [%] über alle Runs
# Farbzonen:
#   Rot (G1):    GEG aktuell / politische Jahresbilanzierung
#   Gelb (G2-G3): Monatliche Regulatorik (EU-Taxonomie-Diskussion)
#   Grün (G5+):  Wissenschaftlicher Standard / Dispatch-relevante Auflösung
# Empfehlungspfeil: "Mindestanforderung für preisoptimierte Netze: G4 (täglich)"

def save_figure(fig, name: str, results_dir: Path) -> None:
    """Speichere als PDF (Vektorformat für Journal) und PNG (Preview)."""
    fig_dir = results_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / f"{name}.pdf", dpi=DPI_PRINT, bbox_inches="tight")
    fig.savefig(fig_dir / f"{name}.png", dpi=DPI_SCREEN, bbox_inches="tight")
```

---

## AUFGABE 5: `paper3_main.py`

Einstiegspunkt — führt alles in Sequenz aus.

```python
def main():
    """
    Vollständige Paper-3-Pipeline:
    1. Prüfe ob SMARD-Daten vorhanden (Hinweis falls nicht: python smard_download.py)
    2. Lade alle Eingangsdaten
    3. Führe 18 Solver-Runs durch (run_simulations.py)
    4. CO₂-Post-Processing (co2_postprocessing.py)
    5. Erstelle alle 12 Abbildungen (figures.py)
    6. Exportiere Ergebnis-Tabellen als CSV für Paper
    """

# CLI:
# python paper3_main.py --step all          # Alles
# python paper3_main.py --step simulate     # Nur Solver-Runs
# python paper3_main.py --step co2          # Nur Post-Processing
# python paper3_main.py --step figures      # Nur Abbildungen
# python paper3_main.py --runs R01 R02 R03  # Spezifische Runs
# python paper3_main.py --force             # Überschreibe Cache
```

---

## ANPASSUNGEN DIE DU (Lukas) VOR DEM START VORNEHMEN MUSST

Markiert mit `# ANPASSEN:` im Code:

```python
# 1. Memmingen-Wärmebedarf einlesen
#    ANPASSEN: Pfad und Format der Messdaten von e-con AG / ECONTEC
q_demand_memmingen = pd.read_csv("./input/memmingen_waermebedarf_2025.csv", ...)

# 2. Stadtbach-Wärmebedarf einlesen
#    ANPASSEN: Format aus Paper-1-Kalibrierung
q_demand_stadtbach = pd.read_csv("./input/stadtbach_waermebedarf_2025.csv", ...)

# 3. Außentemperatur
#    ANPASSEN: DWD CDC Download oder eigene Messdaten
t_outside_memmingen = pd.read_csv("./input/dwd_memmingen_2025.csv", ...)
t_outside_stadtbach = pd.read_csv("./input/dwd_stuttgart_2025.csv", ...)

# 4. Systemparameter Memmingen (aus Paper 2 / Anlagendokumentation e-con AG)
#    ANPASSEN: Echte Anlagenparameter
hp_cap_mw_memmingen  = 12.0    # ANPASSEN
hp_cop_rated         = 3.5     # ANPASSEN: Herstellerdatenblatt
tes_cap_mwh          = 50.0    # ANPASSEN: Paper-2-Auslegungswert
eb_cap_mw            = 5.0     # ANPASSEN: EB-Leistung Memmingen

# 5. Systemparameter Stadtbach
#    ANPASSEN: Entsprechend Paper-1-Netzparametrierung
hp_cap_mw_stadtbach  = ...     # ANPASSEN
tes_cap_mwh_stadtbach = ...    # ANPASSEN

# 6. Fixpreis B1
price_fixed = 120.0             # ANPASSEN: Representativer Fixpreis für Memmingen 2025
```

---

## QUALITÄTSPRÜFUNGEN (nach jedem Run automatisch)

```python
def validate_run_output(result: dict, net: NetworkParams, sys: SystemParams) -> None:
    """
    Pflichtchecks nach jedem Solver-Run:

    CHECK 1: Energiebilanz
      |Σ q_supply - Σ q_demand| / Σ q_demand < 0.001  (< 0.1%)

    CHECK 2: Kapazitätsgrenzen
      p_hp_el.max() ≤ hp_cap_mw / COP_min * 1.001
      p_eb_el.max() ≤ eb_cap_mw * 1.001

    CHECK 3: SOC-Grenzen (S2)
      soc_tes.min() ≥ tes_soc_min - 0.01
      soc_tes.max() ≤ tes_soc_max + 0.01

    CHECK 4: Jahresperiodizität (S2, PF)
      |soc_tes[-1] - soc_tes[0]| / tes_cap_mwh < 0.05

    CHECK 5: Solver-Status
      assert solver_status in ("optimal", "feasible")

    Logge alle Checks. Wirf ValueError bei Fehlschlag.
    """
```

---

## ABHÄNGIGKEITEN

```
# requirements_paper3.txt
pyomo>=6.7
gurobipy>=11.0        # Akademische Lizenz vorhanden
pandas>=2.2
numpy>=1.26
pyarrow>=15.0
matplotlib>=3.8
seaborn>=0.13
requests>=2.31
scipy>=1.12           # für Interpolation / Statistik
tqdm>=4.66            # Fortschrittsbalken Rolling Horizon
```

---

## STIL & KONVENTIONEN

- **Sprache:** Docstrings auf Deutsch, Code/Variablennamen auf Englisch
- **Typen:** Vollständige Type Hints in allen Funktionssignaturen
- **Logging:** `logging`-Modul, kein `print()` in Library-Code
- **Fehlerbehandlung:** Explizite Exceptions mit aussagekräftigen Messages
- **Pfade:** Immer `pathlib.Path`, niemals String-Konkatenation
- **DataFrames:** Index immer timezone-aware (`Europe/Berlin`)
- **Einheiten:** Immer in Variablenname oder Docstring angeben ([MW], [EUR/MWh], [t/a])
- **Caching:** Parquet-Dateien als Cache — Pipeline überspringt Schritte wenn vorhanden

---

## PRIORITÄT DER IMPLEMENTIERUNG

1. `calion_l1_paper3.py` — Kern des Projekts, alles hängt daran
2. `run_simulations.py` — Orchestrierung, einfach sobald Modell steht
3. `co2_postprocessing.py` — Reine Datenverarbeitung, klar spezifiziert
4. `figures.py` — Iterativ, kann parallel zu Auswertung entstehen
5. `paper3_main.py` — Einfaches Wrapper-Skript, zuletzt

**Starte mit Aufgabe 1. Stelle Rückfragen falls Netzparameter (hp_cap_mw,
tes_cap_mwh etc.) für Memmingen/Stadtbach nicht in vorhandenen CALION-Dateien
zu finden sind — Lukas ergänzt diese dann vor dem ersten Run.**
