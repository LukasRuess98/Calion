# data_audit.md

Automatisch erzeugt (§1). Datenbereinigungen und deterministische
Imputationen werden vollständig dokumentiert; sie erfolgen nicht still.

## Lebensmittelunternehmen (Schwarzwald) (`food`)

- Intervalle: 35040  (Jahr 2023)
- P_base,max (beobachtete Grundlastspitze im Lastgangjahr; Proxy für P_max,prev): 16,452.8 kW -> Proxy-Spannungsebene **ms**
- Wärmelast: mean=8,566.9 kW, max=18,840.0 kW, Summe=75,046.4 MWh_th/a
- Quality-Flags: `{'duplicates_dropped': 0, 'negative_base_intervals': 1, 'negative_base_export_kwh': 155.1, 'floor_clipped': 61, 'rows_before_year_filter': 35040, 'rows_out_of_year_dropped': 0, 'interval_count_mismatch': None}`
- Konfigurierte Hinweise: Ein Intervall mit negativer Electricity (-0.6204 MW, vermutlich Netzeinspeisung/Eigenerzeugung) wird als Einspeisung dokumentiert (Spalte p_export_kw, flags.negative_base_export_kwh) und der abrechnungsrelevante Netzbezug auf 0 kW gesetzt; eine Einspeisevergütung wird nicht modelliert. Wärmelast unverändert.

## Chemieunternehmen (Essen) (`chemistry`)

- Intervalle: 35136  (Jahr 2024)
- P_base,max (beobachtete Grundlastspitze im Lastgangjahr; Proxy für P_max,prev): 6,449.3 kW -> Proxy-Spannungsebene **ms**
- Wärmelast: mean=6,087.7 kW, max=13,813.9 kW, Summe=53,474.3 MWh_th/a
- Quality-Flags: `{'duplicates_dropped': 0, 'negative_base_intervals': 0, 'negative_base_export_kwh': 0.0, 'floor_clipped': 1471, 'rows_before_year_filter': 35136, 'rows_out_of_year_dropped': 0, 'interval_count_mismatch': None}`
- Konfigurierte Hinweise: Keine Auffälligkeiten (min/max plausibel, keine Lücken).

## Metallerzeugung (Schwarzwald) (`metal`)

- Intervalle: 35040  (Jahr 2023)
- P_base,max (beobachtete Grundlastspitze im Lastgangjahr; Proxy für P_max,prev): 722.9 kW -> Proxy-Spannungsebene **ns**
- Wärmelast: mean=29.1 kW, max=135.0 kW, Summe=254.5 MWh_th/a
- Quality-Flags: `{'duplicates_dropped': 0, 'negative_base_intervals': 0, 'negative_base_export_kwh': 0.0, 'floor_clipped': 4744, 'rows_before_year_filter': 35040, 'rows_out_of_year_dropped': 0, 'interval_count_mismatch': None}`
- Konfigurierte Hinweise: Minimalwert Heat kW ~7e-48 (numerisches Rauschen um 0) wird auf 0 geklippt (quality_flag=floor_clipped).

## Papierfabrik (Augsburg) (`paper`)

- Intervalle: 35040  (Jahr 2023)
- P_base,max (beobachtete Grundlastspitze im Lastgangjahr; Proxy für P_max,prev): 54,927.4 kW -> Proxy-Spannungsebene **hs_ms**
- Wärmelast: mean=26,571.5 kW, max=59,904.1 kW, Summe=232,766.8 MWh_th/a
- Quality-Flags: `{'duplicates_dropped': 0, 'negative_base_intervals': 0, 'negative_base_export_kwh': 0.0, 'floor_clipped': 5388, 'rows_before_year_filter': 70080, 'rows_out_of_year_dropped': 35040, 'interval_count_mismatch': None}`
- Konfigurierte Hinweise: Rohdatei enthält 2022 UND 2023 (70.080 Zeilen); es wird ausschließlich das Kalenderjahr 2023 verwendet (Filter auf load_year). Gleicher Floor-Clip wie Metall.
