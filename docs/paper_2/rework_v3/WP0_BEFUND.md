# WP0 — Bestandsaufnahme (Befund)

**Stand 2026-09-01.** Antworten auf die fünf WP0-Fragen aus `AGENT_PROMPT_Paper2_v3.md`,
jeweils mit Code-Referenz, plus zwei Zusatzbefunde, die die Diagnose von
`PAPER2_ECM_PLAN_v3.md` §0 direkt betreffen. Erstellt vor jeglichem Modell-Umbau.

> **Kernbefund vorweg:** Die zentrale Prämisse der Rework-Diagnose — „die nutzbare
> Speicherenergie ist **unabhängig von der Heizkurve** modelliert, damit war die Kopplung
> Heizkurve↔Speicher gar nicht abbildbar" — ist **im Code nicht haltbar**. Die ΔT(HK)→E_max-
> Kopplung existiert bereits. Damit ist der STOP-Punkt aus dem Agent-Prompt erreicht
> („melde sofort, wenn die ΔT-Kopplung bereits existiert"). Das „TES = Solver-Rauschen"-
> Ergebnis hat eine **andere** Ursache, die vor dem Umbau zu klären ist (→ Value-Probe).

---

## Frage 1 (kritisch): ΔT-Kopplung, E_max(V), Stillstandsverlust

**Datei:** `calion/models/blocks/geometric_storage.py`,
Injektion in `scripts/paper_2/scenario_runner.py`.

### 1a. Hängt `E_max` von `T_supply − T_return` ab? — **JA.**

```
_energy_coeff_mwh_per_m3(ΔT) = ρ · c_p · ΔT / 3.6e6      # geometric_storage.py:48–52
E_max = energy_coeff · V                                  # geometric_storage.py:249
```

`energy_coeff` ist linear in ΔT. E_max ist damit direkt ΔT-proportional. Der Docstring
sagt es explizit (Zeile 14–16): *„E_TES_max = rho * cp * delta_T * V_TES where delta_T is
treated as a scenario parameter (from heating curve)."*

### 1b. Ändert sich `E_max`, wenn die HK-Stufe wechselt? — **JA.**

`delta_T_scenario_k` wird pro Szenario **aus der HK-Stufe** injiziert:

```
T_VL_min_effective = max(hk_stage["T_VL_min_c"], return_temp_c + min_delta_T)  # scenario_runner.py:304
delta_T_scenario_k = round(T_VL_min_effective − return_temp_c, 2)              # scenario_runner.py:371
_asset_cfg["delta_T_scenario_k"] = delta_T_scenario_k                          # scenario_runner.py:374
```

`hk_stage` kommt aus `scenarios.yaml → heat_curve_stages[network][HK*]`
(scenario_runner.py:264–274). Also: HK0/1/2 → unterschiedliche `T_VL_min_c` →
unterschiedliches ΔT → unterschiedliches `energy_coeff` → unterschiedliches E_max **bei
gleichem V**. Genau die im Projekt geplante Kopplung.

> **Was fehlt:** nur `η_strat` (Schichtungswirkungsgrad, konstanter Skalar ~0.85). Ein
> globaler Multiplikator, der die Kopplung **nicht** qualitativ ändert. WP2 ist damit zu
> ~90 % bereits im Modell; „die verlorene Kopplung" ist nicht verloren.

### 1c. Stillstandsverlust: Volumen- oder Oberflächen-skaliert? — **Weder rein volumen-
noch oberflächen-, sondern SoC-proportional (fraktionaler Zerfall).**

```
loss_factor = hourly_loss ** dt_h                              # geometric_storage.py:342
E[t] = prev · loss_factor + eff_c·Qc·dt − Qd·dt/eff_d          # geometric_storage.py:353
```

Der Verlust pro Stunde ist `E·(1 − loss_factor)` — proportional zur **momentan
gespeicherten Energie**, nicht zur Oberfläche `V^{2/3}`. Bei Vollladung (E=E_max∝V) ist
er ∝ V; der Verlust **pro m³** ist also konstant. Ein `U·A·ΔT`-Stillstandsverlust
(∝ V^{2/3}, konstant unabhängig vom SoC) ist **nicht** implementiert.

**Konsequenz für die Diagnose:** Der Plan behauptet, der heutige Verlustterm „überbestraft
kleine und unterbestraft große Speicher — genau der Fehler, der jedes Optimum an den Cap
treibt". Das ist mechanisch **nicht** der Treiber (siehe Zusatzbefund B unten): ein
Wechsel auf `V^{2/3}` macht große Speicher **relativ günstiger** im Betrieb und treibt das
Optimum eher **stärker** an den Cap, nicht davon weg.

---

## Frage 2: Herkunft des `V_TES ≤ 5000 m³`-Caps

**Nicht hartkodiert, nicht willkürlich — zwei sich überlagernde, belegte Grenzen.**

1. **Config-Cap:** `V_max_m3: 5000.0` in
   `configs/paper_2/Stadtbach_topo.yaml:666` und `Memmingen_P2_base.yaml:438`.
   Inline-Kommentar beider Configs: *„was 50000 (atmospheric-tank scale)"* — d. h.
   bewusst von 50.000 auf 5.000 gesenkt.
2. **Geometrische Druckgrenze:** `p_max_bar: 10.0` (beide Configs, Z. 649 / 425).
   Im Code: `V_max_effective = min(V_max_m3, V_max_from_p)`
   (geometric_storage.py:152–155), mit `V_max_from_p` aus der Druck-Höhen-Grenze
   `h_max = (p_max − p_atm)·1e5/(ρg)`.

**Begründende Quelle:** Der Cap wurde am 2026-07-20 aus einer ASME-Druckbehälter-Rechnung
(thin-wall, P=10 bar, S=130 MPa Baustahl, E=0.85, ~60 mm Wand) auf ~5.500 m³ hergeleitet,
gerundet auf 5.000 m³; gleichzeitig `alpha_tes` **400→1200 €/m³** verdreifacht (PED-Klasse,
Wandstärke/Zertifizierung). Config-Kommentare Stadtbach Z. 652–654 / Memmingen Z. 428–431
dokumentieren das: *„a genuine PED-class pressurized vessel design point, above water's
atmospheric boiling point"*.

> **Das ist der Kern der Technologie-Entscheidung (siehe Zusatzbefund A):** der 5.000-m³-Cap
> ist die **physikalische** Grenze eines **druckbeaufschlagten** Behälters. Die im Plan
> vorgeschlagene Anhebung auf 50.000 m³ + degressive DEA-„pit/tank"-Kostenkurve gilt nur für
> **atmosphärische** Speicher — eine andere Technologie. Autorenentscheidung getroffen
> (2026-09-01): **Wechsel auf atmosphärisch/Pit** → Cap/alpha/p_max werden **ersetzt**, nicht
> „angehoben".

---

## Frage 3: Baseline-Definition (BC-MM / BC-SB)

**Dispatch-optimiert über den Bestandspark, KEINE regelbasierte Ist-Fahrweise — aber mit
einem TVLFIX-vs-HK-Confound.**

`configs/paper_2/scenarios.yaml:128–172`:
- `baseline: true`, `heat_curve_stage: TVLFIX`, `tvl_fix: true` (konstante VL-Temperatur).
- Neu-Investition **deaktiviert**: `hp_*/ek_*` `investment.enabled: false`,
  `capacity_max_mw: 0.0`; TES aus (`V_max_m3: 0.0`).
- Läuft durch **dasselbe** `run_single_scenario` / dieselbe MILP-Dispatch-Optimierung wie
  die Investitionsszenarien (`baseline.py:24–35` ruft nur `run_single_scenario`) — es gibt
  **keinen** separaten regelbasierten Fahrplan.

**Bewertung gegen Plan-Blocker B3:** Die schlimmste Befürchtung des Reviewers („+44,8 % misst
Optimierung vs. Ist-Fahrweise") trifft **nicht** zu — die Baseline ist dispatch-optimiert.
**Aber** zwei echte Confounds bleiben:
1. **Heizkurve:** Baseline = TVLFIX (konstante VL-Temp, Paper-1-Setpoint), Szenarien = HK0/1/2.
   „+44,8 %" mischt damit den Investitionseffekt **mit** dem Heizkurveneffekt. Für eine saubere
   „Effekt von Speicher+HK"-Aussage braucht es eine bei **gleicher** HK-Stufe optimierte
   Referenz (dispatch-optimiert, ohne Neuinvestition).
2. **Bestandspark verifizieren:** BC-SB-Beschreibung nennt „incl. 500 MWh TES + 10 MW P2H" —
   zu prüfen, ob dieser Bestand in den Investitionsszenarien identisch weiterläuft (sonst
   Park-Mismatch). Preisset ist konsistent (gleiche Config).

→ **B3 ist teilweise erfüllt.** To do: HK-gematchte, dispatch-optimierte Referenz als
Vergleichsanker; Bestandspark-Identität explizit prüfen und in `BASELINE_DEFINITION.md`
festhalten.

---

## Frage 4: Modellversions-Delta `e8e445e` ↔ `main`

Aus Projektstand (noch nicht als Git-Diff verifiziert — gehört in WP4/Studie I als
Invarianztabelle): Hauptunterschiede sind **laterale Wärmeverluste** und **Druckphysik auf
beiden Netzen**, die die Variablenzahl materiell erhöhen (MM-S4 ≈ 299k → 493k Variablen,
+65 %). Erwartete Wirkungsrichtung auf TAC: laterale Verluste **↑ Wärmebedarf/Verluste →
↑ TAC**; Druckphysik bindet zusätzliche Nebenbedingungen (Pumparbeit, Geschwindigkeitsgrenzen)
→ tendenziell **↑ TAC** in engpassnahen Szenarien.

**Status:** Als Tabelle (betroffene Gleichung × Wirkungsrichtung) noch zu erstellen; die
eigentliche Absicherung ist die 8-Szenarien-Invarianztabelle (WP4/Studie I) — deren Zweck
ist **nicht** die Absolutdifferenz, sondern ob sich **Rangfolgen** drehen. Autorenempfehlung
(bestätigt): auf `main` rechnen, `e8e445e` als Tag `paper2-campaign-v1` nur für Invarianz.

---

## Frage 5: Emissionsfaktor `ef_el` — konstant oder Zeitreihe?

**KORRIGIERT (2026-09-01, nach genauerer Prüfung): Das Modell nutzt bereits eine ECHTE
STÜNDLICHE EF-Zeitreihe — sowohl in der Zielfunktion als auch im Reporting. Der konstante
`ef_el_kg_per_mwh: 400` ist ein TOTER Config-Parameter (nirgends im Code gelesen).**

- **Daten vorhanden:** Die Input-Datei enthält die reale Stundenspalte `grid_co2_kg_MWh`
  (Config-Mapping `site.columns.co2_grid: "grid_co2_kg_MWh"` in beiden Netzen —
  `Stadtbach_topo.yaml:52`, `Memmingen_P2_base.yaml:23`). Stadtbach 2025: 8760 h, Mittel
  **277,9**, min **59,1**, max **562,7** kg/MWh (σ=121,3), Korrelation mit Spotpreis **0,73**
  — also echte, stark variable Netz-CO₂-Intensität, kein Platzhalter.
- **Zielfunktion nutzt sie stündlich:** `system_builder.py:292-295` baut
  `grid_co2_series_dict = {i: table["grid_co2_kg_MWh"][i]}` und übergibt sie an
  `EmissionsCalculator`; `emissions_calculator.py:113`: `elec[t] · grid_co2_series[t-1] · dt_h`.
- **Reporting/KPI nutzt sie stündlich:** `result_collector.py:836,861`
  (`P_buy[i] · grid_co2[i] · dt_h`).
- **`ef_el_kg_per_mwh: 400` wird im Code NICHT gelesen** (`grep ef_el_kg_per_mwh` über
  `calion/`+`scripts/` = leer). Ein irreführender Altwert; verleitete den Reviewer zu B5.
  (Der 400-Fallback in `network.py:518` greift nur im Legacy-`Network`-Pfad, wenn die Spalte
  fehlt — für Paper 2 ist die Spalte via `io/loader.py:321` PFLICHT und wird geladen.)

**Plan-Punkt B5 ist damit im Kern schon ERLEDIGT, nicht offen.** Was real noch zu tun ist:
1. Den toten `ef_el_kg_per_mwh: 400` aus beiden Configs entfernen/klar als „unused" markieren
   (er steht bei 400, der echte Jahresmittelwert der genutzten Reihe ist ~278 — Stolperfalle).
2. **Provenienz geklärt (2026-09-01):** `grid_co2_kg_MWh` = **electricitymaps** (Datensatz-Vintage
   2026). In T2 so zitieren. **Kleiner Caveat für §Limitations/T4:** die Modell-Horizont-Timestamps
   sind CY2025 (`horizon 2025-01-01…2025-12-31`, gleiche Zeilenausrichtung wie Last/Wetter) — falls
   die electricitymaps-Reihe inhaltlich 2026 ist, liegt die Netz-CO₂-Intensität in einem anderen
   Jahr als Last/Preis; positionsweise (Zeilenindex) konsistent verwendet, aber als Ein-Jahr-/
   Jahresmisch-Disclosure in T4 nennen. Beim Finalisieren kurz prüfen, welches Kalenderjahr die
   Reihe abdeckt.
3. Nur für F6 (Break-even-Karte, 2030/2045-Politikszenarien): zukünftige EF-Varianten — die sind
   **konstruierbar**, indem man die reale 2025-Stundenform auf projizierte Jahresmittel
   herunterskaliert (Projektion zitieren), keine neue Datenbeschaffung nötig.

---

## Zusatzbefund A — Die atmosphärisch-Entscheidung kollidiert mit Stadtbachs 122 °C

Die Autorenentscheidung „Wechsel auf atmosphärisch/Pit" (2026-09-01) hat eine harte
Machbarkeitsgrenze: ein atmosphärischer Speicher siedet bei ~100 °C, praktikable Decke
~95 °C. Die realen VL-Temperaturen (`scenarios.yaml:28–70`):

| Netz | T_VL_min (HK0→HK2) | **T_VL_max** | T_return (HK0→HK2) |
|---|---|---|---|
| Memmingen | 74 → 66 °C | **100 °C** | 63,6 → 51 °C |
| Stadtbach | 70 → 60 °C | **122 °C** | 60 → 45 °C |

- Für die **regulären** Szenarien basiert ΔT auf `T_VL_min` (60–74 °C) → Decke bindet nie.
- Für die **Hot-Charging**-Szenarien wird bei `T_VL_max` geladen
  (`scenario_runner.py:414`, `T_charge = T_VL_max`): Memmingen 100 °C **grenzwertig**,
  Stadtbach 122 °C **27 °C über** der atmosphärischen Decke.

→ Der Technologiewechsel erzwingt eine **explizite Speicher-Temperaturdecke (~95 °C)**, die
den Speicher vom Netz-Spitzen-VL entkoppelt. Physikalisch Standard (dänische Pit-Speicher
fahren 80–90 °C in heißeren Netzen), aber es macht den Speicher zu einem **niedrig-ΔT-,
groß­volumigen** Gerät — genau das Regime, in dem Geometrie zählt. Modellierungsentscheidung,
bewusst zu treffen, nicht zu erben. Betrifft die Hot-Charging-Szenarien (v. a. Stadtbach).

---

## Zusatzbefund B — Beide Geometrie-Fixes treiben das Optimum ZUM Cap, nicht davon weg

Der TES-Beitrag zum (zu minimierenden) Ziel: `CapEx(V) + Verlust(V) − Wert(V)`.

- **Oberflächenverlust** `∝ V^{2/3}` → Verlust **pro m³** ∝ `V^{−1/3}`, fallend → begünstigt
  **große** Speicher.
- **Degressive CapEx** `∝ V^{b}, b<1` → Kosten **pro m³** fallend → begünstigt **große**
  Speicher.

Beide WP1-Fixes machen große Speicher **pro m³ billiger**. Das heutige Ergebnis baut TES
schon beim **teuren** 1200-€/m³-Druckpreis bis an den 5.000-m³-Cap → Grenzwert des Speichers
> Grenzkosten selbst am Cap. Billiger + verlustärmer (atmosphärisch + diese Fixes) drückt das
Optimum **härter** in den Cap.

**Ein inneres Optimum kann daher nur von der Wertseite kommen** — Sättigung des
Arbitrage-/Peak-Shaving-Werts bei endlichen Speicherstunden — **oder** von einer echten
Bauplatz-/Footprint-Grenze. Die Plan-Behauptung „Geometrie-Fixes ergeben erstmals ein
inneres Optimum statt einer Randlösung" ist mechanisch **rückwärts**. Ob F2 (die zentrale
Abbildung) überhaupt existiert, ist eine **empirische** Frage: **wo sättigt der Speicherwert?**

→ Das ist der Zweck der **Value-Saturation-Probe** (nächster Schritt): dispatch-only,
HP-Kapazität fix, TES als **nicht-investierbarer** Fixtank über eine Energie-Rasterung
(0 → weit über 5.000 m³ hinaus, via Probe-Override von `p_max_bar`/`V_max_m3`), Messung von
`OPEX(E)`. Da der Fixtank **keine** CAPEX ins Ziel bringt (`investable=False` →
`InvestmentResult=None`), ist `OPEX(E)` die reine **Wertkurve**, kosten- und ΔT-unabhängig.
Grenzwert `m(E) = −dOPEX/dE`; Schnittpunkt mit der (atmosphärischen bzw. aktuellen)
Grenzkosten­geraden = Optimum. Ein Datenpunkt beantwortet es für **jede** Kostenannahme.

---

## Fazit / STOP

- WP0-Frage 1 (kritisch) ist beantwortet: **ΔT↔HK↔E_max-Kopplung existiert** → WP2 reduziert
  sich auf `η_strat` + korrekte Interpretation. Der STOP-Punkt des Agent-Prompts ist erreicht.
- Der 5.000-m³-Cap ist **echte Druckbehälter-Physik**, kein stiller Parameter → wird durch
  die atmosphärische Technologie **ersetzt**, mit expliziter ~95 °C-Decke (Zusatzbefund A).
- Das „TES = Solver-Rauschen"-Ergebnis ist **nicht** durch eine fehlende Kopplung erklärt.
  Vor dem Umbau klärt die **Value-Probe**, ob ein inneres Optimum physikalisch möglich ist
  (Zusatzbefund B). Ergebnis entweder: inneres Optimum (F2 publizierbar) **oder**
  site-limitiert (anderes, ebenso publizierbares Paper — Intro muss es dann von Anfang tragen).
- WP1-Codeweg: **`geometric_storage.py` erweitern** (nicht neues Modul); degressive Kosten an
  die **bestehende diskrete Energie-Leiter** hängen (exakt, gap-fest, kein SOS2 nötig).
