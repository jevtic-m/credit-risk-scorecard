# Credit Risk Scorecard & Portfolio Dashboard

**Business-Frage:** Wo sollte eine Bank ihren Annahme-Cutoff setzen?

**Kernergebnis:** Ein Cutoff bei Score 515 senkt den Expected Loss von 11,83 % auf 8,80 % des Portfoliovolumens (minus 25,6 %) und kostet 20,1 % des genehmigten Volumens. Gerechnet auf 518.744 zeitlich getrennten Testkrediten (2016–2018, 7,5 Mrd. USD), Scorecard ohne Lending Clubs eigene Risikoeinstufung, AUC 0,688.

**Stack:** DuckDB (SQL) · Python (optbinning, scikit-learn) · Power BI · Excel

---

## Daten

Lending Club, angenommene Kredite 2007–2018, 1.348.099 Kredite nach Filterung, Kaggle-Datensatz `wordsforthewise/lending-club`, Lizenz CC0 (Public Domain).

| Schritt | Kredite |
|---|---|
| Rohdatei | 2.260.701 (davon 33 Summenzeilen ohne Kredit) |
| Nach Filter auf abgeschlossene Kredite (Fully Paid, Charged Off, Default) | 1.348.099 |
| Ausfallquote im bereinigten Datensatz | 19,98 % (269.360 Ausfälle) |
| Zeitraum (issue_d) | Juni 2007 bis Dezember 2018 |

Ausgeschlossen: laufende Kredite (Current, Late, In Grace Period), weil ihr Ausgang noch offen ist. Würde man sie als "gut" werten, wäre die Ausfallquote systematisch zu niedrig (Zensierungsproblem).

Ausgeschlossen: 38 Spalten, die erst nach der Kreditvergabe entstehen (Zahlungen, Rückflüsse, Härtefall- und Vergleichsdaten). Die vollständige Liste steht in `02_python/01_data_prep.py` und in `reports/findings.md`.

## Methodik

1. SQL-Analyse: Ausfallquoten nach Segment, Vintage-Kurven, Kohorten
2. Feature-Auswahl unter strikter Vermeidung von Datenleckage
3. WoE-Binning und Information Value
4. Logistische Scorecard mit PDO-Skalierung
5. Modellgüte: AUC/Gini, KS, Kalibrierung, PSI
6. Expected Loss mit empirisch geschätzter LGD
7. Cutoff-Analyse

## Ergebnisse

**AP1 – Datenbasis:** Von 2.260.701 Zeilen der Rohdatei bleiben 1.348.099 Kredite mit bekanntem Ausgang. Davon sind 269.360 ausgefallen, die Ausfallquote liegt bei 19,98 %. Kredite mit 60 Monaten Laufzeit fallen mit 32,45 % etwa doppelt so oft aus wie 36-Monats-Kredite mit 16,02 %. Das bereinigte Portfolio hat ein ausgezahltes Volumen von 19,41 Mrd. USD. 38 Spalten wurden als Datenleckage ausgeschlossen, 41 Spalten bleiben in `data/processed/loans_clean.parquet`.

**AP2 – Risikotreiber (SQL):** Lending Clubs eigene Einstufung ist streng monoton, von Grade A mit 6,04 % bis G mit 49,67 % Ausfallquote. 60-Monats-Kredite fallen mit 32,45 % doppelt so oft aus wie 36-Monats-Kredite (16,02 %). FICO (ab 750: 8,89 %, 660–679: 25,30 %) und DTI (unter 10: 14,93 %, ab 40: 30,55 %) trennen deutlich. Das Risiko sitzt in absoluten Zahlen in den Grades C und D: A bis C sind 71,5 % des Volumens, aber nur 51,9 % des ausgefallenen Volumens.

**Vintage und Reifegrad:** Nur Jahrgänge bis 2013 (60 Monate) bzw. bis 2015 (36 Monate) sind vollständig ausgereift. Die Ausfallquote der 36-Monats-Kredite stieg leicht von 10,9 % (2010) auf 14,9 % (2015), die der 60-Monats-Kredite lag bei 22 bis 28 %. Ausfallquoten der Jahrgänge ab 2016 sind nicht belastbar, weil dort noch kein Kredit seine volle Laufzeit hatte. Alle 15 Abfragen mit Ergebnis stehen in `01_sql/`.

**AP3 – Split und Binning:** Zeitbasierter Split bei Januar 2016: Training 829.355 Kredite (2007–2015, Ausfallquote 18,46 %), Test 518.744 Kredite (2016–2018, Ausfallquote 22,42 %). WoE-Binning mit optbinning auf 32 Kandidaten ohne grade/int_rate. Stärkste Variablen nach Information Value: term_months (0,238), loan_to_income (0,126), fico_range_low (0,122), acc_open_past_24mths (0,082), dti (0,075). 17 Variablen mit IV ≥ 0,02 gehen ins Modell. Keine Variable des Hauptmodells liegt über 0,5, es gibt also kein Leckage-Signal. Zum Vergleich: Lending Clubs eigene Merkmale sub_grade (0,498), grade (0,469) und int_rate (0,466) sind jeweils doppelt so stark wie die beste eigene Variable.

**AP4 – Scorecard:** Logistische Regression auf WoE-Werten, skaliert mit PDO 20 und 600 Punkten bei Odds 50:1. Zwei Variablen (loan_amnt, revol_util) bekamen wegen Überschneidung mit loan_to_income ein positives Vorzeichen und wurden entfernt; das Hauptmodell A hat 15 Variablen, alle mit plausiblem Vorzeichen. Scores liegen zwischen 453 und 619 Punkten. Erste Güte: AUC 0,706 im Training und 0,688 im zeitlich getrennten Test. Das Benchmark-Modell B mit Lending Clubs grade, sub_grade und int_rate erreicht 0,705 im Test, also nur 0,017 mehr. Die Scorecard-Tabelle steht in `reports/scorecard_table_a.csv`.

**AP5 – Modellgüte (Test 2016–2018, zeitlich getrennt):**

| Modell | AUC | Gini | KS |
|---|---|---|---|
| A Scorecard, 15 Variablen ohne grade/int_rate | 0,688 | 0,377 | 0,270 |
| B Benchmark mit grade, sub_grade, int_rate | 0,705 | 0,411 | 0,296 |
| Gradient Boosting, gleiche 15 Variablen wie A | 0,696 | 0,393 | 0,282 |

Kalibrierung: Im ausgereiften Training trifft die mittlere PD die Ausfallquote exakt (18,45 % gegen 18,46 %). Im Testzeitraum liegt die beobachtete Quote 27 % über der PD, weil dort nur früh abgeschlossene Kredite enthalten sind und frühe Ausfälle überrepräsentiert sind (Zensierung, nicht Modellfehler). PSI der Score-Verteilung Train gegen Test: 0,008, also stabil. Boosting bringt nur 0,008 AUC mehr, die erklärbare Scorecard bleibt das Hauptmodell. Charts in `reports/figures/`.

**AP6 – Expected Loss:** LGD empirisch aus 269.360 ausgefallenen Krediten: Mittelwert 62,2 %, Median 66,4 % (36 Monate 57,3 %, 60 Monate 69,9 %, Grade A 52,3 % bis G 75,4 %). EAD = ausgezahlter Betrag. Lifetime-EL des zeitlich getrennten Testportfolios (2016–2018, 7,50 Mrd. USD): 887 Mio. USD oder 11,83 % des Volumens; Gesamtportfolio 2.353 Mio. USD oder 12,12 %. Backtest auf dem ausgereiften Training: Modell-EL 12,30 % gegen realisierten Verlust 11,61 %, das Modell ist leicht konservativ. Sensitivität: mit LGD 30 % sinkt der EL auf 5,71 %, mit 60 % auf 11,41 %.

**AP7 – Cutoff-Analyse (Testportfolio 2016–2018):**

| Cutoff | Annahmequote | Volumen verloren | EL-Rate | EL-Senkung | abgelehnte Gute | abgelehnte Ausfälle |
|---|---|---|---|---|---|---|
| kein | 100,0 % | 0 % | 11,83 % | 0 % | 0 % | 0 % |
| 500 | 94,6 % | 7,3 % | 10,44 % | 11,7 % | 3,4 % | 12,3 % |
| **515** | **84,5 %** | **20,1 %** | **8,80 %** | **25,6 %** | **11,4 %** | **29,5 %** |
| 530 | 64,5 % | 41,0 % | 6,86 % | 42,1 % | 29,6 % | 55,7 % |
| 550 | 28,4 % | 73,8 % | 4,28 % | 63,8 % | 66,9 % | 87,9 % |

Der Referenz-Cutoff 515 ist der Knick der Trade-off-Kurve: Bis dahin bringt jeder Prozentpunkt verlorenes Volumen viel EL-Senkung, danach wird es teuer. Absolut sinkt der EL von 887 auf 527 Mio. USD (360 Mio. USD weniger) bei 1,51 Mrd. USD weniger Neugeschäft. Auf dem Gesamtportfolio liegt der Knick bei 510. Mit LGD 60 % statt 30 % ist der Cutoff doppelt so viel wert (348 statt 174 Mio. USD gesparter EL), die Form der Kurve ändert sich nicht. Vollständige Tabelle in `reports/cutoff_table.csv`, Charts `reports/figures/cutoff_curve_test.png` und `cutoff_tradeoff_test.png`.

**AP8 – Dashboard und Excel:** `02_python/07_dashboard_export.py` erzeugt `03_dashboard/scored_portfolio.csv` (1.348.099 Kredite, 20 Spalten, 190 MB, nicht im Repo). `03_dashboard/measures.dax` und `layout.md` beschreiben die vier Dashboard-Seiten mit Cutoff-Regler, `04_excel/score_bands.csv` und `calculator_spec.md` den Excel-Policy-Rechner.

### Dashboard-Screenshots

[Screenshot Seite 1: Portfolio-Übersicht – 03_dashboard/screenshots/01_portfolio.png]

[Screenshot Seite 2: Risikotreiber – 03_dashboard/screenshots/02_risikotreiber.png]

[Screenshot Seite 3: Modellgüte – 03_dashboard/screenshots/03_modellguete.png]

[Screenshot Seite 4: Cutoff-Simulator – 03_dashboard/screenshots/04_cutoff_simulator.png]

Bis die Screenshots vorliegen, zeigen die Charts in `reports/figures/` die Ergebnisse: `cutoff_curve_test.png`, `cutoff_tradeoff_test.png`, `roc_curve.png`, `calibration_plot.png`, `score_distribution.png`, `ks_plot.png`, `iv_ranking.png`, `lgd_distribution.png`.

## Annahmen und Limitationen

- PD über Gesamtlaufzeit, keine 12-Monats-PD
- EAD als funded_amnt approximiert
- LGD empirisch geschätzt, Sensitivität gerechnet
- Vintages ab 2014 (60 Monate) bzw. ab 2016 (36 Monate) nicht vollständig gereift
- US-Verbraucherkredite, nicht direkt auf deutsche Portfolios übertragbar
- `grade`, `sub_grade` und `int_rate` sind Lending Clubs eigene Risikoeinstufung und stehen nicht im Hauptmodell (nur im Benchmark-Modell)

## Reproduktion

Voraussetzung: Python 3.11 oder neuer, Git, ca. 5 GB freier Plattenplatz.

1. Repo klonen und Rohdatei ablegen:
   Kaggle-Datensatz `wordsforthewise/lending-club` herunterladen und die Datei
   `accepted_2007_to_2018Q4.csv.gz` nach `data/raw/` legen (nicht entpacken).
2. Virtuelle Umgebung anlegen und Pakete installieren:
   ```bash
   python -m venv .venv
   .venv/Scripts/python.exe -m pip install -r requirements.txt
   ```
   (Unter macOS/Linux: `.venv/bin/python` statt `.venv/Scripts/python.exe`.)
3. AP1 – Daten laden, Zielvariable, Leckage-Filter, bereinigte Parquet-Datei:
   ```bash
   .venv/Scripts/python.exe 02_python/01_data_prep.py
   ```
   Erzeugt `data/credit.duckdb` und `data/processed/loans_clean.parquet`.
   Die SQL-Exploration aus AP1 steht in `01_sql/01_exploration.sql` und wird vom Skript mit ausgeführt.

4. AP2 – die 15 SQL-Analysen ausführen (liest nur die Parquet-Datei):
   ```bash
   .venv/Scripts/python.exe 02_python/run_sql.py
   ```

5. AP3 – zeitbasierter Split und WoE-Binning (schreibt `reports/iv_table.csv`, `reports/woe_bins.csv`, Charts):
   ```bash
   .venv/Scripts/python.exe 02_python/02_woe_binning.py
   ```

6. AP4 – Scorecard bauen (schreibt `reports/scorecard_table_a.csv`, `_b.csv` und `data/processed/scored_loans.parquet`):
   ```bash
   .venv/Scripts/python.exe 02_python/03_scorecard.py
   ```

7. AP5 – Modellgüte (schreibt `reports/model_metrics.csv`, `calibration_table.csv`, `psi_table.csv`, Charts):
   ```bash
   .venv/Scripts/python.exe 02_python/04_model_evaluation.py
   ```

8. AP6 – Expected Loss (schreibt `reports/lgd_summary.csv`, `expected_loss_summary.csv`, `data/processed/portfolio_el.parquet`):
   ```bash
   .venv/Scripts/python.exe 02_python/05_expected_loss.py
   ```

9. AP7 – Cutoff-Analyse (schreibt `reports/cutoff_table.csv`, `cutoff_summary.csv`, `04_excel/score_bands.csv`, Charts):
   ```bash
   .venv/Scripts/python.exe 02_python/06_cutoff_analysis.py
   ```

10. AP8 – Export für Power BI (schreibt `03_dashboard/scored_portfolio.csv`, `model_quality.csv`, Charts nach `03_dashboard/figures/`):
    ```bash
    .venv/Scripts/python.exe 02_python/07_dashboard_export.py
    ```
11. Dashboard in Power BI nach `03_dashboard/layout.md` mit den Measures aus `03_dashboard/measures.dax` bauen; Excel-Rechner nach `04_excel/calculator_spec.md` auf `04_excel/score_bands.csv` bauen.

Gesamtlaufzeit der Skripte auf einem Laptop: rund 5 Minuten, davon 2 Minuten für das einmalige Laden der Rohdatei.

## Abnahmekriterien je Arbeitspaket

| AP | Kriterium | Status |
|---|---|---|
| AP1 | Fallzahl nach Filter, Ausfallquote, ausgeschlossene Spalten mit Grund | erfüllt: 1.348.099 Kredite, 19,98 %, 38 Spalten |
| AP2 | Alle 15 Queries laufen, Frage und Ergebnis je Query | erfüllt |
| AP3 | IV-Tabelle liegt vor, fünf stärkste Variablen fachlich erklärt | erfüllt: term_months, loan_to_income, fico_range_low, acc_open_past_24mths, dti |
| AP4 | Scorecard-Tabelle liegt vor, PD zu Score erklärt | erfüllt: `reports/scorecard_table_a.csv`, Beispiel in findings |
| AP5 | AUC/Gini/KS, Kalibrierung, Boosting-Vergleich, PSI | erfüllt: AUC 0,688, PSI 0,008 |
| AP6 | Portfolio-EL als Zahl und Prozent, LGD hergeleitet | erfüllt: 887 Mio. USD, 11,83 %, LGD 62,2 % empirisch |
| AP7 | Trade-off-Tabelle, Satz mit Zahlen | erfüllt: Cutoff 515, 11,83 % auf 8,80 %, 20,1 % Volumen |
| AP8 | Repo reproduzierbar, Screenshots, Story | teilweise: reproduzierbar und Story ja, Screenshots fehlen bis das Dashboard in Power BI gebaut ist, Excel als Spezifikation |

Details zu jedem AP in `reports/findings.md`, Interviewfragen mit Antworten in `reports/interview_notes.md`, Datei-für-Datei-Erklärung in `reports/walkthrough.md`.
