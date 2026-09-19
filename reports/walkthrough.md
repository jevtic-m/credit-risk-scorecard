# Walkthrough: das Repo Datei fuer Datei in Ausfuehrungsreihenfolge

Diese Datei erklaert, was jede Datei tut und in welcher Reihenfolge sie laeuft.
Sie wird mit jedem Arbeitspaket ergaenzt.

## Grundlagen (kein Code)

| Datei | Zweck |
|---|---|
| `README.md` | Einstieg: Business-Frage, Kernzahl, Daten, Methodik, Reproduktion |
| `reports/findings.md` | Entscheidungen und Ergebnisse je Arbeitspaket |
| `reports/interview_notes.md` | Interviewfragen mit Antworten aus den echten Ergebnissen |
| `requirements.txt` | Gepinnte Python-Pakete |
| `.gitignore` | Haelt Rohdaten, Parquet-Dateien und die DuckDB-Datei aus dem Repo |

## AP1: Daten laden und verstehen

Ausfuehren: `.venv/Scripts/python.exe 02_python/01_data_prep.py`

| Reihenfolge | Datei | Was passiert |
|---|---|---|
| 1 | `01_sql/00_setup.sql` | Liest `data/raw/accepted_2007_to_2018Q4.csv.gz` direkt (ohne Entpacken) und legt die Tabelle `loans_raw` in `data/credit.duckdb` an. Alle Spalten als Text, damit nichts still falsch erkannt wird. Laeuft nur einmal; beim zweiten Start wird die Tabelle wiederverwendet. |
| 2 | `01_sql/01_exploration.sql` | Vier Erkundungsabfragen: erste Zeilen (mit LIMIT), Verteilung von `loan_status`, Kredite je Ausgabejahr, Fehlquoten der Kernspalten. Jede Abfrage hat im Kommentar Frage und Ergebnis. |
| 3 | `02_python/01_data_prep.py` | Steuert Schritt 1 und 2, baut dann die Zielvariable, wendet die Leckage-Ausschlussliste an, bereinigt Datentypen und schreibt `data/processed/loans_clean.parquet` (Grundlage fuer alles ab AP2) und `data/processed/lgd_inputs.parquet` (nur fuer die LGD in AP6). Zum Schluss schreibt es `reports/ap1_summary.md` mit den Kennzahlen. |

Ergebnisdateien (nicht im Repo, weil in `.gitignore`):
- `data/credit.duckdb`: Tabellen `loans_raw` und `loans_clean`
- `data/processed/loans_clean.parquet`
- `data/processed/lgd_inputs.parquet`

Ergebnisdateien im Repo:
- `reports/ap1_summary.md`: Kennzahlen des Laufs
- `reports/findings.md`: Was gemacht, was rauskam, warum so entschieden
- `reports/interview_notes.md`: Interviewfragen mit Antworten aus den echten Ergebnissen

## AP2: SQL-Analysen

Ausfuehren: `.venv/Scripts/python.exe 02_python/run_sql.py` (alle drei Dateien) oder mit Dateiname als Argument.

| Reihenfolge | Datei | Was passiert |
|---|---|---|
| 1 | `02_python/common.py` | Gemeinsame Pfade und Hilfsfunktionen fuer alle Skripte ab AP2. `connect()` oeffnet die DuckDB-Datei und legt die Sicht `loans` auf `loans_clean.parquet` an. `run_sql_file()` fuehrt eine SQL-Datei Abfrage fuer Abfrage aus. |
| 2 | `02_python/run_sql.py` | Kleiner Runner: nimmt SQL-Dateien als Argument, fuehrt sie ueber `common.py` aus und druckt jedes Ergebnis. |
| 3 | `01_sql/02_default_rates.sql` | Abfragen 1 bis 10: Portfolio-Uebersicht und Ausfallquoten nach grade, sub_grade, term, purpose, Einkommen, Bundesstaat, home_ownership x verification, DTI, FICO. |
| 4 | `01_sql/03_vintage.sql` | Abfragen 11 bis 13: Vintage je Jahr mit Reifegrad-Kennzeichnung, Vintage je Laufzeit (11b), Vintage je Quartal als CTE, Kreditsumme und Zins ueber die Zeit mit LAG. |
| 5 | `01_sql/04_cohorts.sql` | Abfragen 14 und 15: Kohortenmatrix Jahr x Grade (nur ausgereifte Kredite) und Konzentrationsanalyse mit kumulierten Anteilen ueber SUM() OVER. |

Die Sicht `loans` ist eine Sicht auf die Parquet-Datei, keine Kopie: Die SQL-Abfragen lesen genau die
Daten, die AP1 bereinigt hat. Die Rohtabelle `loans_raw` wird ab hier nicht mehr benutzt.

## AP3: Feature-Aufbereitung, zeitbasierter Split, WoE-Binning

Ausfuehren: `.venv/Scripts/python.exe 02_python/02_woe_binning.py` (ca. 30 Sekunden)

| Reihenfolge | Datei | Was passiert |
|---|---|---|
| 1 | `02_python/common.py` | Enthaelt ab AP3 die Modellkonfiguration: Schnittdatum `SPLIT_DATE`, die Variablenlisten fuer Modell A (ohne grade/int_rate) und Benchmark B, die Ausschlussliste `EXCLUDED_FROM_MODEL` mit Gruenden und die PDO-Parameter. `load_model_frame()` liest nur die Modellspalten aus der Parquet-Datei, leitet `credit_history_months` und `loan_to_income` ab und setzt die Spalte `sample` (train/test) nach `issue_date`. |
| 2 | `02_python/02_woe_binning.py` | Prueft per assert, dass der Split zeitlich sauber ist. Fittet optbinning auf den Trainingsdaten (Modell-A-Variablen und getrennt die drei Benchmark-Merkmale), berechnet IV je Variable, meldet IV > 0,5 als Leckage-Warnung, waehlt Variablen mit IV >= 0,02 aus. |

Ergebnisdateien im Repo:
- `reports/iv_table.csv`: IV je Variable, Klasse, Auswahl-Flag (wird von AP4 gelesen)
- `reports/woe_bins.csv`: alle Bins aller Variablen mit Anzahl, Ausfallquote, WoE, IV
- `reports/figures/iv_ranking.png`: IV-Rangliste
- `reports/figures/woe_<variable>.png`: Bins und Ausfallquote der fuenf staerksten Variablen

Ergebnisdateien nicht im Repo (`.gitignore`):
- `data/processed/split.parquet`: id und sample (train/test)
- `data/processed/binning_process_a.pkl`: gefitteter Binning-Prozess Modell A

## AP4: Scorecard bauen

Ausfuehren: `.venv/Scripts/python.exe 02_python/03_scorecard.py` (ca. 70 Sekunden)

| Reihenfolge | Datei | Was passiert |
|---|---|---|
| 1 | `02_python/03_scorecard.py` | Liest die Variablenauswahl aus `reports/iv_table.csv`, baut mit optbinning eine Scorecard (Binning, logistische Regression, PDO-Skalierung 20 / 600 / 50:1). Vorzeichen-Regel: Variablen mit positivem Koeffizienten werden nacheinander entfernt und das Modell neu gefittet. Modell B (Benchmark) bekommt zusaetzlich grade, sub_grade, int_rate und installment. Schreibt Scorecard-Tabellen, Score und PD fuer alle Kredite und ein Rechenbeispiel PD zu Score. |

Ergebnisdateien im Repo:
- `reports/scorecard_table_a.csv`: Hauptmodell, je Bin: Anteil, Ausfallquote, WoE, Koeffizient, Punkte
- `reports/scorecard_table_b.csv`: dasselbe fuer das Benchmark-Modell

Ergebnisdateien nicht im Repo (`.gitignore`):
- `data/processed/scored_loans.parquet`: alle 1.348.099 Kredite mit sample, Score und PD beider Modelle plus Auswertungsspalten (Grundlage fuer AP5 bis AP8)
- `data/processed/scorecard_a.pkl`, `scorecard_b.pkl`: die gefitteten Modelle
