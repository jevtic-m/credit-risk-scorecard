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
