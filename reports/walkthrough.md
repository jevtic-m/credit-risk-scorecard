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
