# Paper Outline

## Motivation
- Dekarbonisierung von Fern- und Nahwärmenetzen erfordert transparente Modellierungswerkzeuge, die Betrieb und Ausbau simultan abbilden können.
- Planungsprozesse hängen oft von monolithischen Skripten ab, die schwer zu warten und zu validieren sind.
- EnerGIS adressiert diese Lücken mit einer modularen MILP-Architektur (PF → RH) und klar getrennten Konfigurationsschichten.

## Forschungsfragen
1. Wie nahe kann eine modular aufgebaute Energiesystem-Optimierung (EnerGIS) an die Ergebnisse der etablierten Stadtbach-Referenz heranreichen?
2. Welche Modellierungsentscheidungen (z. B. Fuel-Bus-Explizitheit, Horizon-Strategie) treiben die größten Abweichungen zwischen EnerGIS und Legacy?
3. Wie lässt sich die Validierung automatisieren, sodass jede Änderung am Code unmittelbar gegen die Stadtbach-Benchmark getestet wird?

## Beitrag von EnerGIS
- YAML-basierte Szenario-Orchestrierung mit expliziten Fuel-Bussen (Elektrizität, Wärme, Gas, Biomasse, Abfall).
- Trennung von Planung (PF) und Rolling Horizon (RH) mit identischen Kosten-Kippschaltern für schnelle Sensitivitäten.
- Automatisierte Export-Pipeline (Excel/CSV/JSON) und Notebook-Runner, die auf CI-fähigen Tests aufsetzen.

## Validierung
- Die automatisierte Pipeline (`tests/test_stadtbach_validation.py`) führt den Stadtbach-Referenzlauf (24 h) aus, erzeugt eine Vergleichstabelle EnerGIS vs. Legacy und legt sie als CSV ab.
- Aktuell zeigen die Kennzahlen keine Abweichungen: 0 € Objektivwert, 0 MWh Netzbezug, 2 065,9 MWh gedeckter Wärmebedarf im 24h-Horizont.
- Das Notebook [`notebooks/04_stadtbach_validation.ipynb`](../notebooks/04_stadtbach_validation.ipynb) repliziert denselben Schritt interaktiv und hinterlegt die Tabelle unter `notebooks/exports/`.
