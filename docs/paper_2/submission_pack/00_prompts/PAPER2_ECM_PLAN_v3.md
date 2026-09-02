# Paper 2 — Reworked Plan v3 (ECM-Ausrichtung)

**Stand 2026-09-01. Ersetzt `IMPLEMENTATION_PLAN.md` (v2, 2026-08-30) als Source of Truth.**
Ziel: die ursprüngliche Paper-Idee (geometrische, topologische, heizkurvenbasierte
Auslegung von Speichern und Wärmepumpen) wiederherstellen, **ohne** die neuen
Ergebnisse zu verwerfen — sondern indem sie an die richtige Stelle gerückt werden.
Zieljournal: *Energy Conversion and Management* (≈9.000 Wörter, ≤15 Elemente Haupttext).

---

## 0. Diagnose in drei Sätzen

Die Rework-Runde vom August hat ein methodisch sauberes, aber inhaltlich falsch
gewichtetes Paper erzeugt: Der Elektrifizierungs-Sweep (ein *Nebenergebnis*, das
zudem parameterdeterminiert ist) wurde zum Centrepiece, während die
Speicherauslegung — das eigentliche Thema — **kein einziges verwertbares Ergebnis
liefert** (Memmingen: TES vernachlässigbar; Stadtbach: TES am 5.000-m³-Cap in jedem
Szenario). Der Grund dafür ist nicht die Physik der Netze, sondern **eine Lücke im
Modell**: Speicherverluste skalieren linear mit dem Volumen statt mit der Oberfläche,
die Investitionskosten sind linear statt degressiv, und die nutzbare Speicherenergie
ist **unabhängig von der Heizkurve** modelliert. Damit war die geplante Kopplung
Heizkurve ↔ Speichergröße ↔ COP **modellseitig gar nicht abbildbar** — das
„TES-Volumen ist Solver-Rauschen"-Ergebnis ist ein Modellartefakt, kein Befund.

Das ist die gute Nachricht: Die verlorene Kernstory ist nicht widerlegt, sie war nie
im Modell. Sie zurückzuholen kostet einen überschaubaren Modell-Ausbau und macht das
Paper gleichzeitig ECM-tauglich.

---

## 1. Neue Positionierung

**Arbeitstitel:**
*Where, how large, and under which conditions? Nodal MILP co-design of heat-pump
siting and thermal-storage geometry in existing district heating networks.*

**Beitrag (vier Aussagen, alle mit n=2 verteidigbar, weil Methoden- bzw.
Schwellenwertaussagen):**

| # | Beitrag | Warum n=2 reicht |
|---|---|---|
| C1 | **Geometrische Speicherauslegung im MILP**: oberflächenskalierte Verluste (V^{2/3}), degressive Investitionskosten, heizkurvenabhängige nutzbare Energiedichte — ergibt erstmals ein *inneres* Optimum statt einer Randlösung | Methodenbeitrag |
| C2 | **Heizkurve ↔ Speicher ↔ COP als echter Zielkonflikt**: Absenkung hebt COP und senkt Netzverluste, **verringert aber ΔT und damit die nutzbare Speicherkapazität pro m³** — das Optimum ist nicht die tiefste Heizkurve | physikalischer Mechanismus, an zwei Netzen quantifiziert |
| C3 | **Topologie ändert die Investitionsentscheidung**: (a) Siting-Landschaft, (b) direkter Vergleich aggregiertes Ein-Knoten-Modell vs. nodales L3+-Modell → Fehlentscheidungskosten | Methodenbeitrag, Brücke zu Paper 1 |
| C4 | **Wann sich Elektrifizierung rechnet**: Break-even-CO₂-Preis / Strom-Gas-Preisverhältnis je Netz statt „rechnet sich 2026 nicht" | Schwellenwert ist übertragbar, das Einzelergebnis nicht |

**Was wir NICHT mehr behaupten:** „Multi-fidelity framework L1–L3+" als eigener
Beitrag (kollidiert mit Paper 1 → Salami-Verdacht). Fidelity-Levels erscheinen nur
als *Methodenkontext mit Zitat auf Paper 1*. Ebenso raus: jede Aussage der Form
„Netzgröße/Topologie *verursacht* X".

---

## 2. Der Modell-Ausbau (das Herzstück, WP1–WP2)

### 2.1 Speichergeometrie statt Speichervolumen

Zylindrischer Tank, Volumen `V`, Schlankheitsgrad `AR = h/d`:

```
d = (4V / (π·AR))^(1/3)
A(V, AR) = π·(AR + 0.5)·(4/(π·AR))^(2/3) · V^(2/3)  =  k(AR) · V^(2/3)
```

- **Stillstandsverlust:** `Q̇_loss = U · k(AR) · V^(2/3) · (T̄_TES − T_amb)`
  statt heute `hourly_loss = 0.001 · SoC` (volumenproportional).
  Der heutige Ansatz **überbestraft kleine und unterbestraft große Speicher** —
  genau der Fehler, der jedes Optimum an den Cap treibt.
- **Geometrie-Trade-off (kleines, aber sauberes Nebenergebnis):** `k(AR)` ist minimal
  bei `AR = 1`; reale Schichtspeicher haben `AR = 2…4`. Der Oberflächenaufschlag
  beträgt nur ≈5 % (AR=2 vs. AR=1) — d. h. **Schichtungsqualität ist billiger als
  ihr Verlustpreis**. Das ist eine belastbare, zitierfähige Aussage und liefert die
  im Projektauftrag geforderte *geometrische* Auslegung.
- **Degressive Investitionskosten:** `C_inv(V) = c_0 · (V/V_0)^b`, `b ≈ 0.6…0.7`
  (Literatur: DEA Technology Data, Pit/Tank TES-Kostenkurven) statt
  `1200 €/m³ + 100 k€`. Linearisierung: **SOS2-λ-PWL, 5–6 Stützstellen** (exakt,
  unabhängig von Konvexität — anders als eine naive Sekanten-PWL).

### 2.2 Heizkurve → nutzbare Speicherkapazität (die verlorene Kopplung)

```
E_max(V, HK) = ρ · c_p · V · ΔT(HK) · η_strat ,   ΔT(HK) = T_sup(HK) − T_ret
```

**Vor dem Bauen zu prüfen (WP0):** ob die aktuelle Implementierung `E_TES` bereits an
ΔT koppelt. Nach Aktenlage (F4-Befund „TES-Volumen = Solver-Rauschen") vermutlich
nicht. Falls nicht, ist das der wichtigste Fix des ganzen Pakets:

Ohne diese Kopplung ist die Heizkurvenabsenkung im Modell **einseitig positiv**
(COP↑, Verluste↓) und ein Optimierer geht immer zur tiefsten Stufe. Mit ihr entsteht
der echte Zielkonflikt: −5 K Vorlauf bei 40 K Spreizung heißt −12,5 % Energiedichte,
d. h. +14 % Volumen für dieselbe Speicherleistung. **Das ist die im Projekt
ursprünglich geplante „heizkurvenbasierte Auslegung von Speichern" — und sie wird
jetzt erstmals quantifizierbar.**

### 2.3 Cap-Politik

- Cap 5.000 m³ → **50.000 m³** (bzw. so weit, bis in beiden Netzen ein *inneres*
  Optimum erscheint). Wenn der Cap physikalisch gemeint war (Grundstück, Statik,
  max. Bauhöhe ~30 m), muss er als **Nebenbedingung mit Quelle** erscheinen, nicht
  als stiller Modellparameter.
- Ergebnisberichterstattung **normiert**: `V/Peak-Last [m³/MW]` bzw.
  **Speicherstunden** `E_max / Peak-Last [h]`. Nur so sind 5-MW- und 200-MW-Netz
  überhaupt vergleichbar — Voraussetzung für die „Endpunkte"-Argumentation.

### 2.4 Wärmepumpe

COP(T_sup) ist vorhanden. Zu ergänzen bzw. explizit zu diskutieren: `min_load`
erzeugt bei Überdimensionierung Teillast-/Taktverluste → **auch für die WP existiert
ein inneres Kapazitätsoptimum**, das der bisherige gezwungene Sweep verdeckt hat.

---

## 3. Papierstruktur (ECM)

| § | Titel | Inhalt | Elemente |
|---|---|---|---|
| 1 | Introduction | Lücke: Siting *und* Sizing von WP/TES in **Bestandsnetzen** werden üblicherweise auf aggregierten Ein-Knoten-Modellen entschieden; Speichergeometrie und Vorlauftemperatur-Kopplung fehlen | — |
| 2 | Method | Nodales L3+-MILP (Kurzfassung, Verweis Paper 1); **neu**: TES-Geometriemodul, ΔT(HK)-Kopplung, degressive PWL-Kosten, McCormick; Investitionsformulierung; Gap-Disziplin | Gl. (1)–(≈18), T2 (Parameter) |
| 3 | Case studies & experimental design | Zwei Netze als Endpunkte; Faktor-Design; Baseline-Definition | T1, F1 |
| 4 | **Results I — Sizing & geometry** | Speicher-Kostenkurve mit innerem Optimum (normiert auf Speicherstunden); Zerlegung CAPEX/Verlust/Arbitragewert; AR-Trade-off; WP-Kapazitätsoptimum | **F2**, T3 |
| 5 | **Results II — Heat-curve coupling** | COP↑ vs. Energiedichte↓ vs. Netzverluste↓ → Netto-TAC; optimale HK-Stufe je Elektrifizierungsgrad | **F3** |
| 6 | **Results III — Topology** | Siting-Landschaft; **aggregiert vs. nodal**: welche Auslegung empfiehlt ein Ein-Knoten-Modell und was kostet dieser Fehler | **F4**, **F5** |
| 7 | **Results IV — Conditions** | Elektrifizierungsgrad × Preis/EF-Ebene → Break-even-CO₂-Preis je Netz | **F6** |
| 8 | Discussion | Sensitivität, Übertragbarkeit, Limitationen (n=2, ein Wetterjahr, MIP-Gap, Modellversion) | **F7**, T4 |
| 9 | Conclusions | — | — |

**Element-Budget: 7 Abbildungen + 4 Tabellen = 11** (Limit 15). Supplement: SoC-Zyklen
(alt F9), Spatial T/p (alt F8, mit 20-bar-Caveat), Kapazitäts-Sweep-Kreuzvalidierung
(alt F3), Pumpenvergleich, vollständige KPI-Tabellen, ausgeschlossene Läufe.

### Abbildungen im Detail

- **F1 Netze** — 2 Panels, gemeinsame Legende, Erzeuger/WP-/TES-Kandidatenknoten markiert. *(du ersetzt gerade)*
- **F2 Speicherauslegung** — (a) TAC bzw. LCOH über Speicherstunden je Netz, mit innerem Optimum und Gap-Band; (b) Kostenzerlegung (CAPEX / Stillstandsverlust / eingesparte Erzeugungskosten) über derselben Achse. *Kernabbildung des Papers.*
- **F3 Heizkurven-Kopplung** — 3 Panels: COP(HK), nutzbare Energiedichte ΔT(HK), Netto-TAC(HK) mit Kurvenschar über Elektrifizierungsgrad. Zeigt, dass das HK-Optimum **nicht** die tiefste Stufe ist.
- **F4 Siting-Landschaft** — Heatmap HP×TES-Knoten, Optimum als Stern. **Statt „77× schlechtester Knoten": Verteilung (Median, P10/P90) + Aussage „x % der Kandidatenknoten liegen >y % über dem Optimum".**
- **F5 Aggregiert vs. nodal** — je Netz: (links) empfohlene Auslegung (WP-Größe, TES-Volumen, Standort) aus Ein-Knoten- vs. nodalem Modell; (rechts) reale Kosten dieser Auslegung, im nodalen Modell nachgerechnet → **Fehlentscheidungskosten in %**.
- **F6 Bedingungsraum** — je Netz Heatmap `c_CO2` × `c_el/c_gas` mit Break-even-Kontur (WP wirtschaftlich / nicht), Markierung des 2026-Punkts und zweier Politikszenarien (2030/2045 EF).
- **F7 Tornado (tier-2)** — Re-Dispatch, geteilte Farben, Wertelabels.

### Tabellen

- **T1** Netzkenndaten + Erzeugerportfolio (zusammengelegt).
- **T2** Modell- und Kostenparameter inkl. **Geometrieparameter** (U, k(AR), b, V_0, ΔT je HK-Stufe) mit Quellen.
- **T3** Headline-KPIs beider Netze, **inkl. Spalte `MIP gap [%]`** und Speicherstunden.
- **T4** Validierung: Energiebilanzschluss (**≤2 %**), COP-Plausibilität, Sweep-vs-MILP, Paper-1-Konsistenz (mit Preis-Harmonisierungsnotiz), **Modellversions-Invarianz**, Ein-Jahres-Disclosure.

---

## 4. Rechenkampagne

Alle Studien mit identisch definierten Faktoren in beiden Netzen. **Jede berichtete
Zahl trägt ihren MIP-Gap; innerhalb des Gaps wird nicht gerankt.**

| Studie | Zweck | Klasse | Läufe |
|---|---|---|---|
| **G — Sizing/Geometrie** | F2: TAC über V-Raster (bis inneres Optimum), je HK-Stufe, ΔT-gekoppelt | Dispatch (fix V) | 8 V × 3 HK × 2 Netze = **48** |
| **G2 — AR-Variation** | Geometrie-Trade-off | Dispatch | 3 AR × 2 Netze = **6** |
| **B — Heizkurve × Elektrifizierung** | F3 | Dispatch (fixes Design) | 3 HK × 4 Elektrifizierungsstufen × 2 = **24** |
| **C — Siting** | F4, Enumeration HP×TES | MILP | **61** |
| **N — aggregiert vs. nodal** | F5 | MILP + Nachrechnung | **6** |
| **P — Preis/EF-Ebene** | F6 | Dispatch, fixes und endogenes Design | 5×5 × 2 = **50** |
| **A — Elektrifizierungs-Sweep** | Eingang zu F6, SB-Tail sauber nachlösen | Dispatch | **18** |
| **E — Tornado tier-2** | F7 | Dispatch | **20** |
| **H — Headline-Matrix + Baselines** | T3 (gestrafft, **nicht** die alten 46 Zeilen) | MILP | **~20** |
| **I — Modellversions-Invarianz** | T4, `e8e445e` vs. `main` | MILP | **8** |

**≈260 Läufe, davon ~75 % Dispatch-Klasse** (Minuten, Gap ≤0,5 %). Das ist bewusst so
geschnitten: Alle *feinen* Aussagen (Geometrie, Heizkurve, Preisschwelle) liegen in
der Dispatch-Klasse und sind damit **gap-fest**; die Investitions-MILPs tragen nur die
groben Aussagen (Siting-Landschaft, Headline-Vergleiche), wo 1–4 % Gap unschädlich sind.

---

## 5. Blocker, die vor der Kampagne gelöst sein müssen

| # | Thema | Anforderung |
|---|---|---|
| B1 | **Modellversion** | Entscheidung `main` vs. `e8e445e` ist **keine Archivierungsfrage**: MM-S4 299k vs. 493k (+65 %) heißt, dass laterale Verluste + Druckphysik das Ergebnis materiell verschieben. **Empfehlung: auf `main` rechnen** (die bessere Physik ist verteidigbar, die schlechtere nicht) und `e8e445e` nur noch für die Invarianztabelle. Wenn Rechenzeit das verbietet: 8-Szenarien-Invarianztabelle als Mindestnachweis, dass die *Rangfolgen* halten. |
| B2 | **Energiebilanzschluss** | An der Quelle fixen (Σ stündlich `P_el·COP` als Wärmeoutput exportieren), Ziel **≤2 %**. Nicht verhandelbar — das ist der erste Wert, den ein Reviewer prüft. |
| B3 | **Baseline-Definition** | Baseline = identischer Erzeugerpark, **dispatch-optimiert**, keine Neuinvestition, gleiches Preisset. Sonst misst „+44,8 %" den Unterschied zwischen Optimierung und Ist-Fahrweise, nicht den Effekt von Speicher und Heizkurve. Die Zahl fällt sonst im Review. |
| B4 | **Gap-Disziplin** | Gap-Extraktion aus den Gurobi-Logs automatisieren; jede Vergleichsaussage prüft `|ΔTAC| > gap_1 + gap_2`, sonst „nicht unterscheidbar". |
| B5 | **ef_el** | Konstante 400 kg/MWh bei stündlichem Spotpreis ist inkonsistent → **stündlicher EF** als Default, konstanter EF als Sensitivität, 2030/2045-Szenarien in F6. Ohne das ist „Elektrifizierung senkt CO₂ nicht" nicht haltbar. |
| B6 | **Doc-Konsolidierung** | Diese Datei ist Source of Truth. `IMPLEMENTATION_PLAN.md`, `PUBLICATION_FIGURES.md`, `REVIEWER_PACKET.md` werden daraus neu abgeleitet, nicht parallel gepflegt (sie widersprechen sich aktuell in Finding #1). |

---

## 6. Was mit den bisherigen Ergebnissen passiert

| Bisher | Neue Rolle |
|---|---|
| F-ELEC (Elektrifizierungs-Sweep) | Wird **eine Achse** von F6, nicht mehr Centrepiece. Die Aussage „bei 2026-Preisen unwirtschaftlich" bleibt — aber als *ein Punkt* in der Break-even-Karte. |
| F4 alt („HK-Nutzen ist elektrifizierungsabhängig") | **Muss neu gerechnet werden.** Der Befund entstand ohne ΔT-Kopplung und ist damit modellseitig vorbestimmt. Mit Kopplung wird daraus die deutlich stärkere Aussage C2. |
| F6 alt (Siting) | Bleibt, wird zu F4 — aber mit Verteilungsstatistik statt Max/Min-Ratio, und mit Artefakt-Check (hängt der schlechteste Knoten am 20-bar-Deckel?). |
| F5 alt (Kosten/CO₂ vs. Baseline) | Ins Supplement, nach Baseline-Redefinition. |
| F3 alt (Kapazitätsfläche) | Wird durch F2 (Sizing-Kurve) ersetzt; die 2D-Fläche geht als Kreuzvalidierung ins Supplement. |
| F7, F8, F9 | Unverändert (F7 auf tier-2 heben). |
| „+44,8 % Memmingen" | Erst nach B3 wieder zitierfähig. |
| „77× schlechtestes Siting" | Erst nach Artefakt-Check; Berichterstattung als Verteilung. |

---

## 7. Zeitplan (realistisch)

| Meilenstein | Inhalt | Dauer |
|---|---|---|
| M1 | B1-Entscheidung, B2-Fix, B3-Baseline, Gap-Extraktion (B4) | 1 Woche |
| M2 | WP1/WP2: Geometriemodul + ΔT-Kopplung + Unit-Tests + Regressionsnachweis | 1–1,5 Wochen |
| M3 | Studien G, G2, B (Dispatch-Klasse) → F2, F3 | 1 Woche |
| M4 | Studien C, N → F4, F5 | 1 Woche |
| M5 | Studien P, A, E → F6, F7 | 1 Woche |
| M6 | H, I, Tabellen, Validierung | 0,5 Woche |
| M7 | Manuskript | 2–3 Wochen |

**≈8–9 Wochen bis Einreichung.** Der Ausbau in M2 ist die Investition, die das Paper
vom Fallstudienbericht zum Methodenbeitrag hebt — ohne ihn bleibt die
Speicherauslegung eine Randlösung und das Paper ein n=2-Preisexperiment.

## 8. Ehrliche Restrisiken

- **M2 macht alle bisherigen Zahlen ungültig.** Das ist gewollt, aber es heißt: keine
  Abbildung final bauen, bevor M2 steht.
- **SOS2-PWL erhöht die Binärzahl** in den Investitions-MILPs → Gap-Risiko. Mitigation:
  Die Sizing-Evidenz kommt aus der *parametrischen* Dispatch-Studie G; die PWL-Version
  muss diese nur reproduzieren, nicht tragen.
- **Die Break-even-Karte könnte zeigen, dass die WP erst bei unrealistischen Preisen
  kippt.** Auch das ist ein publizierbares Ergebnis — aber dann muss die Einleitung es
  von Anfang an als Forschungsfrage tragen, nicht als Überraschung am Ende.
- **Bleibt auch mit korrekter Geometrie kein inneres TES-Optimum**, ist das ein
  echtes Ergebnis („in Bestandsnetzen mit billiger, CO₂-armer Grundlast ist der Speicher
  nur so groß wie der Bauplatz") — dann aber explizit so schreiben, statt es als
  Auslegungskurve zu verkaufen.
