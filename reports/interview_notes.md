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

---

## Nach AP2 (SQL)

**Was ist eine Vintage-Analyse und wozu braucht man sie?**

Eine Vintage-Analyse gruppiert Kredite nach ihrem Ausgabezeitraum (Jahrgang, Quartal) und vergleicht,
wie sich die Ausfallquote je Jahrgang entwickelt. Man braucht sie, um zu erkennen, ob sich die Qualität
des Neugeschäfts verändert hat, unabhängig davon, wie groß das Portfolio insgesamt ist. In diesem
Repo zeigt sie zum Beispiel, dass die 36-Monats-Kredite von 2010 bis 2015 langsam von 10,9 % auf
14,9 % Ausfallquote gestiegen sind, während das Neugeschäft je Quartal um mehr als das Zehnfache
gewachsen ist.

**Warum ist die Ausfallquote der Vintages von 2018 niedriger als die von 2014?**

Weil der Datensatz im Dezember 2018 endet und die Kredite von 2018 ihre Laufzeit noch gar nicht
durchlaufen haben. In den Daten mit bekanntem Ausgang stehen von 2018 nur 56.318 von 495.242 Krediten,
und zwar die, die früh zurückgezahlt oder früh ausgefallen sind. Die Quote von 15,8 % sagt deshalb
nichts über den Jahrgang aus. Vergleichbar sind nur ausgereifte Jahrgänge: 36-Monats-Kredite bis 2015,
60-Monats-Kredite bis 2013. Bei 2014 ist die Quote der abgeschlossenen Kredite sogar höher (18,45 %) als
die der ausgereiften (13,73 %), weil die noch laufenden 60-Monats-Kredite in der ausgereiften Menge fehlen.

**Wann brauchst du eine Window Function statt GROUP BY?**

GROUP BY verdichtet mehrere Zeilen zu einer Zeile pro Gruppe. Eine Window Function rechnet über eine
Gruppe von Zeilen, lässt die Zeilen aber bestehen. Ich brauche sie, wenn eine Zeile einen Wert aus
anderen Zeilen sehen muss: In Abfrage 13 holt LAG den Vorjahreswert in dieselbe Zeile, um die Veränderung
zu berechnen. In Abfrage 15 bildet SUM() OVER (ORDER BY grade) die kumulierte Summe von A nach G, so dass
in der Zeile für C steht, dass A bis C 71,5 % des Volumens sind. Mit GROUP BY allein ginge beides nicht.

---

## Nach AP3 (Binning)

**Was ist Weight of Evidence und warum passt es zur logistischen Regression?**

WoE eines Bins ist der Logarithmus aus "Anteil der Guten im Bin" geteilt durch "Anteil der Schlechten im
Bin". Bei fico_range_low ab 752 ist der WoE zum Beispiel +1,06 (nur 7,3 % Ausfälle), unter 662 ist er
-0,38 (24,8 % Ausfälle). Die logistische Regression modelliert genau die Log-Odds, also den Logarithmus
des Verhältnisses gut zu schlecht. WoE bringt jede Variable, egal ob Zahl oder Kategorie, auf dieselbe
Log-Odds-Skala. Dadurch braucht die Regression keine Dummy-Variablen und die Koeffizienten sind direkt
vergleichbar.

**Ab welchem IV wirst du misstrauisch statt zufrieden?**

Ab 0,5. Im Kreditrisiko ist keine einzelne Antragsvariable so stark, dass sie allein den Ausfall fast
erklärt. Ein IV über 0,5 heißt fast immer, dass die Variable Wissen aus der Zukunft enthält, zum Beispiel
Rückzahlungen. In meinem Hauptmodell liegt die stärkste Variable, term_months, bei 0,238. Selbst Lending
Clubs eigene Einstufung sub_grade kommt nur auf 0,498, und die ist ja schon ein ganzes Modell. Wenn eine
meiner Variablen 0,8 hätte, würde ich zuerst nach dem Datenfehler suchen, nicht feiern.

**Warum imputierst du fehlende Werte nicht?**

Weil "fehlt" im Kreditrisiko selbst eine Information ist. optbinning legt für jede Variable einen eigenen
Missing-Bin an und schätzt dessen Ausfallquote. Bei acc_open_past_24mths fehlt der Wert bei 50.030
Trainingskrediten, und diese Gruppe hat mit 15,3 % eine deutlich andere Ausfallquote als der
Durchschnitt von 18,5 %. Würde ich den Median einsetzen, würde ich diese Gruppe in einen Bin mischen, zu
dem sie nicht gehört, und die Information verlieren.

**Warum hast du zeitbasiert statt zufällig gesplittet?**

Weil das Modell im Einsatz künftige Kredite bewertet, nicht eine Zufallsstichprobe der Vergangenheit. Ich
trainiere auf 2007 bis 2015 (829.355 Kredite) und teste auf 2016 bis 2018 (518.744 Kredite). Ein
zufälliger Split hätte Kredite aus demselben Monat in beide Teile gelegt, und das Modell hätte davon
profitiert, dass sich Konjunktur und Vergabepolitik in Train und Test gleichen. Der zeitbasierte Test ist
härter: Die Ausfallquote im Test liegt mit 22,4 % über den 18,5 % im Training, und genau diese
Verschiebung muss ein Modell in der Praxis aushalten.
