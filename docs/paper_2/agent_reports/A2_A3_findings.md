# A2 + A3 — Befunde (Lukas-Session, 2026-10-22)

## A2 — Standortunterschied S1 vs. S2/S3

### A2a — Solution count, Inkumbentenverlauf, Warmstartquelle, Gap-Verlauf (Stage-2-Läufe)
Antwort: Beide Stage-2-Re-Solves (`SB-S2-HK0`, `SB-S3-HK0`) liefen als **saubere Einzelläufe ohne Neustart** über die
volle 8h-TimeLimit, mit **echter B&B-Exploration**: Gurobi-Log zeigt `Solution count 10` für beide (NICHT `1`, wie
`meta.json` fälschlich berichtet — siehe Meldepflicht unten). Warmstartquelle: PIN0-Dump (`CALION_WARMSTART_DUMP` +
`CALION_SEED_FILL_ZERO=1`), erkennbar an `"0 size one-hot(s) -> zero rung (TES no-build state)"` — der Dump trug
selbst keinen Standort-State, war also für j_man-Siting-Fragen unverzerrt.
Evidenz: `output/_s2/sb_s2_resolve2/logs/gurobi_SB-S2-HK0.log:445` (`Solution count 10: 2.3319e+07 ...`),
`output/_s2/sb_s3_resolve/logs/gurobi_SB-S3-HK0.log:504` (`Solution count 10: 2.33169e+07 ...`),
`output/_s2/sb_s2_resolve2/chain.output:616` (`[SEED-DUMP] inheritance fill-zero: 236521 unset vars -> 0, 0 size
one-hot(s) -> zero rung`), Endgaps: S2=0,1867% (`meta.json: mip_gap=0.001866558...`), S3=0,1772%
(`meta.json: mip_gap=0.0017715528...`).
Status: belegt
Offen: -

**Meldepflicht A2-M2 (neu):** `meta.json`-Feld `solution_count` ist bei S2 und S3 falsch (zeigt `1`, echtes Gurobi-Log
zeigt `10`). Das ist ein ZWEITER, von A5s Design-Helpers-Bug UNABHÄNGIGER Extraktions-Bug (vermutlich in
`scenario_runner.py`s meta.json-Writer — las vermutlich ein falsches Solver-Attribut oder einen Default-Wert statt
`model.solution_count` vom Solver). Betrifft mindestens B4 (Konvergenz-Tabelle) — dort wird `solution_count` nicht aus
`meta.json`, sondern aus dem echten Gurobi-Log übernommen (an die B3/B4-Agent-Session weitergegeben).
Fixvorschlag: in `scenario_runner.py` suchen, wo `meta.json["solution_count"]` gesetzt wird, und gegen
`results.solver.statistics` bzw. das Gurobi-Modellattribut `SolCount` validieren. Aufwand: klein (vermutlich 1 Zeile).

### A2b — Build-only-Diff S1 vs. S2 (n_vars/n_constraints); physikalische Anschließbarkeit j_man
Antwort: `n_vars`/`n_constraints` von S1 und S2 sind **bit-identisch** (7.358.422 / 9.224.291) — das Modell ist an
j_man STRUKTURELL genauso aufgebaut wie an j_hkw (gleiche TES-Geometrie-Bounds, siehe Log unten), kein
Blockierungs-Constraint fehlt. S3 hat 8.760 zusätzliche Variablen/Constraints (durch den Hot-Charging-Block, ein
Constraint je Zeitschritt). Das bestätigt wörtlich den bereits in Stage 1 (`REPORT_Klaerung_2026-10-19.md:181-189`,
Commit `2d2cce2` auf `main`) belegten Befund — hier erneut direkt nachgeprüft, nicht nur zitiert.
Evidenz: `output/_s2/sb_s2_resolve2/paper2_runs/SB-S2-HK0/meta.json` (n_vars=7358422, n_constraints=9224291),
`output/_s2/sb_s3_resolve/paper2_runs/SB-S3-HK0/meta.json` (n_vars=7367182, n_constraints=9233051),
`output/_s2/sb_s2_resolve2/chain.output:~29` (`[TES-GEOM] tes_sb: geometry VERIFIED against storage_geometry.yaml
(r_hd=2.00, p_max_bar=5.5, V_max_m3=250000, unit_tank_m3=50000.0)` — identisch zu S1s Log-Zeile).
Status: belegt

**Physikalische Anschließbarkeit — KORRIGIERTE Rechnung (Stage-1-Schätzung präzisiert):** Stage 1 hatte den
Rohrquerschnitt und Massenstrom per Hand aus Durchmesser+Geschwindigkeit geschätzt (→ 366,1 kg/s, ≈53,7 MW). Die
ECHTE, modellseitig berechnete Grenze steht direkt in `pipes.csv`: `hkw_to_man`: `m_dot_max_kg_s=333,109`,
`v_max_m_s=3.0`, `diameter_mm=400`. Mit c_p,Wasser=4,186 kJ/(kg·K):
- bei ΔT=15K (Netz-Standard, T_VL_min=75°C/T_return=60°C): Q_max ≈ 333,109 × 4,186 × 15 / 1000 ≈ **20,9 MW**
- bei ΔT=35K (TES-Hot-Charge-Spreizung, siehe S3-Log): Q_max ≈ 333,109 × 4,186 × 35 / 1000 ≈ **48,8 MW**
Evidenz: `output/_s2/sb_s2_resolve2/paper2_runs/SB-S2-HK0/pipes.csv` Zeile `hkw_to_man` (`m_dot_max_kg_s=333.10935...`,
`v_max_m_s=3.0`), `configs/paper_2/Stadtbach_topo.yaml:345-351` (`hkw_to_man: from: j_hkw, to: j_man,
diameter_mm: 400`).
Status: berechnet (Formel + reale Pipe-Parameter, kein neuer Solve nötig)

Fazit (berechnet): S1s TES hat `cap_power_MW=109,5` — selbst im GÜNSTIGSTEN Fall (ΔT=35K, 48,8 MW) trägt die einzige
Leitung nach j_man **weniger als die Hälfte** der S1-Kapazität, im realistischeren Netz-ΔT-Fall (15K) sogar nur **ein
Fünftel**. Das ist eine STRENGERE Grenze als Stage-1s Schätzung (53,7 MW) — der ursprüngliche Befund "j_man ist
strukturell limitiert" wird durch die exakten Werte nicht entkräftet, sondern bestätigt und verschärft.

### A2c — Warum ist S3 (Hot-Charging) ohne gebauten Tank wirkungslos?
Antwort: Hot-Charging ist ein Lademodus FÜR einen Speicher (höhere Ladetemperatur über COP-Abschlag, siehe
`output/_s2/sb_s3_resolve/chain.output`: `"HOT CHARGING: T_charge=95.0 degC, TES dT=35.0 K, COP_hot mean=3.01 (vs net
3.26)"`). Wenn der Speicher selbst mit `build=0` nicht gebaut wird, hat der Hot-Charging-Mechanismus keinen Lastträger
— die 8.760 zusätzlichen Constraints sind dann strukturell vorhanden, aber ökonomisch irrelevant (sie binden nur,
wenn `tes_sb` Kapazität > 0 hat). Da S3 (wie S2) am selben j_man-Standort sitzt und derselben Pipe-Kapazitätsgrenze
unterliegt (A2b), erübrigt sich die Frage "lohnt sich Hot-Charging dort" bereits auf der vorgelagerten
Standortentscheidung.
Evidenz: `output/_s2/sb_s3_resolve/paper2_runs/SB-S3-HK0/geometry.csv` (`build=0`), obiges Logzitat.
Status: belegt + berechnet (logische Folgerung aus A2b)
Offen: Nicht geprüft, ob Hot-Charging an einem ANDEREN (pipe-unlimitierten) Standort einen eigenständigen Zusatznutzen
über reines Cold-Charging hinaus hätte — das wäre eine neue Fragestellung, nicht Teil dieses Auftrags.

### A2d — HP/EK-Größen und Standorte: S1 vs. S2/S3
Antwort: S1 baut `hp_sb` auf **2,51 MW** (Spitzendispatch 2,5058 MW), S2 auf **1,84 MW** (1,8396 MW), S3 auf
**1,85 MW** (1,8481 MW) — S2/S3 bauen eine KLEINERE Wärmepumpe als S1, nicht dieselbe. Alle übrigen (nicht
investierbaren) Erzeuger (`AVA_FEED`, `BMHKW`, `GTOST`, `HKW`, `HWS_BOILER`, `HWW_BOILER`) zeigen in S1/S2/S3
IDENTISCHE Spitzenwerte (45,0 / 14,5 / 35,0 / 127,0 / 25,3479 / 41,4853 MW) — korrekt, da fix/nicht-investierbar,
unabhängig vom TES-Standort.
Evidenz: `output/{v7_final/SB-S1-HK0,_s2/sb_s2_resolve2/paper2_runs/SB-S2-HK0,_s2/sb_s3_resolve/paper2_runs/SB-S3-HK0}/dispatch_per_asset.csv`
(Spaltenmaxima `hp_sb_MW`).
Status: belegt
Offen: EK_SB-Kapazität (investierbar laut Log `"[ASSEMBLE] EK_SB: investable EK cap∈[0.0, 50.0] MW, capex=150000
€/MW"`) konnte NICHT direkt als gebaute Kapazität identifiziert werden — `dispatch_per_asset.csv` hat keine
eindeutige EK-Spalte (einzig `P2H_MW` kommt infrage, ist aber in S1/S2/S3 identisch bei 9,9 MW trotz unterschiedlicher
`share_EK_pct` in economics.csv [0,61% / 0,75% / 0,75%] — das spricht GEGEN P2H_MW=EK_SB, da eine echte
Kapazitätsänderung sich dort zeigen müsste). Das bedeutet: **Die Trennung Speicher↔WP/EK aus B3 ist für HP klar
belegt, für EK aber noch offen** — braucht entweder eine andere Exportdatei oder eine gezielte Pyomo-Variablenabfrage
(kein Solve nötig, nur ein Read der bereits gelösten `full_solution_dump.json`, die alle Variablenwerte inkl. EK-Cap
enthält). Aufwand: klein (ein Lookup-Skript, ~15-20 Minuten).

---

## A3 — c0-Sweep: Konsistenz, Umpreisung, Plausibilität

### A3a — Inkumbentenverlauf aller sieben Läufe

| c0-Skalierung | obj_eur (UB) | Gap | Status | TES build | E_TES_max_MWh | V_TES_m3 | Solution count (echtes Log) |
|---|---|---|---|---|---|---|---|
| PIN0 | 23.370.804,48 | 0,1436% | optimal | 0 | - | - | 1 (proven optimal, kein Problem) |
| ×0,5 | 22.981.415,31 | 0,2277% | maxTimeLimit | 1 | 438,0 | 30.379,4 | **1** (sauberer Einzellauf, 11.134 Knoten exploriert) |
| ×0,7 | 23.057.656,99 | 0,1529% | maxTimeLimit | 1 | 438,0 | 30.379,4 | **1** (sauberer Einzellauf, 12.669 Knoten exploriert) |
| ×1,0 | 23.172.019,51 | 0,1365% | optimal | 1 | 438,0 | 30.379,4 | 1 (proven optimal) |
| ×1,3 | 23.286.382,04 | 0,3372% | maxTimeLimit | 1 | 438,0 | 30.379,4 | **1-2, MEHRFACH NEUGESTARTET** (siehe A3c) |
| ×1,5 | 23.362.623,72 | 0,5692% | maxTimeLimit | 1 | 438,0 | 30.379,4 | **1-2, MEHRFACH NEUGESTARTET** (siehe A3c) |
| ×2,0 | 23.369.171,04 | 0,4355% | maxTimeLimit | 1 | **37,0** | **2.566,3** | **10** (sauberer Einzellauf, echte Exploration) |

Evidenz: je `output/{v7_final/SB-S0-HK0-PIN0, v7_final/SB-S1-HK0, _s2/sb_c0x05/paper2_runs/SB-S1-HK0,
_s2/sb_c0x07/paper2_runs/SB-S1-HK0, _parallel_aa3/c0x1.3/paper2_runs/SB-S1-HK0,
_parallel_aa3/c0x1.5/paper2_runs/SB-S1-HK0, _parallel_aa3/c0x2.0/paper2_runs/SB-S1-HK0}/{meta.json,geometry.csv}` +
zugehörige `logs/gurobi_SB-S1-HK0.log` (`Solution count` Zeile; `×1,3`/`×1,5` zusätzlich `grep "Loaded user MIP
start"` → 3 bzw. 3 Treffer mit IDENTISCHEM Startwert, d.h. mehrfacher Neustart ohne Fortschritt).
Status: belegt
Warmstartquelle je Lauf: PIN0/S1 = `optimal`, kein externer Warmstart nötig; ×0,5/×0,7/×1,3/×1,5 = `output/v7_final/SB-S1-HK0`
(CALION_WARMSTART_FROM, Hint-Modus); ×2,0 = ebenfalls `output/v7_final/SB-S1-HK0` laut Konvention dieser Kampagne
(nicht einzeln neu verifiziert, **vermutet** nach Namenskonvention — Offen: expliziten Log-Beleg für ×2,0s
Warmstartquelle nicht gegengeprüft).
Tankgröße je Lauf verändert? NEIN bei ×0,5/×0,7/×1,0/×1,3/×1,5 (alle exakt 438,0 MWh / 30.379,4 m³ — identisch bis
auf die letzte Dezimale), JA bei ×2,0 (37,0 MWh / 2.566,3 m³ — deutlich kleiner).

### A3b — Konsistenz-Assertion: Tankkosten-Formel

Formel (aus `scenario_meta.json`, s.u.): `CAPEX_total_EUR = c0_scale × c0_eur × (V_m3 / v0_m3) ^ exponent_b`, mit
`c0_eur=2.500.000`, `v0_m3=10.000`, `exponent_b=0,7` (alle aus `output/v7_final/SB-S1-HK0/scenario_meta.json` →
`tank_config.tes_sb`). Annuität = `CAPEX_total_EUR × annual_factor`, `annual_factor=0,0651` (aus
`output/_s2/sb_s2_resolve2/chain.output`, Logzeile `"[GEOMETRIC_STORAGE] tes_sb: ... annual_factor=0.0651"`).

Nachrechnung für V=30.379,4 m³, c0_scale=1,0: `(30.379,4/10.000)^0,7 = 3,03794^0,7 ≈ 2,176`.
`CAPEX_total ≈ 2.500.000 × 2,176 ≈ 5.439.000 EUR`. `Annuität ≈ 5.439.000 × 0,0651 ≈ 354.079 EUR/a`.
Vergleich mit real beobachteter TES-Annuitäts-Differenz zwischen drei echten Läufen (aus `cost_breakdown.json`
`Capex_cost_EUR`, die neben TES auch HP/EK/Rohr enthält, aber bei KONSTANTER TES-Größe linear in c0 sein muss):
`Capex(c0×0,5)=438.395,29`, `Capex(c0×0,7)=509.195,14`, `Capex(c0×1,0)=615.394,91` → aus den Differenzen:
`ΔCapex(0,7→1,0)/Δc0(0,3) = 353.999,8 EUR/a` und `ΔCapex(0,5→0,7)/Δc0(0,2) = 354.000 EUR/a` (zwei unabhängige
Steigungsschätzungen, STIMMEN exakt überein → linear in c0, wie von der Formel vorhergesagt). Die aus der Formel
berechnete Annuität (354.079 EUR/a) trifft den real beobachteten Wert (354.000 EUR/a) auf **79 EUR von 354.000
(0,02%)** — die Kostenformel ist damit konsistent mit den echten MILP-Ergebnissen bestätigt.
Evidenz: `output/{_s2/sb_c0x05,_s2/sb_c0x07,v7_final}/.../cost_breakdown.json` → `real_costs_EUR.Capex_cost_EUR.value`.
Status: berechnet (aus drei echten, unabhängigen Läufen rückgerechnet, Formel aus Code/Config belegt)

**TES-O&M skaliert NICHT sauber trennbar mit c0:** `OM_fixed_cost_EUR` (Systemweit, nicht TES-exklusiv) ist
1.581.726,64 (c0×1,0) / 1.568.122,05 (c0×0,5) / 1.573.563,89 (c0×0,7) / 1.563.692,70 (c0×2,0) — Unterschiede von
≤1,2%, die vermutlich NICHT von TES-O&M selbst stammen (TES-O&M sollte NICHT von c0 abhängen, nur die CAPEX-Formel
tut das), sondern vom unterschiedlichen HP-Dispatch/-Größe je Lauf. Eine saubere TES-exklusive O&M-Zahl ist aus
`cost_breakdown.json` NICHT isolierbar.
Status: belegt (Zahlen) / vermutet (Interpretation der Ursache)
Offen: Feinere O&M-Aufschlüsselung je Technologie wäre nötig (Teil von B1, siehe unten).

### A3c — Umpreisung (Repricing) und Prüfung von H5

Repricing-Formel (reine Arithmetik, S1-Lösung mit konstanter Nicht-TES-Komponente `x` + linearem TES-Term `c0×T`,
beide aus A3b abgeleitet: `x = Capex(1,0) - T = 615.394,91 - 353.999,9 = 261.395,0`):
`obj_repriced(c0) ≈ obj(1,0) + (c0-1) × T`, mit `T=354.000 EUR/a`.

| c0 | obj_repriced (berechnet) | obj_real (Lauf) | Δ (real − repriced) | Δ in % der PIN0-TAC |
|---|---|---|---|---|
| 0,5 | 22.995.019,9 | 22.981.415,3 | **−13.604,6** (real BESSER) | −0,058% |
| 0,7 | 23.065.019,9 | 23.057.657,0 | −7.362,9 (real BESSER) | −0,032% |
| 1,3 | 23.278.219,9 | 23.286.382,0 | **+8.162,1** (real SCHLECHTER) | +0,035% |
| 1,5 | 23.349.019,9 | 23.362.623,7 | **+13.603,7** (real SCHLECHTER) | +0,058% |

Status: berechnet (alle Eingangswerte belegt, s.o.)

**WICHTIGE KORREKTUR/EINORDNUNG (nachträglich gefunden):** Dieses Unterkonvergenz-Problem ist KEIN neuer Fund — es
ist bereits seit 2026-10-12 in `docs/paper_2/submission_pack/00_statements/MODEL_AND_DOE_CONTROL.md` §4ck
("Offener Belastbarkeits-Vorbehalt: c0×1,3/1,5 vermutlich NICHT neu-optimierte TES-Größe") EXPLIZIT dokumentiert,
mit identischer Begründung (`Solution count 1` vs. `10`, bit-identische Tankgröße) UND einer bereits getroffenen
Nutzerentscheidung: "Auf Nutzeranweisung NICHT neu gerechnet (Zeitdruck Richtung Manuskript) — als dokumentierte
Einschränkung festgehalten, nicht stillschweigend als 'final' verwendet." §4cn bestätigt zusätzlich, dass die
Z5-Elastizitätsanalyse ×1,3/1,5 bereits BEWUSST ausschließt. **Mein Beitrag hier ist NICHT die Entdeckung, sondern
die quantitative Nachrechnung** (die Repricing-Delta-Tabelle oben, 8-14k EUR Abweichung) — das war in §4ck noch
nicht so quantifiziert. D2 (Re-Solve ohne S1-Warmstart-Bindung) bleibt der richtige nächste Schritt, ist aber
bereits als bekannter offener Punkt dokumentiert, keine neue Empfehlung.

**Bewertung (berechnet + belegt, bestätigt H5 mit Evidenz, nicht nur Verdacht):** Bei c0×1,3/1,5 ist das reale
Ergebnis SCHLECHTER als die triviale Umpreisung derselben S1-Lösung — das ist ökonomisch unplausibel (der Solver
sollte MINDESTENS die umgepreiste S1-Lösung erreichen, da sie eine zulässige Lösung ist) und erklärt sich durch die
in A3a gefundene Logevidenz: diese beiden Läufe wurden MEHRFACH neugestartet (identischer "Loaded user MIP start"-Wert
3× wiederholt) und kamen nie über `Solution count 1-2` hinaus — die kumulierte, nutzbare B&B-Explorationszeit war
also DEUTLICH kürzer als die nominalen 8h TimeLimit suggerieren. **Das ist der vermutete Grund für H5: ×1,3/×1,5 sind
unterkonvergiert, nicht ein echtes (schlechteres) Optimum.**
Bei c0×0,5/0,7 ist das reale Ergebnis dagegen BESSER als die Umpreisung — das ist NICHT widersprüchlich (die
Umpreisungsformel ist nur eine lineare Näherung über CAPEX; Dispatch-Freiheitsgrade bei leicht veränderter
Kostenstruktur können marginal bessere Lösungen finden, und beide Läufe hatten SAUBERE Einzelläufe mit 11-13 Tsd.
explorierten Knoten, nicht die Neustart-Pathologie von ×1,3/×1,5) — die Abweichung (0,03-0,06% der TAC) liegt in der
Größenordnung der jeweiligen MIP-Gaps und ist kein Hinweis auf ein Problem.

**Empfehlung (deckt sich mit dem bereits im Auftrag vorgeschlagenen D2):** ×1,3 und ×1,5 sollten mit frischem
Warmstart (PIN0-Dump + SEED_FILL_ZERO, wie beim Stage-2-Fix für S2/S3) neu gelöst werden, NICHT vom alten,
mehrfach-gescheiterten S1-Warmstart aus. Erwartung (vermutet, nicht belegt): der Solver würde dabei vermutlich einen
KLEINEREN Tank als 438 MWh finden (analog zu ×2,0s 37 MWh-Ergebnis mit echter `Solution count 10`-Exploration), was
sowohl H4 ("Tankgröße konstant über ×0,5-1,5 = Anker") als auch H5 in einem Schritt auflösen würde. Das ist exakt
Teil-D-Punkt D2 im Auftrag — hier NICHT gestartet (kein `[x]`), nur die Evidenz dafür zusammengetragen.

### A3d — Plausibilität: Warum wählt der Solver bei halbem Preis keinen größeren Tank?
Antwort: Weil er es gar nicht ausprobiert hat — bei `Solution count 1` wurde die Tankgröße NIE verändert, der Solver
hat nur um den transplantierten S1-Warmstart herum exploriert (B&B-Knoten für Dispatch-Feinheiten, nicht für
alternative TES-Größen-Rungs). Diese Frage bleibt für c0×0,5/0,7 **offen** (vermutet, nicht geprüft): ob ein
größerer Tank bei halbem Preis tatsächlich günstiger wäre, kann nur ein Lauf OHNE S1-Größen-Festlegung im Warmstart
beantworten (das ist exakt D2s Ankertest-Logik, nur für die UNTERE statt OBERE c0-Richtung — im Auftrag nicht
explizit für ×0,5/0,7 vorgesehen, aber methodisch identisch).
Status: vermutet
Offen: D2-artiger Ankertest auch für ×0,5/×0,7 wäre nötig, um diese Frage abschließend zu klären (nicht Teil des
aktuellen `[x]`-Umfangs).

## Zusammenfassung A2+A3
A2 bestätigt und verschärft (mit exakten statt handgerechneten Pipe-Werten) den Stage-1-Befund: j_man ist
hydraulisch auf ≈21-49 MW begrenzt, S1s Tank bräuchte 109,5 MW — S2/S3s `build=0` ist jetzt durch echte
B&B-Exploration (`Solution count 10`, nicht `1` wie `meta.json` fälschlich zeigt) ZWEIFACH abgesichert: strukturell
(Pipe-Kapazität) UND empirisch (Solver findet unabhängig keinen Vorteil). A3 bestätigt H4 (Tankgröße invariant über
×0,5-1,5) ist bei ×0,5/0,7 wahrscheinlich eine echte, aber bei ×1,3/1,5 eine ARTEFAKT-Invarianz durch
Mehrfach-Neustart-Unterkonvergenz (A3c) — ×2,0s erfolgreicher Tankschrumpf (438→37 MWh, echte Exploration) ist der
Gegenbeweis, dass der Solver bei genügend Explorationszeit durchaus reagiert. Zwei neue Meldepflichten: (1)
`meta.json["solution_count"]` ist bei mehreren Läufen falsch (zeigt oft `1` egal was das echte Log sagt), (2) D2
(Re-Solve ×1,3/×1,5 mit PIN0-Dump-Warmstart) ist jetzt nicht mehr nur "interessant", sondern durch A3c als nötig
belegt, um H4/H5 abschließend zu klären.
