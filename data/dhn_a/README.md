# Datensatz DHN-A (anonymisiert)

Anonymisierte Mess- und Plandaten eines städtischen Fernwärme-Verbundnetzes (PN25, ≈ 392 MW Anschlussleistung) für die
Speicherstudie (`docs/dhn_storage_study/`) und die Analysen in `scripts/dhn_study/`. Freigabe zur Ablage im Repository
durch den Auftraggeber; vor einer Weitergabe außerhalb des Projekts erneut klären.

## Dateien

| Datei | Inhalt |
|---|---|
| `measurements_2025_hourly.parquet` | 8 759 Stundenwerte 2025, 169 Signale aus dem Leitsystem; Index naive Ortszeit (Sommerzeit: 30.03. 02:00 fehlt, Doppelstunde 26.10. auf einen Wert reduziert) |
| `consumers.csv` | Verbraucher V01–V24 mit Netzregion und Hinweis (Regelpunkte V06, V01, V13). V01 gehört zum Westnetz (Druckkorrelation) |
| `generation_profiles_2020_2022_hourly.csv` | Stündliche Gesamterzeugung 2020–2022 [MW], Zeile = Stunde ab 01.01. (2020 fortlaufend inkl. 29.02., endet 30.12.) |
| `ambient_temperature_hourly.parquet` | Außentemperatur stündlich ab 2019 [°C], naive Ortszeit |
| `ambient_temperature_daily.csv` | Tagesmittel der Außentemperatur ab 1955 [°C] |
| `plants.yaml` | Anlagendaten der Erzeuger und Pumpstationen aus den Betreiberplänen; Höhen relativ zur Hauptanlage. Δp-Werte sind laut Plan Erfahrungswerte, Leistungen bei −14 °C gelten für n−1 |
| `sectors.csv` | 52 Teilgebiete mit versorgender Stammleitung (L1–L4, West W1–W3), Region, Netzvolumen [m³], Kundenzahl und Anschlussleistung [MW], Stand 2022. Summen: Verbund 392,0 MW / 8 875 m³, West 75,7 MW / 1 781 m³. In Teilgebiet L7-O ist die Kundenzahl der Quelle widersprüchlich |

## Signalnamen

Aufbau `<Objekt>_<Größe>`.

**Objekte:**
* `V01`…`V24`: Verbraucher bzw. Messstellen
* `gas_CHP`: Gas-KWK, Hauptanlage und Druckhalter
* `waste_incineration`: Abfallverbrennung
* `gas_turbine`: Gasturbine
* `biomass_CHP`: Biomasse-KWK
* `boiler_plant_1`: Heizwerk 1
* `boiler_plant_2`: Heizwerk 2. Unterobjekte: `_hx_…` ist die Übergabe aus dem Verbund über Wärmeübertrager, `_secondary_…` das Sekundärnetz West
* `pump_station_1`, `pump_station_2`: Pumpstationen im Vorlauf

**Größen:**
* `p_supply`, `p_return`: Vorlauf- bzw. Rücklaufdruck, bar Überdruck
* `dp`: Differenzdruck [bar]
* `T_supply`, `T_return` [°C]
* `flow`: Durchfluss in **t/h** (Einheitentest; Biomasse-KWK in m³/h im Vorlauf)
* `heat`: Wärmeleistung [MW]
* `gas_CHP_flow_line_1…4`: Durchfluss der Stammleitungen ab der Hauptanlage; vorzeichenbehaftet, + = aus der Anlage, gemessen im Rücklauf
* `gas_CHP_flow_total_out`: Summe der positiven Stammleitungsflüsse

## Bekannte Datenfehler

| Signal | Fehler | Behandlung |
|---|---|---|
| `gas_turbine_heat` | identisch mit `boiler_plant_2_secondary_heat` (Exportfehler) | nicht verwenden; GT-Wärme aus `gas_turbine_flow`·Δh, siehe `scripts/dhn_study/daten.erzeugung` |
| `gas_turbine_flow` | nur 35 % Abdeckung | Lücken imputieren und kennzeichnen |
| `pump_station_2_flow_return_to_center` | hängt in 2,5 % der Stunden bei 1078 | als Hängewert behandeln |
| `pump_station_2_flow_return_to_west`, `pump_station_1_flow_return_to_south` | 1 % bzw. 7 % Abdeckung | nicht verwenden |
| `boiler_plant_2_hx_heat` | 2 Stunden über 40 MW | Spitzen maskieren |

## Quellen und Lizenz

* **Mess- und Plandaten:** Netzbetreiber, anonymisiert. Verbraucher-, Gebiets- und Ortsnamen, Armaturennummern und absolute Höhen sind entfernt.
* **Außentemperatur:** Datenbasis Deutscher Wetterdienst (DWD Climate Data Center, Stundenwerte Lufttemperatur), Stationsangabe entfernt, in Ortszeit umgerechnet. Nutzung nach den DWD-Nutzungsbedingungen (CC BY 4.0, Quellenvermerk „Deutscher Wetterdienst“).

Restrisiko der Anonymisierung: Netzgröße, Anlagentypen und der Verlauf der Temperatur- und Lastreihen können für Insider auf das Netz schließen lassen.
