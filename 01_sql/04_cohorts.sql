-- 04_cohorts.sql  --  AP2, Abfragen 14 und 15: fortgeschrittene Auswertungen
-- Datengrundlage: Sicht `loans` = data/processed/loans_clean.parquet (nur abgeschlossene Kredite).
-- Ausfuehren: .venv/Scripts/python.exe 02_python/run_sql.py 01_sql/04_cohorts.sql


-- Abfrage 14: Kohortentabelle Ausgabejahr x Grade, Ausfallquote als Matrix
-- Frage: Gilt "hoeherer Grade = hoehere Ausfallquote" in jedem Jahrgang, und verschiebt sich
--        das Niveau ueber die Zeit?
-- Nur ausgereifte Kredite (volle Laufzeit vor Datenende), damit die Jahrgaenge vergleichbar sind.
-- Bedingte Aggregation (avg ... FILTER) statt PIVOT, damit die Abfrage in jeder SQL-Datenbank laeuft.
-- Ergebnis: In jedem ausgereiften Jahrgang gilt A < B < C < D < E < F (< G), die Einstufung funktioniert also
--           durchgehend. Das Niveau schwankt je Grade: A liegt stabil bei 5-7 %, G zwischen 32 % und 49 %.
--           2015 liegen D bis G deutlich hoeher als 2013/2014 (z. B. F 42,4 % vs. 29,5 %).
SELECT
    year(issue_date)                                            AS issue_year,
    count(*)                                                    AS loans_matured,
    round(100.0 * avg("default") FILTER (WHERE grade = 'A'), 1) AS grade_a_pct,
    round(100.0 * avg("default") FILTER (WHERE grade = 'B'), 1) AS grade_b_pct,
    round(100.0 * avg("default") FILTER (WHERE grade = 'C'), 1) AS grade_c_pct,
    round(100.0 * avg("default") FILTER (WHERE grade = 'D'), 1) AS grade_d_pct,
    round(100.0 * avg("default") FILTER (WHERE grade = 'E'), 1) AS grade_e_pct,
    round(100.0 * avg("default") FILTER (WHERE grade = 'F'), 1) AS grade_f_pct,
    round(100.0 * avg("default") FILTER (WHERE grade = 'G'), 1) AS grade_g_pct
FROM loans
WHERE issue_date + INTERVAL (term_months) MONTH <= DATE '2018-12-01'
GROUP BY issue_year
ORDER BY issue_year;


-- Abfrage 15: Konzentrationsanalyse nach Grade (kumulierte Anteile, Window Function)
-- Frage: Wo sitzt das Risiko? Welcher Anteil des Volumens und welcher Anteil der Ausfaelle
--        entfaellt auf die Grades, kumuliert von A nach G?
-- SUM() OVER (ORDER BY grade) summiert Zeile fuer Zeile auf; so sieht man z. B. "A bis C
--        sind X % des Volumens, aber nur Y % der ausgefallenen Kredite".
-- Ergebnis: A bis C sind 71,5 % des Volumens, aber nur 51,9 % des ausgefallenen Volumens. D bis G sind 28,5 % des
--           Volumens und 48,1 % des ausgefallenen Volumens. Allein Grade C traegt 30,2 % der Ausfaelle, weil es
--           gross (27,9 %) und mittel riskant (23,3 %) ist. Das Risiko sitzt also in C und D, nicht nur in F/G.
WITH by_grade AS (
    SELECT
        grade,
        count(*)                                    AS loans,
        sum(funded_amnt)                            AS volume_usd,
        sum("default")                              AS defaults,
        sum(funded_amnt * "default")                AS defaulted_volume_usd
    FROM loans
    GROUP BY grade
)
SELECT
    grade,
    loans,
    round(volume_usd / 1e9, 2)                                              AS volume_bn_usd,
    round(100.0 * volume_usd / sum(volume_usd) OVER (), 1)                  AS volume_share_pct,
    round(100.0 * sum(volume_usd) OVER (ORDER BY grade) / sum(volume_usd) OVER (), 1)
                                                                            AS volume_share_cum_pct,
    round(100.0 * defaulted_volume_usd / sum(defaulted_volume_usd) OVER (), 1)
                                                                            AS defaulted_volume_share_pct,
    round(100.0 * sum(defaulted_volume_usd) OVER (ORDER BY grade) / sum(defaulted_volume_usd) OVER (), 1)
                                                                            AS defaulted_volume_share_cum_pct,
    round(100.0 * defaulted_volume_usd / volume_usd, 2)                     AS default_rate_by_volume_pct
FROM by_grade
ORDER BY grade;
