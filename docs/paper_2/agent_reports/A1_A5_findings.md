# A1 + A5 — Befunde (Lukas-Session, 2026-10-22, selbst bearbeitet nach Rate-Limit-Ausfall des Recherche-Agents)

## A1 — MONTHLY-Mechanismus verifizieren

### A1a — Ist der Monatsleistungspreis im freien Modell strukturell aktiv?
Antwort: **JA, zweifelsfrei.** `model_finalizer.py:667` prüft `grid.demand_charge_mode=='monthly'`; wenn aktiv, baut
`constraint_builder.py:1073-1083` ECHTE zusätzliche Pyomo-Objekte: `model.P_buy_peak_month` (1 Var je Kalendermonat,
12 Stück) + `model.peak_con_month` (1 Constraint je (Monat,Stunde)-Paar, 8.760 Stück bei Stundenauflösung). Exakter
Beleg per Build-only-Diff: `SB-S1-HK0-MONTHLY` hat `n_vars=7.358.434` = normales `SB-S1-HK0`s `7.358.422` **+12**
(exakt die 12 Monats-Peak-Variablen), `n_constraints=9.233.051` = `9.224.291` **+8.760** (exakt die Monats-Stunden-
Paare) — die Differenzen treffen die Code-Struktur bis auf die letzte Stelle.
Evidenz: `calion/models/constraint_builder.py:1073-1083`, `calion/models/model_finalizer.py:667-675,741-747`,
`output/_z3/sb_free_monthly/paper2_runs/SB-S1-HK0-MONTHLY/meta.json` (n_vars/n_constraints) vs.
`output/v7_final/SB-S1-HK0/meta.json`.
Status: belegt

### A1b — Gurobi-Log: MIP-Start, Inkumbentenverlauf
Antwort: `Loaded user MIP start with objective 2.3172e+07` (Zeile 45) und `Solution count 1: 2.3172e+07` (Zeile 550,
`Time limit reached`) — **Start- und Endwert sind identisch**, der Lauf hat die vollen 8h (29.464,98s) NIE eine
verbesserte Lösung gefunden. Das beantwortet H1 direkt: SB-MONTHLY ist trotz ECHTER monatlicher Constraint-Struktur
(A1a) NIE unter genuinen monatlichen Anreizen neu optimiert worden — er hat nur den (jährlich-optimierten)
Warmstart aus `v7_final/SB-S1-HK0` geerbt und nie verlassen.
Evidenz: `output/_z3/sb_free_monthly/logs/gurobi_SB-S1-HK0-MONTHLY.log:45,550,552`.
Status: belegt

### A1c — Code-Pfad von `cost_demand_charge_eur`; jährlich oder monatlich aggregiert?
Antwort: `calion/run/result_collector.py:1363-1381`: wenn `model` verfügbar, wird `demand_cost =
float(_diag_demand_cost_expr)` verwendet — das ist `model.demand_cost_expr`, eine Pyomo-Expression, die in
`model_finalizer.py:743-747` je nach `demand_charge_mode` auf `calculate_demand_charge_monthly(...)` ODER die
jährliche Formel geschaltet wird; d.h. **der reportierte Wert reflektiert korrekt, welcher Modus tatsächlich gebaut
wurde** — ABER er ist nutzlos als unabhängiger Beleg, solange der Dispatch selbst nie neu optimiert wurde (A1b).
ZUSÄTZLICH berechnet `result_collector.py:1385-1411` unabhängig davon IMMER (nicht modusgebunden) eine
Diagnose-Kennzahl (`Demand_charge_annual_billing_EUR` vs. `Demand_charge_monthly_billing_EUR_equiv_rate`), rein aus
der Dispatch-Zeitreihe `pbuy_series` — diese Diagnose würde selbst bei einem ANNUAL-Modus-Lauf ein monatliches
Äquivalent ausrechnen, ist aber nicht das, was die MONTHLY-Läufe berichten.
Evidenz: `calion/run/result_collector.py:1363-1411`, `calion/models/model_finalizer.py:741-754`.
Status: belegt

### A1d — Herkunft von `peak_import_MW = 1,0`
Antwort: **NICHT bestätigt mit den geprüften Dateien.** `output/_z3/sb_free_monthly/paper2_runs/SB-S1-HK0-MONTHLY/economics.csv`
zeigt `peak_import_MW=0,4120841196738621` — IDENTISCH (auf viele Dezimalstellen) zum normalen `SB-S1-HK0`-Lauf, NICHT
`1,0`. Es gibt einen GETRENNTEN Export-Pfad (`calion/io/publication_exporter.py:635`: `kpis["grid"]["peak_import_MW"]
= grid.get("peak_import_MW")`), der aus einer anderen `grid`-Sektion liest — diese Datei wurde für den MONTHLY-Lauf
NICHT lokalisiert/geprüft (kein `kpis.json` o.ä. im Laufordner gefunden). H2s konkrete Zahlenangabe (`1,0000`) konnte
ich NICHT reproduzieren.
Status: vermutet, dass H2 sich auf eine andere, nicht lokalisierte Datei bezieht — die ÖKONOMISCH RELEVANTE
Behauptung dahinter (dass der berichtete Spitzenwert in MONTHLY-Läufen ein von der echten Dispatch-Zeitreihe
losgelöster Platzhalter sein könnte) bleibt daher UNBESTÄTIGT, nicht widerlegt.
Offen: Datei/Feld mit echtem Wert `1,0` nicht gefunden — bräuchte eine gezielte Nachfrage an den Auftraggeber, WELCHE
Datei er meint.

### Fazit A1
**SB-MONTHLY ist als eigenständiges Ergebnis NICHT gültig.** Die monatliche Lastspitzen-Logik ist strukturell real
im Modell vorhanden (A1a — keine reine Attrappe), aber der konkrete Lauf wurde nie unter ihrem Einfluss neu gelöst
(A1b, `Solution count 1`, Start=Endwert). Der nahezu identische Gesamtzielwert (23.172.019,514568 vs. ...514733,
Differenz 0,000165 EUR) ist dadurch vollständig erklärt — er beweist NICHTS über die tatsächliche Kostenwirkung
monatlicher Abrechnung, weder dass sie klein ist noch dass sie groß wäre. **Empfehlung:** entspricht exakt Teil-D-
Punkt D1 im Auftrag (`[ ]`, nicht gestartet) — Re-Solve mit PIN0-MONTHLY-Dump-Warmstart + `SEED_FILL_ZERO=1`, damit
der Solver nicht am alten (ANNUAL-optimalen) Dispatch-Muster klebt.

---

## A5 — Logging-Bug und Reporting

### A5a — Ursache in `calion/run/design_helpers.py` / `result_collector.py` (ZWEI Fundstellen, identisches Bug-Muster)

**Root Cause (belegt, Code gelesen):** `calion/run/result_collector.py:1296-1314` (und eine fast identische Kopie
in der höherstufigen Design-Fixierungs-Logik `calion/run/design_helpers.py:37-47`, die vermutlich DIESEN bereits
falschen `summary`-Wert weiterverarbeitet, nicht selbst neu einen Fehler einführt) liest die TES-Kapazität über:
```python
cap_e_var = getattr(model, "TES_cap_energy", None)
cap_p_var = getattr(model, "TES_cap_power", None)
build_var = getattr(model, "TES_build", None)
```
Diese generischen Attributnamen (`TES_cap_energy`, `TES_cap_power`, `TES_build`) existieren NUR im ALTEN,
generischen (Ein-Tank-)Storage-Modell. Die AKTUELL verwendete, komponentenbasierte `geometric_storage.py`
(AC1/AC2-Refactor) benennt ihre Pyomo-Variablen component-spezifisch (z.B. `tes_sb`-Präfix), NICHT
`TES_cap_energy`/`TES_cap_power`/`TES_build`. `getattr(..., None)` liefert daher `None`, der `if cap_e_var is not
None:`-Block wird übersprungen, und der Code fällt auf den Fallback aus Zeile 1293-1294 zurück:
`meta["storage"].get("e_cap_init", meta["storage"]["e_max"])` — wenn DIESER Metadaten-Defaultwert ebenfalls 0 ist
(was für den geometrischen Storage-Typ offenbar der Fall ist, da er diese Felder anders befüllt), bleibt
`energy_cap=0`, `power_cap=0`, und `build_val = 1.0 if energy_cap > 0 else 0.0` wird fälschlich `0.0`.
Status: belegt (Codepfad gelesen und Variablennamen-Mismatch identifiziert — NICHT durch Ausführung/Debugger
verifiziert, daher "belegt" im Sinne von Code-Lektüre, nicht Laufzeit-Trace)

### A5b — Wer konsumiert den fehlerhaften Wert außer dem Log?
Antwort: Der falsche `energy_cap`/`power_cap`/`build_val` wird in `storage_section["Capacity_MWh"]`,
`["Power_limit_MW"]`, `["Build_binary"]` geschrieben (`result_collector.py:1320-1322`) und landet darüber in
`summary_sections[f"storage_{name}"]`, die am Ende via `_flatten_summary(summary_sections)` zu `flat` werden
(`result_collector.py:1564-1565`). **WICHTIG, gute Nachricht:** Die tatsächlich für das Paper verwendeten Artefakte
— `geometry.csv` (über `design_helpers`' EIGENE, direkte Geometrie-Variablen-Extraktion, nicht über diesen
`summary`-Pfad) UND `cost_breakdown.json` (CAPEX-Werte, separat berechnet) — zeigen BEIDE die KORREKTEN Werte (siehe
A2/A3-Nachweise: `geometry.csv` build=1, 438 MWh, exakt). Das heißt: **dieser Bug hat (soweit geprüft) KEINEN
Einfluss auf die im Paper zitierten Zahlen** — er verschmutzt nur das Logfile UND (vermutlich) irgendeine
`flat`-Export-Datei, deren genauer Dateiname/Pfad ich NICHT lokalisieren konnte (kein offensichtlicher
`summary.json`/`kpis.json` im Laufordner mit diesem Inhalt gefunden).
Status: belegt (die guten Dateien sind sauber) / offen (wohin genau `flat` geschrieben wird, nicht gefunden —
Aufwand für vollständige Klärung: klein, ein `grep -rn "_flatten_summary\|return series, summary_sections, flat"`
weiterverfolgen bis zum Dateischreiber).

### A5c — Existiert eine Konsistenzprüfung? Fixvorschlag.
Antwort: Keine Konsistenzprüfung gefunden. **Fixvorschlag:** In `result_collector.py:1296-1299` die `getattr`-Ziele
auf die ECHTEN, komponentenspezifischen Pyomo-Variablennamen ändern (z.B. über `meta["storage"]["name"]` dynamisch
`getattr(model, f"{name}_V_m3")`-artige Lookups statt hartcodierter generischer Namen — exakte Variablennamen müsste
man in `geometric_storage.py` nachschlagen, nicht Teil dieser Analyse). Aufwand: **klein bis mittel** (richtige
Variablennamen finden + beide Fundstellen patchen + Regressionstest gegen ein bekanntes `geometry.csv` eines echten
TES-Laufs).
Status: vermutet (Fixvorschlag, kein Code geändert — Teil-A ist reines Lesen)

### A5d — Weitere dokumentierte Defekte seit 2026-10-02?
Antwort: `MODEL_AND_DOE_CONTROL.md` endet NICHT bei §4cj (06.10.), wie der Auftrag (§0) annimmt — es geht bis
**§4cr (2026-10-22, HEUTE)**. Relevante, bisher dem Auftraggeber unbekannte Abschnitte: §4ck (c0-Sweep-Vorbehalt zu
×1,3/1,5, bereits dokumentiert — siehe A3-Korrektur in `A2_A3_findings.md`), §4cq/§4cr (AC-Block: TES-Leistung jetzt
bepreist+endogen, Geometrie-Defaults GEÄNDERT). **Kritische neue Information für Reproduzierbarkeit (E3-relevant):**
§4cr dokumentiert, dass die "Altmodell-Reproduktion" JETZT **fünf** Env-Variablen braucht
(`CALION_TES_POWER_CAPEX=0 CALION_TES_HMAX=0 CALION_TES_RHD=2.0 CALION_TES_P2E_HOURS=4 CALION_TES_POWER_MAX=0`),
nicht mehr nur zwei (`CALION_TES_POWER_CAPEX=0 CALION_TES_HMAX=0`, wie noch bei meinen eigenen, VORHER (20./21.10.)
gelaufenen Stage-2-Completion-Läufen c0×0,5/0,7 ausreichend). Diese Läufe bleiben für IHREN Zeitpunkt gültig (zum
Laufzeitpunkt waren `r_hd`/E-P-ratio-Defaults noch die alten), sind aber mit der HEUTIGEN Codebasis NICHT mehr mit
nur zwei Env-Vars reproduzierbar — relevant für B4/E3s "Reproduzierbarkeits"-Spalten.
Status: belegt

## Zusammenfassung A1+A5
A1: SB-MONTHLY ist ein Stuck-Warmstart-Artefakt trotz strukturell echter Monats-Constraints — nicht verwertbar ohne
D1-Re-Solve. A5: Der Logging-Bug ist ein klarer, lokalisierter Variablennamen-Mismatch zwischen altem und neuem
Storage-Modell (`result_collector.py:1296-1299`), betrifft NACHWEISLICH NICHT die im Paper zitierten Werte
(`geometry.csv`/`cost_breakdown.json` sind über einen anderen, korrekten Pfad erzeugt), aber vermutlich eine
namenlose `flat`-Exportdatei. Wichtigster Nebenbefund: die Codebasis hat sich HEUTE (§4cr) so verändert, dass die
Altmodell-Reproduktionsrezeptur von 2 auf 5 Env-Variablen gewachsen ist — alle VOR heute gelaufenen "Altmodell"-Läufe
(inkl. meiner eigenen Stage-2-Completion c0×0,5/0,7) bleiben gültig, sind aber mit der aktuellen Codebasis nicht mehr
1:1 mit der alten 2-Var-Rezeptur reproduzierbar.
