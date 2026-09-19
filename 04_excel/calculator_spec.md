# Excel-Policy-Rechner: Aufbau und Formeln

Eine Arbeitsmappe `policy_calculator.xlsx` (wird von Hand gebaut, nicht im Repo) mit zwei Blättern.
Datengrundlage: `04_excel/score_bands.csv` (Testportfolio 2016–2018, 17 Score-Bänder à 10 Punkte).
Für das Gesamtportfolio gibt es `score_bands_full_portfolio.csv` mit gleichem Aufbau.

## Blatt "Daten": score_bands.csv eingefügt ab Zelle A1

| Spalte | Inhalt |
|---|---|
| A band_lower | Untergrenze des Score-Bands (450, 460, ..., 610) |
| B band_upper | Obergrenze (459, 469, ..., 619) |
| C loans | Anzahl Kredite im Band |
| D volume_usd | Summe funded_amnt im Band |
| E defaults | Anzahl tatsächlich ausgefallener Kredite im Band |
| F observed_default_rate | E / C |
| G avg_pd | mittlere Modell-PD im Band |
| H expected_loss_usd | Summe EL im Band, gerechnet mit LGD 0,622 |
| I el_rate | H / D |

Zeilen 2 bis 18 sind die 17 Bänder. Zelle C20 = SUMME(C2:C18) (alle Kredite), D20 = SUMME(D2:D18)
(Gesamtvolumen), H20 = SUMME(H2:H18) (EL ohne Cutoff).

Wichtig: `expected_loss_usd` ist mit der empirischen LGD 0,622 gerechnet. Für eine andere LGD wird der
EL proportional skaliert: EL(LGD) = EL x LGD / 0,622. Das ist exakt, weil im Modell eine LGD für alle
Kredite gilt.

## Blatt "Rechner"

### Eingaben (gelb hinterlegt)

| Zelle | Inhalt | Standardwert | Zulässig |
|---|---|---|---|
| B3 | Cutoff-Score (Kredite mit Score >= Cutoff werden angenommen) | 515 | 450 bis 620, Schritt 10 (Bandgrenzen) |
| B4 | LGD-Annahme | 0,622 | 0,30 bis 0,70 |
| B5 | Zielvolumen in USD (optional, für den Vergleich) | 6.000.000.000 | > 0 |

Datenüberprüfung für B3: Liste 450;460;...;610. Zwischenwerte wie 515 sind mit 10er-Bändern nicht
abbildbar; wer 5er-Schritte braucht, erzeugt `score_bands.csv` mit `width=5` in
`02_python/06_cutoff_analysis.py` (Funktion `score_bands`).

### Berechnung (grau hinterlegt, Formeln geschützt)

| Zelle | Bezeichnung | Formel |
|---|---|---|
| B8 | Angenommene Kredite | `=SUMMEWENNS(Daten!C:C;Daten!A:A;">="&B3)` |
| B9 | Annahmequote | `=B8/Daten!C20` |
| B10 | Genehmigtes Volumen (USD) | `=SUMMEWENNS(Daten!D:D;Daten!A:A;">="&B3)` |
| B11 | Anteil am Gesamtvolumen | `=B10/Daten!D20` |
| B12 | Verlorenes Volumen (USD) | `=Daten!D20-B10` |
| B13 | Erwarteter Verlust angenommen (USD) | `=SUMMEWENNS(Daten!H:H;Daten!A:A;">="&B3)*B4/0,622` |
| B14 | Verlustquote (EL in % des genehmigten Volumens) | `=B13/B10` |
| B15 | Tatsächlich ausgefallene Kredite im angenommenen Portfolio | `=SUMMEWENNS(Daten!E:E;Daten!A:A;">="&B3)` |
| B16 | Beobachtete Ausfallquote angenommen | `=B15/B8` |
| B17 | Abgelehnte Ausfälle (Anteil aller Ausfälle) | `=1-B15/SUMME(Daten!E2:E18)` |
| B18 | Abgelehnte gute Kredite (Anteil aller Guten) | `=(SUMMEWENNS(Daten!C:C;Daten!A:A;"<"&B3)-SUMMEWENNS(Daten!E:E;Daten!A:A;"<"&B3))/(Daten!C20-SUMME(Daten!E2:E18))` |

### Vergleich zum Status quo (kein Cutoff)

| Zelle | Bezeichnung | Formel |
|---|---|---|
| D8 | EL ohne Cutoff (USD) | `=Daten!H20*B4/0,622` |
| D9 | Verlustquote ohne Cutoff | `=D8/Daten!D20` |
| D10 | Gesparter EL (USD) | `=D8-B13` |
| D11 | Senkung der Verlustquote | `=1-B14/D9` |
| D12 | Volumen gegenüber Ziel | `=B10-B5` (negativ = Zielvolumen wird verfehlt) |
| D13 | EL je 1 USD verlorenes Volumen | `=WENN(B12>0;D10/B12;"")` |

### Kontrollwerte (LGD 0,622, Testportfolio)

| Cutoff | Annahmequote | Genehmigtes Volumen | Verlustquote | EL ohne Cutoff |
|---|---|---|---|---|
| 450 (alle) | 100,0 % | 7,50 Mrd. USD | 11,83 % | 11,83 % |
| 510 | 88,7 % | 6,38 Mrd. USD | 9,39 % | 11,83 % |
| 520 | 79,2 % | 5,54 Mrd. USD | 8,18 % | 11,83 % |

Die Werte müssen mit `reports/cutoff_table.csv` (Portfolio test, Cutoffs 510 und 520) übereinstimmen.

### Optik

- Eingaben B3:B5 gelb (RGB 255, 242, 204), Ausgaben grau (RGB 242, 242, 242).
- Blatt schützen, nur B3:B5 entsperrt.
- Kleines Diagramm rechts neben dem Rechner: Punkt-Linie mit X = band_lower (Daten!A2:A18) und
  Y = kumulierte Verlustquote je möglichem Cutoff. Dafür Hilfsspalten im Blatt Daten:
  - J2: `=SUMMEWENNS($H$2:$H$18;$A$2:$A$18;">="&A2)/SUMMEWENNS($D$2:$D$18;$A$2:$A$18;">="&A2)` (Verlustquote bei Cutoff A2), nach unten kopieren
  - K2: `=SUMMEWENNS($C$2:$C$18;$A$2:$A$18;">="&A2)/$C$20` (Annahmequote bei Cutoff A2), nach unten kopieren
  - Diagramm: X = A2:A18, Y1 = J2:J18 (Verlustquote), Y2 = K2:K18 (Annahmequote, Sekundärachse).
- Eine Textzeile über dem Rechner: "PD über die Laufzeit aus der Scorecard (AUC 0,69), LGD empirisch
  62,2 %, EAD = Auszahlung. Testportfolio 2016–2018, 518.744 Kredite."
