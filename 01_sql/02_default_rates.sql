-- 02_default_rates.sql  --  AP2, Abfragen 1 bis 10: Grundlagen und Segmentierung
-- Datengrundlage: Sicht `loans` = data/processed/loans_clean.parquet (nur abgeschlossene Kredite).
-- Ausfuehren: .venv/Scripts/python.exe 02_python/run_sql.py 01_sql/02_default_rates.sql
--
-- Hinweis zu allen Ausfallquoten: "default" ist 1 fuer Charged Off / Default und 0 fuer Fully Paid.
-- avg("default") ist deshalb direkt der Anteil ausgefallener Kredite.


-- Abfrage 1: Portfolio-Uebersicht
-- Frage: Wie gross ist das bereinigte Portfolio, und wie hoch ist die Ausfallquote insgesamt?
-- Ergebnis: 1.348.099 Kredite, 19,41 Mrd. USD ausgezahlt, durchschnittlich 14.400 USD je Kredit. 269.360 Ausfaelle,
--           Ausfallquote 19,98 % nach Anzahl und 21,56 % nach Volumen (groessere Kredite fallen oefter aus).
SELECT
    count(*)                                        AS loans,
    round(sum(funded_amnt) / 1e9, 2)                AS volume_bn_usd,
    round(avg(funded_amnt), 0)                      AS avg_loan_usd,
    sum("default")                                  AS defaults,
    round(100.0 * avg("default"), 2)                AS default_rate_pct,
    -- Volumengewichtete Ausfallquote: Anteil des ausgezahlten Volumens, das ausgefallen ist
    round(100.0 * sum(funded_amnt * "default") / sum(funded_amnt), 2) AS default_rate_by_volume_pct
FROM loans;


-- Abfrage 2: Ausfallquote nach grade (A bis G)
-- Frage: Trennt Lending Clubs eigene Risikoeinstufung die Ausfaelle sauber?
-- Ergebnis: Streng monoton: A 6,04 %, B 13,40 %, C 22,44 %, D 30,38 %, E 38,43 %, F 45,15 %, G 49,67 %.
--           Der Zinssatz steigt parallel von 7,1 % (A) auf 27,5 % (G). B und C sind mit je 28-29 % die groessten Klassen.
SELECT
    grade,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(100.0 * avg("default"), 2)                AS default_rate_pct,
    round(avg(int_rate), 2)                         AS avg_int_rate_pct
FROM loans
GROUP BY grade
ORDER BY grade;


-- Abfrage 3: Ausfallquote nach sub_grade (A1 bis G5)
-- Frage: Ist die feinere Einstufung ebenfalls monoton, oder gibt es Ausreisser?
-- Ergebnis: Auch auf sub_grade-Ebene fast durchgehend monoton, von A1 3,23 % bis G5 52,66 %. Kleine Ausreisser nur
--           in den duenn besetzten Klassen F3 (45,02 % < F2 45,22 %) und G1 (47,71 % < F5 49,15 %).
SELECT
    sub_grade,
    count(*)                                        AS loans,
    round(100.0 * avg("default"), 2)                AS default_rate_pct,
    round(avg(int_rate), 2)                         AS avg_int_rate_pct
FROM loans
GROUP BY sub_grade
ORDER BY sub_grade;


-- Abfrage 4: Ausfallquote nach Laufzeit (36 vs. 60 Monate)
-- Frage: Sind laengere Kredite riskanter?
-- Ergebnis: 60-Monats-Kredite fallen mit 32,45 % doppelt so oft aus wie 36-Monats-Kredite mit 16,02 %. Sie sind
--           24,1 % der Kredite, aber im Schnitt groesser (20.275 vs. 12.535 USD).
SELECT
    term_months,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(avg(funded_amnt), 0)                      AS avg_loan_usd,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
GROUP BY term_months
ORDER BY term_months;


-- Abfrage 5: Ausfallquote nach Verwendungszweck (purpose)
-- Frage: Welcher Verwendungszweck ist riskant, welcher sicher?
-- Ergebnis: Riskantester Zweck: small_business mit 29,86 % (nur 1,2 % der Kredite). Sicherste: wedding 12,43 %,
--           car 14,72 %, credit_card 16,93 %. Der dominierende Zweck debt_consolidation (58 %) liegt bei 21,16 %.
SELECT
    purpose,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
GROUP BY purpose
ORDER BY default_rate_pct DESC;


-- Abfrage 6: Ausfallquote nach Einkommensklasse
-- Frage: Faellt die Ausfallquote mit steigendem Jahreseinkommen?
-- ENTSCHEIDUNG: Feste Klassengrenzen (CASE WHEN) statt Quantile (NTILE), weil feste Grenzen
-- im Gespraech leichter zu benennen sind ("unter 40.000 USD"). Die Grenzen sind grob an
-- den Quartilen des Portfolios orientiert.
-- Ergebnis: Monoton fallend: unter 40k 23,77 %, 40-60k 21,70 %, 60-80k 20,10 %, 80-120k 17,63 %, ab 120k 15,62 %.
--           Der Effekt ist klar, aber schwaecher als bei grade oder term.
SELECT
    CASE
        WHEN annual_inc <  40000 THEN '1: unter 40k'
        WHEN annual_inc <  60000 THEN '2: 40k bis 60k'
        WHEN annual_inc <  80000 THEN '3: 60k bis 80k'
        WHEN annual_inc < 120000 THEN '4: 80k bis 120k'
        ELSE                          '5: ab 120k'
    END                                             AS income_band,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
WHERE annual_inc IS NOT NULL
GROUP BY income_band
ORDER BY income_band;


-- Abfrage 7: Ausfallquote nach Bundesstaat (addr_state)
-- Frage: Gibt es geografische Konzentration von Volumen oder Risiko?
-- Nur Staaten mit mindestens 5.000 Krediten, sonst schwanken die Quoten zufaellig.
-- Ergebnis: Spanne von 14,4 % (OR) bis 26,1 % (MS). Die Suedstaaten MS, AR, AL, OK, LA liegen oben, OR, NH, CO, WA
--           unten. Volumen konzentriert sich auf CA (15,0 %), TX (8,4 %), NY (8,4 %), FL (7,3 %).
SELECT
    addr_state,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(sum(funded_amnt) / 1e9, 2)                AS volume_bn_usd,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
GROUP BY addr_state
HAVING count(*) >= 5000
ORDER BY default_rate_pct DESC;


-- Abfrage 8: Ausfallquote nach home_ownership und verification_status (zweidimensional)
-- Frage: Sind Mieter riskanter als Eigentuemer, und aendert eine Einkommensverifikation etwas?
-- Ergebnis: Mieter fallen in jeder Verifikationsstufe haeufiger aus als Hypothekenkunden (z. B. Verified: RENT 27,88 %
--           vs. MORTGAGE 20,77 %). Ueberraschend: 'Verified' hat ueberall die hoechste Ausfallquote, 'Not Verified'
--           die niedrigste. Lending Club prueft das Einkommen gezielt bei riskanteren Antraegen (Selektionseffekt).
SELECT
    home_ownership,
    verification_status,
    count(*)                                        AS loans,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
WHERE home_ownership IN ('MORTGAGE', 'RENT', 'OWN')
GROUP BY home_ownership, verification_status
ORDER BY home_ownership, verification_status;


-- Abfrage 9: Ausfallquote nach DTI-Klassen (Schulden-zu-Einkommen)
-- Frage: Steigt die Ausfallquote mit der Verschuldung relativ zum Einkommen?
-- Ergebnis: Monoton steigend: unter 10 14,93 %, 10-20 17,86 %, 20-30 23,05 %, 30-40 29,09 %, ab 40 30,55 %.
--           Nur 374 Kredite ohne dti.
SELECT
    CASE
        WHEN dti IS NULL THEN '0: fehlt'
        WHEN dti < 10  THEN '1: unter 10'
        WHEN dti < 20  THEN '2: 10 bis 20'
        WHEN dti < 30  THEN '3: 20 bis 30'
        WHEN dti < 40  THEN '4: 30 bis 40'
        ELSE                '5: ab 40'
    END                                             AS dti_band,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
GROUP BY dti_band
ORDER BY dti_band;


-- Abfrage 10: Ausfallquote nach FICO-Baendern
-- Frage: Wie stark trennt der FICO-Score bei Antrag die Ausfaelle?
-- fico_range_low ist die Untergrenze des 5-Punkte-Bandes, das Lending Club berichtet.
-- Ergebnis: Monoton fallend: 660-679 25,30 %, 680-699 21,45 %, 700-719 17,30 %, 720-749 13,36 %, ab 750 8,89 %.
--           Unter 660 gibt es fast keine Kredite (489), weil Lending Club dort kaum vergibt.
SELECT
    CASE
        WHEN fico_range_low < 660 THEN '1: unter 660'
        WHEN fico_range_low < 680 THEN '2: 660 bis 679'
        WHEN fico_range_low < 700 THEN '3: 680 bis 699'
        WHEN fico_range_low < 720 THEN '4: 700 bis 719'
        WHEN fico_range_low < 750 THEN '5: 720 bis 749'
        ELSE                           '6: ab 750'
    END                                             AS fico_band,
    count(*)                                        AS loans,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS share_pct,
    round(100.0 * avg("default"), 2)                AS default_rate_pct
FROM loans
GROUP BY fico_band
ORDER BY fico_band;
