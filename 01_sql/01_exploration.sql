-- 01_exploration.sql
-- Erste Erkundung der Rohdaten in DuckDB. Wird von 02_python/01_data_prep.py ausgefuehrt.
-- Regel fuer dieses Repo: nie SELECT * auf die volle Tabelle, immer nur die noetigen Spalten,
-- beim Anschauen einzelner Zeilen immer mit LIMIT.

-- Abfrage 1: Wie sehen die ersten Zeilen aus?
-- Frage: Welche Form haben die Kernspalten (Text? Zahl? Datum als Text?).
-- Ergebnis: Werte sind als Text gespeichert; term hat Form " 36 months", issue_d "Dec-2015",
--           emp_length "10+ years", int_rate und revol_util sind reine Zahlen ohne Prozentzeichen.
SELECT id, loan_amnt, funded_amnt, term, int_rate, grade, emp_length,
       annual_inc, issue_d, loan_status, purpose, dti, fico_range_low, revol_util
FROM loans_raw
LIMIT 5;

-- Abfrage 2: Wie ist loan_status verteilt?
-- Frage: Wie viele Kredite haben einen bekannten Ausgang, wie viele laufen noch?
-- Ergebnis: 1.348.099 Kredite (59,6 %) sind abgeschlossen (Fully Paid, Charged Off, Default, jeweils
--           inkl. der Variante 'Does not meet the credit policy'), 912.569 (40,4 %) laufen noch
--           (Current, Late, In Grace Period). 33 Zeilen ohne Status sind Summenzeilen der Kaggle-Datei.
SELECT loan_status,
       count(*)                                  AS loans,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct
FROM loans_raw
GROUP BY loan_status
ORDER BY loans DESC;

-- Abfrage 3: Wie verteilen sich die Kredite ueber die Zeit (issue_d)?
-- Frage: Welchen Zeitraum decken die Daten ab, und wo liegt das Volumen?
-- Ergebnis: Erste Kredite Juni 2007, letzte Dezember 2018. Bis 2012 sind es nur wenige tausend Kredite
--           pro Jahr, ab 2015 ueber 400.000 pro Jahr. Ab 2016 ist weniger als die Haelfte der Kredite
--           eines Jahrgangs abgeschlossen (2018: 56.318 von 495.242), weil sie noch laufen.
SELECT CAST(strptime(issue_d, '%b-%Y') AS DATE)                    AS issue_month,
       count(*)                                                    AS loans
FROM loans_raw
WHERE issue_d IS NOT NULL
GROUP BY issue_month
ORDER BY issue_month
LIMIT 5;

SELECT year(strptime(issue_d, '%b-%Y'))                            AS issue_year,
       count(*)                                                    AS loans,
       round(sum(CAST(loan_amnt AS DOUBLE)) / 1e9, 2)              AS volume_bn_usd,
       count(*) FILTER (WHERE loan_status IN ('Fully Paid', 'Charged Off', 'Default',
                    'Does not meet the credit policy. Status:Fully Paid',
                    'Does not meet the credit policy. Status:Charged Off')) AS loans_closed
FROM loans_raw
WHERE issue_d IS NOT NULL
GROUP BY issue_year
ORDER BY issue_year;

-- Abfrage 4: Fehlende Werte in den Kernspalten
-- Frage: Welche Modellspalten haben Luecken, und wie gross sind sie?
-- Ergebnis: issue_d ist vollstaendig. emp_length fehlt bei 6,5 %, dti und revol_util bei unter 0,1 %.
--           mths_since_last_delinq fehlt bei 51 %, mths_since_last_record bei 84 %: hier bedeutet
--           'fehlt' meist 'nie passiert' und ist damit selbst ein Signal (eigene Bin-Kategorie ab AP3).
SELECT
    round(100.0 * count(*) FILTER (WHERE issue_d IS NULL) / count(*), 2)                 AS issue_d_missing_pct,
    round(100.0 * count(*) FILTER (WHERE emp_length IS NULL) / count(*), 2)              AS emp_length_missing_pct,
    round(100.0 * count(*) FILTER (WHERE dti IS NULL) / count(*), 2)                     AS dti_missing_pct,
    round(100.0 * count(*) FILTER (WHERE revol_util IS NULL) / count(*), 2)              AS revol_util_missing_pct,
    round(100.0 * count(*) FILTER (WHERE mths_since_last_delinq IS NULL) / count(*), 2)  AS mths_since_last_delinq_missing_pct,
    round(100.0 * count(*) FILTER (WHERE mths_since_last_record IS NULL) / count(*), 2)  AS mths_since_last_record_missing_pct,
    round(100.0 * count(*) FILTER (WHERE mort_acc IS NULL) / count(*), 2)                AS mort_acc_missing_pct,
    round(100.0 * count(*) FILTER (WHERE bc_util IS NULL) / count(*), 2)                 AS bc_util_missing_pct
FROM loans_raw;
