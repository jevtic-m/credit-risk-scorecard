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
