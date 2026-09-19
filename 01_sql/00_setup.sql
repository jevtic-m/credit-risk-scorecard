-- 00_setup.sql
-- Frage: Wie bekommen wir die 1,3-GB-Rohdatei so in DuckDB, dass alle weiteren
--        Abfragen in Sekunden laufen, ohne die Datei jedes Mal neu zu lesen?
-- Ergebnis: Eine Tabelle loans_raw mit 2.260.701 Zeilen und 151 Spalten in data/credit.duckdb,
--           Ladezeit ca. 2 Minuten (Zeilenzahl wird von 02_python/01_data_prep.py geprueft).
--
-- Ausfuehren aus dem Repo-Root:
--   .venv/Scripts/python.exe -c "import duckdb; duckdb.connect('data/credit.duckdb').execute(open('01_sql/00_setup.sql').read())"
-- oder einfach 02_python/01_data_prep.py starten, das diese Datei zuerst ausfuehrt.

-- ENTSCHEIDUNG: Wir lesen die gepackte Kaggle-Datei (.csv.gz) direkt, statt sie vorher zu
-- entpacken. So laeuft das Repo mit dem unveraenderten Kaggle-Download und die Rohdaten
-- brauchen nur einmal Platz auf der Platte.

-- ENTSCHEIDUNG: Die Rohdatei wird einmalig komplett als Tabelle in DuckDB materialisiert
-- (auf der Platte, nicht im Arbeitsspeicher). Alle Explorationsabfragen laufen danach in
-- Sekunden, statt jedes Mal 1,3 GB neu zu lesen. Das ist kein "SELECT * in pandas".

CREATE OR REPLACE TABLE loans_raw AS
SELECT *
FROM read_csv(
    'data/raw/accepted_2007_to_2018Q4.csv.gz',
    header = true,
    -- Die Kaggle-Datei enthaelt 33 Summenzeilen ("Total amount funded in policy code ..."),
    -- die keine Kredite sind. Sie landen mit loan_status = NULL in loans_raw und werden in
    -- 01_data_prep.py durch den Filter auf loan_status entfernt. ignore_errors faengt
    -- zusaetzlich kaputte Zeilen ab, statt den ganzen Ladevorgang abzubrechen.
    ignore_errors = true,
    -- Alle Spalten erst einmal als Text einlesen. Die Typumwandlung passiert kontrolliert
    -- in 01_data_prep.py, damit keine stille Fehlerkennung (z. B. id als Zahl) passiert.
    all_varchar = true
);
