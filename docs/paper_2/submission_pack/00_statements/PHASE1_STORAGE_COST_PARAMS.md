# Phase-1 prep — atmospheric storage cost parameterization (T2)

**Stand 2026-09-01.** Vorbereitet während der laufenden Value-Probe. Quellen: realisierte
dänische PTES-Projekte + DEA/IEA-DHC-Benchmarks. Ersetzt die druckbeaufschlagte
1.200 €/m³-Annahme durch eine technologie- und größenrichtige, degressive Kostenkurve.

## Technologie-Bifurkation nach Größe (wichtig)

Die Speicherkosten hängen von der **Bauform** ab, die wiederum von der **Größe** abhängt:

| Regime | Volumen | Bauform | Kosten | Anwendung |
|---|---|---|---|---|
| klein | ~100–3.000 m³ | atmosph. Stahltank (TTES) | ~200–500 €/m³ | Memmingen (~600 m³ Optimum) |
| groß | 10.000–200.000 m³ | Erdbecken-Speicher (PTES) | ~24–67 €/m³ | Stadtbach (saisonal, falls Value-Probe es zeigt) |

Beide sind **atmosphärisch** (≤ ~90 °C) → die ~95 °C-Decke aus WP0_BEFUND Zusatzbefund A gilt
für beide; PTES fährt real sogar nur ~80–90 °C (Vojens ~80 °C).

## Degressive Kostenkurve (PTES, realisierte dän. Projekte)

Realisierte spezifische Kosten (Investition je m³ Speichervolumen):

| Projekt | Jahr | Volumen | €/m³ |
|---|---|---|---|
| Marstal | 2012 | 10.000 m³ | 67 |
| Dronninglund (Sunstore 3) | 2014 | 60.000 m³ | 38 |
| Vojens | 2015 | 200.000 m³ | 24 |
| DEA/Benchmark | — | ≥100.000 m³ | ~30 |

**Fit** `C_inv(V) = C₀ · (V/V₀)^b`, V₀ = 10.000 m³, C₀ = 670.000 € (= 67 €/m³ × 10.000):
- aus (10k, 67) und (200k, 24): `b − 1 = ln(24/67)/ln(20) = −0,343` → **b = 0,657**.
- Kreuzcheck Dronninglund: 67·(60000/10000)^(−0,343) = **35,9 €/m³** vs. real 38 → guter Fit.

→ **b ≈ 0,66** (im vom Reviewer/DEA genannten Band 0,6–0,7). Für die MILP-Linearisierung an
die **bestehende diskrete Energie-Leiter** hängen (jede Stufe bekommt ihre `C₀·(V_k/V₀)^b`-
Kosten — exakt, gap-fest, kein SOS2), NICHT als kontinuierliche PWL.

## Konsequenz (bereits aus der Value-Probe ableitbar)

Der Technologiewechsel **kippt Memmingen von „kein Speicher" zu „~10 MWh Speicher"**:
- Value-Probe: 10 MWh (~600 m³) senken OPEX um ~27.000 €/a.
- Druckbeaufschlagt (1.200 €/m³): 600 m³ → 720 k€ → ~37.000 €/a annuisiert **> Wert** → unwirtschaftlich (= heutiges „TES vernachlässigbar").
- Atmosph. Stahltank (~300 €/m³): 600 m³ → 180 k€ → ~9.200 €/a annuisiert **≪ Wert 27 k€** → **klar wirtschaftlich**, Netto ~+18 k€/a.

Das ist der zentrale Mechanismus des Papers, jetzt mit Zahlen: nicht die HK-Kopplung (die war
immer da), sondern die **Speichertechnologie/-kostenannahme** entscheidet, ob ein inneres
Optimum ökonomisch erreicht wird.

## Noch zu holen (klein)
- DEA-TTES-Eintrag (Stahltank-Kostenkurve) für das Klein-Regime präziser als der ~200–500 €/m³-
  Bereich; Zitat für T2.
- U-Wert für den Oberflächenverlust: PTES ~ 0,15–0,3 W/m²K (Deckel schlechter als Wände);
  Quelle in T2 nennen (WP1 `storage_geometry.yaml`).

## Quellen
- Seasonal pit heat storage cost benchmark (30 €/m³, Marstal/Vojens/Dronninglund):
  https://solarthermalworld.org/news/seasonal-pit-heat-storage-cost-benchmark-30-eurm3/
- IEA-DHC Annex XII, PTES for Smart District Heating (design + cost):
  https://www.iea-dhc.org/fileadmin/documents/Annex_XII/2020.03.09_Report_Task_C_IEA_DHC_Annex_XII_Project_03.pdf
- Høje Taastrup WPTES monitoring (temperatures/operation): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11791156/
