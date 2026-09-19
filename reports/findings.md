# Findings

Pro Arbeitspaket drei Teile: Was wurde gemacht, was kam heraus, warum so entschieden.
Alle Zahlen stammen aus `reports/ap1_summary.md` bzw. den Abfragen in `01_sql/`.

---

## AP1: Daten laden und verstehen

### Was wurde gemacht

1. Die Kaggle-Rohdatei `accepted_2007_to_2018Q4.csv.gz` (1,3 GB gepackt) wurde einmalig mit DuckDB
   direkt aus dem gepackten Zustand in die Tabelle `loans_raw` in `data/credit.duckdb` geladen
   (`01_sql/00_setup.sql`, ca. 2 Minuten). Alle Spalten zunächst als Text.
2. Vier Erkundungsabfragen (`01_sql/01_exploration.sql`): erste Zeilen mit LIMIT, Verteilung von
   `loan_status`, Kredite und Volumen je Ausgabejahr, Fehlquoten der Kernspalten.
3. Zielvariable `default` gebaut, laufende Kredite ausgeschlossen.
4. Leckage-Ausschlussliste mit 38 Spalten im Code festgehalten und angewendet.
5. Datentypen bereinigt: `term` zu Ganzzahl (`term_months`), `emp_length` zu Ganzzahl 0 bis 10
   (`emp_length_years`), `issue_d` und `earliest_cr_line` zu Datum, alle Zahlenspalten von Text zu Zahl.
6. `data/processed/loans_clean.parquet` (41 Spalten) und `data/processed/lgd_inputs.parquet`
   (nur ausgefallene Kredite, nur für die LGD in AP6) geschrieben.

### Was kam heraus

| Kennzahl | Wert |
|---|---|
| Zeilen Rohdatei | 2.260.701 (davon 33 Summenzeilen ohne Kredit) |
| Spalten Rohdatei | 151 |
| Kredite mit bekanntem Ausgang (Fully Paid, Charged Off, Default) | 1.348.099 (59,6 %) |
| Laufende Kredite, ausgeschlossen (Current, Late, In Grace Period) | 912.569 (40,4 %) |
| Ausfälle (`default = 1`) | 269.360 |
| Ausfallquote | 19,98 % |
| Ausfallquote 36 Monate / 60 Monate | 16,02 % / 32,45 % |
| Ausgezahltes Volumen (bereinigt) | 19,41 Mrd. USD |
| Zeitraum `issue_d` | Juni 2007 bis Dezember 2018 |
| Leckage-Spalten ausgeschlossen | 38 |
| Spalten in `loans_clean.parquet` | 41 |
| Größe `loans_clean.parquet` | 47,3 MB |

Verteilung von `loan_status` in der Rohdatei:

| loan_status | Kredite | Anteil |
|---|---|---|
| Fully Paid | 1.076.751 | 47,63 % |
| Current | 878.317 | 38,85 % |
| Charged Off | 268.559 | 11,88 % |
| Late (31-120 days) | 21.467 | 0,95 % |
| In Grace Period | 8.436 | 0,37 % |
| Late (16-30 days) | 4.349 | 0,19 % |
| Does not meet the credit policy. Status:Fully Paid | 1.988 | 0,09 % |
| Does not meet the credit policy. Status:Charged Off | 761 | 0,03 % |
| Default | 40 | 0,00 % |
| (leer, Summenzeilen) | 33 | 0,00 % |

Kredite je Ausgabejahr (Rohdatei) und Anteil mit bekanntem Ausgang:

| Jahr | Kredite | davon abgeschlossen | Ausfallquote der abgeschlossenen |
|---|---|---|---|
| 2007 | 603 | 603 | 26,20 % |
| 2008 | 2.393 | 2.393 | 20,73 % |
| 2009 | 5.281 | 5.281 | 13,69 % |
| 2010 | 12.537 | 12.537 | 14,01 % |
| 2011 | 21.721 | 21.721 | 15,18 % |
| 2012 | 53.367 | 53.367 | 16,20 % |
| 2013 | 134.814 | 134.804 | 15,60 % |
| 2014 | 235.629 | 223.103 | 18,45 % |
| 2015 | 421.095 | 375.546 | 20,19 % |
| 2016 | 434.407 | 293.105 | 23,29 % |
| 2017 | 443.579 | 169.321 | 23,13 % |
| 2018 | 495.242 | 56.318 | 15,76 % |

Wichtige Beobachtung: Ab 2016 ist weniger als die Hälfte eines Jahrgangs abgeschlossen. Die Ausfallquote
der jungen Jahrgänge (besonders 2018) ist deshalb nicht mit älteren vergleichbar. Bei jungen Jahrgängen
sind bisher vor allem die Kredite abgeschlossen, die früh ausgefallen oder früh vollständig zurückgezahlt
wurden. Das ist das Reifegrad-Problem, es wird in AP2 (Vintage-Analyse)
ausdrücklich behandelt.

Fehlende Werte (Rohdatei): `issue_d` 0 %, `dti` und `revol_util` je 0,08 %, `emp_length` 6,5 %,
`mort_acc` 2,2 %, `bc_util` 3,4 %, `mths_since_last_delinq` 51,3 %, `mths_since_last_record` 84,1 %.
Nach der Typumwandlung fehlen `issue_date` und `term_months` bei 0 Krediten, `earliest_cr_line_date`
bei 29 Krediten.

### Warum so entschieden

- **Zielvariable und Ausschluss laufender Kredite.** `Charged Off` und `Default` sind Ausfall (1),
  `Fully Paid` ist kein Ausfall (0). `Current`, `Late` und `In Grace Period` sind raus, weil ihr Ausgang
  offen ist. Würde man sie als "gut" zählen, läge die Ausfallquote statt bei 19,98 % bei nur rund 12 %
  (269.360 von 2,26 Mio.), also systematisch zu niedrig. Das ist ein Zensierungsproblem.
- **Status mit Zusatz "Does not meet the credit policy".** Diese 2.749 alten Kredite wurden nach einer
  früheren Vergaberegel angenommen, ihr Ausgang ist aber bekannt. Sie werden wie ihr Kernstatus behandelt.
  Ein Ausschluss hätte bei 1,35 Mio. Krediten nichts geändert.
- **Leckage-Ausschlussliste explizit im Code.** 38 Spalten, die erst nach der Kreditvergabe entstehen:
  Zahlungen und Rückflüsse (`total_pymnt`, `total_rec_*`), Verwertungserlöse (`recoveries`,
  `collection_recovery_fee`), letzte und nächste Zahlung, offener Restsaldo (`out_prncp*`), später
  abgerufene Bonitätsdaten (`last_credit_pull_d`, `last_fico_range_*`), Zahlungsplan (`pymnt_plan`),
  15 Härtefall-Spalten (`hardship_*` u. a.) und 7 Vergleichs-Spalten (`settlement_*`,
  `debt_settlement_flag*`). Die Liste ist bewusst breiter als die üblichen Beispiele (Zahlungen, Rückflüsse), weil
  auch `last_fico_range_*` und `pymnt_plan` Wissen aus der Zukunft sind. Das Skript bricht ab, wenn ein
  Name der Liste nicht in der Rohdatei existiert (Schutz vor Tippfehlern).
- **Spaltenauswahl.** Neben den klassischen Modell- und Analysespalten (Kredit, Kreditnehmer, Bonität) bleiben einige gängige
  Kreditbüro-Merkmale (`mort_acc`, `pub_rec_bankruptcies`, `acc_open_past_24mths`, `bc_util`,
  `tot_cur_bal`, `total_rev_hi_lim`, `num_tl_90g_dpd_24m`, `mo_sin_old_rev_tl_op`,
  `mths_since_recent_inq`) sowie `initial_list_status` und `application_type`. Alle stammen aus dem
  Antrag oder der Kreditauskunft bei Antragstellung. Rund 90 weitere Spalten (Zweitantragsteller,
  Detail-Kontozähler) wurden weggelassen: sehr lückenhaft oder für einen Einsteiger schwer erklärbar.
- **`grade`, `sub_grade`, `int_rate` bleiben in der Datei,** aber nur für die SQL-Analysen (AP2) und das
  Benchmark-Modell B. Im Hauptmodell A werden sie ausgeschlossen (siehe AP3/AP4).
- **LGD-Eingaben in separater Datei.** `recoveries` und `total_rec_prncp` sind Leckage und gehören nicht
  in `loans_clean`. Für die LGD-Schätzung auf bereits ausgefallenen Krediten sind sie legitim. Deshalb
  liegen sie in `lgd_inputs.parquet` (269.360 Zeilen), so dass ab AP2 nie mehr die Rohdatei nötig ist und
  das PD-Modell sie nicht sehen kann.
- **Rohdatei direkt aus dem .gz lesen und in DuckDB materialisieren.** Kein Entpacken nötig, das Repo läuft
  mit dem unveränderten Kaggle-Download. Die Tabelle `loans_raw` (ca. 650 MB DuckDB-Datei) macht alle
  Explorationsabfragen sekundenschnell. Alle Spalten wurden zunächst als Text eingelesen und dann
  kontrolliert umgewandelt; vor dem Umwandeln prüft das Skript, dass jeder Wert eine Zahl ist (0 Fehler).
- **`emp_length` ordinal.** "< 1 year" wird 0, "10+ years" wird 10, fehlend bleibt fehlend (78.550
  Kredite) und wird ab AP3 als eigene Kategorie behandelt, nicht imputiert.

### Abnahmekriterium AP1

Erfüllt. Nach dem Filter bleiben 1.348.099 Kredite, die Ausfallquote ist 19,98 %, und die 38
ausgeschlossenen Spalten sind mit Begründung im Code (`02_python/01_data_prep.py`, Liste
`LEAKAGE_COLUMNS`) und oben dokumentiert.

---

## AP2: SQL-Analysen

### Was wurde gemacht

15 SQL-Abfragen (plus eine Zusatzabfrage 11b) in drei Dateien, alle auf der Sicht `loans`, die direkt
`data/processed/loans_clean.parquet` liest. Ausführung mit `02_python/run_sql.py`, das die Sicht anlegt
und jede Abfrage ausgibt. Jede Abfrage hat im Kommentar die fachliche Frage und das Ergebnis mit Zahl.

| Datei | Abfragen |
|---|---|
| `01_sql/02_default_rates.sql` | 1 Portfolio, 2 grade, 3 sub_grade, 4 term, 5 purpose, 6 Einkommen, 7 Bundesstaat, 8 home_ownership x verification, 9 DTI, 10 FICO |
| `01_sql/03_vintage.sql` | 11 Vintage je Jahr mit Reifegrad, 11b Vintage je Laufzeit, 12 Vintage je Quartal (CTE), 13 Kreditsumme und Zins mit LAG |
| `01_sql/04_cohorts.sql` | 14 Kohortenmatrix Jahr x Grade, 15 Konzentration nach Grade (kumulierte Anteile) |

### Was kam heraus

**Portfolio (Abfrage 1):** 1.348.099 Kredite, 19,41 Mrd. USD, Ausfallquote 19,98 % nach Anzahl und 21,56 %
nach Volumen. Größere Kredite fallen also etwas öfter aus.

**Die stärksten Treiber (Abfragen 2 bis 10):**

| Segment | niedrigste Quote | höchste Quote |
|---|---|---|
| grade (2) | A 6,04 % | G 49,67 % |
| term (4) | 36 Monate 16,02 % | 60 Monate 32,45 % |
| FICO (10) | ab 750: 8,89 % | 660-679: 25,30 % |
| DTI (9) | unter 10: 14,93 % | ab 40: 30,55 % |
| Einkommen (6) | ab 120k: 15,62 % | unter 40k: 23,77 % |
| purpose (5) | wedding 12,43 % | small_business 29,86 % |
| Bundesstaat (7) | OR 14,43 % | MS 26,11 % |
| home_ownership x verification (8) | MORTGAGE / Not Verified 12,72 % | RENT / Verified 27,88 % |

grade und sub_grade sind fast perfekt monoton (A1 3,23 % bis G5 52,66 %). Das bestätigt: Lending Clubs
eigene Einstufung enthält sehr viel Information. Genau deshalb bleibt sie aus dem Hauptmodell draußen,
sonst würden wir ein fremdes Modell kopieren statt ein eigenes zu bauen.

Überraschung in Abfrage 8: "Verified" hat in jeder Wohnform die höchste Ausfallquote, "Not Verified"
die niedrigste. Erklärung: Lending Club verlangt die Einkommensverifikation gezielt bei riskanteren
Anträgen. Der Status ist also ein Signal für Risiko, das Lending Club schon gesehen hat, nicht die
Ursache. Solche Selektionseffekte sind bei Beobachtungsdaten normal und müssen benannt werden.

**Vintage (Abfragen 11, 11b, 12):** Über alle abgeschlossenen Kredite sieht es so aus, als stiege die
Ausfallquote von 15,6 % (2013) auf 23,3 % (2016) und fiele 2018 auf 15,8 %. Das ist ein Artefakt des
Reifegrads:

| Jahrgang | abgeschlossen | davon ausgereift | Quote alle abgeschlossenen | Quote nur ausgereifte |
|---|---|---|---|---|
| 2013 | 134.804 | 100 % | 15,60 % | 15,60 % |
| 2014 | 223.103 | 72,9 % | 18,45 % | 13,73 % |
| 2015 | 375.546 | 75,4 % | 20,19 % | 14,89 % |
| 2016 | 293.105 | 0 % | 23,29 % | nicht berechenbar |
| 2017 | 169.321 | 0 % | 23,13 % | nicht berechenbar |
| 2018 | 56.318 | 0 % | 15,76 % | nicht berechenbar |

Getrennt nach Laufzeit (11b) steigt die Quote der 36-Monats-Kredite leicht von 10,9 % (2010) auf 14,9 %
(2015). 60-Monats-Kredite (nur bis 2013 ausgereift) liegen bei 22 bis 28 %, rund doppelt so hoch. Der
Sprung zwischen 2013 und 2014 in Abfrage 11 kommt daher, dass ab 2014 nur noch 36-Monats-Kredite
ausgereift sind, die Mischung sich also ändert.

Das Neugeschäft ist von 110 Mio. USD (Q1 2012) auf 1,13 Mrd. USD (Q4 2015) je Quartal gewachsen, die
Ausfallquote der ausgereiften Kredite blieb dabei zwischen 12,9 % und 17,0 % (Abfrage 12).

**Kreditsumme und Zins (13):** Durchschnittliche Kreditsumme von 7.946 USD (2007) auf rund 14.500 USD
(ab 2013), danach stabil. Zinssatz zwischen 11,8 % und 14,5 %, Hoch 2013, Tief 2015.

**Kohorten (14):** In jedem ausgereiften Jahrgang gilt A < B < C < D < E < F. Grade A liegt stabil bei
5 bis 7 %, die schlechten Grades schwanken stark (F: 29,5 % in 2014, 42,4 % in 2015).

**Konzentration (15):** A bis C sind 71,5 % des Volumens, aber nur 51,9 % des ausgefallenen Volumens.
D bis G sind 28,5 % des Volumens und tragen 48,1 % der Ausfälle. Allein Grade C trägt 30,2 % des
ausgefallenen Volumens, weil die Klasse groß und mittel riskant ist. Das Risiko sitzt in absoluten Zahlen
in C und D, nicht nur in F und G.

### Warum so entschieden

- **Reifegrad über "volle Laufzeit vor Datenende".** Ein Kredit gilt als ausgereift, wenn
  issue_date + term_months <= Dezember 2018. Die Alternative (Ausfälle in den ersten 24 Monaten zählen)
  bräuchte den Ausfallzeitpunkt, der nur aus der Leckage-Spalte last_pymnt_d ableitbar wäre. Diese
  Spalte liegt bewusst nicht in loans_clean.
- **Vintage zusätzlich je Laufzeit (11b).** Ohne die Trennung vermischt sich ab 2014 der Reifegrad-Effekt
  mit dem Laufzeit-Effekt. Die Zusatzabfrage macht das sichtbar.
- **Feste Klassengrenzen statt NTILE** bei Einkommen, DTI und FICO, weil sich feste Grenzen im Gespräch
  benennen lassen ("unter 40.000 USD") und die Klassen für das Dashboard stabil bleiben.
- **Mindestgröße 5.000 Kredite je Bundesstaat** in Abfrage 7, sonst schwanken die Quoten kleiner
  Staaten zufällig.
- **Bedingte Aggregation statt PIVOT** in Abfrage 14, damit die Abfrage in jeder SQL-Datenbank läuft.
- **Hilfsskripte run_sql.py und common.py.** Beide stehen nicht in der ursprünglich geplanten Repo-Struktur.
  Sie sind reine Ausführungshilfe (Sicht `loans` anlegen, SQL-Datei ausführen, Ergebnis drucken), damit
  die SQL-Dateien ohne Kopieren in eine Konsole laufen.

### Abnahmekriterium AP2

Erfüllt. Alle 15 Abfragen (plus 11b) laufen mit `.venv/Scripts/python.exe 02_python/run_sql.py`,
jede hat Frage und Ergebnis im Kommentar, und die Interpretation steht oben.

---

## AP3: Feature-Aufbereitung, zeitbasierter Split, WoE-Binning

### Was wurde gemacht

1. Modellspalten aus `loans_clean.parquet` geladen (nie die ganze Datei), zwei Merkmale abgeleitet:
   `credit_history_months` (Monate zwischen erster Kreditlinie und Vergabe) und `loan_to_income`
   (Kreditsumme geteilt durch Jahreseinkommen).
2. Zeitbasierter Split über `issue_date`, Schnitt 1. Januar 2016. Das Skript prüft per `assert`, dass
   der jüngste Trainingskredit älter ist als der älteste Testkredit.
3. WoE-Binning mit optbinning auf den Trainingsdaten: 32 Kandidaten für Modell A (ohne grade,
   sub_grade, int_rate), getrennt davon die drei Benchmark-Merkmale. Fehlende Werte bekommen automatisch
   einen eigenen Bin ("Missing"), es wird nichts imputiert. Bei Zahlenvariablen wird Monotonie erzwungen.
4. Information Value je Variable, Leckage-Warnung bei IV > 0,5, Auswahl bei IV >= 0,02.
5. Ergebnisse: `reports/iv_table.csv`, `reports/woe_bins.csv`, `reports/figures/iv_ranking.png`, WoE-Charts
   der fünf stärksten Variablen, Binning-Prozess als Pickle für AP4.

### Was kam heraus

**Split:**

| Teil | Kredite | Zeitraum | Ausfallquote |
|---|---|---|---|
| Train | 829.355 (61,5 %) | Juni 2007 bis Dezember 2015 | 18,46 % |
| Test | 518.744 (38,5 %) | Januar 2016 bis Dezember 2018 | 22,42 % |

Die höhere Ausfallquote im Test ist der Reifegrad-Effekt aus AP2: Von 2016 bis 2018 sind nur früh
abgeschlossene Kredite enthalten, und darunter sind überdurchschnittlich viele frühe Ausfälle.

**IV-Tabelle Modell A (Train), alle 32 Kandidaten:**

| Variable | IV | Klasse | ausgewählt |
|---|---|---|---|
| term_months | 0,238 | mittel | ja |
| loan_to_income | 0,126 | mittel | ja |
| fico_range_low | 0,122 | mittel | ja |
| acc_open_past_24mths | 0,082 | schwach | ja |
| dti | 0,075 | schwach | ja |
| verification_status | 0,050 | schwach | ja |
| mths_since_recent_inq | 0,038 | schwach | ja |
| loan_amnt | 0,036 | schwach | ja |
| tot_cur_bal | 0,033 | schwach | ja |
| annual_inc | 0,032 | schwach | ja |
| inq_last_6mths | 0,028 | schwach | ja |
| bc_util | 0,028 | schwach | ja |
| total_rev_hi_lim | 0,028 | schwach | ja |
| mort_acc | 0,028 | schwach | ja |
| mo_sin_old_rev_tl_op | 0,023 | schwach | ja |
| revol_util | 0,023 | schwach | ja |
| home_ownership | 0,021 | schwach | ja |
| purpose | 0,018 | nicht prädiktiv | nein |
| addr_state | 0,014 | nicht prädiktiv | nein |
| credit_history_months | 0,010 | nicht prädiktiv | nein |
| open_acc | 0,008 | nicht prädiktiv | nein |
| emp_length_years | 0,006 | nicht prädiktiv | nein |
| mths_since_last_record | 0,006 | nicht prädiktiv | nein |
| pub_rec | 0,005 | nicht prädiktiv | nein |
| pub_rec_bankruptcies | 0,004 | nicht prädiktiv | nein |
| num_tl_90g_dpd_24m | 0,004 | nicht prädiktiv | nein |
| revol_bal | 0,004 | nicht prädiktiv | nein |
| mths_since_last_delinq | 0,002 | nicht prädiktiv | nein |
| delinq_2yrs | 0,002 | nicht prädiktiv | nein |
| initial_list_status | 0,001 | nicht prädiktiv | nein |
| total_acc | 0,000 | nicht prädiktiv | nein |
| application_type | 0,000 | nicht prädiktiv | nein |

Benchmark-Merkmale (nur Modell B): sub_grade 0,498, grade 0,469, int_rate 0,466. Alle drei "stark",
keines über 0,5.

**Die drei Prüfungen nach AP3:**

| Prüfung | Ergebnis |
|---|---|
| Split zeitbasiert über issue_d, nicht zufällig? | Ja. Train endet Dezember 2015, Test beginnt Januar 2016, per assert geprüft. |
| Eine Variable mit IV > 0,5 (Leckage-Warnsignal)? | Nein. Höchster Wert im Hauptmodell: term_months 0,238. Auch die Benchmark-Merkmale bleiben unter 0,5. |
| optbinning ohne Fehler durch alle Variablen? | Ja. Alle 35 Variablen mit Löser-Status OPTIMAL, Laufzeit 18 Sekunden. |

**Die fünf stärksten Variablen fachlich erklärt:**

- **term_months (0,238):** 60-Monats-Kredite fallen mit 31,9 % im Training aus, 36-Monats-Kredite mit
  13,9 %. Längere Laufzeit heißt länger Zeit für Jobverlust oder Krankheit, und wer 60 Monate wählt,
  braucht die niedrigere Rate oft, weil das Budget knapp ist.
- **loan_to_income (0,126):** Von 11,1 % Ausfallquote (Kredit unter 6 % des Jahreseinkommens) bis 28,6 %
  (über 40 %). Je größer der Kredit im Verhältnis zum Einkommen, desto schwerer wiegt jede Rate. Die
  abgeleitete Variable ist stärker als loan_amnt (0,036) und annual_inc (0,032) einzeln.
- **fico_range_low (0,122):** Streng monoton von 24,8 % (unter 662) bis 7,3 % (ab 752). Der FICO-Score
  fasst die Zahlungshistorie beim Kreditbüro zusammen, also genau das, was für Kreditrisiko zählt.
- **acc_open_past_24mths (0,082):** Von 12,7 % (höchstens 1 neues Konto in 2 Jahren) bis 28,7 % (10 und
  mehr). Viele neu eröffnete Konten bedeuten wachsenden Kreditbedarf. Der Missing-Bin (50.030 Kredite,
  15,3 %) sind ältere Jahrgänge, bei denen Lending Club dieses Feld noch nicht geliefert hat.
- **dti (0,075):** Von 13,0 % (DTI unter 7,2) bis 27,8 % (über 30). Hohe laufende Schulden im Verhältnis
  zum Einkommen lassen wenig Puffer für eine weitere Rate.

Auffällig: `emp_length_years` (0,006) und die Verzugsmerkmale (`delinq_2yrs`, `mths_since_last_delinq`)
sind im Lending-Club-Portfolio kaum prädiktiv. Erklärung: Lending Club vergibt fast nur an Kunden mit
FICO über 660, das Portfolio ist also bereits vorselektiert, und die Verzugsmerkmale streuen dort kaum.

### Warum so entschieden

- **Schnittdatum 1. Januar 2016.** Damit liegen alle vollständig ausgereiften 36-Monats-Jahrgänge (bis
  2015) im Training, und der Test hat mit 518.744 Krediten genug Masse. Alternativen: Schnitt Mitte 2016
  (mehr Training, kleinerer Test) oder Schnitt 2014 (Test ausgereifter, aber Training nur 400.000
  Kredite). Nachteil des gewählten Schnitts: Der Testzeitraum ist nicht ausgereift; das wird in AP5 bei
  der Kalibrierung ausdrücklich berücksichtigt.
- **Zeitbasiert statt zufällig,** weil das Modell im Einsatz künftige Kredite bewertet. Ein zufälliger
  Split würde Kredite aus denselben Monaten in Training und Test mischen und die Güte überschätzen.
- **Fehlende Werte als eigener Bin,** nicht imputiert. "Information fehlt" ist im Kreditrisiko oft selbst
  ein Signal. Beispiel: Der Missing-Bin von acc_open_past_24mths hat eine eigene, niedrigere Ausfallquote.
- **Monotonie erzwungen** (auto_asc_desc) bei allen Zahlenvariablen. Kostet etwas Trennschärfe, macht
  aber jede Scorecard-Zeile fachlich prüfbar: Mehr Verschuldung darf nie Punkte bringen.
- **Höchstens 10 Bins, jeder Bin mindestens 2 % der Trainingsdaten.** Kleinere Bins wären Rauschen,
  mehr Bins machen die Scorecard unlesbar.
- **Auswahl rein nach IV >= 0,02.** purpose liegt mit 0,018 knapp darunter und fällt raus, obwohl es in
  AP2 einen sichtbaren Effekt hatte. Der Effekt ist real, aber klein, und die Regel ist wichtiger als
  die Ausnahme. Wer purpose drin haben will, senkt die Schwelle in `02_woe_binning.py`.
- **installment nur im Benchmark B,** weil die Rate aus Betrag, Laufzeit und Zinssatz berechnet wird und
  über den Zinssatz Lending Clubs Risikoeinstufung enthält. Ebenso funded_amnt (fast identisch mit
  loan_amnt) und fico_range_high (immer low + 4) ausgeschlossen, um Dopplungen zu vermeiden.
- **IV > 0,5 wird gemeldet, nicht automatisch entfernt.** Ob es Leckage ist, muss ein Mensch prüfen. In
  diesem Lauf war keine Meldung nötig.

### Abnahmekriterium AP3

Erfüllt. Die IV-Tabelle liegt in `reports/iv_table.csv`, die fünf stärksten Variablen sind oben
fachlich erklärt, alle drei Prüfungen (zeitbasierter Split, kein IV über 0,5, optbinning fehlerfrei)
sind positiv.

---

## AP4: Scorecard bauen

### Was wurde gemacht

1. Die 17 Variablen mit IV >= 0,02 aus AP3 gehen in eine optbinning-Scorecard: Binning (gleiche
   Parameter wie AP3), logistische Regression auf den WoE-Werten, PDO-Skalierung.
2. Skalierung: PDO = 20, 600 Punkte bei Odds 50:1 (gut zu schlecht). Factor = 20 / ln(2) = 28,85,
   Offset = 600 - 28,85 x ln(50) = 487,12. Punkte je Bin auf ganze Zahlen gerundet.
3. Vorzeichen-Regel: Jeder Koeffizient muss negativ sein (hoher WoE = weniger Ausfälle). Variablen mit
   positivem Koeffizienten werden nacheinander entfernt und das Modell neu gefittet.
4. Modell B als Benchmark: dieselben Variablen plus grade, sub_grade, int_rate und installment.
5. Score und PD für alle 1.348.099 Kredite nach `data/processed/scored_loans.parquet`, Scorecard-Tabellen
   nach `reports/scorecard_table_a.csv` und `_b.csv`.

### Was kam heraus

**Vorzeichen-Regel hat zwei Variablen entfernt:** loan_amnt (Koeffizient +0,21) und danach revol_util
(+0,08). Beide hängen eng mit anderen Modellvariablen zusammen (loan_amnt steckt in loan_to_income,
revol_util in bc_util). Sobald die stärkere Variable im Modell ist, dreht sich ihr Vorzeichen, und die
Scorecard würde größeren Krediten mehr Punkte geben. Das Hauptmodell A hat danach 15 Variablen, alle
mit negativem Koeffizienten.

**Scorecard Modell A, Punktespanne je Variable (max minus min über die Bins):**

| Variable | Koeffizient | Punkte min | Punkte max | Spanne |
|---|---|---|---|---|
| fico_range_low | -0,693 | 28 | 57 | 29 |
| term_months | -0,923 | 16 (60 Monate) | 44 (36 Monate) | 28 |
| acc_open_past_24mths | -0,833 | 22 | 46 | 24 |
| loan_to_income | -0,496 | 27 | 44 | 17 |
| dti | -0,480 | 28 | 41 | 13 |
| total_rev_hi_lim | -0,448 | 33 | 42 | 9 |
| inq_last_6mths | -0,541 | 30 | 38 | 8 |
| bc_util | -0,432 | 31 | 39 | 8 |
| mo_sin_old_rev_tl_op | -0,430 | 31 | 38 | 7 |
| mort_acc | -0,472 | 33 | 40 | 7 |
| mths_since_recent_inq | -0,398 | 32 | 38 | 6 |
| tot_cur_bal | -0,359 | 34 | 40 | 6 |
| home_ownership | -0,586 | 33 (RENT) | 38 (MORTGAGE) | 5 |
| annual_inc | -0,283 | 34 | 38 | 4 |
| verification_status | -0,263 | 34 | 38 | 4 |

Intercept -1,547. Theoretischer Score-Bereich 446 bis 621 Punkte, tatsächlich 453 bis 619. Mittelwert
535 im Training, 537 im Test, Standardabweichung 22. Ein Kredit mit 60 Monaten Laufzeit, FICO unter 662
und 10 neuen Konten in zwei Jahren verliert gegenüber dem besten Kunden allein aus diesen drei Variablen
81 Punkte, also 4 Verdopplungen der Ausfall-Odds.

**Erste Güte (vollständig in AP5):**

| Modell | AUC Train | AUC Test (2016 bis 2018) |
|---|---|---|
| A (Hauptmodell, 15 Variablen) | 0,706 | 0,688 |
| B (Benchmark mit grade, sub_grade, int_rate, installment) | 0,719 | 0,705 |

Der Test-AUC von 0,688 liegt im erwarteten Bereich von 0,68 bis 0,72 für Lending Club ohne grade. Der
Abstand zwischen Train und Test (0,018) ist die übliche Verschlechterung bei zeitlicher Trennung.
Bemerkenswert: Lending Clubs eigene Einstufung bringt im Benchmark nur 0,017 AUC mehr. Die eigenen
15 Antragsvariablen enthalten also den größten Teil der Information, die auch in grade steckt.

**Rechenbeispiel (Kredit 134492425 aus dem Test):** PD 0,0936, Odds gut zu schlecht 9,68.
Score = 487,12 + 28,85 x ln(9,68) = 552,6. Summe der gerundeten Bin-Punkte in der Scorecard: 552.

### Warum so entschieden

- **PDO 20, 600 Punkte bei Odds 50:1.** Lehrbuch-Parametrierung (Siddiqi, Credit Risk Scorecards). Sie ändert
  nichts an der Rangfolge, nur an der Skala. Alle 20 Punkte verdoppeln sich die Odds auf Rückzahlung.
- **Vorzeichen-Regel statt Behalten.** Eine Scorecard mit positivem Koeffizienten gibt Punkte in die
  falsche Richtung und wäre einem Kunden nicht erklärbar. Der AUC ändert sich durch das Entfernen
  praktisch nicht (0,6880 vor, 0,6884 nach), die Erklärbarkeit gewinnt.
- **Logistische Regression ohne Klassengewichte, Standard-Regularisierung.** Mit 15 WoE-Variablen und
  830.000 Zeilen gibt es keine Überanpassung. Ohne Gewichte bleiben die PDs im Mittel auf dem Niveau
  der echten Ausfallquote, was für Kalibrierung und EL-Rechnung entscheidend ist.
- **Punkte gerundet.** Echte Scorecards arbeiten mit ganzen Punkten. Der Rundungsfehler ist im
  Beispiel 0,6 Punkte.
- **installment nur im Benchmark.** Die Rate ist aus Betrag, Laufzeit und Zinssatz berechnet und trägt
  über den Zinssatz Lending Clubs Einstufung in sich.

### Abnahmekriterium AP4

Erfüllt. Die Scorecard-Tabelle mit Punkten je Bin liegt in `reports/scorecard_table_a.csv`, die
Umrechnung PD zu Score ist oben mit Formel und Beispiel erklärt, Modell B liegt als Benchmark vor.

---

## AP5: Modellgüte

### Was wurde gemacht

1. Trennschärfe für Modell A, Modell B und ein Gradient-Boosting-Benchmark, jeweils auf Train und Test:
   AUC, Gini, KS-Statistik, Brier-Score.
2. AUC-Prüfung gegen die vorab festgelegte Erwartung 0,68 bis 0,72, Abbruch bei über 0,85.
3. Kalibrierung: vorhergesagte PD gegen beobachtete Ausfallquote je PD-Dezil, für Train, Test und die
   drei Testjahre einzeln.
4. Gradient Boosting (HistGradientBoosting, 300 Bäume) auf exakt denselben 15 Rohvariablen wie Modell A.
5. PSI der Score-Verteilung Train gegen Test.
6. Charts: ROC-Kurve, Score-Verteilung Good vs. Bad, KS-Plot, Kalibrierungsplot.

### Was kam heraus

**Trennschärfe (`reports/model_metrics.csv`):**

| Modell | Stichprobe | AUC | Gini | KS | Brier |
|---|---|---|---|---|---|
| A Scorecard (15 Variablen, ohne grade) | Train | 0,706 | 0,412 | 0,299 | 0,137 |
| A Scorecard | **Test 2016–2018** | **0,688** | **0,377** | **0,270** | 0,163 |
| B Benchmark (mit grade, sub_grade, int_rate, installment) | Test | 0,705 | 0,411 | 0,296 | 0,160 |
| Gradient Boosting (gleiche 15 Variablen wie A) | Train | 0,722 | 0,445 | 0,322 | 0,135 |
| Gradient Boosting | Test | 0,696 | 0,393 | 0,282 | 0,161 |

- **AUC-Prüfung:** 0,688 liegt im erwarteten Bereich 0,68 bis 0,72. Kein Leckage-Signal, kein Abbruch.
- **Boosting bringt wenig:** +0,008 AUC im Test gegenüber der Scorecard, bei denselben Variablen. Im
  Training ist der Abstand größer (+0,016), das Boosting passt sich also stärker an die Vergangenheit an.
- **Lending Clubs eigene Einstufung bringt +0,017 AUC** (Modell B). Das ist der Wert der Information, die
  in grade und int_rate über die 15 Antragsvariablen hinaus steckt.

**Kalibrierung Modell A (`reports/calibration_table.csv`):**

| Segment | Kredite | mittlere PD | beobachtete Quote | Verhältnis beobachtet/PD |
|---|---|---|---|---|
| Train 2007–2015 | 829.355 | 18,45 % | 18,46 % | 1,00 |
| Test 2016–2018 | 518.744 | 17,62 % | 22,42 % | 1,27 |
| Test 2016 | 293.105 | 17,92 % | 23,29 % | 1,30 |
| Test 2017 | 169.321 | 17,44 % | 23,13 % | 1,33 |
| Test 2018 | 56.318 | 16,55 % | 15,76 % | 0,95 |

Je PD-Dezil im Test liegt die beobachtete Quote gleichmäßig 10 bis 43 % über der PD (Verhältnis 1,10
bis 1,43), die Rangfolge stimmt aber in jedem Dezil (5,9 % im besten, 46,4 % im schlechtesten Dezil).

Einordnung: Das ist kein Kalibrierungsfehler des Modells, sondern der Reifegrad-Effekt aus AP2. Im
Testzeitraum sind nur die bis Ende 2018 abgeschlossenen Kredite enthalten. Ein 2016 vergebener
60-Monats-Kredit ist 2018 nur abgeschlossen, wenn er entweder früh ausgefallen ist oder vorzeitig
komplett zurückgezahlt wurde, und frühe Ausfälle sind in dieser Auswahl überrepräsentiert. Die
"beobachtete Quote" von 22,4 % ist deshalb keine Lifetime-Ausfallquote des Jahrgangs, sondern nach
oben verzerrt. Beim Jahrgang 2018 (nur 11 % abgeschlossen) kippt es in die andere Richtung (0,95).
Die auf dem ausgereiften Training kalibrierte PD (Verhältnis 1,00) ist die bessere Schätzung der
Lifetime-PD. Was das Modell zusätzlich nicht abbildet: Sollte sich die Kreditqualität ab 2016 wirklich
verschlechtert haben (AP2 zeigt einen leichten Anstieg bei den 36-Monats-Krediten), unterschätzt die
PD das echte Risiko ein Stück weit. Für die EL-Rechnung in AP6 wird deshalb die Modell-PD verwendet und
diese Unsicherheit über die LGD-Sensitivität und die Cutoff-Tabelle sichtbar gemacht.

**Stabilität (PSI, `reports/psi_table.csv`):** PSI der Score-Verteilung Train gegen Test = 0,008,
weit unter der Warnschwelle 0,10. Die Score-Verteilung hat sich zwischen 2007–2015 und 2016–2018
praktisch nicht verschoben (Mittelwert 535 gegen 537). Nur die besten Scores ab 563 sind im Test etwas
häufiger (12,6 % statt 10,5 %).

**Charts in `reports/figures/`:** `roc_curve.png` (drei Modelle), `score_distribution.png` (Good vs.
Bad), `ks_plot.png` (KS = 0,270), `calibration_plot.png` (Train auf der Diagonalen, Test 2016/2017
parallel darüber, 2018 darunter).

### Warum so entschieden

- **Boosting mit denselben 15 Variablen,** nicht mit allen 32 Kandidaten. So misst der Vergleich den
  Algorithmus, nicht zusätzliche Daten. Keine Hyperparameter-Suche, weil es ein Benchmark ist.
- **Scorecard trotz Boosting.** +0,008 AUC rechtfertigen kein Modell, das weder ein Kunde noch ein
  Prüfer nachvollziehen kann. Die Scorecard hat feste Punkte je Bin, prüfbare Vorzeichen und Monotonie,
  läuft in jedem Kernbanksystem und lässt sich über die Zeit über PSI je Variable überwachen.
  Aufsichtlich (BaFin, EBA) und gegenüber Kunden (Begründungspflicht bei Ablehnung) ist das der
  entscheidende Punkt.
- **Kalibrierung auf der ausgereiften Basis akzeptiert, nicht auf den Test umgerechnet.** Eine
  Anpassung des Intercepts an die Testquote (Faktor 1,27) würde eine zensierte, nach oben verzerrte
  Quote als Wahrheit nehmen. Die Verzerrung ist dokumentiert, die Rangfolge stimmt, und die
  Unsicherheit wird in AP6/AP7 über Sensitivitäten gezeigt.
- **PSI mit Train-Dezilen als Referenz,** Standardvorgehen, 10 Bins.

### Abnahmekriterium AP5

Erfüllt. AUC, Gini, KS, Brier, Kalibrierung je Dezil und Jahr, Boosting-Vergleich und PSI sind
berechnet und liegen in `reports/model_metrics.csv`, `calibration_table.csv`, `psi_table.csv`. Die
Prüfung "AUC zwischen 0,68 und 0,72, nicht über 0,85" ist mit 0,688 positiv.

---

## AP6: Expected Loss

### Was wurde gemacht

1. LGD empirisch aus den 269.360 ausgefallenen Krediten geschätzt, aus `lgd_inputs.parquet` (AP1):
   LGD = 1 - (recoveries + total_rec_prncp) / funded_amnt, auf 0 bis 1 gekappt. Mittelwert, Median,
   volumengewichtet, nach Stichprobe, Laufzeit und Grade. Verteilung als Chart.
2. PD aus Modell A, EAD = funded_amnt, EL = PD x LGD x EAD je Kredit.
3. Portfolio-EL absolut und in Prozent des Volumens für gesamt, Train und Test.
4. Backtest auf dem ausgereiften Trainingsportfolio: Modell-EL gegen tatsächlich realisierten Verlust.
5. Sensitivität mit LGD 30 %, empirisch, 60 %.

### Was kam heraus

**LGD (`reports/lgd_summary.csv`):**

| Segment | Ausfälle | LGD Mittelwert | LGD Median | volumengewichtet |
|---|---|---|---|---|
| alle Ausfälle | 269.360 | **62,2 %** | 66,4 % | 64,0 % |
| Train 2007–2015 (ausgereift) | 153.065 | 56,9 % | 60,3 % | 58,5 % |
| Test 2016–2018 | 116.295 | 69,2 % | 72,9 % | 71,2 % |
| 36 Monate | 163.926 | 57,3 % | 60,5 % | 57,8 % |
| 60 Monate | 105.434 | 69,9 % | 73,7 % | 70,1 % |
| Grade A | 14.214 | 52,3 % | 54,2 % | 53,0 % |
| Grade G | 4.632 | 75,4 % | 79,0 % | 76,0 % |

Nur 0,4 % der Ausfälle sind Totalverluste (LGD über 99 %) und 0,4 % wurden praktisch vollständig
zurückgeholt. Der größte Teil des Rückflusses ist der vor dem Ausfall getilgte Kapitalanteil, nicht die
Verwertung nach Ausfall. Die LGD steigt mit Laufzeit und Grade: Schlechte Grades fallen früher aus und
haben bis dahin weniger getilgt. Aus demselben Grund liegt die LGD im Test (nur frühe Ausfälle) mit
69,2 % über dem ausgereiften Training (56,9 %).

**Expected Loss (`reports/expected_loss_summary.csv`), LGD 62,2 %:**

| Portfolio | Kredite | Volumen | mittlere PD | EL absolut | EL in % des Volumens |
|---|---|---|---|---|---|
| gesamt 2007–2018 | 1.348.099 | 19,41 Mrd. USD | 18,1 % | 2.353 Mio. USD | 12,12 % |
| Train 2007–2015 (ausgereift) | 829.355 | 11,91 Mrd. USD | 18,5 % | 1.466 Mio. USD | 12,30 % |
| **Test 2016–2018 (zeitlich getrennt)** | 518.744 | 7,50 Mrd. USD | 17,6 % | **887 Mio. USD** | **11,83 %** |

Diese PD ist eine PD über die gesamte Laufzeit, keine 12-Monats-PD. Der EL ist deshalb ein
Lifetime-EL und liegt entsprechend hoch. Zum Vergleich: Ein Portfolio mit 12 % Lifetime-Verlust bei
einem mittleren Zinssatz von rund 13 % über 3 bis 5 Jahre ist für unbesicherte Konsumentenkredite
plausibel.

**Backtest Train (ausgereift):** Modell-EL 1.465,8 Mio. USD (12,30 % des Volumens) gegen
realisierten Verlust 1.382,8 Mio. USD (11,61 %), Verhältnis 0,943. Das Modell liegt also 6 % über dem
tatsächlichen Verlust, weil die verwendete LGD (62,2 % über alle Ausfälle) über der LGD der
ausgereiften Kredite (56,9 %) liegt. Leicht konservativ, das ist für Risikovorsorge die richtige Seite.
Im Test steht der bisher realisierte Verlust (17,30 %) über dem Modell-EL (11,83 %), aber diese Zahl
ist wegen der Zensierung (nur frühe Ausfälle enthalten, Rückzahlungen noch offen) keine Lifetime-Quote.

**Sensitivität (Testportfolio, 7,50 Mrd. USD):**

| LGD | EL absolut | EL in % |
|---|---|---|
| 30 % | 428 Mio. USD | 5,71 % |
| 62,2 % (empirisch) | 887 Mio. USD | 11,83 % |
| 60 % | 856 Mio. USD | 11,41 % |

Die LGD ist der Hebel mit der größten Unsicherheit: Zwischen 30 % und 60 % verdoppelt sich der EL.
Zum Basel-Referenzwert 45 %: Das ist der Foundation-IRB-Wert für senior unbesicherte Forderungen an
Staaten, Banken und Unternehmen, kein Retail-Wert. Die empirischen 62 % für unbesicherte
US-Konsumentenkredite sind höher, was plausibel ist (keine Sicherheiten, keine Aufrechnung).

### Warum so entschieden

- **LGD als eine Zahl für das ganze Portfolio (62,2 %, Mittelwert über alle Ausfälle).** Eine LGD je
  Laufzeit oder Grade wäre genauer (57 % bis 70 %), würde aber Cutoff-Analyse und Excel-Rechner
  komplizierter machen. Der Mittelwert über alle Ausfälle ist etwas höher als der über die ausgereiften
  (56,9 %), also konservativ; der Backtest (0,943) zeigt, dass der Fehler klein ist. Die
  Segmentwerte stehen in `reports/lgd_summary.csv`, wer sie braucht, tauscht die Spalte `lgd` in
  `05_expected_loss.py` aus.
- **Inkassogebühr nicht abgezogen.** `collection_recovery_fee` ist im Datensatz nicht sauber vom Erlös zu
  trennen. Die LGD ist dadurch minimal zu niedrig; die 60-%-Sensitivität deckt das ab.
- **Werte außerhalb 0 bis 1 gekappt.** Ein paar Kredite haben Rückflüsse über der Auszahlung (Zinsen
  vor dem Ausfall); eine negative LGD ergibt keinen Sinn.
- **EAD = funded_amnt.** Bei Ratenkrediten ohne Rahmen ist das Exposure bei Vergabe die Auszahlung. Der
  Restsaldo zum Ausfallzeitpunkt wäre niedriger, steht aber nur in Leckage-Spalten. Die Annahme ist
  konservativ (EL eher zu hoch). Sie überschneidet sich teilweise mit der LGD-Formel, in der die Tilgung
  vor Ausfall bereits als Rückfluss zählt; das Produkt PD x LGD x funded_amnt ist deshalb konsistent.
- **Leckage-Spalten nur hier.** recoveries und total_rec_prncp kommen aus `lgd_inputs.parquet`, das
  nur ausgefallene Kredite enthält. Das PD-Modell hat diese Datei nie gesehen.
- **Modell-PD, keine Nachkalibrierung auf den Test.** Begründung in AP5.

### Abnahmekriterium AP6

Erfüllt. Portfolio-EL steht als Zahl (887 Mio. USD im Testportfolio, 2.353 Mio. USD gesamt) und als
Prozentsatz (11,83 % bzw. 12,12 % des Volumens), die LGD-Herleitung mit Formel, Verteilung und
Segmenten ist dokumentiert, die Sensitivität ist gerechnet.
