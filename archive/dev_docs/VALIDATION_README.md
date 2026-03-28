# Framework Validierung - Dokumentations-Index

**Created:** 2026-03-27  
**Status:** ✅ Produktionsreif

---

## Überblick: 4 Validierungs-Dokumente

Sie haben jetzt 4 Dokumente für umfassende Framework-Prüfung:

```
├─ QA_CHECKLIST.md (HIER BEGINNEN!)
│  └─ 8-Phasen-Checkliste: Vor → Nach Optimierung
│  └─ Für: Projektmanager, Team-Lead
│  └─ Zeit: 15 min pro Run zum Abhaken
│
├─ VALIDATION_STRATEGIES.md (KONZEPTE LERNEN)
│  └─ 10 Strategien für Qualitätspricherung
│  └─ Für: Entwickler, Data Engineers
│  └─ Zeit: 30 min Überblick, dann gezielt nutzen
│
├─ DEBUGGING_GUIDE.md (PROBLEME LÖSEN)
│  └─ 7 häufige Probleme + systematisches Debugging
│  └─ Für: Wenn was schiefgeht
│  └─ Zeit: 5-20 min je Problem
│
└─ validate_framework.py (AUTOMATISCH TESTEN)
   └─ Single-command validation
   └─ Für: Schnelle Checks, CI/CD
   └─ Zeit: <10 Sekunden
```

---

## Wann welches Dokument nutzen?

### 🚀 Neue Optimierung starten?
1. Öffne: **QA_CHECKLIST.md** Phase 1-2
2. Häkchen abhaken
3. Läuft!

### ✅ Optimierung beendet - Ergebnisse prüfen?
1. Starte Validierungsskript:
   ```bash
   python validate_framework.py
   ```
2. Sollte anzvigen: `✅ ALLE CHECKS BESTANDEN`
3. Dann: **QA_CHECKLIST.md** Phase 3-5

### 🔍 Ergebnisse sehen merkwürdig aus?
1. Konsultiere: **DEBUGGING_GUIDE.md**
2. Finde Problem in "Häufige Probleme" Section
3. Folge Debug-Schritte

### 📚 Framework-Kenntnis erweitern?
1. Lese: **VALIDATION_STRATEGIES.md**
2. Wähle interessanteBereiche aus
3. Implementiere zusätzliche Checks

---

## Quick Start (5 Minuten)

### Scenario 1: "Alles läuft - nur validieren wollen"

```bash
# Single command
python validate_framework.py

# Expected output:
# ✅ ALLE CHECKS BESTANDEN - Framework ist valid!
```

**→ Fertig!** Wenn grün, alles OK.

---

### Scenario 2: "Ich muss eine Optimierung durchführen"

```bash
# Schritt 1: Öffne QA_CHECKLIST.md Phase 1
# Abhaken:
  ☐ CSV Input 8760 Zeilen
  ☐ Config YAML valid
  ☐ Python Environment ready
  
# Schritt 2: Run
python -m energis.run configs/scenarios/stadtbach_baseline_2023.yaml

# Schritt 3: Nach ~2 min, validiere
python validate_framework.py

# Schritt 4: Öffne QA_CHECKLIST.md Phase 3-5
# Weitere Details prüfen
```

**→ Fertig!** Framework ist validiert.

---

### Scenario 3: "Solver gibt Error"

```bash
# Fehlermeldung kopieren
python -m energis.run configs/scenarios/stadtbach_baseline_2023.yaml 2>&1 | tail -20

# Öffne: DEBUGGING_GUIDE.md
# Suche nach Fehlertyp in "Häufige Probleme"
  - Problem 1: No solution (infeasible)
  - Problem 2: Wrong physics
  - Problem 3: Empty export
  - etc.

# Folge Debug-Schritte im Guide
```

**→ Problem gelöst!** Guide hat Schritt-für-Schritt Anleitung.

---

## Dokument-Details

### 📋 QA_CHECKLIST.md (8 Phasen)

**Wann:** Vor + nach jeder Optimierung  
**Dauer:** ~30 Minuten  
**Zielgruppe:** Alle (Projekt-Manager, Entwickler, Betreiber)

**Struktur:**
```
Phase 1: Vor der Optimierung (Daten + Config)
Phase 2: Während die Optimierung läuft (Monitoring)
Phase 3: Nach der Optimierung (Sofort-Checks)
Phase 4: Detaillierte Validierung (Wärmebilanz, Kosten)
Phase 5: Finale Validierungssuite (Unit Tests)
Phase 6: Dokumentation (Report erstellen)
Phase 7: Übergabe (Stakeholder-Signoff)
Phase 8: Laufende Überwachung (Monatliche Checks)
```

**Verwendung:** Beim Durchführen einer Optimierung alle 8 Phasen in dieser Reihenfolge durcharbeiten.

---

### 🎯 VALIDATION_STRATEGIES.md (10 Strategien)

**Wann:** Zum Lernen + konzeptionelle Fragen  
**Dauer:** 5-30 min je Strategie  
**Zielgruppe:** Entwickler, Data Engineers

**Strategien:**
1. Unit Tests (Component-Level)
2. Ergebnisvalidierung (Output Checks)
3. Wirtschaftliche Validierung
4. Sensitivitätsanalyse
5. Vergleichstests (Benchmarking)
6. Physikalische Validierung
7. Automated Validation Suite
8. Regression Tests
9. Integration Tests
10. Dokumentation & Benchmarks

**Verwendung:** 
- Neue Mitarbeiter lesen Überblick für Framework-Verständnis
- Entwickler nutzen spezifische Strategien bei Code-Änderungen
- Team-Lead nutzt für QA-Plan

---

### 🔧 DEBUGGING_GUIDE.md (7 Problem-Klassen)

**Wann:** Wenn was schiefgeht  
**Dauer:** 5-20 min je Problem  
**Zielgruppe:** Wenn Fehler auftritt

**Probleme:**
1. Solver meldet keine optimale Lösung
2. Ergebnisse machen physikalisch keinen Sinn
3. CSV ist leer oder unvollständig
4. Kosten sind unrealistisch
5. Solver ist sehr langsam
6. Unterschiede zwischen zwei Läufen (Regression)
7. Export-Dateien sind beschädigt

**Verwendung:**
- Suche nach dem Fehlersymbol / Symptom
- Folge Debug-Schritte
- Referenziert alle anderen Guides

---

### ⚙️ validate_framework.py (Automatisierung)

**Wann:** Nach jeder Optimierung  
**Dauer:** <10 Sekunden  
**Zielgruppe:** Automatisiert (CI/CD), manueller Schnell-Check

**Checks (8 total):**
1. Time Coverage (8760 hours?)
2. No Null Values
3. Data Types OK
4. Heat Balance (Demand ≈ Supply)
5. Storage Consistency
6. Capacity Limits OK
7. Demand Plausibility
8. Annual Statistics

**Verwendung:**
```bash
# Nach der Optimierung
python validate_framework.py

# Integration in CI/CD
# - GitHub Actions
# - Daily batch runs
# - Pre-export hooks
```

---

## Workflow Pro: Alle zusammen nutzen

```
Tag 1: LEARNING
├─ Lese QA_CHECKLIST.md komplett (verstehe Phasenverlauf)
├─ Lese VALIDATION_STRATEGIES.md Überblick
└─ Lese DEBUGGING_GUIDE.md Inhaltsverzeichnis

Tag 2: ERSTE RUN
├─ Folge QA_CHECKLIST Phase 1-5
├─ Starte: python validate_framework.py
└─ Bei Error: Konsultiere DEBUGGING_GUIDE

Tag 3+: ROUTINEBETRIEB
├─ Für jede Optimierung:
│  ├─ QA Phase 1 + 3 (vor + nach)
│  ├─ python validate_framework.py
│  └─ QA Phase 4 (wenn Werte verstehen wollen)
└─ Bei Problemen → DEBUGGING_GUIDE
```

---

## Integration in Ihr Team-Prozess

### Für Projekt-Manager
- **Hauptdoku:** QA_CHECKLIST.md
- **Workflow:** Phase 1 (Vorbereitung) → Phase 7 (Stakeholder-Signoff)
- **Tool:** validate_framework.py für Quick-Check vor Meetings

### Für Entwickler
- **Hauptdoku:** VALIDATION_STRATEGIES.md + DEBUGGING_GUIDE.md
- **Workflow:** Wenn Code ändert → alle neuen Funktionen mit Strategie X testen
- **Tool:** Unit-Tests + validate_framework.py vor Commit

### Für Betreiber (Produktivbetrieb)
- **Hauptdoku:** QA_CHECKLIST.md Phase 3 (Nach Optimierung)
- **Workflow:** Nach automatischer Optimierung → validieren → publishieren
- **Tool:** `python validate_framework.py` als Status-Check

### Für Übergabe an Kunden
- **Deliverables:** QA_CHECKLIST.md Phase 6 (Reports)
- **Dokumentation:** VALIDATION_STRATEGIES.md (Shows rigor)
- **Support:** DEBUGGING_GUIDE.md (Falls Fragen)

---

## Signoff nach Validierung

Wenn alle Checks grün sind, können Sie signoff geben:

```markdown
## Validation Signoff - Q1 2026

✅ **Technical Validation:**
- QA Checklist: Phase 1-5 completed
- Validator script: All checks passed
- Unit tests: 8/8 passed
- No regressions detected

✅ **Business Validation:**
- Costs plausible (€35/MWh)
- Energy balance OK (±2%)
- All required exports present

**Approved by:** [Name], [Date]
**Status:** READY FOR PRODUCTION
```

---

## Häufige Setup-Fragen

**Q: "Muss ich alle 4 Dokumente lesen?"**
A: Nein! Für normale Optimierung nur QA_CHECKLIST.md. Andere zur Referenz wenn nötig.

**Q: "Wie oft sollte ich validieren?"**
A: Minimum: Nach jeder Optimierung (5 min mit Checkliste). Ideal: Vor jedem Stakeholder-Meeting.

**Q: "Was wenn validate_framework.py fehlschlägt?"**
A: → Konsultiere DEBUGGING_GUIDE.md. Fast immer schnelle Lösung.

**Q: "Können wir automatisiert jeden Tag checken?"**
A: Ja! Integriere `python validate_framework.py` in Cron-Job / GitHub Actions.

**Q: "Brauchen wir Gurobi oder kostenlosen HiGHS?"**
A: HiGHS reicht! Validierung funktioniert mit jedem Solver.

---

## Feedback & Updates

Diese Dokumente sind **lebende Dokumentation**. Wenn Sie Fragen haben:

1. **Neue Probleme?** → Ergänze DEBUGGING_GUIDE.md
2. **Neue Strategien?** → Ergänze VALIDATION_STRATEGIES.md
3. **Prozess-Anpassung?** → Update QA_CHECKLIST.md
4. **Code-Bug?** → Fix validate_framework.py

---

## Weitere Ressourcen

| Thema | Datei | Beschreibung |
|-------|-------|-------------|
| **Erste Schritte** | QA_CHECKLIST.md | Start hier |
| **Konzepte** | VALIDATION_STRATEGIES.md | Tieferes Wissen |
| **Probleme** | DEBUGGING_GUIDE.md | Troubleshooting |
| **Automatisiert** | validate_framework.py | Single command |
| **API Docs** | docs/api_reference.rst | Framework API |
| **User Guide** | docs/USER_GUIDE.md | Allgemein |

---

**Version:** 1.0  
**Stand:** 2026-03-27  
**Status:** ✅ Produktionsreif

**Nächster Schritt:** Offen QA_CHECKLIST.md und beginne mit Phase 1! 🚀
