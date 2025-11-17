# Modellmethodik

Diese Notiz fasst die wichtigsten Elemente des MILP-Modells zusammen und verweist direkt auf die Pyomo-Formulierungen.

## Variablen
- **Netzflüsse**: Stündliche Stromzukäufe `P_buy` und Verkäufe `P_sell` sowie der Modus-Binärschalter `grid_mode` steuern den Strombus. 【F:energis/models/system_builder.py†L232-L238】【F:energis/models/system_builder.py†L279-L286】
- **Wärmenachfrage und Dumping**: `Q_dump` erlaubt Überschüsse in der Wärmebilanz abzuleiten. 【F:energis/models/system_builder.py†L234-L286】
- **Wärmepumpen**: Für jede HP entstehen Wärmestrom `HP*_Q`, WRG-Anteil `HP*_Q_wrg`, Backup-Anteil `HP*_Q_def`, Betriebsbinärvariablen `HP*_on` und Kapazität `HP*_cap_mw`. 【F:energis/models/blocks/heat_pump.py†L34-L92】
- **Speicher**: Energieinhalt `TES_E`, Lade-/Entladeleistungen `TES_Qc`/`TES_Qd`, Betriebsmodi (`charge_mode`, `discharge_mode`, `active`), Bauentscheidung `TES_build` sowie Energie- und Leistungskapazitäten. 【F:energis/models/blocks/storage.py†L43-L141】

## Constraints
- **Elektrische und thermische Bilanzen** setzen Netzflüsse, Erzeugung und Speicher mit Nachfrage bzw. Verkäufen gleich. 【F:energis/models/system_builder.py†L273-L286】
- **Netz-Kopplung** erzwingt wechselseitigen Ausschluss von Kauf und Verkauf über Big-M-Gates. 【F:energis/models/system_builder.py†L288-L291】
- **Wärmepumpen-Kapazitäten** koppeln Produktion an installierte Leistung, Mindestlast und WRG-Verfügbarkeit. 【F:energis/models/blocks/heat_pump.py†L66-L115】
- **Speicherdynamik** begrenzt Energie- und Leistungskapazitäten, sorgt für Moduskonsistenz und bildet den SOC-Fortschreibungszustand ab. 【F:energis/models/blocks/storage.py†L96-L137】【F:energis/models/blocks/storage.py†L139-L155】

## Objectives
Die Zielfunktion minimiert Energiekosten (Kauf/Verkauf), Dumping, Brennstoffe, CO₂-Kosten, Demand-Charges sowie Investitions-, Aktivierungs-, Tie-Breaker- und Installationskosten. 【F:energis/models/system_builder.py†L298-L336】

## Solverwahl
Der gewünschte Solver kommt aus der Laufkonfiguration (`run.solver`), wobei beim Szenariolauf ein Fallback auf `glpk` erfolgt, falls der angefragte Solver fehlt. Solver-Metadaten (Name, Status, Termination Condition) werden zusammen mit dem Ergebnis protokolliert. 【F:energis/run/rolling_horizon.py†L324-L337】【F:energis/run/rolling_horizon.py†L499-L533】

## YAML-Mappings
- **Zeitschritt und Solver**: `run.dt_h` und `run.solver` aus `configs/base.yaml` bestimmen Zeitschrittweite und Solverauswahl der Modellinstanz. 【F:configs/base.yaml†L1-L21】
- **Netz- und Kostenparameter**: Gebühren, Big-M-Wert und CO₂-Preis stammen aus `grid`- bzw. `costs`-Einträgen der Basisdatei und fließen direkt in die Parameter für Preisbildung, Demand Charge und CO₂-Term ein. 【F:configs/base.yaml†L18-L35】【F:energis/models/system_builder.py†L223-L271】
- **Systemlayout**: Komponentenlisten in `configs/systems/baseline.system.yaml` erzeugen Wärmepumpen-, Speicher- und Generator-Blöcke und definieren deren Investitionsgrenzen. 【F:configs/systems/baseline.system.yaml†L1-L82】【F:energis/models/system_builder.py†L240-L371】
- **Terminal-Policy**: Speicher-Grenzwerte, Wirkungsgrade und Terminalbedingungen werden aus `storage`-Abschnitten der Systemkonfiguration übernommen. 【F:configs/systems/baseline.system.yaml†L48-L60】【F:energis/models/system_builder.py†L320-L371】
