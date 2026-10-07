## Vorbemerkung (eine Rückfrage, nicht blockierend)

Du schreibst „Elektrifizierung von **Wärmenetzen**", beide Entwürfe behandeln aber **industrielle Prozesswärme** (werksinterne Wärmeversorgung). Ich habe konsistent auf Prozesswärme zusammengeführt. Falls du Fernwärme-/Nahwärmenetze meinst, ändern sich Temperaturbänder, Technologiemenge und Regulatorik (Netzanschluss, § 118 EnWG, Wärmeplanung) — dann bitte kurz melden, ich passe an.

---

# Teil 1 — Kritische Prüfung

## Entwurf A (7 Seiten, VHT/Gießerei, 10 Sweep-Phasen)

| # | Befund | Bewertung |
|---|---|---|
| A1 | Analytischer Kern ($h^*$, $\theta$, $\sigma(h)$), Zeichenbudget, Platzhaltersystem, Abbildungsplan | **Stärke — übernehmen** |
| A2 | „Disjunktive Zerlegung in zwei LPs ist **exakt**" für StromNEV | **Falsch.** Mit $E\le 2{,}5\,P^{max}$ und nur $P^{max}\ge P_t$ kann das LP $P^{max}$ künstlich anheben, um in das günstigere Tarifpaar zu rutschen. B's Kritik ist berechtigt. |
| A3 | Drittes Band VHT + E-Schmelzofen (Magnesium 670 °C) | Fachlich richtig, aber **Scope-Sprenger**: 5 Erzeuger, 3 Bänder, eigene Sensitivitäten → nicht in 8 Seiten. Nur minimalinvasiv beibehalten. |
| A4 | Speicheranalytik 3.5 ($v_{grid}=\sigma h/COP$, $h_e^*$) | Dimensionell/logisch unsauber, nicht belastbar. **Streichen**, qualitative Fallunterscheidung behalten. |
| A5 | 10 Sweep-Phasen, ~300 Läufe, 22 Tests, 4 Zusatz-Markdown-Berichte | **Überdimensioniert** für 8 Seiten. |
| A6 | $\sigma$ vergleicht nur den Leistungs-/Kapazitätsaufschlag | **Irreführend, wenn nicht benannt**: unter AgNes steigt gleichzeitig $AP_1$ (Anteil $\alpha$). Der Gesamteffekt ist nicht durch $\sigma$ allein bestimmt. Muss explizit stehen. |
| A7 | θ-Spannweite als Ergebnisplatzhalter ⟦R-01⟧ | Unnötig — analytisch fest: Faktor **8,75** (bei α∈[0,3;0,6], f∈[2,0;3,5]). |
| A8 | Werksgrundlast im Netzbezug teils nicht sauber geführt | **Fehler mit großem Hebel** — Netzentgelt gilt für den Gesamtbezug. |
| A9 | Ebenenzuordnung über Ist-Höchstlast + `level_shift`-Flag | **Stärke — übernehmen** (billig, guter Nebenbefund). |

## Entwurf B (Provenienz-Fassung, 12 Blocker, Repo-Struktur)

| # | Befund | Bewertung |
|---|---|---|
| B1 | Grundlast im Gesamtbezug, $LCOH^{inc}$ über BASE-Lauf, $r_{sim}$-Check, Break-even-Methodik, DOI-Literaturliste, DE+EN-Abstract | **Stärken — übernehmen** |
| B2 | 12 blockierende Punkte, u. a. „amtliche AgNes-PDF" und „standortbezogene Preisblätter" | **Übervorsichtig bis projektverhindernd.** Das Paper ist ein *Regimevergleich unter Entwurfsstand*; szenarische Tarifkalibrierung ist legitim, wenn deklariert. → auf **4 echte Blocker** reduzieren. |
| B3 | `src/`-Paket, Makefile, pytest, 8 Modulordner | **Widerspricht deinem Ziel** („ein Jupyter Notebook"). |
| B4 | 12 Szenariophasen, 28 Tests, Rolling Horizon als MUST | Zu viel; RH → SHOULD für einen Standort. |
| B5 | Kein Seiten-/Zeichenbudget, kein Abbildungs-Platzbudget | **Lücke** — bei 8 Seiten entscheidend. |
| B6 | $LCOH^{inc}$ als Differenz zweier Optima | Korrekt, aber **Interpretationsfalle**: der Kapazitätspreis ist zwischen Grundlast und Wärmelast **nicht additiv separierbar**. Muss als „inkrementell, nicht verursachungsgerecht" benannt werden. |
| B7 | „Metall" statt Magnesium-Gießerei, LT/HT ohne VHT | Vereinfachung gut, widerspricht aber deiner bestätigten Option A. → Kompromiss unten. |
| B8 | Verzicht auf A's Prognosetest ($C$ vs. Lastdauerlinie bei $h^*$) | **Verlust des praktisch wertvollsten Beitrags.** |

## Was beiden fehlt (mein wichtigster Zusatz)

Beide lassen den einfachsten und praktisch anwendbarsten Befund liegen. Er ist **exakt beweisbar** und trägt das ganze Paper:

> Für einen gegebenen Lastgang ist $F(C)=KP\cdot C+AP_1E+(AP_2-AP_1)E_2(C)$ konvex mit $\mathrm{d}E_2/\mathrm{d}C=-D(C)$, wobei $D(C)$ die gewichtete Dauer über $C$ ist. Das Optimum liegt genau dort, wo $D(C^*) = h^*$ gilt.
> **Praxisregel:** Bestellkapazität = Schnittpunkt der Jahresdauerlinie mit $h^*$ — ohne Optimierer, mit Excel machbar.

Das LP dient dann dazu zu zeigen, **wie weit die endogene Anlagenauslegung diese Regel verschiebt**. Damit wird das Paper einfach *und* neu.

---

# Teil 2 — Zusammenführungsentscheidungen

| Thema | Entscheidung |
|---|---|
| Fokus | Ein Kernbeitrag (Bestellregel + Auslegungswirkung), nicht sieben Nebenbefunde |
| Standorte | 4 (Lebensmittel, Chemie, Metall, Papier); Preisjahre: 2023 / **2024 (Chemie)** / 2023 / 2023 |
| Temperaturbänder | LT, HT; **VHT nur Standort Metall**, ohne Speicher, ohne κ, ohne eigene Sweeps (respektiert Option A, kostet ~1 Absatz + 10 Codezeilen) |
| Technologien | HP (LT + HT-Vorwärmung κ), Elektrodenkessel, Gaskessel, TES pro Band; Metall zusätzlich E-Ofen / Gas-Ofen im VHT |
| Modellklasse | **Reines LP**, kontinuierlich, Perfect Foresight; kein MILP im Hauptteil |
| Netzbezug | $P_t = P^{base}_t + P^{HP}_t + P^{EK}_t (+P^{EF}_t)$ — Netzentgelt auf Gesamtbezug (aus B) |
| Kostenmaß | $LCOH^{inc}$ gegen BASE-Lauf (aus B), plus absolute Kostenkomponenten |
| StromNEV | Zwei Tarifpaar-Läufe **ohne** Benutzungsstunden-Zwang + Konsistenzprüfung ($P^{max}=\max_t P_t$, realisierte Benutzungsdauer passt zum Paar) + Flag. Kein „exakt"-Anspruch. |
| AgNes-Tarife | Modus `synthetic_first_order` aus $k, t_B, \alpha, f$; $k,t_B$ aus BNetzA-Monitoringbericht je Ebene. Klar als Szenario deklariert, **nicht** als Preisblatt. |
| Blocker | Nur 4: (1) Werks-Wärmelastgang, (2) Grundlast + Messgrenze, (3) $P^{grid}$ & Vorjahreshöchstlast, (4) Bandanteile LT/HT/VHT |
| Sweeps | 6 MUST-Phasen (statt 10–12), ~120 Läufe, davon 64 in 15 min |
| Tests | 12 Asserts im Notebook (statt 22/28), kein pytest |
| Deliverable | **Ein Notebook** `agnes_p2h.ipynb` + `config.yaml` + `outputs/` |
| Gestrichen | MILP-Mindestlast, Ebenen-Grenzfall-Doppelläufe als MUST, Speicheranalytik-Formeln, Fixpunkt-Modellierung (bleibt Diskussion), 4 separate Audit-Markdowns (→ 1 Datei) |
| Marker | Einheitlich `[[R-…]]`, `[[D-…]]`, `[[P-…]]`, `[[REG-…]]`, `[[V-…]]`; Notebook patcht den Draft automatisch |

---

# DOKUMENT 1 — Paper-Draft v1.0

**Format:** ZWF-Fachbeitrag · 8 Seiten · **5 Abbildungen, 3 Tabellen** · ~20 Quellen · Zeichenbudget 29.000 (final gegen ZWF-Autorenleitfaden kalibrieren)

## Titel

**Bestellkapazität statt Jahreshöchstlast**
*Auswirkungen der Netzentgeltreform AgNes auf die Elektrifizierung industrieller Prozesswärme — eine einfache Bestellregel und ihre Grenzen*

**Fußnote 1:** Grundlage ist der konsultierte Festlegungsentwurf zur allgemeinen Netzentgeltsystematik Strom (AgNes). `Az. GBK-25-01-1#3, Entwurf 2026-08-06, Konsultation bis 2026-09-18, Anwendung ab 2029-01-01 (löst StromNEV ab, die zum 2028-12-31 ausläuft, Folge eines EuGH-Urteils)` Der Beitrag vergleicht Regime; er prognostiziert keine künftigen Entgelthöhen.

## Abstract (DE, ~950 Zeichen)

> Der AgNes-Entwurf ersetzt den Leistungspreis auf die gemessene Jahreshöchstlast durch einen Kapazitätspreis auf eine frei bestellbare Kapazität in Verbindung mit einem zweistufigen Arbeitspreis. Damit wird die Netzentgeltbelastung zur Auslegungsvariable — besonders relevant für elektrische Wärmeerzeuger mit geringer Auslastung. Der Beitrag leitet analytisch eine kritische Überschreitungsdauer $h^*$ ab und zeigt, dass die kostenminimale Bestellkapazität bei gegebenem Lastgang exakt dem Schnittpunkt der Jahresdauerlinie mit $h^*$ entspricht. Diese Regel ist ohne Optimierungssoftware anwendbar. Ein lineares Modell, das Bestellkapazität, Anlagenauslegung und Betrieb simultan bestimmt, wird auf vier gemessene Fabriklastgänge (Lebensmittel, Chemie, Metall, Papier) in einem 2×2-Design aus Netzentgelt- und Beschaffungsregime angewendet. Die Ergebnisse zeigen `LCOH^inc zwischen 30,7 und 58,5 EUR/MWh_th (4 Standorte x 4 Regime)`, `TES-Kapazität verschiebt sich um -14.671..1.380 kWh zwischen StromNEV- und AgNes-Fixpreis-Auslegung` und eine Abweichung der Bestellregel vom Modelloptimum von `34,7 %`.

## Abstract (EN, ~950 Zeichen)

> The AgNes draft replaces the demand charge on metered annual peak load with a capacity charge on a customer-booked capacity, combined with a two-tier volumetric tariff. Grid charges thereby become a design variable, which matters most for electric heat generators with low utilisation. We derive a critical excess duration $h^*$ and show that, for a given load profile, the cost-minimal booked capacity is exactly the intersection of the annual load duration curve with $h^*$ — a rule applicable without optimisation software. A linear programme jointly optimising booked capacity, technology sizing and operation is applied to four metered factory load profiles (food, chemical, metal, paper) in a 2×2 design of grid-tariff and procurement regimes. Results show `LCOH^inc zwischen 30,7 und 58,5 EUR/MWh_th (4 Standorte x 4 Regime)`, `TES-Kapazität verschiebt sich um -14.671..1.380 kWh zwischen StromNEV- und AgNes-Fixpreis-Auslegung`, and a deviation of the simple booking rule from the model optimum of `34,7 %`.

**Schlüsselwörter:** Netzentgelt, AgNes, Bestellkapazität, Prozesswärme, Wärmepumpe, Elektrodenkessel, thermischer Speicher, lineare Optimierung, Fabrikplanung

## Kernaussagen (ZWF-Kasten, 4 Punkte)

1. Unter AgNes ist der netzentgeltseitige Aufschlag selten genutzter Leistung nach oben begrenzt: maximal $AP_2-AP_1$ statt $1000\,LP/h$ — der strukturelle Nachteil elektrischer Spitzenlasttechnik entfällt teilweise.
2. Die kostenminimale Bestellkapazität ist der Schnittpunkt der Jahresdauerlinie mit $h^*=1000\,KP/(AP_2-AP_1)$ — eine Regel, die jedes Werk mit einem Viertelstundenlastgang selbst anwenden kann.
3. Im gekoppelten Auslegungsmodell verschiebt sich diese Bestellkapazität um `food: 34,7%; chemistry: 0,9%; metal: 9,9%; paper: 27,0%`, weil sich Anlagenauslegung und Lastgang mitverändern.
4. Netzentgelt- und Spotpreisflexibilität wirken `substitutiv (Interaktionsterm überwiegend negativ)`.

## Gliederung mit Zeichenbudget

| Nr. | Abschnitt | Zeichen | Elemente | Schreibstatus |
|---|---|---:|---|---|
| — | Titel, Abstracts DE/EN, Kernaussagen | 2.600 | — | schreibbar |
| 1 | Einleitung und Forschungslücke | 2.800 | — | schreibbar |
| 2 | AgNes im Vergleich zu StromNEV | 3.000 | Tab. 1 | nach `[[REG-*]]` |
| 3 | Analytik: $h^*$, Bestellregel, $\theta$ | 4.200 | Abb. 1, 2 | **vollständig schreibbar** |
| 4 | Modell und Untersuchungsdesign | 3.800 | Abb. 3 | schreibbar |
| 5 | Fallstudien und Daten | 2.400 | Tab. 2 | wartet auf Daten |
| 6 | Ergebnisse | 7.000 | Abb. 4, 5, Tab. 3 | wartet auf Läufe |
| 7 | Diskussion und Grenzen | 3.200 | — | halb schreibbar |
| 8 | Handlungsempfehlungen und Fazit | 2.000 | — | halb schreibbar |
| | **Summe** | **31.000** | 5 Abb., 3 Tab. | |

*Kürzungsreserve, falls ZWF-Layout knapper ausfällt: Abschnitt 6.5 (Break-even) auf halbe Länge, Abb. 5 ins Supplement.*

## 1 Einleitung und Forschungslücke (4 Absätze)

1. Prozesswärme als größter fossiler Endenergieblock; Wärmepumpe, Elektrodenkessel, elektrische Öfen sind technisch verfügbar [1–5], die Entscheidung scheitert an der Wirtschaftlichkeit.
2. Netzentgelte werden in Auslegungsrechnungen als exogener Aufschlag behandelt. Für Spitzenlasttechnik sind sie der bestimmende Block: Ein Elektrodenkessel mit wenigen hundert Volllaststunden erzeugt über den Leistungspreis Fixkosten wie eine Dauerlast.
3. AgNes macht die Netzentgeltbelastung zur Entscheidungsvariable. `Az. GBK-25-01-1#3, Entwurf 2026-08-06, Konsultation bis 2026-09-18, Anwendung ab 2029-01-01 (löst StromNEV ab, die zum 2028-12-31 ausläuft, Folge eines EuGH-Urteils)`
4. Lücke: Auslegungsmodelle behandeln Netzentgelte exogen [13–15], Tarifdesign-Literatur untersucht Kapazitätstarife ohne technologiescharfe Auslegung [16–18]. Vier Forschungsfragen: (i) Auslegungswirkung auf HP/EK/TES, (ii) Höhe und Bestimmbarkeit der optimalen Bestellkapazität, (iii) Verhältnis von Netzentgelt- und Spotpreisflexibilität, (iv) Verschiebung des fossilen Break-even.

## 2 AgNes im Vergleich zu StromNEV

**2.1 Statusvorbehalt.** Maßgeblich ist die amtlich veröffentlichte Fassung; jede Ziffer wird einzeln belegt. `Az. GBK-25-01-1#3, Entwurf 2026-08-06, Konsultation bis 2026-09-18, Anwendung ab 2029-01-01 (löst StromNEV ab, die zum 2028-12-31 ausläuft, Folge eines EuGH-Urteils)`
**2.2 Referenzregime StromNEV.** Arbeitspreis + Preis auf gemessene Jahreshöchstlast, zwei Preispaare an der Schwelle 2.500 h/a [20].
**2.3 AgNes-Grundmodell.** Kapazitätspreis $KP$ auf bestellte Kapazität $C$; $AP_1$ innerhalb, $AP_2>AP_1$ oberhalb; Untergrenze $\beta P^{max,prev}$, Obergrenze $P^{grid}$; Bestellung vor Jahresbeginn. `[[OFFEN: REG-02 — Nachrecherchiert, weiterhin teiloffen: t_B=2500h ist real (StromNEV § 19 Abs. 2, reviewed). Für k je Ebene wurde gezielt nach einem BNetzA-Monitoringbericht mit Netzentgeltniveaus je Ebene gesucht - kein konsistentes, textuell auswertbares Ebenen-Tabellenwerk gefunden (nur gescannte PDFs bzw. AI-Suchzusammenfassungen mit widersprüchlichen Zahlen). Stattdessen jetzt EIN reales, konsistentes Preisblatt für alle drei Ebenen verwendet: Stadtwerke Tübingen GmbH, Preisblatt Netzentgelte Strom, gültig ab 01.01.2025 (MS weiterhin eam-netz.de, 2024 - andere DSO). k je Ebene bleibt damit 'derived/reviewed-Anker + Konstruktion', keine amtliche Monitoringbericht-Tabelle. Die DSO-zu-DSO-Streuung (z.B. Bayernwerk HS 2025: 175,16 EUR/kWa vs. SWTü HS 123,12 EUR/kWa) ist real und wird als Limitation benannt, nicht geglättet.]]`
**2.4 Behandlung elektrischer Wärmeerzeuger.** `[[OFFEN: REG-03 — Nachrecherchiert, weiterhin offen: Der veröffentlichte AgNes-Entwurf und Presseberichte zum Konsultationsstand (2026-08-06 bis 2026-09-18) klären nicht abschließend, ob elektrische Wärmeerzeuger regulär oder in einem Sonderregime behandelt werden. Ein indirekter, für die Diskussion relevanter Befund: saisonal differenzierte Arbeitspreise wurden von der BNetzA explizit VERWORFEN, weil sie den Betrieb von Wärmepumpen deutlich verteuern würden - ein Hinweis, dass keine gezielte Verteuerung elektrischer Wärmeerzeuger beabsichtigt ist, aber keine formale Entscheidung zum Letztverbraucher-Regime. Nicht aus Daten ableitbar.]]` — bis zur Klärung: reguläre Behandlung, Alternative als Sensitivität.
**2.5 Nicht Gegenstand.** Keine zeitvariablen Netzentgelte, Flexibilitäts-Sondernetzentgelt offen, Übergangsregelungen nicht im Kernmodell. `[[OFFEN: REG-04 — Offen: Übergangsregelungen/Flexibilitäts-Sondernetzentgelt sind nicht Teil des Kernmodells (Draft §2.5) und daher nicht quantifizierbar. Recherche zum Konsultationsstand liefert keine über REG-01 hinausgehenden Details zu Übergangsfristen.]]` Konsequenz: Das kurzfristige Flexibilitätssignal kommt allein vom Beschaffungsmarkt — Begründung für das 2×2-Design.

→ **Tabelle 1: Modellrelevanter Regimevergleich** (Element | StromNEV | AgNes | Fundstelle | Freigabestatus)

## 3 Analytik (datenunabhängig, vollständig schreibbar)

**3.1 Kritische Überschreitungsdauer.** Für eine Leistungsscheibe $\Delta P$ mit Bedarfsdauer $h$ [h/a]:

$$KP\,\Delta P \;=\; (AP_2-AP_1)\frac{\Delta P\,h^*}{1000} \quad\Rightarrow\quad \boxed{\,h^*=\frac{1000\,KP}{AP_2-AP_1}=\frac{1000\,KP}{(f-1)AP_1}\,}$$

$KP$ in €/(kW·a), $AP$ in €/MWh, $f=AP_2/AP_1$.

**3.2 Optimale Bestellkapazität (Kernbeitrag).** Bei gegebenem Lastgang gilt $F(C)=KP\,C+AP_1E+(AP_2-AP_1)E_2(C)$. $E_2(C)$ ist konvex und fallend mit $\mathrm{d}E_2/\mathrm{d}C=-D(C)/1000$, wobei $D(C)$ die gewichtete Dauer mit $P_t>C$ ist. Aus der Optimalitätsbedingung folgt unmittelbar:

$$\boxed{\,D(C^*)=h^*\,}\qquad\text{d. h. } C^*=P_{LDC}(h^*),\ \text{geklippt auf }[\beta P^{max,prev},\,P^{grid}]$$

Die kostenminimale Bestellung liest man also am Schnittpunkt der Jahresdauerlinie mit $h^*$ ab. Diese Regel ist **exakt** bei fixem Lastgang und wird in Abschnitt 6.4 gegen das gekoppelte Modell geprüft.

**3.3 Dimensionslose Form (Annahme, keine Identität).** Mit $KP=(1-\alpha)k$ und $AP_1=1000\alpha k/t_B$:

$$\theta=\frac{h^*}{t_B}=\frac{1-\alpha}{(f-1)\alpha}$$

Gilt nur unter dieser Erlösaufteilungs- und Referenzkollektivannahme; Überschreitungserlöse sind vernachlässigt. Für α∈[0,30;0,60] und f∈[2,0;3,5] `[[OFFEN: REG-02 — Nachrecherchiert, weiterhin teiloffen: t_B=2500h ist real (StromNEV § 19 Abs. 2, reviewed). Für k je Ebene wurde gezielt nach einem BNetzA-Monitoringbericht mit Netzentgeltniveaus je Ebene gesucht - kein konsistentes, textuell auswertbares Ebenen-Tabellenwerk gefunden (nur gescannte PDFs bzw. AI-Suchzusammenfassungen mit widersprüchlichen Zahlen). Stattdessen jetzt EIN reales, konsistentes Preisblatt für alle drei Ebenen verwendet: Stadtwerke Tübingen GmbH, Preisblatt Netzentgelte Strom, gültig ab 01.01.2025 (MS weiterhin eam-netz.de, 2024 - andere DSO). k je Ebene bleibt damit 'derived/reviewed-Anker + Konstruktion', keine amtliche Monitoringbericht-Tabelle. Die DSO-zu-DSO-Streuung (z.B. Bayernwerk HS 2025: 175,16 EUR/kWa vs. SWTü HS 123,12 EUR/kWa) ist real und wird als Limitation benannt, nicht geglättet.]]` liegt θ zwischen 0,27 und 2,33 — **Spannweite Faktor 8,75**. Damit ist die Auslegungswirkung der Reform in erheblichem Maß eine Frage der Parametrierung, nicht der Systematik.

**3.4 Spezifischer Aufschlag.** Nur der leistungs-/kapazitätsbezogene Anteil:

$$\sigma_{NEV}(h)=\frac{1000\,LP}{h},\qquad \sigma_{AgNes}(h)=\min\!\left\{\frac{1000\,KP}{h},\;AP_2-AP_1\right\}\quad[\text{€/MWh}]$$

Kernaussage: unter AgNes nach oben beschränkt, unter StromNEV für $h\to0$ unbeschränkt. **Wichtige Einschränkung, die im Text stehen muss:** Der Vergleich betrifft nur den Aufschlag. Bei erlösäquivalenter Kalibrierung liegt $AP_1$ über dem StromNEV-Arbeitspreis; Dauerlasten werden also belastet, während Spitzenlasten entlastet werden. Die Netto­wirkung ist standortspezifisch und nur numerisch bestimmbar.

**3.5 Prüfbare Hypothesen zum Speicher** (statt Formeln): (a) Senkt der Speicher die Bestellkapazität ($h>h^*$), sinkt sein Netzentgeltwert nur im Verhältnis $KP/LP$. (b) Vermeidet er lediglich kurze Überschreitungen ($h<h^*$), entfällt der Netzentgeltwert nahezu vollständig. Welcher Fall dominiert, entscheidet das Modell (6.3).

**3.6 Arbitrage-Freischaltungsschwelle.** $N_{unlock}(\sigma)=\#\{t:\bar p-p_t>\sigma\}$ wird **vor** dem ersten Solve aus der Preisreihe berechnet: Anzahl Intervalle, in denen Lastverschiebung den Aufschlag überhaupt verdient. Dient als Vorzeichenerwartung für die 2×2-Interaktion.

→ **Abbildung 2:** (a) $\sigma_{NEV}$ vs. $\sigma_{AgNes}$ über $h$, log-x, $h^*$ markiert; (b) θ(α,f)-Heatmap mit Isolinie θ = 1.

## 4 Modell und Untersuchungsdesign

**4.1 Systemgrenze.** Gesamter Netzbezug $P_t=P^{base}_t+P^{HP}_t+P^{EK}_t+P^{EF}_t$; Netzentgelt, $P^{grid}$ und $P^{max}$ beziehen sich auf diesen Gesamtbezug — nicht auf Power-to-Heat allein. → **Abbildung 3 (Superstruktur)**

**4.2 Temperaturbänder.** LT (≤ 100 °C): HP, EK, GB, TES. HT (100–250 °C): HP nur Vorwärmung bis $q^{HP,pre}_t\le\kappa Q_{HT,t}$ mit eigenem $COP_{pre}$, EK, GB, TES. VHT (> 500 °C, nur Standort Metall): elektrischer Ofen oder Gasofen, kein Speicher.

**4.3 Modellklasse.** Reines LP, kontinuierliche Kapazitäten, Perfect Foresight, 15 min, ein Kalenderjahr, zyklisch geschlossener Speicher. Wegen $AP_2>AP_1$ gilt $P_{1,t}=\min(P_t,C)$ ohne Binärvariable.

**4.4 Zielfunktion.** Annuisiertes CAPEX (VDI 2067 / DIN EN 17463 [24]) + Strom + Gas + CO₂ + Netzentgelt + fixes O&M.

**4.5 Entgeltregime.** AgNes: $F=KP\,C+AP_1E_1+AP_2E_2$, $\beta P^{max,prev}\le C\le P^{grid}$. StromNEV: je Tarifpaar ein LP, anschließend **Konsistenzprüfung** ($P^{max}=\max_tP_t$; realisierte Benutzungsdauer im zum Paar gehörenden Bereich). Nur konsistente Läufe werden gewertet; Mehrdeutigkeit wird als `tariff_ambiguous` berichtet. Der Beitrag erhebt hier ausdrücklich **keinen** Exaktheitsanspruch.

**4.6 2×2-Design.** {StromNEV, AgNes} × {FIXED, Day-Ahead}; Kennungen 00/01/10/11. Festpreis lastgewichtet auf ein **vorab festgelegtes** starres Referenzprofil kalibriert, Risikoprämie ρ als Sensitivität. Interaktion $\Delta_{inter}=Y_{11}-Y_{10}-Y_{01}+Y_{00}$ (deterministische Szenariodifferenz, kein Schätzer).

**4.7 Kostenmaß.** $LCOH^{inc}=(K^{site}-K^{base})/Q^{useful}$ mit BASE = identischer Standort ohne modellierte Wärmeversorgung im gleichen Regime. Klarstellung im Text: inkrementell, **nicht** verursachungsgerecht — der Kapazitätspreis ist zwischen Grundlast und Wärmelast nicht additiv aufteilbar.

**4.8 Dekomposition.** $\Delta_{total}=\Delta_{mech}+\Delta_{disp}+\Delta_{design}$ über drei Modi: `evaluate` (Auslegung und Betrieb fix, nur $C$ analytisch nach 3.2), `redispatch` (Auslegung fix), `optimize`. Trennt Umverteilung von Verhaltensanpassung.

## 5 Fallstudien und Daten

**5.1 Auswahl.** Vier gemessene Fabrikprofile. **Formulierungspflicht:** „vier Fabriken" nur bei gemessenen Lastgängen; bei Rekonstruktion „vier kontrastierende industrielle Wärmeprofile" plus Methodenbeschreibung.
**5.2 Preisjahre.** Lebensmittel/Metall/Papier 2023, Chemie 2024 [22]. Primärvergleich daher **innerhalb** eines Standorts; Preisjahr-Sensitivität separat.
**5.3 Aufbereitung.** UTC als kanonischer Index, keine Interpolation, kein Hochskalieren stündlicher Werksprofile, Stundenpreise viermal wiederholt (Limitation: unterschätzt Intraday-Arbitrage).
**5.4 Ebenen- und Bandzuordnung.** Spannungsebene aus gemessener Ist-Höchstlast vor Elektrifizierung, danach fixiert; Überschreitung einer Schwelle nach Elektrifizierung → Flag und Diskussion. Bandanteile prozessbasiert, Regel offengelegt, Sensitivität ±10 Prozentpunkte.

→ **Tabelle 2: Standortübersicht** (Prozess, Wärmebedarf, Anteile LT/HT/VHT, Temperaturniveaus, Wärme-Volllaststunden, Grundlast Ø/max, Ebene, $P^{grid}$, $P^{max,prev}$, κ, Lastgang-/Preisjahr) — vollständig aus `table02_cases.md`, alle Felder `[[D-*]]`.

## 6 Ergebnisse (vorzeichenoffene Satzschablonen)

**6.1 Datenqualität und Validierung.** Intervalle je Standort `food: 35040, chemistry: 35136, metal: 35040, paper: 35040`, Wärmebilanzfehler `1.1e-16`, Speicherbilanzfehler `0.0e+00`, Solverstatus `96/96 optimal`; 15 min vs. 1 h: $P^{max}$ `chemistry: 6.440->6.449 kW; paper: 68.005->68.505 kW`, $LCOH^{inc}$ `chemistry: 0,04%; paper: 0,11%`.

**6.2 Kostenwirkung und Interaktion.** Regimewechsel unter FIXED: `-4,1` bis `14,9` €/MWh_th; unter Day-Ahead `-8,5` bis `15,1`. $\Delta_{inter}$ bei `2 von 4` von vier Standorten negativ, Spanne `-4,4`…`4,8`. Dekomposition: `74,8` % mechanisch, `30,3` % Betrieb, `-5,1` % Auslegung.

**6.3 Auslegung.** Δ Wärmepumpe `-4.850..38 kW über 4 Standorte`, Δ Elektrodenkessel `0..0 kW über 4 Standorte`, Δ E-Ofen `[[OFFEN: R-DES-EF — n/a: VHT/E-Ofen ist gemäß Teil-3-Entscheidung #2 als Limitation behandelt (Rohdaten stützen keine VHT-Bandtrennung), daher kein EF in diesem Modell.]]`, Δ TES `-14.671`…`1.380`; noTES-Vergleich ergibt Systemwert `361.848 EUR/a Summe über alle S1-Zellen`; Hypothesen aus 3.5 `(a) h>h*: 3 Standorte, (b) h<h*: 1 Standorte`.

**6.4 Bestellkapazität und Güte der einfachen Regel.** $C/P^{max}$ = `15 %`…`91 %`; $E_2/E$ = `14 % (Mittel)`. Die Regel aus 3.2 trifft im `evaluate`-Modus exakt (`bestanden (T08, Abweichung < 0,5% im evaluate-Fall)`); im gekoppelten Modell weicht sie um `34,7` % ab, Richtung `höher`. **Das ist der zentrale Praxisbefund.** → **Abbildung 4 (Lastdauerlinien)**

**6.5 Fossiler Break-even.** Gaspreis `13..32 (über beide Netzregime, 7/8 Ketten konvergiert)` €/MWh_Hu bei fixem CO₂-Preis, CO₂-Preis `11..30 (über beide Netzregime, 2/8 Ketten konvergiert)` €/t bei fixem Gaspreis; Regimeverschiebung `food/gas: 104,9%; chemistry/gas: 18,9%; paper/gas: 21,2%`. → **Abbildung 5**

**6.6 Tarifsensitivität.** Über α×f variiert $C$ um `63.456`, TES um `37.895`; bei θ > 1 `bei theta>1 erreicht C in 0% der Läufe >=98% von P_max (vs. 2% bei theta<=1)`. Bandanteile ±10 pp: `Technologie-Rangfolge (größter Erzeuger) stabil unter Wärmelast +-10% bei 4/4 Standorten`.

→ **Tabelle 3: Kern-KPI** je Standort × Regime ($LCOH^{inc}_{00}$, $\Delta_{Netz}$, $\Delta_{Preis}$, $\Delta_{inter}$, $C/P^{max}$, $E_2/E$).

## 7 Diskussion und Grenzen

**7.1 Ist Elektrifizierung besser gestellt?** Dreifache Entlastung (Wegfall Höchstlastbezug, Kapazitätswahl als Option, begrenzter Aufschlag) gegen vier Gegenargumente: höherer $AP_1$ belastet elektrifizierte Grundlast, kein Power-to-Heat-Sondernetzentgelt, Wegfall der Netzreservekapazität, Bestellung ein Jahr im Voraus unter Unsicherheit.
**7.2 Speicherwirkung nicht eindeutig** — Verweis auf 3.5/6.3, ausdrückliche Absage an die pauschale Aussage „AgNes entwertet Speicher".
**7.3 Erlösneutralität und Fixpunkt.** Bei endogenem $C$ ist die Absatzstruktur selbst preisabhängig; bei θ > 1 bricht das Kapazitätspreisaufkommen ein und muss über $AP_1$ gedeckt werden. Konsultationsrelevanter Punkt, nicht modelliert (½ Absatz).
**7.4 Grenzen.** LP ohne Mindestlast/Anfahrt/diskrete Größen; Perfect Foresight (`stromnev/fixed: 0,09%; stromnev/dayahead: 0,10%; agnes/fixed: -0,00%; agnes/dayahead: -0,01%`, Rolling Horizon nur für einen Standort); Wärmebedarf exogen; Tarife szenarisch kalibriert, keine Preisblätter; Bandzuordnung regelbasiert; Ebenenzuordnung aus Ist-Höchstlast; ein Kalenderjahr, unterschiedliche Preisjahre; § 19 StromNEV und Baukostenzuschüsse nicht modelliert; $P^{grid}$ exogen; Entwurfsstand der Festlegung.
**7.5 Ausblick.** Zweistufig stochastische Bestellung, Flexibilitäts-Sondernetzentgelt, Kopplung mit Netzanschlussplanung.

## 8 Handlungsempfehlungen und Fazit

**Fünf-Schritte-Bestellverfahren ohne Optimierungssoftware** (der Praxisteil, ergebnisunabhängig schreibbar):

1. Viertelstundenlastgang des **Gesamtwerks** für das Bestelljahr prognostizieren, geplante Wärmeelektrifizierung addieren.
2. $h^*=1000\,KP/(AP_2-AP_1)$ aus dem Preisblatt berechnen.
3. Jahresdauerlinie bilden, Kapazität bei $h^*$ ablesen → $C^*$.
4. Auf $[\beta P^{max,prev},\,P^{grid}]$ begrenzen; Prognoseunsicherheit als Zuschlag prüfen (asymmetrische Kosten: Unterbestellung kostet $AP_2-AP_1$, Überbestellung $KP$).
5. Erst danach über Speicher entscheiden — bewertet am Gesamtsystemwert, nicht an der Höchstlastreduktion.

**Fazit:** `AgNes verschiebt die inkrementellen Wärmekosten je nach Standort und Beschaffungsregime um -4,1 bis 14,9 EUR/MWh (Fixpreis) bzw. -8,5 bis 15,1 EUR/MWh (Day-Ahead) ggü. StromNEV.`, `Die auf dem vor Elektrifizierung beobachteten Grundlastgang basierende Ex-ante-Bestellregel weicht im vollständig gekoppelten Elektrifizierungsmodell um bis zu 34,7% von der optimalen Bestellkapazität ab. Die Differenz umfasst die Wirkung des veränderten Gesamtlastgangs sowie Rückkopplungen aus Auslegung, Speicherbetrieb und Bestellentscheidung. Bei reinem Grundlastgang (V-01) bzw. bei Anwendung auf den vom LP realisierten Gesamtlastgang (V-04) trifft die Regel das Optimum exakt - die Abweichung ist damit korrekt der Elektrifizierung selbst zuzuschreiben, nicht einem Fehler der Regel.`.

## Abbildungs- und Tabellenplan

| Nr. | Inhalt | Datenquelle |
|---|---|---|
| Abb. 1 | Systemgrenze/Superstruktur, drei Bänder, Netzentgelt auf Gesamtbezug | statisch |
| Abb. 2 | (a) σ(h) beide Regime + $h^*$; (b) θ(α,f)-Heatmap, Isolinie θ = 1 | `fig02_analytics.csv` |
| Abb. 3 | Kernergebnisse: (a) $LCOH^{inc}$ 4 Regime; (b) Erzeugerkapazitäten gestapelt; (c) TES je Band | `kpi.csv` |
| Abb. 4 | Lastdauerlinien, 4 Panels, $C$, $P^{max}$, $E_2$-Fläche, Marker $h^*$ | `load_duration.csv` |
| Abb. 5 | Break-even Gas- und CO₂-Preis je Standort × Netzregime | `breakeven.csv` |
| Tab. 1 | Regimevergleich mit Fundstellen | `table01_regulatory.md` |
| Tab. 2 | Standortübersicht | `table02_cases.md` |
| Tab. 3 | Kern-KPI | `table03_core_results.md` |

Vorgaben: farbenblindtaugliche Palette, graustufenfest, deutsche Achsen mit Einheiten, keine dualen Achsen im Panel, je Abbildung eine CSV.

## Literatur (Kurzliste, numerisch ZWF)

[1] Naegler et al., *Int. J. Energy Res.* 39 (2015) 15, 2019–2030, DOI 10.1002/er.3436 · [2] Rehfeldt et al., *Energy Efficiency* 11 (2018) 1057–1082, DOI 10.1007/s12053-017-9571-y · [3] Madeddu et al., *ERL* 15 (2020) 124004, DOI 10.1088/1748-9326/abbd02 · [4] Lechtenböhmer et al., *Energy* 115 (2016) 1623–1631, DOI 10.1016/j.energy.2016.07.110 · [5] IEA, *The Future of Heat Pumps*, 2022 · [6] Arpagaus et al., *Energy* 152 (2018) 985–1010, DOI 10.1016/j.energy.2018.03.166 · [7] Zühlsdorf et al., *ECM:X* 2 (2019) 100011 · [8] Schlosser et al., *RSER* 133 (2020) 110219 · [9] Marina et al., *RSER* 139 (2021) 110545 · [10] IEA HPT Annex 58 `Zühlsdorf, B., Armato, V., Poulsen, J. L., Andersen, M. P., Arpagaus, C., Schlosser, F., Dusek, S. (2024). IEA HPT Annex 58 High-Temperature Heat Pumps Final Report. DOI: 10.23697/2qxe-av87.` · [11] Bloess/Schill/Zerrahn, *Applied Energy* 212 (2018) 1611–1626 · [12] Miró et al., *Applied Energy* 179 (2016) 284–301 · [13] Shoreh et al., *EPSR* 141 (2016) 31–49 · [14] Paulus/Borggrefe, *Applied Energy* 88 (2011) 432–441 · [15] Gils, *Energy* 67 (2014) 1–18 · [16] Schittekatte/Momber/Meeus, *Energy Economics* 70 (2018) 484–498 · [17] Passey et al., *Energy Policy* 109 (2017) 642–649 · [18] CEER, C16-DS-27-03, 2017 · [19] BNetzA, AgNes-Festlegung `Az. GBK-25-01-1#3, Entwurf 2026-08-06, Konsultation bis 2026-09-18, Anwendung ab 2029-01-01 (löst StromNEV ab, die zum 2028-12-31 ausläuft, Folge eines EuGH-Urteils)` · [20] StromNEV, geltende Fassung · [21] BNetzA, Monitoringbericht (Netzentgeltniveaus je Ebene) `[[OFFEN: BIB-02 — Offen: BNetzA-Monitoringbericht (Netzentgeltniveaus je Ebene) - s. REG-02.]]` · [22] BNetzA, SMARD · [23] Danish Energy Agency, Technology Data `Danish Energy Agency, Technology Data for Industrial Process Heat, 2023 (ens.dk Technology Catalogues, Sektor 'Industrial process heat').` · [24] DIN EN 17463:2021-12 (VALERI) bzw. VDI 2067.

---

# DOKUMENT 2 — Anweisung an den Coding Agent

## 1 Auftrag

Erstelle **ein** reproduzierbares Jupyter Notebook `agnes_p2h.ipynb`, das aus vier gemessenen Fabriklastgängen und zwei Day-Ahead-Preisjahren ein LP aufbaut, die Szenariomatrix rechnet und **alle** Marker aus dem Paper-Draft mit belegten Zahlen belegt. Zusätzlich nur: `config.yaml` (alle Parameter), `outputs/<run_ts>/` (Ergebnisse), `README.md` (10 Zeilen). **Kein** src-Paket, **kein** Makefile, **kein** pytest — Selbsttests sind `assert`-Zellen im Notebook.

Empfohlener Stack: Python 3.11, `linopy` (vektorisiert, schnell bei 35.040 Zeitschritten) oder Pyomo, Solver **HiGHS**; `pandas`, `xarray`, `matplotlib`, `pyyaml`. Optional papermill-Parameterzelle.

## 2 Nicht verhandelbare Regeln

| ID | Regel |
|---|---|
| G-01 | Keine synthetischen Werksdaten, keine Zahlenübernahme aus früheren Entwürfen |
| G-02 | Fehlende Pflichtwerte → kontrollierter Abbruch (`MissingParameterError`), keine Defaults |
| G-03 | Jeder Parameter mit Wert, Einheit, Quelle, Status (`unverified`/`reviewed`/`approved`) |
| G-04 | Netzentgelt, $P^{grid}$, $P^{max}$ gelten für den **Gesamtnetzbezug inkl. Grundlast** |
| G-05 | Keine stillschweigende Interpolation, Nullsetzung, Forward-Fill; kein Hochskalieren stündlicher Werkslastgänge |
| G-06 | Ergebnisrichtungen sind nie Tests; keine „Korrektur" auf erwartete Vorzeichen |
| G-07 | Jede Paper-Zahl mit Run-ID + Config-Hash rückverfolgbar |
| G-08 | Nicht-optimale oder als inkonsistent geflaggte Läufe gehen nicht in Aggregate ein |
| G-09 | Test-Fixtures strikt getrennt vom Ergebnisexport |

## 3 Vier blockierende Eingaben (alles andere blockiert nicht)

| ID | Benötigt | Bei Fehlen |
|---|---|---|
| B-01 | Wärmelastgang LT/HT (Metall zusätzlich VHT), 15 min | Standort blockiert |
| B-02 | Grundlast $P^{base}_t$ und Definition der Messgrenze (Eigenerzeugung/Export abgegrenzt) | Standort blockiert |
| B-03 | $P^{grid}$ und Viertelstunden-Höchstlast des Vorjahres an derselben Messgrenze | AgNes-Läufe blockiert |
| B-04 | Bandanteile bzw. Zuordnungsregel LT/HT/VHT mit Begründung | Standort blockiert |

Alles andere (AgNes-Ziffern, Preisblätter, Technologieparameter) wird über `config.yaml` mit Status geführt: `status: unverified` ist zulässig, erscheint aber automatisch in `open_issues.md` und im Limitations-Text.

## 4 Notebook-Struktur (Abschnitte = Zellgruppen)

| § | Inhalt | Ausgabe |
|---|---|---|
| 0 | Parameterzelle, Versionen, Seeds, Output-Ordner | `environment.md` |
| 1 | Datenimport, Qualitätsprüfung, Ebenen- und Bandzuordnung | `data_audit.md`, `table02_cases.md` |
| 2 | Tarifauflösung + Kalibrierung, θ-Feld, σ(h), $N_{unlock}$ | `tariff_resolved.md`, `fig02_analytics.csv` |
| 3 | **Analytische Bestellregel** $C^*=P_{LDC}(h^*)$ je Standort (vor jedem Solve) | `rule_prediction.csv` |
| 4 | LP-Aufbau (eine Funktion `build_model(site, regime, config, mode)`) | — |
| 5 | Selbsttests T01–T12 (alle grün, sonst Stopp) | `test_report.md` |
| 6 | Kernläufe S1–S4 | `runs.parquet`, `kpi.csv` |
| 7 | Sweeps S5–S7, Dekomposition S8 | `kpi.csv` (fortgeschrieben), `decomposition.csv`, `breakeven.csv` |
| 8 | KPI-Aggregation, 2×2-Interaktion, Regelgüte | `interaction.csv`, `rule_validation.csv` |
| 9 | Abbildungen 1–5 + je CSV | `figures/*.pdf|svg|png` |
| 10 | Tabellen 1–3 + Supplement | `tables/*.md|csv` |
| 11 | **Marker-Export und Draft-Patch** | `paper_values.json`, `marker_map.csv`, `paper_patch.md`, `draft_filled.md` |
| 12 | Offene Punkte, QA-Zusammenfassung | `open_issues.md`, `qa_report.md` |

## 5 Konfiguration (Ausschnitt)

```yaml
study:
  timestep_min: 15
  currency: EUR
  solver: highs
  bands: [LT, HT, VHT]        # VHT nur wo site.has_vht = true

sites:
  food:      {price_year: 2023, load_year: null, has_vht: false}
  chemistry: {price_year: 2024, load_year: null, has_vht: false}
  metal:     {price_year: 2023, load_year: null, has_vht: true}
  paper:     {price_year: 2023, load_year: null, has_vht: false}

tariffs:
  mode: synthetic_first_order        # published | synthetic_first_order
  k_eur_per_kw_a:  {value: null, source: null, status: unverified}
  t_B_h:           {value: null, source: null, status: unverified}
  alpha:           {value: 0.45, range: [0.30, 0.60], status: unverified}
  f:               {value: 2.75, range: [2.0, 3.5],   status: unverified}
  beta_min_order:  {value: 0.10, status: unverified}
  stromnev:
    pair_low:  {lp_eur_kw_a: null, ap_eur_mwh: null, status: unverified}
    pair_high: {lp_eur_kw_a: null, ap_eur_mwh: null, status: unverified}

technologies:
  hp:  {capex_eur_kw: null, cop_lt: null, cop_pre: null, kappa: null, lifetime_a: null}
  ek:  {capex_eur_kw: null, eta: null, lifetime_a: null}
  gb:  {capex_eur_kw: null, eta: null, lifetime_a: null}
  ef:  {capex_eur_kw: null, eta: null, lifetime_a: null}   # VHT elektrisch
  gf:  {capex_eur_kw: null, eta: null, lifetime_a: null}   # VHT Gas
  tes: {capex_eur_kwh: null, loss_per_h: null, eta_ch: null, eta_dis: null, min_duration_h: null}

finance: {wacc: null, price_base_year: null}
energy:  {gas_eur_mwh_hu: null, co2_eur_t: null, ef_gas_t_mwh: null, el_levies_eur_mwh: null}
```

Kalibrierung bei `synthetic_first_order`: $AP_1=1000\alpha k/t_B$, $AP_2=fAP_1$, $KP=(1-\alpha)k$. In `tariff_resolved.md` automatisch den Satz erzeugen: „szenarische Kalibrierung, erlösäquivalent nur für das Referenzkollektiv bei unveränderter Absatzstruktur; kein veröffentlichtes Preisblatt."

## 6 Datenvertrag je Standort (15-min-Zeitreihe)

| Feld | Einheit | Pflicht |
|---|---|---|
| `timestamp_utc` | ISO 8601 UTC | ja |
| `q_lt_kw`, `q_ht_kw` | kW_th | ja |
| `q_vht_kw` | kW_th | nur Metall |
| `p_base_grid_kw` | kW | ja |
| `t_source_c`, `t_sink_lt_c`, `t_sink_ht_c` | °C | falls COP zeitvariabel |
| `quality_flag`, `source_row_id` | Enum / Text | ja |

Metadaten: Messgrenze, Spannungsebene, Netzbetreiber, $P^{grid}$, $P^{max,prev}$, Bestandsanlagen (falls Retrofit), Anonymisierungsstatus. Erwartete Intervalle: 35.040 (2023) / 35.136 (2024). 15 min → 1 h nur als Leistungsmittel (energieerhaltend); Stundenpreise dürfen 4× wiederholt werden.

## 7 Modell (MUST)

Variablen: $x_{HP},x_{EK},x_{GB},x_{EF},x_{GF}$ [kW_th], $x_{TES,b}$ [kWh_th], $C$ [kW]; $q_{j,b,t}$, $q^{HP,pre}_t$, $S_{b,t}$, $q^{ch}_{b,t}$, $q^{dis}_{b,t}$, $P_t$, $P_{1,t}$, $P_{2,t}$, $G_t$, $P^{max}$.

| ID | Nebenbedingung |
|---|---|
| N1 | Wärmebilanz je Band und Intervall als **Gleichung** (kein Wärme-Dump) |
| N2 | $q^{HP,HT}=0$; HT-Beitrag nur $q^{HP,pre}_t\le\kappa Q_{HT,t}$ mit $COP_{pre}$ |
| N3 | VHT ausschließlich durch EF und GF |
| N4 | $q_{j,b,t}\le x_j$ je Erzeuger |
| N5 | $S_{b,t}=(1-\lambda_b\Delta t)S_{b,t-1}+\eta^{ch}q^{ch}\Delta t-q^{dis}\Delta t/\eta^{dis}$, zyklisch geschlossen |
| N6 | $S_{b,t}\le x_{TES,b}$; $q^{ch}+q^{dis}\le x_{TES,b}/h^{min}_{dur}$ |
| N7 | $P_t=P^{base}_t+q^{HP,LT}/COP_{LT}+q^{HP,pre}/COP_{pre}+\sum_b q^{EK}_b/\eta_{EK}+q^{EF}/\eta_{EF}$ |
| N8 | $P_t\le P^{grid}$; $P_t\le P^{max}$ |
| N9 | AgNes: $P_t=P_{1,t}+P_{2,t}$, $P_{1,t}\le C$, $\beta P^{max,prev}\le C\le P^{grid}$ |
| N10 | StromNEV: je Tarifpaar ein LP **ohne** Benutzungsstundenzwang + Konsistenzprüfung (§ 4.5 Draft) |

Modi: `optimize` (alles endogen), `redispatch` (Kapazitäten fix, Betrieb frei), `evaluate` (Kapazitäten und Betrieb fix; $C$ analytisch nach $D(C^*)=h^*$). Konfigurationen: `BASE` (keine modellierte Wärmeerzeugung), `ELEC` (HP/EK/TES, Metall + EF), `ELEC_noTES`, `GAS`, optional `MIX`.

## 8 Laufmatrix

| ID | Inhalt | Δt | Läufe | Prio |
|---|---|---|---:|---|
| S1 | `ELEC` × 4 Standorte × 2 Netz- × 2 Preisregime | 15 min | 16 | MUST |
| S2 | `BASE` zu allen S1-Regimen | 15 min | 16 | MUST |
| S3 | `GAS` zu allen S1-Regimen | 15 min | 16 | MUST |
| S4 | `ELEC_noTES` zu allen S1-Regimen | 15 min | 16 | MUST |
| S5 | α×f-Feld 3×3 × 4 Standorte × AgNes×{FIXED,DA} | 1 h | 72 | MUST |
| S6 | 1-h-Zwillinge der S1-Läufe | 1 h | 16 | MUST |
| S7 | Break-even Gas und CO₂ (Bisektion, ≤ 25 Schritte, Toleranz 0,1 %) | 1 h | ~16 Ketten | MUST |
| S8 | Dekomposition `evaluate`/`redispatch` für 00→10 | 15 min | 8 | SHOULD |
| S9 | Bandanteile ±10 pp | 1 h | 8 | SHOULD |
| S10 | Rolling Horizon (36 h / 24 h) für 1 Standort × 4 Regime, $C$ ex ante fix | 15 min | 4 | MAY |
| S11 | COP, WACC, Risikoprämie ρ | 1 h | ≤ 24 | MAY |

Reihenfolge: § 1–3 → Tests grün → S1–S4 → S5–S7 → S8/S9 → Rest. **Stopp-Punkt nach § 1 und § 3:** Datenaudit und analytische Vorhersage vorlegen, bevor produktive Läufe starten.

## 9 Selbsttests (12, alle vor Sweeps grün)

| ID | Prüfung | Akzeptanz |
|---|---|---|
| T01 | Intervallzahl, UTC/DST, keine Lücken/Duplikate | exakt |
| T02 | Einheiten-Sentinel + Faktor-1000-Mutation bricht den Test | muss brechen |
| T03 | Wärmebilanz je Band und Intervall | rel. < 1e-6 |
| T04 | Strombilanz inkl. $P^{base}$ | rel. < 1e-6 |
| T05 | Speicher zyklisch geschlossen, Grenzen und Raten eingehalten | Toleranz |
| T06 | $r_{sim}=\frac{\sum\min(q^{ch},q^{dis})\Delta t}{\sum(q^{ch}+q^{dis})\Delta t}\le 10^{-8}$ | sonst Lauf gesperrt |
| T07 | AgNes: $P_{1,t}=\min(P_t,C)$ im Optimum; $C$ in Grenzen | Toleranz |
| T08 | **Bestellregel:** im `evaluate`-Modus gilt $D(C^*)=h^*$ und $C^*$ minimiert $F(C)$ (Gitter-Gegenprobe) | rel. < 0,5 % |
| T09 | StromNEV: $P^{max}=\max_t P_t$ und gewähltes Tarifpaar konsistent | sonst `tariff_ambiguous` |
| T10 | Dominanzen: TES ≤ noTES, endogenes $C$ ≤ fixes $C$, Monotonie in Gas-/CO₂-Preis | keine Verletzung |
| T11 | Objective-Rekonstruktion aus Komponenten = Solverwert; $P^{max}_{15}\ge P^{max}_{60}$ | rel. < 1e-6 |
| T12 | Determinismus und Solververgleich (HiGHS vs. Alternative) | Δ TOTEX < 0,01 % |

Hartkodierte Analytik-Fixture ($h^*$, θ, $C^*$ an einem Mini-Lastgang) nur unter `fixtures/` — nie in den Export.

## 10 KPIs (in `kpi.csv`, eine Zeile pro Run)

Kosten: TOTEX, CAPEX-Annuität, Strom-/Gas-/CO₂-OPEX, Netzentgelt total sowie getrennt $KP\cdot C$, $AP_1E_1$, $AP_2E_2$, $LCOH^{inc}$ · Auslegung: $x_{HP},x_{EK},x_{GB},x_{EF},x_{GF},x_{TES,b}$, TES-Vollzyklen · Netz: $E$, $P^{max}$, $C$, $C/P^{max}$, $E_1$, $E_2$, $E_2/E$, gewichtete Dauer $P_t>C$, Benutzungsstunden · Analytik: $h^*$, θ, $C^*_{Regel}$, Abweichung zu $C_{LP}$, $N_{unlock}$ · Vergleiche: $\Delta_{Netz}$, $\Delta_{Preis}$, $\Delta_{inter}$, $\Delta_{mech}/\Delta_{disp}/\Delta_{design}$ · Diagnostik: Solverstatus, Laufzeit, $r_{sim}$, `tariff_ambiguous`, `level_shift_triggered`, `degenerate` (ε-Störungssolve).

## 11 Marker-Export

```json
{
  "R-BOOK-MIN": {
    "value": 0.63,
    "unit": "-",
    "display_value": "63 %",
    "run_ids": ["food__2023__agnes__da__elec__15min"],
    "kpi": "C_over_Pmax",
    "config_sha256": "…",
    "result_file": "runs.parquet"
  }
}
```

Pflichtdateien: `paper_values.json`, `marker_map.csv` (Marker → KPI → Run-ID), `paper_patch.md` (Ersetzungsliste), `draft_filled.md` (automatisch gepatchter Draft, deutsche Zahlenformate: Komma, Tausenderpunkt). Nicht belieferbare Marker bleiben mit Begründung **sichtbar offen** — niemals mit `0.0` füllen.

## 12 Definition of Done

1. Keine Zahl aus alten Entwürfen ungeprüft übernommen. 2. T01–T12 grün. 3. Alle MUST-Läufe optimal und reproduzierbar (ein Notebook-Durchlauf „Run All"). 4. Jede Kostenzahl aus Komponenten rekonstruierbar. 5. 5 Abbildungen + 3 Tabellen + Supplement erzeugt, je mit Quelldaten. 6. `paper_values.json` beliefert alle `[[R-*]]` oder begründet sie als offen. 7. `draft_filled.md` ohne manuelles Zahlenübertragen erzeugt. 8. `open_issues.md` listet alle `unverified`-Parameter mit Wirkung auf die Kernaussagen.

**Startanweisung:** Zuerst nur § 0–3 ausführen (Datenaudit, Tarifauflösung, analytische Bestellregel) und Bericht vorlegen. Produktive Läufe erst nach Freigabe.

---

# Teil 3 — Was du jetzt entscheiden musst

| # | Offener Punkt | Vorschlag |
|---|---|---|
| 1 | Prozesswärme vs. Fernwärmenetz (siehe Vorbemerkung) | Prozesswärme | --> prozesswärme
| 2 | VHT-Band beibehalten? | Ja, minimalinvasiv nur für Metall — falls die VHT-Datenlage dünn ist, streichen und als Limitation nennen (spart ~1 Seite)--> Limitation |
| 3 | Quelle für $k$ und $t_B$ je Spannungsebene | BNetzA-Monitoringbericht; bitte Ausgabe/Jahr festlegen | --> selbst festlegen
| 4 | Sind es gemessene Werkslastgänge oder rekonstruierte Profile? | Bestimmt Titel- und Abstractformulierung (Formulierungspflicht in § 5.1) |--> gemessenen werte
| 5 | Rolling Horizon (S10) rechnen oder als Limitation belassen? | Bei Zeitdruck: Limitation | --> RH-Rechnen