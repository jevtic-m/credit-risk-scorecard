# Credit Risk Scorecard & Portfolio Dashboard

**Business-Frage:** Wo sollte eine Bank ihren Annahme-Cutoff setzen?

**Kernergebnis:** Ein Cutoff bei Score [X] senkt den Expected Loss von [A] % auf [B] % des Portfoliovolumens und kostet [Z] % des genehmigten Volumens.

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

[Weitere Ergebnisse folgen mit AP5 bis AP8.]

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

[Weitere Schritte folgen mit AP5 bis AP8.]
