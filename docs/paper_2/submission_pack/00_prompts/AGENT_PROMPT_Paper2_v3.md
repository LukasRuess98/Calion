# CALION — Arbeitsauftrag Paper 2, Rework v3: Speichergeometrie, Heizkurvenkopplung, Topologie-Wert

**Technische Spezifikation für einen KI-Coding-Agenten**
Lukas Ruess | Fraunhofer IPA / EEP Universität Stuttgart | September 2026
Referenzdokumente: `PAPER2_ECM_PLAN_v3.md` (Source of Truth),
`CALION_Paper2_Implementation_Statement.md` (Teile A–I),
`CALION_Paper2_Sweep_und_Grafiken_Prompt_v2_final.md` (Grafik-Konventionen).

---

## 0. Rollendefinition und harte Regeln

Du baust **keine neue Physik nach Gutdünken** und triffst **keine wissenschaftlichen
Entscheidungen**. Du implementierst die unten spezifizierten Arbeitspakete, weist ihre
Korrektheit nach und lieferst Ergebnisse mit vollständiger Provenienz.

**Verbindliche Regeln:**

1. **Kein stillschweigender Parameterwechsel.** Jede Änderung an einem Config-Wert,
   Cap, Bound oder Solver-Setting wird in `CHANGELOG_v3.md` mit Vorher/Nachher,
   Begründung und Quelle protokolliert.
2. **Keine Zahl ohne MIP-Gap.** Jede exportierte KPI-Zeile trägt `mip_gap_pct`,
   `solver_status`, `solve_time_s`, `code_commit`, `config_hash`.
3. **Keine Aussage innerhalb des Gaps.** Vergleichsfunktionen geben
   `"indistinguishable"` zurück, wenn `|ΔTAC| ≤ gap_A·TAC_A + gap_B·TAC_B`.
4. **STOP-Punkte sind verbindlich.** Wo unten „⛔ STOP" steht, legst du das Ergebnis
   vor und wartest auf Freigabe, bevor du weiterbaust.
5. **Keine Grafik vor Freigabe der Datenbasis.** Erst Zahlen, dann Bilder.
6. **Alles reproduzierbar.** Jeder Lauf schreibt ein `run_manifest.json`
   (Commit, Config, Solver-Version, Seed, Laufzeit, Gap).
7. **Tests vor Kampagne.** Kein Studienlauf startet, bevor die Unit-/Regressionstests
   des jeweiligen Arbeitspakets grün sind.

---

## WP0 — Bestandsaufnahme und Entscheidungsgrundlagen

**Ziel:** Klären, was das Modell heute tatsächlich tut, bevor irgendetwas gebaut wird.

**Aufgaben**

1. **ΔT-Kopplung prüfen (kritisch):** Finde im Modellcode, wie die nutzbare
   Speicherenergie `E_max` aus dem Volumen berechnet wird. Beantworte präzise, mit
   Datei- und Zeilenangabe:
   - Hängt `E_max` von `T_supply − T_return` ab?
   - Ändert sich `E_max`, wenn die Heizkurvenstufe (HK0/1/2) wechselt?
   - Wie ist der Stillstandsverlust implementiert (`hourly_loss`)? Skaliert er mit
     dem Volumen oder mit einer Oberfläche?
2. **Cap-Herkunft:** Woher kommt `V_TES ≤ 5000 m³`? Config, Default oder
   hartkodiert? Gibt es eine begründende Quelle?
3. **Baseline-Definition:** Was genau rechnet `BC-MM` / `BC-SB`? Ist die Baseline
   dispatch-**optimiert** mit identischem Erzeugerpark und identischem Preisset, oder
   eine regelbasierte Ist-Fahrweise? Zeige die relevante Codestelle.
4. **Modellversions-Delta:** Liste die inhaltlichen Unterschiede zwischen `e8e445e`
   und aktuellem `main` (laterale Verluste, Druckphysik, weitere) als Tabelle:
   betroffene Gleichung, erwartete Wirkungsrichtung auf TAC.
5. **Emissionsfaktor:** Ist `ef_el` konstant oder als Zeitreihe verarbeitbar? Was wäre
   nötig, um eine stündliche EF-Zeitreihe einzuspeisen?

**Ergebnis:** `WP0_BEFUND.md` mit den fünf Antworten, jeweils mit Codereferenz.

⛔ **STOP.** Vorlage und Freigabe abwarten. Insbesondere Punkt 1 entscheidet über den
Umfang von WP2.

---

## WP1 — Speichergeometrie-Modul

**Ziel:** Speicherverluste und -kosten physikalisch korrekt an die Geometrie koppeln.

**Implementierung** (neues Modul `calion/model/storage_geometry.py`):

```python
def surface_factor(aspect_ratio: float) -> float:
    """k(AR) mit A = k(AR) * V**(2/3) für einen Zylinder mit AR = h/d."""
    return math.pi * (aspect_ratio + 0.5) * (4.0 / (math.pi * aspect_ratio)) ** (2/3)

def standing_loss_kw(volume_m3, aspect_ratio, u_value_w_m2k, t_tes_c, t_amb_c) -> float:
    """Q_loss = U * k(AR) * V^(2/3) * (T_TES - T_amb)"""

def capex_eur(volume_m3, c0_eur, v0_m3, exponent_b) -> float:
    """Degressive Kostenkurve C = c0 * (V/V0)**b."""
```

**Modellintegration**

- Der bisherige volumenproportionale Verlustterm (`hourly_loss * SoC`) wird
  **ersetzt**. Der alte Pfad bleibt über ein Config-Flag
  `storage.loss_model: {"proportional" | "geometric"}` erhalten, Default `geometric`.
- In der **Dispatch-Klasse** (V fix) ist `Q̇_loss` eine Konstante → keine neuen
  Binärvariablen.
- In der **Investitionsklasse** (V endogen) werden `V^(2/3)` und `C_inv(V)` als
  **SOS2-λ-PWL mit 6 Stützstellen** über `[0, V_max]` formuliert. Verwende ausdrücklich
  die λ-Formulierung mit SOS2, nicht eine Sekantennäherung — die Funktionen sind konkav
  und erscheinen mit positivem Vorzeichen in einer Minimierung, eine naive PWL wäre
  nicht exakt.
- Parameter in `configs/paper_2/storage_geometry.yaml`, mit Quellenkommentar je Wert:
  `u_value_w_m2k` (Vorschlag 0.15–0.30, Quelle nennen), `aspect_ratio` (Default 2.0),
  `t_tes_mean_c`, `t_amb_c` (Zeitreihe oder Jahresmittel — begründen),
  `c0_eur`, `v0_m3`, `exponent_b` (Vorschlag 0.6–0.7, DEA Technology Data zitieren).

**Cap:** `V_TES_max` von 5.000 auf **50.000 m³** anheben (Config, nicht hartkodiert).
Falls für Stadtbach ein physikalisches Platzlimit existiert, als separate,
kommentierte Nebenbedingung führen.

**Akzeptanzkriterien**

- `surface_factor` minimiert bei `AR = 1` (numerisch prüfen), `k(2)/k(1) ≈ 1.05`.
- Unit-Test: Verdopplung von V erhöht die Oberfläche um Faktor `2^(2/3) ≈ 1.587`.
- Regressionstest: mit `loss_model: proportional` und altem Cap reproduziert das
  Modell die alten Ergebnisse **bitgenau** (Toleranz 0,1 % TAC).
- Ein Testlauf mit `geometric` zeigt: Verlust pro m³ sinkt mit steigendem Volumen.

---

## WP2 — Heizkurvenkopplung der Speicherkapazität

**Ziel:** Die im Projekt ursprünglich geplante Kopplung Heizkurve ↔ Speicher herstellen.

```
E_max(V, HK) = rho * c_p * V * (T_sup(HK) - T_ret) * eta_strat
```

- `T_sup(HK)` kommt aus der bestehenden Heizkurvenlogik; `T_ret` aus der Config
  (falls ebenfalls HK-abhängig: dokumentieren und beide Effekte trennen).
- `eta_strat` (Default 0.85, Quelle nennen) als Config-Parameter.
- Gilt für **beide** Klassen (Dispatch und Investition). In der Dispatch-Klasse ist
  `E_max` eine Konstante pro Lauf.
- Achtung: Auch die maximale **Lade-/Entladeleistung** kann ΔT-abhängig sein
  (`P_max = ṁ_max · c_p · ΔT`). Prüfen, ob das im Modell vorhanden ist, und falls ja,
  konsistent an dieselbe ΔT-Definition hängen. Falls nein: in `WP2_BEFUND.md`
  vermerken, **nicht** eigenmächtig hinzufügen.

**Akzeptanzkriterien**

- Unit-Test: `E_max` sinkt proportional zu ΔT; −5 K bei 40 K Basis-Spreizung ergibt
  −12,5 % Kapazität.
- Integrationstest: Ein Szenario mit HK2 (tiefere Kurve) zeigt gegenüber HK0 einen
  **höheren COP und eine geringere nutzbare Speicherenergie** bei gleichem V.
  Beide Effekte müssen im Log sichtbar sein.

⛔ **STOP** nach WP1+WP2: Lege einen Kurzbericht mit einem Beispielnetz vor
(TAC, COP, E_max, Q̇_loss je HK-Stufe, alt vs. neu). Erst nach Freigabe Kampagne.

---

## WP3 — Datenqualität (Blocker aus dem QC-Review)

1. **Energiebilanzschluss an der Quelle:** Im Extraktor die **Wärmeabgabe** der
   WP exportieren (`Σ_t P_el(t) · COP(t)`), nicht die elektrische Leistung.
   `validation.json` muss danach `closure_error_pct ≤ 2 %` im Median über alle Läufe
   zeigen. Bestehende `closure_error_pct_heat`-Nachkorrektur entfernen.
2. **Baseline:** Baseline-Läufe so konfigurieren, dass sie denselben Erzeugerpark,
   dasselbe Preisset und **dispatch-optimiert** ohne Neuinvestition rechnen. In
   `BASELINE_DEFINITION.md` in einem Absatz dokumentieren, was die Baseline ist und
   was sie **nicht** ist.
3. **Gap-Extraktion:** Gurobi-Logs parsen → `mip_gap_pct`, `solver_status`,
   `nodes_explored`, `solve_time_s` in jede KPI-Zeile.
4. **`_is_diagnostic()`-Guard** aus der KPI-Berechnung beibehalten und mit einem Test
   absichern (Diagnoseläufe dürfen nie als Baseline gezogen werden).
5. **Stündlicher Emissionsfaktor:** `ef_el` als Zeitreihe einlesbar machen
   (Default weiterhin konstant 400 kg/MWh, aber überschreibbar). Quelle der Zeitreihe
   vom Auftraggeber erfragen — **nicht selbst beschaffen**.

---

## WP4 — Modellversion und Invarianz

1. `e8e445e` als Git-Tag `paper2-campaign-v1` sichern.
2. **Kanonische Basis für die neue Kampagne ist `main`** (bessere Physik), sofern die
   Laufzeiten es zulassen. Prüfe an drei Szenarien, ob `main` in vertretbarer Zeit
   löst; berichte Laufzeit und Gap.
3. **Invarianztabelle** (`T4`-Bestandteil): 8 Szenarien (Baseline je Netz, bestes
   Design je Netz, zwei Elektrifizierungsstufen, Siting-Optimum und schlechtester
   Siting-Knoten) auf **beiden** Codeständen. Ausgabe: TAC, LCOH, CO₂, **und die
   Rangfolge**. Die Kernaussage der Tabelle ist nicht die absolute Differenz, sondern
   ob sich Rangfolgen drehen.

⛔ **STOP.** Wenn sich in der Invarianztabelle eine Rangfolge dreht, sofort melden —
das ist ein inhaltlicher Befund, kein technisches Detail.

---

## WP5 — Rechenkampagne

Alle Studien mit identischen Faktordefinitionen in beiden Netzen. Ergebnisse nach
`03_data/<studie>_<netz>.csv` mit vollständigen Metadatenspalten.

| Studie | Beschreibung | Klasse | Läufe |
|---|---|---|---|
| **G** | `V_TES` auf Raster {0, 250, 500, 1k, 2k, 5k, 10k, 20k, 50k m³} (netzspezifisch skaliert), × HK{0,1,2}, Siting am Optimum fix, WP-Kapazität fix | Dispatch | 2×3×9 = 54 |
| **G2** | `AR ∈ {1, 2, 4}` am Optimalvolumen | Dispatch | 6 |
| **B** | HK{0,1,2} × Elektrifizierungsgrad {0, 25, 50, 100 % des jeweiligen Optimums} | Dispatch | 24 |
| **C** | Vollenumeration HP×TES-Kandidatenknoten bei HK-Optimum | MILP | 61 |
| **N** | Aggregiertes Ein-Knoten-Modell je Netz (gleiche Erzeuger, gleiche Last, keine Topologie) → Auslegung ableiten → **diese Auslegung im nodalen Modell fixieren und nachrechnen** → Kostendifferenz zum nodalen Optimum | MILP + Dispatch | 6 |
| **P** | Raster `c_CO2 ∈ {0,50,100,200,300 €/t}` × `c_el/c_gas`-Verhältnis (5 Stufen) | Dispatch | 50 |
| **A** | Elektrifizierungs-Sweep, Stadtbach-Tail (60–100 %) sauber nachlösen | Dispatch | 18 |
| **E** | Tornado tier-2 (Re-Dispatch je Parametervariante) | Dispatch | 20 |
| **H** | Gestraffte Headline-Matrix + Baselines (**nicht** die alten 46 Zeilen) | MILP | ~20 |

**Hinweise zu Studie N (wichtigster neuer Baustein):**
Das aggregierte Modell muss ein *fairer* Vergleich sein — identische Erzeuger,
identische Lastsumme, identische Preise, nur ohne Netztopologie (ein Knoten, keine
Rohrverluste bzw. pauschaler Verlustaufschlag). Dokumentiere die Aggregationsregel
explizit in `AGGREGATION_RULE.md`. Ausgabe je Netz: empfohlene WP-Kapazität,
TES-Volumen, (kein Standort) — und die im nodalen Modell nachgerechneten realen Kosten
dieser Auslegung gegenüber dem nodalen Optimum, als **Fehlentscheidungskosten in %**.

---

## WP6 — Abbildungen und Tabellen

Konventionen unverändert: Memmingen = FHG-Blau, Stadtbach = FHG-Grün,
Kostenkomponenten = Paper-1-Palette (navy/teal/amber), Temperatur = rot.
Matplotlib, statisch, PDF+SVG+PNG, els-cas Doppelspalte, englische Beschriftungen.

| Element | Inhalt | Datenquelle |
|---|---|---|
| **F1** | Netzkarten, 2 Panels, gemeinsame Legende | vom Auftraggeber geliefert |
| **F2** | (a) TAC/LCOH über **Speicherstunden** (`E_max/Peak`) je Netz, inneres Optimum markiert, Gap-Band; (b) Kostenzerlegung CAPEX / Stillstandsverlust / eingesparte Erzeugungskosten | Studie G |
| **F3** | 3 Panels: COP(HK), nutzbare Energiedichte(HK), Netto-TAC(HK) als Kurvenschar über Elektrifizierungsgrad | Studien B, G |
| **F4** | Siting-Heatmap HP×TES, Optimum als Stern. **Titel nennt Median und P90 der Mehrkosten, nicht das Maximum.** Zusätzlich Artefakt-Check: markiere Knoten, die an einer Druck- oder Kapazitätsgrenze hängen | Studie C |
| **F5** | Aggregiert vs. nodal: (links) empfohlene Auslegung, (rechts) Fehlentscheidungskosten in % | Studie N |
| **F6** | Heatmap `c_CO2` × Preisverhältnis mit **Break-even-Kontur**, 2026-Punkt markiert | Studie P |
| **F7** | Tornado tier-2 | Studie E |
| **T1** | Netzkenndaten + Erzeugerportfolio | Configs |
| **T2** | Modell-/Kostenparameter **inkl. Geometrie** (U, AR, b, V0, ΔT je HK), jede Zeile mit Quelle | Configs |
| **T3** | Headline-KPIs beider Netze, Spalten inkl. `MIP gap [%]`, `V_TES [m³]`, `Speicherstunden [h]` | Studie H |
| **T4** | Validierung: Bilanzschluss, COP-Band, Sweep-vs-MILP, Paper-1-Konsistenz, **Modellversions-Invarianz**, Ein-Jahres-Disclosure | WP3, WP4 |

Supplement: SoC-Zyklen, Spatial T/p (mit 20-bar-Caveat in der Caption),
2D-Kapazitätsfläche als Kreuzvalidierung, Pumpenvergleich, vollständige KPI-Tabellen,
Liste ausgeschlossener Läufe.

**Jede Caption nennt:** Szenario, Heizkurvenstufe, Siting, MIP-Gap, Codestand.

---

## WP7 — Reproduzierbarkeitspaket

- `submission_pack/REPRODUCE.md`: Ein Befehl pro Abbildung, vom Rohlauf bis zur PDF.
- `environment.yml` / `requirements.txt` mit gepinnten Versionen inkl. Gurobi.
- `PROVENANCE_v3.md`: Abbildung → Skript → Datendatei → Lauf-IDs → Commit.
- Alle Configs der Kampagne unter `configs/paper_2/v3/` eingecheckt.

---

## Reihenfolge und Abbruchbedingungen

```
WP0 ──⛔── WP1 ─ WP2 ──⛔── WP3 ─ WP4 ──⛔── WP5 ─ WP6 ─ WP7
```

**Melde sofort und stoppe, wenn:**
- die ΔT-Kopplung bereits existiert (dann ist der F4-Altbefund echt und WP2 entfällt —
  aber die Interpretation ändert sich, das ist eine Autorenentscheidung);
- nach WP1/WP2 in **keinem** der beiden Netze ein inneres Speicheroptimum entsteht
  (auch bei 50.000 m³ Cap) — das ist ein Ergebnis, kein Fehler, muss aber besprochen
  werden, bevor Abbildungen gebaut werden;
- sich in der Invarianztabelle eine Rangfolge dreht;
- ein Studienlauf systematisch am Zeitlimit hängt (nicht einfach das Limit erhöhen —
  melden, mit Gap-Verlauf).

**Nicht tun, auch wenn es naheliegt:** repräsentative Typtage implementieren
(separates Feature, bewusst zurückgestellt); Zeitauflösung vergröbern (nachweislich
verzerrend: 2 h → −11,7 % TAC); Parameter „plausibel machen"; Läufe aus dem Ergebnis
entfernen, ohne sie in der Ausschlussliste zu dokumentieren.
