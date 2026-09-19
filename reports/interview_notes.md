# Interview-Notizen

Die Fragen sind typische Interviewfragen zu jedem Arbeitspaket. Jede Antwort bezieht sich auf die echten
Ergebnisse dieses Repos (Zahlen aus `reports/ap1_summary.md` und `reports/findings.md`).

---

## Nach AP1 (Daten)

**Warum schließt du laufende Kredite aus?**

Bei laufenden Krediten (Current, Late, In Grace Period) ist noch nicht bekannt, ob sie zurückgezahlt
werden oder ausfallen. Das sind 912.569 der 2,26 Mio. Kredite, also 40 %. Würde ich sie als "gut"
werten, läge die Ausfallquote bei etwa 12 % statt bei den tatsächlichen 19,98 % der abgeschlossenen
Kredite. Das ist ein Zensierungsproblem: Man sieht das Ergebnis noch nicht, darf es aber nicht mit
"kein Ausfall" verwechseln.

**Was ist Datenleckage und welche Spalten waren bei dir betroffen?**

Datenleckage heißt, dass das Modell Informationen benutzt, die es zum Entscheidungszeitpunkt gar nicht
haben kann. Bei Lending Club sind das alle Spalten, die erst während der Laufzeit oder nach einem Ausfall
entstehen. Ich habe 38 Spalten explizit ausgeschlossen: Zahlungen und Rückflüsse (`total_pymnt`,
`total_rec_prncp`, `total_rec_int`), Verwertungserlöse (`recoveries`), letzte und nächste Zahlung,
offener Restsaldo (`out_prncp`), später neu abgerufene FICO-Werte (`last_fico_range_*`), 15
Härtefall-Spalten und 7 Vergleichs-Spalten (`settlement_*`). Die Liste steht als Python-Liste im Code,
und das Skript bricht ab, wenn ein Name darin nicht in der Rohdatei existiert.

**Warum ist `recoveries` problematisch, obwohl es doch Information über den Verlust enthält?**

`recoveries` ist der Betrag, den die Bank nach einem Ausfall noch eintreiben konnte. Der Wert ist nur bei
ausgefallenen Krediten größer als null. Ein Modell, das diese Spalte sieht, würde den Ausfall daran fast
perfekt "erkennen", aber bei einem neuen Antrag ist der Wert immer null, weil noch nichts passiert ist.
Für die Ausfallwahrscheinlichkeit ist die Spalte deshalb wertlos und gefährlich. Für die Verlusthöhe
nach Ausfall (LGD) ist sie dagegen genau richtig, weil dort der Ausfall schon eingetreten ist. Deshalb
liegt sie in einer eigenen Datei (`lgd_inputs.parquet`, nur die 269.360 ausgefallenen Kredite) und nicht
in den Modelldaten.

**Zusatzfrage, die sich aus den Daten ergibt: Warum ist die Ausfallquote des Jahrgangs 2018 mit
15,76 % niedriger als die von 2016 mit 23,29 %?**

Weil von 2018 erst 56.318 von 495.242 Krediten abgeschlossen sind, also 11 %. Abgeschlossen sind
bisher vor allem Kredite, die sehr früh zurückgezahlt oder sehr früh ausgefallen sind. Der Jahrgang ist
nicht ausgereift, die Quote ist deshalb nicht vergleichbar. In AP2 wird das über die Vintage-Analyse mit
Reifegrad-Hinweis sauber behandelt.
