# Rolling-Horizon Parity: Korrektur-Aufgaben

## Kontext
Reviewer-Hinweise zeigen drei Stellen, an denen Rolling-Horizon (RH) und Parity-Dokumentation auseinanderlaufen oder Kosten falsch aggregiert werden:
- `docs/parity_check.md` listet Grid-Kappen und CapEx-Doppelzählung als offene Punkte, obwohl Grid-Limits im Code vorhanden sind und das RH-Design-Fix weitere Investitionen nach Fenster 1 stoppt.
- Tie-Breaker- und installationsbezogene CapEx-Terme bleiben in der RH-Zielfunktion aktiv und werden pro Fenster in `aggregated_costs` aufsummiert.
- Die Ergebnisaggregation summiert jeden numerischen Kosteneintrag pro Fenster, auch Fixkosten oder horizon-bezogene Charges, ohne Klarstellung zur Skalierung.

## Aufgabe
Formuliere und implementiere einen Fix, der die oben genannten Abweichungen zwischen Dokumentation und Code behebt und die RH-Kostenaggregation präzisiert.

### Teilaufgaben
1. **Parity-Dokument aktualisieren**
   - Passe `docs/parity_check.md` so an, dass umgesetzte Grid-Kappen und CapEx-Fix als erledigt markiert und korrekt beschrieben sind.
   - Hebe verbleibende offene Punkte hervor (z. B. Kostenaggregation, Tie-Breaker-Terme), damit Reviewer den aktuellen Stand sehen.

2. **Tie-Breaker- und Installationskosten im RH**
   - Ergänze einen expliziten Schalter oder eine Einmal-Amortisation, damit tie-breaker/install CapEx nur einmalig oder nach definierter Logik angesetzt werden.
   - Sorge dafür, dass `aggregated_costs` in `energis/run/rolling_horizon.py` diese Logik respektiert (kein Fenster-Overcounting).

3. **Ergebnisaggregation klären**
   - Prüfe `_accumulate_costs` auf jährliche/horizon-bezogene Skalierungen (Demand Charge, Fixkosten). Definiere, was rollierend vs. einmalig summiert wird, damit PF-only und PF→RH vergleichbar sind.
   - Dokumentiere die Aggregationslogik im Code (Docstring/Kommentar) und ergänze, falls nötig, Tests, die PF- und RH-Ergebnisse gegenüberstellen.

### Akzeptanzkriterien
- Parity-Dokumentation spiegelt den implementierten Stand wider und verweist auf bekannte Einschränkungen.
- RH-Zielfunktion und `aggregated_costs` führen tie-breaker/install CapEx nur gemäß definierter Einmal- oder Roll-Logik auf.
- Kostenaggregation ist dokumentiert und durch Tests abgesichert, sodass PF-only und RH-Läufe konsistente Summen liefern.
