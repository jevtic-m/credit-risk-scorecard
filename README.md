# Credit Risk Scorecard & Portfolio Dashboard

**Business-Frage:** Wo sollte eine Bank ihren Annahme-Cutoff setzen?

**Kernergebnis:** Ein Cutoff bei Score [X] senkt den Expected Loss von [A] % auf [B] % des Portfoliovolumens und kostet [Z] % des genehmigten Volumens.

**Stack:** DuckDB (SQL) · Python (optbinning, scikit-learn) · Power BI · Excel

---

## Daten

Lending Club, angenommene Kredite 2007–2018, 1.348.099 Kredite nach Filterung, Kaggle-Datensatz `wordsforthewise/lending-club`, Lizenz CC0 (Public Domain).

| Schritt | Kredite |
|---|---|
| Rohdatei | 2.260.701 (davon 33 Summenzeilen ohne Kredit) |
| Nach Filter auf abgeschlossene Kredite (Fully Paid, Charged Off, Default) | 1.348.099 |
| Ausfallquote im bereinigten Datensatz | 19,98 % (269.360 Ausfälle) |
| Zeitraum (issue_d) | Juni 2007 bis Dezember 2018 |

Ausgeschlossen: laufende Kredite (Current, Late, In Grace Period), weil ihr Ausgang noch offen ist. Würde man sie als "gut" werten, wäre die Ausfallquote systematisch zu niedrig (Zensierungsproblem).

Ausgeschlossen: 38 Spalten, die erst nach der Kreditvergabe entstehen (Zahlungen, Rückflüsse, Härtefall- und Vergleichsdaten). Die vollständige Liste steht in `02_python/01_data_prep.py` und in `reports/findings.md`.

## Methodik

1. SQL-Analyse: Ausfallquoten nach Segment, Vintage-Kurven, Kohorten
2. Feature-Auswahl unter strikter Vermeidung von Datenleckage
3. WoE-Binning und Information Value
4. Logistische Scorecard mit PDO-Skalierung
5. Modellgüte: AUC/Gini, KS, Kalibrierung, PSI
6. Expected Loss mit empirisch geschätzter LGD
7. Cutoff-Analyse

## Ergebnisse

**AP1 – Datenbasis:** Von 2.260.701 Zeilen der Rohdatei bleiben 1.348.099 Kredite mit bekanntem Ausgang. Davon sind 269.360 ausgefallen, die Ausfallquote liegt bei 19,98 %. Kredite mit 60 Monaten Laufzeit fallen mit 32,45 % etwa doppelt so oft aus wie 36-Monats-Kredite mit 16,02 %. Das bereinigte Portfolio hat ein ausgezahltes Volumen von 19,41 Mrd. USD. 38 Spalten wurden als Datenleckage ausgeschlossen, 41 Spalten bleiben in `data/processed/loans_clean.parquet`.

[Weitere Ergebnisse folgen mit AP2 bis AP8.]

## Annahmen und Limitationen

- PD über Gesamtlaufzeit, keine 12-Monats-PD
- EAD als funded_amnt approximiert
- LGD empirisch geschätzt, Sensitivität gerechnet
- Vintages ab [Jahr] nicht vollständig gereift
- US-Verbraucherkredite, nicht direkt auf deutsche Portfolios übertragbar
- `grade`, `sub_grade` und `int_rate` sind Lending Clubs eigene Risikoeinstufung und stehen nicht im Hauptmodell (nur im Benchmark-Modell)

## Reproduktion

Voraussetzung: Python 3.11 oder neuer, Git, ca. 5 GB freier Plattenplatz.

1. Repo klonen und Rohdatei ablegen:
   Kaggle-Datensatz `wordsforthewise/lending-club` herunterladen und die Datei
   `accepted_2007_to_2018Q4.csv.gz` nach `data/raw/` legen (nicht entpacken).
2. Virtuelle Umgebung anlegen und Pakete installieren:
   ```bash
   python -m venv .venv
   .venv/Scripts/python.exe -m pip install -r requirements.txt
   ```
   (Unter macOS/Linux: `.venv/bin/python` statt `.venv/Scripts/python.exe`.)
3. AP1 – Daten laden, Zielvariable, Leckage-Filter, bereinigte Parquet-Datei:
   ```bash
   .venv/Scripts/python.exe 02_python/01_data_prep.py
   ```
   Erzeugt `data/credit.duckdb` und `data/processed/loans_clean.parquet`.
   Die SQL-Exploration aus AP1 steht in `01_sql/01_exploration.sql` und wird vom Skript mit ausgeführt.

[Weitere Schritte folgen mit AP2 bis AP8.]
