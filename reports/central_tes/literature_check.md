# Literature check of the techno-economic assumptions (2026-10-09)

Checked against current sources (DEA technology catalogues as updated in 2025/2026, German official data for 2025).
Consequences for the model: see `docs/dhn_storage_study/central_tes/model_and_deviations.md`, D17.

| # | Item | Before | Literature | Verdict → used now |
|---|---|---|---|---|
| 1a | Large HP investment | 0.8 M EUR/MW | DEA 2025: waste-heat HP 10 MW 0.91–0.95, air 1.02, seawater 0.94 M EUR/MW (+5 % for 40–80 °C networks) [1]; Agora/IEG 2023: 0.7–1.6 [2] | low → **0.95 M EUR/MW** (range 0.7–1.6) |
| 1b | HP lifetime | 20 a | DEA 25 a (15–40) [1] | kept 20 a (conservative) |
| 1c | Carnot fraction | 0.5 (0.4–0.6) | DEA/Agora/Arpagaus: 40–60 % (DEA as Lorenz efficiency; 43–50 % for installed plants) [1–3] | OK |
| 1d | High-lift COP / two-stage | flag > 70 K | Arpagaus: COP 2.2–2.8 at 70 K lift; DEA reference plants are double/two-stage units [1, 3] | supports the two-stage statement |
| 2 | Gas peak boiler | 0.1 M EUR/MW, 2 kEUR/MW/a, 25 a | DEA: 0.064 (0.043–0.27) M EUR/MW, 2.07–2.13 kEUR/MW/a, 25 a [1] | assumption at the upper-middle of the DEA range (incl. connection at the south end) → kept |
| 3a | Atmospheric tank | 160–260 EUR/m³ | DEA 2025 cost curve P = 3055·V^−0.309 (900–12 000 m³): ≈ 220 EUR/m³ at 5 000 m³, 177 at 10 000 m³ (≈ 143 at 20 000 m³ extrapolated); DEA 50 000 m³ case ≈ 250 EUR/m³ (scale advantage lost above ≈ 40 000 m³) [4] | used for the atmospheric comparison (AT) |
| 3b | Pressurised tank (≈ 120 °C) | 300 / 1 200 / 2 000 EUR/m³ | DEA: "significantly higher"; projects: 3 000 m³ ≈ 1 170 EUR/m³ (2014) [5]; 2 × 5 500 m³ up to 150 °C ≈ 1 800 EUR/m³ (2013) [6, 7] | lower bound not supported → **1 000 / 1 500 / 2 500 EUR/m³** (+0.1 M EUR) |
| 3c | TES lifetime, loss | 30 a, 0.01 %/h | DEA 40 a (30–50); 0.15 %/day at 5 000 m³ [4] | kept (conservative) |
| 4 | DN 400 pipe, urban | 2 500 EUR/m, 40 a | DEA city single line 25–100 MW: 2 862 EUR/m (2020 EUR) ≈ 3 300 EUR/m (2024); lifetime 45 a [8] | low → **3 000 EUR/m** |
| 5 | Gas price | 48 EUR/MWh | THE day-ahead 2025 mean 37.2 EUR/MWh [9]; network charge 5.6, storage levy ≈ 2.9 EUR/MWh [10–12] | OK: 48 = commodity ≈ 40 (EEX THE futures means for the 2025 delivery halves 44.7 / 35.5; day-ahead mean 37.2) + ≈ 8 (network charge, storage levy, metering) |
| 6 | EUA 2025 | 72 EUR/t | auction average 73.4–73.9 EUR/t [13, 14] | 2–3 % low; effect small (P: 100 EUR/t) → kept, stated |
| 7a | HP grid fee + levies | 38 EUR/MWh | levies 2025 ≈ 11–13 EUR/MWh + network charge 24 GWh case 42.8 (23.6–61.8) EUR/MWh [11, 15, 16] → 37–76 | reference = HV / reduced-fee case; **sensitivity 55 / 76 EUR/MWh** (PR) |
| 7b | EB electricity cost | 9 / 60 EUR/MWh | non-waivable levy floor ≈ 11.4 EUR/MWh [15, 16]; + network charge 42.8 (23.6–61.8) EUR/MWh for the industrial 24 GWh case [11] → **35 / 54 / 73 EUR/MWh**; demand charge avoidable under atypical grid use (§ 19 (2) 1 StromNEV) if the EB stays out of the DSO's high-load windows [21] | low case → **12 EUR/MWh**; reference 60 kept (upper half of the literature range 35–73; conservative for partner B); set BL: 35 / 54 / 73 (2026-10-12) |
| 8 | Waste-heat fee | 5 EUR/MWh | no German value; EWI 2025: negotiated split [17]; Danish cap 2025 ≈ 46 EUR/MWh for delivered heat [18] | assumption, sensitivity 0–20 |
| 9 | EB premium | 10–20 EUR/MWh (result) | no published values; DEA large electric boiler 0.07 M EUR/MW [1] | presented as model result |
| 10 | Δp limits | 4 bar KWK, 1.0–1.2 bar worst point | connection conditions: ≥ 0.2 bar at the house station [19]; utility connection conditions give network-specific values only (e.g. 0.4–2.0 bar available differential pressure, Δp_min 0.8 bar in a hot-water network [22]); FW 510 is water quality, not pressure [20] | no generic literature value for a plant-side Δp limit exists (re-checked 2026-10-12) → 4 bar = operator experience value, used only as a reported soft threshold and in X4; hard limits from pump curves, shutdown pressures and PN 25 (plan A); 1.0–1.2 bar conservative planning margin |

## References

1. Danish Energy Agency & Energinet. *Technology Data – Generation of Electricity and District Heating* (ch. 40 heat pumps, 41 electric boilers, 44 gas DH only; updated 2026). https://ens.dk/en/analyses-and-statistics/technology-data-generation-electricity-and-district-heating
2. Agora Energiewende (2023). *Roll-out von Großwärmepumpen in Deutschland* (with IEG), pp. 75–76. https://www.agora-energiewende.de/
3. Arpagaus C. et al. (2018). High temperature heat pumps: market overview, state of the art, research status, refrigerants, and application potentials. *Energy* 152, 985–1010.
4. Danish Energy Agency. *Technology Data – Energy Storage* (ch. 141 TTES, updated 2026). https://ens.dk/en/analyses-and-statistics/technology-data-energy-storage
5. stadt+werk (2014). "Wärme unter Druck" (3 000 m³ pressurised store, ≈ 3.5 M EUR). https://www.stadt-und-werk.de/meldung_18920_W%C3%A4rme+unter+Druck.pdf
6. vienna.at (2013). Report on 2 × 5 500 m³ pressurised DH storage tanks, 150 °C, 6–10 bar, ≈ 20 M EUR. https://www.vienna.at/innovative-technologie-wien-energie-waermt-mit-mega-thermoskannen/3781168
7. Fink C. et al., AEE INTEC (2023). *Steckbrief Großwärmespeicher – Marktentwicklung 2022*, BMK. https://nachhaltigwirtschaften.at/resources/iea_pdf/steckbrief-marktstatistik-2022-grosswaermespeicher.pdf
8. Danish Energy Agency. *Technology Data for Energy Transport* (ch. 113, 2025), tables 11 and 13. https://ens.dk/media/6440/download
9. EEX spot THE day-ahead 2025 daily prices. https://www.engie-deutschland.de/sites/engie-deutschland/files/2025-03/erdgas_eex-spotmarkt-handelstage_2025.pdf
10. THE gas storage levy 2025 (2.99 / 2.89 EUR/MWh). https://www.nusconsulting.com/energy-news/the-announces-gas-storage-levy-reduction-july-2025/
11. Bundesnetzagentur / Bundeskartellamt (2025). *Monitoringbericht 2025*, tables 27, 35, 66. https://data.bundesnetzagentur.de/Bundesnetzagentur/SharedDocs/Mediathek/Monitoringberichte/MonitoringberichtEnergie2025.pdf
12. Abolition of the gas storage levy from 2026 (4th EnWG amendment). https://www.nwb-experten-blog.de/abschaffung-der-gasspeicherumlage-sinken-jetzt-die-energiekosten-fuer-wirtschaft-und-verbraucher/
13. Umweltbundesamt / DEHSt (2026). Press release 01/2026. https://www.umweltbundesamt.de/presse/pressemitteilungen/emissionshandel-21-milliarden-euro-fliessen-in-den
14. KOBiZE (2025). *Analiza rynku CO2*, December 2025. https://dokumenty.kobize.pl/www/9_Analiza_rynku_CO2_grudzien_2025.pdf
15. German TSOs (netztransparenz.de, 2024). *Datenbasis zum Aufschlag für besondere Netznutzung 2025*. https://netztransparenz.de
16. Forvis Mazars (2025). StromStG reform and § 9b relief. https://www.forvismazars.com/de/en/who-we-are/news/press-media/newsletters/newsletter-steuern/newsletter-steuern-3-2025/stromstg-reform-2025-folgen-fuer-9b
17. Klaas A.-K., Walde M., Leibfritz T., EWI (2025). *Abwärmenutzung in Fernwärmenetzen*. https://www.ewi.uni-koeln.de/cms/wp-content/uploads/2025/10/251010_Abwaermenutzung-in-Fernwaermenetzen-Modellgestuetzte-Analyse-des-Systemwerts-exemplarischer-Abwaermeprofile.pdf
18. Forsyningstilsynet (2024). *Udmeldelse af prisloft for overskudsvarme 2025* (95 DKK/GJ). https://forsyningstilsynet.dk/
19. STAWAG (2026). *TAB Fernwärme*, § 5.2. https://www.stawag.de/fileadmin/stawag/content/Dokumente/Waerme/26-02-26_TAB.pdf
20. AGFW FW 510 (2022-07). https://dinmedia.de/en/technical-rule/agfw-fw-510/360391651
21. Stromnetzentgeltverordnung (StromNEV), § 19 (2) sentence 1 (atypical grid use). https://www.gesetze-im-internet.de/stromnev/__19.html — individual grid fees are under review in the BNetzA AgNes process.
22. Stadtwerke Kiel. *Technische Anschlussbedingungen Fernwärme*, sections 4.2 and 6.2. https://www.stadtwerke-kiel.de/fileadmin/user_upload/Medien/Dokumente/Produkte/Fernwaerme/tab-fernwaerme-anschlussbedingungen-stadtwerke-kiel.pdf

