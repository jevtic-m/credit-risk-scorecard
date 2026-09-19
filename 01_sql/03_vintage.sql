-- 03_vintage.sql  --  AP2, Abfragen 11 bis 13: zeitliche Analysen
-- Datengrundlage: Sicht `loans` = data/processed/loans_clean.parquet (nur abgeschlossene Kredite).
-- Ausfuehren: .venv/Scripts/python.exe 02_python/run_sql.py 01_sql/03_vintage.sql
--
-- Reifegrad-Hinweis: Der Datensatz endet im Dezember 2018. Ein Kredit
-- von 2017 mit 60 Monaten Laufzeit ist dann noch nicht ausgelaufen. In loans_clean stehen von
-- jungen Jahrgaengen nur die Kredite, die schon frueh abgeschlossen wurden (frueh ausgefallen
-- oder frueh zurueckgezahlt). Ihre Ausfallquote ist deshalb nicht mit alten Jahrgaengen
-- vergleichbar. Wir markieren jeden Kredit als "ausgereift", wenn seine volle Laufzeit vor dem
-- Datenende lag: issue_date + term_months <= 2018-12-01.
--
-- ENTSCHEIDUNG: Reifegrad ueber "volle Laufzeit im Beobachtungsfenster" statt ueber ein
-- einheitliches Alter (z. B. "Ausfaelle in den ersten 24 Monaten"). Die Alternative braeuchte den
-- Ausfallzeitpunkt, der nur aus Leckage-Spalten (last_pymnt_d) ableitbar waere und deshalb nicht
-- in loans_clean liegt.


-- Abfrage 11: Vintage-Kurve, Ausfallquote je Ausgabejahr, mit und ohne Reifegrad-Filter
-- Frage: Wie entwickelt sich die Ausfallquote ueber die Jahrgaenge, und welche Jahrgaenge sind
--        ueberhaupt vergleichbar?
-- Ergebnis: Ueber alle abgeschlossenen Kredite steigt die Quote scheinbar von 15,6 % (2013) auf 23,3 % (2016) und
--           faellt 2018 auf 15,8 %. Nur die Jahrgaenge bis 2013 sind vollstaendig ausgereift (100 %), 2014 und 2015
--           zu 73-75 % (nur die 36-Monats-Kredite), ab 2016 gar nicht. Die Werte ab 2016 sind nicht belastbar.
SELECT
    year(issue_date)                                AS issue_year,
    count(*)                                        AS loans_closed,
    round(100.0 * avg("default"), 2)                AS default_rate_all_closed_pct,
    count(*) FILTER (WHERE issue_date + INTERVAL (term_months) MONTH <= DATE '2018-12-01')
                                                    AS loans_matured,
    round(100.0 * avg("default") FILTER (WHERE issue_date + INTERVAL (term_months) MONTH <= DATE '2018-12-01'), 2)
                                                    AS default_rate_matured_pct,
    round(100.0 * count(*) FILTER (WHERE issue_date + INTERVAL (term_months) MONTH <= DATE '2018-12-01') / count(*), 1)
                                                    AS matured_share_pct
FROM loans
GROUP BY issue_year
ORDER BY issue_year;


-- Abfrage 11b: Vintage-Kurve getrennt nach Laufzeit, nur ausgereifte Kredite
-- Frage: Ab 2014 sind nur noch 36-Monats-Kredite ausgereift. Wie sehen die Jahrgaenge aus, wenn
--        man 36- und 60-Monats-Kredite getrennt betrachtet, damit sich die Mischung nicht aendert?
-- Ergebnis: 36 Monate: 2010 10,9 %, 2011 10,6 %, 2012 13,6 %, 2013 12,3 %, 2014 13,7 %, 2015 14,9 %, also ein
--           leichter Anstieg. 60 Monate (nur bis 2013 ausgereift): 22,4 % bis 27,7 %, rund doppelt so hoch.
--           Die Mischung aus beiden Laufzeiten erklaert den Sprung zwischen 2013 und 2014 in Abfrage 11.
SELECT
    year(issue_date)                                AS issue_year,
    count(*) FILTER (WHERE term_months = 36)        AS loans_36m,
    round(100.0 * avg("default") FILTER (WHERE term_months = 36), 2) AS default_rate_36m_pct,
    count(*) FILTER (WHERE term_months = 60)        AS loans_60m,
    round(100.0 * avg("default") FILTER (WHERE term_months = 60), 2) AS default_rate_60m_pct
FROM loans
WHERE issue_date + INTERVAL (term_months) MONTH <= DATE '2018-12-01'
GROUP BY issue_year
ORDER BY issue_year;


-- Abfrage 12: Vintage nach Quartal mit Volumen (CTE), nur ausgereifte Kredite
-- Frage: Wie haengen Wachstum des Neugeschaefts und Ausfallquote je Quartal zusammen?
-- Ergebnis: Das Neugeschaeft waechst von 110 Mio. USD (Q1 2012) auf 1,13 Mrd. USD (Q4 2015) je Quartal, also mehr als
--           verzehnfacht. Die Ausfallquote der ausgereiften Kredite bleibt dabei zwischen 12,9 % und 17,0 %,
--           mit einem leichten Anstieg ab 2014 (Vorsicht: ab 2014 nur 36-Monats-Kredite enthalten).
WITH matured_loans AS (
    SELECT
        year(issue_date)                                    AS issue_year,
        quarter(issue_date)                                 AS issue_quarter,
        funded_amnt,
        "default"
    FROM loans
    WHERE issue_date + INTERVAL (term_months) MONTH <= DATE '2018-12-01'
),
by_quarter AS (
    SELECT
        issue_year,
        issue_quarter,
        count(*)                                            AS loans,
        round(sum(funded_amnt) / 1e6, 1)                    AS volume_mn_usd,
        round(100.0 * avg("default"), 2)                    AS default_rate_pct
    FROM matured_loans
    GROUP BY issue_year, issue_quarter
)
SELECT *
FROM by_quarter
WHERE issue_year >= 2012
ORDER BY issue_year, issue_quarter;


-- Abfrage 13: Entwicklung von Kreditsumme und Zinssatz ueber die Zeit (Window Function LAG)
-- Frage: Wie haben sich durchschnittliche Kreditsumme und Zinssatz von Jahr zu Jahr veraendert?
-- LAG holt den Wert des Vorjahres in dieselbe Zeile, so dass die Veraenderung direkt berechenbar ist.
-- Ergebnis: Die Kreditsumme steigt von 7.946 USD (2007) auf rund 14.500 USD (ab 2013) und stagniert dann. Der
--           Zinssatz schwankt zwischen 11,8 % und 14,5 %: Hoch 2013 (14,53 %), Tief 2015 (12,39 %), danach wieder
--           steigend. LAG liefert die Veraenderung zum Vorjahr in derselben Zeile.
WITH by_year AS (
    SELECT
        year(issue_date)                                    AS issue_year,
        count(*)                                            AS loans,
        round(avg(funded_amnt), 0)                          AS avg_loan_usd,
        round(avg(int_rate), 2)                             AS avg_int_rate_pct
    FROM loans
    GROUP BY issue_year
)
SELECT
    issue_year,
    loans,
    avg_loan_usd,
    round(100.0 * (avg_loan_usd - LAG(avg_loan_usd) OVER (ORDER BY issue_year))
              / LAG(avg_loan_usd) OVER (ORDER BY issue_year), 1)          AS avg_loan_change_pct,
    avg_int_rate_pct,
    round(avg_int_rate_pct - LAG(avg_int_rate_pct) OVER (ORDER BY issue_year), 2)
                                                                          AS int_rate_change_pp
FROM by_year
ORDER BY issue_year;
