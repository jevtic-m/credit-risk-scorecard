# Power-BI-Dashboard: Aufbau und Felder

Datenquelle: `03_dashboard/scored_portfolio.csv` (erzeugt von `02_python/07_dashboard_export.py`, eine
Zeile je Kredit, 1.348.099 Zeilen). Measures: `03_dashboard/measures.dax`. Statische Charts für Seite 3:
`03_dashboard/figures/`. Kennzahlen für Seite 3: `03_dashboard/model_quality.csv`.

Die CSV ist wegen ihrer Größe (über 100 MB) nicht im Git-Repo, sondern wird lokal erzeugt:

```bash
.venv/Scripts/python.exe 02_python/07_dashboard_export.py
```

## Spalten in scored_portfolio.csv

| Spalte | Inhalt | Typ in Power BI |
|---|---|---|
| loan_id | Lending-Club-Kredit-ID | Ganze Zahl |
| issue_year, issue_quarter | Ausgabejahr, Quartal ("2016-Q1") | Ganze Zahl, Text |
| sample | "train" (2007–2015) oder "test" (2016–2018, zeitlich getrennt) | Text |
| matured | "ja", wenn die volle Laufzeit vor Dezember 2018 lag (Reifegrad) | Text |
| grade, sub_grade | Lending Clubs Einstufung (nur zur Analyse, nicht im Modell) | Text |
| term_months | 36 oder 60 | Ganze Zahl |
| purpose, addr_state, home_ownership | Verwendungszweck, Bundesstaat, Wohnform | Text |
| income_band, dti_band, fico_band | Klassen wie in `01_sql/02_default_rates.sql` | Text |
| funded_amnt | ausgezahlter Betrag in USD (= EAD) | Ganze Zahl |
| default | 1 = Charged Off / Default, 0 = Fully Paid | Ganze Zahl |
| score | Scorecard-Punkte Modell A (453 bis 619) | Ganze Zahl |
| pd | Ausfallwahrscheinlichkeit über die Laufzeit, Modell A | Dezimalzahl |
| lgd | 0,622 für alle Kredite (empirischer Mittelwert) | Dezimalzahl |
| el | Expected Loss in USD = pd x lgd x funded_amnt | Dezimalzahl |

Empfohlene globale Slicer auf jeder Seite: `sample`, `issue_year`, `term_months`. Die Kernzahl im
README gilt für `sample = test`.

## Seite 1: Portfolio-Übersicht

| Visual | Felder / Measures |
|---|---|
| KPI-Karte: Gesamtvolumen | [Total Volume], Format Mrd. USD |
| KPI-Karte: Anzahl Kredite | [Total Loans] |
| KPI-Karte: Ausfallquote | [Default Rate], Prozent |
| KPI-Karte: Expected Loss absolut | [Total EL], Mio. USD |
| KPI-Karte: EL in % des Volumens | [EL Rate Total] |
| Linienchart mit zwei Achsen: Volumen und Ausfallquote je Ausgabejahr | Achse issue_year, Säulen [Total Volume], Linie [Default Rate] |
| Balken: Volumen nach Grade | Achse grade, Wert [Total Volume] |

Hinweis auf der Seite (Textfeld): "Ausfallquoten der Jahrgänge ab 2016 sind nicht ausgereift; Filter
matured = ja zeigt nur Kredite mit voller Laufzeit im Beobachtungsfenster."

## Seite 2: Risikotreiber

| Visual | Felder / Measures |
|---|---|
| Matrix (Heatmap): Ausfallquote Grade x Ausgabejahr | Zeilen issue_year, Spalten grade, Wert [Default Rate], bedingte Formatierung Farbskala |
| Karte: Ausfallquote nach Bundesstaat | Ort addr_state, Farbe [Default Rate], Blasengröße [Total Volume] |
| Balken: Ausfallquote nach purpose | Achse purpose, Wert [Default Rate], absteigend sortiert |
| Balken: Ausfallquote nach income_band | Achse income_band, Wert [Default Rate] |
| Balken: Ausfallquote nach dti_band | Achse dti_band, Wert [Default Rate] |
| Balken: Ausfallquote nach fico_band | Achse fico_band, Wert [Default Rate] |

Erwartete Bilder (aus AP2): Grade A 6,0 % bis G 49,7 %; DTI unter 10: 14,9 %, ab 40: 30,6 %; FICO ab
750: 8,9 %, 660–679: 25,3 %.

## Seite 3: Modellgüte

Statische Bilder aus `03_dashboard/figures/` (Bild-Visual) plus eine Tabelle aus `model_quality.csv`.

| Visual | Quelle |
|---|---|
| ROC-Kurve mit AUC (drei Modelle) | `roc_curve.png` |
| Kalibrierungsplot je Dezil | `calibration_plot.png` |
| Score-Verteilung Good vs. Bad | `score_distribution.png` |
| KS-Plot | `ks_plot.png` |
| Tabelle: AUC, Gini, KS je Modell und Stichprobe | `model_quality.csv` (Modell A Test: AUC 0,688, Gini 0,377, KS 0,270) |

Textfeld: "Modell A ohne Lending Clubs Einstufung, 15 Antragsvariablen, zeitlich getrennter Test 2016–2018.
Kalibrierung im Test liegt 27 % über der PD, weil dort nur früh abgeschlossene Kredite enthalten sind
(Zensierung, siehe reports/findings.md AP5)."

## Seite 4: Cutoff-Simulator (Kern)

| Visual | Felder / Measures |
|---|---|
| Schieberegler | What-if-Parameter CutoffParam (450 bis 620, Schritt 5, Standard 515) |
| KPI-Karte: Annahmequote | [Approval Rate] |
| KPI-Karte: Genehmigtes Volumen | [Approved Volume] |
| KPI-Karte: Verlorenes Volumen | [Volume Lost Share] |
| KPI-Karte: Ausfallquote des angenommenen Portfolios | [Approved Bad Rate] |
| KPI-Karte: Expected Loss absolut | [Approved EL] |
| KPI-Karte: EL in % | [EL Rate] |
| KPI-Karte: EL-Senkung gegenüber kein Cutoff | [EL Rate Reduction] |
| KPI-Karte: abgelehnte gute Kredite | [Rejected Good Share] |
| Zwei-Achsen-Diagramm: EL-Rate und Annahmequote gegen Cutoff | X-Achse 'CutoffParam'[Cutoff], Linie 1 [EL Rate by Cutoff], Linie 2 [Approval Rate by Cutoff], Referenzlinie bei [Cutoff] |
| Optional: zweiter Regler LGD | What-if-Parameter LgdParam, KPI [EL Rate at LGD] |

Kontrollwerte bei Slicer sample = test und Cutoff 515 (aus `reports/cutoff_summary.csv`):
Annahmequote 84,5 %, verlorenes Volumen 20,1 %, EL-Rate 8,80 % (ohne Cutoff 11,83 %), EL-Senkung
25,6 %, Ausfallquote angenommen 18,70 %, abgelehnte Gute 11,4 %. Weichen die Werte ab, stimmt
entweder der Slicer nicht oder die CSV ist nicht aktuell.

## Screenshots

Nach dem Aufbau je Seite einen Screenshot nach `03_dashboard/screenshots/` legen:
`01_portfolio.png`, `02_risikotreiber.png`, `03_modellguete.png`, `04_cutoff_simulator.png`, und die
Platzhalter im README ersetzen.
